from os import getenv
from pathlib import Path

from dotenv import load_dotenv
from pydantic import BaseModel, Field, ValidationError

__all__ = (
    "load_config",
    "env_vars",
)

load_dotenv()
REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DATA_DIR = REPO_ROOT / "data"


class BotConfig(BaseModel):
    token: str = ""
    prefix: str = Field(default="$", min_length=1, max_length=8)
    owner_ids: list[int] = Field(default_factory=list)
    default_bet: int = Field(default=100, ge=1, le=1_000_000)
    bonus_multiplier: int = Field(default=5, ge=1, le=1_000)
    bonus_cooldown: int = Field(default=12, ge=1, le=168)


class StorageConfig(BaseModel):
    data_dir: Path
    database_path: Path
    log_path: Path


class Config(BaseModel):
    bot: BotConfig
    storage: StorageConfig


env_vars = (
    "DISCORD_TOKEN",
    "DISCORD_PREFIX",
    "DISCORD_OWNER_IDS",
    "DISCORD_DEFAULT_BET",
    "DISCORD_BONUS_MULTIPLIER",
    "DISCORD_BONUS_COOLDOWN",
    "CASINO_DATA_DIR",
    "CASINO_DATABASE_PATH",
    "CASINO_LOG_PATH",
)


def _parse_owner_ids(raw_owner_ids: str | None) -> list[int]:
    if not raw_owner_ids:
        return []
    return [int(owner_id.strip()) for owner_id in raw_owner_ids.split(",") if owner_id.strip()]


def _parse_int_env(name: str, default: int) -> int:
    raw = getenv(name)
    if raw is None or raw.strip() == "":
        return default
    return int(raw.strip())


def _parse_path_env(name: str, default: Path) -> Path:
    raw = getenv(name)
    if raw is None or raw.strip() == "":
        candidate = default
    else:
        candidate = Path(raw.strip()).expanduser()
    if not candidate.is_absolute():
        candidate = REPO_ROOT / candidate
    return candidate.resolve()


def load_config() -> Config:
    try:
        bot = BotConfig(
            token=(getenv("DISCORD_TOKEN", "").strip()),
            prefix=getenv("DISCORD_PREFIX", "$"),
            owner_ids=_parse_owner_ids(getenv("DISCORD_OWNER_IDS")),
            default_bet=_parse_int_env("DISCORD_DEFAULT_BET", 100),
            bonus_multiplier=_parse_int_env("DISCORD_BONUS_MULTIPLIER", 5),
            bonus_cooldown=_parse_int_env("DISCORD_BONUS_COOLDOWN", 12),
        )
        data_dir = _parse_path_env("CASINO_DATA_DIR", DEFAULT_DATA_DIR)
        database_path = _parse_path_env(
            "CASINO_DATABASE_PATH",
            data_dir / "economy.db",
        )
        log_path = _parse_path_env(
            "CASINO_LOG_PATH",
            data_dir / "logs" / "casino-bot.log",
        )
        data_dir.mkdir(parents=True, exist_ok=True)
        database_path.parent.mkdir(parents=True, exist_ok=True)
        log_path.parent.mkdir(parents=True, exist_ok=True)
        storage = StorageConfig(
            data_dir=data_dir,
            database_path=database_path,
            log_path=log_path,
        )
        return Config(bot=bot, storage=storage)
    except (ValueError, ValidationError) as exc:
        raise RuntimeError(f"Invalid bot configuration: {exc}") from exc


config = load_config()
