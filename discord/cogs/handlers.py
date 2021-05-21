import discord
from discord.ext import commands
from discord.ext.commands.errors import *
import json


DEFAULT_PREFIX='$'

class Handlers(commands.Cog, name='handlers'):
    def __init__(self, client: commands.Bot):
        self.client = client

    @commands.Cog.listener()
    async def on_ready(self):
        print(self.client.user.name + " is ready")
        try:
            await self.client.change_presence(activity=discord.Game("blackjack | $help"))
        except:
            pass

    @commands.Cog.listener()
    async def on_command_error(self, ctx: commands.Context, error):
        if hasattr(ctx.command, 'on_error'):
            return
        ignored = (MissingPermissions, )
        if isinstance(error, CommandNotFound):
            await self.client.get_command('help')(ctx)

        elif isinstance(error, (MissingRequiredArgument, TooManyArguments)):
            await self.client.get_command('help')(ctx, ctx.command.name)

        elif isinstance(error, (UserNotFound, MemberNotFound)):
            await ctx.send(f"Member, `{error.argument}`, was not found.")

        elif isinstance(error, MissingPermissions):
            await ctx.send("Must have following permission(s): " + ", ".join([f'`{perm}`' for perm in error.missing_perms]))

        elif isinstance(error, BotMissingPermissions):
            await ctx.send("I must have following permission(s): " + ", ".join([f'`{perm}`' for perm in error.missing_perms]))

        else:
            raise error

def setup(client: commands.Bot):
    client.add_cog(Handlers(client))