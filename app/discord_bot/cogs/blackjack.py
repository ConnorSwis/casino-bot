import asyncio
import os
import random
from pathlib import Path
from typing import List, Tuple, Union
from uuid import uuid4

import discord
from discord.ext import commands
from PIL import Image

from app.config import config
from app.discord_bot.modules.card import Card
from app.discord_bot.modules.economy import Economy
from app.discord_bot.modules.helpers import ABS_PATH, InsufficientFundsException, make_embed


class Blackjack(commands.Cog):
    def __init__(self, client: commands.Bot):
        self.client = client
        self.economy = Economy()

    def check_bet(
        self,
        ctx: commands.Context,
        bet: int = config.bot.default_bet,
    ):
        bet = int(bet)
        if bet <= 0:
            raise commands.errors.BadArgument()
        current = self.economy.get_entry(ctx.author.id)[1]
        if bet > current:
            raise InsufficientFundsException(current, bet)

    @staticmethod
    def hand_to_images(hand: List[Card]) -> List[Image.Image]:
        images: List[Image.Image] = []
        for card in hand:
            with Image.open(os.path.join(ABS_PATH, "modules/cards", card.image)) as img:
                images.append(img.convert("RGBA"))
        return images

    @staticmethod
    def center(*hands: Tuple[Image.Image]) -> Image.Image:
        """Creates blackjack table with cards placed."""
        bg = Image.open(os.path.join(ABS_PATH, "modules", "table.png")).convert("RGBA")
        bg_center_x = bg.size[0] // 2
        bg_center_y = bg.size[1] // 2

        img_w = hands[0][0].size[0]
        img_h = hands[0][0].size[1]

        start_y = bg_center_y - (((len(hands) * img_h) + ((len(hands) - 1) * 15)) // 2)
        for hand in hands:
            start_x = bg_center_x - (((len(hand) * img_w) + ((len(hand) - 1) * 10)) // 2)
            for card in hand:
                bg.alpha_composite(card, (start_x, start_y))
                start_x += img_w + 10
            start_y += img_h + 15
        return bg

    def output(self, output_path: Path, *hands: Tuple[List[Card]]) -> None:
        final_image = self.center(*map(self.hand_to_images, hands))
        try:
            final_image.save(output_path)
        finally:
            final_image.close()

    @staticmethod
    def calc_hand(hand: List[Card]) -> int:
        """Calculates the sum of the card values and accounts for aces."""
        non_aces = [c for c in hand if c.symbol != "A"]
        aces = [c for c in hand if c.symbol == "A"]
        total = 0
        for card in non_aces:
            if not card.down:
                if card.symbol in "JQK":
                    total += 10
                else:
                    total += card.value
        for card in aces:
            if not card.down:
                if total <= 10:
                    total += 11
                else:
                    total += 1
        return total

    @commands.command(
        aliases=["bj"],
        brief="Play a simple game of blackjack.\nBet must be greater than $0",
        usage=f"blackjack [bet- default=${config.bot.default_bet}]",
    )
    @commands.max_concurrency(1, per=commands.BucketType.user, wait=False)
    async def blackjack(
        self,
        ctx: commands.Context,
        bet: int = config.bot.default_bet,
    ):
        self.check_bet(ctx, bet)
        deck = [Card(suit, num) for num in range(2, 15) for suit in Card.suits]
        random.shuffle(deck)

        player_hand: List[Card] = []
        dealer_hand: List[Card] = []

        player_hand.append(deck.pop())
        dealer_hand.append(deck.pop())
        player_hand.append(deck.pop())
        dealer_hand.append(deck.pop().flip())

        table_path = Path(f"{ctx.author.id}-{uuid4().hex}.png")
        result: tuple[str, str] = ("You lose!", "lost")
        player_score = self.calc_hand(player_hand)
        dealer_score = self.calc_hand(dealer_hand)
        standing = False

        async def out_table(**kwargs) -> discord.Message:
            self.output(table_path, dealer_hand, player_hand)
            embed = make_embed(**kwargs)
            file = discord.File(str(table_path), filename=table_path.name)
            embed.set_image(url=f"attachment://{table_path.name}")
            msg: discord.Message = await ctx.send(file=file, embed=embed)
            return msg

        def check(
            reaction: discord.Reaction,
            user: Union[discord.Member, discord.User],
            message: discord.Message,
        ) -> bool:
            return all(
                (
                    str(reaction.emoji) in ("🇸", "🇭"),
                    user == ctx.author,
                    user != self.client.user,
                    reaction.message == message,
                )
            )

        try:
            while True:
                player_score = self.calc_hand(player_hand)
                dealer_score = self.calc_hand(dealer_hand)

                if player_score == 21:
                    bet = int(bet * 1.5)
                    self.economy.add_money(ctx.author.id, bet)
                    result = ("Blackjack!", "won")
                    break
                if player_score > 21:
                    self.economy.add_money(ctx.author.id, bet * -1)
                    result = ("Player busts", "lost")
                    break

                msg = await out_table(
                    title="Your Turn",
                    description=f"Your hand: {player_score}\nDealer's hand: {dealer_score}",
                )
                await msg.add_reaction("🇭")
                await msg.add_reaction("🇸")

                try:
                    reaction, _ = await self.client.wait_for(
                        "reaction_add",
                        timeout=60,
                        check=lambda r, u: check(r, u, msg),
                    )
                except asyncio.TimeoutError:
                    self.economy.add_money(ctx.author.id, bet * -1)
                    result = ("Timed out", "lost")
                    await msg.delete()
                    break

                await msg.delete()

                if str(reaction.emoji) == "🇭":
                    player_hand.append(deck.pop())
                    continue

                standing = True
                break

            if standing:
                dealer_hand[1].flip()
                player_score = self.calc_hand(player_hand)
                dealer_score = self.calc_hand(dealer_hand)

                while dealer_score < 17:
                    dealer_hand.append(deck.pop())
                    dealer_score = self.calc_hand(dealer_hand)

                if dealer_score == 21:
                    self.economy.add_money(ctx.author.id, bet * -1)
                    result = ("Dealer blackjack", "lost")
                elif dealer_score > 21:
                    self.economy.add_money(ctx.author.id, bet)
                    result = ("Dealer busts", "won")
                elif dealer_score == player_score:
                    result = ("Tie!", "kept")
                elif dealer_score > player_score:
                    self.economy.add_money(ctx.author.id, bet * -1)
                    result = ("You lose!", "lost")
                else:
                    self.economy.add_money(ctx.author.id, bet)
                    result = ("You win!", "won")

            color = (
                discord.Color.red()
                if result[1] == "lost"
                else discord.Color.green()
                if result[1] == "won"
                else discord.Color.blue()
            )

            player_score = self.calc_hand(player_hand)
            dealer_score = self.calc_hand(dealer_hand)
            await out_table(
                title=result[0],
                color=color,
                description=(
                    f"**You {result[1]} ${bet}**\n"
                    f"Your hand: {player_score}\n"
                    f"Dealer's hand: {dealer_score}"
                ),
            )
        finally:
            if table_path.exists():
                table_path.unlink()


async def setup(client: commands.Bot):
    await client.add_cog(Blackjack(client))
