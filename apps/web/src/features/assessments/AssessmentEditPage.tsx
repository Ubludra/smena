import { api, ApiError } from "../../shared/api/client";
import { useApiToken, useAuth } from "../../shared/hooks/auth";
import { useAsync } from "../../shared/hooks/useAsync";
import { ErrorState } from "../../shared/ui/ErrorState";
import { Skeleton } from "../../shared/ui/Skeleton";
import { navigate } from "../../shared/lib/routes";
import { AssessmentForm } from "./AssessmentForm";

/** Edit route: load the assessment, then render the form with its values. */
export function AssessmentEditPage({ id }: { id: string }) {
  const token = useApiToken();
  const { handleUnauthorized } = useAuth();
  const { data, error, loading, reload } = useAsync(
    () => api.getAssessment(token, id),
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
          message="Проверочная не найдена. Возможно, она была удалена."
          onRetry={() => navigate("#/assessments")}
        />
      );
    }
    return <ErrorState message="Не удалось загрузить проверочную." onRetry={reload} />;
  }

  if (!data) return null;

  return (
    <>
      <div className="page-header">
        <div>
          <p className="eyebrow">ПРОВЕРОЧНАЯ</p>
          <h1>Редактировать проверочную</h1>
        </div>
      </div>
      <AssessmentForm
        assessment={data}
        onSaved={() => undefined}
        onCancel={() => navigate(`#/assessments/${id}`)}
      />
    </>
  );
}
