import { api, ApiError } from "../../shared/api/client";
import { useApiToken, useAuth } from "../../shared/hooks/auth";
import { useAsync } from "../../shared/hooks/useAsync";
import { ErrorState } from "../../shared/ui/ErrorState";
import { Skeleton } from "../../shared/ui/Skeleton";
import { MaterialForm } from "./MaterialForm";

/**
 * Create route: renders an empty form, or — when opened from a report
 * template («Использовать» on #/templates) — loads the template and
 * prefills the form with its skeleton. A missing or non-report template
 * falls back to an empty form rather than breaking the page.
 */
export function MaterialCreatePage({ templateId }: { templateId?: string }) {
  const token = useApiToken();
  const { handleUnauthorized } = useAuth();
  const template = useAsync(
    () =>
      templateId === undefined
        ? Promise.resolve(null)
        : api.getTemplate(token, templateId),
    [token, templateId],
  );

  if (templateId !== undefined && template.loading && !template.data) {
    return <Skeleton lines={6} />;
  }

  if (template.error) {
    if (template.error instanceof ApiError && template.error.isUnauthorized) {
      handleUnauthorized();
      return null;
    }
    // Unknown template id: the form still works, just not prefilled —
    // same contract as the plan create page.
    if (!(template.error instanceof ApiError && template.error.status === 404)) {
      return (
        <ErrorState
          message="Не удалось загрузить шаблон."
          onRetry={template.reload}
        />
      );
    }
  }

  const preset =
    template.data && template.data.entity_type === "report"
      ? template.data.payload
      : undefined;
  const templateName = template.data?.name;

  return (
    <>
      <div className="page-header">
        <div>
          <p className="eyebrow">ВАША БИБЛИОТЕКА</p>
          <h1>
            {templateName
              ? `Новый материал из шаблона «${templateName}»`
              : "Создать материал"}
          </h1>
        </div>
      </div>
      <MaterialForm preset={preset} onSaved={() => undefined} />
    </>
  );
}
