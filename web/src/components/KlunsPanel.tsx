import { TrendingDown } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardAction,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import { points } from "@/lib/format";
import { cn } from "@/lib/utils";
import type { KlunsOption, ModelPayload } from "@/types";

interface KlunsPanelProps {
  model: ModelPayload;
  kluns: string;
  inTeam: (player: string) => boolean;
  onMakeKluns: (player: string) => void;
}

/**
 * Kluns candidates, ranked by the total team value when forced as kluns
 * (the whole team is re-optimised per candidate by the backend).
 */
export function KlunsPanel({ model, kluns, inTeam, onMakeKluns }: KlunsPanelProps) {
  const options: KlunsOption[] = model.kluns_options.slice(0, 8);
  const best = options[0]?.team_ev;

  if (options.length === 0) {
    return (
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2 text-base">
            <TrendingDown className="size-4 text-destructive" /> Loser options
          </CardTitle>
          <CardDescription>
            No loser alternatives available for this model yet.
          </CardDescription>
        </CardHeader>
      </Card>
    );
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2 text-base">
          <TrendingDown className="size-4 text-destructive" /> Loser options
        </CardTitle>
        <CardDescription>
          Penalty = −10 per round survived (max 50). The loser's black points
          are recycled into your budget.
        </CardDescription>
        <CardAction>
          <Badge variant="destructive">{kluns}</Badge>
        </CardAction>
      </CardHeader>
      <CardContent>
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Player</TableHead>
              <TableHead className="text-center">Black</TableHead>
              <TableHead className="text-right">Penalty</TableHead>
              <TableHead className="text-right">Team EV</TableHead>
              <TableHead className="w-24"></TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {options.map((option) => {
              const delta = option.team_ev - (best ?? option.team_ev);
              return (
                <TableRow
                  key={option.kluns}
                  className={cn(option.kluns === kluns && "bg-muted/50")}
                >
                  <TableCell className="font-medium">
                    <div className="flex items-center gap-2">
                      {option.kluns}
                      {option.black > 0 && (
                        <Tooltip>
                          <TooltipTrigger asChild>
                            <Badge variant="secondary">
                              +{option.black} budget
                            </Badge>
                          </TooltipTrigger>
                          <TooltipContent>
                            His {option.black} black point(s) are added to
                            your budget: a weaker kluns, but a stronger team.
                          </TooltipContent>
                        </Tooltip>
                      )}
                      {!inTeam(option.kluns) && (
                        <Badge variant="ghost">not in team</Badge>
                      )}
                    </div>
                  </TableCell>
                  <TableCell className="text-center font-mono tabular-nums">
                    {option.black}
                  </TableCell>
                  <TableCell className="text-right font-mono tabular-nums text-destructive">
                    {points(option.e_penalty)}
                  </TableCell>
                  <TableCell className="text-right font-mono font-semibold tabular-nums">
                    {points(option.team_ev)}
                    {delta < -0.01 && (
                      <span className="ml-1 text-xs font-normal text-muted-foreground">
                        {delta.toFixed(1)}
                      </span>
                    )}
                  </TableCell>
                  <TableCell>
                    <Button
                      size="sm"
                      variant={option.kluns === kluns ? "secondary" : "outline"}
                      className="h-7 w-full text-xs"
                      disabled={option.kluns === kluns}
                      onClick={() => onMakeKluns(option.kluns)}
                    >
                      {option.kluns === kluns ? "Loser" : "Make loser"}
                    </Button>
                  </TableCell>
                </TableRow>
              );
            })}
          </TableBody>
        </Table>
      </CardContent>
    </Card>
  );
}
