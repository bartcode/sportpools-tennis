import {
  Bar,
  BarChart,
  Cell,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import type { EvaluateResult } from "@/types";

const ROLE_COLORS: Record<string, string> = {
  player: "var(--color-primary)",
  joker: "var(--color-chart-2)",
  kluns: "var(--color-destructive)",
};

/**
 * Expected contribution per selected player, coloured by role.
 */
export function ContributionChart({ evaluation }: { evaluation: EvaluateResult }) {
  const data = [...evaluation.players].sort(
    (a, b) => a.contribution - b.contribution,
  );

  return (
    <div className="h-72 w-full">
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={data} layout="vertical" margin={{ left: 8, right: 16 }}>
          <XAxis type="number" fontSize={11} stroke="currentColor" />
          <YAxis
            type="category"
            dataKey="player"
            width={130}
            fontSize={11}
            stroke="currentColor"
          />
          <Tooltip
            cursor={{ fill: "var(--color-muted)", opacity: 0.3 }}
            formatter={(value) =>
              [Number(value ?? 0).toFixed(1), "Verwachte punten"] as [string, string]
            }
          />
          <ReferenceLine x={0} stroke="currentColor" opacity={0.4} />
          <Bar dataKey="contribution" radius={3} barSize={14}>
            {data.map((row) => (
              <Cell
                key={row.player}
                fill={ROLE_COLORS[row.role] ?? ROLE_COLORS.player}
              />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}
