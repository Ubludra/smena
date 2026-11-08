import { useState } from "react";
import { api, ApiError } from "../../shared/api/client";
import { useApiToken, useAuth } from "../../shared/hooks/auth";
import { useAsync } from "../../shared/hooks/useAsync";
import { relativeDate } from "../../shared/lib/dates";
import { AttachedFiles } from "../../shared/ui/AttachedFiles";
import { Button } from "../../shared/ui/Button";
import { ConfirmDialog } from "../../shared/ui/ConfirmDialog";
import { ErrorState } from "../../shared/ui/ErrorState";
import { Skeleton } from "../../shared/ui/Skeleton";
import { navigate } from "../../shared/lib/routes";

const STATUS_LABELS: Record<string, string> = {
  active: "Активно",
  done: "Готово",
  archived: "В архиве",
};

/** Assignment detail: read, status transitions, edit, delete. */
export function AssignmentDetail({ id }: { id: string }) {
  const token = useApiToken();
  const { handleUnauthorized } = useAuth();
  const { data, error, loading, reload } = useAsync(
    () => api.getAssignment(token, id),
    [token, id],
  );
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState<string | null>(null);
  const [confirmOpen, setConfirmOpen] = useState(false);

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

  async function setStatus(status: "active" | "done" | "archived") {
    setBusy(true);
    setNotice(null);
    try {
      await api.updateAssignment(token, data!.id, { status });
      reload();
    } catch (err) {
      if (err instanceof ApiError && err.isUnauthorized) handleUnauthorized();
      else setNotice("Не удалось изменить статус. Попробуйте ещё раз.");
    } finally {
      setBusy(false);
    }
  }

  async function remove() {
    setBusy(true);
    try {
      await api.deleteAssignment(token, data!.id);
      navigate("#/assignments");
    } catch (err) {
      if (err instanceof ApiError && err.isUnauthorized) handleUnauthorized();
      else setNotice("Не удалось удалить задание.");
      setBusy(false);
      setConfirmOpen(false);
    }
  }

  const overdue =
    data.status === "active" &&
    data.due_at !== null &&
    new Date(data.due_at).getTime() < Date.now();

  return (
    <article className="material-detail plan-detail">
      <p className="eyebrow">ЗАДАНИЕ</p>
      <h1 className="detail-title">
        {data.title}
        <span className={`status-badge status-${data.status}`}>
          {STATUS_LABELS[data.status]}
        </span>
        {overdue && <span className="status-badge status-overdue">Просрочено</span>}
      </h1>
      <p className="detail-meta">
        {data.class_name && <span>{data.class_name} · </span>}
        {data.subject && <span>{data.subject} · </span>}
        изменено {relativeDate(data.updated_at)}
      </p>

      {data.due_at && (
        <div className="plan-when">
          Срок сдачи: <strong>{formatDue(data.due_at)}</strong>
        </div>
      )}

      <div className="detail-content plan-sections">
        {data.description !== "" && (
          <section className="plan-section">
            <h2>Описание</h2>
            <p>{data.description}</p>
          </section>
        )}
      </div>

      {notice && (
        <p className="inline-notice" role="status">
          {notice}
        </p>
      )}

      <div className="detail-actions">
        {data.status !== "done" && (
          <Button variant="secondary" busy={busy} onClick={() => void setStatus("done")}>
            Отметить выполненным
          </Button>
        )}
        {data.status !== "archived" && (
          <Button variant="secondary" busy={busy} onClick={() => void setStatus("archived")}>
            В архив
          </Button>
        )}
        {data.status !== "active" && (
          <Button variant="ghost" busy={busy} onClick={() => void setStatus("active")}>
            Вернуть в активные
          </Button>
        )}
        <Button variant="secondary" onClick={() => navigate(`#/assignments/${data.id}/edit`)}>
          Редактировать
        </Button>
        <Button variant="ghost" className="danger-link" onClick={() => setConfirmOpen(true)}>
          Удалить
        </Button>
      </div>

      <AttachedFiles
        target={{ kind: "assignment", id: data.id }}
        emptyText="К этому заданию файлов пока нет."
      />

      <ConfirmDialog
        open={confirmOpen}
        title="Удалить задание?"
        description={`«${data.title}» будет удалено без возможности восстановления.`}
        confirmLabel="Удалить"
        busy={busy}
        onConfirm={() => void remove()}
        onCancel={() => setConfirmOpen(false)}
      />
    </article>
  );
}

function formatDue(value: string): string {
  return new Date(value).toLocaleString("ru-RU", {
    day: "numeric",
    month: "long",
    hour: "2-digit",
    minute: "2-digit",
  });
}
