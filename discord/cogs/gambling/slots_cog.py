from discord.ext import commands
from .blackjack import Blackjack

class Slots(Blackjack):
    def __init__(self, client: commands.Bot):
        self.client = client
        super().__init__(self.client)

    @commands.command()
    async def test(self, ctx):
        pass
