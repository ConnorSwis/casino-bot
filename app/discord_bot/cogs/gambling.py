import asyncio
import logging
import random
from contextlib import suppress
from uuid import uuid4

import discord
from discord.ext import commands
from discord.ext.commands.errors import BadArgument

from app.config import config
from app.discord_bot.modules.betting import validate_money_bet
from app.discord_bot.modules.card import Card
from app.discord_bot.modules.card_table import render_card_table_bytes
from app.discord_bot.modules.economy import Economy
from app.discord_bot.modules.helpers import InsufficientFundsException, make_embed
from app.discord_bot.modules.wallet_logging import log_wallet_change

logger = logging.getLogger(__name__)


class HighCardRedrawView(discord.ui.View):
    def __init__(self, *, cog: "Gambling", user_id: int, bet: int, timeout: float = 120):
        super().__init__(timeout=timeout)
        self.cog = cog
        self.user_id = user_id
        self.bet = bet
        self.message: discord.Message | None = None
        self._redraw_in_progress = False

    def _disable_items(self) -> None:
        for item in self.children:
            if hasattr(item, "disabled"):
                item.disabled = True

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if not interaction.user or interaction.user.id != self.user_id:
            if not interaction.response.is_done():
                await interaction.response.send_message(
                    "Only the player who started this round can use this button.",
                    ephemeral=True,
                )
            else:
                await interaction.followup.send(
                    "Only the player who started this round can use this button.",
                    ephemeral=True,
                )
            return False
        return True

    async def on_timeout(self) -> None:
        self._disable_items()
        if self.message is not None:
            with suppress(discord.HTTPException):
                await self.message.edit(view=self)

    @discord.ui.button(label="Redraw Same Bet", style=discord.ButtonStyle.primary)
    async def redraw(self, interaction: discord.Interaction, _: discord.ui.Button):
        if self._redraw_in_progress:
            await interaction.response.send_message(
                "Redraw already in progress.",
                ephemeral=True,
            )
            return

        try:
            normalized_bet = self.cog.check_bet_for_user(self.user_id, self.bet)
        except InsufficientFundsException as exc:
            await interaction.response.send_message(str(exc), ephemeral=True)
            return

        self._redraw_in_progress = True
        await interaction.response.defer()
        try:
            await self.cog._send_highcard_round(
                destination=interaction,
                user=interaction.user,
                bet=normalized_bet,
                source="redraw_button",
                edit_existing_interaction_message=True,
            )
        finally:
            self._redraw_in_progress = False


class Gambling(commands.Cog):
    def __init__(self, client: commands.Bot):
        self.client = client
        self.economy = getattr(client, "economy", Economy())

    def check_bet_for_user(
        self,
        user_id: int,
        bet: int = config.bot.default_bet,
    ) -> int:
        return validate_money_bet(self.economy, user_id, bet)[0]

    def check_bet(
        self,
        ctx: commands.Context,
        bet: int = config.bot.default_bet,
    ):
        return self.check_bet_for_user(ctx.author.id, bet)

    @staticmethod
    def _format_delta(amount: int) -> str:
        if amount > 0:
            return f"+${amount}"
        if amount < 0:
            return f"-${abs(amount)}"
        return "$0"

    def _resolve_highcard_round(
        self,
        *,
        user_id: int,
        bet: int,
        ctx: commands.Context | None = None,
        source: str = "command",
        guild_id: int | None = None,
        channel_id: int | None = None,
    ) -> tuple[Card, Card, str, int, int]:
        deck = [Card(suit, value) for value in range(2, 15) for suit in Card.suits]
        random.shuffle(deck)
        dealer_card = deck.pop()
        player_card = deck.pop()

        if player_card.value > dealer_card.value:
            title = "You win!"
            delta = bet
        elif player_card.value < dealer_card.value:
            title = "You lose!"
            delta = bet * -1
        else:
            title = "Push"
            delta = 0

        if delta:
            self.economy.add_money(user_id, delta)

        metadata: dict[str, int | str] = {"source": source}
        if ctx is None:
            if guild_id is not None:
                metadata["guild_id"] = guild_id
            if channel_id is not None:
                metadata["channel_id"] = channel_id

        log_wallet_change(
            logger,
            event="high_card_round",
            user_id=user_id,
            money_delta=delta,
            ctx=ctx,
            bet=bet,
            dealer_card=str(dealer_card),
            player_card=str(player_card),
            result=title.lower().replace("!", ""),
            **metadata,
        )

        balance = self.economy.get_entry(user_id)[1]
        return dealer_card, player_card, title, delta, balance

    @staticmethod
    def _highcard_result_color(delta: int) -> discord.Color:
        if delta < 0:
            return discord.Color.red()
        if delta > 0:
            return discord.Color.green()
        return discord.Color.blue()

    async def _send_highcard_round(
        self,
        *,
        destination: commands.Context | discord.Interaction,
        user: discord.User | discord.Member,
        bet: int,
        source: str = "command",
        ctx: commands.Context | None = None,
        edit_existing_interaction_message: bool = False,
    ) -> discord.Message:
        guild_id = destination.guild.id if isinstance(destination, discord.Interaction) and destination.guild else None
        channel_id = (
            destination.channel.id
            if isinstance(destination, discord.Interaction)
            and destination.channel is not None
            and hasattr(destination.channel, "id")
            else None
        )
        dealer_card, player_card, title, delta, balance = self._resolve_highcard_round(
            user_id=user.id,
            bet=bet,
            ctx=ctx,
            source=source,
            guild_id=guild_id,
            channel_id=channel_id,
        )

        output_filename = f"highcard-{user.id}-{uuid4().hex}.png"
        table_buffer = await asyncio.to_thread(
            render_card_table_bytes,
            [dealer_card],
            [[player_card]],
        )
        view = HighCardRedrawView(cog=self, user_id=user.id, bet=bet)
        try:
            embed = make_embed(
                title=title,
                description=(
                    f"Dealer: **{dealer_card}**\n"
                    f"Player: **{player_card}**\n"
                    f"Bet: **${bet}**\n"
                    f"Net: **{self._format_delta(delta)}**\n"
                    f"Balance: **${balance:,}**"
                ),
                color=self._highcard_result_color(delta),
            )
            file = discord.File(fp=table_buffer, filename=output_filename)
            embed.set_image(url=f"attachment://{output_filename}")
            if isinstance(destination, commands.Context):
                message = await destination.send(file=file, embed=embed, view=view)
            elif edit_existing_interaction_message:
                await destination.edit_original_response(
                    attachments=[file],
                    embed=embed,
                    view=view,
                )
                message = destination.message
                if message is None:
                    message = await destination.original_response()
            else:
                message = await destination.followup.send(
                    file=file,
                    embed=embed,
                    view=view,
                    wait=True,
                )
            view.message = message
            return message
        finally:
            table_buffer.close()

    @commands.command(
        brief="Flip a coin\nBet must be greater than $0",
        usage=f"flip [heads|tails] *[bet- default=${config.bot.default_bet}]",
    )
    async def flip(
        self,
        ctx: commands.Context,
        choice: str,
        bet: int = config.bot.default_bet
    ):
        normalized_bet = self.check_bet(ctx, bet)
        choices = {'h': True, 't': False}
        choice = choice.lower()[0]
        if choice in choices.keys():
            if random.choice(list(choices.keys())) == choice:
                await ctx.send('correct')
                self.economy.add_money(ctx.author.id, normalized_bet)
                log_wallet_change(
                    logger,
                    event="coin_flip_win",
                    user_id=ctx.author.id,
                    money_delta=normalized_bet,
                    ctx=ctx,
                    bet=normalized_bet,
                )
            else:
                await ctx.send('wrong')
                self.economy.add_money(ctx.author.id, normalized_bet * -1)
                log_wallet_change(
                    logger,
                    event="coin_flip_loss",
                    user_id=ctx.author.id,
                    money_delta=normalized_bet * -1,
                    ctx=ctx,
                    bet=normalized_bet,
                )
        else:
            raise BadArgument()

    @commands.command(
        brief="Roll 1 die\nBet must be greater than $0",
        usage=f"roll [guess:1-6] [bet- default=${config.bot.default_bet}]",
    )
    async def roll(
        self,
        ctx: commands.Context,
        choice: int,
        bet: int = config.bot.default_bet
    ):
        normalized_bet = self.check_bet(ctx, bet)
        choices = range(1, 7)
        if choice in choices:
            if random.choice(choices) == choice:
                await ctx.send('correct')
                delta = normalized_bet * 6
                self.economy.add_money(ctx.author.id, delta)
                log_wallet_change(
                    logger,
                    event="roll_win",
                    user_id=ctx.author.id,
                    money_delta=delta,
                    ctx=ctx,
                    bet=normalized_bet,
                    guess=choice,
                )
            else:
                await ctx.send('wrong')
                delta = normalized_bet * -1
                self.economy.add_money(ctx.author.id, delta)
                log_wallet_change(
                    logger,
                    event="roll_loss",
                    user_id=ctx.author.id,
                    money_delta=delta,
                    ctx=ctx,
                    bet=normalized_bet,
                    guess=choice,
                )
        else:
            raise BadArgument()

    @commands.command(
        brief="Draw a high card against the dealer.\nBet must be greater than $0",
        usage=f"highcard *[bet- default=${config.bot.default_bet}]",
        aliases=["war"],
    )
    async def highcard(
        self,
        ctx: commands.Context,
        bet: int = config.bot.default_bet,
    ):
        normalized_bet = self.check_bet(ctx, bet)
        await self._send_highcard_round(
            destination=ctx,
            user=ctx.author,
            bet=normalized_bet,
            ctx=ctx,
        )


async def setup(client: commands.Bot):
    await client.add_cog(Gambling(client))
