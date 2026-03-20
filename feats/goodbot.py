import discord
from discord.ext import commands
import config
from feats.utils import reply_mention


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

        if message.author.id == config.MAMA_USER_ID and "?" in content:
            await message.reply("yes mama", mention_author=False)
            return

        if "good bot" in content:
            await message.reply(f"Thank you {reply_mention(message.author)}.", mention_author=False)

async def setup(bot: commands.Bot):
    await bot.add_cog(GoodBot(bot))
