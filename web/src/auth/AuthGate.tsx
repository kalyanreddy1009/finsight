import type { ReactNode } from "react";
import { Button } from "../components/Button";
import { SetupScreen } from "./SetupScreen";
import { SignInScreen } from "./SignInScreen";
import { useAuth } from "./useAuth";

// Shows the app only when signed in. Everything else is a full-page auth or status screen.
export function AuthGate({ children }: { children: ReactNode }) {
  const { status, retry } = useAuth();
  switch (status) {
    case "signedIn":
      return <>{children}</>;
    case "setup":
      return <SetupScreen />;
    case "signedOut":
      return <SignInScreen />;
    case "unavailable":
      return (
        <main className="auth-page">
          <div className="auth-card">
            <h1 className="title2">FinSight is not reachable</h1>
            <p className="footnote">Check that the FinSight server is running, then try again.</p>
            <Button variant="primary" onClick={retry}>
              Try Again
            </Button>
          </div>
        </main>
      );
    case "loading":
      return (
        <main className="auth-page" aria-busy="true">
          <p className="footnote" role="status">
            Loading FinSight
          </p>
        </main>
      );
  }
}
