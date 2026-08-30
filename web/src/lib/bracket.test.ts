import { describe, expect, it } from "vitest";
import {
  buildBracket,
  COL_WIDTH,
  heatBucket,
  orderPool,
  ROUND_COLUMNS,
} from "@/lib/bracket";
import type { PoolPlayer } from "@/types";

/** Synthetic 128-player pool: section s favourite has the highest probs. */
function syntheticPool(): PoolPlayer[] {
  const players: PoolPlayer[] = [];
  for (let section = 1; section <= 8; section += 1) {
    for (let position = 0; position < 16; position += 1) {
      // Earlier sections and positions are stronger; avoids exact prob ties.
      const strength =
        (128 * 2 - position - (section - 1) * 2) / (128 * 2);
      players.push({
        player: `P${section}-${position}`,
        seed: position === 0 ? section : 0,
        black: position === 0 ? 5 : 0,
        section,
        position,
        potency: strength * 30,
        joker_bonus: strength * 20,
        kluns_penalty: -strength * 10,
        probs: Array.from({ length: 7 }, (_, i) =>
          Math.max(0, Math.min(1, strength ** (i + 1) * 0.9)),
        ),
      });
    }
  }
  return players;
}

describe("orderPool", () => {
  it("orders by section then position", () => {
    const ordered = orderPool(syntheticPool().slice().reverse());
    expect(ordered).toHaveLength(128);
    expect(ordered[0].player).toBe("P1-0");
    expect(ordered[15].player).toBe("P1-15");
    expect(ordered[16].player).toBe("P2-0");
    expect(ordered[127].player).toBe("P8-15");
  });
});

describe("buildBracket", () => {
  const bracket = buildBracket(syntheticPool());

  it("creates 13 columns for rounds R1 through the final", () => {
    expect(ROUND_COLUMNS).toHaveLength(13);
    expect(ROUND_COLUMNS[6]).toBe("FINAL");
  });

  it("has 64 round-1 matches with real players and certain occupancy", () => {
    const r1 = bracket.nodes.filter((n) => n.round === 1);
    expect(r1).toHaveLength(64);
    for (const node of r1) {
      expect(node.rows[0].pReach).toBe(1);
      expect(node.rows[0].expected).toBe(false);
    }
  });

  it("starts both halves at the same vertical position", () => {
    const r1 = bracket.nodes.filter((n) => n.round === 1);
    const leftFirst = r1.find((n) => n.columnIndex === 0)!;
    const rightFirst = r1.find((n) => n.columnIndex === 12)!;
    expect(rightFirst.center).toBeCloseTo(leftFirst.center, 6);

    // ...and both halves span the same height
    const leftLast = r1.filter((n) => n.columnIndex === 0).at(-1)!;
    const rightLast = r1.filter((n) => n.columnIndex === 12).at(-1)!;
    expect(rightLast.center).toBeCloseTo(leftLast.center, 6);
  });

  it("places later-round nodes at the mean of their feeders", () => {
    const later = bracket.nodes.filter((n) => n.round > 1 && n.children);
    for (const node of later) {
      const [a, b] = node.children!;
      expect(node.center).toBeCloseTo((a.center + b.center) / 2, 6);
    }
  });

  it("keeps every node inside the canvas", () => {
    for (const node of bracket.nodes) {
      expect(node.x).toBeGreaterThanOrEqual(0);
      expect(node.x).toBeLessThan(bracket.width);
      expect(node.center).toBeGreaterThan(0);
      expect(node.center).toBeLessThan(bracket.height);
    }
  });

  it("picks the strongest sub-bracket player as the modal occupant", () => {
    // QF top-A merges sections 1 and 2; their position-0 players dominate.
    const qf = bracket.nodes.filter((n) => n.round === 5);
    expect(qf).toHaveLength(4);
    const names = qf.flatMap((node) => node.rows.map((row) => row.player.player));
    for (const section of [1, 2, 3, 4, 5, 6, 7, 8]) {
      expect(names).toContain(`P${section}-0`);
    }
  });

  it("has exactly one final with modal occupants from both halves", () => {
    const finals = bracket.nodes.filter((n) => n.round === 7);
    expect(finals).toHaveLength(1);
    const halfOf = (player: string) =>
      Number(player.slice(1).split("-")[0]) <= 4;
    const [rowA, rowB] = finals[0].rows;
    expect(halfOf(rowA.player.player)).not.toBe(halfOf(rowB.player.player));
  });

  it("draws connectors for every non-leaf node (3 segments per side)", () => {
    const nonLeaf = bracket.nodes.filter((n) => n.children).length;
    expect(nonLeaf).toBe(64 - 1); // every match except the final produces a next round... 
    expect(bracket.connectors.length).toBeGreaterThan(120);
  });

  it("positions the final in the centre column", () => {
    const finals = bracket.nodes.filter((n) => n.round === 7);
    expect(finals[0].x).toBe(6 * (COL_WIDTH + 26));
  });
});

describe("heatBucket", () => {
  it("maps title chances to tint buckets", () => {
    expect(heatBucket(0.005)).toBe("");
    expect(heatBucket(0.02)).toContain("bg-sky-500");
    expect(heatBucket(0.4)).toContain("bg-violet-500");
  });
});
