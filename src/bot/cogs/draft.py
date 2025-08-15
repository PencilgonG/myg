
# src/bot/cogs/draft.py
import asyncio
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional

import discord
from discord import app_commands
from discord.ext import commands

from bot.helpers import safe_defer, first_response_or_followup
from bot.store import get_profile

# Helpers repris (liens depuis profil)
def parse_region_from_tag(name_tag: str | None) -> str | None:
    if not name_tag or "#" not in name_tag:
        return None
    _, tag = name_tag.rsplit("#", 1)
    tag = tag.strip().lower()
    m = {
        "euw": "euw", "euw1": "euw", "eune": "eune", "eun1": "eune",
        "na": "na", "na1": "na", "kr": "kr", "br": "br", "br1": "br",
        "lan": "lan", "las": "las", "oce": "oce", "oc1": "oce",
        "tr": "tr", "ru": "ru", "jp": "jp",
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

# ================== Draft models ==================

class DraftMode(str, Enum):
    normal = "normal"
    fearless = "fearless"
    hardfearless = "hardfearless"

@dataclass
class DraftState:
    guild_id: int
    channel_id: int
    lobby_message_id: int
    mode: DraftMode
    team_a_name: str = "Team A"
    team_b_name: str = "Team B"
    captain_a_id: int = 0
    captain_b_id: int = 0
    order: List[str] = field(default_factory=list)  # "A"/"B"
    remaining_user_ids: List[int] = field(default_factory=list)
    team_a: List[int] = field(default_factory=list)
    team_b: List[int] = field(default_factory=list)
    current_index: int = 0
    finished: bool = False

    @property
    def current_side(self) -> str:
        if self.current_index < len(self.order):
            return self.order[self.current_index]
        return "A"

    def pick(self, user_id: int) -> None:
        side = self.current_side
        if side == "A":
            self.team_a.append(user_id)
        else:
            self.team_b.append(user_id)
        self.remaining_user_ids = [u for u in self.remaining_user_ids if u != user_id]
        self.current_index += 1
        if self.current_index >= len(self.order):
            self.finished = True

# ================== View / UI ==================

class PickSelect(discord.ui.Select):
    def __init__(self, parent_view: "DraftView", options: List[discord.SelectOption]):
        super().__init__(min_values=1, max_values=1, options=options, placeholder="Choisir un joueur à drafter…")
        self.parent_view = parent_view

    async def callback(self, interaction: discord.Interaction):
        state = self.parent_view.state
        expected_captain = state.captain_a_id if state.current_side == "A" else state.captain_b_id

        # Garde-fous (messages éphémères sûrs)
        if interaction.user.id != expected_captain:
            await first_response_or_followup(interaction, content="Ce n'est pas ton tour de choisir.", ephemeral=True)
            return

        raw = self.values[0]
        if raw == "none":
            await first_response_or_followup(interaction, content="Aucun joueur sélectionnable pour le moment.", ephemeral=True)
            return

        try:
            picked_user_id = int(raw.split(":")[1])
        except Exception:
            await first_response_or_followup(interaction, content="Sélection invalide.", ephemeral=True)
            return

        if picked_user_id not in state.remaining_user_ids:
            await first_response_or_followup(interaction, content="Joueur déjà pris.", ephemeral=True)
            return

        state.pick(picked_user_id)
        await self.parent_view.refresh(interaction)

class UndoButton(discord.ui.Button):
    def __init__(self, parent_view: "DraftView"):
        super().__init__(style=discord.ButtonStyle.secondary, label="Annuler le dernier pick", emoji="↩️")
        self.parent_view = parent_view

    async def callback(self, interaction: discord.Interaction):
        state = self.parent_view.state
        if interaction.user.id not in {state.captain_a_id, state.captain_b_id, self.parent_view.author_id}:
            await first_response_or_followup(interaction, content="Action réservée aux capitaines.", ephemeral=True)
            return

        if state.current_index == 0:
            await first_response_or_followup(interaction, content="Rien à annuler.", ephemeral=True)
            return

        state.current_index -= 1
        side = state.order[state.current_index]
        if side == "A":
            if not state.team_a:
                await first_response_or_followup(interaction, content="Rien à annuler.", ephemeral=True)
                return
            uid = state.team_a.pop()
        else:
            if not state.team_b:
                await first_response_or_followup(interaction, content="Rien à annuler.", ephemeral=True)
                return
            uid = state.team_b.pop()
        state.finished = False
        if uid not in state.remaining_user_ids:
            state.remaining_user_ids.append(uid)
        await self.parent_view.refresh(interaction)

class FinishButton(discord.ui.Button):
    def __init__(self, parent_view: "DraftView"):
        super().__init__(style=discord.ButtonStyle.success, label="Terminer la draft", emoji="✅")
        self.parent_view = parent_view

    async def callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.parent_view.author_id:
            await first_response_or_followup(interaction, content="Réservé à l'initiateur de la draft.", ephemeral=True)
            return
        self.parent_view.state.finished = True
        await self.parent_view.refresh(interaction)

class CancelButton(discord.ui.Button):
    def __init__(self, parent_view: "DraftView"):
        super().__init__(style=discord.ButtonStyle.danger, label="Annuler", emoji="🛑")
        self.parent_view = parent_view

    async def callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.parent_view.author_id:
            await first_response_or_followup(interaction, content="Réservé à l'initiateur de la draft.", ephemeral=True)
            return
        await self.parent_view.on_cancel(interaction)

class DraftView(discord.ui.View):
    def __init__(self, state: DraftState, pool_labels: Dict[int, str], author_id: int):
        super().__init__(timeout=None)
        self.state = state
        self.pool_labels = pool_labels
        self.author_id = author_id

        self.select = PickSelect(self, self._make_options())
        self.add_item(self.select)

        self.add_item(UndoButton(self))
        self.add_item(FinishButton(self))
        self.add_item(CancelButton(self))

    def _make_options(self) -> List[discord.SelectOption]:
        opts: List[discord.SelectOption] = []
        for uid in sorted(self.state.remaining_user_ids):
            label = self.pool_labels.get(uid, f"User#{uid}")
            opts.append(discord.SelectOption(label=label, value=f"user:{uid}"))
        if not opts:
            opts = [discord.SelectOption(label="Aucun joueur restant", value="none", default=True)]
        return opts

    async def refresh(self, interaction: discord.Interaction):
        # Toujours acquitter puis éditer => aucune bannière rouge
        await safe_defer(interaction, update=True)

        self.clear_items()
        self.select = PickSelect(self, self._make_options())
        self.select.disabled = self.state.finished or not self.state.remaining_user_ids
        self.add_item(self.select)
        self.add_item(UndoButton(self))
        self.add_item(FinishButton(self))
        self.add_item(CancelButton(self))

        embed = await self._make_embed(interaction.client)
        try:
            if getattr(interaction, "message", None) is not None:
                await interaction.message.edit(embed=embed, view=self)
            else:
                # Fallback extrême (rare)
                ch = interaction.channel
                if ch:
                    await ch.send(embed=embed, view=self)
        except Exception:
            pass

    async def _make_embed(self, bot: commands.Bot) -> discord.Embed:
        state = self.state
        emb = discord.Embed(
            title=f"Draft — {state.team_a_name} vs {state.team_b_name} ({state.mode})",
            color=discord.Color.purple(),
        )

        def fmt_user(uid: int) -> str:
            prof = get_profile(uid)
            nt = prof.get("name_tag") if prof else None
            main_link, _ = build_links_from_profile(prof)
            text = nt or f"<@{uid}>"
            if main_link:
                text = f"[{text}]({main_link})"
            return text

        team_a_lines = [f"• {fmt_user(uid)}" for uid in state.team_a] or ["—"]
        team_b_lines = [f"• {fmt_user(uid)}" for uid in state.team_b] or ["—"]
        emb.add_field(name=state.team_a_name, value="\n".join(team_a_lines), inline=True)
        emb.add_field(name=state.team_b_name, value="\n".join(team_b_lines), inline=True)

        if not state.finished:
            side = state.current_side
            cap_id = state.captain_a_id if side == "A" else state.captain_b_id
            emb.set_footer(text=f"Tour de {'Team A' if side=='A' else 'Team B'} — Capitaine: <@{cap_id}>")
        else:
            emb.set_footer(text="Draft terminée ✅")
        return emb

    async def on_cancel(self, interaction: discord.Interaction):
        await safe_defer(interaction, update=True)
        try:
            await interaction.message.edit(content="Draft annulée 🛑", embed=None, view=None)
        except Exception:
            pass

# ================== Cog ==================

class Draft(commands.Cog):
    """Draft par capitaines pour les lobbys du cog Core."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    def _get_core_lobby(self, lobby_message_id: int):
        core = self.bot.get_cog("Core")
        if not core:
            return None
        return core.lobbies.get(lobby_message_id)

    def _build_pick_order(self, mode: DraftMode, total_players: int, first_side: str) -> List[str]:
        # par équipe: on doit drafter (total_players/2 - 1) joueurs car le capitaine est déjà dans son équipe
        per_team_to_pick = total_players // 2 - 1
        order: List[str] = []
        if mode == DraftMode.normal:
            base = "ABBA" if first_side == "A" else "BAAB"
            for _ in range(per_team_to_pick):
                order += list(base)
        elif mode == DraftMode.fearless:
            base = "AABB" if first_side == "A" else "BBAA"
            for _ in range(per_team_to_pick):
                order += list(base)
        else:  # hardfearless
            base = "ABAB" if first_side == "A" else "BABA"
            for _ in range(per_team_to_pick):
                order += list(base)
        picks_needed = per_team_to_pick * 2
        return order[:picks_needed]

    @app_commands.command(name="start_draft", description="Lancer une draft par capitaines sur un lobby existant.")
    @app_commands.describe(
        lobby_message_id="ID du message du lobby (clic droit > Copier l'identifiant)",
        mode="Mode de draft (normal/fearless/hardfearless)",
        team_a_name="Nom Team A",
        team_b_name="Nom Team B",
        captain_a="Capitaine Team A (doit être présent dans le lobby)",
        captain_b="Capitaine Team B (doit être présent dans le lobby)",
        first_pick="Qui choisit en premier (A ou B) ?",
        include_subs="Inclure les subs si besoin pour compléter la pool",
    )
    @app_commands.choices(
        first_pick=[
            app_commands.Choice(name="A", value="A"),
            app_commands.Choice(name="B", value="B"),
        ]
    )
    async def start_draft(
        self,
        interaction: discord.Interaction,
        lobby_message_id: str,
        mode: DraftMode,
        team_a_name: str = "Team A",
        team_b_name: str = "Team B",
        captain_a: discord.Member | None = None,
        captain_b: discord.Member | None = None,
        first_pick: str = "A",
        include_subs: bool = True,
    ):
        # Valider lobby
        try:
            msg_id = int(lobby_message_id)
        except Exception:
            await first_response_or_followup(interaction, content="ID de message invalide.", ephemeral=True)
            return

        core = self.bot.get_cog("Core")
        lobby = core.lobbies.get(msg_id) if core else None
        if not lobby:
            await first_response_or_followup(interaction, content="Lobby introuvable. Donne l'ID du message du lobby.", ephemeral=True)
            return

        # Pool joueurs
        pool_ids: List[int] = list(lobby.players.keys())
        if include_subs and len(pool_ids) < lobby.total_slots:
            for uid in lobby.subs.keys():
                if uid not in pool_ids:
                    pool_ids.append(uid)

        if captain_a is None or captain_b is None:
            await first_response_or_followup(interaction, content="Tu dois choisir les deux capitaines.", ephemeral=True)
            return
        if captain_a.id not in pool_ids or captain_b.id not in pool_ids:
            await first_response_or_followup(interaction, content="Les capitaines doivent être dans le lobby.", ephemeral=True)
            return
        if captain_a.id == captain_b.id:
            await first_response_or_followup(interaction, content="Les deux capitaines doivent être différents.", ephemeral=True)
            return

        total_players = lobby.total_slots
        if total_players % 2 != 0 or total_players < 2:
            await first_response_or_followup(interaction, content="Le lobby doit avoir un nombre pair de slots ≥ 2.", ephemeral=True)
            return

        # État initial
        state = DraftState(
            guild_id=interaction.guild_id,
            channel_id=interaction.channel_id,
            lobby_message_id=msg_id,
            mode=mode,
            team_a_name=team_a_name,
            team_b_name=team_b_name,
            captain_a_id=captain_a.id,
            captain_b_id=captain_b.id,
        )
        state.team_a.append(captain_a.id)
        state.team_b.append(captain_b.id)
        state.remaining_user_ids = [u for u in pool_ids if u not in (captain_a.id, captain_b.id)]
        state.order = self._build_pick_order(mode, total_players, first_pick)

        # Labels du select
        pool_labels: Dict[int, str] = {}
        for uid in pool_ids:
            prof = get_profile(uid)
            nt = prof.get("name_tag") if prof else None
            elo = prof.get("elo") if prof else None
            label = nt or f"User:{uid}"
            if elo:
                label = f"{label} · {elo}"
            pool_labels[uid] = label

        view = DraftView(state, pool_labels, author_id=interaction.user.id)
        embed = await view._make_embed(self.bot)
        await first_response_or_followup(interaction, embed=embed, view=view, ephemeral=False)

async def setup(bot: commands.Bot):
    await bot.add_cog(Draft(bot))
