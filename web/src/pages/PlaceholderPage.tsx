import type { ReactNode } from "react";
import { useDocumentTitle } from "../hooks/useDocumentTitle";

interface PlaceholderPageProps {
  title: string;
  message: string;
  children?: ReactNode;
}

// Honest empty state for screens that are not built yet. No fake data.
export function PlaceholderPage({ title, message, children }: PlaceholderPageProps) {
  useDocumentTitle(title);
  return (
    <section className="placeholder" aria-labelledby="page-title">
      <h1 id="page-title" className="title">
        {title}
      </h1>
      <p className="empty-state">{message}</p>
      {children}
    </section>
  );
}
