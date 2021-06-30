import helpers  # type:ignore
from discord.ext import commands


class Help(commands.Cog):
    def __init__(self, client: commands.Bot):
        self.client = client

    @commands.command(brief="Lists commands and gives info.", usage="help *command", hidden=True)
    async def help(self, ctx, request=None):
        if not request:
            embed = helpers.make_embed(title="Commands")
            commands_list = [(name, [command for command in cog.get_commands() if not command.hidden]) for name, cog in self.client.cogs.items()]
            for name, cog_commands in commands_list:
                if len(cog_commands) != 0:
                    embed.add_field(
                        name=name,
                        value='\n'.join([f'{self.client.command_prefix}{command}' for command in cog_commands]),
                        inline=True
                        )
        else:
            com = self.client.get_command(request)
            if not com:
                await self.get_commands('help')(ctx)
                return
            embed = helpers.make_embed(title=com.name, description=com.brief, footer="* optional")                       
            embed.add_field(name='Usage:', value='`'+self.client.command_prefix+com.usage+'`')
        await ctx.send(embed=embed)

    @commands.command(hidden=True)
    @commands.is_owner()
    async def kill(self, ctx: commands.Context):
        self.client.remove_cog('handlers')
        await self.client.logout()


def setup(client):
    client.add_cog(Help(client))
