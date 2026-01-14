import discord

def get_role_by_name(guild: discord.Guild, name: str):
    return discord.utils.get(guild.roles, name=name)
