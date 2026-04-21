import discord
from discord.ext import commands

from app.config import config
from app.discord_bot.modules.economy import Economy
from app.discord_bot.modules.helpers import make_embed


class GamblingHelpers(commands.Cog, name="General"):
    def __init__(self, client: commands.Bot) -> None:
        self.client = client
        self.economy = Economy()

    @commands.command(hidden=True)
    @commands.is_owner()
    async def set(
        self,
        ctx: commands.Context,
        user_id: int | None = None,
        money: int = 0,
        credits: int = 0,
    ):
        if user_id is None:
            user_id = ctx.author.id
        if money:
            self.economy.set_money(user_id, money)
        if credits:
            self.economy.set_credits(user_id, credits)

    @commands.command(
        brief=(
            f"Gives you ${config.bot.default_bet*config.bot.bonus_multiplier} "
            f"once every {config.bot.bonus_cooldown}hrs"
        ),
        usage="add",
    )
    @commands.cooldown(1, config.bot.bonus_cooldown * 3600, type=commands.BucketType.user)
    async def add(self, ctx: commands.Context):
        amount = config.bot.default_bet * config.bot.bonus_multiplier
        self.economy.add_money(ctx.author.id, amount)
        await ctx.send(f"Added ${amount} come back in {config.bot.bonus_cooldown}hrs")

    @commands.command(
        brief="How much money you or someone else has",
        usage="money *[@member]",
        aliases=["credits"],
    )
    async def money(self, ctx: commands.Context, user: discord.Member | None = None):
        target_user = user or ctx.author
        profile = self.economy.get_entry(target_user.id)
        embed = make_embed(
            title=target_user.name,
            description=(
                "**${:,}**".format(profile[1]) + "\n**{:,}** credits".format(profile[2])
            ),
        )
        embed.set_thumbnail(url=target_user.display_avatar.url)
        await ctx.send(embed=embed)

    @commands.command(
        brief="Shows the user with the most money",
        usage="leaderboard",
        aliases=["top"],
    )
    async def leaderboard(self, ctx: commands.Context):
        entries = self.economy.top_entries(5)
        embed = make_embed(title="Leaderboard:", color=discord.Color.gold())
        for i, entry in enumerate(entries):
            user = self.client.get_user(entry[0])
            name = user.name if user else f"User {entry[0]}"
            embed.add_field(
                name=f"{i+1}. {name}",
                value="${:,}".format(entry[1]),
                inline=False,
            )
        await ctx.send(embed=embed)


async def setup(client: commands.Bot):
    await client.add_cog(GamblingHelpers(client))
