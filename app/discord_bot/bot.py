import logging

import discord
from discord.ext import commands

from app.config import config
from app.discord_bot.cogs import (
    Blackjack,
    Gambling,
    GamblingHelpers,
    Handlers,
    Help,
    Slots,
)
from app.discord_bot.modules.economy import Economy

logger = logging.getLogger(__name__)

COGS = (
    Blackjack,
    GamblingHelpers,
    Gambling,
    Handlers,
    Help,
    Slots,
)


def build_intents() -> discord.Intents:
    intents = discord.Intents.default()
    intents.guilds = True
    intents.messages = True
    intents.message_content = True
    intents.members = True
    return intents


class CasinoBot(commands.Bot):
    def __init__(self) -> None:
        super().__init__(
            command_prefix=config.bot.prefix,
            owner_ids=set(config.bot.owner_ids),
            intents=build_intents(),
        )
        self.remove_command("help")
        self._cogs_loaded = False
        self.economy = Economy()

    async def setup_hook(self) -> None:
        await register_cogs(self)

    async def close(self) -> None:
        try:
            self.economy.close()
        finally:
            await super().close()


client = CasinoBot()


async def register_cogs(bot: commands.Bot | None = None) -> None:
    bot = bot or client
    if isinstance(bot, CasinoBot) and bot._cogs_loaded:
        return

    for cog in COGS:
        if bot.get_cog(cog.__name__):
            continue
        await bot.add_cog(cog(bot))
        logger.info("Loaded cog: %s", cog.__name__)

    if isinstance(bot, CasinoBot):
        bot._cogs_loaded = True
