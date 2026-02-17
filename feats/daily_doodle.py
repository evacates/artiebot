import asyncio
from datetime import datetime, timezone, timedelta

import discord
from discord import app_commands
from discord.ext import commands

import config

DAILY_DOODLER_ROLE_NAME = "Daily Doodler"


def _next_post_utc() -> datetime:
    now = datetime.now(timezone.utc)
    today = now.replace(
        hour=config.DAILY_DOODLE_POST_HOUR_UTC,
        minute=config.DAILY_DOODLE_POST_MINUTE_UTC,
        second=0,
        microsecond=0,
    )
    if now >= today:
        today += timedelta(days=1)
    return today


def _theme_for_date(d: datetime) -> str:
    day_of_year = d.timetuple().tm_yday
    idx = (day_of_year - 1) % len(config.DAILY_DOODLE_THEMES)
    return config.DAILY_DOODLE_THEMES[idx]


def _emoji_for_theme(theme: str) -> str:
    emoji = config.DAILY_DOODLE_THEME_EMOJIS.get(theme, config.DAILY_DOODLE_DEFAULT_EMOJI)
    return emoji if emoji else config.DAILY_DOODLE_DEFAULT_EMOJI


def _date_str(d: datetime) -> str:
    return f"{d.month}/{d.day}/{d.year % 100:02d}"


def _build_daily_doodle_message(
    guild: discord.Guild,
    when: datetime | None = None,
) -> str | None:
    """Build the exact message that would be posted. Returns None if role not found."""
    role = discord.utils.get(guild.roles, name=DAILY_DOODLER_ROLE_NAME)
    if role is None:
        return None
    d = when or datetime.now(timezone.utc)
    theme = _theme_for_date(d)
    emoji = _emoji_for_theme(theme)
    date_str = _date_str(d)
    return f"{role.mention} Todays prompt is: {theme} {emoji}\n{date_str}"


def _build_theme_emoji_test() -> tuple[str, list[tuple[str, list[str]]]]:
    """Returns (full list text, list of (emoji, [themes]) for duplicates)."""
    theme_to_emoji = {}
    for theme in config.DAILY_DOODLE_THEMES:
        theme_to_emoji[theme] = _emoji_for_theme(theme)
    emoji_to_themes: dict[str, list[str]] = {}
    for theme, emoji in theme_to_emoji.items():
        emoji_to_themes.setdefault(emoji, []).append(theme)
    lines = ["**Daily Doodle test — all themes & emojis**", ""]
    for theme in config.DAILY_DOODLE_THEMES:
        emoji = theme_to_emoji[theme]
        lines.append(f"{theme} {emoji}")
    duplicates = [(emoji, themes) for emoji, themes in emoji_to_themes.items() if len(themes) > 1]
    return "\n".join(lines), duplicates


async def _post_daily_doodle(bot: commands.Bot) -> bool:
    guild = bot.get_guild(config.GUILD_ID)
    if guild is None:
        return False
    channel = guild.get_channel(config.DAILY_DOODLE_CHANNEL_ID)
    if not isinstance(channel, discord.TextChannel):
        return False
    role = discord.utils.get(guild.roles, name=DAILY_DOODLER_ROLE_NAME)
    if role is None:
        return False
    now = datetime.now(timezone.utc)
    theme = _theme_for_date(now)
    emoji = _emoji_for_theme(theme)
    date_str = _date_str(now)
    message = (
        f"{role.mention} Todays prompt is: {theme} {emoji}\n"
        f"{date_str}"
    )
    await channel.send(message)
    return True


async def _daily_doodle_loop(bot: commands.Bot):
    await bot.wait_until_ready()
    while True:
        next_run = _next_post_utc()
        now = datetime.now(timezone.utc)
        wait_seconds = (next_run - now).total_seconds()
        if wait_seconds > 0:
            await asyncio.sleep(wait_seconds)
        ok = await _post_daily_doodle(bot)
        if not ok:
            print("Daily doodle: failed to post (check channel/role)")
        # Avoid running twice: sleep until we're past this run
        await asyncio.sleep(60)


class DailyDoodle(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self._task = None

    async def cog_load(self):
        self._task = asyncio.create_task(_daily_doodle_loop(self.bot))

    async def cog_unload(self):
        if self._task is not None:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass

    @commands.Cog.listener()
    async def on_ready(self):
        # Ensure loop is running (in case of reconnect)
        if self._task is not None and self._task.done():
            self._task = asyncio.create_task(_daily_doodle_loop(self.bot))

    @app_commands.command(
        name="post_daily_doodle",
        description="Post today's daily doodle prompt now (staff only).",
    )
    @app_commands.checks.has_permissions(manage_guild=True)
    async def post_daily_doodle(self, interaction: discord.Interaction):
        if interaction.guild is None:
            return await interaction.response.send_message("Server only.", ephemeral=True)
        await interaction.response.defer(ephemeral=True)
        ok = await _post_daily_doodle(self.bot)
        if ok:
            await interaction.followup.send("Daily doodle posted.", ephemeral=True)
        else:
            await interaction.followup.send(
                "Failed to post (check DAILY_DOODLE_CHANNEL_ID and Daily Doodler role).",
                ephemeral=True,
            )

    @app_commands.command(
        name="preview_daily_doodle",
        description="Show the exact daily doodle message that would be posted (staff only).",
    )
    @app_commands.checks.has_permissions(manage_guild=True)
    async def preview_daily_doodle(self, interaction: discord.Interaction):
        if interaction.guild is None:
            return await interaction.response.send_message("Server only.", ephemeral=True)
        msg = _build_daily_doodle_message(interaction.guild)
        if msg is None:
            return await interaction.response.send_message(
                "Daily Doodler role not found.",
                ephemeral=True,
            )
        await interaction.response.send_message(msg, ephemeral=True)

    @app_commands.command(
        name="test_daily_doodle",
        description="Preview all daily doodle themes and emojis; reports duplicates (staff only).",
    )
    @app_commands.checks.has_permissions(manage_guild=True)
    async def test_daily_doodle(self, interaction: discord.Interaction):
        if interaction.guild is None:
            return await interaction.response.send_message("Server only.", ephemeral=True)
        await interaction.response.defer(ephemeral=True)
        list_text, duplicates = _build_theme_emoji_test()
        # Discord limit 2000 chars; send list first, then duplicate report if needed
        if len(list_text) <= 2000:
            msg = list_text
            if duplicates:
                dup_lines = ["**⚠️ Duplicate emojis (consider changing in config):**", ""]
                for emoji, themes in duplicates:
                    dup_lines.append(f"{emoji} → {', '.join(themes)}")
                dup_block = "\n".join(dup_lines)
                if len(msg) + len(dup_block) + 2 <= 2000:
                    msg = msg + "\n\n" + dup_block
                else:
                    await interaction.followup.send(msg, ephemeral=True)
                    msg = dup_block
            await interaction.followup.send(msg, ephemeral=True)
        else:
            # Split into chunks
            chunks = [list_text[i : i + 1990] for i in range(0, len(list_text), 1990)]
            for c in chunks:
                await interaction.followup.send(c, ephemeral=True)
            if duplicates:
                dup_lines = ["**⚠️ Duplicate emojis:**", ""]
                for emoji, themes in duplicates:
                    dup_lines.append(f"{emoji} → {', '.join(themes)}")
                await interaction.followup.send("\n".join(dup_lines), ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(DailyDoodle(bot))
