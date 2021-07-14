import random

from discord.ext import commands
from discord.ext.commands.errors import BadArgument
from modules.economy import Economy
from modules.helpers import DEFAULT_BET


class Gambling(commands.Cog):
    def __init__(self, client: commands.Bot):
        self.client = client
        self.economy = Economy()


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

def setup(client: commands.Bot):
    client.add_cog(Gambling(client))