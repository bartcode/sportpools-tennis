import { ArrowDownRight, ArrowUpRight, CheckCircle2, GitCompareArrows } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { pct, points, quarterStyle, seedLabel } from "@/lib/format";
import { cn } from "@/lib/utils";
import type { PredictionResult, TeamPlayer } from "@/types";

function RoleIcon({ role }: { role: string }) {
  if (role === "joker") return <span title="Joker">★</span>;
  if (role === "kluns") return <span title="Kluns">▼</span>;
  return null;
}

function PlayerChip({ player }: { player: TeamPlayer }) {
  return (
    <div
      className={cn(
        "animate-rise flex items-center gap-2 rounded-lg border bg-card px-2.5 py-1.5 text-sm shadow-sm",
        player.role === "joker" && "border-amber-500/40",
        player.role === "kluns" && "border-rose-500/40",
      )}
    >
      <span
        className={cn(
          "size-2 shrink-0 rounded-full",
          player.role === "joker" && "bg-amber-500",
          player.role === "kluns" && "bg-rose-500",
          player.role === "player" && "bg-sky-500",
        )}
        title={player.role}
      />
      <span className="font-medium">{player.player}</span>
      {player.role !== "player" && (
        <span className="text-xs text-muted-foreground">
          <RoleIcon role={player.role} />
        </span>
      )}
      <Badge variant="outline" className="px-1.5 text-[10px]">
        {seedLabel(player.seed)}
      </Badge>
      {player.black > 0 && (
        <Badge variant="ghost" className="px-1.5 text-[10px]">
          {player.black} zwart
        </Badge>
      )}
      {player.section > 0 && (
        <Badge
          variant="outline"
          className={cn("px-1.5 text-[10px]", quarterStyle(player.section))}
        >
          S{player.section}
        </Badge>
      )}
    </div>
  );
}

interface DiffRowProps {
  player: TeamPlayer;
  entering: boolean;
}

function DiffRow({ player, entering }: DiffRowProps) {
  return (
    <div className="animate-rise flex items-center justify-between gap-2 rounded-lg border border-dashed px-3 py-2">
      <div className="flex min-w-0 items-center gap-2 text-sm">
        {entering ? (
          <ArrowDownRight className="size-4 shrink-0 text-emerald-500" />
        ) : (
          <ArrowUpRight className="size-4 shrink-0 text-rose-500" />
        )}
        <span className="truncate font-medium">{player.player}</span>
        <Badge variant="outline" className="px-1.5 text-[10px]">
          {seedLabel(player.seed)}
        </Badge>
        {player.role !== "player" && (
          <Badge
            variant="outline"
            className={cn(
              "px-1.5 text-[10px]",
              player.role === "joker"
                ? "border-amber-500/40 text-amber-600 dark:text-amber-300"
                : "border-rose-500/40 text-rose-600 dark:text-rose-300",
            )}
          >
            <RoleIcon role={player.role} /> {player.role}
          </Badge>
        )}
      </div>
      <div className="shrink-0 text-right">
        <p className="font-mono text-sm font-semibold tabular-nums">
          {points(player.potency)}
        </p>
        <p className="font-mono text-[10px] tabular-nums text-muted-foreground">
          R4 {pct(player.probs[2])} · W {pct(player.probs[6])}
        </p>
      </div>
    </div>
  );
}

/**
 * Model comparison: robust picks shared by both models, and the players
 * each model would add or drop relative to the other.
 */
export function CompareView({ result }: { result: PredictionResult }) {
  const surfaces = result.surfaces;
  if (surfaces.length < 2) {
    return (
      <p className="text-sm text-muted-foreground">
        Draai een voorspelling met meerdere ratingmodellen (hardcourt- en
        totaal-Elo) om te vergelijken.
      </p>
    );
  }

  const [aKey, bKey] = surfaces;
  const a = result.models[aKey];
  const b = result.models[bKey];

  const namesA = new Set(a.team.players.map((p) => p.player));
  const namesB = new Set(b.team.players.map((p) => p.player));
  const shared = a.team.players.filter((p) => namesB.has(p.player));
  const onlyA = a.team.players.filter((p) => !namesB.has(p.player));
  const onlyB = b.team.players.filter((p) => !namesA.has(p.player));

  return (
    <div className="space-y-5">
      {/* Summary */}
      <div className="grid grid-cols-3 gap-3">
        <div className="rounded-xl border bg-gradient-to-br from-sky-500/10 to-blue-600/10 p-4 text-center">
          <p className="text-xs font-medium tracking-wide text-muted-foreground uppercase">
            {a.label}
          </p>
          <p className="font-mono text-2xl font-semibold tabular-nums">
            {points(a.team.expected_points)}
          </p>
          <p className="text-xs text-muted-foreground">verwachte punten</p>
        </div>
        <div className="rounded-xl border bg-gradient-to-br from-violet-500/10 to-fuchsia-500/10 p-4 text-center">
          <p className="text-xs font-medium tracking-wide text-muted-foreground uppercase">
            Overlap
          </p>
          <p className="font-mono text-2xl font-semibold tabular-nums">
            {shared.length}/{result.count}
          </p>
          <p className="flex items-center justify-center gap-1 text-xs text-muted-foreground">
            <CheckCircle2 className="size-3 text-emerald-500" /> robuuste keuzes
          </p>
        </div>
        <div className="rounded-xl border bg-gradient-to-br from-emerald-500/10 to-teal-500/10 p-4 text-center">
          <p className="text-xs font-medium tracking-wide text-muted-foreground uppercase">
            {b.label}
          </p>
          <p className="font-mono text-2xl font-semibold tabular-nums">
            {points(b.team.expected_points)}
          </p>
          <p className="text-xs text-muted-foreground">verwachte punten</p>
        </div>
      </div>

      {/* Robust picks */}
      <div>
        <h3 className="mb-2 flex items-center gap-2 text-sm font-semibold">
          <CheckCircle2 className="size-4 text-emerald-500" />
          In beide modellen ({shared.length})
        </h3>
        <div className="flex flex-wrap gap-2">
          {shared
            .sort((x, y) => y.potency - x.potency)
            .map((player) => (
              <PlayerChip key={player.player} player={player} />
            ))}
        </div>
      </div>

      {/* Differences */}
      {onlyA.length === 0 && onlyB.length === 0 ? (
        <div className="rounded-xl border border-emerald-500/30 bg-emerald-500/5 p-4 text-sm text-emerald-700 dark:text-emerald-300">
          Beide modellen kiezen exact dezelfde selectie — je team is volledig
          robuust tegen de keuze van ratingmodel.
        </div>
      ) : (
        <div className="grid gap-4 md:grid-cols-2">
          {[
            { model: a, only: onlyA, counterpart: b.label },
            { model: b, only: onlyB, counterpart: a.label },
          ].map(({ model, only, counterpart }) => (
            <Card key={model.surface} className="animate-rise">
              <CardHeader>
                <CardTitle className="flex items-center gap-2 text-base">
                  <GitCompareArrows className="size-4 text-violet-500" />
                  Extra in {model.label}
                </CardTitle>
                <CardDescription>
                  {only.length === 0
                    ? `Kiest geen extra spelers; verschil zit bij ${counterpart}.`
                    : `${only.length} keuze(s) die ${counterpart} niet maakt.`}
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-2">
                {only
                  .sort((x, y) => y.potency - x.potency)
                  .map((player) => (
                    <DiffRow key={player.player} player={player} entering />
                  ))}
              </CardContent>
            </Card>
          ))}
        </div>
      )}
    </div>
  );
}
