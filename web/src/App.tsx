import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { RefreshCw, RotateCcw, TriangleAlert } from "lucide-react";
import { toast } from "sonner";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Separator } from "@/components/ui/separator";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { TooltipProvider } from "@/components/ui/tooltip";
import { BenchDialog } from "@/components/BenchDialog";
import { BudgetMeter } from "@/components/BudgetMeter";
import { BracketView } from "@/components/BracketView";
import { CompareView } from "@/components/CompareView";
import { ContributionChart } from "@/components/ContributionChart";
import { JokerPanel } from "@/components/JokerPanel";
import { KlunsPanel } from "@/components/KlunsPanel";
import { MatchupsCard } from "@/components/MatchupsCard";
import { PlayerSheet } from "@/components/PlayerSheet";
import { PredictForm } from "@/components/PredictForm";
import { ProgressPanel } from "@/components/ProgressPanel";
import { SavedTeamsCard } from "@/components/SavedTeamsCard";
import { StatTiles } from "@/components/StatTiles";
import { TeamTable } from "@/components/TeamTable";
import { ThemeToggle } from "@/components/ThemeToggle";
import {
  evaluateTeam,
  getJob,
  getJobResult,
  getLatestPrediction,
  optimizeTeam,
  startPrediction,
  type PredictBody,
} from "@/lib/api";
import { useTheme } from "@/lib/useTheme";
import { pct, points, seedLabel } from "@/lib/format";
import type {
  EvaluateResult,
  JobStatus,
  PredictionResult,
  ReservePlayer,
  Role,
  TeamMember,
} from "@/types";

function membersFromTeam(result: PredictionResult, surface: string): TeamMember[] {
  const model = result.models[surface];
  return model.team.players.map((player) => ({
    player: player.player,
    role: player.role,
    locked: false,
  }));
}

const JOB_STORAGE_KEY = "sportpools:job";
const PARAMS_STORAGE_KEY = "sportpools:params";
const SURFACE_STORAGE_KEY = "sportpools:surface";

export default function App() {
  const [jobId, setJobId] = useState<string | null>(() => {
    try {
      return localStorage.getItem(JOB_STORAGE_KEY);
    } catch {
      return null;
    }
  });
  const [result, setResult] = useState<PredictionResult | null>(null);
  const [activeSurface, setActiveSurface] = useState<string>("");
  const [tab, setTab] = useState<string>("");
  const [members, setMembers] = useState<TeamMember[]>([]);
  const [dirty, setDirty] = useState(false);
  const [evaluation, setEvaluation] = useState<EvaluateResult | null>(null);
  const [sheetPlayer, setSheetPlayer] = useState<string | null>(null);
  const [benchFor, setBenchFor] = useState<string | null>(null);
  const [optimizing, setOptimizing] = useState(false);
  const evaluateToken = useRef(0);
  const { theme, toggle: toggleTheme } = useTheme();

  const job = useQuery({
    queryKey: ["job", jobId],
    queryFn: () => getJob(jobId!),
    enabled: jobId !== null,
    refetchInterval: (query) =>
      query.state.data && ["pending", "running"].includes(query.state.data.status)
        ? 500
        : false,
  });

  const jobStatus: JobStatus | undefined = job.data ?? undefined;
  const running =
    jobId !== null &&
    (job.isLoading || (jobStatus !== undefined && ["pending", "running"].includes(jobStatus.status)));

  // Fetch the result once the job is done.
  useEffect(() => {
    if (jobStatus?.status === "done" && jobId && result === null) {
      getJobResult(jobId)
        .then((payload) => {
          setResult(payload);
          const stored =
            ((): string | null => {
              try {
                return localStorage.getItem(SURFACE_STORAGE_KEY);
              } catch {
                return null;
              }
            })() ?? payload.surfaces[0];
          const first = payload.surfaces.includes(stored)
            ? stored
            : payload.surfaces[0];
          setActiveSurface(first);
          setTab(first);
          setMembers(membersFromTeam(payload, first));
          setDirty(false);
          setEvaluation(null);
        })
        .catch((error) => toast.error(`Failed to fetch result: ${String(error)}`));
    }
    if (jobStatus?.status === "error") {
      toast.error(`Prediction failed: ${jobStatus.error ?? "unknown error"}`);
    }
  }, [jobStatus?.status, jobId, result]);

  // First visit (nothing stored locally): restore the latest cached
  // prediction so the dashboard loads without touching the Predict button.
  const latestAttempted = useRef(false);
  useEffect(() => {
    if (jobId !== null || latestAttempted.current) return;
    latestAttempted.current = true;

    getLatestPrediction()
      .then(({ job_id }) => {
        try {
          localStorage.setItem(JOB_STORAGE_KEY, job_id);
        } catch {
          // storage unavailable
        }
        setJobId(job_id);
      })
      .catch(() => undefined); // nothing cached yet: show the empty form
  }, [jobId]);

  // The server no longer knows the stored job (e.g. after a restart):
  // re-run the stored prediction, which the backend serves from its
  // on-disk prediction cache, so the dashboard returns instantly.
  const restoreAttempted = useRef(false);
  useEffect(() => {
    if (!job.isError || !jobId || restoreAttempted.current) return;
    restoreAttempted.current = true;

    let params: PredictBody | null = null;
    try {
      const raw = localStorage.getItem(PARAMS_STORAGE_KEY);
      params = raw ? (JSON.parse(raw) as PredictBody) : null;
    } catch {
      params = null;
    }

    try {
      localStorage.removeItem(JOB_STORAGE_KEY);
    } catch {
      // storage unavailable
    }
    setJobId(null);

    if (params) {
      startPrediction(params)
        .then(({ job_id }) => {
          try {
            localStorage.setItem(JOB_STORAGE_KEY, job_id);
            localStorage.setItem(PARAMS_STORAGE_KEY, JSON.stringify(params));
          } catch {
            // storage unavailable
          }
          setJobId(job_id);
        })
        .catch(() => undefined);
    }
  }, [job.isError, jobId]);

  const model = result && activeSurface ? result.models[activeSurface] : null;
  const joker = members.find((m) => m.role === "joker")?.player ?? "";
  const kluns = members.find((m) => m.role === "kluns")?.player ?? "";

  // Live evaluation whenever the selection or model changes.
  useEffect(() => {
    if (!model || members.length === 0 || !jobId) return;
    const token = ++evaluateToken.current;
    const timer = setTimeout(() => {
      evaluateTeam({
        job_id: jobId,
        surface: activeSurface,
        players: members.map((m) => m.player),
        joker,
        kluns,
        black_points: result?.black_points ?? 20,
        count: result?.count ?? 15,
      })
        .then((body) => {
          if (token === evaluateToken.current) setEvaluation(body);
        })
        .catch(() => {
          if (token === evaluateToken.current) setEvaluation(null);
        });
    }, 250);
    return () => clearTimeout(timer);
  }, [members, activeSurface, model, jobId, joker, kluns, result?.black_points, result?.count]);

  const poolByPlayer = useMemo(
    () => new Map((model?.pool ?? []).map((p) => [p.player, p])),
    [model],
  );

  const mutateMembers = useCallback(
    (updater: (current: TeamMember[]) => TeamMember[]) => {
      setMembers((current) => updater(current));
      setDirty(true);
    },
    [],
  );

  const setRole = useCallback(
    (player: string, role: Role) => {
      mutateMembers((current) =>
        current.map((member) => {
          if (member.player === player) return { ...member, role };
          if (member.role === role) return { ...member, role: "player" };
          return member;
        }),
      );
    },
    [mutateMembers],
  );

  const forceRole = useCallback(
    (player: string, role: Role) => {
      const holder = members.find((m) => m.role === role);
      if (members.some((m) => m.player === player)) {
        setRole(player, role);
        return;
      }
      if (!holder) {
        toast.error("No current role holder to replace");
        return;
      }
      mutateMembers((current) =>
        current.map((member) =>
          member.player === holder.player
            ? { ...member, player, locked: false }
            : member,
        ),
      );
      toast.success(
        `${player} is now the ${role === "joker" ? "joker" : "loser"}`,
      );
    },
    [members, mutateMembers, setRole],
  );

  const swap = useCallback(
    (out: string, inPlayer: string) => {
      mutateMembers((current) =>
        current.map((member) =>
          member.player === out ? { ...member, player: inPlayer } : member,
        ),
      );
    },
    [mutateMembers],
  );

  const toggleLock = useCallback(
    (player: string) => {
      mutateMembers((current) =>
        current.map((member) =>
          member.player === player
            ? { ...member, locked: !member.locked }
            : member,
        ),
      );
    },
    [mutateMembers],
  );

  function switchTab(next: string) {
    setTab(next);
    if (next === "compare" || next === "schema") return;
    setActiveSurface(next);
    try {
      localStorage.setItem(SURFACE_STORAGE_KEY, next);
    } catch {
      // storage unavailable
    }
    if (dirty) {
      toast.info("Your edits stay in place when switching models", {
        description:
          "Click 'Reset to optimal' to load this model's optimal team.",
      });
      return;
    }
    if (result) {
      setMembers(membersFromTeam(result, next));
      setEvaluation(null);
    }
  }

  function resetToOptimal() {
    if (!result) return;
    setMembers(membersFromTeam(result, activeSurface));
    setDirty(false);
    setEvaluation(null);
    toast.success(`Optimal selection loaded (${model?.label ?? activeSurface})`);
  }

  async function reoptimize() {
    if (!jobId || !model) return;
    setOptimizing(true);
    try {
      const team = await optimizeTeam({
        job_id: jobId,
        surface: activeSurface,
        locked: members.filter((m) => m.locked).map((m) => m.player),
        joker,
        kluns,
        black_points: result?.black_points ?? 20,
        count: result?.count ?? 15,
      });
      setMembers(
        team.players.map((player) => ({
          player: player.player,
          role: player.role,
          locked: members.some((m) => m.player === player.player && m.locked),
        })),
      );
      setDirty(true);
      toast.success(
        `Re-optimised: ${team.expected_points.toFixed(1)} expected points`,
      );
    } catch (error) {
      toast.error(`Re-optimisation failed: ${String(error)}`);
    } finally {
      setOptimizing(false);
    }
  }

  const blackLeft = evaluation
    ? evaluation.black_points.limit - evaluation.black_points.used
    : 20;

  const expectedPoints = evaluation
    ? evaluation.expected_points
    : (model?.team.expected_points ?? 0);

  const showDashboard = result !== null && model !== null;
  const coverage = result ? result.models[result.surfaces[0]]?.coverage : null;

  return (
    <TooltipProvider delayDuration={200}>
      <div className="min-h-screen bg-background text-foreground">
        <div className="w-full space-y-6 p-4 md:px-8 md:py-6">
          <header className="flex flex-wrap items-end justify-between gap-2">
            <div>
              <h1 className="text-xl font-semibold tracking-tight">
                Sportpools Optimiser
              </h1>
              <p className="text-sm text-muted-foreground">
                Optimal team based on Elo ratings and the actual
                tournament draw.
              </p>
            </div>
            <div className="flex items-center gap-3">
              {result && coverage && (
                <div className="hidden items-center gap-2 text-xs text-muted-foreground sm:flex">
                  <Badge variant="outline">
                    {result.tournament} {result.year}
                  </Badge>
                  <span>
                    ratings matched:{" "}
                    {coverage.exact + coverage.fuzzy + coverage.estimated}/128
                    {coverage.unmatched.length > 0 &&
                      ` (${coverage.unmatched.join(", ")} estimated)`}
                  </span>
                  <SourceAgeChip label="draw" age={result.sources?.draw_age_hours} />
                  <SourceAgeChip label="Elo" age={result.sources?.ratings_age_hours} />
                </div>
              )}
              <ThemeToggle theme={theme} onToggle={toggleTheme} />
            </div>
          </header>

          <PredictForm
            onStarted={(id, params) => {
              try {
                localStorage.setItem(JOB_STORAGE_KEY, id);
                localStorage.setItem(PARAMS_STORAGE_KEY, JSON.stringify(params));
                localStorage.removeItem(SURFACE_STORAGE_KEY);
              } catch {
                // storage unavailable
              }
              setJobId(id);
              setResult(null);
              setMembers([]);
              setEvaluation(null);
              setDirty(false);
            }}
            disabled={running}
          />

          {running && jobStatus && <ProgressPanel status={jobStatus} />}
          {running && !jobStatus && (
            <ProgressPanel
              status={{
                id: jobId ?? "",
                status: "running",
                progress: 0,
                stage: "Starting…",
              }}
            />
          )}

          {showDashboard && (
            <>
              <StatTiles
                model={model}
                members={members}
                evaluation={evaluation ?? undefined}
                expectedPoints={expectedPoints}
              />

              {evaluation && !evaluation.valid && (
                <Alert variant="destructive">
                  <TriangleAlert className="size-4" />
                  <AlertTitle>Selection is not valid</AlertTitle>
                  <AlertDescription>
                    <ul className="list-inside list-disc space-y-0.5">
                      {evaluation.errors.map((error) => (
                        <li key={error}>{error}</li>
                      ))}
                    </ul>
                  </AlertDescription>
                </Alert>
              )}

              <Tabs value={tab} onValueChange={switchTab}>
                <TabsList>
                  {result.surfaces.map((surface) => (
                    <TabsTrigger key={surface} value={surface}>
                      {result.models[surface].label}
                    </TabsTrigger>
                  ))}
                  {result.surfaces.length > 1 && (
                    <TabsTrigger value="compare">Compare</TabsTrigger>
                  )}
                  <TabsTrigger value="schema">Draw</TabsTrigger>
                </TabsList>

                {result.surfaces.map((surface) => (
                  <TabsContent
                    key={surface}
                    value={surface}
                    className="space-y-4"
                  >
                    <Card>
                      <CardHeader>
                        <CardTitle className="text-base">
                          Selection ({members.length}/{result.count})
                        </CardTitle>
                        <CardDescription>
                          Click a player for their route to the final; swap
                          players or change roles inline.
                        </CardDescription>
                      </CardHeader>
                      <CardContent>
                        <TeamTable
                          model={model}
                          members={members}
                          evaluation={evaluation ?? undefined}
                          onSetRole={setRole}
                          onToggleLock={toggleLock}
                          onSelectPlayer={setSheetPlayer}
                          onOpenBench={setBenchFor}
                        />
                      </CardContent>
                    </Card>

                    <div className="flex flex-wrap items-center gap-2">
                      <Button onClick={reoptimize} disabled={optimizing}>
                        <RefreshCw className="size-4" />
                        {optimizing ? "Optimising…" : "Re-optimise"}
                      </Button>
                      <Button variant="outline" onClick={resetToOptimal}>
                        <RotateCcw className="size-4" /> Reset to optimal
                      </Button>
                      <p className="text-xs text-muted-foreground">
                        Locked players, joker and loser stay in place; the
                        rest is re-chosen.
                      </p>
                    </div>

                    <div className="grid gap-4 xl:grid-cols-2">
                      <JokerPanel
                        model={model}
                        joker={joker}
                        inTeam={(player) =>
                          members.some((m) => m.player === player)
                        }
                        onMakeJoker={(player) => forceRole(player, "joker")}
                      />
                      <KlunsPanel
                        model={model}
                        kluns={kluns}
                        inTeam={(player) =>
                          members.some((m) => m.player === player)
                        }
                        onMakeKluns={(player) => forceRole(player, "kluns")}
                      />
                    </div>
                  </TabsContent>
                ))}

                {result.surfaces.length > 1 && (
                  <TabsContent value="compare">
                    <Card>
                      <CardHeader>
                        <CardTitle className="text-base">
                          Model comparison
                        </CardTitle>
                        <CardDescription>
                          Where the hard-court and overall Elo models pick the
                          same players, your choice is robust.
                        </CardDescription>
                      </CardHeader>
                      <CardContent>
                        <CompareView result={result} />
                      </CardContent>
                    </Card>
                  </TabsContent>
                )}

                <TabsContent value="schema">
                  <BracketView
                    model={model}
                    members={members}
                    onSelectPlayer={setSheetPlayer}
                  />
                </TabsContent>
              </Tabs>

              <div className="grid gap-4 lg:grid-cols-3">
                <Card>
                  <CardHeader>
                    <CardTitle className="text-base">Budget</CardTitle>
                  </CardHeader>
                  <CardContent>
                    <BudgetMeter
                      used={evaluation?.black_points.used ?? 0}
                      limit={evaluation?.black_points.limit ?? 20}
                      recycled={evaluation?.black_points.kluns_recycled ?? 0}
                    />
                    <Separator className="my-4" />
                    <p className="text-xs text-muted-foreground">
                      Evaluation model: {model.label}.{" "}
                      {dirty
                        ? "Selection manually edited."
                        : "Optimal selection."}
                    </p>
                  </CardContent>
                </Card>

                <MatchupsCard matchups={model.matchups} />

                <Card>
                  <CardHeader>
                    <CardTitle className="text-base">
                      Expected contribution per player
                    </CardTitle>
                  </CardHeader>
                  <CardContent>
                    {evaluation ? (
                      <ContributionChart evaluation={evaluation} />
                    ) : (
                      <p className="text-sm text-muted-foreground">
                        Loading evaluation…
                      </p>
                    )}
                  </CardContent>
                </Card>
              </div>

              <div className="grid gap-4 lg:grid-cols-3">
                <div className="lg:col-span-2">
                  <Card>
                    <CardHeader>
                      <CardTitle className="text-base">
                        Suggested reserves
                      </CardTitle>
                      <CardDescription>
                        Best unselected players by expected points.
                      </CardDescription>
                    </CardHeader>
                    <CardContent>
                      <ReservesTable reserves={model.reserves} />
                    </CardContent>
                  </Card>
                </div>
                <SavedTeamsCard
                  tournament={result.tournament}
                  year={result.year}
                  surface={activeSurface}
                  members={members}
                  expectedPoints={expectedPoints}
                  canPersist
                  seedOf={(player) => poolByPlayer.get(player)?.seed ?? 0}
                  onLoad={(payload) => {
                    setMembers(
                      payload.players.map((player) => ({
                        player,
                        role:
                          player === payload.joker
                            ? "joker"
                            : player === payload.kluns
                              ? "kluns"
                              : "player",
                        locked: false,
                      })),
                    );
                    setDirty(true);
                    toast.success("Team loaded");
                  }}
                />
              </div>
            </>
          )}
        </div>
      </div>

      <PlayerSheet
        player={sheetPlayer}
        model={model}
        onClose={() => setSheetPlayer(null)}
      />

      <BenchDialog
        open={benchFor !== null}
        replacePlayer={benchFor}
        members={members}
        model={model}
        blackBudgetLeft={blackLeft}
        onClose={() => setBenchFor(null)}
        onSwap={swap}
      />
    </TooltipProvider>
  );
}

function ReservesTable({ reserves }: { reserves: ReservePlayer[] }) {
  return (
    <Table>
      <TableHeader>
        <TableRow>
          <TableHead>Player</TableHead>
          <TableHead className="text-center">Black</TableHead>
          <TableHead className="text-right">Points</TableHead>
          <TableHead className="text-center">P·R4</TableHead>
          <TableHead className="text-center">P·W</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {reserves.map((reserve) => (
          <TableRow key={reserve.player}>
            <TableCell className="font-medium">
              <div className="flex items-center gap-2">
                {reserve.player}
                <Badge variant="outline">{seedLabel(reserve.seed)}</Badge>
              </div>
            </TableCell>
            <TableCell className="text-center font-mono tabular-nums">
              {reserve.black}
            </TableCell>
            <TableCell className="text-right font-mono tabular-nums">
              {points(reserve.potency)}
            </TableCell>
            <TableCell className="text-center font-mono text-xs tabular-nums text-muted-foreground">
              {pct(reserve.p_r4)}
            </TableCell>
            <TableCell className="text-center font-mono text-xs tabular-nums text-muted-foreground">
              {pct(reserve.p_w)}
            </TableCell>
          </TableRow>
        ))}
      </TableBody>
    </Table>
  );
}


function SourceAgeChip({ label, age }: { label: string; age?: number | null }) {
  if (age === undefined || age === null) return null;
  const fresh = age < 0.1;
  return (
    <Badge
      variant="outline"
      className={
        fresh
          ? "border-emerald-500/40 text-emerald-600 dark:text-emerald-300"
          : "border-sky-500/40 text-sky-600 dark:text-sky-300"
      }
      title={`Age of the ${label} data used`}
    >
      {label} {fresh ? "fresh" : `${age.toFixed(1)}h old`}
    </Badge>
  );
}
