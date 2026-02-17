import discord
from discord.ext import commands
import config
from feats.utils import reply_mention

# welcome 
class Welcome(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    async def send_welcome(self, member: discord.Member):
        channel = member.guild.get_channel(config.WELCOME_CHANNEL_ID)
        if not isinstance(channel, discord.TextChannel):
            return

        rules = member.guild.get_channel(config.RULES_CHANNEL_ID)
        roles = member.guild.get_channel(config.ROLES_CHANNEL_ID)

        rules_mention = rules.mention if rules else "#rules"
        roles_mention = roles.mention if roles else "#roles"

        await channel.send(
            f"Hello {reply_mention(member)}, welcome to the Keyresonant Workshop!\n\n"
            f"You’ll find the key to the rest of the server in {rules_mention}.\n"
            f"When you’re ready, you can shape your presence in {roles_mention}.\n\n"
        )

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        await self.send_welcome(member)


async def setup(bot: commands.Bot):
    await bot.add_cog(Welcome(bot))
