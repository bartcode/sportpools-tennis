import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ClipboardCopy, Save, Trash2 } from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { deleteTeam, listTeams, saveTeam } from "@/lib/api";
import { teamExportText } from "@/lib/format";
import type { TeamMember } from "@/types";

interface SavedTeamsCardProps {
  tournament: string;
  year: number;
  surface: string;
  members: TeamMember[];
  expectedPoints: number;
  canPersist: boolean;
  seedOf: (player: string) => number;
  onLoad: (payload: { players: string[]; joker: string; kluns: string }) => void;
}

/**
 * Save, reload, delete and export the current selection.
 */
export function SavedTeamsCard({
  tournament,
  year,
  surface,
  members,
  expectedPoints,
  canPersist,
  seedOf,
  onLoad,
}: SavedTeamsCardProps) {
  const queryClient = useQueryClient();
  const [name, setName] = useState("");
  const [dialogOpen, setDialogOpen] = useState(false);

  const teams = useQuery({ queryKey: ["teams"], queryFn: listTeams });

  const save = useMutation({
    mutationFn: () =>
      saveTeam({
        name: name.trim() || `team ${new Date().toLocaleDateString("nl-NL")}`,
        tournament,
        year,
        surface,
        players: members.map((m) => m.player),
        joker: members.find((m) => m.role === "joker")?.player ?? "",
        kluns: members.find((m) => m.role === "kluns")?.player ?? "",
      }),
    onSuccess: () => {
      toast.success("Team saved");
      setDialogOpen(false);
      setName("");
      queryClient.invalidateQueries({ queryKey: ["teams"] });
    },
    onError: (error) => toast.error(`Save failed: ${String(error)}`),
  });

  const remove = useMutation({
    mutationFn: (id: number) => deleteTeam(id),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["teams"] }),
  });

  function copyExport() {
    const joker = members.find((m) => m.role === "joker")?.player ?? "";
    const kluns = members.find((m) => m.role === "kluns")?.player ?? "";
    const text = teamExportText(
      members.map((m) => ({
        player: m.player,
        seed: seedOf(m.player),
        role: m.role,
      })),
      joker,
      kluns,
      expectedPoints,
    );
    navigator.clipboard.writeText(text).then(
      () => toast.success("Selection copied"),
      () => toast.error("Copy failed"),
    );
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base">Saved teams</CardTitle>
        <CardDescription>
          {canPersist
            ? "Save your selection or load an earlier version."
            : "Run a prediction first; saved teams can be loaded afterwards."}
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-3">
        <div className="flex gap-2">
          <Button
            size="sm"
            variant="outline"
            disabled={!canPersist}
            onClick={() => setDialogOpen(true)}
          >
            <Save className="size-3.5" /> Save
          </Button>
          <Button size="sm" variant="outline" onClick={copyExport}>
            <ClipboardCopy className="size-3.5" /> Copy selection
          </Button>
        </div>

        <div className="space-y-1.5">
          {(teams.data?.teams ?? []).map((team) => (
            <div
              key={team.id}
              className="flex items-center justify-between gap-2 rounded-md border border-border px-3 py-1.5 text-sm"
            >
              <div className="min-w-0">
                <p className="truncate font-medium">{team.name}</p>
                <p className="text-xs text-muted-foreground">
                  {team.tournament} {team.year} · {team.surface} ·{" "}
                  {new Date(team.created_at + "Z").toLocaleString("en-GB", {
                    dateStyle: "short",
                    timeStyle: "short",
                  })}
                </p>
              </div>
              <div className="flex shrink-0 gap-1">
                <Button
                  size="sm"
                  variant="ghost"
                  disabled={!canPersist}
                  onClick={() => onLoad(team.payload)}
                >
                  Load
                </Button>
                <Button
                  size="icon-sm"
                  variant="ghost"
                  className="text-muted-foreground"
                  onClick={() => remove.mutate(team.id)}
                >
                  <Trash2 className="size-3.5" />
                </Button>
              </div>
            </div>
          ))}
          {teams.data?.teams.length === 0 && (
            <p className="text-xs text-muted-foreground">No saved teams yet.</p>
          )}
        </div>

        <Dialog open={dialogOpen} onOpenChange={setDialogOpen}>
          <DialogContent className="sm:max-w-sm">
            <DialogHeader>
              <DialogTitle>Save team</DialogTitle>
            </DialogHeader>
            <Input
              placeholder="Name, e.g. 'US Open base'"
              value={name}
              onChange={(event) => setName(event.target.value)}
            />
            <DialogFooter>
              <Button
                size="sm"
                onClick={() => save.mutate()}
                disabled={save.isPending}
              >
                {save.isPending ? "Saving…" : "Save"}
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>
      </CardContent>
    </Card>
  );
}
