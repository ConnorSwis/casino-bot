import asyncio
import logging
from collections import deque
from contextlib import asynccontextmanager, suppress
from pathlib import Path
from time import monotonic

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from app.backend.demo_runtime import DemoRuntimeManager
from app.common import setup_logging

setup_logging()

from app.config import config

logger = logging.getLogger(__name__)
STATIC_DIR = Path(__file__).resolve().parent / "static"
DEMO_INDEX = STATIC_DIR / "demo" / "index.html"
demo_runtime = DemoRuntimeManager()

DEMO_RATE_WINDOW_SECONDS = 15.0
DEMO_RATE_MAX_IP_REQUESTS = 60
DEMO_RATE_MAX_SESSION_REQUESTS = 36
DEMO_RATE_MAX_IP_IN_FLIGHT = 10
DEMO_RATE_MAX_SESSION_IN_FLIGHT = 4

_rate_lock = asyncio.Lock()
_ip_timestamps: dict[str, deque[float]] = {}
_session_timestamps: dict[str, deque[float]] = {}
_ip_in_flight: dict[str, int] = {}
_session_in_flight: dict[str, int] = {}


class DemoCommandRequest(BaseModel):
    session_id: str = Field(min_length=8, max_length=128)
    command: str = Field(min_length=1, max_length=300)


class DemoActionRequest(BaseModel):
    session_id: str = Field(min_length=8, max_length=128)
    action: dict[str, object]


class DemoResetRequest(BaseModel):
    session_id: str = Field(min_length=8, max_length=128)


def _log_task_result(task: asyncio.Task) -> None:
    if task.cancelled():
        logger.info("Discord task was cancelled.")
        return

    exc = task.exception()
    if exc is not None:
        logger.exception("Discord task crashed.", exc_info=exc)
    else:
        logger.info("Discord task exited.")


def _prune_expired(timestamps: deque[float], now: float) -> None:
    cutoff = now - DEMO_RATE_WINDOW_SECONDS
    while timestamps and timestamps[0] < cutoff:
        timestamps.popleft()


def _client_key(request: Request) -> str:
    client = request.client
    if client is None or not client.host:
        return "unknown"
    return client.host


async def _acquire_rate_limit_slot(
    request: Request,
    *,
    session_id: str | None = None,
) -> tuple[str, str | None]:
    ip_key = _client_key(request)
    now = monotonic()

    async with _rate_lock:
        ip_times = _ip_timestamps.setdefault(ip_key, deque())
        _prune_expired(ip_times, now)
        ip_in_flight = _ip_in_flight.get(ip_key, 0)

        if len(ip_times) >= DEMO_RATE_MAX_IP_REQUESTS or ip_in_flight >= DEMO_RATE_MAX_IP_IN_FLIGHT:
            raise HTTPException(status_code=429, detail="Too many demo API requests. Slow down.")

        session_times: deque[float] | None = None
        session_in_flight = 0
        if session_id:
            session_times = _session_timestamps.setdefault(session_id, deque())
            _prune_expired(session_times, now)
            session_in_flight = _session_in_flight.get(session_id, 0)
            if (
                len(session_times) >= DEMO_RATE_MAX_SESSION_REQUESTS
                or session_in_flight >= DEMO_RATE_MAX_SESSION_IN_FLIGHT
            ):
                raise HTTPException(status_code=429, detail="Demo session is rate limited. Slow down.")

        ip_times.append(now)
        _ip_in_flight[ip_key] = ip_in_flight + 1

        if session_id and session_times is not None:
            session_times.append(now)
            _session_in_flight[session_id] = session_in_flight + 1

    return ip_key, session_id


async def _release_rate_limit_slot(slot: tuple[str, str | None]) -> None:
    ip_key, session_id = slot
    async with _rate_lock:
        ip_in_flight = _ip_in_flight.get(ip_key, 0)
        if ip_in_flight <= 1:
            _ip_in_flight.pop(ip_key, None)
        else:
            _ip_in_flight[ip_key] = ip_in_flight - 1

        if session_id:
            session_in_flight = _session_in_flight.get(session_id, 0)
            if session_in_flight <= 1:
                _session_in_flight.pop(session_id, None)
            else:
                _session_in_flight[session_id] = session_in_flight - 1


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting application...")
    bot_task: asyncio.Task | None = None
    bot_client = None
    if config.bot.token:
        from app.discord_bot.bot import client as discord_client

        bot_client = discord_client
        bot_task = asyncio.create_task(
            bot_client.start(config.bot.token),
            name="discord-bot",
        )
        bot_task.add_done_callback(_log_task_result)
        logger.info("Discord bot startup initiated.")
    else:
        logger.warning(
            "DISCORD_TOKEN is missing. Running web-only mode; Discord bot will not start."
        )

    logger.info("Application started.")
    try:
        yield
    finally:
        logger.info("Stopping application...")
        if bot_task is not None and bot_client is not None:
            await bot_client.close()
            bot_task.cancel()
            with suppress(asyncio.CancelledError):
                await bot_task
        logger.info("Application stopped.")


app = FastAPI(lifespan=lifespan)

if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


def _serve_demo_index() -> FileResponse:
    if not DEMO_INDEX.exists():
        raise HTTPException(status_code=404, detail="Demo page not found.")
    return FileResponse(DEMO_INDEX)


@app.get("/", include_in_schema=False)
async def home_page() -> FileResponse:
    return _serve_demo_index()


@app.get("/demo", include_in_schema=False)
async def demo_page() -> FileResponse:
    return _serve_demo_index()


@app.get("/api/demo/config")
async def demo_config(request: Request) -> dict[str, int | str]:
    slot = await _acquire_rate_limit_slot(request)
    try:
        return {
            "prefix": config.bot.prefix,
            "defaultBet": config.bot.default_bet,
            "bonusMultiplier": config.bot.bonus_multiplier,
            "bonusCooldownHours": config.bot.bonus_cooldown,
        }
    finally:
        await _release_rate_limit_slot(slot)


@app.post("/api/demo/command")
async def demo_command(request: Request, payload: DemoCommandRequest) -> dict[str, object]:
    slot = await _acquire_rate_limit_slot(request, session_id=payload.session_id)
    try:
        session = await demo_runtime.get_session(payload.session_id)
        return await session.run_command(payload.command)
    finally:
        await _release_rate_limit_slot(slot)


@app.post("/api/demo/action")
async def demo_action(request: Request, payload: DemoActionRequest) -> dict[str, object]:
    slot = await _acquire_rate_limit_slot(request, session_id=payload.session_id)
    try:
        session = await demo_runtime.get_session(payload.session_id)
        return await session.run_action(payload.action)
    finally:
        await _release_rate_limit_slot(slot)


@app.post("/api/demo/reset")
async def demo_reset(request: Request, payload: DemoResetRequest) -> dict[str, object]:
    slot = await _acquire_rate_limit_slot(request, session_id=payload.session_id)
    try:
        session = await demo_runtime.get_session(payload.session_id)
        return await session.reset()
    finally:
        await _release_rate_limit_slot(slot)


@app.get("/api/demo/assets/{asset_id}")
async def demo_asset(request: Request, asset_id: str) -> Response:
    slot = await _acquire_rate_limit_slot(request)
    try:
        asset = demo_runtime.get_asset(asset_id)
        if asset is None:
            raise HTTPException(status_code=404, detail="Asset not found.")
        return Response(content=asset.data, media_type=asset.content_type)
    finally:
        await _release_rate_limit_slot(slot)
