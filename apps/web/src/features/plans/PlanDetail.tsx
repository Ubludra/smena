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

/**
 * Plan detail: read the whole scenario, then edit, duplicate or delete it.
 * Mirrors MaterialDetail's state handling (loading skeleton, 404 state,
 * unauthorized → re-login, inline failure notices with retry).
 */
export function PlanDetail({ id }: { id: string }) {
  const token = useApiToken();
  const { handleUnauthorized } = useAuth();
  const { data, error, loading, reload } = useAsync(
    () => api.getLessonPlan(token, id),
    [token, id],
  );
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState<string | null>(null);
  const [confirmOpen, setConfirmOpen] = useState(false);

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

  async function duplicate() {
    setBusy(true);
    setNotice(null);
    try {
      const copy = await api.duplicateLessonPlan(token, data!.id);
      navigate(`#/plans/${copy.id}`);
    } catch (err) {
      if (err instanceof ApiError && err.isUnauthorized) handleUnauthorized();
      else setNotice("Не удалось создать копию плана. Попробуйте ещё раз.");
      setBusy(false);
    }
  }

  async function remove() {
    setBusy(true);
    try {
      await api.deleteLessonPlan(token, data!.id);
      navigate("#/plans");
    } catch (err) {
      if (err instanceof ApiError && err.isUnauthorized) handleUnauthorized();
      else setNotice("Не удалось удалить план урока.");
      setBusy(false);
      setConfirmOpen(false);
    }
  }

  async function saveAsTemplate() {
    setBusy(true);
    setNotice(null);
    try {
      await api.createTemplate(token, {
        name: data!.title,
        entity_type: "lesson_plan",
        payload: {
          title: data!.title,
          subject: data!.subject,
          class_name: data!.class_name,
          duration_minutes: data!.duration_minutes,
          topic: data!.topic,
          goal: data!.goal,
          objectives: data!.objectives,
          stages: data!.stages,
          homework: data!.homework,
          notes: data!.notes,
        },
      });
      setNotice("Шаблон сохранён — он доступен в разделе «Шаблоны».");
    } catch (err) {
      if (err instanceof ApiError && err.isUnauthorized) handleUnauthorized();
      else setNotice("Не удалось сохранить шаблон. Попробуйте ещё раз.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <article className="material-detail plan-detail">
      <p className="eyebrow">ПЛАН УРОКА</p>
      <h1 className="detail-title">{data.title}</h1>
      <p className="detail-meta">
        {data.subject && <span>{data.subject} · </span>}
        {data.class_name && <span>{data.class_name} · </span>}
        изменён {relativeDate(data.updated_at)}
      </p>

      {data.lesson_date && (
        <div className="plan-when">
          <strong>{formatFullDate(data.lesson_date)}</strong>
          {data.start_time && <span> · начало {data.start_time.slice(0, 5)}</span>}
          {data.duration_minutes !== null && (
            <span> · {data.duration_minutes} мин</span>
          )}
        </div>
      )}

      <div className="detail-content plan-sections">
        <PlanSection title="Тема" text={data.topic} />
        <PlanSection title="Цель" text={data.goal} />
        {data.objectives.length > 0 && (
          <section className="plan-section">
            <h2>Задачи</h2>
            <ul className="plan-objectives">
              {data.objectives.map((objective, index) => (
                <li key={index}>{objective}</li>
              ))}
            </ul>
          </section>
        )}
        {data.stages.length > 0 && (
          <section className="plan-section">
            <h2>Ход урока</h2>
            <ol className="plan-stages">
              {data.stages.map((stage, index) => (
                <li key={index}>
                  <div className="plan-stage-head">
                    <strong>{stage.title}</strong>
                    {stage.minutes !== null && <span> — {stage.minutes} мин</span>}
                  </div>
                  {stage.description && <p>{stage.description}</p>}
                </li>
              ))}
            </ol>
          </section>
        )}
        <PlanSection title="Домашнее задание" text={data.homework} />
        <PlanSection title="Заметки" text={data.notes} />
      </div>

      <AttachedFiles
        target={{ kind: "lesson_plan", id: data.id }}
        emptyText="К этому плану файлов пока нет."
      />

      {notice && (
        <p className="inline-notice" role="status">
          {notice}
        </p>
      )}

      <div className="detail-actions">
        <Button variant="secondary" onClick={() => navigate(`#/plans/${data.id}/edit`)}>
          Редактировать
        </Button>
        <Button variant="secondary" busy={busy} onClick={() => void duplicate()}>
          Создать копию
        </Button>
        <Button variant="secondary" busy={busy} onClick={() => void saveAsTemplate()}>
          Сохранить как шаблон
        </Button>
        <Button variant="ghost" onClick={() => navigate("#/templates")}>
          Шаблоны
        </Button>
        <Button variant="ghost" className="danger-link" onClick={() => setConfirmOpen(true)}>
          Удалить
        </Button>
      </div>

      <ConfirmDialog
        open={confirmOpen}
        title="Удалить план?"
        description={`«${data.title}» будет удалён без возможности восстановления.`}
        confirmLabel="Удалить"
        busy={busy}
        onConfirm={() => void remove()}
        onCancel={() => setConfirmOpen(false)}
      />
    </article>
  );
}

function PlanSection({ title, text }: { title: string; text: string }) {
  if (text === "") return null;
  return (
    <section className="plan-section">
      <h2>{title}</h2>
      <p>{text}</p>
    </section>
  );
}

function formatFullDate(date: string): string {
  const [y, m, d] = date.split("-").map(Number);
  const months = [
    "января", "февраля", "марта", "апреля", "мая", "июня",
    "июля", "августа", "сентября", "октября", "ноября", "декабря",
  ];
  return `${d} ${months[(m ?? 1) - 1] ?? ""} ${y}`;
}
