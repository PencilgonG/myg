// src/bot/interactions/ids.ts
export const IDS = {
  // ===== Lobby wizard =====
  lobby: {
    // top-level wizard controls
    openConfig: (lobbyId: string) => `lobby:config:${lobbyId}`,
    testFill:  (lobbyId: string) => `lobby:test:${lobbyId}`,
    validate:  (lobbyId: string) => `lobby:validate:${lobbyId}`,

    // modals
    configModal:   (lobbyId: string) => `modal:config:${lobbyId}`,
    scheduleModal: (lobbyId: string) => `modal:schedule:${lobbyId}`,

    // pick UI navigation
    pickPage:     (lobbyId: string, teamNo: number) => `pick:page:${lobbyId}:${teamNo}`,
    pickPrev:     (lobbyId: string, teamNo: number) => `pick:prev:${lobbyId}:${teamNo}`,
    pickNext:     (lobbyId: string, teamNo: number) => `pick:next:${lobbyId}:${teamNo}`,
    pickValidate: (lobbyId: string)               => `pick:validate:${lobbyId}`,
    pickSchedule: (lobbyId: string)               => `pick:schedule:${lobbyId}`,

    // selects
    selectCaptain: (lobbyId: string, teamNo: number) => `select:captain:${lobbyId}:${teamNo}`,
    selectPlayers: (lobbyId: string, teamNo: number) => `select:players:${lobbyId}:${teamNo}`,
  },

  // ===== Match actions =====
  match: {
    validate: (matchId: string) => `match:validate:${matchId}`,
  },

  // ===== Draft actions =====
  draft: {
    remake: (matchId: string) => `draft:remake:${matchId}`,
  },
};
