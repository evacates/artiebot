# config.py
# all of arties configs
# the reason we want all of arties configs here is so we can easily access them across the other files

# IDS
GUILD_ID = 1402420195221438554

# Welcome IDS
WELCOME_CHANNEL_ID = 1460698534696325292
RULES_CHANNEL_ID = 1402420197834625045
ROLES_CHANNEL_ID = 1460725594311495822
INTRO_CHANNEL_ID = 1460715415440457778

# Path to store reaction-roles message ID (so the bot knows which message to listen to)
REACTION_ROLES_DATA_PATH = "data/reaction_roles.json"

# Creative ops
SELF_PROMO_CHANNEL_ID = 1460700818121687186
JOBS_CHANNEL_ID = 1460498120654721237
COMMISSIONS_CHANNEL_ID = 1402421153514913983

# Lounge
LOUNGE_CATEGORY_ID = 1460706656991182868

# Daily doodle — channel to post the daily prompt, and time (UTC)
DAILY_DOODLE_CHANNEL_ID = 1468145168065757266
DAILY_DOODLE_POST_HOUR_UTC = 14   # 9:00 AM EST (UTC-5). Use 13 for 9am EDT in summer
DAILY_DOODLE_POST_MINUTE_UTC = 0
DAILY_DOODLE_THEMES = [
    "Floral", "Rusted", "Bone kin",
    "Flavor", "Aquatic Mammal", "Frozen", "Deserted", "Celestial", "Gothic",
    "Mythic", "Industrial", "Neon", "Forest", "Crystal", "Arcane", "Melted weapon",
    "Steam", "Haunted", "Alien", "Underworld", "Smelly", "Damp Grave",
    "Bioluminescent", "Retro", "Whimsical", "Stone", "Fungal", "Iridescent",
    "Noir", "Stormy", "Futuristic", "Corrupted", "Tropical", "Cavernous",
    "Volcanic", "Feral", "Dreamscape", "Dystopian", "Lunar", "Vexxed", "Mechanical",
]
# Optional: theme name -> emoji for the daily post. Missing themes use default ✏️
DAILY_DOODLE_THEME_EMOJIS = {
    "Floral": "🌸",
    "Rusted": "🔥",
    "Bone kin": "🦴",
    "Flavor": "🍫",
    "Aquatic Mammal": "🐟",
    "Frozen": "❄️",
    "Deserted": "🏜️",
    "Celestial": "🌌",
    "Gothic": "🦇",
    "Mythic": "🐦‍🔥",
    "Industrial": "🏭",
    "Neon": "🌈",
    "Forest": "🌲",
    "Crystal": "🔮",
    "Arcane": "🧙🏻‍♀️",
    "Melted weapon": "🔥🔫",
    "Steam": "🌋",
    "Haunted": "👻",
    "Alien": "👽",
    "Underworld": "👹",
    "Smelly": "🤢",
    "Damp Grave": "💀",
    "Bioluminescent": "💡",
    "Retro": "🕒",
    "Whimsical": "💫",
    "Stone": "🪨",
    "Fungal": "🍄",
    "Iridescent": "🌈",
    "Noir": "🖤",
    "Stormy": "⛈️",
    "Futuristic": "🚀",
    "Corrupted": "👺",
    "Tropical": "🌴",
    "Cavernous": "🕳️",
    "Volcanic": "🌋",
    "Feral": "🐺",
    "Dreamscape": "💭",
    "Dystopian": "🏚",
    "Lunar": "🌙",
    "Vexxed": "👿",
    "Mechanical": "🤖",
}
DAILY_DOODLE_DEFAULT_EMOJI = "✏️"



# Roles
# to add a role command you'll want to name a new variable here and it will store the role data
# you would do so by declaring it like so:
# [VARIABLE_NAME] = "Roles actual name in discord"
# variable names have no spaces and I prefer to keep them in all caps
# for example this one only stores the resonator role in the RESONATOR_ROLE_NAME
RESONATOR_ROLE_NAME = "Resonator" 

# as you can see you can store multiple role names in an array of strings
# an array of strings is just a techy way of saying this storing multiple items of type string
PRONOUN_ROLE_NAMES = ["She/Her", "She/They", "They/Them", 
                      "He/They", "He/Him", "Any", "Ask"]

MEDIUM_ROLE_NAMES = ["Digital", "Traditional", "Painting", "Ink", "Graphite",
                    "3D", "Animation", "Writing", "Photography"]

# Roles for reaction-based opt-in (daily doodle theme & live notifications)
NOTIFICATION_ROLE_NAMES = ["Daily Doodler", "Live Viewer"]
NOTIFICATION_REACTION_EMOJI_NAMES = ["DailyDoodler", "LiveViewer"]
