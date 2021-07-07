import os

import discord
from discord.ext import commands
from modules.helpers import *  # type:ignore
from cogs.help_command import Help
from cogs.handlers import Handlers
from cogs.gambling import Slots


client = commands.Bot(
    command_prefix=PREFIX,  # type:ignore
    owner_ids=OWNER_IDS,  # type:ignore
    intents=discord.Intents.all()
)

client.remove_command('help')

COGS = [Help, Handlers, Slots]
for cog in COGS:
    client.add_cog(cog(client))

client.run(TOKEN)  # type:ignore
