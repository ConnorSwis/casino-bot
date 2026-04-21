from datetime import datetime
from pathlib import Path

from discord import Color, Embed


class InsufficientFundsException(Exception):
    def __init__(self, current, bet) -> None:
        self.needs = bet - current
        super().__init__()

    def __str__(self) -> str:
        return f"${self.needs} more needed to play."


class InsufficientCreditsException(Exception):
    def __init__(self, current: int, required: int) -> None:
        self.needs = required - current
        super().__init__()

    def __str__(self) -> str:
        return f"{self.needs} more credits needed."


ABS_PATH = Path(__file__).resolve().parent.parent
COG_FOLDER = str(ABS_PATH / "cogs")


def make_embed(title=None, description=None, color=None, author=None,
               image=None, link=None, footer=None) -> Embed:
    """Wrapper for making discord embeds"""
    embed = Embed(
        title=title or None,
        description=description or None,
        url=link or None,
        color=color if color else Color.random()
    )
    if author:
        embed.set_author(name=author)
    if image:
        embed.set_image(url=image)
    if footer:
        embed.set_footer(text=footer)
    else:
        embed.set_footer(text=datetime.now().strftime("%m/%d/%Y %H:%M:%S"))
    return embed
