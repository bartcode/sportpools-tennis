import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
} from "@/components/ui/sheet";
import { Badge } from "@/components/ui/badge";
import { Separator } from "@/components/ui/separator";
import { ProbBar } from "@/components/ProbBar";
import { pct, points, roundName, seedLabel } from "@/lib/format";
import { cn } from "@/lib/utils";
import type { ModelPayload } from "@/types";

interface PlayerSheetProps {
  player: string | null;
  model: ModelPayload | null;
  onClose: () => void;
}

/**
 * Per-player drawer: headline stats and the most probable route to the final,
 * round by round with the likeliest opponent.
 */
export function PlayerSheet({ player, model, onClose }: PlayerSheetProps) {
  const pool = player && model ? model.pool.find((p) => p.player === player) : null;
  const route = player && model ? model.routes[player] : null;

  return (
    <Sheet open={player !== null} onOpenChange={(open) => !open && onClose()}>
      <SheetContent side="right" className="w-full overflow-y-auto sm:max-w-md">
        {pool ? (
          <>
            <SheetHeader>
              <SheetTitle className="flex items-center gap-2">
                {pool.player}
                <Badge variant="outline">{seedLabel(pool.seed)}</Badge>
                {pool.black > 0 && (
                  <Badge variant="secondary">{pool.black} zwart</Badge>
                )}
              </SheetTitle>
              <SheetDescription>
                Verwachte punten {points(pool.potency)} · jokerbonus{" "}
                {points(pool.joker_bonus)} · klunsstraf{" "}
                {points(pool.kluns_penalty)}
              </SheetDescription>
            </SheetHeader>

            <div className="space-y-4 px-4 pb-8">
              <div className="grid grid-cols-4 gap-2">
                {pool.probs.slice(0, 7).map((prob, index) => (
                  <div
                    key={index}
                    className="rounded-lg border border-border p-2 text-center"
                  >
                    <p className="text-[10px] font-medium text-muted-foreground">
                      {roundName(index + 1)}
                    </p>
                    <p className="font-mono text-sm font-semibold tabular-nums">
                      {pct(prob)}
                    </p>
                  </div>
                ))}
              </div>

              <Separator />

              <div>
                <h3 className="mb-3 text-sm font-semibold">
                  Meest waarschijnlijke route naar de finale
                </h3>
                <ol className="space-y-3">
                  {(route ?? []).map((step) => (
                    <li key={step.round} className="flex gap-3">
                      <div className="mt-0.5 flex h-7 w-9 shrink-0 items-center justify-center rounded-md bg-muted font-mono text-xs font-semibold">
                        {roundName(step.round)}
                      </div>
                      <div className="min-w-0 flex-1 space-y-1">
                        <div className="flex items-center justify-between gap-2">
                          <span className="truncate text-sm font-medium">
                            {step.opponent}
                          </span>
                          <span className="shrink-0 font-mono text-xs tabular-nums text-muted-foreground">
                            ontmoet {pct(step.p_meet)}
                          </span>
                        </div>
                        <div className="flex flex-wrap gap-x-4 gap-y-0.5 text-xs text-muted-foreground">
                          <span>
                            tegenstander bereikt ronde:{" "}
                            <span className="font-mono tabular-nums">
                              {pct(step.p_opponent)}
                            </span>
                          </span>
                          {step.p_beat !== undefined && (
                            <span>
                              winst:{" "}
                              <span
                                className={cn(
                                  "font-mono font-semibold tabular-nums",
                                  step.p_beat >= 0.5
                                    ? "text-foreground"
                                    : "text-destructive",
                                )}
                              >
                                {pct(step.p_beat)}
                              </span>
                            </span>
                          )}
                          <span>
                            overleeft:{" "}
                            <span className="font-mono tabular-nums">
                              {pct(step.p_reach)}
                            </span>
                          </span>
                        </div>
                        <ProbBar value={step.p_reach} />
                      </div>
                    </li>
                  ))}
                </ol>
              </div>
            </div>
          </>
        ) : (
          <div className="p-4 text-sm text-muted-foreground">
            Speler niet gevonden.
          </div>
        )}
      </SheetContent>
    </Sheet>
  );
}
