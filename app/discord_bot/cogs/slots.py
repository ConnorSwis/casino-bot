import asyncio
from contextlib import suppress
from dataclasses import dataclass
from io import BytesIO
import logging
from pathlib import Path
import random
import ssl
from uuid import uuid4

import aiohttp
import discord
from discord.ext import commands
from PIL import Image

from app.config import config
from app.discord_bot.modules.betting import (
    validate_credits_available,
    validate_credits_bet,
    validate_money_available,
    validate_positive_amount,
)
from app.discord_bot.modules.economy import Economy
from app.discord_bot.modules.helpers import (
    ABS_PATH,
    make_embed,
)
from app.discord_bot.modules.wallet_logging import log_wallet_change

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class SlotRenderSettings:
    frame_count: int
    frame_duration_ms: int
    delays: tuple[float, float, float]


class Slots(commands.Cog):
    # Symbol id (0-5) payouts using the table on the slot machine image.
    # 0=lemon, 1=seven, 2=diamond, 3=coin, 4=bell, 5=cherry
    TRIPLE_PAYOUTS = [4, 80, 40, 25, 10, 5]
    JOKER_SYMBOL = 1  # seven
    ITEM_HEIGHT = 180
    REEL_LEFT_OFFSET = 25
    REEL_TOP_OFFSET = 100
    # Slots GIF tuning knobs.
    # Increase frame_count / decrease frame_duration_ms for smoother animation.
    RENDER_SETTINGS = SlotRenderSettings(
        frame_count=48,
        frame_duration_ms=32,
        delays=(0.0, 0.1, 0.2),
    )

    def __init__(self, client: commands.Bot):
        self.client = client
        self.economy = getattr(client, "economy", Economy())
        self._assets_path = Path(ABS_PATH) / "modules"
        self._slot_facade = Image.open(self._assets_path / "slot-face.png").convert("RGBA")
        self._slot_reel = Image.open(self._assets_path / "slot-reel.png").convert("RGBA")
        self._slot_base = Image.new("RGBA", self._slot_facade.size, color=(255, 255, 255, 255))
        self._reel_width, self._reel_height = self._slot_reel.size
        self._reel_items = self._reel_height // self.ITEM_HEIGHT
        self._reel_x_positions = tuple(
            self.REEL_LEFT_OFFSET + (self._reel_width * index)
            for index in range(3)
        )

        self._progress_table = self._build_progress_table(self.RENDER_SETTINGS)

    def cog_unload(self) -> None:
        for image in (self._slot_facade, self._slot_reel, self._slot_base):
            with suppress(Exception):
                image.close()

    def check_bet(self, ctx: commands.Context, bet: int = config.bot.default_bet):
        return validate_credits_bet(self.economy, ctx.author.id, bet, max_bet=3)[0]

    @staticmethod
    def _is_retryable_send_error(exc: Exception) -> bool:
        if isinstance(exc, (aiohttp.ClientError, ssl.SSLError, TimeoutError, ConnectionResetError)):
            return True
        if isinstance(exc, discord.HTTPException):
            return exc.status >= 500 or exc.status == 0
        return False

    @staticmethod
    def _eased_progress(raw_progress: float, delay: float) -> float:
        if raw_progress <= delay:
            return 0.0
        scaled = (raw_progress - delay) / (1.0 - delay)
        if scaled >= 1.0:
            return 1.0
        # Ease-out cubic.
        return 1.0 - ((1.0 - scaled) ** 3)

    @classmethod
    def _build_progress_table(
        cls,
        settings: SlotRenderSettings,
    ) -> list[tuple[float, float, float]]:
        table: list[tuple[float, float, float]] = []
        for frame_index in range(1, settings.frame_count + 1):
            raw = frame_index / settings.frame_count
            table.append(
                tuple(cls._eased_progress(raw, delay) for delay in settings.delays)
            )
        return table

    def _render_slots_gif(
        self,
        *,
        s1: int,
        s2: int,
        s3: int,
    ) -> BytesIO:
        images: list[Image.Image] = []
        try:
            for p1, p2, p3 in self._progress_table:
                frame = self._slot_base.copy()
                frame.paste(
                    self._slot_reel,
                    (
                        self._reel_x_positions[0],
                        self.REEL_TOP_OFFSET - int(self.ITEM_HEIGHT * s1 * p1),
                    ),
                )
                frame.paste(
                    self._slot_reel,
                    (
                        self._reel_x_positions[1],
                        self.REEL_TOP_OFFSET - int(self.ITEM_HEIGHT * s2 * p2),
                    ),
                )
                frame.paste(
                    self._slot_reel,
                    (
                        self._reel_x_positions[2],
                        self.REEL_TOP_OFFSET - int(self.ITEM_HEIGHT * s3 * p3),
                    ),
                )
                frame.alpha_composite(self._slot_facade)
                images.append(frame)

            output = BytesIO()
            images[0].save(
                output,
                format="GIF",
                save_all=True,
                append_images=images[1:],
                duration=self.RENDER_SETTINGS.frame_duration_ms,
                optimize=False,
                disposal=2,
            )
            output.seek(0)
            return output
        finally:
            for image in images:
                image.close()

    async def _send_slots_embed(
        self,
        *,
        ctx: commands.Context,
        embed: discord.Embed,
        filename: str,
        primary_gif: bytes,
    ) -> None:
        attachment_url = f"attachment://{filename}"
        for attempt in range(1, 3):
            try:
                with BytesIO(primary_gif) as payload:
                    embed_payload = embed.copy()
                    embed_payload.set_image(url=attachment_url)
                    file = discord.File(fp=payload, filename=filename)
                    await ctx.send(file=file, embed=embed_payload)
                return
            except Exception as exc:
                if not self._is_retryable_send_error(exc):
                    raise
                if attempt == 2:
                    logger.warning(
                        "slots_send_retry_exhausted user_id=%s",
                        ctx.author.id,
                        exc_info=exc,
                    )
                    raise
                await asyncio.sleep(0.5 * attempt)

    @staticmethod
    def _symbol_id(stop_position: int) -> int:
        return (1 + stop_position) % 6

    @classmethod
    def _evaluate_spin(cls, s1: int, s2: int, s3: int, bet: int) -> tuple[str, int]:
        symbols = [
            cls._symbol_id(s1),
            cls._symbol_id(s2),
            cls._symbol_id(s3),
        ]

        # Exact triple (including 7-7-7).
        if symbols[0] == symbols[1] == symbols[2]:
            return "triple", cls.TRIPLE_PAYOUTS[symbols[0]] * bet

        # Joker rules:
        # - Pair only pays when the third symbol is 7.
        # - 2x7 + 1xsymbol pays as 3x that non-7 symbol.
        non_jokers = [symbol for symbol in symbols if symbol != cls.JOKER_SYMBOL]
        joker_count = len(symbols) - len(non_jokers)

        # One 7 + two identical non-7 symbols.
        if joker_count == 1 and len(non_jokers) == 2 and non_jokers[0] == non_jokers[1]:
            return "joker_pair", cls.TRIPLE_PAYOUTS[non_jokers[0]] * bet

        # Two 7s + one non-7 symbol.
        if joker_count == 2 and len(non_jokers) == 1:
            return "joker_pair", cls.TRIPLE_PAYOUTS[non_jokers[0]] * bet

        return "none", 0

    @commands.command(
        brief="Slot machine\nbet must be 1-3",
        usage="slots *[bet]",
    )
    async def slots(self, ctx: commands.Context, bet: int = 1):
        normalized_bet = self.check_bet(ctx, bet=bet)
        s1 = random.randint(1, self._reel_items - 1)
        s2 = random.randint(1, self._reel_items - 1)
        s3 = random.randint(1, self._reel_items - 1)

        filename = f"slots-{ctx.author.id}-{uuid4().hex}.gif"
        gif_buffer = await asyncio.to_thread(
            self._render_slots_gif,
            s1=s1,
            s2=s2,
            s3=s3,
        )
        try:
            gif_bytes = gif_buffer.getvalue()
        finally:
            gif_buffer.close()
        # Win logic.
        result = ("lost", normalized_bet)
        net_credits_delta = normalized_bet * -1
        self.economy.add_credits(ctx.author.id, net_credits_delta)
        payout_kind, reward = self._evaluate_spin(s1, s2, s3, normalized_bet)
        if payout_kind != "none":
            result = ("won", reward)
            self.economy.add_credits(ctx.author.id, reward)
            net_credits_delta += reward

        log_wallet_change(
            logger,
            event="slots_spin",
            user_id=ctx.author.id,
            credits_delta=net_credits_delta,
            ctx=ctx,
            bet=normalized_bet,
            reel_stop=(s1, s2, s3),
            symbols=(
                self._symbol_id(s1),
                self._symbol_id(s2),
                self._symbol_id(s3),
            ),
            payout_kind=payout_kind,
            won=result[0] == "won",
            payout=result[1] if result[0] == "won" else 0,
        )

        embed = make_embed(
            title=(
                f"You {result[0]} {result[1]} credits"
                + ("." if result[0] == "lost" else "!")
            ),
            description=(
                "You now have "
                f"**{self.economy.get_entry(ctx.author.id)[2]}** "
                "credits."
            ),
            color=(
                discord.Color.red()
                if result[0] == "lost"
                else discord.Color.green()
            ),
        )
        await self._send_slots_embed(
            ctx=ctx,
            embed=embed,
            filename=filename,
            primary_gif=gif_bytes,
        )

    @commands.command(
        brief=f"Purchase credits. Each credit is worth ${config.bot.default_bet}.",
        usage="buyc [credits]",
        aliases=["buy", "b"],
    )
    async def buyc(self, ctx: commands.Context, amount_to_buy: int):
        user_id = ctx.author.id
        normalized_amount = validate_positive_amount(amount_to_buy)
        cost = normalized_amount * config.bot.default_bet
        validate_money_available(self.economy, user_id, cost)
        self.economy.add_money(user_id, cost * -1)
        self.economy.add_credits(user_id, normalized_amount)
        log_wallet_change(
            logger,
            event="buy_credits",
            user_id=user_id,
            money_delta=cost * -1,
            credits_delta=normalized_amount,
            ctx=ctx,
            credits_bought=normalized_amount,
            unit_price=config.bot.default_bet,
        )
        await ctx.invoke(self.client.get_command("money"))

    @commands.command(
        brief=f"Sell credits. Each credit is worth ${config.bot.default_bet}.",
        usage="sellc [credits]",
        aliases=["sell", "s"],
    )
    async def sellc(self, ctx: commands.Context, amount_to_sell: int):
        user_id = ctx.author.id
        normalized_amount = validate_credits_available(
            self.economy, user_id, amount_to_sell
        )[0]
        money_delta = normalized_amount * config.bot.default_bet
        self.economy.add_credits(user_id, normalized_amount * -1)
        self.economy.add_money(user_id, money_delta)
        log_wallet_change(
            logger,
            event="sell_credits",
            user_id=user_id,
            money_delta=money_delta,
            credits_delta=normalized_amount * -1,
            ctx=ctx,
            credits_sold=normalized_amount,
            unit_price=config.bot.default_bet,
        )
        await ctx.invoke(self.client.get_command("money"))


async def setup(client: commands.Bot):
    await client.add_cog(Slots(client))
