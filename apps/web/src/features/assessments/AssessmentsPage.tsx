import { useState } from "react";
import {
  api,
  ApiError,
  type ApiAssessment,
} from "../../shared/api/client";
import { useApiToken, useAuth } from "../../shared/hooks/auth";
import { useAsync } from "../../shared/hooks/useAsync";
import { useDebounced } from "../../shared/hooks/useDebounced";
import { Button } from "../../shared/ui/Button";
import { EmptyState } from "../../shared/ui/EmptyState";
import { ErrorState } from "../../shared/ui/ErrorState";
import { MaterialListSkeleton } from "../../shared/ui/Skeleton";
import { navigate } from "../../shared/lib/routes";
import { relativeDate } from "../../shared/lib/dates";

/** Assessments list («Проверочные»): search + class filter + Safe flag. */
export function AssessmentsPage() {
  const [search, setSearch] = useState("");
  const [className, setClassName] = useState("");
  const debouncedSearch = useDebounced(search);

  return (
    <>
      <div className="page-header page-intro">
        <div>
          <p className="eyebrow">КОНТРОЛЬ ЗНАНИЙ</p>
          <h1>Проверочные</h1>
        </div>
        <button
          type="button"
          className="header-create page-create"
          onClick={() => navigate("#/assessments/new")}
        >
          <span aria-hidden="true">＋</span>
          Новая проверочная
        </button>
      </div>

      <div className="search-row">
        <input
          type="search"
          className="search-input"
          placeholder="Поиск по названию…"
          aria-label="Поиск проверочных"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
        />
      </div>

      <div className="filter-row" aria-label="Фильтры проверочных">
        <input
          className="filter-input"
          aria-label="Фильтр по классу"
          placeholder="Класс"
          value={className}
          onChange={(e) => setClassName(e.target.value)}
          maxLength={32}
        />
      </div>

      <AssessmentList
        search={debouncedSearch}
        className={className}
        onEmptyAction={() => navigate("#/assessments/new")}
      />
    </>
  );
}

function AssessmentList(props: {
  search: string;
  className: string;
  onEmptyAction: () => void;
}) {
  const token = useApiToken();
  const { handleUnauthorized } = useAuth();
  const { data, error, loading, reload } = useAsync(() => {
    if (token === null) return Promise.reject(new Error("no token"));
    return api.listAssessments(token, {
      search: props.search,
      className: props.className,
    });
  }, [token, props.search, props.className]);

  if (loading && !data) return <MaterialListSkeleton />;

  if (error) {
    if (error instanceof ApiError && error.isUnauthorized) {
      handleUnauthorized();
      return null;
    }
    return (
      <ErrorState
        message="Не удалось загрузить проверочные. Проверьте соединение и попробуйте ещё раз."
        onRetry={reload}
      />
    );
  }

  if (!data) return null;

  if (data.items.length === 0) {
    if (props.search || props.className) {
      return (
        <EmptyState
          icon="search"
          title="Ничего не нашлось"
          description="Попробуйте изменить запрос или сбросить фильтры."
        />
      );
    }
    return (
      <EmptyState
        icon="folder"
        title="У вас пока нет проверочных"
        description="Составьте первую работу с вопросами и ответами."
        action={<Button onClick={props.onEmptyAction}>Создать проверочную</Button>}
      />
    );
  }

  return (
    <div className="material-list">
      {data.items.map((assessment) => (
        <AssessmentCard key={assessment.id} assessment={assessment} />
      ))}
    </div>
  );
}

function AssessmentCard({ assessment }: { assessment: ApiAssessment }) {
  return (
    <button
      type="button"
      className="card material-card plan-card"
      onClick={() => navigate(`#/assessments/${assessment.id}`)}
    >
      <span className="material-card-title">
        {assessment.title}
        {assessment.is_protected && <span className="status-badge status-active">Сейф</span>}
      </span>
      <span className="material-card-meta">
        {assessment.class_name && <span>{assessment.class_name}</span>}
        {assessment.subject && <span>{assessment.subject}</span>}
        <span>
          {assessment.questions.length}{" "}
          {pluralQuestions(assessment.questions.length)}
        </span>
        <span>изменено {relativeDate(assessment.updated_at)}</span>
      </span>
    </button>
  );
}

function pluralQuestions(count: number): string {
  const mod10 = count % 10;
  const mod100 = count % 100;
  if (mod10 === 1 && mod100 !== 11) return "вопрос";
  if (mod10 >= 2 && mod10 <= 4 && (mod100 < 12 || mod100 > 14)) return "вопроса";
  return "вопросов";
}
