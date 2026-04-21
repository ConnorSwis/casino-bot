import json
import logging
from typing import Any

from discord.ext import commands


def log_wallet_change(
    logger: logging.Logger,
    *,
    event: str,
    user_id: int,
    money_delta: int = 0,
    credits_delta: int = 0,
    ctx: commands.Context | None = None,
    **metadata: Any,
) -> None:
    payload: dict[str, Any] = {
        "event": event,
        "user_id": user_id,
        "money_delta": money_delta,
        "credits_delta": credits_delta,
        "command": ctx.command.qualified_name if ctx and ctx.command else None,
        "guild_id": ctx.guild.id if ctx and ctx.guild else None,
        "channel_id": ctx.channel.id if ctx and ctx.channel else None,
    }
    payload.update(metadata)
    logger.info("wallet_change %s", json.dumps(payload, sort_keys=True))
