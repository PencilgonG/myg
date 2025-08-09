import re
from typing import Optional

import discord
from discord import app_commands
from discord.ext import commands

from settings import settings

# DB (profils + stats)
from bot.db import (
    init_db,                   # profils (opgg/dpm/elo)
    get_profile as db_get_profile,
    upsert_profile,
    get_stats,                 # stats globales
    get_role_stats,            # stats par rôle
)

# on réutilise la config du rôle "inhouse" si défini par /set_inhouse_role
from bot.store import get_inhouse_role

# ---- Design MYG ----
MYG_COLOR   = 0xF1E0B0
MYG_DARK    = 0x111111
MYG_ACCENT  = 0xE85D5D
MYG_BANNER  = getattr(settings, "MYG_BANNER_URL", None)
MYG_LOGO    = getattr(settings, "MYG_LOGO_URL", None)

ROLE_EMOJI = {"Top":"🛡️","Jungle":"🌿","Mid":"🧠","ADC":"🏹","Support":"💉"}


def _is_url(s: Optional[str]) -> bool:
    if not s:
        return False
    return bool(re.match(r"^https?://", s.strip(), flags=re.I))


def _clean_url(s: Optional[str]) -> Optional[str]:
    if not s:
        return None
    s = s.strip()
    return s if _is_url(s) else None


async def _ensure_inhouse_role(member: discord.Member) -> None:
    """Assigne (ou crée) le rôle 'inhouse' lors du premier enregistrement de profil."""
    guild = member.guild

    # 1) rôle configuré via /set_inhouse_role
    rid = get_inhouse_role(guild.id)
    role = guild.get_role(rid) if rid else None

    # 2) sinon, rôle existant nommé "inhouse"
    if role is None:
        for r in guild.roles:
            if r.name.lower() == "inhouse":
                role = r
                break

    # 3) sinon, création
    if role is None:
        try:
            role = await guild.create_role(
                name="inhouse",
                colour=discord.Colour.from_rgb(30, 30, 30),
                mentionable=True,
                reason="Création auto pour profils inhouse",
            )
        except Exception:
            role = None

    # attribution
    if role and role not in member.roles:
        try:
            await member.add_roles(role, reason="Premier enregistrement de profil inhouse (à vie).")
        except Exception:
            pass


class Profiles(commands.Cog):
    """Gestion des profils joueur (OPGG, DPM, Elo) + affichage stats dans /profil view."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        # init des tables profils (et db si pas présente)
        init_db()

    group = app_commands.Group(name="profil", description="Gérer ton profil inhouse (opgg, dpm, elo).")

    @group.command(name="set", description="Configurer/mettre à jour ton profil (opgg, dpm, elo).")
    @app_commands.describe(
        opgg="Lien OP.GG (https://...)",
        dpm="Lien DPM (https://...)",
        elo="Ton rang actuel (ex: Gold 2 / Diamond 4 / Master)"
    )
    async def set_profile(
        self,
        interaction: discord.Interaction,
        opgg: Optional[str] = None,
        dpm: Optional[str] = None,
        elo: Optional[str] = None
    ):
        guild = interaction.guild
        if not guild:
            return await interaction.response.send_message("Commande uniquement en serveur.", ephemeral=True)

        member = guild.get_member(interaction.user.id)
        if not member:
            return await interaction.response.send_message("Membre introuvable.", ephemeral=True)

        # normalisation des URLs
        opgg_url = _clean_url(opgg)
        dpm_url  = _clean_url(dpm)

        # état avant pour savoir si première fois
        before = db_get_profile(guild.id, member.id)
        is_first_time = before is None

        # upsert
        upsert_profile(
            guild_id=guild.id,
            user_id=member.id,
            opgg_url=opgg_url if opgg is not None else (before["opgg_url"] if before else None),
            dpm_url=dpm_url if dpm is not None else (before["dpm_url"] if before else None),
            elo=elo if elo is not None else (before["elo"] if before else None),
            discord_name=member.display_name,
        )

        # rôle inhouse si première fois
        if is_first_time:
            await _ensure_inhouse_role(member)

        # confirmation (joli embed)
        after = db_get_profile(guild.id, member.id)
        emb = discord.Embed(
            title="Profil mis à jour",
            description="Tes infos inhouse ont bien été enregistrées.",
            color=MYG_ACCENT
        )
        if MYG_BANNER: emb.set_image(url=MYG_BANNER)
        if MYG_LOGO:   emb.set_thumbnail(url=MYG_LOGO)

        def link(name: str, url: Optional[str]) -> str:
            return f"[{name}]({url})" if url else "—"

        emb.add_field(name="OP.GG", value=link("Voir OPGG", after.get("opgg_url")), inline=True)
        emb.add_field(name="DPM",   value=link("Voir DPM",   after.get("dpm_url")), inline=True)
        emb.add_field(name="Elo",   value=after.get("elo") or "—", inline=True)
        emb.set_footer(text=f"MYG Inhouse • {member.display_name}")

        await interaction.response.send_message(embed=emb, ephemeral=True)

    @group.command(name="view", description="Afficher un profil (par défaut le tien) avec les stats.")
    @app_commands.describe(user="Utilisateur (optionnel)")
    async def view_profile(self, interaction: discord.Interaction, user: Optional[discord.Member] = None):
        guild = interaction.guild
        if not guild:
            return await interaction.response.send_message("Commande uniquement en serveur.", ephemeral=True)

        member = user or guild.get_member(interaction.user.id)
        if not member:
            return await interaction.response.send_message("Membre introuvable.", ephemeral=True)

        prof = db_get_profile(guild.id, member.id)
        if not prof:
            return await interaction.response.send_message("Aucun profil enregistré pour cet utilisateur.", ephemeral=True)

        emb = discord.Embed(
            title=f"Profil — {member.display_name}",
            description="Résumé du profil inhouse",
            color=MYG_DARK
        )
        if MYG_BANNER: emb.set_image(url=MYG_BANNER)
        if MYG_LOGO:   emb.set_thumbnail(url=MYG_LOGO)

        def link(name: str, url: Optional[str]) -> str:
            return f"[{name}]({url})" if url else "—"

        emb.add_field(name="OP.GG", value=link("Voir OPGG", prof.get("opgg_url")), inline=True)
        emb.add_field(name="DPM",   value=link("Voir DPM",   prof.get("dpm_url")), inline=True)
        emb.add_field(name="Elo",   value=prof.get("elo") or "—", inline=True)

        # stats globales
        s = get_stats(guild.id, member.id)
        games, wins, losses = s["games"], s["wins"], s["losses"]
        wr = (wins / games * 100) if games else 0.0
        emb.add_field(
            name="Stats",
            value=f"**{wins}** wins • **{losses}** losses • **{games}** games • **{wr:.1f}%** WR",
            inline=False
        )

        # stats par rôle
        rows = get_role_stats(guild.id, member.id)
        if rows:
            lines = []
            for r in rows:
                g, w = r["games"], r["wins"]
                wr2 = (w / g * 100) if g else 0.0
                lines.append(f"{ROLE_EMOJI.get(r['role'],'🎮')} **{r['role']}** — {w}/{g} wins (*{wr2:.1f}% WR*)")
            emb.add_field(name="Par rôle", value="\n".join(lines), inline=False)

        if s["last_played"]:
            emb.set_footer(text=f"Dernière partie: {s['last_played']}")

        await interaction.response.send_message(embed=emb, ephemeral=False)


async def setup(bot: commands.Bot):
    await bot.add_cog(Profiles(bot))
