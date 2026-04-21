from os import getenv

from dotenv import load_dotenv
from pydantic import BaseModel, Field

__all__ = (
    "load_config",
    "env_vars",
)

load_dotenv()


class BotConfig(BaseModel):
    token: str = ""
    prefix: str = "$"
    owner_ids: list[int] = Field(default_factory=list)
    default_bet: int = 100
    bonus_multiplier: int = 5
    bonus_cooldown: int = 12


class Config(BaseModel):
    bot: BotConfig


env_vars = (
    "DISCORD_TOKEN",
    "DISCORD_PREFIX",
    "DISCORD_OWNER_IDS",
    "DISCORD_DEFAULT_BET",
    "DISCORD_BONUS_MULTIPLIER",
    "DISCORD_BONUS_COOLDOWN",
)


def _parse_owner_ids(raw_owner_ids: str | None) -> list[int]:
    if not raw_owner_ids:
        return []
    return [int(owner_id.strip()) for owner_id in raw_owner_ids.split(",") if owner_id.strip()]


def load_config() -> Config:
    bot = BotConfig(
        token=(getenv("DISCORD_TOKEN", "").strip()),
        prefix=getenv("DISCORD_PREFIX", "$"),
        owner_ids=_parse_owner_ids(getenv("DISCORD_OWNER_IDS")),
        default_bet=int(getenv("DISCORD_DEFAULT_BET", 100)),
        bonus_multiplier=int(getenv("DISCORD_BONUS_MULTIPLIER", 5)),
        bonus_cooldown=int(getenv("DISCORD_BONUS_COOLDOWN", 12)),
    )
    return Config(bot=bot)


config = load_config()
