import { api, ApiError } from "../../shared/api/client";
import { useApiToken, useAuth } from "../../shared/hooks/auth";
import { useAsync } from "../../shared/hooks/useAsync";
import { ErrorState } from "../../shared/ui/ErrorState";
import { Skeleton } from "../../shared/ui/Skeleton";
import { navigate } from "../../shared/lib/routes";
import { PlanForm } from "./PlanForm";

/**
 * Create route: renders an empty form, or — when opened from a template —
 * loads the template and prefills it. A non-plan template falls back to an
 * empty form rather than breaking the page.
 */
export function PlanCreatePage({ templateId }: { templateId?: string }) {
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
    // Unknown/foreign template: the form still works, just not prefilled.
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
    template.data && template.data.entity_type === "lesson_plan"
      ? template.data.payload
      : undefined;
  const templateName = template.data?.name;

  return (
    <>
      <div className="page-header">
        <div>
          <p className="eyebrow">ПЛАН УРОКА</p>
          <h1>
            {templateName ? `Новый план из шаблона «${templateName}»` : "Новый план урока"}
          </h1>
        </div>
      </div>
      <PlanForm
        preset={preset}
        onSaved={() => undefined}
        onCancel={() => navigate("#/plans")}
      />
    </>
  );
}
