import asyncio
import os
import random
from typing import List, Tuple, Union

import discord
from discord.ext import commands
from modules.card import Card
from modules.economy import Economy
from modules.helpers import *
from PIL import Image


class Blackjack(commands.Cog):
    def __init__(self, client: commands.Bot):
        self.client = client
        self.economy = Economy()
    
    def check_bet(
        self,
        ctx: commands.Context,
        bet: int=DEFAULT_BET,
    ):
        bet = int(bet)
        if bet <= 0:
            raise commands.errors.BadArgument()
        current = self.economy.get_entry(ctx.author.id)[1]
        if bet > current:
            raise InsufficientFundsException(current, bet)

    @staticmethod
    def hand_to_images(hand: List[Card]) -> List[Image.Image]:
        return ([
            Image.open(os.path.join(ABS_PATH, 'modules/cards/', card.image))
            for card in hand
        ])

    @staticmethod
    def center(*hands: Tuple[Image.Image]) -> Image.Image:
        """Creates blackjack table with cards placed"""
        bg: Image.Image = Image.open(
            os.path.join(ABS_PATH, 'modules/', 'table.png')
        )
        bg_center_x = bg.size[0] // 2
        bg_center_y = bg.size[1] // 2

        img_w = hands[0][0].size[0]
        img_h = hands[0][0].size[1]

        start_y = bg_center_y - (((len(hands)*img_h) + \
            ((len(hands) - 1) * 15)) // 2)
        for hand in hands:
            start_x = bg_center_x - (((len(hand)*img_w) + \
                ((len(hand) - 1) * 10)) // 2)
            for card in hand:
                bg.alpha_composite(card, (start_x, start_y))
                start_x += img_w + 10
            start_y += img_h + 15
        return bg

    def output(self, name, *hands: Tuple[List[Card]]) -> None:
        self.center(*map(self.hand_to_images, hands)).save(f'{name}.png')

    @staticmethod
    def calc_hand(hand: List[List[Card]]) -> int:
        """Calculates the sum of the card values and accounts for aces"""
        non_aces = [c for c in hand if c.symbol != 'A']
        aces = [c for c in hand if c.symbol == 'A']
        sum = 0
        for card in non_aces:
            if not card.down:
                if card.symbol in 'JQK': sum += 10
                else: sum += card.value
        for card in aces:
            if not card.down:
                if sum <= 10: sum += 11
                else: sum += 1
        return sum


    @commands.command(
        aliases=['bj'],
        brief="Play a simple game of blackjack.\nBet must be greater than $0",
        usage=f"blackjack [bet- default=${DEFAULT_BET}]"
    )
    async def blackjack(self, ctx: commands.Context, bet: int=DEFAULT_BET):
        self.check_bet(ctx, bet)
        deck = [Card(suit, num) for num in range(2,15) for suit in Card.suits]
        random.shuffle(deck) # Generate deck and shuffle it

        player_hand: List[Card] = []
        dealer_hand: List[Card] = []

        player_hand.append(deck.pop())
        dealer_hand.append(deck.pop())
        player_hand.append(deck.pop())
        dealer_hand.append(deck.pop().flip())

        player_score = self.calc_hand(player_hand)
        dealer_score = self.calc_hand(dealer_hand)

        async def out_table(**kwargs) -> discord.Message:
            """Sends a picture of the current table"""
            self.output(ctx.author.id, dealer_hand, player_hand)
            embed = make_embed(**kwargs)
            file = discord.File(
                f"{ctx.author.id}.png", filename=f"{ctx.author.id}.png"
            )
            embed.set_image(url=f"attachment://{ctx.author.id}.png")
            msg: discord.Message = await ctx.send(file=file, embed=embed)
            return msg
        
        def check(
            reaction: discord.Reaction,
            user: Union[discord.Member, discord.User]
        ) -> bool:
            return all((
                str(reaction.emoji) in ("🇸", "🇭"),  # correct emoji
                user == ctx.author,                  # correct user
                user != self.client.user,           # isn't the bot
                reaction.message == msg            # correct message
            ))

        standing = False

        while True:
            player_score = self.calc_hand(player_hand)
            dealer_score = self.calc_hand(dealer_hand)
            if player_score == 21:  # win condition
                bet = int(bet*1.5)
                self.economy.add_money(ctx.author.id, bet)
                result = ("Blackjack!", 'won')
                break
            elif player_score > 21:  # losing condition
                self.economy.add_money(ctx.author.id, bet*-1)
                result = ("Player busts", 'lost')
                break
            msg = await out_table(
                title="Your Turn",
                description=f"Your hand: {player_score}\n" \
                    f"Dealer's hand: {dealer_score}"
            )
            await msg.add_reaction("🇭")
            await msg.add_reaction("🇸")
            
            try:  # reaction command
                reaction, _ = await self.client.wait_for(
                    'reaction_add', timeout=60, check=check
                )
            except asyncio.TimeoutError:
                await msg.delete()

            if str(reaction.emoji) == "🇭":
                player_hand.append(deck.pop())
                await msg.delete()
                continue
            elif str(reaction.emoji) == "🇸":
                standing = True
                break

        if standing:
            dealer_hand[1].flip()
            player_score = self.calc_hand(player_hand)
            dealer_score = self.calc_hand(dealer_hand)

            while dealer_score < 17:  # dealer draws until 17 or greater
                dealer_hand.append(deck.pop())
                dealer_score = self.calc_hand(dealer_hand)

            if dealer_score == 21:  # winning/losing conditions
                self.economy.add_money(ctx.author.id, bet*-1)
                result = ('Dealer blackjack', 'lost')
            elif dealer_score > 21:
                self.economy.add_money(ctx.author.id, bet)
                result = ("Dealer busts", 'won')
            elif dealer_score == player_score:
                result = ("Tie!", 'kept')
            elif dealer_score > player_score:
                self.economy.add_money(ctx.author.id, bet*-1)
                result = ("You lose!", 'lost')
            elif dealer_score < player_score:
                self.economy.add_money(ctx.author.id, bet)
                result = ("You win!", 'won')

        color = (
            discord.Color.red() if result[1] == 'lost'
            else discord.Color.green() if result[1] == 'won'
            else discord.Color.blue()
        )
        try:
            await msg.delete()
        except:
            pass
        msg = await out_table(
            title=result[0],
            color=color,
            description=(
                f"**You {result[1]} ${bet}**\nYour hand: {player_score}\n" +
                f"Dealer's hand: {dealer_score}"
            )
        )
        os.remove(f'./{ctx.author.id}.png')

def setup(client: commands.Bot):
    client.add_cog(Blackjack(client))