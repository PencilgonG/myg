# src/bot/cogs/core.py
import asyncio
import random
from dataclasses import dataclass, field
from typing import Dict, List, Optional

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


# =========================================================
#                    HELPERS LOCAUX
# =========================================================

async def safe_defer(interaction: discord.Interaction, ephemeral: bool = False) -> None:
    """Ack sans erreur. Si déjà ack: ne fait rien."""
    try:
        if not interaction.response.is_done():
            await interaction.response.defer(ephemeral=ephemeral)
    except Exception:
        pass

async def send_resp_or_followup(
    interaction: discord.Interaction,
    *,
    content: Optional[str] = None,
    embed: Optional[discord.Embed] = None,
    view: Optional[discord.ui.View] = None,
    ephemeral: bool = False
):
    """Envoie via response si libre, sinon followup. (n’envoie 'view' que si non-None)"""
    try:
        kwargs = {"ephemeral": ephemeral}
        if content is not None:
            kwargs["content"] = content
        if embed is not None:
            kwargs["embed"] = embed
        if view is not None:
            kwargs["view"] = view

        if not interaction.response.is_done():
            return await interaction.response.send_message(**kwargs)
        else:
            return await interaction.followup.send(**kwargs)
    except Exception:
        return None

def set_discord_name_safe(user_id: int, display_name: str) -> None:
    """Met à jour discord_name sans casser set_profile_fields si sa signature varie."""
    try:
        set_profile_fields(user_id, discord_name=display_name)
        return
    except TypeError:
        try:
            set_profile_fields(user_id, None, None, None, None, display_name)  # type: ignore
            return
        except Exception:
            pass
    except Exception:
        pass


# =========================================
#               DESIGN MYG
# =========================================

ROLE_NAMES = ["Top", "Jungle", "Mid", "ADC", "Support"]

MYG_COLOR   = 0xF1E0B0
MYG_DARK    = 0x111111
MYG_ACCENT  = 0xE85D5D

MYG_BANNER  = getattr(settings, "MYG_BANNER_URL", None)
MYG_LOGO    = getattr(settings, "MYG_LOGO_URL", None)

ROLE_ICON = {
    "Top":     "🛡️",
    "Jungle":  "🌿",
    "Mid":     "🧠",
    "ADC":     "🏹",
    "Support": "💉",
}

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
    alphabet = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
    return "".join(random.choice(alphabet) for _ in range(4))

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
    name_tag: Optional[str] = None

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

    # === Multi-équipes ===
    cap_ids: List[Optional[int]] = field(default_factory=list)  # capitaine par équipe
    team_ids: List[List[int]] = field(default_factory=list)     # membres par équipe

    # === Channels ===
    category_id: Optional[int] = None
    team_text_ids: List[Optional[int]] = field(default_factory=list)
    team_voice_ids: List[Optional[int]] = field(default_factory=list)

    # Message "Team Builder"
    team_builder_msg_id: Optional[int] = None

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

    def num_teams(self) -> int:
        """Nombre d'équipes = min des slots par rôle (>= 2 si possible)."""
        if not self.role_slots:
            return 2
        n = max(1, min(self.role_slots.values()))
        return max(2, n)

    def ensure_team_arrays(self):
        n = self.num_teams()
        # cap_ids
        if not self.cap_ids:
            self.cap_ids = [None for _ in range(n)]
        elif len(self.cap_ids) < n:
            self.cap_ids += [None] * (n - len(self.cap_ids))
        elif len(self.cap_ids) > n:
            self.cap_ids = self.cap_ids[:n]
        # team_ids
        if not self.team_ids:
            self.team_ids = [[] for _ in range(n)]
        elif len(self.team_ids) < n:
            self.team_ids += [[] for _ in range(n - len(self.team_ids))]
        elif len(self.team_ids) > n:
            self.team_ids = self.team_ids[:n]
        # channels arrays
        if not self.team_text_ids or len(self.team_text_ids) != n:
            self.team_text_ids = [None] * n
        if not self.team_voice_ids or len(self.team_voice_ids) != n:
            self.team_voice_ids = [None] * n

    def _format_player_line(self, p: Player) -> str:
        prof = get_profile(p.user_id)
        main_link, _ = build_links_from_profile(prof)

        lol_tag = p.name_tag or (prof.get("name_tag") if prof else None)
        if lol_tag:
            lol_text = f"**{lol_tag}**"
            lol_part = f"[{lol_text}]({main_link})" if main_link else lol_text
        else:
            lol_part = p.mention

        if prof and prof.get("discord_name"):
            discord_name = prof["discord_name"]
        else:
            discord_name = p.mention

        elo = prof.get("elo") if prof else None
        elo_part = f" · {elo}" if elo else ""

        return f"{lol_part} — ({discord_name}){elo_part}"

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
            await safe_defer(interaction, ephemeral=True)
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
        self.add_item(PickTeamsButton(self))

    async def update_lobby_message(self, interaction: discord.Interaction):
        await safe_defer(interaction, ephemeral=True)
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
            await safe_defer(interaction, ephemeral=True)
            return
        role = self.values[0]
        uid = interaction.user.id
        if uid in lobby.players or not lobby.has_free_slot(role):
            await safe_defer(interaction, ephemeral=True)
            return

        async def after_modal(inter: discord.Interaction, name_tag: str):
            lobby.subs.pop(uid, None)
            lobby.players[uid] = Player(uid, inter.user.mention, role=role, name_tag=name_tag)
            lobby.check_full_and_close()
            update_profile_join(uid, name_tag, as_sub=False)
            prof = get_profile(uid) or {}
            if not prof.get("discord_name"):
                set_discord_name_safe(uid, inter.user.display_name)
            await self.parent_view.update_lobby_message(inter)

        prof = get_profile(uid)
        await interaction.response.send_modal(NameTagModal(after_modal, preset=(prof.get("name_tag") if prof else None)))

class SubButton(discord.ui.Button):
    def __init__(self, parent_view: LobbyView):
        super().__init__(style=discord.ButtonStyle.secondary, label="Se mettre Sub", emoji="🧩")
        self.parent_view = parent_view

    async def callback(self, interaction: discord.Interaction):
        # ⚠️ NE PAS defer ici : on ouvre un modal en première réponse.
        lobby = self.parent_view.lobby; uid = interaction.user.id

        async def after_modal(inter: discord.Interaction, name_tag: str):
            lobby.players.pop(uid, None)
            lobby.subs[uid] = Player(uid, inter.user.mention, role=None, name_tag=name_tag)
            update_profile_join(uid, name_tag, as_sub=True)
            prof = get_profile(uid) or {}
            if not prof.get("discord_name"):
                set_discord_name_safe(uid, inter.user.display_name)
            await self.parent_view.update_lobby_message(inter)

        prof = get_profile(uid)
        await interaction.response.send_modal(NameTagModal(after_modal, preset=(prof.get("name_tag") if prof else None)))

class QuitButton(discord.ui.Button):
    def __init__(self, parent_view: LobbyView):
        super().__init__(style=discord.ButtonStyle.danger, label="Quitter", emoji="🚪")
        self.parent_view = parent_view

    async def callback(self, interaction: discord.Interaction):
        await safe_defer(interaction, ephemeral=True)
        lobby = self.parent_view.lobby; uid = interaction.user.id
        removed = False
        if uid in lobby.players: lobby.players.pop(uid); removed = True
        if uid in lobby.subs: lobby.subs.pop(uid); removed = True
        if not removed:
            return
        lobby.closed = False
        await self.parent_view.update_lobby_message(interaction)

class FinishButton(discord.ui.Button):
    def __init__(self, parent_view: LobbyView):
        super().__init__(style=discord.ButtonStyle.primary, label="Terminer", emoji="✅")
        self.parent_view = parent_view

    async def callback(self, interaction: discord.Interaction):
        await safe_defer(interaction, ephemeral=True)
        lobby = self.parent_view.lobby
        if interaction.user.id != lobby.owner_id and not interaction.user.guild_permissions.manage_guild:
            return
        await self.parent_view.cog._end_lobby(interaction, lobby, manual=True)

class TestFillButton(discord.ui.Button):
    def __init__(self, parent_view: LobbyView):
        super().__init__(style=discord.ButtonStyle.success, label="Test Fill (10)", emoji="🧪")
        self.parent_view = parent_view

    async def callback(self, interaction: discord.Interaction):
        await safe_defer(interaction, ephemeral=True)
        lobby = self.parent_view.lobby
        if interaction.user.id != lobby.owner_id and not interaction.user.guild_permissions.manage_guild:
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
    """Crée 1 catégorie + (texte+vocal) * par équipe = num_teams()."""
    lobby.ensure_team_arrays()

    if lobby.category_id:
        return

    category = await guild.create_category(f"Inhouse – {title}")
    lobby.category_id = category.id

    deny_everyone = {guild.default_role: discord.PermissionOverwrite(view_channel=False, connect=False, send_messages=False)}

    # Prépare overwrites staff (mod role)
    mod_role_id = get_mod_role(guild.id)
    mod_role = guild.get_role(mod_role_id) if mod_role_id else None

    for idx in range(lobby.num_teams()):
        # Crée les channels
        text = await guild.create_text_channel(f"team-{idx+1}-chat", category=category, overwrites=deny_everyone)
        vc   = await guild.create_voice_channel(f"Team {idx+1}", category=category, overwrites=deny_everyone)
        lobby.team_text_ids[idx] = text.id
        lobby.team_voice_ids[idx] = vc.id

        # Bâtit les overwrites spécifiques à l'équipe
        ow = {guild.default_role: discord.PermissionOverwrite(view_channel=False, send_messages=False, connect=False)}
        if mod_role:
            ow[mod_role] = discord.PermissionOverwrite(view_channel=True, send_messages=True, connect=True, manage_channels=True)

        members = set(lobby.team_ids[idx])
        if lobby.cap_ids[idx]:
            members.add(lobby.cap_ids[idx])  # type: ignore[arg-type]

        for uid in members:
            m = guild.get_member(uid)
            if m:
                ow[m] = discord.PermissionOverwrite(view_channel=True, send_messages=True, connect=True)

        await text.edit(overwrites=ow)
        await vc.edit(overwrites=ow)

async def cleanup_team_channels(guild: discord.Guild, lobby: Lobby):
    """Supprime tous les channels et la catégorie du lobby."""
    try:
        for chan_id in list(lobby.team_text_ids) + list(lobby.team_voice_ids):
            try:
                if chan_id:
                    ch = guild.get_channel(chan_id)
                    if ch:
                        await ch.delete()
            except Exception:
                pass
        if lobby.category_id:
            cat = guild.get_channel(lobby.category_id)
            if isinstance(cat, discord.CategoryChannel):
                await cat.delete()
    except Exception:
        pass

    lobby.category_id = None
    lobby.team_text_ids = [None] * lobby.num_teams()
    lobby.team_voice_ids = [None] * lobby.num_teams()


# =========================================
#           TEAM BUILDER (multi-équipes)
# =========================================

class PickTeamsButton(discord.ui.Button):
    def __init__(self, parent_view: LobbyView):
        super().__init__(style=discord.ButtonStyle.secondary, label="Pick teams (multi)", emoji="🧿")
        self.parent_view = parent_view

    async def callback(self, interaction: discord.Interaction):
        await safe_defer(interaction, ephemeral=True)
        lobby = self.parent_view.lobby
        if not _is_inhouse_mod_or_owner(interaction, lobby):
            return

        lobby.ensure_team_arrays()
        view = TeamBuilderView(self.parent_view.cog, lobby, page=0)
        embed = view.render_embed(interaction.guild)

        if lobby.team_builder_msg_id:
            try:
                msg = await interaction.channel.fetch_message(lobby.team_builder_msg_id)
                await msg.edit(embed=embed, view=view)
            except Exception:
                lobby.team_builder_msg_id = None

        if not lobby.team_builder_msg_id:
            msg = await interaction.channel.send(embed=embed, view=view)
            lobby.team_builder_msg_id = msg.id


class TeamBuilderView(discord.ui.View):
    """Affiche 2 équipes par page : pour chaque équipe -> 2 Select (Capitaine, Membres) répartis sur 4 lignes."""
    PAGE_SIZE = 2  # 2 équipes affichées par page (chaque équipe occupe 2 rows: cap, membres)

    def __init__(self, cog: "Core", lobby: Lobby, page: int = 0):
        super().__init__(timeout=600)
        self.cog = cog
        self.lobby = lobby
        self.page = page

        self.lobby.ensure_team_arrays()
        self.num_teams = self.lobby.num_teams()

        # Ajoute 1 bloc (capitaine / membres) par équipe – 2 rows par équipe
        start = self.page * self.PAGE_SIZE
        end = min(start + self.PAGE_SIZE, self.num_teams)

        base_row = 0
        for gidx in range(start, end):
            # Capitaine en row base_row, Membres en row base_row+1
            self.add_item(TeamCaptainSelect(self, team_index=gidx, row=base_row))
            self.add_item(TeamAddMembersSelect(self, team_index=gidx, row=base_row + 1))
            base_row += 2  # on consomme 2 lignes par équipe (0/1 puis 2/3)

        # Pagination (row 4 avec les actions)
        self.add_item(PrevPageButton(self))
        self.add_item(NextPageButton(self))

        # Actions
        self.add_item(ResetTeamsButton(self, row=4))
        self.add_item(ValidateTeamsButton(self, row=4))
        self.add_item(CloseTeamBuilderButton(self, row=4))

    def _name_for(self, guild: discord.Guild, uid: int | None) -> str:
        if not uid:
            return "—"
        m = guild.get_member(uid)
        return m.mention if m else f"<@{uid}>"

    def _lines_for_ids(self, guild: discord.Guild, ids: List[int]) -> str:
        if not ids:
            return "—"
        out = []
        for uid in ids:
            p = self.lobby.players.get(uid) or self.lobby.subs.get(uid) or Player(uid, f"<@{uid}>")
            out.append(f"• {self.lobby._format_player_line(p)}")
        return "\n".join(out)

    def _pool_ids(self) -> List[int]:
        """Tous les joueurs inscrits, moins tous les capitaines et les membres d'équipe."""
        all_ids = set(self.lobby.players.keys())
        taken = set()
        for c in self.lobby.cap_ids:
            if c:
                taken.add(c)
        for arr in self.lobby.team_ids:
            taken.update(arr)
        return [uid for uid in all_ids if uid not in taken]

    def render_embed(self, guild: discord.Guild) -> discord.Embed:
        emb = discord.Embed(title="Team Builder", color=MYG_DARK)
        if MYG_BANNER: emb.set_image(url=MYG_BANNER)
        if MYG_LOGO:   emb.set_thumbnail(url=MYG_LOGO)

        start = self.page * self.PAGE_SIZE
        end = min(start + self.PAGE_SIZE, self.num_teams)

        for gidx in range(start, end):
            cap = self.lobby.cap_ids[gidx]
            members = self.lobby.team_ids[gidx]
            team_no = gidx + 1
            emb.add_field(name=f"Capitaine — Équipe {team_no}", value=self._name_for(guild, cap), inline=True)
            emb.add_field(name=f"Membres — Équipe {team_no}",   value=self._lines_for_ids(guild, members), inline=True)
            emb.add_field(name="\u200b", value="\u200b", inline=True)

        pool = [self._name_for(guild, uid) for uid in self._pool_ids()]
        emb.add_field(name="Joueurs disponibles", value="\n".join(pool) or "—", inline=False)

        total_pages = (self.num_teams + self.PAGE_SIZE - 1) // self.PAGE_SIZE
        emb.set_footer(text=f"Page {self.page+1}/{total_pages} • Sélectionne capitaines & membres puis Valider.")
        return emb

    async def _edit_self(self, interaction: discord.Interaction):
        await safe_defer(interaction, ephemeral=True)
        try:
            msg = await interaction.channel.fetch_message(self.lobby.team_builder_msg_id)
            await msg.edit(embed=self.render_embed(interaction.guild), view=self)
        except Exception:
            pass


class PrevPageButton(discord.ui.Button):
    def __init__(self, parent: TeamBuilderView):
        super().__init__(style=discord.ButtonStyle.secondary, label="◀️ Page -", row=4)
        self.parent = parent

    async def callback(self, interaction: discord.Interaction):
        await safe_defer(interaction, ephemeral=True)
        if self.parent.page <= 0:
            return
        new_view = TeamBuilderView(self.parent.cog, self.parent.lobby, page=self.parent.page - 1)
        try:
            msg = await interaction.channel.fetch_message(self.parent.lobby.team_builder_msg_id)
            await msg.edit(embed=new_view.render_embed(interaction.guild), view=new_view)
        except Exception:
            pass


class NextPageButton(discord.ui.Button):
    def __init__(self, parent: TeamBuilderView):
        super().__init__(style=discord.ButtonStyle.secondary, label="Page + ▶️", row=4)
        self.parent = parent

    async def callback(self, interaction: discord.Interaction):
        await safe_defer(interaction, ephemeral=True)
        total_pages = (self.parent.num_teams + self.parent.PAGE_SIZE - 1) // self.parent.PAGE_SIZE
        if self.parent.page + 1 >= total_pages:
            return
        new_view = TeamBuilderView(self.parent.cog, self.parent.lobby, page=self.parent.page + 1)
        try:
            msg = await interaction.channel.fetch_message(self.parent.lobby.team_builder_msg_id)
            await msg.edit(embed=new_view.render_embed(interaction.guild), view=new_view)
        except Exception:
            pass


class TeamCaptainSelect(discord.ui.Select):
    def __init__(self, parent: TeamBuilderView, team_index: int, row: int = 0):
        self.parent = parent
        self.team_index = team_index  # index global
        # Options = "(aucun)" + tous les joueurs de la pool
        opts = [discord.SelectOption(label="(aucun)", value="0", default=(self.parent.lobby.cap_ids[team_index] is None))]
        for uid in parent._pool_ids():
            opts.append(discord.SelectOption(label=str(uid), value=str(uid)))
        team_no = team_index + 1
        super().__init__(placeholder=f"Capitaine — Équipe {team_no}", min_values=1, max_values=1, options=opts, row=row)

    async def callback(self, interaction: discord.Interaction):
        if not _is_inhouse_mod_or_owner(interaction, self.parent.lobby):
            return await self.parent._edit_self(interaction)
        v = int(self.values[0])
        caps = self.parent.lobby.cap_ids
        # définir/remplacer le capitaine de cette team
        caps[self.team_index] = None if v == 0 else v
        # s’assurer qu’un capitaine n’est pas ailleurs
        if v != 0:
            for i, c in enumerate(caps):
                if i != self.team_index and c == v:
                    caps[i] = None
            # retirer des membres d’équipe s’il était dedans
            for arr in self.parent.lobby.team_ids:
                if v in arr:
                    arr.remove(v)
        await self.parent._edit_self(interaction)


class TeamAddMembersSelect(discord.ui.Select):
    def __init__(self, parent: TeamBuilderView, team_index: int, row: int = 1):
        self.parent = parent
        self.team_index = team_index  # index global
        pool = parent._pool_ids()

        team_no = team_index + 1
        if pool:
            opts = [discord.SelectOption(label=str(uid), value=str(uid)) for uid in pool]
            maxv = min(10, len(opts))
            super().__init__(placeholder=f"Ajouter → Équipe {team_no}", min_values=0, max_values=maxv, options=opts, row=row)
        else:
            super().__init__(placeholder="Aucun joueur disponible", min_values=0, max_values=1,
                             options=[discord.SelectOption(label="—", value="none")], row=row)
            self.disabled = True

    async def callback(self, interaction: discord.Interaction):
        if self.disabled or not self.values or self.values == ["none"]:
            return await self.parent._edit_self(interaction)
        if not _is_inhouse_mod_or_owner(interaction, self.parent.lobby):
            return await self.parent._edit_self(interaction)

        ids = [int(x) for x in self.values]
        team_lists = self.parent.lobby.team_ids
        # retirer des autres équipes et des capitaines, puis ajouter à la présente
        for u in ids:
            for arr in team_lists:
                if u in arr:
                    arr.remove(u)
            caps = self.parent.lobby.cap_ids
            for i, c in enumerate(caps):
                if c == u:
                    caps[i] = None
            if u not in team_lists[self.team_index]:
                team_lists[self.team_index].append(u)
        await self.parent._edit_self(interaction)


class ResetTeamsButton(discord.ui.Button):
    def __init__(self, parent: TeamBuilderView, row: int = 4):
        super().__init__(style=discord.ButtonStyle.secondary, label="Reset", emoji="♻️", row=row)
        self.parent = parent

    async def callback(self, interaction: discord.Interaction):
        if not _is_inhouse_mod_or_owner(interaction, self.parent.lobby):
            return await self.parent._edit_self(interaction)
        self.parent.lobby.ensure_team_arrays()
        for i in range(self.parent.lobby.num_teams()):
            self.parent.lobby.cap_ids[i] = None
            self.parent.lobby.team_ids[i].clear()
        await self.parent._edit_self(interaction)


class WinnerPromptView(discord.ui.View):
    def __init__(self, on_pick):
        super().__init__(timeout=120)
        self.on_pick = on_pick

    @discord.ui.button(label="Équipe 1 a gagné", style=discord.ButtonStyle.primary, emoji="🔵")
    async def team1_win(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.on_pick(interaction, 0)

    @discord.ui.button(label="Équipe 2 a gagné", style=discord.ButtonStyle.danger, emoji="🔴")
    async def team2_win(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.on_pick(interaction, 1)

    @discord.ui.button(label="Plus tard", style=discord.ButtonStyle.secondary, emoji="⏭️")
    async def later(self, interaction: discord.Interaction, button: discord.ui.Button):
        await send_resp_or_followup(interaction, content="Ok, enregistrement ignoré pour l’instant.", ephemeral=True)
        self.stop()


class ValidateTeamsButton(discord.ui.Button):
    def __init__(self, parent: "TeamBuilderView", row: int = 4):
        super().__init__(style=discord.ButtonStyle.success, label="Valider", emoji="✅", row=row)
        self.parent = parent

    async def callback(self, interaction: discord.Interaction):
        lob = self.parent.lobby
        if not _is_inhouse_mod_or_owner(interaction, lob):
            return await self.parent._edit_self(interaction)

        lob.ensure_team_arrays()

        # Création des salons pour toutes les équipes
        await create_team_channels(interaction.guild, lob, lob.title)

        # Embed récapitulatif
        final = build_final_teams_embed(interaction.guild, lob)
        await interaction.channel.send(embed=final)

        # Envoi du lien prodraft aux paires (1v2, 3v4, ...)
        try:
            for t in range(0, lob.num_teams(), 2):
                if t + 1 >= lob.num_teams():
                    break  # impaire (sécurité)
                pick_side = random.choice([t, t + 1])
                target_text_id = lob.team_text_ids[pick_side]
                cap_id = lob.cap_ids[pick_side]
                ch = interaction.guild.get_channel(target_text_id) if target_text_id else None
                if isinstance(ch, discord.TextChannel):
                    at = f"<@{cap_id}>" if cap_id else ""
                    await ch.send(
                        f"{at} Utilise ce lien pour créer la draft et partager au capitaine adverse "
                        f"(et le lien spec dans le salon LoL) : http://prodraft.leagueoflegends.com/"
                    )
        except Exception:
            pass

        # Si 2 équipes seulement -> prompt gagnant + record en DB
        if lob.num_teams() == 2:
            async def on_pick(inter: discord.Interaction, winner_idx: int):
                # Map roles connus
                role_map = {}
                for uid, pl in lob.players.items():
                    for arr in lob.team_ids:
                        if uid in arr:
                            if pl.role:
                                role_map[uid] = pl.role
                # équipes
                team1_ids = list(lob.team_ids[0]) + ([lob.cap_ids[0]] if lob.cap_ids[0] else [])
                team2_ids = list(lob.team_ids[1]) + ([lob.cap_ids[1]] if lob.cap_ids[1] else [])
                winner = "blue" if winner_idx == 0 else "red"
                match_id = record_match(
                    guild_id=inter.guild_id,
                    mode=lob.mode,
                    blue_ids=team1_ids,
                    red_ids=team2_ids,
                    winner=winner,
                    role_map=role_map
                )
                emb = discord.Embed(
                    title=f"Match #{match_id} enregistré",
                    description=f"Gagnant: **{'Équipe 1 🔵' if winner_idx==0 else 'Équipe 2 🔴'}** · Mode **{lob.mode}**",
                    color=discord.Color.green()
                )
                await send_resp_or_followup(inter, embed=emb, ephemeral=False)

                try:
                    await cleanup_team_channels(inter.guild, lob)
                except Exception:
                    pass

            view = WinnerPromptView(on_pick)
            await send_resp_or_followup(interaction, content="Qui a gagné cette inhouse ?", view=view, ephemeral=True)

        # Nettoie le message Team Builder
        try:
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
        await safe_defer(interaction, ephemeral=True)
        if not _is_inhouse_mod_or_owner(interaction, self.parent.lobby):
            return await self.parent._edit_self(interaction)
        try:
            if self.parent.lobby.team_builder_msg_id:
                msg = await interaction.channel.fetch_message(self.parent.lobby.team_builder_msg_id)
                await msg.delete()
        except Exception:
            pass
        self.parent.lobby.team_builder_msg_id = None


def build_final_teams_embed(guild: discord.Guild, lobby: Lobby) -> discord.Embed:
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

    for i in range(lobby.num_teams()):
        cap = f"**Capitaine :** <@{lobby.cap_ids[i]}>" if lobby.cap_ids[i] else "—"
        members = fmt(lobby.team_ids[i])
        emb.add_field(name=f"Équipe {i+1}", value=f"{cap}\n\n{members}", inline=(i % 2 == 0))

        # pour mise en page en 2 colonnes, on ajoute une colonne vide après les paires
        if i % 2 == 1:
            emb.add_field(name="\u200b", value="\u200b", inline=True)

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
        init_db_stats()
        if getattr(settings, "GUILD_ID_TEST", None):
            guild = discord.Object(id=settings.GUILD_ID_TEST)
            self.bot.tree.copy_global_to(guild=guild)

    @app_commands.command(name="set_announce_channel", description="Définir le salon d'annonce.")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def set_announce_channel_cmd(self, inter: discord.Interaction, channel: Optional[discord.TextChannel] = None):
        set_announce_channel(inter.guild_id, channel.id if channel else None)
        await send_resp_or_followup(inter, content=("Salon d'annonce défini: "+channel.mention) if channel else "Annonce auto désactivée.", ephemeral=True)

    @app_commands.command(name="set_inhouse_role", description="Définir le rôle ping d'annonce (inhouse).")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def set_inhouse_role_cmd(self, inter: discord.Interaction, role: Optional[discord.Role] = None):
        set_inhouse_role(inter.guild_id, role.id if role else None)
        await send_resp_or_followup(inter, content=("Rôle inhouse: "+role.mention) if role else "Rôle inhouse supprimé.", ephemeral=True)

    @app_commands.command(name="set_mod_role", description="Définir le rôle modérateur Inhouse.")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def set_mod_role_cmd(self, inter: discord.Interaction, role: Optional[discord.Role] = None):
        set_mod_role(inter.guild_id, role.id if role else None)
        await send_resp_or_followup(inter, content=("Rôle modérateur: "+role.mention) if role else "Rôle modérateur supprimé.", ephemeral=True)

    @app_commands.command(name="custom", description="S'auto-assigner ou retirer le rôle 'custom'.")
    async def custom_role_cmd(self, inter: discord.Interaction):
        await safe_defer(inter, ephemeral=True)
        guild = inter.guild
        if not guild:
            return
        role = discord.utils.get(guild.roles, name="custom")
        if role is None:
            try:
                role = await guild.create_role(name="custom", mentionable=True, reason="MYG: auto-assign role")
            except Exception as e:
                return await send_resp_or_followup(inter, content=f"Impossible de créer le rôle : {e}", ephemeral=True)

        member = guild.get_member(inter.user.id)
        if not member:
            return
        try:
            if role in member.roles:
                await member.remove_roles(role, reason="MYG: toggle custom off")
                await send_resp_or_followup(inter, content="Rôle **custom** retiré.", ephemeral=True)
            else:
                await member.add_roles(role, reason="MYG: toggle custom on")
                await send_resp_or_followup(inter, content="Rôle **custom** ajouté.", ephemeral=True)
        except Exception as e:
            await send_resp_or_followup(inter, content=f"Erreur: {e}", ephemeral=True)

    @app_commands.command(name="lobby", description="Assistant de création de lobby (menus).")
    async def lobby_builder(self, interaction: discord.Interaction):
        await safe_defer(interaction, ephemeral=False)
        view = LobbyBuilderView(self)
        msg = await interaction.followup.send(embed=view._render_embed(), view=view)
        view.msg_channel_id = msg.channel.id
        view.msg_id = msg.id

    async def _end_lobby(self, inter: Optional[discord.Interaction], lobby: Lobby, manual: bool, channel: Optional[discord.TextChannel] = None):
        # Supprime le Team Builder s'il existe
        try:
            if lobby.team_builder_msg_id:
                ch = channel or (inter.channel if inter else None)  # type: ignore
                if ch:
                    m = await ch.fetch_message(lobby.team_builder_msg_id)
                    await m.delete()
        except Exception:
            pass
        lobby.team_builder_msg_id = None

        # Supprime les salons
        try:
            g = (inter.guild if inter else (channel.guild if channel else None))  # type: ignore
            if g:
                await cleanup_team_channels(g, lobby)
        except Exception:
            pass

        # Supprime le message principal du lobby
        ch = channel or (inter.channel if inter else None)  # type: ignore
        if ch:
            try:
                msg = await ch.fetch_message(lobby.message_id)
                await msg.delete()
            except Exception:
                pass

        self.lobbies.pop(lobby.message_id, None)

        if inter:
            await send_resp_or_followup(inter, content="Lobby terminé ✅", ephemeral=True)
        elif ch:
            await ch.send("Lobby terminé")


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
                await safe_defer(interaction, ephemeral=True)
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
        await safe_defer(interaction, ephemeral=True)
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
        await safe_defer(interaction, ephemeral=True)
        setattr(self.builder, self.field, not getattr(self.builder, self.field))
        self._sync_label()
        await self.builder.refresh(interaction)

class RegenPwdButton(discord.ui.Button):
    def __init__(self, builder: "LobbyBuilderView"):
        super().__init__(style=discord.ButtonStyle.secondary, label="🔁 Regénérer MDP (4)", emoji="🔑", row=2)
        self.builder = builder

    async def callback(self, interaction: discord.Interaction):
        await safe_defer(interaction, ephemeral=True)
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
            await safe_defer(interaction, ephemeral=True)
            return
        role_slots = dict(b.state_slots); total = sum(role_slots.values())
        if total == 0:
            await safe_defer(interaction, ephemeral=True)
            return

        lobby = Lobby(interaction.guild_id, interaction.user.id, b.state_title, b.state_mode,
                      role_slots, password=b.state_pwd, close_when_full=True)
        lobby.ensure_team_arrays()
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

        try:
            if b.msg_channel_id and b.msg_id:
                ch = interaction.guild.get_channel(b.msg_channel_id)
                if isinstance(ch, discord.TextChannel):
                    m = await ch.fetch_message(b.msg_id)
                    await m.delete()
        except Exception:
            pass
        await safe_defer(interaction, ephemeral=True)

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

class LobbyBuilderView(discord.ui.View):
    def __init__(self, cog: "Core"):
        super().__init__(timeout=600)
        self.cog = cog
        self.state_title: str | None = None
        self.state_mode: str | None = None
        self.state_slots: dict[str, int] = {r: 1 for r in ROLE_NAMES}
        self.state_pwd: str = gen_password4()
        self.state_test: bool = False
        self.state_ping: bool = False
        self.msg_channel_id: int | None = None
        self.msg_id: int | None = None

        self.add_item(SetTitleButton(self))
        self.add_item(ConfigureSlotsButton(self))
        self.add_item(ModeSelect(self))
        self.add_item(RegenPwdButton(self))
        self.add_item(ToggleButton(self, field="state_test", label_on="Test: ON", label_off="Test: OFF", emoji="🧪", row=3))
        self.add_item(ToggleButton(self, field="state_ping", label_on="Ping: ON", label_off="Ping: OFF", emoji="🔔", row=3))
        self.add_item(CreateLobbyButton(self))

    def _render_embed(self) -> discord.Embed:
        emb = discord.Embed(
            title=self.state_title or "myg inhouse",
            description=f"Inhouse **{self.state_mode or '—'}** · MDP : {'`***`' if self.state_pwd else '—'}",
            color=MYG_DARK
        )
        if MYG_BANNER:
            emb.set_image(url=MYG_BANNER)
        if MYG_LOGO:
            emb.set_thumbnail(url=MYG_LOGO)

        total_slots = sum(self.state_slots.values())
        emb.add_field(name="État", value="Préparation", inline=True)
        emb.add_field(name="Slots", value=f"0/{total_slots}", inline=True)
        emb.add_field(name="\u200b", value="\u200b", inline=True)

        left, right = [], []
        for i, r in enumerate(ROLE_NAMES):
            qty = self.state_slots.get(r, 0)
            lines = [f"{ROLE_ICON.get(r, '🎮')} *libre*" for _ in range(qty)]
            block = "\n".join(lines) if lines else "*—*"
            if i < 3:
                left.append(f"**{r}**\n{block}")
            else:
                right.append(f"**{r}**\n{block}")

        emb.add_field(name="Équipe A", value="\n\n".join(left) or "*—*", inline=True)
        emb.add_field(name="Équipe B", value="\n\n".join(right) or "*—*", inline=True)
        emb.add_field(name="Remplaçants", value="*—*", inline=False)
        return emb

    async def refresh(self, interaction: discord.Interaction) -> None:
        await safe_defer(interaction, ephemeral=True)
        if self.msg_channel_id and self.msg_id:
            try:
                ch = interaction.guild.get_channel(self.msg_channel_id)  # type: ignore
                if isinstance(ch, discord.TextChannel):
                    msg = await ch.fetch_message(self.msg_id)
                    await msg.edit(embed=self._render_embed(), view=self)
            except Exception:
                pass


async def setup(bot: commands.Bot):
    await bot.add_cog(Core(bot))
