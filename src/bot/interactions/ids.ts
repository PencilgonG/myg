// path: src/bot/interactions/ids.ts
export const IDS = {
  lobby: {
    openConfig: (lobbyId: string) => `lobby:config:${lobbyId}`,
    testFill:   (lobbyId: string) => `lobby:test:${lobbyId}`,
    validate:   (lobbyId: string) => `lobby:validate:${lobbyId}`,

    // Phase joueurs
    gotoPick:   (lobbyId: string) => `lobby:gotoPick:${lobbyId}`,
    chooseRole: (lobbyId: string) => `lobby:chooseRole:${lobbyId}`,
    quitRole:   (lobbyId: string) => `lobby:quitRole:${lobbyId}`,
    sub:        (lobbyId: string) => `lobby:sub:${lobbyId}`,

    // Pick teams (pagination 1 équipe/page)
    pickPage:     (lobbyId: string, teamNo: number) => `pick:page:${lobbyId}:${teamNo}`,
    pickOpen:     (lobbyId: string) => `pick:open:${lobbyId}`,
    pickCaptain:  (lobbyId: string, teamNo: number) => `pick:captain:${lobbyId}:${teamNo}`,
    pickPlayers:  (lobbyId: string, teamNo: number) => `pick:players:${lobbyId}:${teamNo}`,
    pickPrev:     (lobbyId: string, teamNo: number) => `pick:prev:${lobbyId}:${teamNo}`,
    pickNext:     (lobbyId: string, teamNo: number) => `pick:next:${lobbyId}:${teamNo}`,
    pickValidate: (lobbyId: string) => `pick:validate:${lobbyId}`,
    pickSchedule: (lobbyId: string) => `pick:schedule:${lobbyId}`, // ouvre le modal de planning

    // Select menus / modals ids
    selectCaptain: (lobbyId: string, teamNo: number) => `select:captain:${lobbyId}:${teamNo}`,
    selectPlayers: (lobbyId: string, teamNo: number) => `select:players:${lobbyId}:${teamNo}`,
    scheduleModal: (lobbyId: string) => `modal:schedule:${lobbyId}`,

    // Matches
    matchValidate: (matchId: string) => `match:validate:${matchId}`
  }
} as const;
