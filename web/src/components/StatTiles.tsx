import { Trophy, Target, LayoutGrid, Coins } from "lucide-react";
import { Card, CardContent } from "@/components/ui/card";
import { anyTitleChance } from "@/lib/format";
import { useCountUp } from "@/lib/useCountUp";
import { cn } from "@/lib/utils";
import type { ModelPayload, TeamMember } from "@/types";
import type { EvaluateResult } from "@/types";

interface StatTilesProps {
  model: ModelPayload;
  members: TeamMember[];
  evaluation: EvaluateResult | undefined;
  /** Team EV is taken from the evaluation when editing, else from the model. */
  expectedPoints: number;
}

function Tile({
  label,
  value,
  sub,
  icon,
  tone,
  className,
}: {
  label: string;
  value: React.ReactNode;
  sub?: string;
  icon: React.ReactNode;
  tone: string;
  className?: string;
}) {
  return (
    <Card className={cn("animate-rise py-4", className)}>
      <CardContent className="flex items-center gap-3 px-4">
        <div
          className={cn(
            "flex size-9 shrink-0 items-center justify-center rounded-lg bg-gradient-to-br text-white shadow-sm",
            tone,
          )}
        >
          {icon}
        </div>
        <div className="min-w-0">
          <p className="text-xs font-medium tracking-wide text-muted-foreground uppercase">
            {label}
          </p>
          <p className="font-mono text-2xl leading-tight font-semibold tabular-nums">
            {value}
          </p>
          {sub && (
            <p className="truncate text-xs text-muted-foreground">{sub}</p>
          )}
        </div>
      </CardContent>
    </Card>
  );
}

function AnimatedNumber({
  value,
  format,
}: {
  value: number;
  format: (value: number) => string;
}) {
  const animated = useCountUp(value);
  return <>{format(animated)}</>;
}

/**
 * Headline statistics for the active model and current selection.
 */
export function StatTiles({ model, members, evaluation, expectedPoints }: StatTilesProps) {
  const poolByPlayer = new Map(model.pool.map((p) => [p.player, p]));

  const titleChance = anyTitleChance(
    members.map((m) => poolByPlayer.get(m.player)?.probs[6] ?? 0),
  );
  const reachR4 = members
    .filter((m) => m.role !== "kluns")
    .reduce((acc, m) => acc + (poolByPlayer.get(m.player)?.probs[2] ?? 0), 0);
  const quarters = new Set(
    members
      .map((m) => poolByPlayer.get(m.player)?.section ?? 0)
      .filter((s) => s > 0)
      .map((s) => Math.ceil(s / 2)),
  ).size;

  const blackUsed = evaluation
    ? evaluation.black_points.used
    : model.team.players
        .filter((p) => p.role !== "kluns")
        .reduce((acc, p) => acc + p.black, 0);
  const blackLimit = evaluation
    ? evaluation.black_points.limit
    : 20 + (model.team.players.find((p) => p.role === "kluns")?.black ?? 0);

  return (
    <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
      <Tile
        className="delay-1"
        label="Verwachte punten"
        value={expectedPoints.toFixed(1)}
        sub={evaluation && !evaluation.valid ? "selectie is niet geldig" : model.label}
        icon={<Target className="size-4" />}
        tone="from-sky-500 to-blue-600"
      />
      <Tile
        className="delay-2"
        label="Titelkans in team"
        value={<AnimatedNumber value={titleChance * 100} format={(v) => `${v.toFixed(1)}%`} />}
        sub="kans dat iemand wint"
        icon={<Trophy className="size-4" />}
        tone="from-amber-400 to-orange-500"
      />
      <Tile
        className="delay-3"
        label="Verwacht naar ronde 4"
        value={<AnimatedNumber value={reachR4} format={(v) => v.toFixed(1)} />}
        sub={`${quarters}/4 kwarten gedekt`}
        icon={<LayoutGrid className="size-4" />}
        tone="from-emerald-400 to-teal-600"
      />
      <Tile
        className="delay-4"
        label="Zwarte punten"
        value={`${blackUsed}/${blackLimit}`}
        sub={
          evaluation && evaluation.black_points.kluns_recycled > 0
            ? `${evaluation.black_points.kluns_recycled} teruggewonnen via kluns`
            : undefined
        }
        icon={<Coins className="size-4" />}
        tone={cn(
          "from-rose-400 to-red-600",
          blackUsed > blackLimit && "from-red-500 to-red-700",
        )}
      />
    </div>
  );
}
