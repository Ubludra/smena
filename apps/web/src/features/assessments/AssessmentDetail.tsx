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

/** Assessment detail: questions with a show/hide answer-key toggle. */
export function AssessmentDetail({ id }: { id: string }) {
  const token = useApiToken();
  const { handleUnauthorized } = useAuth();
  const { data, error, loading, reload } = useAsync(
    () => api.getAssessment(token, id),
    [token, id],
  );
  const [busy, setBusy] = useState(false);
  const [showAnswers, setShowAnswers] = useState(false);
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
          message="Проверочная не найдена. Возможно, она была удалена."
          onRetry={() => navigate("#/assessments")}
        />
      );
    }
    if (error instanceof ApiError && error.status === 403) {
      return (
        <ErrorState
          message="Проверочная в Сейфе: сначала разблокируйте Сейф паролем."
          onRetry={() => navigate("#/safe")}
        />
      );
    }
    return <ErrorState message="Не удалось загрузить проверочную." onRetry={reload} />;
  }

  if (!data) return null;

  async function duplicate() {
    setBusy(true);
    setNotice(null);
    try {
      const copy = await api.duplicateAssessment(token, data!.id);
      navigate(`#/assessments/${copy.id}`);
    } catch (err) {
      if (err instanceof ApiError && err.isUnauthorized) handleUnauthorized();
      else setNotice("Не удалось создать копию. Попробуйте ещё раз.");
      setBusy(false);
    }
  }

  async function toggleProtected() {
    setBusy(true);
    setNotice(null);
    try {
      await api.updateAssessment(token, data!.id, {
        is_protected: !data!.is_protected,
      });
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
      await api.deleteAssessment(token, data!.id);
      navigate("#/assessments");
    } catch (err) {
      if (err instanceof ApiError && err.isUnauthorized) handleUnauthorized();
      else setNotice("Не удалось удалить проверочную.");
      setBusy(false);
      setConfirmOpen(false);
    }
  }

  return (
    <article className="material-detail plan-detail">
      <p className="eyebrow">ПРОВЕРОЧНАЯ</p>
      <h1 className="detail-title">
        {data.title}
        {data.is_protected && <span className="status-badge status-active">Сейф</span>}
      </h1>
      <p className="detail-meta">
        {data.subject && <span>{data.subject} · </span>}
        {data.class_name && <span>{data.class_name} · </span>}
        {data.duration_minutes !== null && <span>{data.duration_minutes} мин · </span>}
        изменено {relativeDate(data.updated_at)}
      </p>

      <div className="detail-content plan-sections">
        {data.description !== "" && (
          <section className="plan-section">
            <h2>Описание</h2>
            <p>{data.description}</p>
          </section>
        )}
        <section className="plan-section">
          <div className="section-head-inline">
            <h2>Вопросы ({data.questions.length})</h2>
            <button
              type="button"
              className="link-button"
              aria-pressed={showAnswers}
              onClick={() => setShowAnswers((shown) => !shown)}
            >
              {showAnswers ? "Скрыть ответы" : "Показать ответы"}
            </button>
          </div>
          <ol className="plan-stages">
            {data.questions.map((question) => (
              <li key={question.id}>
                <div className="plan-stage-head">
                  <strong>{question.text}</strong>
                </div>
                {question.type !== "text" && (
                  <ul className="plan-options">
                    {question.options.map((option, optionIndex) => (
                      <li
                        key={optionIndex}
                        className={
                          showAnswers && (question.correct as number[]).includes(optionIndex)
                            ? "option-correct"
                            : undefined
                        }
                      >
                        {option}
                      </li>
                    ))}
                  </ul>
                )}
                {showAnswers && (
                  <p className="plan-answer">
                    Ответ:{" "}
                    {question.correct
                      .map((key) =>
                        question.type === "text" ? String(key) : question.options[Number(key)],
                      )
                      .join(", ")}
                  </p>
                )}
              </li>
            ))}
          </ol>
        </section>
      </div>

      <AttachedFiles
        target={{ kind: "assessment", id: data.id }}
        emptyText="К этой проверочной файлов пока нет."
      />

      {notice && (
        <p className="inline-notice" role="status">
          {notice}
        </p>
      )}

      <div className="detail-actions">
        <Button variant="secondary" onClick={() => navigate(`#/assessments/${data.id}/edit`)}>
          Редактировать
        </Button>
        <Button variant="secondary" busy={busy} onClick={() => void duplicate()}>
          Создать копию
        </Button>
        <Button variant="secondary" busy={busy} onClick={() => void toggleProtected()}>
          {data.is_protected ? "Убрать из Сейфа" : "Добавить в Сейф"}
        </Button>
        <Button variant="ghost" className="danger-link" onClick={() => setConfirmOpen(true)}>
          Удалить
        </Button>
      </div>

      <ConfirmDialog
        open={confirmOpen}
        title="Удалить проверочную?"
        description={`«${data.title}» будет удалена без возможности восстановления.`}
        confirmLabel="Удалить"
        busy={busy}
        onConfirm={() => void remove()}
        onCancel={() => setConfirmOpen(false)}
      />
    </article>
  );
}
