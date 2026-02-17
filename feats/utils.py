import discord
import config


def get_role_by_name(guild: discord.Guild, name: str):
    return discord.utils.get(guild.roles, name=name)


def reply_mention(member: discord.Member | discord.User) -> str:
    """Use 'mama' instead of @-mention when replying to the configured user."""
    if getattr(member, "id", None) == config.MAMA_USER_ID:
        return "mama"
    return member.mention
