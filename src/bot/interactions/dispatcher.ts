// src/bot/interactions/dispatcher.ts
import type {
  Interaction,
  ButtonInteraction,
  StringSelectMenuInteraction,
  ModalSubmitInteraction,
  ChatInputCommandInteraction,
} from "discord.js";

// === LOBBY (wizard) ===
import {
  handleSlashLobby,
  onLobbyButton,
  handleLobbySelect,
  handleLobbyModal,
} from "../lobby/index.js";

// === PROFIL (/profil set | /profil view) ===
import { handleProfileSet } from "../commands/profile/set.js";
import { handleProfileView } from "../commands/profile/view.js";

/**
 * Route les slash commands
 */
export async function handleSlash(interaction: ChatInputCommandInteraction) {
  const name = interaction.commandName;

  // /lobby
  if (name === "lobby") {
    return handleSlashLobby(interaction);
  }

  // /profil set | /profil view
  if (name === "profil") {
    const sub = interaction.options.getSubcommand();
    if (sub === "set") return handleProfileSet(interaction);
    if (sub === "view") return handleProfileView(interaction);
  }

  // non géré → no-op
  return;
}

/**
 * Route UNIQUEMENT les boutons
 * (exposé séparément si ton index.ts en a besoin quelque part)
 */
export async function handleButton(interaction: ButtonInteraction) {
  return onLobbyButton(interaction);
}

/**
 * Route UNIQUEMENT les selects (StringSelectMenu)
 */
export async function handleSelect(
  interaction: StringSelectMenuInteraction,
) {
  return handleLobbySelect(interaction);
}

/**
 * Route UNIQUEMENT les modals
 */
export async function handleModal(interaction: ModalSubmitInteraction) {
  return handleLobbyModal(interaction);
}

/**
 * ⭐ Compatibilité avec ton src/index.ts
 * Ton bootstrap appelle `handleInteractionComponent` pour tout ce qui n’est pas une slash command.
 * On route ici selon le type d’interaction (button/select/modal).
 */
export async function handleInteractionComponent(interaction: Interaction) {
  if (interaction.isButton()) {
    return onLobbyButton(interaction as ButtonInteraction);
  }
  if (interaction.isStringSelectMenu()) {
    return handleLobbySelect(interaction as StringSelectMenuInteraction);
  }
  if (interaction.isModalSubmit()) {
    return handleLobbyModal(interaction as ModalSubmitInteraction);
  }
  // Autres types non gérés → no-op
  return;
}
