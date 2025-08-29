// path: src/bot/lobby/schedule.ts
export type Pair = { a: number; b: number };
export type Round = Pair[];

/**
 * Format attendu, ex:
 * "1-2,3-4 | 1-3,2-4 | 1-4,2-3"
 * Renvoie un tableau de rounds.
 */
export function parseScheduleFormat(input: string, teamCount: number): Round[] {
  const rounds = input
    .split('|')
    .map(r => r.trim())
    .filter(Boolean)
    .map(r => r.split(',').map(p => p.trim()).filter(Boolean));

  const out: Round[] = [];
  for (const pairs of rounds) {
    const round: Round = [];
    for (const pair of pairs) {
      const m = pair.match(/^(\d+)\s*-\s*(\d+)$/);
      if (!m) continue;
      const a = Number(m[1]);
      const b = Number(m[2]);
      if (a >= 1 && a <= teamCount && b >= 1 && b <= teamCount && a !== b) {
        round.push({ a, b });
      }
    }
    if (round.length) out.push(round);
  }
  return out;
}
