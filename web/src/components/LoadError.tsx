import { Button } from "./Button";

interface LoadErrorProps {
  message?: string;
  onRetry: () => void;
}

export function LoadError({ message = "Could not load this section. Check your connection and try again.", onRetry }: LoadErrorProps) {
  return (
    <div className="card notice" role="alert">
      <p>{message}</p>
      <Button onClick={onRetry}>Try Again</Button>
    </div>
  );
}
