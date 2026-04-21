import os
from datetime import datetime
from pathlib import Path

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

def _env_int(name: str, default: int) -> int:
    value = os.getenv(name)
    if value is None:
        return default
    try:
        return int(value)
    except ValueError:
        return default

TOKEN = os.getenv('DISCORD_TOKEN')
PREFIX = os.getenv('DISCORD_PREFIX', '$')

owner_ids = os.getenv('DISCORD_OWNER_IDS', '')
OWNER_IDS = {int(owner_id.strip()) for owner_id in owner_ids.split(',')
             if owner_id.strip().isdigit()} or None

DEFAULT_BET = _env_int('DISCORD_DEFAULT_BET', 100)
B_MULT = _env_int('DISCORD_BONUS_MULTIPLIER', 5)
B_COOLDOWN = _env_int('DISCORD_BONUS_COOLDOWN', 12)


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
