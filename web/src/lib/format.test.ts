import { describe, expect, it } from "vitest";
import { anyTitleChance, pct, roundName, teamExportText } from "@/lib/format";

describe("anyTitleChance", () => {
  it("returns 0 for an all-zero team", () => {
    expect(anyTitleChance([0, 0, 0])).toBe(0);
  });

  it("returns 1 with a certain champion", () => {
    expect(anyTitleChance([0.3, 1, 0.2])).toBe(1);
  });

  it("sums mutually exclusive title chances", () => {
    expect(anyTitleChance([0.5, 0.5])).toBe(1);
    expect(anyTitleChance([0.25, 0.25, 0.1])).toBeCloseTo(0.6);
  });
});

describe("roundName", () => {
  it("maps Sportpools rounds to tennis rounds", () => {
    expect(roundName(1)).toBe("R1");
    expect(roundName(4)).toBe("R4");
    expect(roundName(5)).toBe("QF");
    expect(roundName(7)).toBe("F");
  });
});

describe("pct", () => {
  it("formats as whole percentages by default", () => {
    expect(pct(0.567)).toBe("57%");
    expect(pct(0.567, 1)).toBe("56.7%");
  });
});

describe("teamExportText", () => {
  it("marks the joker and kluns", () => {
    const text = teamExportText(
      [
        { player: "C Alcaraz", seed: 2, role: "player" },
        { player: "T Fritz", seed: 9, role: "joker" },
        { player: "I Buse", seed: 32, role: "kluns" },
      ],
      "T Fritz",
      "I Buse",
      372.7,
    );
    expect(text).toContain("T Fritz (9) ★ joker");
    expect(text).toContain("I Buse (32) ▼ loser");
    expect(text).toContain("C Alcaraz (2)");
    expect(text).toContain("expected 372.7 points");
  });
});
