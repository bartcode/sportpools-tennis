import { Moon, Sun } from "lucide-react";
import { Button } from "@/components/ui/button";
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from "@/components/ui/tooltip";

/**
 * Light/dark theme switch.
 */
export function ThemeToggle({
  theme,
  onToggle,
}: {
  theme: "dark" | "light";
  onToggle: () => void;
}) {
  return (
    <Tooltip>
      <TooltipTrigger asChild>
        <Button variant="outline" size="icon" onClick={onToggle}>
          {theme === "dark" ? (
            <Sun className="size-4 text-chart-4" />
          ) : (
            <Moon className="size-4 text-indigo-500" />
          )}
        </Button>
      </TooltipTrigger>
      <TooltipContent>
        {theme === "dark" ? "Lichte modus" : "Donkere modus"}
      </TooltipContent>
    </Tooltip>
  );
}
