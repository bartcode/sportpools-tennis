import { useMemo, useState } from "react";
import { Maximize2, Trophy, ZoomIn, ZoomOut } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import {
  buildBracket,
  COL_GAP,
  COL_WIDTH,
  HEADER_HEIGHT,
  heatBucket,
  R1_STEP,
  ROUND_COLUMNS,
  type SlotRow,
} from "@/lib/bracket";
import { pct, points, quarterStyle } from "@/lib/format";
import { cn } from "@/lib/utils";
import type { ModelPayload, Role, TeamMember } from "@/types";

const MIN_ZOOM = 0.4;
const MAX_ZOOM = 1.6;
const ZOOM_STEP = 0.15;

interface BracketViewProps {
  model: ModelPayload;
  members: TeamMember[];
  onSelectPlayer: (player: string) => void;
}

interface RowHighlight {
  role: Role | null;
  jokerCandidate: boolean;
  klunsCandidate: boolean;
}

/**
 * The full 128-player draw as a classic bracket: the top half in the left
 * block of columns, the bottom half in the right block, both starting at the
 * top, with the finals chain in the centre. Zoomable, your selection
 * highlighted with role colours, later rounds showing likely occupants.
 */
export function BracketView({ model, members, onSelectPlayer }: BracketViewProps) {
  const [zoom, setZoom] = useState(0.9);

  const bracket = useMemo(() => buildBracket(model.pool), [model.pool]);

  const highlights = useMemo(() => {
    const roleOf = new Map<string, Role>();
    for (const member of members) roleOf.set(member.player, member.role);

    const selected = new Set(members.map((m) => m.player));
    const jokerCandidates = new Set(
      model.joker_options
        .slice(0, 5)
        .filter((option) => !selected.has(option.player))
        .map((option) => option.player),
    );
    const klunsCandidates = new Set(
      model.kluns_options
        .slice(0, 5)
        .filter((option) => !selected.has(option.kluns))
        .map((option) => option.kluns),
    );

    return (player: string): RowHighlight => ({
      role: roleOf.get(player) ?? null,
      jokerCandidate: jokerCandidates.has(player),
      klunsCandidate: klunsCandidates.has(player),
    });
  }, [members, model.joker_options, model.kluns_options]);

  const sectionBadges = useMemo(() => {
    const badges: { section: number; x: number; y: number }[] = [];
    for (let section = 1; section <= 8; section += 1) {
      const blockIndex = (section - 1) % 4;
      badges.push({
        section,
        x: section <= 4 ? -38 : 12 * (COL_WIDTH + COL_GAP) + COL_WIDTH + 10,
        y: (blockIndex * 8 + 4) * R1_STEP,
      });
    }
    return badges;
  }, []);

  const finalCenter = bracket.halfHeight / 2;

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base">Full draw</CardTitle>
        <CardDescription>
          All 128 players: top half left, bottom half right, finals in the
          centre. Your selection is coloured (joker amber, loser rose, players
          sky); round 2 onward each slot shows its most likely player (dashed =
          projection, ↳ = the favourite from the previous round advancing, so
          stars repeat across rounds by design). Click a player for their
          route to the final. Colour tint = title chance ({model.label}).
        </CardDescription>
        <div className="flex items-center gap-1.5">
          <Button
            variant="outline"
            size="icon-sm"
            disabled={zoom <= MIN_ZOOM + 0.001}
            onClick={() => setZoom((z) => Math.max(MIN_ZOOM, z - ZOOM_STEP))}
          >
            <ZoomOut className="size-3.5" />
          </Button>
          <span className="w-10 text-center font-mono text-xs tabular-nums text-muted-foreground">
            {Math.round(zoom * 100)}%
          </span>
          <Button
            variant="outline"
            size="icon-sm"
            disabled={zoom >= MAX_ZOOM - 0.001}
            onClick={() => setZoom((z) => Math.min(MAX_ZOOM, z + ZOOM_STEP))}
          >
            <ZoomIn className="size-3.5" />
          </Button>
          <Button
            variant="ghost"
            size="sm"
            className="h-7 text-xs"
            onClick={() => setZoom(0.9)}
          >
            <Maximize2 className="size-3.5" /> Reset
          </Button>
        </div>
      </CardHeader>
      <CardContent>
        <div className="mb-3 flex flex-wrap items-center gap-3 text-xs text-muted-foreground">
          <span className="flex items-center gap-1.5">
            <span className="size-3 rounded border border-sky-500/60 bg-sky-500/20" />
            selection
          </span>
          <span className="flex items-center gap-1.5">
            <span className="size-3 rounded border border-amber-500/60 bg-amber-500/20" />
            joker · candidate
          </span>
          <span className="flex items-center gap-1.5">
            <span className="size-3 rounded border border-rose-500/60 bg-rose-500/20" />
            loser · candidate
          </span>
          <span className="flex items-center gap-1.5">
            <span className="size-3 rounded bg-sky-500/30" />
            title chance
          </span>
          <span className="flex items-center gap-1.5">
            <span className="size-3 rounded bg-violet-500/40" />
            high title chance
          </span>
        </div>

        <div className="max-h-[78vh] overflow-auto rounded-lg border border-border bg-card/60">
          <div
            style={{
              width: bracket.width * zoom,
              height: bracket.height * zoom,
            }}
          >
            <div
              className="relative"
              style={{
                width: bracket.width,
                height: bracket.height,
                transform: `scale(${zoom})`,
                transformOrigin: "top left",
              }}
            >
              {/* Column headers */}
              <div
                className="relative z-10 border-b border-border bg-card/95"
                style={{ height: HEADER_HEIGHT }}
              >
                {ROUND_COLUMNS.map((label, index) => (
                  <span
                    key={index}
                    className="absolute top-0 flex h-full items-center justify-center text-[10px] font-semibold tracking-wide text-muted-foreground uppercase"
                    style={{
                      left: index * (COL_WIDTH + COL_GAP),
                      width: COL_WIDTH,
                    }}
                  >
                    {label}
                  </span>
                ))}
              </div>

              {/* Canvas */}
              <div
                className="relative"
                style={{ height: bracket.height - HEADER_HEIGHT }}
              >
                {bracket.connectors.map((connector, index) =>
                  connector.horizontal ? (
                    <div
                      key={`h${index}`}
                      className="absolute border-t border-border"
                      style={{
                        left: connector.x,
                        top: connector.y,
                        width: connector.w,
                      }}
                    />
                  ) : (
                    <div
                      key={`v${index}`}
                      className="absolute border-l border-border"
                      style={{
                        left: connector.x,
                        top: connector.y,
                        height: connector.h,
                      }}
                    />
                  ),
                )}

                {sectionBadges.map(({ section, x, y }) => (
                  <Badge
                    key={section}
                    variant="outline"
                    className={cn(
                      "absolute px-1.5 text-[10px]",
                      quarterStyle(section),
                    )}
                    style={{ left: x, top: y - 10 }}
                  >
                    S{section}
                  </Badge>
                ))}

                {bracket.nodes.map((node) => {
                  const feeders = node.children
                    ? node.children.map((child) =>
                        child.rows.map((row) => row.player.player),
                      )
                    : null;
                  return node.rows.map((row, side) => (
                    <BracketRow
                      key={`${node.columnIndex}-${node.round}-${node.center}-${side}`}
                      row={row}
                      nodeX={node.x}
                      nodeCenter={node.center}
                      side={side}
                      continuation={
                        feeders !== null &&
                        feeders[side].includes(row.player.player)
                      }
                      highlight={highlights(row.player.player)}
                      onSelectPlayer={onSelectPlayer}
                    />
                  ));
                })}

                {/* champion, below the final */}
                <div
                  className="absolute flex items-center gap-2 rounded-lg border border-amber-500/50 bg-amber-500/10 px-3 py-2 shadow-sm"
                  style={{
                    left: 6 * (COL_WIDTH + COL_GAP),
                    width: COL_WIDTH,
                    top: finalCenter + 64,
                  }}
                >
                  <Trophy className="size-4 shrink-0 text-amber-500" />
                  <div className="min-w-0">
                    <p className="truncate text-xs font-semibold">
                      {bracket.champion.player.player}
                    </p>
                    <p className="font-mono text-[10px] tabular-nums text-muted-foreground">
                      champion {pct(bracket.champion.pReach, 1)}
                    </p>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </CardContent>
    </Card>
  );
}

function BracketRow({
  row,
  nodeX,
  nodeCenter,
  side,
  continuation,
  highlight,
  onSelectPlayer,
}: {
  row: SlotRow;
  nodeX: number;
  nodeCenter: number;
  side: number;
  continuation: boolean;
  highlight: RowHighlight;
  onSelectPlayer: (player: string) => void;
}) {
  const player = row.player;
  const heat = heatBucket(player.probs[6] ?? 0);
  const top = side === 0 ? nodeCenter - 24 - 1 : nodeCenter + 1;

  return (
    <button
      type="button"
      onClick={() => onSelectPlayer(player.player)}
      title={`${player.player}${player.seed > 0 ? ` (#${player.seed})` : ""} · ${player.black} black · E ${points(player.potency)} pt · P(R4) ${pct(player.probs[2] ?? 0)} · P(title) ${pct(player.probs[6] ?? 0)}${row.expected ? ` · expected here: ${pct(row.pReach)}` : ""}`}
      className={cn(
        "absolute flex h-6 items-center gap-1 overflow-hidden rounded-md border px-1.5 text-left text-xs transition-colors hover:border-ring",
        heat,
        highlight.role === "joker" && "border-amber-500/70 bg-amber-500/[0.12]",
        highlight.role === "kluns" && "border-rose-500/70 bg-rose-500/[0.12]",
        highlight.role === "player" && "border-sky-500/70 bg-sky-500/[0.12]",
        !highlight.role && row.expected && "border-dashed border-border",
        !highlight.role && !row.expected && "border-transparent",
        row.expected && "italic",
        continuation && "opacity-75",
      )}
      style={{ left: nodeX, top, width: COL_WIDTH }}
    >
      {continuation && (
        <span className="shrink-0 text-[10px] text-muted-foreground">↳</span>
      )}
      <span
        className={cn(
          "truncate font-medium",
          continuation && "text-muted-foreground",
        )}
      >
        {player.player}
      </span>
      {player.seed > 0 && (
        <span className="shrink-0 font-mono text-[10px] text-muted-foreground">
          {player.seed}
        </span>
      )}
      {row.expected && (
        <span className="ml-auto shrink-0 font-mono text-[10px] tabular-nums text-muted-foreground">
          {pct(row.pReach)}
        </span>
      )}
      {highlight.jokerCandidate && (
        <span
          className="absolute top-1 right-1 size-1.5 rounded-full bg-amber-500"
          title="Joker candidate"
        />
      )}
      {highlight.klunsCandidate && (
        <span
          className="absolute top-1 right-1 size-1.5 rounded-full bg-rose-500"
          title="Loser candidate"
        />
      )}
    </button>
  );
}
