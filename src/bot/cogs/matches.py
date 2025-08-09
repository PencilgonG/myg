import discord
from discord import app_commands
from discord.ext import commands

from bot.db import init_db_stats, record_match

from bot.store import get_mod_role

def _is_inhouse_mod_or_owner(inter: discord.Interaction) -> bool:
    if inter.user.guild_permissions.manage_guild:
        return True
    rid = get_mod_role(inter.guild_id or 0)
    return bool(rid and any(r.id == rid for r in inter.user.roles))

class Matches(commands.Cog):
    """Enregistrement des résultats d'inhouse -> alimente le leaderboard/stats."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        init_db_stats()

    group = app_commands.Group(name="match", description="Gérer les résultats d'inhouse (ajout).")

    @group.command(name="add", description="Ajouter un résultat d'inhouse (modo/owner).")
    @app_commands.describe(
        blue="Membres de l'équipe BLUE",
        red="Membres de l'équipe RED",
        winner="Gagnant : blue ou red",
        mode="Mode (ex: 5vs5, aram, ...)"
    )
    async def add(
        self,
        interaction: discord.Interaction,
        blue: str,
        red: str,
        winner: app_commands.Choice[str],
        mode: str = "5vs5"
    ):
        if not _is_inhouse_mod_or_owner(interaction):
            return await interaction.response.send_message("Réservé aux modos/owner.", ephemeral=True)

        guild = interaction.guild
        if not guild:
            return await interaction.response.send_message("Commande uniquement en serveur.", ephemeral=True)

        # parse mentions/IDs depuis une chaine (on accepte @mention, <@id>, id séparés par espaces/virgules)
        def parse_users(s: str):
            ids = set()
            for tok in s.replace(",", " ").split():
                tok = tok.strip()
                if tok.startswith("<@") and tok.endswith(">"):
                    tok = tok.strip("<@!>")
                if tok.isdigit():
                    ids.add(int(tok))
            return list(ids)

        blue_ids = parse_users(blue)
        red_ids  = parse_users(red)
        if not blue_ids or not red_ids:
            return await interaction.response.send_message("Liste de joueurs invalide. Donne des mentions ou IDs.", ephemeral=True)

        if winner.value not in ("blue","red"):
            return await interaction.response.send_message("Winner doit être 'blue' ou 'red'.", ephemeral=True)

        match_id = record_match(guild.id, mode, blue_ids, red_ids, winner.value)

        # petit résumé
        def fmt(ids):
            return " ".join(f"<@{i}>" for i in ids)

        emb = discord.Embed(title=f"Résultat enregistré (#{match_id})", color=discord.Color.green())
        emb.add_field(name="Mode", value=mode, inline=True)
        emb.add_field(name="Gagnant", value=("BLUE" if winner.value=="blue" else "RED"), inline=True)
        emb.add_field(name="\u200b", value="\u200b", inline=True)
        emb.add_field(name="BLUE", value=fmt(blue_ids), inline=True)
        emb.add_field(name="RED",  value=fmt(red_ids),  inline=True)
        await interaction.response.send_message(embed=emb, ephemeral=False)

async def setup(bot: commands.Bot):
    await bot.add_cog(Matches(bot))
