import { useState } from "react";
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
import { startPrediction } from "@/lib/api";
import { toast } from "sonner";

interface PredictFormProps {
  onStarted: (jobId: string) => void;
  disabled: boolean;
}

const YEARS = [2026, 2027];

/**
 * Prediction launcher: tournament, year and rating models.
 */
export function PredictForm({ onStarted, disabled }: PredictFormProps) {
  const [tournament, setTournament] = useState("us-open");
  const [year, setYear] = useState(2026);
  const [compare, setCompare] = useState(true);
  const [cacheTtl, setCacheTtl] = useState(6);
  const [busy, setBusy] = useState(false);

  async function run() {
    setBusy(true);
    try {
      const { job_id } = await startPrediction({
        tournament,
        year,
        surfaces: compare ? ["hard", "all"] : ["hard"],
        black_points: 20,
        count: 15,
        cache_ttl: cacheTtl,
      });
      onStarted(job_id);
    } catch (error) {
      toast.error(`Voorspelling starten mislukt: ${String(error)}`);
    } finally {
      setBusy(false);
    }
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base">Nieuwe voorspelling</CardTitle>
        <CardDescription>
          Haalt het schema (Wikipedia) en de Elo-ratings (Tennis Abstract) op en
          simuleert het hele toernooi.
        </CardDescription>
        <CardAction>
          <Button onClick={run} disabled={disabled || busy}>
            <Play className="size-4" /> {busy ? "Starten…" : "Voorspel"}
          </Button>
        </CardAction>
      </CardHeader>
      <CardContent>
        <div className="grid grid-cols-2 gap-4 md:grid-cols-5">
          <div className="space-y-1.5">
            <Label htmlFor="tournament">Toernooi</Label>
            <Select value={tournament} onValueChange={setTournament}>
              <SelectTrigger id="tournament">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="us-open">US Open</SelectItem>
                <SelectItem value="wimbledon">Wimbledon</SelectItem>
                <SelectItem value="roland-garros">Roland Garros</SelectItem>
                <SelectItem value="australian-open">Australian Open</SelectItem>
              </SelectContent>
            </Select>
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="year">Jaar</Label>
            <Select value={String(year)} onValueChange={(v) => setYear(Number(v))}>
              <SelectTrigger id="year">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {YEARS.map((y) => (
                  <SelectItem key={y} value={String(y)}>
                    {y}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="black">Zwarte punten</Label>
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
                <SelectItem value="6">6 uur (standaard)</SelectItem>
                <SelectItem value="24">1 dag</SelectItem>
                <SelectItem value="0.5">30 min</SelectItem>
                <SelectItem value="0">Altijd vers ophalen</SelectItem>
              </SelectContent>
            </Select>
            <p className="text-xs text-muted-foreground">
              Bronnen (schema + Elo) worden hergebruikt binnen deze tijd.
            </p>
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="compare" className="flex items-center gap-2">
              <Switch
                id="compare"
                checked={compare}
                onCheckedChange={setCompare}
              />
              Vergelijk modellen
            </Label>
            <p className="text-xs text-muted-foreground">
              Hardcourt- en totaal-Elo naast elkaar (langere rekentijd).
            </p>
          </div>
        </div>
      </CardContent>
    </Card>
  );
}
