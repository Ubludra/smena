import { Button } from "./Button";

interface ErrorStateProps {
  /** Human message; the server's Russian text when available. */
  message: string;
  onRetry: () => void;
}

/**
 * Visible, actionable failure (product rule §30): the teacher sees what
 * happened and one «Повторить» button — never a raw HTTP status.
 */
export function ErrorState({ message, onRetry }: ErrorStateProps) {
  return (
    <div className="error-state" role="alert">
      <p>{message}</p>
      <Button variant="secondary" onClick={onRetry}>
        Повторить
      </Button>
    </div>
  );
}
