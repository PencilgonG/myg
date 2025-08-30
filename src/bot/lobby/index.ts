// src/bot/lobby/index.ts
// Pont unique vers le “wizard” du lobby.
// ⚠️ Ne surtout pas importer le dispatcher ici (sinon boucle d’import).

export {
  handleSlashLobby,
  onLobbyButton,
  handleLobbySelect,
  handleLobbyModal,
} from "./wizard.js";
