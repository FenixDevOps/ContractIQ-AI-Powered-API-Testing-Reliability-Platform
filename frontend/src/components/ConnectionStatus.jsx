import { RefreshCw } from "lucide-react";

const labels = {
  loading: "Checking backend",
  connected: "Backend connected",
  disconnected: "Backend disconnected",
};

export default function ConnectionStatus({ state, onRetry, compact = false }) {
  return (
    <div className={`connection-status connection-${state} ${compact ? "is-compact" : ""}`}>
      <span className="connection-indicator" aria-hidden="true" />
      <span aria-live="polite">{labels[state]}</span>
      {state === "disconnected" && (
        <button className="retry-button" onClick={onRetry} type="button" aria-label="Retry backend connection">
          <RefreshCw size={13} aria-hidden="true" />
          {!compact && "Retry"}
        </button>
      )}
    </div>
  );
}