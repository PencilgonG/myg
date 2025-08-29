// src/bot/interactions/dispatcher.ts
import type {
  Interaction,
  ChatInputCommandInteraction,
  ButtonInteraction,
  StringSelectMenuInteraction,
  ModalSubmitInteraction,
} from 'discord.js';
import { MessageFlags } from 'discord.js';

// --- utils: safe replies to éviter "InteractionAlreadyReplied" ---
async function safeReply(i: Interaction, content: string) {
  const payload = { content, flags: MessageFlags.Ephemeral } as any;
  // @ts-ignore - different Interaction types
  if (typeof (i as any).reply === 'function' && !(i as any).replied && !(i as any).deferred) {
    try { return await (i as any).reply(payload); } catch {}
  }
  try { return await (i as any).editReply?.(payload); } catch {}
}

export async function dispatch(interaction: Interaction) {
  try {
    if (interaction.isChatInputCommand()) return handleSlash(interaction);
    if (interaction.isButton()) return handleButton(interaction);
    if (interaction.isStringSelectMenu()) return handleSelect(interaction);
    if (interaction.isModalSubmit()) return handleModal(interaction);
  } catch (err: any) {
    return safeReply(interaction, `❌ ${err?.message || 'Erreur inconnue'}`);
  }
}

// ===== Slash =====
async function handleSlash(i: ChatInputCommandInteraction) {
  const name = i.commandName;
  if (name === 'lobby') {
    try {
      const mod = await import('../commands/lobby/index.ts');
      const fn = (mod as any).handleLobbySlash;
      if (typeof fn === 'function') return fn(i);
    } catch {}
    return i.reply({ content: '🛠️ Lobby: dispatcher OK (handler lobby manquant).', flags: MessageFlags.Ephemeral });
  }

  if (name === 'profile') {
    const sub = i.options.getSubcommand();
    if (sub === 'set') {
      try {
        const mod = await import('../commands/profile/set.ts');
        const fn = (mod as any).handleProfileSet;
        if (typeof fn === 'function') return fn(i);
      } catch {}
      return i.reply({ content: '🛠️ Profile set: handler manquant.', flags: MessageFlags.Ephemeral });
    }
    if (sub === 'view') {
      try {
        const mod = await import('../commands/profile/view.ts');
        const fn = (mod as any).handleProfileView;
        if (typeof fn === 'function') return fn(i);
      } catch {}
      return i.reply({ content: '🛠️ Profile view: handler manquant.', flags: MessageFlags.Ephemeral });
    }
  }

  return i.reply({ content: 'Commande inconnue (ou non routée).', flags: MessageFlags.Ephemeral });
}

// ===== Buttons / Select / Modals =====
// Route tous les IDs liés au lobby (configurer, valider, pick teams, draft:remake, match:validate, etc.)
const LOBBY_PREFIXES = ['lobby:', 'wizard:', 'pick:', 'match:', 'draft:'];

async function routeToLobbyModule(method: 'handleLobbyButton' | 'handleLobbySelect' | 'handleLobbyModal', interaction: any) {
  try {
    const mod = await import('../commands/lobby/index.ts');
    const fn = (mod as any)[method];
    if (typeof fn === 'function') return fn(interaction);
  } catch {}
  return safeReply(interaction, '🛠️ Interaction lobby reçue mais handler manquant.');
}

function isLobbyId(id: string) {
  return LOBBY_PREFIXES.some(p => id.startsWith(p) || id.includes(p.replace(':','')));
}

async function handleButton(i: ButtonInteraction) {
  const id = i.customId || '';
  if (isLobbyId(id)) return routeToLobbyModule('handleLobbyButton', i);
  return safeReply(i, 'Bouton non géré.');
}

async function handleSelect(i: StringSelectMenuInteraction) {
  const id = i.customId || '';
  if (isLobbyId(id)) return routeToLobbyModule('handleLobbySelect', i);
  return safeReply(i, 'Sélecteur non géré.');
}

async function handleModal(i: ModalSubmitInteraction) {
  const id = i.customId || '';
  if (isLobbyId(id)) return routeToLobbyModule('handleLobbyModal', i);
  return safeReply(i, 'Modal non géré.');
}
