import json
import os
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


# --- Notification reaction roles (Daily Doodler, Live Viewer) ---

def _load_reaction_roles_data() -> dict | None:
    path = config.REACTION_ROLES_DATA_PATH
    if not os.path.isfile(path):
        return None
    try:
        with open(path) as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return None


def _save_reaction_roles_data(channel_id: int, message_id: int):
    path = config.REACTION_ROLES_DATA_PATH
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        json.dump({"channel_id": channel_id, "message_id": message_id}, f)


def _emoji_to_notification_role(emoji: str | discord.PartialEmoji) -> str | None:
    name = emoji if isinstance(emoji, str) else (emoji.name or "")
    for i, emoji_name in enumerate(config.NOTIFICATION_REACTION_EMOJI_NAMES):
        if emoji_name == name and i < len(config.NOTIFICATION_ROLE_NAMES):
            return config.NOTIFICATION_ROLE_NAMES[i]
    return None


async def _apply_notification_reaction(
    payload: discord.RawReactionActionEvent,
    guild: discord.Guild,
    add: bool,
):
    role_name = _emoji_to_notification_role(payload.emoji)
    if role_name is None:
        return
    role = discord.utils.get(guild.roles, name=role_name)
    if role is None:
        return
    member = guild.get_member(payload.user_id)
    if member is None:
        try:
            member = await guild.fetch_member(payload.user_id)
        except discord.NotFound:
            return
    if member.bot:
        return
    try:
        if add:
            await member.add_roles(role, reason="Reaction role (Artie)")
        else:
            await member.remove_roles(role, reason="Reaction role (Artie)")
    except discord.Forbidden:
        pass

class Roles(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.bot.add_view(MediumRolesView())
        self.bot.add_view(PronounRolesView())

    @commands.Cog.listener()
    async def on_raw_reaction_add(self, payload: discord.RawReactionActionEvent):
        if payload.guild_id is None or payload.user_id == self.bot.user.id:
            return
        data = _load_reaction_roles_data()
        if data is None or data.get("message_id") != payload.message_id:
            return
        if data.get("channel_id") != payload.channel_id:
            return
        guild = self.bot.get_guild(payload.guild_id)
        if guild is None:
            return
        await _apply_notification_reaction(payload, guild, add=True)

    @commands.Cog.listener()
    async def on_raw_reaction_remove(self, payload: discord.RawReactionActionEvent):
        if payload.guild_id is None:
            return
        data = _load_reaction_roles_data()
        if data is None or data.get("message_id") != payload.message_id:
            return
        if data.get("channel_id") != payload.channel_id:
            return
        guild = self.bot.get_guild(payload.guild_id)
        if guild is None:
            return
        await _apply_notification_reaction(payload, guild, add=False)

    @app_commands.command(
        name="post_notification_roles",
        description="Post the notification reaction-roles message (Daily Doodler, Live Viewer). Staff only.",
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
        await interaction.response.defer(ephemeral=True)
        missing = [
            name for name in config.NOTIFICATION_REACTION_EMOJI_NAMES
            if discord.utils.get(interaction.guild.emojis, name=name) is None
        ]
        if missing:
            await interaction.followup.send(
                f"Custom emoji(s) not found: {', '.join(missing)}. Create them in Server Settings → Emoji with those exact names (no spaces).",
                ephemeral=True,
            )
            return
        lines = [
            "**Get notified** — react below with the matching reaction to opt in:",
            "",
            "**Daily Doodler** — pings when there’s a new daily doodle theme",
            "**Live Viewer** — pings when the server owner is live on TikTok",
        ]
        msg = await channel.send("\n".join(lines))
        for emoji_name in config.NOTIFICATION_REACTION_EMOJI_NAMES:
            emoji = discord.utils.get(interaction.guild.emojis, name=emoji_name)
            await msg.add_reaction(emoji)
        _save_reaction_roles_data(channel.id, msg.id)
        await interaction.followup.send(
            "Notification roles message posted. Reactions are active.",
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

