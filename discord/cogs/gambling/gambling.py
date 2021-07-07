import asyncio
import os
import random
from typing import List, Tuple, Union

import discord
from modules.card import Card  # type:ignore
from discord.ext import commands
from discord.ext.commands.errors import BadArgument
from modules.economy import Economy  # type:ignore
from modules.helpers import *  # type:ignore
from PIL import Image


class Gambling(commands.Cog, name='Gambling'):
    def __init__(self, client: commands.Bot):
        self.client = client
        self.economy = Economy()

    def check_bet(self, ctx: commands.Context, bet: int=DEFAULT_BET):
        bet = int(bet)
        if bet <= 0:
            raise BadArgument()
        current = self.economy.get_entry(ctx.author.id)[1]
        if bet > current:
            raise InsufficientFundsException(current, bet)

    @commands.command(hidden=True)
    @commands.is_owner()
    async def set(self, ctx: commands.Context, user_id: int=None, money: int=None):
        self.economy.set_money(user_id, money)

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
        brief="How much money you or someone else has",
        usage="money *[@member]"
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
        brief="Flip a coin\nBet must be greater than $0",
        usage=f"flip [heads|tails] *[bet- default=${DEFAULT_BET}]",
    )
    async def flip(self, ctx: commands.Context, choice: str, bet: int=DEFAULT_BET):
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
    async def roll(self, ctx: commands.Context, choice: int, bet: int=DEFAULT_BET):
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
