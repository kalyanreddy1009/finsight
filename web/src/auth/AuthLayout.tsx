import type { ReactNode } from "react";

interface AuthLayoutProps {
  title: string;
  intro: string;
  children: ReactNode;
}

// Shared frame for the Setup and Sign In screens: one column, no navigation.
export function AuthLayout({ title, intro, children }: AuthLayoutProps) {
  return (
    <main className="auth-page">
      <div className="auth-card">
        <h1 className="title2">{title}</h1>
        <p className="footnote">{intro}</p>
        {children}
      </div>
    </main>
  );
}
