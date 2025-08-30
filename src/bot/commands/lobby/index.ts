// src/bot/lobby/index.ts
import type { Interaction } from "discord.js";

// Flux lobby (slash / boutons / selects / modals)
import {
  handleSlashLobby,
  onLobbyButton,
  handleLobbySelect,
  handleLobbyModal,
} from "./wizard.js";

// Profil (/profil set, /profil view)
import { handleProfileSet } from "../commands/profile/set.js";
import { handleProfileView } from "../commands/profile/view.js";

/**
 * Routeur des commandes slash.
 * On garde tout centralisé ici pour que l’interactions/dispatcher
 * n’ait qu’à déléguer à handleSlash().
 */
export async function handleSlash(interaction: Interaction) {
  if (!interaction.isChatInputCommand()) return;

  // /lobby
  if (interaction.commandName === "lobby") {
    return handleSlashLobby(interaction);
  }

  // /profil set | view
  if (interaction.commandName === "profil") {
    const sub = interaction.options.getSubcommand();
    if (sub === "set") return handleProfileSet(interaction);
    if (sub === "view") return handleProfileView(interaction);
  }
}

// On ré-exporte pour que le dispatcher puisse brancher les composants
export { onLobbyButton, handleLobbySelect, handleLobbyModal };
