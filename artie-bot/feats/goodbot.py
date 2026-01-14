import discord
from discord.ext import commands

class GoodBot(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot:
            return

        if self.bot.user is None or self.bot.user not in message.mentions:
            return

        content = (message.content or "").lower()

        if "good bot" in content:
            await message.reply(f"Thank you {message.author.mention}.", mention_author=False)

async def setup(bot: commands.Bot):
    await bot.add_cog(GoodBot(bot))
