import discord
from discord.ext import commands
from discord.ext.commands.errors import (
    BadArgument,
    BotMissingPermissions,
    CommandInvokeError,
    CommandNotFound,
    CommandOnCooldown,
    MaxConcurrencyReached,
    MemberNotFound,
    MissingPermissions,
    MissingRequiredArgument,
    TooManyArguments,
    UserNotFound,
)

from app.config import config
from app.discord_bot.modules.helpers import InsufficientFundsException


class Handlers(commands.Cog, name="handlers"):
    def __init__(self, client: commands.Bot):
        self.client = client
        self._ready_once = False

    @commands.Cog.listener()
    async def on_ready(self):
        if self._ready_once:
            return
        self._ready_once = True
        print(f"{self.client.user.name} is ready")
        try:
            await self.client.change_presence(
                activity=discord.Game(f"blackjack | {config.bot.prefix}help")
            )
        except discord.HTTPException:
            pass

    @commands.Cog.listener()
    async def on_command_error(self, ctx: commands.Context, error):
        if hasattr(ctx.command, "on_error"):
            return

        if isinstance(error, CommandInvokeError):
            await self.on_command_error(ctx, error.original)
            return

        if isinstance(error, CommandNotFound):
            await ctx.invoke(self.client.get_command("help"))
            return

        if isinstance(error, (MissingRequiredArgument, TooManyArguments, BadArgument)):
            command_name = ctx.command.name if ctx.command else None
            await ctx.invoke(self.client.get_command("help"), command_name)
            return

        if isinstance(error, (UserNotFound, MemberNotFound)):
            await ctx.send(f"Member, `{error.argument}`, was not found.")
            return

        if isinstance(error, MissingPermissions):
            await ctx.send(
                "Must have following permission(s): "
                + ", ".join(f"`{perm}`" for perm in error.missing_perms)
            )
            return

        if isinstance(error, BotMissingPermissions):
            await ctx.send(
                "I must have following permission(s): "
                + ", ".join(f"`{perm}`" for perm in error.missing_perms)
            )
            return

        if isinstance(error, InsufficientFundsException):
            await ctx.send(str(error))
            await ctx.invoke(self.client.get_command("money"))
            return

        if isinstance(error, CommandOnCooldown):
            seconds = int(error.retry_after)
            seconds = seconds % (24 * 3600)
            hours = seconds // 3600
            seconds %= 3600
            minutes = seconds // 60
            seconds %= 60
            await ctx.send(f"{hours}hrs {minutes}min {seconds}sec remaining.")
            return

        if isinstance(error, MaxConcurrencyReached):
            await ctx.send("That command is already running for you right now.")
            return

        raise error


async def setup(client: commands.Bot):
    await client.add_cog(Handlers(client))
