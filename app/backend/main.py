import asyncio
import logging
from contextlib import asynccontextmanager, suppress

from fastapi import FastAPI

from app.config import config
from app.discord_bot.bot import client

logger = logging.getLogger(__name__)


def _log_task_result(task: asyncio.Task) -> None:
    if task.cancelled():
        logger.info("Discord task was cancelled.")
        return

    exc = task.exception()
    if exc is not None:
        logger.exception("Discord task crashed.", exc_info=exc)
    else:
        logger.info("Discord task exited.")


@asynccontextmanager
async def lifespan(app: FastAPI):
    if not config.bot.token:
        raise RuntimeError(
            "DISCORD_TOKEN is missing. Set it in your environment or .env file."
        )

    logger.info("Starting application...")
    bot_task = asyncio.create_task(client.start(config.bot.token), name="discord-bot")
    bot_task.add_done_callback(_log_task_result)
    logger.info("Application started.")
    try:
        yield
    finally:
        logger.info("Stopping application...")
        await client.close()
        bot_task.cancel()
        with suppress(asyncio.CancelledError):
            await bot_task
        logger.info("Application stopped.")


app = FastAPI(lifespan=lifespan)
