import { Outlet } from "react-router-dom";
import { PrimaryNav } from "./PrimaryNav";

export function AppShell() {
  return (
    <div className="app-shell">
      <a className="skip-link" href="#main">
        Skip to content
      </a>
      <PrimaryNav />
      <main id="main" className="app-main" tabIndex={-1}>
        <div className="page">
          <Outlet />
        </div>
      </main>
    </div>
  );
}
