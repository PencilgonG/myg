import os

class settings:
    DISCORD_TOKEN   = os.getenv("DISCORD_TOKEN")  # <-- plus de token en dur
    GUILD_ID_TEST   = int(os.getenv("GUILD_ID_TEST", "0")) or None

    # Pour les embeds stylés (facultatif)
    MYG_BANNER_URL  = os.getenv("https://i.imgur.com/320mZMX.png")
    MYG_LOGO_URL    = os.getenv("https://i.imgur.com/HpLFs36.png")
