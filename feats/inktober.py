import asyncio
from datetime import date, datetime
from zoneinfo import ZoneInfo

import discord
from discord.ext import commands

import config
from feats.roles import NotificationRolesView


INKTOBER_PROMPTS = (
    ("Apple", "![🍎](https://discord.com/assets/a674e7d0da99d47d.svg)"),
    ("Relic", "![🏺](https://discord.com/assets/7048b88ff172ac57.svg)"),
    ("Miniature", "![🧸](https://discord.com/assets/c88359daed276c44.svg)"),
    ("Cactus", "![🌵](https://discord.com/assets/37be3ccf68ee491b.svg)"),
    ("Smack", "![💥](https://discord.com/assets/7742fb3533a81a16.svg)"),
    ("Ogre", "![👹](https://discord.com/assets/aaab62ccb3ea075e.svg)"),
    ("Panic", "![😱](https://discord.com/assets/72c312d2792f53c7.svg)"),
    ("Stinky", "![💩](https://discord.com/assets/a1517e1c721b84d1.svg)"),
    ("Ram", "![🐏](https://discord.com/assets/a045b596cb8c895a.svg)"),
    ("Mystical", "![🔮](https://discord.com/assets/b1b7b56fe20bf6c6.svg)"),
    ("Rescue", "![🛟](https://discord.com/assets/6116af62141b69fb.svg)"),
    ("Toss", "![🤾](https://discord.com/assets/ba269a2cd638870e.svg)"),
    ("Flimsy", "![🪶](https://discord.com/assets/2a0bfe1d3f876727.svg)"),
    ("Lady", "![👩](https://discord.com/assets/81947e5d7ad7ac0c.svg)"),
    ("Hooray", "![🎉](https://discord.com/assets/f7750b45770701de.svg)"),
    ("Gangly", "![🦒](https://discord.com/assets/2d11f7a951962088.svg)"),
    ("Contraption", "![⚙️](https://discord.com/assets/7afdc0163bb3fba3.svg)"),
    ("Flightless", "![🐧](https://discord.com/assets/8b4624ca04ddb9a4.svg)"),
    ("Confused", "![😕](https://discord.com/assets/4b78aed623919cf4.svg)"),
    ("Lounge", "![🛋️](https://discord.com/assets/6e602e88c3146e2d.svg)"),
    ("Hero", "![🦸](https://discord.com/assets/e26a6907fc56d1b4.svg)"),
    ("Beacon", "![🚨](https://discord.com/assets/8d433206d7a0fe81.svg)"),
    ("Dapper", "![🤵](https://discord.com/assets/3241045be18f43f0.svg)"),
    ("Bake", "![🧁](https://discord.com/assets/d60469d5831a2625.svg)"),
    ("Fracture", "![🩻](https://discord.com/assets/1f7345f1ba47af95.svg)"),
    ("Zip", "![🤐](https://discord.com/assets/52aa42ea4bebab36.svg)"),
    ("Dumb", "![🤪](https://discord.com/assets/d9ad5def1e22d863.svg)"),
    ("Trophy", "![🏆](https://discord.com/assets/f11aff9f1c8c5f19.svg)"),
    ("Tusk", "![🦣](https://discord.com/assets/8d06303f435c090c.svg)"),
    ("Cookie", "![🍪](https://discord.com/assets/6e61ba06cad2c1e8.svg)"),
    ("Flex", "![💪](https://discord.com/assets/6550bf7986e6b411.svg)"),
)

EASTERN = ZoneInfo(config.INKTOBER_TIMEZONE)


def _post_time(year: int, month: int, day: int) -> datetime:
    return datetime(
        year,
        month,
        day,
        config.INKTOBER_POST_HOUR,
        config.INKTOBER_POST_MINUTE,
        tzinfo=EASTERN,
    )


def _announcement_time(year: int) -> datetime:
    return datetime(
        year,
        10,
        1,
        config.INKTOBER_ANNOUNCEMENT_HOUR,
        config.INKTOBER_POST_MINUTE,
        tzinfo=EASTERN,
    )


def _next_post(now: datetime) -> datetime:
    local_now = now.astimezone(EASTERN)
    if local_now.month < 10:
        return _post_time(local_now.year, 10, 1)
    if local_now.month == 10 and local_now.day <= 31:
        candidate = _post_time(local_now.year, 10, local_now.day)
        if local_now < candidate:
            return candidate
        if local_now.day < 31:
            return _post_time(local_now.year, 10, local_now.day + 1)
    return _post_time(local_now.year + 1, 10, 1)


def _next_announcement(now: datetime) -> datetime:
    local_now = now.astimezone(EASTERN)
    candidate = _announcement_time(local_now.year)
    if local_now < candidate:
        return candidate
    return _announcement_time(local_now.year + 1)


def _prompt_for_date(local_date: date) -> tuple[int, str, str] | None:
    if local_date.month != 10 or not 1 <= local_date.day <= len(INKTOBER_PROMPTS):
        return None
    day = local_date.day
    prompt, image = INKTOBER_PROMPTS[day - 1]
    return day, prompt, image


def _build_message(local_date: date, role_mention: str = "") -> str | None:
    prompt = _prompt_for_date(local_date)
    if prompt is None:
        return None
    day, name, image = prompt
    mention = f"{role_mention} " if role_mention else ""
    return f"{mention}Todays prompt is: DAY {day}: {name}\n{image}"


def _build_announcement(role_mention: str) -> str:
    return (
        "🎃 **The Keyresonant Workshop Inktober begins...** 🎃\n\n"
        "The page is blank. The month is waiting. Grab your ink and enter a 31-day "
        "descent into creative prompts.\n\n"
        f"Want a notification for each prompt? Head to <#{config.ROLES_CHANNEL_ID}> "
        f"and select the **Inktoberer** role before the first prompt awakens. {role_mention}"
    )


def _build_role_message() -> str:
    return (
        "🎃 **Inktober notifications** 🎃\n\n"
        "Select **Inktoberer** below to receive a notification when the daily Inktober prompt is posted."
    )


async def _post_inktober(bot: commands.Bot, local_date: date | None = None) -> bool:
    guild = bot.get_guild(config.GUILD_ID)
    if guild is None:
        return False

    channel = guild.get_channel(config.INKTOBER_CHANNEL_ID)
    if not isinstance(channel, discord.TextChannel):
        return False

    local_date = local_date or datetime.now(EASTERN).date()
    role = discord.utils.get(guild.roles, name=config.INKTOBERER_ROLE_NAME)
    role_mention = role.mention if role is not None else "@Inktoberer"
    message = _build_message(local_date, role_mention)
    if message is None:
        return False
    await channel.send(message)
    return True


async def _post_inktober_announcement(bot: commands.Bot) -> bool:
    guild = bot.get_guild(config.GUILD_ID)
    if guild is None:
        return False

    announcement_channel = guild.get_channel(config.INKTOBER_ANNOUNCEMENT_CHANNEL_ID)
    roles_channel = guild.get_channel(config.ROLES_CHANNEL_ID)
    role = discord.utils.get(guild.roles, name=config.INKTOBERER_ROLE_NAME)
    role_mention = role.mention if role is not None else "@Inktoberer"
    posted = False

    if isinstance(announcement_channel, discord.TextChannel):
        await announcement_channel.send(_build_announcement(role_mention))
        posted = True
    else:
        print("Inktober: announcement channel is not configured")
    if isinstance(roles_channel, discord.TextChannel):
        await roles_channel.send(_build_role_message(), view=NotificationRolesView())
        posted = True
    else:
        print("Inktober: roles channel is not configured")
    return posted


async def _inktober_loop(bot: commands.Bot):
    await bot.wait_until_ready()
    while True:
        now = datetime.now(EASTERN)
        next_run = _next_post(now)
        await asyncio.sleep(max(0, (next_run - now).total_seconds()))
        if not await _post_inktober(bot, next_run.date()):
            print("Inktober: failed to post (check guild/channel configuration)")
        await asyncio.sleep(60)


async def _inktober_announcement_loop(bot: commands.Bot):
    await bot.wait_until_ready()
    while True:
        now = datetime.now(EASTERN)
        next_run = _next_announcement(now)
        await asyncio.sleep(max(0, (next_run - now).total_seconds()))
        if not await _post_inktober_announcement(bot):
            print("Inktober: failed to post announcement or role panel")
        await asyncio.sleep(60)


class Inktober(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self._tasks: list[asyncio.Task] = []

    async def cog_load(self):
        self._tasks = [
            asyncio.create_task(_inktober_loop(self.bot)),
            asyncio.create_task(_inktober_announcement_loop(self.bot)),
        ]

    async def cog_unload(self):
        for task in self._tasks:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass

    @commands.Cog.listener()
    async def on_ready(self):
        if any(task.done() for task in self._tasks):
            self._tasks = [
                asyncio.create_task(_inktober_loop(self.bot)),
                asyncio.create_task(_inktober_announcement_loop(self.bot)),
            ]


async def setup(bot: commands.Bot):
    await bot.add_cog(Inktober(bot))