import random

import discord
from discord.ext import commands
from discord.ext.commands.errors import BadArgument
from modules.economy import Economy
from modules.helpers import *


class Gambling(commands.Cog, name='Gambling'):
    def __init__(self, client: commands.Bot):
        self.client = client
        self.economy = Economy()

    def check_bet(
        self,
        ctx: commands.Context,
        bet: int=DEFAULT_BET,
        credits=False
    ):
        bet = int(bet)
        if bet <= 0:
            raise BadArgument()
        if credits:
            if bet > 3:
                raise BadArgument()
            current = self.economy.get_entry(ctx.author.id)[2]
        else:
            current = self.economy.get_entry(ctx.author.id)[1]
        if bet > current:
            raise InsufficientFundsException(current, bet)

    @commands.command(hidden=True)
    @commands.is_owner()
    async def set(
        self,
        ctx: commands.Context,
        user_id: int=None,
        money: int=None,
        credits: int=0
    ):
        if money:
            self.economy.set_money(user_id, money)
        if credits:
            self.economy.set_credits(user_id, credits)

    @commands.command(
        brief=f"Gives you ${DEFAULT_BET*B_MULT} once every {B_COOLDOWN}hrs",
        usage="add"
    )
    @commands.cooldown(1, B_COOLDOWN*3600, type=commands.BucketType.user)
    async def add(self, ctx: commands.Context):
        amount = DEFAULT_BET*B_MULT
        self.economy.add_money(ctx.author.id, amount)
        await ctx.send(f"Added ${amount} come back in {B_COOLDOWN}hrs")

    @commands.command(
        brief=f"Purchase credits. Each credit is worth ${DEFAULT_BET}.",
        usage="buyc [credits]",
        aliases=["buy", "b"]
    )
    async def buyc(self, ctx: commands.Context, amount_to_buy: int):
        user_id = ctx.author.id
        profile = self.economy.get_entry(user_id)
        cost = amount_to_buy * DEFAULT_BET
        if profile[1] >= cost:
            self.economy.add_money(user_id, cost*-1)
            self.economy.add_credits(user_id, amount_to_buy)
        await ctx.invoke(self.client.get_command('money'))

    @commands.command(
        brief=f'Sell credits. Each credit is worth ${DEFAULT_BET}.',
        usage="sellc [credits]",
        aliases=["sell", "s"]
    )
    async def sellc(self, ctx: commands.Context, amount_to_sell: int):
        user_id = ctx.author.id
        profile = self.economy.get_entry(user_id)
        if profile[2] >= amount_to_sell:
            self.economy.add_credits(user_id, amount_to_sell*-1)
            self.economy.add_money(user_id, amount_to_sell*DEFAULT_BET)
        await ctx.invoke(self.client.get_command('money'))

    @commands.command(
        brief="How much money you or someone else has",
        usage="money *[@member]",
        aliases=['credits']
    )
    async def money(self, ctx: commands.Context, user: discord.Member=None):
        user = user.id if user else ctx.author.id
        user = self.client.get_user(user)
        profile = self.economy.get_entry(user.id)
        embed = make_embed(
            title=user.name,
            description=(
                '**${:,}**'.format(profile[1]) +
                '\n**{:,}** credits'.format(profile[2])
            ),
            footer=discord.Embed.Empty
        )
        embed.set_thumbnail(url=user.avatar_url)
        await ctx.send(embed=embed)

    @commands.command(
        brief="Shows the user with the most money",
        usage="top"
    )
    async def top(self, ctx):
        top_entry = self.economy.top_entries(1)[0]
        user = self.client.get_user(top_entry[0])
        embed = make_embed(
            title=user.name,
            description=(
                '**${:,}**'.format(top_entry[1]) +
                '\n**{:,}** credits'.format(top_entry[2])
            ),
            footer=' '
        )
        embed.set_thumbnail(url=user.avatar_url)
        await ctx.send(embed=embed)

    @commands.command(
        brief="Flip a coin\nBet must be greater than $0",
        usage=f"flip [heads|tails] *[bet- default=${DEFAULT_BET}]",
    )
    async def flip(
        self,
        ctx: commands.Context,
        choice: str,
        bet: int=DEFAULT_BET
    ):
        choices = {'h': True, 't': False}
        self.check_bet(ctx, bet)
        choice = choice.lower()[0]
        if choice in choices.keys():
            if random.choice(list(choices.keys())) == choice:
                await ctx.send('correct')
                self.economy.add_money(ctx.author.id, bet)
            else:
                await ctx.send('wrong')
                self.economy.add_money(ctx.author.id, bet * -1)
        else:
            raise BadArgument()

    @commands.command(
        brief="Roll 1 die\nBet must be greater than $0",
        usage=f"roll [guess:1-6] [bet- default=${DEFAULT_BET}]"
    )
    async def roll(
        self,
        ctx: commands.Context,
        choice: int,
        bet: int=DEFAULT_BET
    ):
        choices = range(1,7)
        self.check_bet(ctx, bet)
        if choice in choices:
            if random.choice(choices) == choice:
                await ctx.send('correct')
                self.economy.add_money(ctx.author.id, bet*6)
            else:
                await ctx.send('wrong')
                self.economy.add_money(ctx.author.id, bet * -1)
        else:
            raise BadArgument()
