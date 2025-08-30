export enum GameMode {
  SR_5v5 = 'SR_5v5',
  SR_4v4 = 'SR_4v4',
  SR_3v3 = 'SR_3v3',
  SR_2v2 = 'SR_2v2'
}

export enum RoleName {
  TOP = 'TOP',
  JUNGLE = 'JUNGLE',
  MID = 'MID',
  ADC = 'ADC',
  SUPPORT = 'SUPPORT',
  FLEX = 'FLEX'
}

export function rosterSizeFor(mode: GameMode): number {
  switch (mode) {
    case GameMode.SR_5v5: return 5;
    case GameMode.SR_4v4: return 4;
    case GameMode.SR_3v3: return 3;
    case GameMode.SR_2v2: return 2;
    default: return 5;
  }
}

export function modeLabel(m: GameMode): string {
  return {
    [GameMode.SR_5v5]: '5v5',
    [GameMode.SR_4v4]: '4v4',
    [GameMode.SR_3v3]: '3v3',
    [GameMode.SR_2v2]: '2v2'
  }[m];
}
