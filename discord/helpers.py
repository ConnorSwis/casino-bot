import random
from datetime import datetime

import discord


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