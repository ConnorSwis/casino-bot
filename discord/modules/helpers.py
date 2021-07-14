import os
from datetime import datetime
from pathlib import Path

import yaml
from discord import Color, Embed


class InsufficientFundsException(Exception):
    def __init__(self, current, bet) -> None:
        self.needs = bet - current
        super().__init__()

    def __str__(self) -> str:
        return f"${self.needs} more needed to play."

os.chdir(Path(__file__).parent.parent)
ABS_PATH = Path(os.getcwd())
COG_FOLDER = os.path.join(ABS_PATH, 'cogs/')

with open(os.path.join(ABS_PATH.parent, 'config.yml'),  # type:ignore
            'r', encoding='utf-8') as f:
    config = yaml.safe_load(f.read()).get('bot', {})

TOKEN = config.get('token')
PREFIX = config.get('prefix', '$')
OWNER_IDS = config.get('owner_ids')
DEFAULT_BET = config.get('default_bet', 100)
B_MULT = config.get('bonus_multiplier', 5)
B_COOLDOWN = config.get('bonus_cooldown', 12)


def make_embed(title=None, description=None, color=None, author=None,
               image=None, link=None, footer=None) -> Embed:
    """Wrapper for making discord embeds"""
    arg = lambda x: x if x else Embed.Empty
    embed = Embed(
        title=arg(title),
        description=arg(description),
        url=arg(link),
        color=color if color else Color.random()
    )
    if author: embed.set_author(name=author)
    if image: embed.set_image(url=image)
    if footer: embed.set_footer(text=footer)
    else: embed.set_footer(text=datetime.now().strftime("%m/%d/%Y %H:%M:%S"))
    return embed
