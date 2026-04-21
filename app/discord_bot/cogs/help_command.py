import os

import discord
from discord.ext import commands

from app.discord_bot.modules.helpers import ABS_PATH, make_embed


class Help(commands.Cog, name="help"):
    def __init__(self, client: commands.Bot):
        self.client = client

    def _format_command(self, command: commands.Command) -> str:
        base_name = f"{self.client.command_prefix}{command.name}"
        if not command.aliases:
            return base_name
        aliases = ", ".join(
            f"{self.client.command_prefix}{alias}" for alias in command.aliases
        )
        return f"{base_name} ({aliases})"

    @commands.command(
        brief="Lists commands and gives info.",
        usage="help *command",
        hidden=True,
    )
    async def help(self, ctx: commands.Context, request: str | None = None):
        if not request:
            embed = make_embed(title="Commands")
            for name, cog in self.client.cogs.items():
                cog_commands = [command for command in cog.get_commands() if not command.hidden]
                if not cog_commands:
                    continue
                embed.add_field(
                    name=name,
                    value="\n".join(self._format_command(command) for command in cog_commands),
                    inline=False,
                )

            fp = os.path.join(ABS_PATH, "modules/cards/aces.png")
            file = discord.File(fp, filename="aces.png")
            embed.set_thumbnail(url="attachment://aces.png")
        else:
            command = self.client.get_command(request)
            if command is None:
                await ctx.invoke(self.client.get_command("help"))
                return
            embed = make_embed(
                title=command.name,
                description=command.brief,
                footer="* optional",
            )
            embed.add_field(
                name="Usage:",
                value=f"`{self.client.command_prefix}{command.usage}`",
            )
            if command.aliases:
                aliases = ", ".join(
                    f"`{self.client.command_prefix}{alias}`"
                    for alias in command.aliases
                )
                embed.add_field(name="Aliases:", value=aliases)
            file = None

        await ctx.send(file=file, embed=embed)

    @commands.command(hidden=True)
    @commands.is_owner()
    async def kill(self, ctx: commands.Context):
        self.client.remove_cog("handlers")
        await self.client.close()


async def setup(client: commands.Bot):
    await client.add_cog(Help(client))
