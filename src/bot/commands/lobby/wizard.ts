import {
  ActionRowBuilder,
  ButtonBuilder,
  ButtonInteraction,
  ButtonStyle,
  ChatInputCommandInteraction,
  EmbedBuilder,
  Message,
  MessageFlags,
  ModalBuilder,
  ModalSubmitInteraction,
  StringSelectMenuInteraction,
  TextInputBuilder,
  TextInputStyle,
} from 'discord.js';

type GameMode = '5v5' | '4v4' | '3v3' | '2v2' | '1v1' | 'aram' | 'tft';

type LobbyState = {
  guildId: string;
  channelId: string;
  messageId?: string;
  createdBy: string;
  name: string;
  slots: number;
  mode: GameMode;
};

const sessions = new Map<string, LobbyState>();
const keyFrom = (i: { guildId: string | null; channelId: string | null }) => `${i.guildId}:${i.channelId}`;

const lobbyEmbed = (s: LobbyState) =>
  new EmbedBuilder()
    .setColor(0x2b2d31)
    .setTitle('Créer un lobby')
    .setDescription('Configure les paramètres puis valide.')
    .addFields(
      { name: 'Nom', value: s.name, inline: true },
      { name: 'Slots (équipes)', value: String(s.slots), inline: true },
      { name: 'Mode', value: s.mode, inline: true },
    );

const controlsRow = () =>
  new ActionRowBuilder<ButtonBuilder>().addComponents(
    new ButtonBuilder().setCustomId('lobby:config:open').setLabel('Configurer').setStyle(ButtonStyle.Secondary),
    new ButtonBuilder().setCustomId('lobby:test:fill').setLabel('Test').setStyle(ButtonStyle.Secondary),
    new ButtonBuilder().setCustomId('lobby:validate:step1').setLabel('Valider').setStyle(ButtonStyle.Success),
  );

const step2Embed = (s: LobbyState) =>
  new EmbedBuilder().setColor(0x2b2d31).setTitle(`Lobby prêt • ${s.name}`).setDescription('Étape suivante (stub): choix des rôles / teams / matchs.');

const step2Rows = () => [
  new ActionRowBuilder<ButtonBuilder>().addComponents(
    new ButtonBuilder().setCustomId('pick:role:open').setLabel('Choisir rôle').setStyle(ButtonStyle.Secondary),
    new ButtonBuilder().setCustomId('pick:role:leave').setLabel('Quitter rôle').setStyle(ButtonStyle.Secondary),
    new ButtonBuilder().setCustomId('pick:role:sub').setLabel('Sub').setStyle(ButtonStyle.Secondary),
    new ButtonBuilder().setCustomId('pick:teams:open').setLabel('Pick teams').setStyle(ButtonStyle.Primary),
  ),
  new ActionRowBuilder<ButtonBuilder>().addComponents(
    new ButtonBuilder().setCustomId('match:schedule:open').setLabel('Sélectionner matchs').setStyle(ButtonStyle.Secondary),
    new ButtonBuilder().setCustomId('match:validate:all').setLabel('Valider').setStyle(ButtonStyle.Success),
  ),
];

// ===== Entrées exposées =====
export async function onLobbySlash(interaction: ChatInputCommandInteraction) {
  const s: LobbyState = {
    guildId: interaction.guildId!,
    channelId: interaction.channelId!,
    createdBy: interaction.user.id,
    name: 'Nouveau lobby',
    slots: 2,
    mode: '5v5',
  };
  sessions.set(keyFrom(interaction), s);
  const msg = await interaction.reply({ embeds: [lobbyEmbed(s)], components: [controlsRow()], fetchReply: true });
  s.messageId = (msg as Message).id;
  return true;
}

export async function onLobbyConfigure(i: ButtonInteraction) {
  const s = sessions.get(keyFrom(i));
  if (!s) { await i.reply({ content: 'Lobby introuvable.', flags: MessageFlags.Ephemeral }); return true; }

  const modal = new ModalBuilder().setCustomId('lobby:config:modal').setTitle('Configurer le lobby');
  const name = new TextInputBuilder().setCustomId('name').setLabel('Nom du lobby').setStyle(TextInputStyle.Short).setRequired(true).setValue(s.name);
  const slots = new TextInputBuilder().setCustomId('slots').setLabel('Slots (équipes) 1–8').setStyle(TextInputStyle.Short).setRequired(true).setValue(String(s.slots));
  const mode  = new TextInputBuilder().setCustomId('mode').setLabel('Mode (5v5/4v4/3v3/2v2/1v1/aram/tft)').setStyle(TextInputStyle.Short).setRequired(true).setValue(s.mode);
  modal.addComponents(
    new ActionRowBuilder<TextInputBuilder>().addComponents(name),
    new ActionRowBuilder<TextInputBuilder>().addComponents(slots),
    new ActionRowBuilder<TextInputBuilder>().addComponents(mode),
  );

  await i.showModal(modal); // répondre dans les 3s, pas de defer avant
  return true;
}

export async function onLobbyTest(i: ButtonInteraction) {
  const payload = { content: '🧪 Faux joueurs ajoutés (stub).', flags: MessageFlags.Ephemeral } as any;
  if (i.deferred || i.replied) await i.editReply(payload); else await i.reply(payload);
  return true;
}

export async function onLobbyValidate(i: ButtonInteraction) {
  const s = sessions.get(keyFrom(i));
  if (!s) { const p = { content: 'Lobby introuvable.', flags: MessageFlags.Ephemeral } as any; if (i.deferred || i.replied) await i.editReply(p); else await i.reply(p); return true; }

  const ch = await i.client.channels.fetch(s.channelId).catch(() => null);
  if (ch && 'messages' in (ch as any) && s.messageId) {
    const msg = await (ch as any).messages.fetch(s.messageId).catch(() => null);
    if (msg) await msg.edit({ embeds: [step2Embed(s)], components: step2Rows() });
  }

  const ok = { content: '✅ Étape suivante ouverte.', flags: MessageFlags.Ephemeral } as any;
  if (i.deferred || i.replied) await i.editReply(ok); else await i.reply(ok);
  return true;
}

export async function onLobbyButton(i: ButtonInteraction) {
  const id = i.customId;
  if (id.startsWith('pick:')) {
    const p = { content: '🎯 Pick (stub).', flags: MessageFlags.Ephemeral } as any;
    if (i.deferred || i.replied) await i.editReply(p); else await i.reply(p);
    return true;
  }
  if (id.startsWith('match:')) {
    const p = { content: '📅 Match (stub).', flags: MessageFlags.Ephemeral } as any;
    if (i.deferred || i.replied) await i.editReply(p); else await i.reply(p);
    return true;
  }
  if (id.startsWith('draft:')) {
    const p = { content: '🧩 Draft (stub).', flags: MessageFlags.Ephemeral } as any;
    if (i.deferred || i.replied) await i.editReply(p); else await i.reply(p);
    return true;
  }
  return false;
}

export async function onLobbySelect(i: StringSelectMenuInteraction) {
  const p = { content: 'Sélecteur (stub).', flags: MessageFlags.Ephemeral } as any;
  if (i.deferred || i.replied) await i.editReply(p); else await i.reply(p);
  return true;
}

export async function onLobbyModal(i: ModalSubmitInteraction) {
  if (i.customId !== 'lobby:config:modal') {
    const p = { content: 'Modal non géré.', flags: MessageFlags.Ephemeral } as any;
    if (i.deferred || i.replied) await i.editReply(p); else await i.reply(p);
    return true;
  }

  const s = sessions.get(keyFrom(i));
  if (!s) { const p = { content: 'Lobby introuvable.', flags: MessageFlags.Ephemeral } as any; if (i.deferred || i.replied) await i.editReply(p); else await i.reply(p); return true; }

  const name = i.fields.getTextInputValue('name')?.trim() || s.name;
  const slotsRaw = i.fields.getTextInputValue('slots')?.trim() || String(s.slots);
  const modeRaw = (i.fields.getTextInputValue('mode')?.trim() || s.mode).toLowerCase();
  const slots = Math.min(8, Math.max(1, parseInt(slotsRaw, 10) || 2));
  const allowed: GameMode[] = ['5v5', '4v4', '3v3', '2v2', '1v1', 'aram', 'tft'];
  const mode = (allowed.includes(modeRaw as GameMode) ? modeRaw : '5v5') as GameMode;

  s.name = name; s.slots = slots; s.mode = mode;

  const ch = await i.client.channels.fetch(s.channelId).catch(() => null);
  if (ch && 'messages' in (ch as any) && s.messageId) {
    const msg = await (ch as any).messages.fetch(s.messageId).catch(() => null);
    if (msg) await msg.edit({ embeds: [lobbyEmbed(s)], components: [controlsRow()] });
  }

  const ok = { content: '⚙️ Config mise à jour.', flags: MessageFlags.Ephemeral } as any;
  if (i.deferred || i.replied) await i.editReply(ok); else await i.reply(ok);
  return true;
}
