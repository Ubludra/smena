import type { ApiMaterial } from "../../shared/api/client";
import { relativeDate } from "../../shared/lib/dates";

interface MaterialCardProps {
  material: ApiMaterial;
  onOpen: (id: string) => void;
}

/**
 * Whole card is one button (single obvious tap target on phones); the lock
 * is a visual cue, not an affordance — access control lives on the server.
 */
export function MaterialCard({ material, onOpen }: MaterialCardProps) {
  return (
    <button
      type="button"
      className="card material-card"
      onClick={() => onOpen(material.id)}
    >
      <span className="material-card-title">
        {material.is_protected && (
          <svg
            className="lock-badge"
            width="15"
            height="15"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="2"
            strokeLinecap="round"
            aria-hidden="true"
          >
            <rect x="4" y="10" width="16" height="10" rx="2" />
            <path d="M8 10V7a4 4 0 0 1 8 0v3" />
          </svg>
        )}
        {material.title}
      </span>
      <span className="material-card-meta">
        {material.subject && <span>{material.subject}</span>}
        <span>изменён {relativeDate(material.updated_at)}</span>
      </span>
    </button>
  );
}
