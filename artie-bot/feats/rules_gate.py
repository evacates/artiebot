import discord
from discord import app_commands
from discord.ext import commands
import config


RULES_TEXT = (
    "## Keyresonant Workshop · Community Rules\n\n"
    "**Originality:** Don't post other people's work as your own, and any use of AI will not be tolerated!\n\n"
    "**NSFW Content:** Please no NSFW content in the main channels. Keeping this place a good space for networking and community!\n\n"
    "**Appropriate Channels:** Please try to keep things organized. If you've got something to share, be sure to use the right channel.\n\n"
    "**Spam:** Please refrain from spamming or abusing mentions.\n\n"
    "**Respect:** We want to keep this place a fun and collaborative art community that uplifts other artists. "
    "So please be kind and treat everyone with respect!\n\n"
    "**Critique & Feedback:** Please don’t criticize or give feedback on someone’s work unless they are explicitly asking for it.\n\n"
    "**Have fun:** Make art, friends, and enjoy the community!\n\n"
    "By clicking the button below, you agree to these rules and will receive access to the rest of the server.\n\n"
)


class RulesGateView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(
        label="I agree",
        style=discord.ButtonStyle.secondary,
        custom_id="artie:rules:agree"
    )
    async def agree(self, interaction: discord.Interaction, button: discord.ui.Button):
        guild = interaction.guild
        if guild is None:
            return await interaction.response.send_message(
                "This only works in a server.",
                ephemeral=True
            )

        role = discord.utils.get(guild.roles, name=config.RESONATOR_ROLE_NAME)
        if role is None:
            return await interaction.response.send_message(
                f"Role '{config.RESONATOR_ROLE_NAME}' not found.",
                ephemeral=True
            )

        member = interaction.user
        if not isinstance(member, discord.Member):
            member = await guild.fetch_member(interaction.user.id)

        if role in member.roles:
            return await interaction.response.send_message(
                "You already have access.",
                ephemeral=True
            )

        try:
            await member.add_roles(role, reason="Agreed to rules (Artie)")
        except discord.Forbidden:
            return await interaction.response.send_message(
                "I don’t have permission to assign that role.",
                ephemeral=True
            )

        await interaction.response.send_message("Access granted.", ephemeral=True)


class RulesGate(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    # temp command to spawn rules blurb.
    # @app_commands.command(name="post_rules_gate", description="Post the rules + agreement button (staff only).")
    # @app_commands.checks.has_permissions(manage_guild=True)
    # async def post_rules_gate(self, interaction: discord.Interaction):
    #     if interaction.guild is None:
    #         return await interaction.response.send_message("Server only.", ephemeral=True)
    #
    #     rules_channel = interaction.guild.get_channel(config.RULES_CHANNEL_ID)
    #     if not isinstance(rules_channel, discord.TextChannel):
    #         return await interaction.response.send_message(
    #             "RULES_CHANNEL_ID is not configured correctly.",
    #             ephemeral=True
    #         )
    #
    #     await rules_channel.send(content=RULES_TEXT, view=RulesGateView())
    #     await interaction.response.send_message("Posted the rules gate message.", ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(RulesGate(bot))
    bot.add_view(RulesGateView())
