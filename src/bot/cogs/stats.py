import discord
from discord.ext import commands
from discord import app_commands
import sqlite3

DB_PATH = "data.sqlite"  # SQLite local

class Stats(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.setup_db()

    def setup_db(self):
        """Crée les tables si elles n'existent pas"""
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("""
            CREATE TABLE IF NOT EXISTS stats (
                user_id INTEGER PRIMARY KEY,
                wins INTEGER DEFAULT 0,
                losses INTEGER DEFAULT 0,
                kills INTEGER DEFAULT 0,
                deaths INTEGER DEFAULT 0
            )
        """)
        conn.commit()
        conn.close()

    def get_stats(self, user_id):
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("SELECT wins, losses, kills, deaths FROM stats WHERE user_id = ?", (user_id,))
        row = c.fetchone()
        conn.close()
        if row:
            return {"wins": row[0], "losses": row[1], "kills": row[2], "deaths": row[3]}
        else:
            return {"wins": 0, "losses": 0, "kills": 0, "deaths": 0}

    @app_commands.command(name="leaderboard", description="Classement des joueurs.")
    @app_commands.describe(type="Type de classement à afficher")
    @app_commands.choices(type=[
        app_commands.Choice(name="Victoires", value="wins"),
        app_commands.Choice(name="Kills", value="kills"),
        app_commands.Choice(name="Winrate", value="winrate")
    ])
    async def leaderboard(self, interaction: discord.Interaction, type: app_commands.Choice[str]):
        """Affiche le classement selon le type choisi"""
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()

        if type.value == "winrate":
            c.execute("SELECT user_id, wins, losses FROM stats")
            rows = c.fetchall()
            leaderboard_data = []
            for user_id, wins, losses in rows:
                total = wins + losses
                winrate = (wins / total * 100) if total > 0 else 0
                leaderboard_data.append((user_id, winrate))
            leaderboard_data.sort(key=lambda x: x[1], reverse=True)
        else:
            c.execute(f"SELECT user_id, {type.value} FROM stats ORDER BY {type.value} DESC")
            leaderboard_data = c.fetchall()

        conn.close()

        embed = discord.Embed(
            title=f"🏆 Leaderboard - {type.name}",
            color=discord.Color.gold()
        )

        for rank, entry in enumerate(leaderboard_data[:10], start=1):
            if type.value == "winrate":
                user_id, winrate = entry
                value = f"{winrate:.2f}%"
            else:
                user_id, stat_value = entry
                value = str(stat_value)

            user = interaction.guild.get_member(user_id)
            name = user.display_name if user else f"User {user_id}"
            embed.add_field(name=f"#{rank} {name}", value=value, inline=False)

        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="stats", description="Affiche vos statistiques personnelles.")
    async def stats(self, interaction: discord.Interaction):
        """Affiche les stats de l'utilisateur"""
        stats = self.get_stats(interaction.user.id)
        embed = discord.Embed(
            title=f"📊 Stats de {interaction.user.display_name}",
            color=discord.Color.blue()
        )
        embed.add_field(name="Victoires", value=str(stats["wins"]))
        embed.add_field(name="Défaites", value=str(stats["losses"]))
        embed.add_field(name="Kills", value=str(stats["kills"]))
        embed.add_field(name="Morts", value=str(stats["deaths"]))
        total_games = stats["wins"] + stats["losses"]
        winrate = (stats["wins"] / total_games * 100) if total_games > 0 else 0
        embed.add_field(name="Winrate", value=f"{winrate:.2f}%", inline=False)

        await interaction.response.send_message(embed=embed)

async def setup(bot):
    await bot.add_cog(Stats(bot))
