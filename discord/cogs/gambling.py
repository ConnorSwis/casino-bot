import asyncio
import os
import random
from typing import List, Optional, Tuple, Union

import discord
from helpers import *  # type:ignore
from card import Card  # type:ignore
from discord.ext import commands
from economy import Economy  # type:ignore
from PIL import Image


DEFAULT_BET = 100

class Gambling(commands.Cog):
    def __init__(self, client: commands.Bot):
        self.client = client
        self.economy = Economy()

    @commands.command(hidden=True)
    @commands.is_owner()
    async def set(self, ctx: commands.Context, user_id: int=None, money: int=None):
        self.economy.set_money(user_id, money)

    @commands.command(
        brief=f"Gives you ${DEFAULT_BET*5} once every 24hrs",
        usage="add"
    )
    @commands.cooldown(1, 86400, type=commands.BucketType.user)
    async def add(self, ctx: commands.Context):
        amount = DEFAULT_BET*5
        self.economy.add_money(ctx.author.id, amount)
        await ctx.send(f"Added ${amount} come back in 24hrs")

    @commands.command(
        brief="How much money you or someone else has",
        usage="money *<@member>"
    )
    async def money(self, ctx: commands.Context, user: discord.Member=None):
        user = user.id if user else ctx.author.id
        user = self.client.get_user(user)
        embed = make_embed(  # type:ignore
            title=user.name,
            description='**${:,}**'.format(self.economy.get_entry(user.id)[1]),
            footer=discord.Embed.Empty
        )
        embed.set_thumbnail(url=user.avatar_url)
        await ctx.send(embed=embed)

    @commands.command(
        brief="Shows the user with the most money",
        usage="top"
    )
    async def top(self, ctx):
        top_entry = self.economy.top_entry()
        user = self.client.get_user(top_entry[0])
        embed = make_embed(  # type:ignore
            title=user.name,
            description='**${:,}**'.format(top_entry[1]),
            footer=' '
        )
        embed.set_thumbnail(url=user.avatar_url)
        await ctx.send(embed=embed)

    @commands.command(
        brief="Flip a coin",
        usage=f"flip <heads|tails> *<bet- default=${DEFAULT_BET}>"
    )
    async def flip(self, ctx: commands.Context, choice: str, bet: int=DEFAULT_BET):
        choices = {'h': True, 't': False}
        if self.economy.get_entry(ctx.author.id)[1] >= bet and bet > 0:
            if (choice:=choice.lower()[0]) in choices.keys():
                if random.choice(list(choices.keys())) == choice:
                    await ctx.send('correct')
                    self.economy.add_money(ctx.author.id, bet)
                else:
                    await ctx.send('wrong')
                    self.economy.add_money(ctx.author.id, bet * -1)
            else:
                await self.client.get_command('help')(ctx, ctx.command.name)
        else:
            pass  # TODO: user doesn't have enough money

    @commands.command(
        brief="Roll 1 die",
        usage=f"roll <guess:1-6> <bet- default=${DEFAULT_BET}>"
    )
    async def roll(self, ctx: commands.Context, choice: int, bet: int=DEFAULT_BET):
        choices = range(1,7)
        if self.economy.get_entry(ctx.author.id)[1] >= bet and bet > 0:
            if choice in choices:
                if random.choice(choices) == choice:
                    await ctx.send('correct')
                    self.economy.add_money(ctx.author.id, bet*6)
                else:
                    await ctx.send('wrong')
                    self.economy.add_money(ctx.author.id, bet * -1)
            else:
                await self.client.get_command('help')(ctx, ctx.command.name)
        else:
            pass  # TODO: user doesn't have enough money

    @staticmethod
    def hand_to_images(hand: List[Card]) -> List[Image.Image]:
        (print(os.path.join(ABS_PATH, card.image)) for card in hand)  # type:ignore
        return [Image.open(os.path.join(ABS_PATH, card.image)) for card in hand]  # type:ignore

    @staticmethod
    def center(*hands: Tuple[Image.Image]) -> Image.Image:
        bg: Image.Image = Image.open(os.path.join(ABS_PATH, 'table.png'))  # type:ignore
        bg_center_x = bg.size[0] // 2
        bg_center_y = bg.size[1] // 2

        img_w = hands[0][0].size[0]
        img_h = hands[0][0].size[1]

        start_y = bg_center_y - (((len(hands)*img_h) + ((len(hands) - 1) * 15)) // 2)
        for hand in hands:
            start_x = bg_center_x - (((len(hand)*img_w) + ((len(hand) - 1) * 10)) // 2)
            for card in hand:
                bg.paste(card, (start_x, start_y))
                start_x += img_w + 10
            start_y += img_h + 15
        return bg

    def output(self, name, *hands: Tuple[List[Card]]) -> None:
        self.center(*map(self.hand_to_images, hands)).save(f'{name}.png')

    @staticmethod
    def calc_hand(hand: List[Card]) -> int:
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
        brief="Play a simple game of blackjack.",
        usage=f"blackjack <bet- default=${DEFAULT_BET}>"
    )
    async def blackjack(self, ctx: commands.Context, bet: int=DEFAULT_BET):
        if self.economy.get_entry(ctx.author.id)[1] >= bet and bet > 0:
            deck: List[Card] = [Card(suit, num) for num in range(2,15) for suit in Card.suits]
            random.shuffle(deck) # Generate deck and shuffle it

            player_hand: List[Card] = []
            dealer_hand: List[Card] = []

            player_hand.append(deck.pop())  # Deal first hands
            dealer_hand.append(deck.pop())
            player_hand.append(deck.pop())
            dealer_hand.append(deck.pop().flip())

            player_score = self.calc_hand(player_hand)
            dealer_score = self.calc_hand(dealer_hand)

            async def out_table(**kwargs) -> discord.Message:
                """Sends a picture of the current table"""
                self.output(ctx.author.id, dealer_hand, player_hand)
                embed = make_embed(**kwargs)  # type:ignore
                file = discord.File(f"{ctx.author.id}.png", filename=f"{ctx.author.id}.png")
                embed.set_image(url=f"attachment://{ctx.author.id}.png")
                msg: discord.Message = await ctx.send(file=file, embed=embed)
                return msg
            
            def check(reaction: discord.Reaction, user: Union[discord.Member, discord.User]) -> bool:
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
                    self.economy.add_money(ctx.author.id, bet)
                    result = ("Blackjack!", 'won')
                    break
                elif player_score > 21:  # losing condition
                    self.economy.add_money(ctx.author.id, bet*-1)
                    result = ("Player busts", 'lost')
                    break
                msg = await out_table(title="Your Turn", description=f"Your hand: {player_score}\nDealer's hand: {dealer_score}")
                await msg.add_reaction("🇭")
                await msg.add_reaction("🇸")
                
                try:  # reaction command
                    reaction, _ = await self.client.wait_for('reaction_add', timeout=60, check=check)
                except asyncio.exceptions.TimeoutError:
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

            color = discord.Color.red() if result[1] == 'lost' else discord.Color.green() if result[1] == 'won' else discord.Color.blue()
            try:
            	await msg.delete()
            except:
            	pass
            msg = await out_table(
                title=result[0],
                color=color,
                description=f"**You {result[1]} ${bet}**\n" \
                            f"Your hand: {player_score}\nDealer's hand: {dealer_score}"
                )
            os.remove(f'./{ctx.author.id}.png')

        
    

def setup(client: commands.Bot):
    client.add_cog(Gambling(client))
