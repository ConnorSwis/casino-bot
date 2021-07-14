import os
import discord
from modules.helpers import ABS_PATH, make_embed
from discord.ext import commands
import os


class Help(commands.Cog, name='help'):
    def __init__(self, client: commands.Bot):
        self.client = client

    @commands.command(
        brief="Lists commands and gives info.",
        usage="help *command",
        hidden=True
    )
    async def help(self, ctx, request=None):
        if not request:
            embed = make_embed(title="Commands")
            commands_list = [
                (
                    name, [command for command in cog.get_commands()\
                        if not command.hidden]
                ) for name, cog in self.client.cogs.items()
            ]
            for name, cog_commands in commands_list:
                if len(cog_commands) != 0:
                    embed.add_field(
                        name=name,
                        value='\n'.join(
                            [f'{self.client.command_prefix}{command}'
                                for command in cog_commands]
                        ),
                        inline=False
                    )
            fp = os.path.join(ABS_PATH, 'modules/cards/aces.png')
            file = discord.File(fp, filename='aces.png')
            embed.set_thumbnail(url=f"attachment://aces.png")
        else:
            com = self.client.get_command(request)
            if not com:
                await ctx.invoke(self.client.get_command('help'))
                return
            embed = make_embed(
                title=com.name, description=com.brief, footer="* optional"
            )                       
            embed.add_field(
                name='Usage:',
                value='`'+self.client.command_prefix+com.usage+'`'
            )
            file = None
        await ctx.send(file=file, embed=embed)


    @commands.command(hidden=True)
    @commands.is_owner()
    async def kill(self, ctx: commands.Context):
        self.client.remove_cog('handlers')
        await self.client.logout()


def setup(client):
    client.add_cog(Help(client))
