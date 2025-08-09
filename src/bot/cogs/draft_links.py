from dataclasses import dataclass
from typing import Optional, Dict, List
import discord
from discord import app_commands
from discord.ext import commands

from bot.store import append_history, get_mod_role

@dataclass
class DraftRooms:
    guild_id:int; author_id:int
    captain_blue_id:int; captain_red_id:int
    category_id:int; text_blue_id:int; text_red_id:int; voice_blue_id:int; voice_red_id:int
    blue_url:Optional[str]=None; red_url:Optional[str]=None; spec_url:Optional[str]=None; message_id:Optional[int]=None
    lobby_message_id:Optional[int]=None

def is_inhouse_mod():
    async def predicate(inter:discord.Interaction):
        if inter.user.guild_permissions.manage_guild: return True
        rid=get_mod_role(inter.guild_id or 0)
        return rid is not None and any(r.id==rid for r in getattr(inter.user,"roles",[]))
    return app_commands.check(predicate)

class EndDraftButton(discord.ui.Button):
    def __init__(self, cog:"DraftLinks", rooms:DraftRooms):
        super().__init__(style=discord.ButtonStyle.danger, label="Terminer (supprimer salons)", emoji="🗑️")
        self.cog=cog; self.rooms=rooms
    async def callback(self, interaction:discord.Interaction):
        if interaction.user.id!=self.rooms.author_id and not interaction.user.guild_permissions.manage_guild:
            await interaction.response.send_message("Réservé au modérateur/initiatrice.", ephemeral=True); return
        await self.cog._finalize_history(interaction.guild, self.rooms, manual=True)
        await self.cog._delete_rooms(interaction.guild, self.rooms)
        try: await interaction.response.send_message("Draft terminée, salons supprimés ✅", ephemeral=True)
        except Exception: await interaction.followup.send("Draft terminée, salons supprimés ✅", ephemeral=True)

class DraftControlView(discord.ui.View):
    def __init__(self, cog:"DraftLinks", rooms:DraftRooms):
        super().__init__(timeout=None); self.add_item(EndDraftButton(cog, rooms))

class DraftLinks(commands.Cog):
    """ /draft : crée catégorie + salons (Blue/Red) ; /draft_set_links : distribue liens. """
    def __init__(self, bot:commands.Bot):
        self.bot=bot; self.active:Dict[int,DraftRooms]={}
    async def cog_load(self): return

    async def _create_team_structure(self, guild:discord.Guild, prefix:str, captain:discord.Member,
                                     base_ov:Dict[discord.abc.Snowflake, discord.PermissionOverwrite],
                                     category:discord.CategoryChannel)->tuple[discord.TextChannel, discord.VoiceChannel]:
        ov=dict(base_ov); ov[captain]=discord.PermissionOverwrite(view_channel=True,read_message_history=True,send_messages=True,connect=True,speak=True)
        text=await guild.create_text_channel(name=f"{prefix}-text", category=category, overwrites=ov, reason="Inhouse draft setup")
        voice=await guild.create_voice_channel(name=f"{prefix}-voice", category=category, overwrites=ov, reason="Inhouse draft setup")
        return text,voice

    async def _grant_user(self, ch:discord.abc.GuildChannel, member:discord.Member):
        try:
            await ch.set_permissions(member, view_channel=True, read_message_history=True, send_messages=True, connect=True, speak=True)
        except Exception: pass

    async def _delete_rooms(self, guild:discord.Guild, rooms:DraftRooms):
        for cid in [rooms.text_blue_id, rooms.text_red_id, rooms.voice_blue_id, rooms.voice_red_id]:
            ch=guild.get_channel(cid)
            if ch:
                try: await ch.delete(reason="Inhouse draft cleanup")
                except Exception: pass
        cat=guild.get_channel(rooms.category_id)
        if cat:
            try: await cat.delete(reason="Inhouse draft cleanup")
            except Exception: pass
        self.active.pop(guild.id, None)

    async def _finalize_history(self, guild:discord.Guild, rooms:DraftRooms, manual:bool):
        append_history(guild.id, {"type":"draft","title":"inhouse myg","cap_blue":rooms.captain_blue_id,"cap_red":rooms.captain_red_id,"manual":manual})

    # -------- Commands --------

    @app_commands.command(name="draft", description="Créer la structure de draft (salons Blue/Red).")
    @app_commands.describe(
        captain_blue="Capitaine Blue", captain_red="Capitaine Red",
        everyone_can_view="Si vrai: salons visibles par tous",
        lobby_message_id="(Optionnel) ID du message de lobby pour autoriser tous les joueurs",
    )
    @is_inhouse_mod()
    async def draft(self, interaction:discord.Interaction, captain_blue:discord.Member, captain_red:discord.Member,
                    everyone_can_view:bool=False, lobby_message_id:Optional[str]=None):
        try: await interaction.response.send_message("⏳ Création de la structure de draft…", ephemeral=True)
        except Exception: pass

        guild=interaction.guild
        if not guild: return
        base_ov={}
        if not everyone_can_view: base_ov[guild.default_role]=discord.PermissionOverwrite(view_channel=False)

        try:
            category=await guild.create_category(name="inhouse-myg", overwrites=base_ov if not everyone_can_view else None, reason="Inhouse draft setup")
            tb,vb=await self._create_team_structure(guild,"blue",captain_blue,base_ov,category)
            tr,vr=await self._create_team_structure(guild,"red",captain_red,base_ov,category)
        except Exception as e:
            await interaction.followup.send(f"❌ Impossible de créer les salons/catégorie : {e}", ephemeral=True); return

        rooms=DraftRooms(guild.id, interaction.user.id, captain_blue.id, captain_red.id,
                         category.id, tb.id, tr.id, vb.id, vr.id)
        self.active[guild.id]=rooms

        # Option: autoriser tous les joueurs du lobby (accès dans les deux salons pour commencer)
        if lobby_message_id:
            try:
                msg_id=int(lobby_message_id)
                core=self.bot.get_cog("Core")
                lobby = core.lobbies.get(msg_id) if core else None
                if lobby:
                    member_ids=list(lobby.players.keys())[:lobby.total_slots]
                    for uid in member_ids:
                        m=guild.get_member(uid)
                        if m:
                            await self._grant_user(tb, m); await self._grant_user(tr, m); await self._grant_user(vb, m); await self._grant_user(vr, m)
                    rooms.lobby_message_id=msg_id
            except Exception: pass

        ctrl=discord.Embed(
            title="Draft — inhouse myg",
            description=("Salons créés.\n"
                         "1) Va sur **http://prodraft.leagueoflegends.com** (Match: *inhouse myg*, Blue: *blue*, Red: *red*).\n"
                         "2) Copie les 3 liens (blue/red/spec).\n"
                         "3) `/draft_set_links` → DM capitaines + poste lien spectateur."),
            color=discord.Color.blurple(),
        )
        view=DraftControlView(self, rooms)
        try:
            m=await tb.send(embed=ctrl, view=view); rooms.message_id=m.id
            await tr.send("Salon **red** prêt. En attente des liens ProDraft…")
        except Exception: pass

        await interaction.followup.send(f"✅ Catégorie et salons créés — {category.name}", ephemeral=True)

    @app_commands.command(name="draft_set_links", description="Associer les liens ProDraft et les distribuer.")
    @app_commands.describe(blue_url="URL Blue", red_url="URL Red", spec_url="URL spectateur")
    @is_inhouse_mod()
    async def draft_set_links(self, interaction:discord.Interaction, blue_url:str, red_url:str, spec_url:str):
        try: await interaction.response.send_message("⏳ Distribution des liens…", ephemeral=True)
        except Exception: pass
        rooms=self.active.get(interaction.guild_id)
        if not rooms: await interaction.followup.send("Aucune draft active. Lance d'abord `/draft`.", ephemeral=True); return
        rooms.blue_url=blue_url.strip(); rooms.red_url=red_url.strip(); rooms.spec_url=spec_url.strip()

        g=interaction.guild
        try:
            b=g.get_member(rooms.captain_blue_id); 
            if b: await b.send(f"**Lien Blue ProDraft** : {rooms.blue_url}")
        except Exception: pass
        try:
            r=g.get_member(rooms.captain_red_id); 
            if r: await r.send(f"**Lien Red ProDraft** : {rooms.red_url}")
        except Exception: pass

        spec=f"**Lien spectateur ProDraft** : {rooms.spec_url}"
        for cid in (rooms.text_blue_id, rooms.text_red_id):
            ch=g.get_channel(cid)
            if isinstance(ch,discord.TextChannel):
                try: await ch.send(spec)
                except Exception: pass

        await interaction.followup.send("Liens enregistrés et distribués ✅", ephemeral=True)

    # Ajout/Retrait de joueurs dans une équipe (après choix des capitaines)
    @app_commands.command(name="draft_add", description="Donner accès d'équipe à un joueur.")
    @app_commands.describe(team="blue ou red", user="membre à ajouter")
    @is_inhouse_mod()
    async def draft_add(self, interaction:discord.Interaction, team:app_commands.Choice[str], user:discord.Member):
        rooms=self.active.get(interaction.guild_id)
        if not rooms: await interaction.response.send_message("Pas de draft active.", ephemeral=True); return
        g=interaction.guild
        target = g.get_channel(rooms.text_blue_id if team.value=="blue" else rooms.text_red_id)
        voice  = g.get_channel(rooms.voice_blue_id if team.value=="blue" else rooms.voice_red_id)
        await self._grant_user(target, user); await self._grant_user(voice, user)
        await interaction.response.send_message(f"✅ {user.mention} ajouté côté **{team.value}**", ephemeral=True)

    @app_commands.command(name="draft_remove", description="Retirer l'accès d'équipe à un joueur.")
    @app_commands.describe(team="blue ou red", user="membre à retirer")
    @is_inhouse_mod()
    async def draft_remove(self, interaction:discord.Interaction, team:app_commands.Choice[str], user:discord.Member):
        rooms=self.active.get(interaction.guild_id)
        if not rooms: await interaction.response.send_message("Pas de draft active.", ephemeral=True); return
        g=interaction.guild
        text = g.get_channel(rooms.text_blue_id if team.value=="blue" else rooms.text_red_id)
        voice= g.get_channel(rooms.voice_blue_id if team.value=="blue" else rooms.voice_red_id)
        try:
            if text: await text.set_permissions(user, overwrite=None)
            if voice: await voice.set_permissions(user, overwrite=None)
        except Exception: pass
        await interaction.response.send_message(f"✅ {user.mention} retiré de **{team.value}**", ephemeral=True)
async def setup(bot: commands.Bot):
    await bot.add_cog(DraftLinks(bot))
