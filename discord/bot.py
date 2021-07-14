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
for cog in COGS:
    client.add_cog(cog(client))

client.run(TOKEN)
