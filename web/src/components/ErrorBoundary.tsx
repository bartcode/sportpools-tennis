import { Component, type ErrorInfo, type ReactNode } from "react";
import { Button } from "@/components/ui/button";

interface ErrorBoundaryProps {
  children: ReactNode;
}

interface ErrorBoundaryState {
  error: Error | null;
}

/**
 * Catches render errors and shows them instead of a blank page.
 */
export class ErrorBoundary extends Component<
  ErrorBoundaryProps,
  ErrorBoundaryState
> {
  state: ErrorBoundaryState = { error: null };

  static getDerivedStateFromError(error: Error): ErrorBoundaryState {
    return { error };
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    console.error("Render error:", error, info.componentStack);
  }

  render() {
    if (this.state.error) {
      return (
        <div className="flex min-h-screen items-center justify-center p-6">
          <div className="max-w-lg space-y-4 rounded-lg border border-destructive/50 bg-destructive/5 p-6">
            <h1 className="text-lg font-semibold text-destructive">
              Something went wrong in the interface
            </h1>
            <pre className="overflow-x-auto rounded bg-muted p-3 text-xs">
              {this.state.error.message}
              {"\n"}
              {this.state.error.stack?.split("\n").slice(1, 6).join("\n")}
            </pre>
            <Button
              variant="outline"
              onClick={() => {
                this.setState({ error: null });
                window.location.reload();
              }}
            >
              Reload
            </Button>
          </div>
        </div>
      );
    }
    return this.props.children;
  }
}
