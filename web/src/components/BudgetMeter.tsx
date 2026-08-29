import { Progress } from "@/components/ui/progress";
import { cn } from "@/lib/utils";

interface BudgetMeterProps {
  used: number;
  limit: number;
  recycled: number;
}

/**
 * Black-points budget gauge with the kluns recycling visualised.
 */
export function BudgetMeter({ used, limit, recycled }: BudgetMeterProps) {
  const over = used > limit;
  const ratio = limit > 0 ? Math.min(used / limit, 1.35) : 0;

  return (
    <div className="space-y-1.5">
      <div className="flex items-baseline justify-between text-sm">
        <span className="text-muted-foreground">Zwarte lijst punten</span>
        <span
          className={cn(
            "font-mono font-semibold tabular-nums",
            over ? "text-destructive" : "text-foreground",
          )}
        >
          {used} / {limit}
        </span>
      </div>
      <Progress
        value={ratio * 100}
        className={cn(
          "h-2 [&_[data-slot=progress-indicator]]:bg-gradient-to-r [&_[data-slot=progress-indicator]]:from-rose-400 [&_[data-slot=progress-indicator]]:to-orange-500",
          !over &&
            "[&_[data-slot=progress-indicator]]:from-sky-500 [&_[data-slot=progress-indicator]]:to-blue-600",
        )}
      />
      {recycled > 0 && (
        <p className="text-xs text-muted-foreground">
          {limit - recycled} basis + {recycled} teruggewonnen via de kluns
        </p>
      )}
      {over && (
        <p className="text-xs font-medium text-destructive">
          {used - limit} punten over het budget
        </p>
      )}
    </div>
  );
}
