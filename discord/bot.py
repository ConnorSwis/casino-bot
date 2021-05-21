import discord
from discord.ext import commands
import os


PREFIX = '$'
TOKEN = 'XXX'
intents = discord.Intents.all()
client = commands.Bot(command_prefix=PREFIX, owner_id=640393413425889314, intents=intents)

client.remove_command('help')

COG_FOLDER = './cogs'
for filename in os.listdir(COG_FOLDER):
    if filename.endswith('.py'):
        client.load_extension(f'cogs.{filename[:-3]}')

client.run(TOKEN)
