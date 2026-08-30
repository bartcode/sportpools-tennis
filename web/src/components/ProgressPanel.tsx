import { Loader2 } from "lucide-react";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Progress } from "@/components/ui/progress";
import { cn } from "@/lib/utils";
import type { JobStatus } from "@/types";

const STAGE_HINTS: { match: RegExp; label: string }[] = [
  { match: /draw/i, label: "Fetch draw" },
  { match: /rating|elo/i, label: "Fetch Elo ratings" },
  { match: /simulat/i, label: "Simulate tournament" },
  { match: /optimis/i, label: "Optimise team" },
  { match: /loser/i, label: "Loser alternatives" },
  { match: /route/i, label: "Routes & matchups" },
];

function stageChecklist(stage: string): { label: string; done: boolean }[] {
  const hints = STAGE_HINTS.map((hint) => hint.label);
  const current = STAGE_HINTS.find((hint) => hint.match.test(stage))?.label;
  const currentIndex = current ? hints.indexOf(current) : -1;
  return hints.map((label, index) => ({
    label,
    done: currentIndex > index,
  }));
}

/**
 * Live progress of the running prediction job.
 */
export function ProgressPanel({ status }: { status: JobStatus }) {
  const failed = status.status === "error";
  const checklist = stageChecklist(status.stage);

  return (
    <Card className="animate-rise">
      <CardHeader>
        <CardTitle className="flex items-center gap-2 text-base">
          {!failed && (
            <Loader2 className="size-4 animate-spin text-primary" />
          )}
          Computing prediction
        </CardTitle>
        <CardDescription>
          {failed ? status.error : status.stage}
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="relative overflow-hidden rounded-full">
          <Progress
            value={failed ? 100 : status.progress * 100}
            className={cn(
              "h-2 [&_[data-slot=progress-indicator]]:bg-gradient-to-r [&_[data-slot=progress-indicator]]:from-sky-500 [&_[data-slot=progress-indicator]]:via-violet-500 [&_[data-slot=progress-indicator]]:to-emerald-400",
              failed &&
                "[&_[data-slot=progress-indicator]]:from-red-500 [&_[data-slot=progress-indicator]]:via-red-500 [&_[data-slot=progress-indicator]]:to-red-400",
            )}
          />
          {!failed && (
            <div className="progress-shimmer pointer-events-none absolute inset-0" />
          )}
        </div>
        <div className="flex items-center justify-between text-sm">
          <span className="font-mono tabular-nums text-muted-foreground">
            {Math.round(status.progress * 100)}%
          </span>
          <span className="text-muted-foreground">{status.stage}</span>
        </div>
        <ul className="grid grid-cols-2 gap-1.5 text-xs text-muted-foreground">
          {checklist.map((item) => (
            <li
              key={item.label}
              className={item.done ? "text-foreground" : undefined}
            >
              {item.done ? "✓" : "·"} {item.label}
            </li>
          ))}
        </ul>
      </CardContent>
    </Card>
  );
}
