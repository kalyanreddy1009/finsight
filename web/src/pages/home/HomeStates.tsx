import { Button } from "../../components/Button";

export function HomeSkeleton() {
  return (
    <div className="skeleton-stack" aria-busy="true">
      <p className="visually-hidden" role="status">
        Loading your summary
      </p>
      <div className="card skeleton-card" aria-hidden="true">
        <div className="skeleton skeleton-subhead" />
        <div className="skeleton skeleton-amount" />
        <div className="skeleton skeleton-line" />
        <div className="skeleton skeleton-bar" />
      </div>
      <div className="card skeleton-card" aria-hidden="true">
        <div className="skeleton skeleton-line" />
        <div className="skeleton skeleton-line" />
        <div className="skeleton skeleton-line" />
      </div>
    </div>
  );
}

export function HomeLoadError({ onRetry }: { onRetry: () => void }) {
  return (
    <div className="card notice" role="alert">
      <p>Could not load your summary. Check your connection and try again.</p>
      <Button variant="secondary" onClick={onRetry}>
        Try Again
      </Button>
    </div>
  );
}
