import bisect
import os
import random

import discord
from discord.ext import commands
from modules.economy import Economy
from modules.helpers import *
from PIL import Image


class Slots(commands.Cog):
    def __init__(self, client: commands.Bot):
        self.client = client
        self.economy = Economy()

    def check_bet(self, ctx: commands.Context, bet: int=DEFAULT_BET):
        bet = int(bet)
        if bet <= 0 or bet > 3:
            raise commands.errors.BadArgument()
        current = self.economy.get_entry(ctx.author.id)[2]
        if bet > current:
            raise InsufficientFundsException(current, bet)

    @commands.command(
        brief='Slot machine\nbet must be 1-3',
        usage='slots *[bet]'
    )
    async def slots(self, ctx: commands.Context, bet: int=1):
        self.check_bet(ctx, bet=bet)
        path = os.path.join(ABS_PATH, 'modules/')
        facade = Image.open(f'{path}slot-face.png').convert('RGBA')
        reel = Image.open(f'{path}slot-reel.png').convert('RGBA')

        rw, rh = reel.size
        item = 180
        items = rh//item

        s1 = random.randint(1, items-1)
        s2 = random.randint(1, items-1)
        s3 = random.randint(1, items-1)

        win_rate = 12/100

        if random.random() < win_rate:
            symbols_weights = [3.5, 7, 15, 25, 55] # 
            x = round(random.random()*100, 1)
            pos = bisect.bisect(symbols_weights, x)
            s1 = pos + (random.randint(1, (items/6)-1) * 6)
            s2 = pos + (random.randint(1, (items/6)-1) * 6)
            s3 = pos + (random.randint(1, (items/6)-1) * 6)
            # ensure no reel hits the last symbol
            s1 = s1 - 6 if s1 == items else s1
            s2 = s2 - 6 if s2 == items else s2
            s3 = s3 - 6 if s3 == items else s3

        images = []
        speed = 6
        for i in range(1, (item//speed)+1):
            bg = Image.new('RGBA', facade.size, color=(255,255,255))
            bg.paste(reel, (25 + rw*0, 100-(speed * i * s1)))
            bg.paste(reel, (25 + rw*1, 100-(speed * i * s2))) # dont ask me why this works, but it took me hours
            bg.paste(reel, (25 + rw*2, 100-(speed * i * s3)))
            bg.alpha_composite(facade)
            images.append(bg)

        fp = str(id(ctx.author.id))+'.gif'
        images[0].save(
            fp,
            save_all=True,
            append_images=images[1:], # append all images after first to first
            duration=50  # duration of each slide (ms)
        )

        # win logic
        result = ('lost', bet)
        self.economy.add_credits(ctx.author.id, bet*-1)       
        # (1+s1)%6 gets the symbol 0-5 inclusive
        if (1+s1)%6 == (1+s2)%6 == (1+s3)%6:
            symbol = (1+s1)%6
            reward = [4, 80, 40, 25, 10, 5][symbol] * bet
            result = ('won', reward)
            self.economy.add_credits(ctx.author.id, reward)

        embed = make_embed(
            title=(
                f'You {result[0]} {result[1]} credits'+
                ('.' if result[0] == 'lost' else '!') # happy or sad based on outcome
            ),
            description=(
                'You now have ' +
                f'**{self.economy.get_entry(ctx.author.id)[2]}** ' +
                'credits.'
            ),
            color=(
                discord.Color.red() if result[0] == "lost"
                else discord.Color.green()
            )
        )

        file = discord.File(fp, filename=fp)
        embed.set_image(url=f"attachment://{fp}") # none of this makes sense to me :)
        await ctx.send(
            file=file,
            embed=embed
        )

        os.remove(fp)

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

def setup(client: commands.Bot):
    client.add_cog(Slots(client))