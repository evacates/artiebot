import discord
from discord import app_commands
from discord.ext import commands
import config

def _slug(role_name: str) -> str:
    return (
        role_name.lower()
        .replace(" ", "_")
        .replace("/", "_")
        .replace("\\", "_")
        .replace(":", "_")
    )

async def _toggle_role(interaction: discord.Interaction, role_name: str):
    guild = interaction.guild
    if guild is None:
        return await interaction.response.send_message("Server only.", ephemeral=True)

    role = discord.utils.get(guild.roles, name=role_name)
    if role is None:
        return await interaction.response.send_message(
            f"Role '{role_name}' not found.",
            ephemeral=True
        )

    member = interaction.user
    if not isinstance(member, discord.Member):
        member = await guild.fetch_member(interaction.user.id)

    try:
        if role in member.roles:
            await member.remove_roles(role, reason="Role toggle (Artie)")
            await interaction.response.send_message(f"Removed **{role_name}**.", ephemeral=True)
        else:
            await member.add_roles(role, reason="Role toggle (Artie)")
            await interaction.response.send_message(f"Added **{role_name}**.", ephemeral=True)
    except discord.Forbidden:
        await interaction.response.send_message(
            "I don’t have permission to manage that role.",
            ephemeral=True
        )


def _medium_button_id(role_name: str) -> str:
    return f"artie:medium:{_slug(role_name)}"

class MediumRoleButton(discord.ui.Button):
    def __init__(self, role_name: str):
        super().__init__(
            label=role_name,
            style=discord.ButtonStyle.secondary,
            custom_id=_medium_button_id(role_name),
        )
        self.role_name = role_name

    async def callback(self, interaction: discord.Interaction):
        await _toggle_role(interaction, self.role_name)

class MediumRolesView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        for i, rn in enumerate(config.MEDIUM_ROLE_NAMES):
            btn = MediumRoleButton(rn)
            btn.row = i // 5
            self.add_item(btn)


def _pronoun_button_id(role_name: str) -> str:
    return f"artie:pronoun:{_slug(role_name)}"

class PronounRoleButton(discord.ui.Button):
    def __init__(self, role_name: str):
        super().__init__(
            label=role_name,
            style=discord.ButtonStyle.secondary,
            custom_id=_pronoun_button_id(role_name),
        )
        self.role_name = role_name

    async def callback(self, interaction: discord.Interaction):
        await _toggle_role(interaction, self.role_name)

class PronounRolesView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        for i, rn in enumerate(config.PRONOUN_ROLE_NAMES):
            btn = PronounRoleButton(rn)
            btn.row = i // 5
            self.add_item(btn)


# --- Notification roles (Daily Doodler, Live Viewer) — buttons, no emojis ---

def _notification_button_id(role_name: str) -> str:
    return f"artie:notification:{_slug(role_name)}"

class NotificationRoleButton(discord.ui.Button):
    def __init__(self, role_name: str):
        super().__init__(
            label=role_name,
            style=discord.ButtonStyle.secondary,
            custom_id=_notification_button_id(role_name),
        )
        self.role_name = role_name

    async def callback(self, interaction: discord.Interaction):
        await _toggle_role(interaction, self.role_name)

class NotificationRolesView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        for i, rn in enumerate(config.NOTIFICATION_ROLE_NAMES):
            btn = NotificationRoleButton(rn)
            btn.row = i // 5
            self.add_item(btn)

class Roles(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.bot.add_view(MediumRolesView())
        self.bot.add_view(PronounRolesView())
        self.bot.add_view(NotificationRolesView())

    @app_commands.command(
        name="post_notification_roles",
        description="Post the notification roles message (Daily Doodler, Live Viewer). Staff only.",
    )
    @app_commands.checks.has_permissions(manage_guild=True)
    async def post_notification_roles(self, interaction: discord.Interaction):
        if interaction.guild is None:
            return await interaction.response.send_message("Server only.", ephemeral=True)
        channel = interaction.guild.get_channel(config.ROLES_CHANNEL_ID)
        if not isinstance(channel, discord.TextChannel):
            return await interaction.response.send_message(
                "ROLES_CHANNEL_ID is not configured.",
                ephemeral=True,
            )
        lines = [
            "Would you like to be notified when we post new daily doodles or when @keyresonance is live?",
            "",
            "Daily Doodler — pings when there’s a new daily doodle theme",
            "Live Viewer — pings when @keyresonance is live",
        ]
        await channel.send("\n".join(lines), view=NotificationRolesView())
        await interaction.response.send_message(
            "Notification roles message posted. Buttons are active.",
            ephemeral=True,
        )

    # @app_commands.command(
    #     name="post_medium_roles",
    #     description="Post the medium role buttons panel (staff only)."
    # )
    # @app_commands.checks.has_permissions(manage_guild=True)
    # async def post_medium_roles(self, interaction: discord.Interaction):
    #     if interaction.guild is None:
    #         return await interaction.response.send_message("Server only.", ephemeral=True)

    #     channel = interaction.guild.get_channel(config.ROLES_CHANNEL_ID)
    #     if not isinstance(channel, discord.TextChannel):
    #         return await interaction.response.send_message(
    #             "ROLES_CHANNEL_ID is not configured correctly.",
    #             ephemeral=True
    #         )

    #     await channel.send("What mediums do you use?", view=MediumRolesView())

    # @app_commands.command(
    #     name="post_pronoun_roles",
    #     description="Post the pronoun role buttons panel (staff only)."
    # )
    # @app_commands.checks.has_permissions(manage_guild=True)
    # async def post_pronoun_roles(self, interaction: discord.Interaction):
    #     if interaction.guild is None:
    #         return await interaction.response.send_message("Server only.", ephemeral=True)

    #     channel = interaction.guild.get_channel(config.ROLES_CHANNEL_ID)
    #     if not isinstance(channel, discord.TextChannel):
    #         return await interaction.response.send_message(
    #             "ROLES_CHANNEL_ID is not configured correctly.",
    #             ephemeral=True
    #         )

    #     await channel.send("What pronouns do you use?", view=PronounRolesView())


async def setup(bot: commands.Bot):
    await bot.add_cog(Roles(bot))

