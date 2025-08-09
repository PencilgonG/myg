# src/bot/cogs/core.py
import asyncio
import random
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

import discord
from discord import app_commands
from discord.ext import commands

from settings import settings

# Store (clé/val) existant du projet
from bot.store import (
    set_announce_channel, get_announce_channel,
    set_inhouse_role, get_inhouse_role,
    set_mod_role, get_mod_role,
    update_profile_join, get_profile, set_profile_fields,
)

# DB (SQLite) – stats/matches
from bot.db import init_db_stats, record_match

# =========================================
#               DESIGN MYG
# =========================================

ROLE_NAMES = ["Top", "Jungle", "Mid", "ADC", "Support"]

MYG_COLOR   = 0xF1E0B0      # sable
MYG_DARK    = 0x111111      # noir
MYG_ACCENT  = 0xE85D5D      # rouge accent

MYG_BANNER  = getattr(settings, "MYG_BANNER_URL", None)  # ex: https://cdn.discordapp.com/.../myg_banner.png
MYG_LOGO    = getattr(settings, "MYG_LOGO_URL", None)    # ex: https://cdn.discordapp.com/.../myg_logo.png

ROLE_ICON = {
    "Top":     "🛡️",
    "Jungle":  "🌿",
    "Mid":     "🧠",
    "ADC":     "🏹",
    "Support": "💉",
}

def role_label(r: str) -> str:
    return f"{ROLE_ICON.get(r,'🎮')} {r}"

def parse_region_from_tag(name_tag: str | None) -> str | None:
    if not name_tag or "#" not in name_tag:
        return None
    _, tag = name_tag.rsplit("#", 1)
    tag = tag.strip().lower()
    m = {
        "euw": "euw", "euw1": "euw",
        "eune": "eune", "eun1": "eune",
        "na": "na", "na1": "na",
        "kr": "kr", "br": "br", "br1": "br",
        "lan": "lan", "las": "las",
        "oce": "oce", "oc1": "oce",
        "tr": "tr", "ru": "ru", "jp": "jp"
    }
    return m.get(tag)

def build_links_from_profile(prof: dict | None) -> tuple[Optional[str], Optional[str]]:
    """Retourne (main_link, dpm_link) – main = opgg si dispo, sinon dpm."""
    if not prof:
        return (None, None)
    opgg = prof.get("opgg_url")
    dpm = prof.get("dpm_url")
    if opgg:
        return (opgg, dpm)
    nt = prof.get("name_tag")
    region = parse_region_from_tag(nt)
    if nt and region:
        summ = nt.split("#")[0]
        return (f"https://www.op.gg/summoners/{region}/{summ}", dpm)
    return (dpm, None) if dpm else (None, None)

def gen_password4() -> str:
    alphabet = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"  # sans 0/O/I/1
    return "".join(random.choice(alphabet) for _ in range(4))

def is_inhouse_mod():
    async def predicate(inter: discord.Interaction):
        if inter.user.guild_permissions.manage_guild:
            return True
        rid = get_mod_role(inter.guild_id or 0)
        return rid is not None and any(r.id == rid for r in getattr(inter.user, "roles", []))
    return app_commands.check(predicate)

def _is_inhouse_mod_or_owner(inter: discord.Interaction, lobby: "Lobby") -> bool:
    if inter.user.guild_permissions.manage_guild:
        return True
    if inter.user.id == lobby.owner_id:
        return True
    rid = get_mod_role(inter.guild_id or 0)
    return bool(rid and any(r.id == rid for r in inter.user.roles))

# =========================================
#            DONNÉES DU LOBBY
# =========================================

@dataclass
class Player:
    user_id: int
    mention: str
    role: Optional[str] = None
    name_tag: Optional[str] = None  # "Summoner#TAG"

@dataclass
class Lobby:
    guild_id: int
    owner_id: int
    title: str
    mode: str
    role_slots: Dict[str, int]
    password: Optional[str] = None
    players: Dict[int, Player] = field(default_factory=dict)
    subs: Dict[int, Player] = field(default_factory=dict)
    message_id: Optional[int] = None
    close_when_full: bool = True
    closed: bool = False
    auto_end_task: Optional[asyncio.Task] = None
    auto_end_at: Optional[float] = None

    # Team Builder
    cap_blue_id: Optional[int] = None
    cap_red_id: Optional[int] = None
    team_blue_ids: List[int] = field(default_factory=list)
    team_red_ids: List[int] = field(default_factory=list)
    team_builder_msg_id: Optional[int] = None

    # Catégorie/salons d’équipe
    category_id: Optional[int] = None
    blue_text_id: Optional[int] = None
    red_text_id: Optional[int] = None
    blue_voice_id: Optional[int] = None
    red_voice_id: Optional[int] = None

    @property
    def total_slots(self) -> int:
        return sum(self.role_slots.values())

    def counts_by_role(self) -> Dict[str, int]:
        c = {r: 0 for r in ROLE_NAMES}
        for p in self.players.values():
            if p.role in c:
                c[p.role] += 1
        return c

    def has_free_slot(self, role: str) -> bool:
        return self.counts_by_role().get(role, 0) < self.role_slots.get(role, 0)

    def check_full_and_close(self):
        if self.close_when_full and len(self.players) >= self.total_slots:
            self.closed = True

    # ---- AFFICHAGE JOUEUR ----
    def _format_player_line(self, p: Player) -> str:
        """
        Affiche : [LoLName#TAG](op.gg) — (DiscordName) · Elo
        """
        prof = get_profile(p.user_id)
        main_link, _ = build_links_from_profile(prof)

        lol_tag = p.name_tag or (prof.get("name_tag") if prof else None)
        if lol_tag:
            lol_text = f"**{lol_tag}**"
            lol_part = f"[{lol_text}]({main_link})" if main_link else lol_text
        else:
            lol_part = p.mention

        # Discord name lisible (persisté en profile si présent)
        if prof and prof.get("discord_name"):
            discord_name = prof["discord_name"]
        else:
            discord_name = p.mention  # fallback lisible

        elo = prof.get("elo") if prof else None
        elo_part = f" · {elo}" if elo else ""

        return f"{lol_part} — ({discord_name}){elo_part}"

    # ---- EMBED LOBBY (style MYG, horizontal) ----
    def as_embed(self) -> discord.Embed:
        emb = discord.Embed(
            title=self.title,
            description=f"Inhouse **{self.mode}** · MDP : {'`***`' if self.password else '—'}",
            color=MYG_DARK
        )
        if MYG_BANNER:
            emb.set_image(url=MYG_BANNER)
        if MYG_LOGO:
            emb.set_thumbnail(url=MYG_LOGO)

        state = "Fermé" if self.closed else "Ouvert"
        emb.add_field(name="État", value=state, inline=True)
        emb.add_field(name="Slots", value=f"{len(self.players)}/{self.total_slots}", inline=True)
        emb.add_field(name="\u200b", value="\u200b", inline=True)

        # colonnes par rôle (3 / 2)
        col_left, col_right = [], []
        for i, r in enumerate(ROLE_NAMES):
            taken = [p for p in self.players.values() if p.role == r]
            maxr = self.role_slots.get(r, 0)
            lines = []
            for p in taken:
                lines.append(f"{ROLE_ICON.get(r,'🎮')} {self._format_player_line(p)}")
            for _ in range(max(0, maxr - len(taken))):
                lines.append(f"{ROLE_ICON.get(r,'🎮')} *libre*")
            block = "\n".join(lines) if lines else "*—*"
            (col_left if i < 3 else col_right).append(f"**{r}**\n{block}")

        emb.add_field(name="Équipe A", value="\n\n".join(col_left) or "—", inline=True)
        emb.add_field(name="Équipe B", value="\n\n".join(col_right) or "—", inline=True)

        subs_text = "—" if not self.subs else "\n".join(f"• {self._format_player_line(p)}" for p in self.subs.values())
        emb.add_field(name="Remplaçants", value=subs_text, inline=False)

        if self.auto_end_at:
            import time
            remaining = int(self.auto_end_at - time.time())
            if remaining > 0:
                emb.set_footer(text=f"Se termine automatiquement ~ {remaining // 60} min")
        return emb


# =========================================
#      VUE LOBBY (inscriptions)
# =========================================

class NameTagModal(discord.ui.Modal, title="Entre ton pseudo LoL"):
    def __init__(self, on_submit_callback, preset: Optional[str] = None):
        super().__init__()
        self.on_submit_callback = on_submit_callback
        self.name_tag = discord.ui.TextInput(
            label="Pseudo (ex: TheBest#EUW)", style=discord.TextStyle.short,
            default=preset or "", required=True, max_length=40
        )
        self.add_item(self.name_tag)

    async def on_submit(self, interaction: discord.Interaction):
        await self.on_submit_callback(interaction, str(self.name_tag.value).strip())

class ToggleCloseButton(discord.ui.Button):
    def __init__(self, parent_view: "LobbyView"):
        label = "Close when full: ON" if parent_view.lobby.close_when_full else "Close when full: OFF"
        style = discord.ButtonStyle.success if parent_view.lobby.close_when_full else discord.ButtonStyle.secondary
        super().__init__(style=style, label=label, emoji="🔒")
        self.parent_view = parent_view

    async def callback(self, interaction: discord.Interaction):
        rid = get_mod_role(interaction.guild_id or 0)
        is_mod = interaction.user.guild_permissions.manage_guild or (rid and any(r.id == rid for r in interaction.user.roles))
        if not is_mod:
            if not interaction.response.is_done():
                try: await interaction.response.defer()
                except Exception: pass
            return
        self.parent_view.lobby.close_when_full = not self.parent_view.lobby.close_when_full
        self.label = "Close when full: ON" if self.parent_view.lobby.close_when_full else "Close when full: OFF"
        self.style = discord.ButtonStyle.success if self.parent_view.lobby.close_when_full else discord.ButtonStyle.secondary
        await self.parent_view.update_lobby_message(interaction)

class LobbyView(discord.ui.View):
    def __init__(self, cog: "Core", lobby: Lobby, test_fill: bool = False, show_finish: bool = True):
        super().__init__(timeout=None)
        self.cog = cog
        self.lobby = lobby

        options = [discord.SelectOption(label=r, description=f"Rejoindre en {r}", emoji=ROLE_ICON.get(r)) for r in ROLE_NAMES]
        self.role_select = RoleSelect(self, options=options, placeholder="Choisir un rôle pour s'inscrire…")
        self.add_item(self.role_select)

        self.add_item(SubButton(self))
        self.add_item(QuitButton(self))
        if test_fill: self.add_item(TestFillButton(self))
        if show_finish: self.add_item(FinishButton(self))
        self.add_item(ToggleCloseButton(self))

        # bouton Team Builder (modo)
        self.add_item(PickTeamsButton(self))

    async def update_lobby_message(self, interaction: discord.Interaction):
        try:
            if not interaction.response.is_done():
                await interaction.response.defer()
        except Exception:
            pass
        try:
            msg = await interaction.channel.fetch_message(self.lobby.message_id)
            self.role_select.disabled = self.lobby.closed
            await msg.edit(embed=self.lobby.as_embed(), view=self)
        except Exception:
            pass

class RoleSelect(discord.ui.Select):
    def __init__(self, parent_view: LobbyView, options: List[discord.SelectOption], placeholder: str):
        super().__init__(min_values=1, max_values=1, options=options, placeholder=placeholder)
        self.parent_view = parent_view

    async def callback(self, interaction: discord.Interaction):
        lobby = self.parent_view.lobby
        if lobby.closed:
            if not interaction.response.is_done():
                try: await interaction.response.defer()
                except Exception: pass
            return
        role = self.values[0]
        uid = interaction.user.id
        if uid in lobby.players or not lobby.has_free_slot(role):
            if not interaction.response.is_done():
                try: await interaction.response.defer()
                except Exception: pass
            return

        async def after_modal(inter: discord.Interaction, name_tag: str):
            lobby.subs.pop(uid, None)
            lobby.players[uid] = Player(uid, inter.user.mention, role=role, name_tag=name_tag)
            lobby.check_full_and_close()
            update_profile_join(uid, name_tag, as_sub=False)
            # mémoriser un nom discord lisible si pas encore stocké
            prof = get_profile(uid) or {}
            if not prof.get("discord_name"):
                set_profile_fields(uid, {"discord_name": inter.user.display_name})
            await self.parent_view.update_lobby_message(inter)

        prof = get_profile(uid)
        await interaction.response.send_modal(NameTagModal(after_modal, preset=(prof.get("name_tag") if prof else None)))

class SubButton(discord.ui.Button):
    def __init__(self, parent_view: LobbyView):
        super().__init__(style=discord.ButtonStyle.secondary, label="Se mettre Sub", emoji="🧩")
        self.parent_view = parent_view

    async def callback(self, interaction: discord.Interaction):
        lobby = self.parent_view.lobby; uid = interaction.user.id

        async def after_modal(inter: discord.Interaction, name_tag: str):
            lobby.players.pop(uid, None)
            lobby.subs[uid] = Player(uid, inter.user.mention, role=None, name_tag=name_tag)
            update_profile_join(uid, name_tag, as_sub=True)
            prof = get_profile(uid) or {}
            if not prof.get("discord_name"):
                set_profile_fields(uid, {"discord_name": inter.user.display_name})
            await self.parent_view.update_lobby_message(inter)

        prof = get_profile(uid)
        await interaction.response.send_modal(NameTagModal(after_modal, preset=(prof.get("name_tag") if prof else None)))

class QuitButton(discord.ui.Button):
    def __init__(self, parent_view: LobbyView):
        super().__init__(style=discord.ButtonStyle.danger, label="Quitter", emoji="🚪")
        self.parent_view = parent_view

    async def callback(self, interaction: discord.Interaction):
        lobby = self.parent_view.lobby; uid = interaction.user.id
        removed = False
        if uid in lobby.players: lobby.players.pop(uid); removed = True
        if uid in lobby.subs: lobby.subs.pop(uid); removed = True
        if not removed:
            if not interaction.response.is_done():
                try: await interaction.response.defer()
                except Exception: pass
            return
        lobby.closed = False
        await self.parent_view.update_lobby_message(interaction)

class FinishButton(discord.ui.Button):
    def __init__(self, parent_view: LobbyView):
        super().__init__(style=discord.ButtonStyle.primary, label="Terminer", emoji="✅")
        self.parent_view = parent_view

    async def callback(self, interaction: discord.Interaction):
        lobby = self.parent_view.lobby
        if interaction.user.id != lobby.owner_id and not interaction.user.guild_permissions.manage_guild:
            if not interaction.response.is_done():
                try: await interaction.response.defer()
                except Exception: pass
            return
        await self.parent_view.cog._end_lobby(interaction, lobby, manual=True)

class TestFillButton(discord.ui.Button):
    def __init__(self, parent_view: LobbyView):
        super().__init__(style=discord.ButtonStyle.success, label="Test Fill (10)", emoji="🧪")
        self.parent_view = parent_view

    async def callback(self, interaction: discord.Interaction):
        lobby = self.parent_view.lobby
        if interaction.user.id != lobby.owner_id and not interaction.user.guild_permissions.manage_guild:
            if not interaction.response.is_done():
                try: await interaction.response.defer()
                except Exception: pass
            return
        lobby.players.clear(); lobby.subs.clear()
        fake_id = 10_000
        for r in ROLE_NAMES:
            for _ in range(lobby.role_slots.get(r, 0)):
                fake_id += 1
                lobby.players[fake_id] = Player(fake_id, f"`@Fake{fake_id}`", r, f"Fake{r}#{r[:2].upper()}")
        for i in range(3):
            lobby.subs[20_000 + i] = Player(20_000 + i, f"`@Sub{i+1}`", None, f"Sub{i+1}#XX")
        lobby.check_full_and_close()
        await self.parent_view.update_lobby_message(interaction)

# =========================================
#      CRÉATION / CLEANUP DES SALONS
# =========================================

async def create_team_channels(guild: discord.Guild, lobby: Lobby, title: str):
    """Crée catégorie + 2 salons text + 2 salons voc, configure permissions par membre."""
    if lobby.category_id:
        return

    category = await guild.create_category(f"Inhouse – {title}")
    lobby.category_id = category.id

    deny_everyone = {guild.default_role: discord.PermissionOverwrite(view_channel=False, connect=False, send_messages=False)}

    blue_text = await guild.create_text_channel("blue-chat", category=category, overwrites=deny_everyone)
    red_text  = await guild.create_text_channel("red-chat",  category=category, overwrites=deny_everyone)
    blue_vc   = await guild.create_voice_channel("Blue",    category=category, overwrites=deny_everyone)
    red_vc    = await guild.create_voice_channel("Red",     category=category, overwrites=deny_everyone)

    lobby.blue_text_id = blue_text.id
    lobby.red_text_id  = red_text.id
    lobby.blue_voice_id = blue_vc.id
    lobby.red_voice_id  = red_vc.id

    # overwrites par équipe + mods
    overwrites_blue = {guild.default_role: discord.PermissionOverwrite(view_channel=False)}
    overwrites_red  = {guild.default_role: discord.PermissionOverwrite(view_channel=False)}
    mod_role_id = get_mod_role(guild.id)
    if mod_role_id:
        role = guild.get_role(mod_role_id)
        if role:
            overwrites_blue[role] = discord.PermissionOverwrite(view_channel=True, send_messages=True, connect=True)
            overwrites_red[role]  = discord.PermissionOverwrite(view_channel=True, send_messages=True, connect=True)

    blue_member_ids = set([lobby.cap_blue_id] if lobby.cap_blue_id else []) | set(lobby.team_blue_ids)
    red_member_ids  = set([lobby.cap_red_id]  if lobby.cap_red_id  else []) | set(lobby.team_red_ids)

    for uid in blue_member_ids:
        m = guild.get_member(uid)
        if m: overwrites_blue[m] = discord.PermissionOverwrite(view_channel=True, send_messages=True, connect=True)
    for uid in red_member_ids:
        m = guild.get_member(uid)
        if m: overwrites_red[m] = discord.PermissionOverwrite(view_channel=True, send_messages=True, connect=True)

    await blue_text.edit(overwrites=overwrites_blue)
    await blue_vc.edit(overwrites=overwrites_blue)
    await red_text.edit(overwrites=overwrites_red)
    await red_vc.edit(overwrites=overwrites_red)

async def cleanup_team_channels(guild: discord.Guild, lobby: Lobby):
    """Supprime proprement les salons Blue/Red puis la catégorie (si encore présente)."""
    # 1) supprimer les salons si on les a encore
    for chan_id in (lobby.blue_text_id, lobby.red_text_id, lobby.blue_voice_id, lobby.red_voice_id):
        try:
            if chan_id:
                ch = guild.get_channel(chan_id)
                if ch:  # text ou voice
                    await ch.delete()
        except Exception:
            pass

    # 2) supprimer la catégorie (sinon les enfants seraient détachés en haut)
    try:
        if lobby.category_id:
            cat = guild.get_channel(lobby.category_id)
            if isinstance(cat, discord.CategoryChannel):
                await cat.delete()
    except Exception:
        pass

    # 3) reset des IDs en mémoire
    lobby.category_id = None
    lobby.blue_text_id = None
    lobby.red_text_id = None
    lobby.blue_voice_id = None
    lobby.red_voice_id = None

# =========================================
#           TEAM BUILDER (MANUEL)
# =========================================

class PickTeamsButton(discord.ui.Button):
    def __init__(self, parent_view: LobbyView):
        super().__init__(style=discord.ButtonStyle.secondary, label="Pick captains / Teams", emoji="🧿")
        self.parent_view = parent_view

    async def callback(self, interaction: discord.Interaction):
        lobby = self.parent_view.lobby
        if not _is_inhouse_mod_or_owner(interaction, lobby):
            if not interaction.response.is_done():
                try: await interaction.response.defer()
                except Exception: pass
            return

        # un seul Team Builder à la fois
        if lobby.team_builder_msg_id:
            try:
                if not interaction.response.is_done():
                    await interaction.response.defer()
                msg = await interaction.channel.fetch_message(lobby.team_builder_msg_id)
                view = TeamBuilderView(self.parent_view.cog, lobby)
                await msg.edit(embed=view.render_embed(interaction.guild), view=view)
                return
            except Exception:
                lobby.team_builder_msg_id = None

        view = TeamBuilderView(self.parent_view.cog, lobby)
        embed = view.render_embed(interaction.guild)
        if not interaction.response.is_done():
            await interaction.response.defer()
        msg = await interaction.channel.send(embed=embed, view=view)
        lobby.team_builder_msg_id = msg.id

class TeamBuilderView(discord.ui.View):
    """UI pour choisir 2 capitaines et répartir les joueurs dans BLUE/RED. Un seul message qui s'édite."""
    def __init__(self, cog: "Core", lobby: Lobby):
        super().__init__(timeout=600)
        self.cog = cog
        self.lobby = lobby

        # selects capitaines (rows séparées)
        self.add_item(BlueCaptainSelect(self, row=0))
        self.add_item(RedCaptainSelect(self, row=1))
        # selects ajout joueurs (rows séparées)
        self.add_item(AddBlueSelect(self, row=2))
        self.add_item(AddRedSelect(self, row=3))
        # boutons tous en row=4
        self.add_item(ResetTeamsButton(self, row=4))
        self.add_item(ValidateTeamsButton(self, row=4))   # <-- Valider = crée salons + embed final + prompt vainqueur
        self.add_item(CloseTeamBuilderButton(self, row=4))

    def _name_for(self, guild: discord.Guild, uid: int | None) -> str:
        if not uid: return "—"
        m = guild.get_member(uid)
        return m.mention if m else f"<@{uid}>"

    def _lines_for_ids(self, guild: discord.Guild, ids: List[int]) -> str:
        if not ids: return "—"
        out = []
        for uid in ids:
            p = self.lobby.players.get(uid) or self.lobby.subs.get(uid) or Player(uid, f"<@{uid}>")
            out.append(f"• {self.lobby._format_player_line(p)}")
        return "\n".join(out)

    def _pool_ids(self) -> List[int]:
        all_ids = list(self.lobby.players.keys())
        taken = set(self.lobby.team_blue_ids) | set(self.lobby.team_red_ids)
        if self.lobby.cap_blue_id: taken.add(self.lobby.cap_blue_id)
        if self.lobby.cap_red_id: taken.add(self.lobby.cap_red_id)
        return [uid for uid in all_ids if uid not in taken]

    def render_embed(self, guild: discord.Guild) -> discord.Embed:
        emb = discord.Embed(title="Team Builder", color=MYG_DARK)
        if MYG_BANNER: emb.set_image(url=MYG_BANNER)
        if MYG_LOGO:   emb.set_thumbnail(url=MYG_LOGO)

        emb.add_field(name="Capitaine BLUE", value=self._name_for(guild, self.lobby.cap_blue_id), inline=True)
        emb.add_field(name="Capitaine RED",  value=self._name_for(guild, self.lobby.cap_red_id),  inline=True)
        emb.add_field(name="\u200b", value="\u200b", inline=True)
        emb.add_field(name="BLUE", value=self._lines_for_ids(guild, self.lobby.team_blue_ids), inline=True)
        emb.add_field(name="RED",  value=self._lines_for_ids(guild, self.lobby.team_red_ids),  inline=True)
        pool = [self._name_for(guild, uid) for uid in self._pool_ids()]
        emb.add_field(name="Joueurs disponibles", value="\n".join(pool) or "—", inline=False)
        emb.set_footer(text="Sélectionne les capitaines puis répartis les joueurs, clique Valider.")
        return emb

    async def _edit_self(self, interaction: discord.Interaction):
        try:
            if not interaction.response.is_done():
                if getattr(interaction, "message", None) is not None:
                    await interaction.response.defer_update()
                else:
                    await interaction.response.defer()
        except Exception:
            pass
        try:
            msg = await interaction.channel.fetch_message(self.lobby.team_builder_msg_id)
            await msg.edit(embed=self.render_embed(interaction.guild), view=self)
        except Exception:
            pass

class BlueCaptainSelect(discord.ui.Select):
    def __init__(self, parent: TeamBuilderView, row: int = 0):
        options = [discord.SelectOption(label="(aucun)", value="0", default=parent.lobby.cap_blue_id is None)]
        for uid in parent.lobby.players.keys():
            options.append(discord.SelectOption(label=str(uid), value=str(uid)))
        super().__init__(placeholder="Capitaine BLUE", min_values=1, max_values=1, options=options, row=row)
        self.parent = parent

    async def callback(self, interaction: discord.Interaction):
        if not _is_inhouse_mod_or_owner(interaction, self.parent.lobby):
            return await self.parent._edit_self(interaction)
        v = int(self.values[0])
        self.parent.lobby.cap_blue_id = None if v == 0 else v
        await self.parent._edit_self(interaction)

class RedCaptainSelect(discord.ui.Select):
    def __init__(self, parent: TeamBuilderView, row: int = 1):
        options = [discord.SelectOption(label="(aucun)", value="0", default=parent.lobby.cap_red_id is None)]
        for uid in parent.lobby.players.keys():
            options.append(discord.SelectOption(label=str(uid), value=str(uid)))
        super().__init__(placeholder="Capitaine RED", min_values=1, max_values=1, options=options, row=row)
        self.parent = parent

    async def callback(self, interaction: discord.Interaction):
        if not _is_inhouse_mod_or_owner(interaction, self.parent.lobby):
            return await self.parent._edit_self(interaction)
        v = int(self.values[0])
        self.parent.lobby.cap_red_id = None if v == 0 else v
        await self.parent._edit_self(interaction)

class AddBlueSelect(discord.ui.Select):
    def __init__(self, parent: TeamBuilderView, row: int = 2):
        pool = parent._pool_ids()
        opts = [discord.SelectOption(label=str(uid), value=str(uid)) for uid in pool]
        maxv = min(10, len(opts)) if len(opts) > 0 else 1
        super().__init__(placeholder="Ajouter -> BLUE", min_values=0, max_values=maxv, options=opts, row=row)
        self.parent = parent

    async def callback(self, interaction: discord.Interaction):
        if not _is_inhouse_mod_or_owner(interaction, self.parent.lobby):
            return await self.parent._edit_self(interaction)
        ids = [int(x) for x in self.values]
        self.parent.lobby.team_blue_ids.extend(u for u in ids if u not in self.parent.lobby.team_blue_ids)
        await self.parent._edit_self(interaction)

class AddRedSelect(discord.ui.Select):
    def __init__(self, parent: TeamBuilderView, row: int = 3):
        pool = parent._pool_ids()
        opts = [discord.SelectOption(label=str(uid), value=str(uid)) for uid in pool]
        maxv = min(10, len(opts)) if len(opts) > 0 else 1
        super().__init__(placeholder="Ajouter -> RED", min_values=0, max_values=maxv, options=opts, row=row)
        self.parent = parent

    async def callback(self, interaction: discord.Interaction):
        if not _is_inhouse_mod_or_owner(interaction, self.parent.lobby):
            return await self.parent._edit_self(interaction)
        ids = [int(x) for x in self.values]
        self.parent.lobby.team_red_ids.extend(u for u in ids if u not in self.parent.lobby.team_red_ids)
        await self.parent._edit_self(interaction)

class ResetTeamsButton(discord.ui.Button):
    def __init__(self, parent: TeamBuilderView, row: int = 4):
        super().__init__(style=discord.ButtonStyle.secondary, label="Reset", emoji="♻️", row=row)
        self.parent = parent

    async def callback(self, interaction: discord.Interaction):
        if not _is_inhouse_mod_or_owner(interaction, self.parent.lobby):
            return await self.parent._edit_self(interaction)
        self.parent.lobby.team_blue_ids.clear()
        self.parent.lobby.team_red_ids.clear()
        await self.parent._edit_self(interaction)

class WinnerPromptView(discord.ui.View):
    def __init__(self, on_pick):
        super().__init__(timeout=120)
        self.on_pick = on_pick

    @discord.ui.button(label="Blue a gagné", style=discord.ButtonStyle.primary, emoji="🔵")
    async def blue_win(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.on_pick(interaction, "blue")

    @discord.ui.button(label="Red a gagné", style=discord.ButtonStyle.danger, emoji="🔴")
    async def red_win(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.on_pick(interaction, "red")

    @discord.ui.button(label="Plus tard", style=discord.ButtonStyle.secondary, emoji="⏭️")
    async def later(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message("Ok, enregistrement ignoré pour l’instant.", ephemeral=True)
        self.stop()

class ValidateTeamsButton(discord.ui.Button):
    def __init__(self, parent: "TeamBuilderView", row: int = 4):
        super().__init__(style=discord.ButtonStyle.success, label="Valider", emoji="✅", row=row)
        self.parent = parent

    async def callback(self, interaction: discord.Interaction):
        lob = self.parent.lobby
        if not _is_inhouse_mod_or_owner(interaction, lob):
            return await self.parent._edit_self(interaction)

        if not lob.cap_blue_id or not lob.cap_red_id:
            try:
                await interaction.response.send_message("Choisis d'abord les deux capitaines.", ephemeral=True)
            except Exception:
                pass
            return

        # crée les salons si pas déjà faits
        await create_team_channels(interaction.guild, lob, lob.title)

        # embed final (stylé & horizontal)
        final = build_final_teams_embed(interaction.guild, lob)
        await interaction.channel.send(embed=final)

        # demander le vainqueur pour enregistrer la game
        async def on_pick(inter: discord.Interaction, winner: str):
            # rôle par joueur depuis le lobby (pour stats par rôle)
            role_map = {}
            for uid, pl in lob.players.items():
                if (uid in lob.team_blue_ids) or (uid in lob.team_red_ids) or (uid == lob.cap_blue_id) or (uid == lob.cap_red_id):
                    if pl.role:
                        role_map[uid] = pl.role

            blue_ids = list(lob.team_blue_ids)
            red_ids  = list(lob.team_red_ids)
            if lob.cap_blue_id and lob.cap_blue_id not in blue_ids:
                blue_ids.append(lob.cap_blue_id)
            if lob.cap_red_id and lob.cap_red_id not in red_ids:
                red_ids.append(lob.cap_red_id)

            match_id = record_match(
                guild_id=inter.guild_id,
                mode=lob.mode,
                blue_ids=blue_ids,
                red_ids=red_ids,
                winner=winner,
                role_map=role_map
            )
            emb = discord.Embed(
                title=f"Match #{match_id} enregistré",
                description=f"Gagnant: **{'BLUE 🔵' if winner=='blue' else 'RED 🔴'}** · Mode **{lob.mode}**",
                color=discord.Color.green()
            )
            await inter.response.send_message(embed=emb, ephemeral=False)

        view = WinnerPromptView(on_pick)
        await interaction.followup.send(content="Qui a gagné cette inhouse ?", view=view, ephemeral=True)

        # ferme le Team Builder (on retire la carte)
        try:
            if not interaction.response.is_done():
                await interaction.response.defer()
            if lob.team_builder_msg_id:
                msg = await interaction.channel.fetch_message(lob.team_builder_msg_id)
                await msg.delete()
        except Exception:
            pass
        lob.team_builder_msg_id = None

class CloseTeamBuilderButton(discord.ui.Button):
    def __init__(self, parent: TeamBuilderView, row: int = 4):
        super().__init__(style=discord.ButtonStyle.danger, label="Close", emoji="🛑", row=row)
        self.parent = parent

    async def callback(self, interaction: discord.Interaction):
        if not _is_inhouse_mod_or_owner(interaction, self.parent.lobby):
            return await self.parent._edit_self(interaction)
        try:
            if not interaction.response.is_done():
                await interaction.response.defer()
            msg = await interaction.channel.fetch_message(self.parent.lobby.team_builder_msg_id)
            await msg.delete()
        except Exception:
            pass
        self.parent.lobby.team_builder_msg_id = None


def build_final_teams_embed(guild: discord.Guild, lobby: Lobby) -> discord.Embed:
    """Embed final avec les deux équipes et les capitaines, style MYG."""
    emb = discord.Embed(
        title=f"{lobby.title} — Line-ups",
        description=f"Inhouse **{lobby.mode}** · MDP : {'`***`' if lobby.password else '—'}",
        color=MYG_DARK
    )
    if MYG_BANNER: emb.set_image(url=MYG_BANNER)
    if MYG_LOGO:   emb.set_thumbnail(url=MYG_LOGO)

    def fmt(ids: List[int]) -> str:
        if not ids: return "—"
        out = []
        for uid in ids:
            p = lobby.players.get(uid) or lobby.subs.get(uid) or Player(uid, f"<@{uid}>")
            out.append(f"• {lobby._format_player_line(p)}")
        return "\n".join(out)

    cap_blue = f"**Capitaine :** <@{lobby.cap_blue_id}>" if lobby.cap_blue_id else "—"
    cap_red  = f"**Capitaine :** <@{lobby.cap_red_id}>"  if lobby.cap_red_id else "—"

    emb.add_field(name="Équipe Blue", value=f"{cap_blue}\n\n{fmt(lobby.team_blue_ids)}", inline=True)
    emb.add_field(name="Équipe Red",  value=f"{cap_red}\n\n{fmt(lobby.team_red_ids)}", inline=True)

    # Remplaçants
    subs_text = "—" if not lobby.subs else "\n".join(f"• {lobby._format_player_line(p)}" for p in lobby.subs.values())
    emb.add_field(name="Remplaçants", value=subs_text, inline=False)

    emb.set_footer(text="Bonne game • MYG Inhouse")
    return emb


# =========================================
#                COG CORE
# =========================================

class Core(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.lobbies: Dict[int, Lobby] = {}

    async def cog_load(self):
        # init tables stats/matches
        init_db_stats()
        # sync local si GUILD_ID_TEST est défini (copie dans main.py aussi)
        if getattr(settings, "GUILD_ID_TEST", None):
            guild = discord.Object(id=settings.GUILD_ID_TEST)
            self.bot.tree.copy_global_to(guild=guild)

    @app_commands.command(name="ping", description="Répond avec la latence.")
    async def ping(self, interaction: discord.Interaction):
        await interaction.response.send_message(f"Pong! {round(self.bot.latency*1000)} ms", ephemeral=True)

    @app_commands.command(name="set_announce_channel", description="Définir le salon d'annonce.")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def set_announce_channel_cmd(self, inter: discord.Interaction, channel: Optional[discord.TextChannel] = None):
        set_announce_channel(inter.guild_id, channel.id if channel else None)
        await inter.response.send_message(("Salon d'annonce défini: "+channel.mention) if channel else "Annonce auto désactivée.", ephemeral=True)

    @app_commands.command(name="set_inhouse_role", description="Définir le rôle ping d'annonce (inhouse).")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def set_inhouse_role_cmd(self, inter: discord.Interaction, role: Optional[discord.Role] = None):
        set_inhouse_role(inter.guild_id, role.id if role else None)
        await inter.response.send_message(("Rôle inhouse: "+role.mention) if role else "Rôle inhouse supprimé.", ephemeral=True)

    @app_commands.command(name="set_mod_role", description="Définir le rôle modérateur Inhouse.")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def set_mod_role_cmd(self, inter: discord.Interaction, role: Optional[discord.Role] = None):
        set_mod_role(inter.guild_id, role.id if role else None)
        await inter.response.send_message(("Rôle modérateur: "+role.mention) if role else "Rôle modérateur supprimé.", ephemeral=True)

    # ---------- Assistant de création (menus/inline) ----------
    @app_commands.command(name="lobby", description="Assistant de création de lobby (menus).")
    async def lobby_builder(self, interaction: discord.Interaction):
        # acquitter vite pour éviter 10062
        if not interaction.response.is_done():
            await interaction.response.defer(ephemeral=False)

        view = LobbyBuilderView(self)
        msg = await interaction.followup.send(content=view._render_content(), view=view, wait=True)
        view.msg_channel_id = msg.channel.id
        view.msg_id = msg.id

    async def _end_lobby(self, inter: Optional[discord.Interaction], lobby: Lobby, manual: bool, channel: Optional[discord.TextChannel] = None):
        if lobby.auto_end_task and not lobby.auto_end_task.done():
            lobby.auto_end_task.cancel()

        # fermer team builder si présent
        try:
            if lobby.team_builder_msg_id:
                ch = channel or (inter.channel if inter else None)
                if ch:
                    m = await ch.fetch_message(lobby.team_builder_msg_id)
                    await m.delete()
        except Exception:
            pass
        lobby.team_builder_msg_id = None

        # supprimer salons/catégorie d'équipes (salons d'abord)
        try:
            g = (inter.guild if inter else (channel.guild if channel else None))
            if g:
                await cleanup_team_channels(g, lobby)
        except Exception:
            pass

        ch = channel or (inter.channel if inter else None)
        if ch:
            try:
                msg = await ch.fetch_message(lobby.message_id)
                await msg.delete()
            except Exception:
                pass

        self.lobbies.pop(lobby.message_id, None)

        if inter:
            try: await inter.response.send_message("Lobby terminé ✅" if manual else "Lobby terminé automatiquement ⏲️", ephemeral=True)
            except Exception: pass
        elif ch:
            await ch.send("Lobby terminé automatiquement ⏲️")


# =========================================
#          BUILDER (menus inline)
# =========================================

class TitleModal(discord.ui.Modal, title="Titre du lobby"):
    def __init__(self, builder: "LobbyBuilderView", current: str):
        super().__init__()
        self.builder = builder
        self.input = discord.ui.TextInput(label="Titre", default=current, required=True, max_length=80)
        self.add_item(self.input)

    async def on_submit(self, interaction: discord.Interaction):
        self.builder.state_title = str(self.input.value).strip()
        await self.builder.refresh(interaction)

class SlotsModal(discord.ui.Modal, title="Configurer les slots (1–10)"):
    def __init__(self, builder: "LobbyBuilderView"):
        super().__init__()
        self.builder = builder
        self.inputs: dict[str, discord.ui.TextInput] = {}
        for role in ROLE_NAMES:
            field = discord.ui.TextInput(label=f"{role}", placeholder="1 à 10",
                                         default=str(self.builder.state_slots.get(role, 1)),
                                         max_length=2, required=True)
            self.inputs[role] = field
            self.add_item(field)

    async def on_submit(self, interaction: discord.Interaction):
        new_slots = {}
        for role, field in self.inputs.items():
            try:
                v = int(str(field.value).strip())
                if not (1 <= v <= 10): raise ValueError
            except Exception:
                if not interaction.response.is_done():
                    try: await interaction.response.defer()
                    except Exception: pass
                return
            new_slots[role] = v
        self.builder.state_slots = new_slots
        await self.builder.refresh(interaction)

class ModeSelect(discord.ui.Select):
    def __init__(self, builder: "LobbyBuilderView"):
        options = [discord.SelectOption(label=m) for m in ["5vs5","aram","4vs4","3vs3","2vs2","1vs1","arena","tft"]]
        super().__init__(placeholder="Choisis un mode…", min_values=1, max_values=1, options=options, row=1)
        self.builder = builder

    async def callback(self, interaction: discord.Interaction):
        self.builder.state_mode = self.values[0]
        await self.builder.refresh(interaction)

class ToggleButton(discord.ui.Button):
    def __init__(self, builder: "LobbyBuilderView", field: str, label_on: str, label_off: str, emoji: str, row: int):
        self.builder = builder; self.field = field
        self.label_on = label_on; self.label_off = label_off
        super().__init__(style=discord.ButtonStyle.secondary, label="...", emoji=emoji, row=row)
        self._sync_label()

    def _sync_label(self):
        self.label = (self.label_on if getattr(self.builder, self.field) else self.label_off)

    async def callback(self, interaction: discord.Interaction):
        setattr(self.builder, self.field, not getattr(self.builder, self.field))
        self._sync_label()
        await self.builder.refresh(interaction)

class RegenPwdButton(discord.ui.Button):
    def __init__(self, builder: "LobbyBuilderView"):
        super().__init__(style=discord.ButtonStyle.secondary, label="🔁 Regénérer MDP (4)", emoji="🔑", row=2)
        self.builder = builder

    async def callback(self, interaction: discord.Interaction):
        self.builder.state_pwd = gen_password4()
        await self.builder.refresh(interaction)

class ConfigureSlotsButton(discord.ui.Button):
    def __init__(self, builder: "LobbyBuilderView"):
        super().__init__(style=discord.ButtonStyle.secondary, label="Configurer les slots (5 rôles)", emoji="🎛️", row=0)
        self.builder = builder

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.send_modal(SlotsModal(self.builder))

class ConfirmCreateModal(discord.ui.Modal, title="Confirmer la création du lobby"):
    def __init__(self, builder: "LobbyBuilderView"):
        super().__init__(); self.builder = builder
        self.note = discord.ui.TextInput(label="Note (optionnel)", required=False, max_length=120, placeholder="Laisse vide si rien à ajouter")
        self.add_item(self.note)

    async def on_submit(self, interaction: discord.Interaction):
        b = self.builder
        if not b.state_title or not b.state_mode:
            if not interaction.response.is_done():
                try: await interaction.response.defer()
                except Exception: pass
            return
        role_slots = dict(b.state_slots); total = sum(role_slots.values())
        if total == 0:
            if not interaction.response.is_done():
                try: await interaction.response.defer()
                except Exception: pass
            return

        lobby = Lobby(interaction.guild_id, interaction.user.id, b.state_title, b.state_mode,
                      role_slots, password=b.state_pwd, close_when_full=True)
        view = LobbyView(b.cog, lobby, test_fill=b.state_test, show_finish=True)
        msg = await interaction.channel.send(embed=lobby.as_embed(), view=view)
        lobby.message_id = msg.id
        b.cog.lobbies[msg.id] = lobby

        ann = get_announce_channel(interaction.guild_id); inhouse = get_inhouse_role(interaction.guild_id)
        if ann:
            ch = interaction.guild.get_channel(ann)
            if isinstance(ch, discord.TextChannel):
                emb = discord.Embed(
                    title=f"[Annonce] {b.state_title}",
                    description=f"Mode **{b.state_mode}** — Slots **{total}**\n→ Rejoindre dans {interaction.channel.mention}",
                    color=MYG_ACCENT
                )
                content = (f"<@&{inhouse}> " if (b.state_ping and inhouse) else None)
                try: await ch.send(content=content, embed=emb)
                except Exception: pass

        async def _auto_end_job():
            import time
            lobby.auto_end_at = time.time() + b.state_auto_end * 60
            try:
                await asyncio.sleep(b.state_auto_end * 60)
            except asyncio.CancelledError:
                return
            await b.cog._end_lobby(None, lobby, manual=False, channel=interaction.channel)
        lobby.auto_end_task = asyncio.create_task(_auto_end_job())

        # supprime le message du builder
        try:
            if b.msg_channel_id and b.msg_id:
                ch = interaction.guild.get_channel(b.msg_channel_id)
                if isinstance(ch, discord.TextChannel):
                    m = await ch.fetch_message(b.msg_id)
                    await m.delete()
        except Exception:
            pass
        if not interaction.response.is_done():
            try: await interaction.response.defer()
            except Exception: pass

class CreateLobbyButton(discord.ui.Button):
    def __init__(self, builder: "LobbyBuilderView"):
        super().__init__(style=discord.ButtonStyle.success, label="Créer le lobby ✅", row=2)
        self.builder = builder

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.send_modal(ConfirmCreateModal(self.builder))

class SetTitleButton(discord.ui.Button):
    def __init__(self, builder: "LobbyBuilderView"):
        super().__init__(style=discord.ButtonStyle.primary, label="Définir le titre ✏️", row=0)
        self.builder = builder

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.send_modal(TitleModal(self.builder, self.builder.state_title or ""))

class AutoEndSelect(discord.ui.Select):
    def __init__(self, builder: "LobbyBuilderView"):
        options = [
            discord.SelectOption(label="60 min", value="60"),
            discord.SelectOption(label="120 min", value="120"),
            discord.SelectOption(label="180 min", value="180"),
            discord.SelectOption(label="300 min (défaut)", value="300", default=True),
            discord.SelectOption(label="480 min", value="480"),
        ]
        super().__init__(placeholder="Auto-end (minutes)", min_values=1, max_values=1, options=options, row=4)
        self.builder = builder

    async def callback(self, interaction: discord.Interaction):
        self.builder.state_auto_end = int(self.values[0])
        await self.builder.refresh(interaction)

class LobbyBuilderView(discord.ui.View):
    """Vue publique (un seul message) pour configurer un lobby avant création."""
    def __init__(self, cog: "Core"):
        super().__init__(timeout=600)
        self.cog = cog
        self.state_title: str | None = None
        self.state_mode: str | None = None
        self.state_slots: Dict[str, int] = {r: 1 for r in ROLE_NAMES}
        self.state_pwd: str = gen_password4()
        self.state_test: bool = False
        self.state_ping: bool = False
        self.state_auto_end: int = 300
        self.msg_channel_id: Optional[int] = None
        self.msg_id: Optional[int] = None

        self.add_item(SetTitleButton(self))
        self.add_item(ConfigureSlotsButton(self))
        self.add_item(ModeSelect(self))
        self.add_item(RegenPwdButton(self))
        self.add_item(CreateLobbyButton(self))
        self.add_item(ToggleButton(self, "state_test", "Test Fill: ON", "Test Fill: OFF", "🧪", row=3))
        self.add_item(ToggleButton(self, "state_ping", "Ping inhouse: ON", "Ping inhouse: OFF", "🔔", row=3))
        self.add_item(AutoEndSelect(self))

    def _render_content(self) -> str:
        return (
            "**Configurer ici ↓**\n\n"
            "**Création de lobby (assistant)**\n"
            f"• Titre: **{self.state_title or '—'}**\n"
            f"• Mode: **{self.state_mode or '—'}**\n"
            "• Slots: " + ", ".join(f"{r}:{self.state_slots[r]}" for r in ROLE_NAMES) + "\n"
            f"• MDP: `{self.state_pwd}` • Test: **{'ON' if self.state_test else 'OFF'}** "
            f"• Ping: **{'ON' if self.state_ping else 'OFF'}** • Auto-end: **{self.state_auto_end} min**\n"
            "• Le bouton **Close when full** sera disponible dans le lobby (modos uniquement)."
        )

    async def refresh(self, interaction: discord.Interaction):
        try:
            if not interaction.response.is_done():
                if getattr(interaction, "message", None) is not None:
                    await interaction.response.defer_update()
                else:
                    await interaction.response.defer()
        except Exception:
            pass

        if self.msg_channel_id and self.msg_id:
            try:
                ch = interaction.guild.get_channel(self.msg_channel_id)
                if isinstance(ch, discord.TextChannel):
                    msg = await ch.fetch_message(self.msg_id)
                    await msg.edit(content=self._render_content(), view=self)
            except Exception:
                pass


async def setup(bot: commands.Bot):
    await bot.add_cog(Core(bot))
