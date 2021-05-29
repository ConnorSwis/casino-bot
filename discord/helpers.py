import os
import pathlib
import random
from datetime import datetime

import yaml

import discord


ABS_PATH = pathlib.Path(__file__).parent.absolute()
COG_FOLDER = os.path.join(ABS_PATH, 'cogs/')

with open(os.path.join(ABS_PATH.parent, 'config.yml'),  # type:ignore
            'r', encoding='utf-8') as f:
    config = yaml.safe_load(f.read()).get('bot', {})

TOKEN = config.get('token')
PREFIX = config.get('prefix', '$')
owner_ids = config.get('owner_ids')
DEFAULT_BET = config.get('default_bet', 100)


def make_embed(title=None, description=None, color=None, author=None,
               image=None, link=None, footer=None) -> discord.Embed:
    """Wrapper for making discord embeds"""
    arg = lambda x: x if x else discord.Embed.Empty
    embed = discord.Embed(
        title=arg(title),
        description=arg(description),
        url=arg(link),
        color=color if color else discord.Color.random()
    )
    if author: embed.set_author(name=author)
    if image: embed.set_image(url=image)
    if footer: embed.set_footer(text=footer)
    else: embed.set_footer(text=datetime.now().strftime("%m/%d/%Y %H:%M:%S"))
    return embed
