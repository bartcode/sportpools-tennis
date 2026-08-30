import { Star } from "lucide-react";
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
import { pct, points, seedLabel } from "@/lib/format";
import { cn } from "@/lib/utils";
import type { JokerOption, ModelPayload } from "@/types";

interface JokerPanelProps {
  model: ModelPayload;
  joker: string;
  inTeam: (player: string) => boolean;
  onMakeJoker: (player: string) => void;
}

/**
 * Joker candidates: one-time bonus (50 - 5*zw) x P(reach round 4).
 */
export function JokerPanel({ model, joker, inTeam, onMakeJoker }: JokerPanelProps) {
  const options: JokerOption[] = model.joker_options.slice(0, 8);

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2 text-base">
          <Star className="size-4 text-chart-2" /> Joker options
        </CardTitle>
        <CardDescription>
          Bonus = (50 − 5×black) × chance of reaching round 4. The joker must be
          in your team.
        </CardDescription>
        <CardAction>
          <Badge variant="secondary">{joker}</Badge>
        </CardAction>
      </CardHeader>
      <CardContent>
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Player</TableHead>
              <TableHead className="text-center">Black</TableHead>
              <TableHead className="text-center">P·R4</TableHead>
              <TableHead className="text-right">Bonus</TableHead>
              <TableHead className="w-24"></TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {options.map((option) => (
              <TableRow
                key={option.player}
                className={cn(option.player === joker && "bg-muted/50")}
              >
                <TableCell className="font-medium">
                  <div className="flex items-center gap-2">
                    {option.player}
                    <Badge variant="outline">{seedLabel(option.seed)}</Badge>
                    {!inTeam(option.player) && (
                      <Badge variant="ghost">not in team</Badge>
                    )}
                  </div>
                </TableCell>
                <TableCell className="text-center font-mono tabular-nums">
                  {option.black}
                </TableCell>
                <TableCell className="text-center font-mono tabular-nums text-muted-foreground">
                  {pct(option.p_r4)}
                </TableCell>
                <TableCell className="text-right font-mono font-semibold tabular-nums">
                  {points(option.joker_bonus)}
                </TableCell>
                <TableCell>
                  <Button
                    size="sm"
                    variant={option.player === joker ? "secondary" : "outline"}
                    className="h-7 w-full text-xs"
                    disabled={option.player === joker}
                    onClick={() => onMakeJoker(option.player)}
                  >
                    {option.player === joker ? "Joker" : "Make joker"}
                  </Button>
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </CardContent>
    </Card>
  );
}
