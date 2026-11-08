/**
 * Shared list view for «Мои материалы» and «Сейф».
 *
 * Covers all required states: skeleton while loading, ErrorState with retry,
 * two distinct empty states (no materials at all vs nothing found by the
 * search), and the plain list.
 */

import { useEffect } from "react";
import { api, ApiError, type ApiMaterial } from "../../shared/api/client";
import { useApiToken, useAuth } from "../../shared/hooks/auth";
import { useAsync } from "../../shared/hooks/useAsync";
import { Button } from "../../shared/ui/Button";
import { EmptyState } from "../../shared/ui/EmptyState";
import { ErrorState } from "../../shared/ui/ErrorState";
import { MaterialListSkeleton } from "../../shared/ui/Skeleton";
import { navigate } from "../../shared/lib/routes";
import { MaterialCard } from "./MaterialCard";

interface MaterialsListProps {
  search: string;
  onlyProtected: boolean;
  onEmptyAction?: () => void;
  /** Protected listing answered 403: the Safe unlock died (expired). */
  onSafeLocked?: () => void;
  emptyTitle?: string;
  emptyDescription?: string;
  emptyIcon?: "folder" | "lock";
}

export function MaterialsList({
  search,
  onlyProtected,
  onEmptyAction,
  onSafeLocked,
  emptyTitle = "У вас пока нет материалов",
  emptyDescription = "Добавьте первый материал — он появится здесь.",
  emptyIcon = "folder",
}: MaterialsListProps) {
  const token = useApiToken();
  const { handleUnauthorized } = useAuth();
  const { data, error, loading, reload } = useAsync(
    () => api.listMaterials(token, { search, onlyProtected }),
    [token, search, onlyProtected],
  );

  const safeLocked = onlyProtected && error instanceof ApiError && error.status === 403;
  useEffect(() => {
    if (safeLocked) onSafeLocked?.();
  }, [safeLocked, onSafeLocked]);

  if (loading && !data) return <MaterialListSkeleton />;

  if (error) {
    if (error instanceof ApiError && error.isUnauthorized) {
      handleUnauthorized();
      return null;
    }
    if (safeLocked) {
      // The Safe screen replaced this list moments ago; keep it quiet.
      return null;
    }
    return (
      <ErrorState
        message="Не удалось загрузить материалы. Проверьте соединение и попробуйте ещё раз."
        onRetry={reload}
      />
    );
  }

  if (!data) return null;

  if (data.items.length === 0) {
    if (search) {
      return (
        <EmptyState
          icon="search"
          title="Ничего не нашлось"
          description="Попробуйте изменить запрос или очистить поиск."
        />
      );
    }
    return (
      <EmptyState
        icon={emptyIcon}
        title={emptyTitle}
        description={emptyDescription}
        action={
          onEmptyAction ? (
            <Button onClick={onEmptyAction}>Создать материал</Button>
          ) : undefined
        }
      />
    );
  }

  return (
    <>
      <div className="materials-list-toolbar">
        <p className="materials-count" role="status">
          {data.total} {materialWord(data.total)}
        </p>
        {onEmptyAction && (
          <button
            type="button"
            className="text-action"
            onClick={onEmptyAction}
          >
            Создать материал <span aria-hidden="true">→</span>
          </button>
        )}
      </div>
      <List items={data.items} />
    </>
  );
}

function List({ items }: { items: ApiMaterial[] }) {
  return (
    <div className="material-list material-grid">
      {items.map((material) => (
        <MaterialCard
          key={material.id}
          material={material}
          onOpen={(id) => navigate(`#/materials/${id}`)}
        />
      ))}
    </div>
  );
}

function materialWord(count: number): string {
  const mod10 = count % 10;
  const mod100 = count % 100;
  if (mod10 === 1 && mod100 !== 11) return "материал";
  if (mod10 >= 2 && mod10 <= 4 && (mod100 < 12 || mod100 > 14)) {
    return "материала";
  }
  return "материалов";
}
