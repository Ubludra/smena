import { useState } from "react";
import {
  api,
  ApiError,
  type ApiTemplate,
  type TemplateEntityType,
} from "../../shared/api/client";
import { useApiToken, useAuth } from "../../shared/hooks/auth";
import { useAsync } from "../../shared/hooks/useAsync";
import { Button } from "../../shared/ui/Button";
import { ConfirmDialog } from "../../shared/ui/ConfirmDialog";
import { EmptyState } from "../../shared/ui/EmptyState";
import { ErrorState } from "../../shared/ui/ErrorState";
import { MaterialListSkeleton } from "../../shared/ui/Skeleton";
import { navigate } from "../../shared/lib/routes";
import { relativeDate } from "../../shared/lib/dates";

const TYPE_LABELS: Record<TemplateEntityType, string> = {
  lesson_plan: "План урока",
  assignment: "Задание",
  assessment: "Проверочная",
  report: "Отчёт",
};

const TYPE_ROUTES: Record<TemplateEntityType, string> = {
  lesson_plan: "#/plans",
  assignment: "#/assignments",
  assessment: "#/assessments",
  report: "#/reports",
};

/**
 * Templates: each entry is a head start, not a decoration. Using a template
 * opens the entity's own create form prefilled — the result is a normal
 * object the teacher edits and saves.
 */
export function TemplatesPage() {
  const [entityType, setEntityType] = useState<TemplateEntityType | "">("");
  const [deleting, setDeleting] = useState<ApiTemplate | null>(null);
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState<string | null>(null);
  const [listNonce, setListNonce] = useState(0);
  const token = useApiToken();
  const { handleUnauthorized } = useAuth();

  async function removeTemplate() {
    if (deleting === null) return;
    setBusy(true);
    setNotice(null);
    try {
      await api.deleteTemplate(token, deleting.id);
      setDeleting(null);
      setListNonce((n) => n + 1);
    } catch (err) {
      if (err instanceof ApiError && err.isUnauthorized) handleUnauthorized();
      else setNotice("Не удалось удалить шаблон. Попробуйте ещё раз.");
      setBusy(false);
    }
  }

  return (
    <>
      <div className="page-header page-intro">
        <div>
          <p className="eyebrow">БЫСТРЫЙ СТАРТ</p>
          <h1>Шаблоны</h1>
          <p className="page-description">
            Заготовки для планов, заданий, проверочных и отчётов — начните с готового.
          </p>
        </div>
      </div>

      <div className="filter-row" aria-label="Фильтр шаблонов по типу">
        <div className="chip-row" role="group" aria-label="Тип шаблона">
          <button
            type="button"
            className={`chip${entityType === "" ? " chip-active" : ""}`}
            aria-pressed={entityType === ""}
            onClick={() => setEntityType("")}
          >
            Все
          </button>
          {(Object.keys(TYPE_LABELS) as TemplateEntityType[]).map((type) => (
            <button
              type="button"
              key={type}
              className={`chip${entityType === type ? " chip-active" : ""}`}
              aria-pressed={entityType === type}
              onClick={() => setEntityType(type)}
            >
              {TYPE_LABELS[type]}
            </button>
          ))}
        </div>
      </div>

      {notice && (
        <p className="inline-notice" role="status">
          {notice}
        </p>
      )}

      <TemplateList
        entityType={entityType}
        listNonce={listNonce}
        onDelete={(template) => setDeleting(template)}
      />

      <ConfirmDialog
        open={deleting !== null}
        title="Удалить шаблон?"
        description={
          deleting
            ? `«${deleting.name}» будет удалён без возможности восстановления.`
            : ""
        }
        confirmLabel="Удалить"
        busy={busy}
        onConfirm={() => void removeTemplate()}
        onCancel={() => setDeleting(null)}
      />
    </>
  );
}

function TemplateList(props: {
  entityType: TemplateEntityType | "";
  listNonce: number;
  onDelete: (template: ApiTemplate) => void;
}) {
  const token = useApiToken();
  const { handleUnauthorized } = useAuth();
  const { data, error, loading, reload } = useAsync(() => {
    if (token === null) return Promise.reject(new Error("no token"));
    return api.listTemplates(token, {
      entityType: props.entityType === "" ? undefined : props.entityType,
    });
  }, [token, props.entityType, props.listNonce]);

  if (loading && !data) return <MaterialListSkeleton />;

  if (error) {
    if (error instanceof ApiError && error.isUnauthorized) {
      handleUnauthorized();
      return null;
    }
    return (
      <ErrorState
        message="Не удалось загрузить шаблоны. Проверьте соединение и попробуйте ещё раз."
        onRetry={reload}
      />
    );
  }

  if (!data) return null;

  if (data.items.length === 0) {
    return (
      <EmptyState
        icon="folder"
        title={
          props.entityType === "" ? "У вас пока нет шаблонов" : "Нет шаблонов этого типа"
        }
        description={
          props.entityType === ""
            ? "Откройте план, задание или проверочную и нажмите «Сохранить как шаблон»."
            : "Сохраните шаблон этого типа из соответствующего раздела."
        }
      />
    );
  }

  return (
    <div className="material-list">
      {data.items.map((template) => (
        <div className="template-card-row" key={template.id}>
          <button
            type="button"
            className="card material-card plan-card"
            onClick={() =>
              navigate(`${TYPE_ROUTES[template.entity_type]}/from/${template.id}`)
            }
          >
            <span className="material-card-title">{template.name}</span>
            <span className="material-card-meta">
              <span>{TYPE_LABELS[template.entity_type]}</span>
              <span>изменён {relativeDate(template.updated_at)}</span>
            </span>
          </button>
          {/* System skeletons are seeded read-only: no delete affordance. */}
          {!template.is_system && (
            <Button variant="ghost" onClick={() => props.onDelete(template)}>
              Удалить
            </Button>
          )}
        </div>
      ))}
    </div>
  );
}
