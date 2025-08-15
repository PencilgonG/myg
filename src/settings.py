# src/settings.py
import os
import sys

class Settings:
    def __init__(self):
        # --- Sécurité ---
        self.DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
        if not self.DISCORD_TOKEN:
            print("❌ ERREUR : DISCORD_TOKEN est manquant. Ajoute-le en variable d'env (Codespaces Secret ou export).")
            sys.exit(1)

        # --- Identité visuelle MYG ---
        self.MYG_COLOR      = 0x111111   # fond sombre
        self.MYG_ACCENT     = 0xE85D5D   # rouge accent (⚠️ utilisé par core.py)
        self.MYG_SAND       = 0xF1E0B0   # sable / secondaire
        self.MYG_LOGO_URL   = os.getenv("MYG_LOGO_URL",   "https://i.imgur.com/HpLFs36.png")
        self.MYG_BANNER_URL = os.getenv("MYG_BANNER_URL", "https://i.imgur.com/320mZMX.png")

        # --- Icônes de rôles (mets tes liens Imgur directs .png) ---
        self.ROLE_ICON_URLS = {
            "Top":     os.getenv("LOL_ICON_TOP",     "https://i.imgur.com/6D4fG50.png"),
            "Jungle":  os.getenv("LOL_ICON_JUNGLE",  "https://i.imgur.com/MI28LCe.png"),
            "Mid":     os.getenv("LOL_ICON_MID",     "https://i.imgur.com/0TAduX2.png"),
            "ADC":     os.getenv("LOL_ICON_ADC",     "https://i.imgur.com/0s2saAq.png"),
            "Support": os.getenv("LOL_ICON_SUPPORT", "https://i.imgur.com/4eHketl.png"),
            "Sub":     os.getenv("LOL_ICON_SUB",     "https://i.imgur.com/your_sub.png"),
        }

        # --- Emojis de rôles (affichage texte dans les embeds) ---
        self.ROLE_EMOJI = {
            "Top": "🛡️",
            "Jungle": "🌿",
            "Mid": "🧠",
            "ADC": "🏹",
            "Support": "💉",
        }

        # Footer commun aux embeds
        self.EMBED_FOOTER_TEXT = "MYG Inhouse • League of Legends"

settings = Settings()
