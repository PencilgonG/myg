# src/main.py
import asyncio
import logging
import sys

import discord
from discord.ext import commands

from settings import settings

# -------------------------------------------------------------------
# Logging de base
# -------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger("root")


# -------------------------------------------------------------------
# Bot
# -------------------------------------------------------------------
class MyBot(commands.Bot):
    def __init__(self) -> None:
        # Pas besoin de message_content pour les slashs
        intents = discord.Intents.default()
        intents.guilds = True
        intents.members = True  # utile pour permissions/roles/etc.

        super().__init__(
            command_prefix=commands.when_mentioned_or("!"),  # pas utilisé pour slash
            intents=intents,
            help_command=None,
        )
        self._synced = False  # évite de sync plusieurs fois

    async def setup_hook(self) -> None:
        """
        Chargement des cogs. NE PAS faire de sync ici (sinon application_id pas encore dispo).
        """
        # Cogs actifs
        await self.load_extension("bot.cogs.core")
        await self.load_extension("bot.cogs.profiles")
        await self.load_extension("bot.cogs.matches")
        await self.load_extension("bot.cogs.stats")
# (matches.py reste utile si tu veux /match add manuel ; sinon tu peux le laisser chargé aussi)
# await self.load_extension("bot.cogs.matches")



        log.info("Cogs chargés.")

    async def on_ready(self) -> None:
        """
        Sync des commandes une fois connecté (application_id présent).
        """
        if self._synced:
            return

        try:
            if getattr(settings, "GUILD_ID_TEST", None):
                guild_id = int(settings.GUILD_ID_TEST)
                guild = discord.Object(id=guild_id)
                # On peut copier le global vers le guild de test si besoin :
                # self.tree.copy_global_to(guild=guild)
                synced = await self.tree.sync(guild=guild)
                log.info("🔄 Slash sync local sur guild %s OK (%d commandes).", guild_id, len(synced))
            else:
                synced = await self.tree.sync()
                log.info("🔄 Slash sync global OK (%d commandes).", len(synced))

            self._synced = True
        except Exception:
            log.exception("❌ Erreur sync slash")

        log.info("✅ Connecté en tant que %s (ID: %s)", self.user, getattr(self.user, "id", "unknown"))
        log.info("------")


# -------------------------------------------------------------------
# Entrée
# -------------------------------------------------------------------
async def main() -> None:
    token = getattr(settings, "DISCORD_TOKEN", None)
    if not token:
        print("DISCORD_TOKEN manquant dans settings.py", file=sys.stderr)
        return

    bot = MyBot()

    # Lancement propre
    async with bot:
        try:
            await bot.start(token)
        except KeyboardInterrupt:
            log.info("Arrêt demandé par l'utilisateur.")
        except Exception:
            log.exception("Bot crashed")


if __name__ == "__main__":
    asyncio.run(main())
