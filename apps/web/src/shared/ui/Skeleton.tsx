/** List loading placeholder: keeps layout stable while the API responds. */
export function MaterialListSkeleton({ rows = 3 }: { rows?: number }) {
  return (
    <div className="material-list" aria-hidden="true">
      {Array.from({ length: rows }, (_, i) => (
        <div className="card card-skeleton" key={i}>
          <div className="skeleton skeleton-title" />
          <div className="skeleton skeleton-meta" />
        </div>
      ))}
    </div>
  );
}

/** Generic text-block placeholder. */
export function Skeleton({ lines = 3 }: { lines?: number }) {
  return (
    <div className="skeleton-block" aria-hidden="true">
      {Array.from({ length: lines }, (_, i) => (
        <div
          className={`skeleton ${i === 0 ? "skeleton-title" : "skeleton-line"}`}
          key={i}
        />
      ))}
    </div>
  );
}
