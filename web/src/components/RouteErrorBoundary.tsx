import { Component, type ReactNode } from "react";
import { LoadError } from "./LoadError";

const ROUTE_ERROR_MESSAGE = "This page could not load. Check your connection and try again.";

interface RouteErrorBoundaryProps {
  children: ReactNode;
}

interface RouteErrorBoundaryState {
  failed: boolean;
}

// Catches a failed lazy page load (or a render error) for one route. It sits inside the app shell,
// so the navigation stays on screen. Reloading the page is the retry, because a failed chunk is not retried in place.
export class RouteErrorBoundary extends Component<RouteErrorBoundaryProps, RouteErrorBoundaryState> {
  state: RouteErrorBoundaryState = { failed: false };

  static getDerivedStateFromError(): RouteErrorBoundaryState {
    return { failed: true };
  }

  render() {
    if (this.state.failed) {
      return <LoadError message={ROUTE_ERROR_MESSAGE} onRetry={() => window.location.reload()} />;
    }
    return this.props.children;
  }
}
