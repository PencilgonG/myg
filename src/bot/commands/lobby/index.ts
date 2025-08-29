import {
  ActionRowBuilder,
  ButtonBuilder,
  ButtonInteraction,
  ButtonStyle,
  ChatInputCommandInteraction,
  EmbedBuilder,
  MessageFlags,
  ModalSubmitInteraction,
  StringSelectMenuInteraction,
} from 'discord.js';

// --- cache import du wizard pour éviter le délai du 1er import ---
let wizardMod: any | null = null;
let wizardLoad: Promise<any> | null = null;
async function loadWizard() {
  if (wizardMod) return wizardMod;
  if (!wizardLoad) wizardLoad = import('../../lobby/wizard.ts').catch(() => null);
  wizardMod = await wizardLoad;
  return wizardMod;
}

async function callWizard(fnName: string, ...args: any[]): Promise<boolean> {
  const mod = await loadWizard();
  const fn = mod?.[fnName];
  if (typeof fn !== 'function') return false;
  await fn(...args);
  return true;
}

async function safeEphemeral(i: any, content: string) {
  const payload = { content, flags: MessageFlags.Ephemeral } as any;
  if (!i.deferred && !i.replied) {
    try { return await i.reply(payload); } catch {}
  }
  try { return await i.editReply?.(payload); } catch {}
}

// ===== /lobby =====
export async function handleLobbySlash(interaction: ChatInputCommandInteraction) {
  // Tente de déléguer au wizard (écran initial) – si dispo
  if (await callWizard('onLobbySlash', interaction)) return;

  const embed = new EmbedBuilder()
    .setColor(0x2b2d31)
    .setTitle('Créer un lobby')
    .setDescription('Configure les paramètres puis valide.')
    .addFields(
      { name: 'Nom', value: 'Nouveau lobby', inline: true },
      { name: 'Slots (équipes)', value: '2', inline: true },
      { name: 'Mode', value: '5v5', inline: true },
    );

  const row = new ActionRowBuilder<ButtonBuilder>().addComponents(
    new ButtonBuilder().setCustomId('lobby:config:open').setLabel('Configurer').setStyle(ButtonStyle.Secondary),
    new ButtonBuilder().setCustomId('lobby:test:fill').setLabel('Test').setStyle(ButtonStyle.Secondary),
    new ButtonBuilder().setCustomId('lobby:validate:step1').setLabel('Valider').setStyle(ButtonStyle.Success),
  );

  return interaction.reply({ embeds: [embed], components: [row] });
}

// ===== Buttons =====
export async function handleLobbyButton(interaction: ButtonInteraction) {
  const id = interaction.customId || '';

  // IMPORTANT: ne jamais defer avant un showModal
  if (id.startsWith('lobby:config:open')) {
    const handled = await callWizard('onLobbyConfigure', interaction);
    if (handled) return; // modal ouvert
    return safeEphemeral(interaction, '🛠️ Stub: panneau de configuration (wizard absent).');
  }

  // Le reste peut être différé pour éviter le bandeau rouge
  try { await interaction.deferReply({ flags: MessageFlags.Ephemeral }); } catch {}

  if (id.startsWith('lobby:test:fill')) {
    if (await callWizard('onLobbyTest', interaction)) return;
    return safeEphemeral(interaction, '🧪 Stub: remplissage de faux joueurs (wizard absent).');
  }

  if (id.startsWith('lobby:validate:step1')) {
    if (await callWizard('onLobbyValidate', interaction)) return;
    return safeEphemeral(interaction, '✅ Stub: validation (wizard absent).');
  }

  if (id.startsWith('pick:') || id.startsWith('match:') || id.startsWith('draft:')) {
    if (await callWizard('onLobbyButton', interaction)) return;
    return safeEphemeral(interaction, '🛠️ Interaction lobby reçue mais handler manquant.');
  }

  return safeEphemeral(interaction, 'Bouton non géré.');
}

// ===== Select =====
export async function handleLobbySelect(interaction: StringSelectMenuInteraction) {
  try { await interaction.deferReply({ flags: MessageFlags.Ephemeral }); } catch {}
  if (await callWizard('onLobbySelect', interaction)) return;
  return safeEphemeral(interaction, 'Sélecteur lobby non géré (wizard absent).');
}

// ===== Modals =====
export async function handleLobbyModal(interaction: ModalSubmitInteraction) {
  // Ne pas deferUpdate sur un modal submit; on répond directement, ou le wizard le fera
  if (await callWizard('onLobbyModal', interaction)) return;
  return safeEphemeral(interaction, 'Modal lobby non géré (wizard absent).');
}