import { api, ApiError } from "../../shared/api/client";
import { useApiToken, useAuth } from "../../shared/hooks/auth";
import { useAsync } from "../../shared/hooks/useAsync";
import { ErrorState } from "../../shared/ui/ErrorState";
import { Skeleton } from "../../shared/ui/Skeleton";
import { navigate } from "../../shared/lib/routes";
import { PlanForm } from "./PlanForm";

/** Edit route: load the plan, then render the form with its values. */
export function PlanEditPage({ id }: { id: string }) {
  const token = useApiToken();
  const { handleUnauthorized } = useAuth();
  const { data, error, loading, reload } = useAsync(
    () => api.getLessonPlan(token, id),
    [token, id],
  );

  if (loading && !data) return <Skeleton lines={6} />;

  if (error) {
    if (error instanceof ApiError && error.isUnauthorized) {
      handleUnauthorized();
      return null;
    }
    if (error instanceof ApiError && error.status === 404) {
      return (
        <ErrorState
          message="План не найден. Возможно, он был удалён."
          onRetry={() => navigate("#/plans")}
        />
      );
    }
    return <ErrorState message="Не удалось загрузить план урока." onRetry={reload} />;
  }

  if (!data) return null;

  return (
    <>
      <div className="page-header">
        <div>
          <p className="eyebrow">ПЛАН УРОКА</p>
          <h1>Редактировать план</h1>
        </div>
      </div>
      <PlanForm
        plan={data}
        onSaved={() => undefined}
        onCancel={() => navigate(`#/plans/${id}`)}
      />
    </>
  );
}
