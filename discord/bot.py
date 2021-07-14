import discord
from cogs.gambling import Slots
from cogs.handlers import Handlers
from cogs.help_command import Help
from discord.ext import commands
from modules.helpers import *


client = commands.Bot(
    command_prefix=PREFIX,
    owner_ids=OWNER_IDS,
    intents=discord.Intents.all()
)

client.remove_command('help')

COGS = [Help, Handlers, Slots]
for Cog in COGS:
    client.add_cog(Cog(client))

client.run(TOKEN)
