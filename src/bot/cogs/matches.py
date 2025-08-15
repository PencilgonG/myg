# Ce module n’enregistre plus de commandes (on garde le fichier pour éviter une erreur de load).
from discord.ext import commands

async def setup(bot: commands.Bot):
    # Ne rien ajouter => aucune commande /match exposée
    return
