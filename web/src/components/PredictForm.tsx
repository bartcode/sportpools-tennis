import { useEffect, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Play } from "lucide-react";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardAction,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Switch } from "@/components/ui/switch";
import { getTournaments, startPrediction, type PredictBody } from "@/lib/api";
import { toast } from "sonner";

interface PredictFormProps {
  onStarted: (jobId: string, params: PredictBody) => void;
  disabled: boolean;
}

/**
 * Prediction launcher: tournament, year and rating models. Tournaments and
 * years come from the backend, so new seasons appear without a rebuild.
 */
export function PredictForm({ onStarted, disabled }: PredictFormProps) {
  const [tournament, setTournament] = useState("us-open");
  const [year, setYear] = useState<number | null>(null);
  const [compare, setCompare] = useState(true);
  const [cacheTtl, setCacheTtl] = useState(6);
  const [busy, setBusy] = useState(false);

  const tournaments = useQuery({
    queryKey: ["tournaments"],
    queryFn: getTournaments,
    staleTime: Infinity,
  });

  const options = tournaments.data?.tournaments ?? [];
  const selected = options.find((option) => option.key === tournament);

  // Follow the tournament's next edition until the user picks a year.
  useEffect(() => {
    if (selected && year === null) {
      setYear(selected.default_year);
    }
  }, [selected, year]);

  function switchTournament(key: string) {
    setTournament(key);
    const next = options.find((option) => option.key === key);
    if (next) setYear(next.default_year);
  }

  async function run() {
    if (!selected || year === null) {
      toast.error("Tournament options are still loading");
      return;
    }
    setBusy(true);
    try {
      const params: PredictBody = {
        tournament,
        year,
        surfaces: compare ? ["hard", "all"] : ["hard"],
        black_points: 20,
        count: 15,
        cache_ttl: cacheTtl,
      };
      const { job_id } = await startPrediction(params);
      onStarted(job_id, params);
    } catch (error) {
      toast.error(`Failed to start prediction: ${String(error)}`);
    } finally {
      setBusy(false);
    }
  }

  const loading = options.length === 0;

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base">New prediction</CardTitle>
        <CardDescription>
          Fetches the draw (Wikipedia) and the Elo ratings (Tennis Abstract) and
          simulates the entire tournament.
        </CardDescription>
        <CardAction>
          <Button onClick={run} disabled={disabled || busy || loading}>
            <Play className="size-4" /> {busy ? "Starting…" : "Predict"}
          </Button>
        </CardAction>
      </CardHeader>
      <CardContent>
        <div className="grid grid-cols-2 gap-4 md:grid-cols-5">
          <div className="space-y-1.5">
            <Label htmlFor="tournament">Tournament</Label>
            <Select
              value={tournament}
              onValueChange={switchTournament}
              disabled={loading}
            >
              <SelectTrigger id="tournament">
                <SelectValue placeholder="Loading…" />
              </SelectTrigger>
              <SelectContent>
                {options.map((option) => (
                  <SelectItem key={option.key} value={option.key}>
                    {option.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="year">Year</Label>
            <Select
              value={year === null ? undefined : String(year)}
              onValueChange={(v) => setYear(Number(v))}
              disabled={loading}
            >
              <SelectTrigger id="year">
                <SelectValue placeholder="Loading…" />
              </SelectTrigger>
              <SelectContent>
                {(selected?.years ?? []).map((y) => (
                  <SelectItem key={y} value={String(y)}>
                    {y}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="black">Black points</Label>
            <Input id="black" type="number" defaultValue={20} disabled />
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="cache">Cache</Label>
            <Select
              value={String(cacheTtl)}
              onValueChange={(v) => setCacheTtl(Number(v))}
            >
              <SelectTrigger id="cache">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="6">6 hours (default)</SelectItem>
                <SelectItem value="24">1 day</SelectItem>
                <SelectItem value="0.5">30 min</SelectItem>
                <SelectItem value="0">Always fetch fresh</SelectItem>
              </SelectContent>
            </Select>
            <p className="text-xs text-muted-foreground">
              Sources (draw + Elo) are reused within this window.
            </p>
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="compare" className="flex items-center gap-2">
              <Switch
                id="compare"
                checked={compare}
                onCheckedChange={setCompare}
              />
              Compare models
            </Label>
            <p className="text-xs text-muted-foreground">
              Hard-court and overall Elo side by side (longer compute time).
            </p>
          </div>
        </div>
      </CardContent>
    </Card>
  );
}
