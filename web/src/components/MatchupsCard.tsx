import { Swords } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { ProbBar } from "@/components/ProbBar";
import { pct, roundName } from "@/lib/format";
import type { Matchup } from "@/types";

/**
 * When your own players can knock each other out: the round they can meet
 * and the probability the match actually happens.
 */
export function MatchupsCard({ matchups }: { matchups: Matchup[] }) {
  const notable = matchups.filter((m) => m.p_meet >= 0.02);

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2 text-base">
          <Swords className="size-4" /> Internal matchups
        </CardTitle>
        <CardDescription>
          When players from your own selection can knock each other out.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-3">
        {notable.length === 0 && (
          <p className="text-sm text-muted-foreground">
            No realistic internal matchups (chance &lt; 2%).
          </p>
        )}
        {notable.slice(0, 10).map((matchup) => (
          <div key={`${matchup.a}-${matchup.b}`} className="space-y-1">
            <div className="flex items-center justify-between gap-2 text-sm">
              <span className="font-medium">
                {matchup.a} <span className="text-muted-foreground">vs</span>{" "}
                {matchup.b}
              </span>
              <span className="flex items-center gap-2">
                <Badge variant="outline">{roundName(matchup.round)}</Badge>
                <span className="font-mono text-xs tabular-nums text-muted-foreground">
                  {pct(matchup.p_meet)}
                </span>
              </span>
            </div>
            <ProbBar value={matchup.p_meet} tone="warn" />
          </div>
        ))}
        {notable.length > 10 && (
          <p className="text-xs text-muted-foreground">
            +{notable.length - 10} less likely matchups
          </p>
        )}
      </CardContent>
    </Card>
  );
}
