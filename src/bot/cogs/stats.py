import discord
from discord import app_commands
from discord.ext import commands

from bot.db import get_stats, get_role_stats

class Stats(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="stats", description="Affiche vos statistiques personnelles.")
    async def stats(self, interaction: discord.Interaction, user: discord.Member | None = None):
        guild = interaction.guild
        if not guild:
            return await interaction.response.send_message("Commande uniquement en serveur.", ephemeral=True)

        member = user or guild.get_member(interaction.user.id)
        if not member:
            return await interaction.response.send_message("Membre introuvable.", ephemeral=True)

        s = get_stats(guild.id, member.id)
        games, wins, losses = s["games"], s["wins"], s["losses"]
        wr = (wins / games * 100) if games else 0.0

        emb = discord.Embed(
            title=f"📊 Stats de {member.display_name}",
            description=f"**{wins}** victoires • **{losses}** défaites • **{games}** parties • **{wr:.1f}%** WR",
            color=discord.Color.blurple()
        )

        roles = get_role_stats(guild.id, member.id)
        if roles:
            lines = []
            for r in roles:
                g, w = r["games"], r["wins"]
                wr2 = (w / g * 100) if g else 0.0
                lines.append(f"• **{r['role']}** — {w}/{g} (*{wr2:.1f}%*)")
            emb.add_field(name="Par rôle", value="\n".join(lines), inline=False)

        if s["last_played"]:
            emb.set_footer(text=f"Dernière partie: {s['last_played']}")

        await interaction.response.send_message(embed=emb, ephemeral=False)

async def setup(bot: commands.Bot):
    await bot.add_cog(Stats(bot))
