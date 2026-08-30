export const ROUND_LABELS = [
  "R1",
  "R2",
  "R3",
  "R4",
  "QF",
  "SF",
  "F",
];

export function pct(value: number, digits = 0): string {
  return `${(value * 100).toFixed(digits)}%`;
}

export function points(value: number): string {
  return value.toFixed(1);
}

export function seedLabel(seed: number): string {
  return seed > 0 ? `#${seed}` : "—";
}

/** Human label for a tournament round index (1-7). */
export function roundName(round: number): string {
  return ROUND_LABELS[round - 1] ?? `R${round}`;
}

/**
 * Probability that at least one team member wins the title. Exactly one
 * champion exists, so the events are mutually exclusive and the exact
 * probability is the sum of the members' title chances.
 */
export function anyTitleChance(titleProbs: number[]): number {
  return Math.min(1, titleProbs.reduce((acc, p) => acc + p, 0));
}

/** Copy-friendly export of the current team. */
export function teamExportText(
  rows: { player: string; seed: number; role: string }[],
  joker: string,
  kluns: string,
  expectedPoints: number,
): string {
  const lines = rows.map(
    (row) =>
      `${row.player}${row.seed > 0 ? ` (${row.seed})` : ""}${
        row.role === "joker" ? " ★ joker" : row.role === "kluns" ? " ▼ loser" : ""
      }`,
  );
  return [
    `Sportpools selection — expected ${points(expectedPoints)} points`,
    ...lines,
    `Joker: ${joker}`,
    `Kluns: ${kluns}`,
  ].join("\n");
}

/** Bracket quarter (1-4) a draw section (1-8) belongs to. */
export function quarterOf(section: number): number {
  return Math.ceil(section / 2);
}

const QUARTER_STYLES = [
  "border-sky-500/40 bg-sky-500/10 text-sky-600 dark:text-sky-300",
  "border-emerald-500/40 bg-emerald-500/10 text-emerald-600 dark:text-emerald-300",
  "border-violet-500/40 bg-violet-500/10 text-violet-600 dark:text-violet-300",
  "border-orange-500/40 bg-orange-500/10 text-orange-600 dark:text-orange-300",
];

/** Colour classes for a quarter chip. */
export function quarterStyle(section: number): string {
  return QUARTER_STYLES[quarterOf(section) - 1] ?? QUARTER_STYLES[0];
}
