import { useMemo, useState } from "react";
import { ArrowRightLeft } from "lucide-react";
import { toast } from "sonner";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { pct, points, seedLabel } from "@/lib/format";
import type { ModelPayload, TeamMember } from "@/types";

interface BenchDialogProps {
  open: boolean;
  replacePlayer: string | null;
  members: TeamMember[];
  model: ModelPayload | null;
  blackBudgetLeft: number;
  onClose: () => void;
  onSwap: (out: string, inPlayer: string) => void;
}

/**
 * Bench picker: search the pool and swap a player into the selection.
 * Rows that would blow the black-points budget are disabled.
 */
export function BenchDialog({
  open,
  replacePlayer,
  members,
  model,
  blackBudgetLeft,
  onClose,
  onSwap,
}: BenchDialogProps) {
  const [query, setQuery] = useState("");

  const selected = new Set(members.map((m) => m.player));
  const replaceBlack = replacePlayer
    ? (model?.pool.find((p) => p.player === replacePlayer)?.black ?? 0)
    : 0;

  const candidates = useMemo(() => {
    if (!model) return [];
    const needle = query.trim().toLowerCase();
    return model.pool
      .filter((p) => !selected.has(p.player))
      .filter((p) => !needle || p.player.toLowerCase().includes(needle))
      .sort((a, b) => b.potency - a.potency)
      .slice(0, 40);
  }, [model, query, selected]);

  if (!model) return null;

  return (
    <Dialog
      open={open}
      onOpenChange={(next) => {
        if (!next) {
          setQuery("");
          onClose();
        }
      }}
    >
      <DialogContent className="max-h-[80vh] sm:max-w-2xl">
        <DialogHeader>
          <DialogTitle>
            {replacePlayer ? `Wissel ${replacePlayer}` : "Speler toevoegen"}
          </DialogTitle>
          <DialogDescription>
            Zoek in de overige spelers, gesorteerd op verwachte punten.
          </DialogDescription>
        </DialogHeader>

        <Input
          placeholder="Zoek speler…"
          value={query}
          onChange={(event) => setQuery(event.target.value)}
        />

        <div className="max-h-[55vh] overflow-y-auto">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Speler</TableHead>
                <TableHead className="text-center">Zwart</TableHead>
                <TableHead className="text-right">Punten</TableHead>
                <TableHead className="text-center">P·R4</TableHead>
                <TableHead className="w-20"></TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {candidates.map((candidate) => {
                const affordable =
                  blackBudgetLeft + replaceBlack >= candidate.black;
                return (
                  <TableRow key={candidate.player}>
                    <TableCell className="font-medium">
                      <div className="flex items-center gap-2">
                        {candidate.player}
                        <Badge variant="outline">{seedLabel(candidate.seed)}</Badge>
                      </div>
                    </TableCell>
                    <TableCell className="text-center font-mono tabular-nums">
                      {candidate.black}
                    </TableCell>
                    <TableCell className="text-right font-mono tabular-nums">
                      {points(candidate.potency)}
                    </TableCell>
                    <TableCell className="text-center font-mono text-xs tabular-nums text-muted-foreground">
                      {pct(candidate.probs[2])}
                    </TableCell>
                    <TableCell>
                      <Button
                        size="sm"
                        variant="outline"
                        disabled={!affordable}
                        onClick={() => {
                          if (!replacePlayer) {
                            toast.error("Kies eerst een speler om te wisselen");
                            return;
                          }
                          onSwap(replacePlayer, candidate.player);
                          setQuery("");
                          onClose();
                        }}
                      >
                        <ArrowRightLeft className="size-3.5" /> In
                      </Button>
                    </TableCell>
                  </TableRow>
                );
              })}
              {candidates.length === 0 && (
                <TableRow>
                  <TableCell
                    colSpan={5}
                    className="py-6 text-center text-muted-foreground"
                  >
                    Geen spelers gevonden
                  </TableCell>
                </TableRow>
              )}
            </TableBody>
          </Table>
        </div>
      </DialogContent>
    </Dialog>
  );
}
