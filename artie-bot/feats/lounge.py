import discord
from discord import app_commands
from discord.ext import commands
import config


def _pickable_role_names() -> list[str]:
    # If you define this list in config, we ONLY use that (best practice).
    if hasattr(config, "LOUNGE_PICK_ROLE_NAMES"):
        return list(config.LOUNGE_PICK_ROLE_NAMES)

    names: list[str] = []
    if hasattr(config, "MEDIUM_ROLE_NAMES"):
        names += list(config.MEDIUM_ROLE_NAMES)
    if hasattr(config, "PRONOUN_ROLE_NAMES"):
        names += list(config.PRONOUN_ROLE_NAMES)
    if hasattr(config, "RESONATOR_ROLE_NAME"):
        names.append(config.RESONATOR_ROLE_NAME)

    # de-dupe while preserving order
    seen = set()
    out: list[str] = []
    for n in names:
        if n not in seen:
            seen.add(n)
            out.append(n)
    return out


def _build_role_options(guild: discord.Guild) -> list[discord.SelectOption]:
    options: list[discord.SelectOption] = []
    for role_name in _pickable_role_names():
        role = discord.utils.get(guild.roles, name=role_name)
        if role is None:
            continue
        options.append(discord.SelectOption(label=role.name, value=str(role.id)))

    # Discord select max options = 25
    return options[:25]


def _clamp_user_limit(n: int) -> int:
    if n < 0:
        return 0
    if n > 99:
        return 99
    return n


def _default_channel_name(interaction: discord.Interaction) -> str:
    return f"{interaction.user.display_name}'s Lounge"[:96]


def _sanitize_channel_name(name: str) -> str:
    name = name.strip()
    if not name:
        name = "Lounge"
    return name[:96]


def _summary_text(channel_name: str, user_limit: int, role_ids: set[int], guild: discord.Guild) -> str:
    limit_txt = "No limit" if user_limit == 0 else str(user_limit)

    if role_ids:
        roles = [guild.get_role(rid) for rid in role_ids]
        roles = [r for r in roles if r is not None]
        role_txt = ", ".join(r.mention for r in roles) if roles else "Selected roles (some missing?)"
    else:
        # Default access = Resonator role, not @everyone
        if hasattr(config, "RESONATOR_ROLE_NAME"):
            base = discord.utils.get(guild.roles, name=config.RESONATOR_ROLE_NAME)
            if base:
                role_txt = f"{base.mention} (default)"
            else:
                role_txt = "Resonator (default)"
        else:
            role_txt = "Baseline role (default)"

    return (
        "**Lounge Setup**\n"
        f"• **Name:** {discord.utils.escape_markdown(channel_name)}\n"
        f"• **User limit:** {limit_txt}\n"
        f"• **Who can join:** {role_txt}\n\n"
        "Buttons: set name / set limit / roles → then **Create Lounge**."
    )


class LoungeCreateView(discord.ui.View):
    def __init__(
        self,
        bot: commands.Bot,
        requester_id: int,
        channel_name: str,
        user_limit: int,
        category_id: int,
        options: list[discord.SelectOption],
        lounge_cog: "Lounge",
    ):
        super().__init__(timeout=180)  # 3 minutes to configure + create
        self.bot = bot
        self.requester_id = requester_id
        self.channel_name = channel_name
        self.user_limit = user_limit
        self.category_id = category_id
        self.lounge_cog = lounge_cog

        self.selected_role_ids: set[int] = set()
        self.setup_message_id: int | None = None  # for modal edits

        if options:
            self.add_item(RoleMultiSelect(options))

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.requester_id:
            await interaction.response.send_message("This isn’t your lounge menu.", ephemeral=True)
            return False
        return True

    async def _edit_setup_message(self, interaction: discord.Interaction):
        guild = interaction.guild
        if guild is None:
            return

        content = _summary_text(self.channel_name, self.user_limit, self.selected_role_ids, guild)

        # Buttons/selects have interaction.message
        if interaction.message is not None:
            if not interaction.response.is_done():
                await interaction.response.edit_message(content=content, view=self)
            else:
                await interaction.edit_original_response(content=content, view=self)
            return

        # Modal submits often don't
        if self.setup_message_id is not None:
            try:
                if not interaction.response.is_done():
                    await interaction.response.defer(ephemeral=True)

                await interaction.followup.edit_message(
                    message_id=self.setup_message_id,
                    content=content,
                    view=self,
                )
            except discord.HTTPException:
                pass

    @discord.ui.button(label="Set Name", style=discord.ButtonStyle.secondary, custom_id="artie:lounge:setname")
    async def set_name_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(NameModal(self))

    @discord.ui.button(label="Set User Limit", style=discord.ButtonStyle.secondary, custom_id="artie:lounge:setlimit")
    async def set_limit_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(LimitModal(self))

    @discord.ui.button(label="Reset Roles (Default)", style=discord.ButtonStyle.secondary, custom_id="artie:lounge:resetroles")
    async def reset_roles_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.selected_role_ids.clear()
        await self._edit_setup_message(interaction)

    @discord.ui.button(label="Create Lounge", style=discord.ButtonStyle.primary, custom_id="artie:lounge:create")
    async def create_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        guild = interaction.guild
        if guild is None:
            return await interaction.response.send_message("Server only.", ephemeral=True)

        category = guild.get_channel(self.category_id)
        if not isinstance(category, discord.CategoryChannel):
            return await interaction.response.send_message("Lounge category not configured.", ephemeral=True)

        # Baseline role (Resonator) is used when no roles are selected
        baseline_role = None
        if hasattr(config, "RESONATOR_ROLE_NAME"):
            baseline_role = discord.utils.get(guild.roles, name=config.RESONATOR_ROLE_NAME)

        # Always explicit overwrites so we don't inherit a locked category unexpectedly
        overwrites: dict[discord.abc.Snowflake, discord.PermissionOverwrite] = {}

        # Always deny @everyone so non-verified users can't see/join
        overwrites[guild.default_role] = discord.PermissionOverwrite(view_channel=False, connect=False)

        # Always allow creator
        if isinstance(interaction.user, discord.Member):
            overwrites[interaction.user] = discord.PermissionOverwrite(
                view_channel=True,
                connect=True,
                manage_channels=True,
                move_members=True
            )

        # Always allow bot
        if self.bot.user:
            bot_member = guild.get_member(self.bot.user.id)
            if bot_member is not None:
                overwrites[bot_member] = discord.PermissionOverwrite(
                    view_channel=True,
                    connect=True,
                    manage_channels=True,
                    move_members=True
                )

        if self.selected_role_ids:
            # Private to selected roles
            for rid in self.selected_role_ids:
                role = guild.get_role(rid)
                if role is not None:
                    overwrites[role] = discord.PermissionOverwrite(view_channel=True, connect=True)
        else:
            # Default access = baseline role (Resonator)
            if baseline_role is None:
                return await interaction.response.send_message(
                    "Baseline role not found (RESONATOR_ROLE_NAME). Can’t create the default lounge.",
                    ephemeral=True
                )
            overwrites[baseline_role] = discord.PermissionOverwrite(view_channel=True, connect=True)

        try:
            vc = await guild.create_voice_channel(
                name=self.channel_name,
                category=category,
                user_limit=self.user_limit,
                overwrites=overwrites,
                reason=f"Temp lounge created by {interaction.user} via Artie"
            )

            self.lounge_cog.temp_lounge_channels.add(vc.id)

            if self.selected_role_ids:
                roles = [guild.get_role(rid) for rid in self.selected_role_ids]
                roles = [r for r in roles if r is not None]
                privacy = " · allowed: " + ", ".join(r.mention for r in roles) if roles else ""
            else:
                privacy = f" · allowed: {baseline_role.mention}" if baseline_role else ""

            limit_txt = f" (limit: {self.user_limit})" if self.user_limit else " (no limit)"

            for item in self.children:
                item.disabled = True

            await interaction.response.edit_message(
                content=f"Created **{vc.name}**{limit_txt}{privacy}.",
                view=self
            )

        except discord.Forbidden:
            await interaction.response.send_message(
                "I don’t have permission to create channels / set permissions in The Lounge.",
                ephemeral=True
            )


class NameModal(discord.ui.Modal, title="Set Lounge Name"):
    name_input = discord.ui.TextInput(
        label="Channel name",
        placeholder="e.g. Study Room / Chill / Raid Squad",
        max_length=96,
        required=True,
    )

    def __init__(self, view: LoungeCreateView):
        super().__init__()
        self._view = view

    async def on_submit(self, interaction: discord.Interaction):
        self._view.channel_name = _sanitize_channel_name(str(self.name_input.value))
        await self._view._edit_setup_message(interaction)


class LimitModal(discord.ui.Modal, title="Set User Limit"):
    limit_input = discord.ui.TextInput(
        label="User limit (0 = no limit, max 99)",
        placeholder="0",
        max_length=2,
        required=True,
    )

    def __init__(self, view: LoungeCreateView):
        super().__init__()
        self._view = view

    async def on_submit(self, interaction: discord.Interaction):
        raw = str(self.limit_input.value).strip()
        try:
            n = int(raw)
        except ValueError:
            await interaction.response.send_message("That isn’t a number.", ephemeral=True)
            return

        self._view.user_limit = _clamp_user_limit(n)
        await self._view._edit_setup_message(interaction)


class RoleMultiSelect(discord.ui.Select):
    def __init__(self, options: list[discord.SelectOption]):
        super().__init__(
            placeholder="Pick who can join (optional). No selection = Resonator default.",
            min_values=0,
            max_values=min(25, len(options)) if options else 0,
            options=options,
            custom_id="artie:lounge:roleselect"
        )

    async def callback(self, interaction: discord.Interaction):
        view: LoungeCreateView = self.view  # type: ignore
        view.selected_role_ids = {int(v) for v in self.values}
        await view._edit_setup_message(interaction)


class Lounge(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.temp_lounge_channels: set[int] = set()

    @app_commands.command(name="lounge", description="Create a temporary Lounge voice channel.")
    async def lounge(self, interaction: discord.Interaction):
        guild = interaction.guild
        if guild is None:
            return await interaction.response.send_message("Server only.", ephemeral=True)

        options = _build_role_options(guild)

        view = LoungeCreateView(
            bot=self.bot,
            requester_id=interaction.user.id,
            channel_name=_default_channel_name(interaction),
            user_limit=0,
            category_id=config.LOUNGE_CATEGORY_ID,
            options=options,
            lounge_cog=self
        )

        content = _summary_text(view.channel_name, view.user_limit, view.selected_role_ids, guild)
        await interaction.response.send_message(content, view=view, ephemeral=True)

        # Store the ephemeral setup message id so modals can edit it later.
        try:
            msg = await interaction.original_response()
            view.setup_message_id = msg.id
        except discord.HTTPException:
            view.setup_message_id = None

    @commands.Cog.listener()
    async def on_voice_state_update(self, member: discord.Member, before: discord.VoiceState, after: discord.VoiceState):
        if before.channel and before.channel.id in self.temp_lounge_channels:
            if len(before.channel.members) == 0:
                try:
                    await before.channel.delete(reason="Empty temp lounge channel (Artie)")
                finally:
                    self.temp_lounge_channels.discard(before.channel.id)


async def setup(bot: commands.Bot):
    await bot.add_cog(Lounge(bot))
