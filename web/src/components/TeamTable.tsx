import { Lock, Star, TrendingDown } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import { ProbBar } from "@/components/ProbBar";
import { pct, points, quarterStyle, seedLabel } from "@/lib/format";
import { cn } from "@/lib/utils";
import type { EvaluateResult, ModelPayload, Role, TeamMember } from "@/types";

interface TeamTableProps {
  model: ModelPayload;
  members: TeamMember[];
  evaluation: EvaluateResult | undefined;
  onSetRole: (player: string, role: Role) => void;
  onToggleLock: (player: string) => void;
  onSelectPlayer: (player: string) => void;
  onOpenBench: (replacePlayer: string) => void;
}

const probHeads = ["P·R4", "P·QF", "P·SF", "P·F", "P·W"];

/**
 * The editable selection: roles, contributions and round probabilities.
 */
export function TeamTable({
  model,
  members,
  evaluation,
  onSetRole,
  onToggleLock,
  onSelectPlayer,
  onOpenBench,
}: TeamTableProps) {
  const poolByPlayer = new Map(model.pool.map((p) => [p.player, p]));
  const contribution = new Map(
    (evaluation?.players ?? []).map((row) => [row.player, row.contribution]),
  );

  const rows = [...members].sort((a, b) => {
    const order = { kluns: 2, joker: 1, player: 0 } as const;
    return order[a.role] - order[b.role];
  });

  return (
    <div className="overflow-x-auto">
      <Table>
        <TableHeader>
          <TableRow className="hover:bg-transparent">
            <TableHead className="w-9"></TableHead>
            <TableHead>Speler</TableHead>
            <TableHead className="text-center">Zwart</TableHead>
            <TableHead className="w-28">Rol</TableHead>
            <TableHead className="text-right">Punten</TableHead>
            {probHeads.map((head) => (
              <TableHead key={head} className="w-16 text-center">
                {head}
              </TableHead>
            ))}
            <TableHead className="w-20"></TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {rows.map((member) => {
            const pool = poolByPlayer.get(member.player);
            const probs = pool?.probs ?? [];
            const contrib = contribution.get(member.player) ?? pool?.potency ?? 0;
            const isKluns = member.role === "kluns";
            const isJoker = member.role === "joker";

            return (
              <TableRow
                key={member.player}
                className={cn(
                  "animate-rise cursor-pointer",
                  isJoker && "bg-amber-500/[0.05] hover:bg-amber-500/[0.09]",
                  isKluns && "bg-rose-500/[0.05] hover:bg-rose-500/[0.09]",
                )}
                onClick={() => onSelectPlayer(member.player)}
              >
                <TableCell onClick={(e) => e.stopPropagation()}>
                  <Tooltip>
                    <TooltipTrigger asChild>
                      <Button
                        variant="ghost"
                        size="icon-sm"
                        onClick={() => onToggleLock(member.player)}
                        className={cn(
                          "h-6 w-6",
                          member.locked
                            ? "text-primary"
                            : "text-muted-foreground/40",
                        )}
                      >
                        <Lock className="size-3.5" />
                      </Button>
                    </TooltipTrigger>
                    <TooltipContent>
                      {member.locked ? "Vastzetten op" : "Vastzetten"} (gebruikt
                      bij her-optimaliseren)
                    </TooltipContent>
                  </Tooltip>
                </TableCell>
                <TableCell className="font-medium">
                  <div className="flex items-center gap-1.5">
                    <span>{member.player}</span>
                    {isJoker && (
                      <Badge className="gap-1 border-amber-500/40 bg-amber-500/15 text-amber-700 dark:text-amber-300">
                        <Star className="size-3" /> Joker
                      </Badge>
                    )}
                    {isKluns && (
                      <Badge className="gap-1 border-rose-500/40 bg-rose-500/15 text-rose-700 dark:text-rose-300">
                        <TrendingDown className="size-3" /> Kluns
                      </Badge>
                    )}
                    {member.locked && (
                      <Lock className="size-3 text-primary" />
                    )}
                  </div>
                  <div className="mt-0.5 flex items-center gap-1.5">
                    <span className="text-xs text-muted-foreground">
                      {seedLabel(pool?.seed ?? 0)}
                    </span>
                    {pool && pool.section > 0 && (
                      <Badge
                        variant="outline"
                        className={cn("px-1.5 text-[10px]", quarterStyle(pool.section))}
                      >
                        S{pool.section}
                      </Badge>
                    )}
                  </div>
                </TableCell>
                <TableCell className="text-center font-mono tabular-nums">
                  {pool?.black ?? "–"}
                </TableCell>
                <TableCell onClick={(e) => e.stopPropagation()}>
                  <Select
                    value={member.role}
                    onValueChange={(value) =>
                      onSetRole(member.player, value as Role)
                    }
                  >
                    <SelectTrigger size="sm" className="h-7 w-24 text-xs">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="player">Speler</SelectItem>
                      <SelectItem value="joker">Joker</SelectItem>
                      <SelectItem value="kluns">Kluns</SelectItem>
                    </SelectContent>
                  </Select>
                </TableCell>
                <TableCell
                  className={cn(
                    "text-right font-mono font-semibold tabular-nums",
                    isKluns && contrib < 0 && "text-destructive",
                    isJoker && "text-amber-600 dark:text-amber-300",
                  )}
                >
                  {points(contrib)}
                </TableCell>
                {[2, 3, 4, 5, 6].map((index) => (
                  <TableCell key={index} className="px-2">
                    <div className="flex flex-col items-center gap-0.5">
                      <span className="font-mono text-[10px] tabular-nums text-muted-foreground">
                        {probs[index] !== undefined ? pct(probs[index]) : "–"}
                      </span>
                      <ProbBar
                        value={probs[index] ?? 0}
                        tone={
                          isKluns
                            ? "kluns"
                            : index === 6
                              ? "title"
                              : isJoker && index === 2
                                ? "joker"
                                : "default"
                        }
                      />
                    </div>
                  </TableCell>
                ))}
                <TableCell onClick={(e) => e.stopPropagation()}>
                  <Button
                    variant="outline"
                    size="sm"
                    className="h-7 text-xs"
                    onClick={() => onOpenBench(member.player)}
                  >
                    Wissel
                  </Button>
                </TableCell>
              </TableRow>
            );
          })}
        </TableBody>
      </Table>
      <p className="mt-2 px-2 text-xs text-muted-foreground">
        Kolommen geven de kans per ronde: ronde 4, kwartfinale, halve finale,
        finale en titel. S1–S8 is het bracketsegment; klik op een speler voor
        de route naar de finale.
      </p>
    </div>
  );
}
