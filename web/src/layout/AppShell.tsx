import { useState } from "react";
import { Outlet } from "react-router-dom";
import { useAuth } from "../auth/useAuth";
import { BrandLockup } from "../components/BrandMark";
import { Button } from "../components/Button";
import { PrimaryNav } from "./PrimaryNav";

export function AppShell() {
  const { signOut } = useAuth();
  const [signingOut, setSigningOut] = useState(false);

  async function handleSignOut() {
    setSigningOut(true);
    await signOut();
  }

  return (
    <div className="app-shell">
      <a className="skip-link" href="#main">
        Skip to content
      </a>
      <header className="app-header">
        <BrandLockup />
        <PrimaryNav />
        <Button variant="plain" className="sign-out-button" onClick={() => void handleSignOut()} disabled={signingOut}>
          {signingOut ? "Signing Out…" : "Sign Out"}
        </Button>
      </header>
      <main id="main" className="app-main" tabIndex={-1}>
        <div className="page">
          <Outlet />
        </div>
      </main>
    </div>
  );
}
