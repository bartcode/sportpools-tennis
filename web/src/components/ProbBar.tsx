import { cn } from "@/lib/utils";

interface ProbBarProps {
  value: number;
  className?: string;
  /** Highlight intensity class for the filled part. */
  tone?: "default" | "joker" | "kluns" | "warn" | "title";
}

const toneClasses: Record<string, string> = {
  default: "bg-gradient-to-r from-sky-500 to-blue-600",
  joker: "bg-gradient-to-r from-amber-400 to-orange-500",
  kluns: "bg-gradient-to-r from-rose-400 to-red-500",
  warn: "bg-gradient-to-r from-orange-400 to-rose-500",
  title: "bg-gradient-to-r from-emerald-400 to-teal-500",
};

/**
 * A thin horizontal probability bar with the percentage as tooltip text.
 */
export function ProbBar({ value, className, tone = "default" }: ProbBarProps) {
  const clamped = Math.max(0, Math.min(1, value));
  return (
    <div
      className={cn(
        "h-1.5 w-full overflow-hidden rounded-full bg-muted",
        className,
      )}
      title={`${(clamped * 100).toFixed(1)}%`}
    >
      <div
        className={cn(
          "animate-grow-x h-full rounded-full transition-all duration-500",
          toneClasses[tone],
        )}
        style={{ width: `${clamped * 100}%` }}
      />
    </div>
  );
}
