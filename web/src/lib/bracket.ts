import type { PoolPlayer } from "@/types";

/**
 * Classic single-elimination bracket geometry for a 128-player draw.
 *
 * The draw is rendered as 13 columns: the top half flows left-to-right
 * (R1, R2, R3, R4), meets the bottom half in the centre (QF, SF, F, SF, QF)
 * and the bottom half flows right-to-left (R4, R3, R2, R1).
 */

export interface BracketPlayer extends PoolPlayer {
  position: number;
}

export const COL_WIDTH = 150;
export const COL_GAP = 26;
export const ROW_HEIGHT = 24;
export const R1_MATCH_GAP = 10;
export const HEADER_HEIGHT = 30;

export const ROUND_COLUMNS = [
  "R1", "R2", "R3", "R4", "QF", "SF", "FINAL", "SF", "QF", "R4", "R3", "R2", "R1",
];

export interface SlotRow {
  player: BracketPlayer;
  /** Probability the player occupies this slot (1 for round 1). */
  pReach: number;
  /** True for rounds beyond the first: the modal (most likely) occupant. */
  expected: boolean;
}

export interface Connector {
  /** Horizontal segment. */
  x: number;
  y: number;
  w: number;
  horizontal: boolean;
  /** Height for vertical segments. */
  h?: number;
}

export interface BracketNode {
  round: number; // 1..7
  columnIndex: number; // 0..12
  x: number;
  center: number;
  rows: [SlotRow, SlotRow];
  children: [BracketNode, BracketNode] | null;
  /** Section(s) feeding this node, for labels. */
  sections: number[];
}

export interface BracketModel {
  width: number;
  height: number;
  nodes: BracketNode[];
  connectors: Connector[];
  champion: SlotRow;
  halfHeight: number;
}

/** Probability that a player reaches round `round` (1-7). */
function reachProbability(player: BracketPlayer, round: number): number {
  if (round <= 1) return 1;
  return player.probs[round - 2] ?? 0;
}

/** The most likely occupant of a slot at `round` among `players`. */
function modalOccupant(
  players: BracketPlayer[],
  round: number,
): SlotRow {
  let best = players[0];
  let bestProb = -1;
  for (const player of players) {
    const prob = reachProbability(player, round);
    if (prob > bestProb) {
      best = player;
      bestProb = prob;
    }
  }
  return { player: best, pReach: bestProb, expected: true };
}

/** Players ordered by bracket slot: section 1..8, position 0..15. */
export function orderPool(pool: PoolPlayer[]): BracketPlayer[] {
  const withPosition = pool
    .filter((p) => p.section >= 1 && p.position >= 0)
    .map((p) => p as BracketPlayer);
  withPosition.sort((a, b) =>
    a.section === b.section
      ? a.position - b.position
      : a.section - b.section,
  );
  return withPosition;
}

const MATCH_BLOCK = 2 * ROW_HEIGHT + 4;
const R1_STEP = MATCH_BLOCK + R1_MATCH_GAP;
export { R1_STEP, MATCH_BLOCK };

export function buildBracket(pool: PoolPlayer[]): BracketModel {
  const players = orderPool(pool);
  const nodes: BracketNode[] = [];
  const connectors: Connector[] = [];

  const columnX = (index: number) => index * (COL_WIDTH + COL_GAP);
  const halfHeight = 32 * R1_STEP;

  /** Build a section subtree (rounds 1-4) anchored at `baseY`. */
  function buildSection(section: number, baseY: number): BracketNode {
    const sectionPlayers = players.filter((p) => p.section === section);
    const sectionIndex = section - 1; // 0..7
    const half = sectionIndex < 4 ? "top" : "bottom";
    const columnIndex = half === "top" ? 0 : 12;

    // Round 1 leaves: 8 matches of the section.
    let level: BracketNode[] = [];
    for (let m = 0; m < 8; m += 1) {
      const top = sectionPlayers[2 * m];
      const bottom = sectionPlayers[2 * m + 1];
      const center =
        baseY +
        (sectionIndex % 4) * 8 * R1_STEP +
        m * R1_STEP +
        MATCH_BLOCK / 2;
      level.push({
        round: 1,
        columnIndex,
        x: columnX(columnIndex),
        center,
        rows: [
          { player: top, pReach: 1, expected: false },
          { player: bottom, pReach: 1, expected: false },
        ],
        children: null,
        sections: [section],
      });
    }
    nodes.push(...level);

    // Rounds 2-4 within the section.
    for (let round = 2; round <= 4; round += 1) {
      const next: BracketNode[] = [];
      for (let i = 0; i < level.length; i += 2) {
        const a = level[i];
        const b = level[i + 1];
        const col = half === "top" ? columnIndex + (round - 1) : columnIndex - (round - 1);
        const node: BracketNode = {
          round,
          columnIndex: col,
          x: columnX(col),
          center: (a.center + b.center) / 2,
          rows: [
            modalOccupant(
              playersOf(a, players),
              round,
            ),
            modalOccupant(playersOf(b, players), round),
          ],
          children: [a, b],
          sections: [section],
        };
        next.push(node);
        emitConnectors(connectors, node);
      }
      nodes.push(...next);
      level = next;
    }
    return level[0]; // the R4 node = section winner slot
  }

  // Both halves start at the top: the top half occupies the left block of
  // columns, the bottom half the right block, and they meet in the centre
  // columns at half the height.
  const topSections = [1, 2, 3, 4].map((s) => buildSection(s, 0));
  const bottomSections = [5, 6, 7, 8].map((s) => buildSection(s, 0));

  function buildCrossRound(
    round: number,
    columnIndex: number,
    a: BracketNode,
    b: BracketNode,
  ): BracketNode {
    const node: BracketNode = {
      round,
      columnIndex,
      x: columnX(columnIndex),
      center: (a.center + b.center) / 2,
      rows: [
        modalOccupant(playersOf(a, players), round),
        modalOccupant(playersOf(b, players), round),
      ],
      children: [a, b],
      sections: [...a.sections, ...b.sections],
    };
    nodes.push(node);
    emitConnectors(connectors, node);
    return node;
  }

  // Quarterfinals: section winners meet (1v2, 3v4 top; 5v6, 7v8 bottom).
  const qfTopA = buildCrossRound(5, 4, topSections[0], topSections[1]);
  const qfTopB = buildCrossRound(5, 4, topSections[2], topSections[3]);
  const qfBottomA = buildCrossRound(5, 8, bottomSections[0], bottomSections[1]);
  const qfBottomB = buildCrossRound(5, 8, bottomSections[2], bottomSections[3]);

  // Semifinals: top half and bottom half finals.
  const sfTop = buildCrossRound(6, 5, qfTopA, qfTopB);
  const sfBottom = buildCrossRound(6, 7, qfBottomA, qfBottomB);

  // The final.
  buildCrossRound(7, 6, sfTop, sfBottom);

  const champion = modalOccupant(players, 8);

  return {
    width: 13 * COL_WIDTH + 12 * COL_GAP,
    height: halfHeight + HEADER_HEIGHT + 60,
    nodes,
    connectors,
    champion,
    halfHeight,
  };
}

/** All players under a node's subtree (derived from its sections + geometry). */
function playersOf(node: BracketNode, all: BracketPlayer[]): BracketPlayer[] {
  if (node.round === 1) {
    return [node.rows[0].player, node.rows[1].player];
  }
  const [a, b] = node.children!;
  return [...playersOf(a, all), ...playersOf(b, all)];
}

/**
 * Per-side connectors between a node and its children. Works for nodes with
 * both children on one side (normal rounds) and on opposite sides (the final).
 */
function emitConnectors(connectors: Connector[], node: BracketNode) {
  const [a, b] = node.children!;
  for (const child of [a, b]) {
    const onLeft = child.columnIndex < node.columnIndex;
    const childOuter = onLeft ? child.x + COL_WIDTH : child.x;
    const nodeInner = onLeft ? node.x : node.x + COL_WIDTH;
    const midX = (childOuter + nodeInner) / 2;

    connectors.push({ x: childOuter, y: child.center, w: midX - childOuter, horizontal: true });
    connectors.push({
      x: midX,
      y: Math.min(child.center, node.center),
      w: 1,
      h: Math.abs(node.center - child.center),
      horizontal: false,
    });
    connectors.push({ x: midX, y: node.center, w: nodeInner - midX, horizontal: true });
  }
}

/** Background tint class by title probability. */
export function heatBucket(titleChance: number): string {
  if (titleChance < 0.01) return "";
  if (titleChance < 0.05) return "bg-sky-500/[0.07]";
  if (titleChance < 0.15) return "bg-sky-500/[0.14]";
  if (titleChance < 0.3) return "bg-violet-500/[0.16]";
  return "bg-violet-500/[0.28]";
}
