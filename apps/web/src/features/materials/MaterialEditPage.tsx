import { api, ApiError } from "../../shared/api/client";
import { useApiToken, useAuth } from "../../shared/hooks/auth";
import { useAsync } from "../../shared/hooks/useAsync";
import { ErrorState } from "../../shared/ui/ErrorState";
import { Skeleton } from "../../shared/ui/Skeleton";
import { navigate } from "../../shared/lib/routes";
import { MaterialForm } from "./MaterialForm";

/** Edit route: load the material, then render the form with its values. */
export function MaterialEditPage({ id }: { id: string }) {
  const token = useApiToken();
  const { handleUnauthorized } = useAuth();
  const { data, error, loading, reload } = useAsync(
    () => api.getMaterial(token, id),
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
          message="Материал не найден. Возможно, он был удалён."
          onRetry={() => navigate("#/materials")}
        />
      );
    }
    return <ErrorState message="Не удалось загрузить материал." onRetry={reload} />;
  }

  if (!data) return null;

  return (
    <>
      <div className="page-header">
        <div>
          <p className="eyebrow">ВАША БИБЛИОТЕКА</p>
          <h1>Редактировать материал</h1>
        </div>
      </div>
      <MaterialForm material={data} onSaved={() => undefined} />
    </>
  );
}
