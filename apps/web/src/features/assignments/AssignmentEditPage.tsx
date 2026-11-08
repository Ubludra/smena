import { api, ApiError } from "../../shared/api/client";
import { useApiToken, useAuth } from "../../shared/hooks/auth";
import { useAsync } from "../../shared/hooks/useAsync";
import { ErrorState } from "../../shared/ui/ErrorState";
import { Skeleton } from "../../shared/ui/Skeleton";
import { navigate } from "../../shared/lib/routes";
import { AssignmentForm } from "./AssignmentForm";

/** Edit route: load the assignment, then render the form with its values. */
export function AssignmentEditPage({ id }: { id: string }) {
  const token = useApiToken();
  const { handleUnauthorized } = useAuth();
  const { data, error, loading, reload } = useAsync(
    () => api.getAssignment(token, id),
    [token, id],
  );

  if (loading && !data) return <Skeleton lines={4} />;

  if (error) {
    if (error instanceof ApiError && error.isUnauthorized) {
      handleUnauthorized();
      return null;
    }
    if (error instanceof ApiError && error.status === 404) {
      return (
        <ErrorState
          message="Задание не найдено. Возможно, оно было удалено."
          onRetry={() => navigate("#/assignments")}
        />
      );
    }
    return <ErrorState message="Не удалось загрузить задание." onRetry={reload} />;
  }

  if (!data) return null;

  return (
    <>
      <div className="page-header">
        <div>
          <p className="eyebrow">ЗАДАНИЕ</p>
          <h1>Редактировать задание</h1>
        </div>
      </div>
      <AssignmentForm
        assignment={data}
        onSaved={() => undefined}
        onCancel={() => navigate(`#/assignments/${id}`)}
      />
    </>
  );
}
