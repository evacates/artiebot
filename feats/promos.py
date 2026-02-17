import os
import re
import json
import time
import asyncio
import discord
from discord import app_commands
from discord.ext import commands
import config
from feats.utils import reply_mention

COOLDOWN_SECONDS = 24 * 60 * 60  # 24 hours

DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
COOLDOWN_FILE = os.path.join(DATA_DIR, "promo_cooldowns.json")
THREADS_FILE = os.path.join(DATA_DIR, "promo_threads.json")

MAX_IMAGES = 4


def _ensure_data_dir():
    os.makedirs(DATA_DIR, exist_ok=True)


def _now() -> int:
    return int(time.time())


def _fmt_remaining(seconds: int) -> str:
    seconds = max(0, seconds)
    h = seconds // 3600
    m = (seconds % 3600) // 60
    s = seconds % 60
    if h > 0:
        return f"{h}h {m}m"
    if m > 0:
        return f"{m}m {s}s"
    return f"{s}s"


def is_staff(member: discord.Member) -> bool:
    return member.guild_permissions.manage_guild or member.guild_permissions.administrator


def _clean_lines(text: str) -> str:
    lines = [ln.strip() for ln in (text or "").splitlines()]
    lines = [ln for ln in lines if ln]
    return "\n".join(lines)


def _is_image_url(url: str) -> bool:
    url = url.lower().strip()
    return any(url.endswith(ext) for ext in (".png", ".jpg", ".jpeg", ".webp", ".gif"))


_URL_RE = re.compile(r"(https?://\S+)")


def _extract_urls(text: str) -> list[str]:
    if not text:
        return []
    return [m.group(1).strip(")>,.]}") for m in _URL_RE.finditer(text)]


class PromoCooldownStore:
    def __init__(self):
        self._lock = asyncio.Lock()
        self._data: dict[str, int] = {}
        _ensure_data_dir()
        self._load()

    def _load(self):
        try:
            with open(COOLDOWN_FILE, "r", encoding="utf-8") as f:
                raw = json.load(f)
            if isinstance(raw, dict):
                self._data = {str(k): int(v) for k, v in raw.items()}
        except FileNotFoundError:
            self._data = {}
        except Exception:
            self._data = {}

    def _save(self):
        _ensure_data_dir()
        with open(COOLDOWN_FILE, "w", encoding="utf-8") as f:
            json.dump(self._data, f, indent=2)

    async def check_and_set(self, member: discord.Member) -> tuple[bool, int]:
        if is_staff(member):
            return True, 0

        async with self._lock:
            uid = str(member.id)
            last = self._data.get(uid, 0)
            now = _now()
            elapsed = now - last

            if elapsed < COOLDOWN_SECONDS:
                return False, COOLDOWN_SECONDS - elapsed

            self._data[uid] = now
            try:
                self._save()
            except Exception:
                pass

            return True, 0


class PromoThreadStore:
    """
    Tracks threads created for promos so we can collect up to 4 images
    and update the original embed message.
    """
    def __init__(self):
        self._lock = asyncio.Lock()
        self._threads: dict[str, dict] = {}
        _ensure_data_dir()
        self._load()

    def _load(self):
        try:
            with open(THREADS_FILE, "r", encoding="utf-8") as f:
                raw = json.load(f)
            if isinstance(raw, dict):
                self._threads = raw
        except FileNotFoundError:
            self._threads = {}
        except Exception:
            self._threads = {}

    def _save(self):
        _ensure_data_dir()
        with open(THREADS_FILE, "w", encoding="utf-8") as f:
            json.dump(self._threads, f, indent=2)

    async def add_thread(self, thread_id: int, parent_message_id: int, author_id: int):
        async with self._lock:
            self._threads[str(thread_id)] = {
                "parent_message_id": int(parent_message_id),
                "author_id": int(author_id),
                "created_at": _now(),
                "images": []
            }
            try:
                self._save()
            except Exception:
                pass

    async def get(self, thread_id: int) -> dict | None:
        async with self._lock:
            return self._threads.get(str(thread_id))

    async def add_image(self, thread_id: int, url: str) -> tuple[bool, int]:
        """
        Returns (added, count_after)
        """
        async with self._lock:
            entry = self._threads.get(str(thread_id))
            if not entry:
                return False, 0

            imgs = entry.get("images", [])
            if url in imgs:
                return False, len(imgs)

            if len(imgs) >= MAX_IMAGES:
                return False, len(imgs)

            imgs.append(url)
            entry["images"] = imgs
            self._threads[str(thread_id)] = entry
            try:
                self._save()
            except Exception:
                pass

            return True, len(imgs)

    async def remove_thread(self, thread_id: int):
        async with self._lock:
            self._threads.pop(str(thread_id), None)
            try:
                self._save()
            except Exception:
                pass


class CommissionModal(discord.ui.Modal, title="Post a Commission"):
    title_input = discord.ui.TextInput(label="Title", placeholder="e.g., Commissions Open!", max_length=80)
    offer_input = discord.ui.TextInput(
        label="What you offer",
        placeholder="icons, half-body, full-body, ref sheets…",
        style=discord.TextStyle.paragraph,
        max_length=1000
    )
    prices_input = discord.ui.TextInput(
        label="Prices",
        placeholder="Icon $20 | Half $45 | Full $70",
        style=discord.TextStyle.paragraph,
        max_length=1000
    )
    terms_input = discord.ui.TextInput(
        label="Terms (optional)",
        placeholder="payment upfront, turnaround time, no NSFW, etc.",
        style=discord.TextStyle.paragraph,
        required=False,
        max_length=1000
    )
    contact_input = discord.ui.TextInput(
        label="Contact / Main link",
        placeholder="portfolio/carrd/DMs/whatever",
        max_length=200
    )

    def __init__(self, cog: "Promo"):
        super().__init__()
        self.cog = cog

    async def on_submit(self, interaction: discord.Interaction):
        if interaction.guild is None:
            return await interaction.response.send_message("Server only.", ephemeral=True)

        member = interaction.user
        if not isinstance(member, discord.Member):
            member = await interaction.guild.fetch_member(interaction.user.id)

        ok, remaining = await self.cog.cooldowns.check_and_set(member)
        if not ok:
            return await interaction.response.send_message(
                f"Cooldown: try again in **{_fmt_remaining(remaining)}**.",
                ephemeral=True
            )

        channel = interaction.guild.get_channel(config.COMMISSIONS_CHANNEL_ID)
        if not isinstance(channel, discord.TextChannel):
            return await interaction.response.send_message("COMMISSIONS_CHANNEL_ID is wrong.", ephemeral=True)

        embed = discord.Embed(
            title=str(self.title_input),
            description=f"Posted by {reply_mention(interaction.user)}"
        )
        embed.add_field(name="What I Offer", value=str(self.offer_input), inline=False)
        embed.add_field(name="Prices", value=str(self.prices_input), inline=False)

        if str(self.terms_input).strip():
            embed.add_field(name="Terms", value=str(self.terms_input), inline=False)

        embed.add_field(name="Contact / Link", value=str(self.contact_input), inline=False)

        try:
            msg = await channel.send(embed=embed)
        except discord.Forbidden:
            return await interaction.response.send_message(
                "I can’t post there. Give me Send Messages + Embed Links.",
                ephemeral=True
            )

        thread = await self.cog.create_image_thread(
            parent_message=msg,
            author_id=interaction.user.id,
            base_name=f"{interaction.user.display_name} — commissions"
        )

        await interaction.response.send_message(
            f"Posted in {channel.mention}. Add up to **{MAX_IMAGES}** images in {thread.mention}.",
            ephemeral=True
        )


class SelfPromoModal(discord.ui.Modal, title="Post a Self-Promo"):
    title_input = discord.ui.TextInput(label="Title", placeholder="e.g., Eva’s Art / Portfolio", max_length=80)
    about_input = discord.ui.TextInput(
        label="About",
        placeholder="What you make / what you want people to know…",
        style=discord.TextStyle.paragraph,
        max_length=1200
    )
    socials_input = discord.ui.TextInput(
        label="Links & Socials (as many as you want)",
        placeholder="One per line.\nInstagram: …\nTwitter/X: …\nCarrd: …\nKo-fi: …",
        style=discord.TextStyle.paragraph,
        max_length=1200
    )

    def __init__(self, cog: "Promo"):
        super().__init__()
        self.cog = cog

    async def on_submit(self, interaction: discord.Interaction):
        if interaction.guild is None:
            return await interaction.response.send_message("Server only.", ephemeral=True)

        member = interaction.user
        if not isinstance(member, discord.Member):
            member = await interaction.guild.fetch_member(interaction.user.id)

        ok, remaining = await self.cog.cooldowns.check_and_set(member)
        if not ok:
            return await interaction.response.send_message(
                f"Cooldown: try again in **{_fmt_remaining(remaining)}**.",
                ephemeral=True
            )

        channel = interaction.guild.get_channel(config.SELF_PROMO_CHANNEL_ID)
        if not isinstance(channel, discord.TextChannel):
            return await interaction.response.send_message("SELF_PROMO_CHANNEL_ID is wrong.", ephemeral=True)

        embed = discord.Embed(
            title=str(self.title_input),
            description=f"Posted by {reply_mention(interaction.user)}"
        )
        embed.add_field(name="About", value=str(self.about_input), inline=False)

        socials_clean = _clean_lines(str(self.socials_input))
        if socials_clean:
            embed.add_field(name="Links & Socials", value=socials_clean, inline=False)

        try:
            msg = await channel.send(embed=embed)
        except discord.Forbidden:
            return await interaction.response.send_message(
                "I can’t post there. Give me Send Messages + Embed Links.",
                ephemeral=True
            )

        thread = await self.cog.create_image_thread(
            parent_message=msg,
            author_id=interaction.user.id,
            base_name=f"{interaction.user.display_name} — promo"
        )

        await interaction.response.send_message(
            f"Posted in {channel.mention}. Add up to **{MAX_IMAGES}** images in {thread.mention}.",
            ephemeral=True
        )


class JobModal(discord.ui.Modal, title="Post a Job / Artist Search"):
    title_input = discord.ui.TextInput(label="Title", placeholder="e.g., Looking for an animator", max_length=80)
    details_input = discord.ui.TextInput(
        label="Project details",
        placeholder="What you need, style, timeline, deliverables…",
        style=discord.TextStyle.paragraph,
        max_length=1200
    )
    budget_input = discord.ui.TextInput(label="Budget / Pay", placeholder="e.g., $200–$400, negotiable", max_length=120)
    timeline_input = discord.ui.TextInput(label="Timeline", placeholder="e.g., Need by Feb 10 / ASAP / flexible", max_length=120)
    contact_input = discord.ui.TextInput(label="Contact / Link", placeholder="Discord, email, form, etc.", max_length=200)

    def __init__(self, cog: "Promo"):
        super().__init__()
        self.cog = cog

    async def on_submit(self, interaction: discord.Interaction):
        if interaction.guild is None:
            return await interaction.response.send_message("Server only.", ephemeral=True)

        member = interaction.user
        if not isinstance(member, discord.Member):
            member = await interaction.guild.fetch_member(interaction.user.id)

        ok, remaining = await self.cog.cooldowns.check_and_set(member)
        if not ok:
            return await interaction.response.send_message(
                f"Cooldown: try again in **{_fmt_remaining(remaining)}**.",
                ephemeral=True
            )

        channel = interaction.guild.get_channel(config.JOBS_CHANNEL_ID)
        if not isinstance(channel, discord.TextChannel):
            return await interaction.response.send_message("JOBS_CHANNEL_ID is wrong.", ephemeral=True)

        embed = discord.Embed(title=str(self.title_input), description=f"Posted by {reply_mention(interaction.user)}")
        embed.add_field(name="Details", value=str(self.details_input), inline=False)
        embed.add_field(name="Budget / Pay", value=str(self.budget_input), inline=False)
        embed.add_field(name="Timeline", value=str(self.timeline_input), inline=False)
        embed.add_field(name="Contact", value=str(self.contact_input), inline=False)

        try:
            await channel.send(embed=embed)
        except discord.Forbidden:
            return await interaction.response.send_message(
                "I can’t post there. Give me Send Messages + Embed Links.",
                ephemeral=True
            )

        await interaction.response.send_message("Posted.", ephemeral=True)


class Promo(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.cooldowns = PromoCooldownStore()
        self.threads = PromoThreadStore()

    async def create_image_thread(self, parent_message: discord.Message, author_id: int, base_name: str) -> discord.Thread:
        # Name limits are annoying; keep it short.
        name = base_name.strip()
        if len(name) > 90:
            name = name[:90]

        try:
            thread = await parent_message.create_thread(
                name=name,
                auto_archive_duration=1440,  # 24h
                reason="Promo image thread (Artie)"
            )
        except discord.Forbidden:
            # If we can't create threads, just fall back to no-thread UX
            # (But your goal is threads, so fix perms if this triggers.)
            raise

        await self.threads.add_thread(thread.id, parent_message.id, author_id)

        await thread.send(
            f"Drop up to **{MAX_IMAGES}** images here.\n"
            f"I’ll pull them into the main post automatically.\n\n"
            f"Tip: uploads work best. Links can work too (if they end in .png/.jpg/.gif)."
        )

        return thread

    async def _update_parent_embed(self, thread: discord.Thread, entry: dict):
        parent_message_id = entry["parent_message_id"]
        images: list[str] = entry.get("images", [])

        if not images:
            return

        # Fetch the parent message from thread.parent
        parent = thread.parent
        if parent is None:
            return

        try:
            msg = await parent.fetch_message(parent_message_id)
        except Exception:
            return

        if not msg.embeds:
            return

        embed = msg.embeds[0]

        # Featured image
        embed.set_image(url=images[0])

        # Remove existing "More examples" field if present
        new_fields = []
        for f in embed.fields:
            if f.name != "More examples":
                new_fields.append(f)
        embed.clear_fields()
        for f in new_fields:
            embed.add_field(name=f.name, value=f.value, inline=f.inline)

        # Extra images as links
        if len(images) > 1:
            more = "\n".join(f"🔗 {u}" for u in images[1:])
            embed.add_field(name="More examples", value=more, inline=False)

        try:
            await msg.edit(embed=embed)
        except discord.Forbidden:
            pass

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        # Ignore bots
        if message.author.bot:
            return

        # Must be in a thread
        if not isinstance(message.channel, discord.Thread):
            return

        thread = message.channel
        entry = await self.threads.get(thread.id)
        if not entry:
            return

        # Only accept images from the original author (keeps it tidy)
        if message.author.id != entry["author_id"]:
            return

        collected_any = False

        # 1) Attachments (best UX)
        for att in message.attachments:
            # attachment.url is a CDN link that embeds fine
            added, count = await self.threads.add_image(thread.id, att.url)
            if added:
                collected_any = True

        # 2) Image links (works only if message.content is available; otherwise attachments only)
        # If you want link parsing reliably, enable Message Content Intent in dev portal + bot intents.
        for url in _extract_urls(getattr(message, "content", "") or ""):
            if _is_image_url(url):
                added, count = await self.threads.add_image(thread.id, url)
                if added:
                    collected_any = True

        if not collected_any:
            return

        # Update the parent embed
        entry2 = await self.threads.get(thread.id)
        if entry2:
            await self._update_parent_embed(thread, entry2)

            imgs = entry2.get("images", [])
            if len(imgs) >= MAX_IMAGES:
                await thread.send("That’s **4** — perfect. I’m locking this in.")
                # Optional: auto-archive the thread
                try:
                    await thread.edit(archived=True, locked=False)
                except Exception:
                    pass
                await self.threads.remove_thread(thread.id)

    @app_commands.command(name="commission", description="Post a commission listing (staff bypasses cooldown).")
    async def commission(self, interaction: discord.Interaction):
        if interaction.guild is None:
            return await interaction.response.send_message("Server only.", ephemeral=True)
        await interaction.response.send_modal(CommissionModal(self))

    @app_commands.command(name="selfpromo", description="Post a self-promo (staff bypasses cooldown).")
    async def selfpromo(self, interaction: discord.Interaction):
        if interaction.guild is None:
            return await interaction.response.send_message("Server only.", ephemeral=True)
        await interaction.response.send_modal(SelfPromoModal(self))

    @app_commands.command(name="job", description="Post a job / artist search (staff bypasses cooldown).")
    async def job(self, interaction: discord.Interaction):
        if interaction.guild is None:
            return await interaction.response.send_message("Server only.", ephemeral=True)
        await interaction.response.send_modal(JobModal(self))


async def setup(bot: commands.Bot):
    await bot.add_cog(Promo(bot))
