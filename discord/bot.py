import os

import discord
from discord.ext import commands
from helpers import *  # type:ignore


client = commands.Bot(
    command_prefix=PREFIX,  # type:ignore
    owner_ids=OWNER_IDS,  # type:ignore
    intents=discord.Intents.all()
)

client.remove_command('help')

for filename in os.listdir(COG_FOLDER):  # type:ignore
    if filename.endswith('.py'):
        client.load_extension(f'cogs.{filename[:-3]}')

client.run(TOKEN)  # type:ignore
