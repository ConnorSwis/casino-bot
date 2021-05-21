import discord
from discord.ext import commands
import os


TOKEN = 'XXX'
owner_ids = [123456789012345678]

PREFIX = '$'
intents = discord.Intents.all()
client = commands.Bot(command_prefix=PREFIX, owner_ids=owner_ids, intents=intents)

client.remove_command('help')

COG_FOLDER = './cogs'
for filename in os.listdir(COG_FOLDER):
    if filename.endswith('.py'):
        client.load_extension(f'cogs.{filename[:-3]}')

client.run(TOKEN)
