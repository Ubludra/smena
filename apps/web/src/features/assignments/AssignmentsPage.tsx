import { useState } from "react";
import {
  api,
  ApiError,
  type ApiAssignment,
  type AssignmentStatus,
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

const STATUS_LABELS: Record<AssignmentStatus, string> = {
  active: "Активно",
  done: "Готово",
  archived: "В архиве",
};

const STATUS_FILTERS: { value: AssignmentStatus | ""; label: string }[] = [
  { value: "", label: "Все" },
  { value: "active", label: "Активные" },
  { value: "done", label: "Готовые" },
  { value: "archived", label: "Архив" },
];

export function AssignmentsPage() {
  const [search, setSearch] = useState("");
  const [status, setStatus] = useState<AssignmentStatus | "">("");
  const [className, setClassName] = useState("");
  const debouncedSearch = useDebounced(search);

  return (
    <>
      <div className="page-header page-intro">
        <div>
          <p className="eyebrow">КОНТРОЛЬ И СРОКИ</p>
          <h1>Задания</h1>
        </div>
        <button
          type="button"
          className="header-create page-create"
          onClick={() => navigate("#/assignments/new")}
        >
          <span aria-hidden="true">＋</span>
          Новое задание
        </button>
      </div>

      <div className="search-row">
        <input
          type="search"
          className="search-input"
          placeholder="Поиск по названию или описанию…"
          aria-label="Поиск заданий"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
        />
      </div>

      <div className="filter-row" aria-label="Фильтры заданий">
        <div className="chip-row" role="group" aria-label="Статус задания">
          {STATUS_FILTERS.map((filter) => (
            <button
              type="button"
              key={filter.value || "all"}
              className={`chip${status === filter.value ? " chip-active" : ""}`}
              aria-pressed={status === filter.value}
              onClick={() => setStatus(filter.value)}
            >
              {filter.label}
            </button>
          ))}
        </div>
        <input
          className="filter-input"
          aria-label="Фильтр по классу"
          placeholder="Класс"
          value={className}
          onChange={(e) => setClassName(e.target.value)}
          maxLength={32}
        />
      </div>

      <AssignmentList
        search={debouncedSearch}
        status={status}
        className={className}
        onEmptyAction={() => navigate("#/assignments/new")}
      />
    </>
  );
}

function AssignmentList(props: {
  search: string;
  status: AssignmentStatus | "";
  className: string;
  onEmptyAction: () => void;
}) {
  const token = useApiToken();
  const { handleUnauthorized } = useAuth();
  const { data, error, loading, reload } = useAsync(() => {
    if (token === null) return Promise.reject(new Error("no token"));
    return api.listAssignments(token, {
      search: props.search,
      status: props.status,
      className: props.className,
    });
  }, [token, props.search, props.status, props.className]);

  if (loading && !data) return <MaterialListSkeleton />;

  if (error) {
    if (error instanceof ApiError && error.isUnauthorized) {
      handleUnauthorized();
      return null;
    }
    return (
      <ErrorState
        message="Не удалось загрузить задания. Проверьте соединение и попробуйте ещё раз."
        onRetry={reload}
      />
    );
  }

  if (!data) return null;

  const filtered =
    props.search !== "" || props.status !== "" || props.className !== "";

  if (data.items.length === 0) {
    if (filtered) {
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
        title="У вас пока нет заданий"
        description="Создайте первое задание — активные с ближайшим сроком будут видны на Главной."
        action={<Button onClick={props.onEmptyAction}>Создать задание</Button>}
      />
    );
  }

  return (
    <div className="material-list">
      {data.items.map((assignment) => (
        <AssignmentCard key={assignment.id} assignment={assignment} />
      ))}
    </div>
  );
}

function AssignmentCard({ assignment }: { assignment: ApiAssignment }) {
  const overdue =
    assignment.status === "active" &&
    assignment.due_at !== null &&
    new Date(assignment.due_at).getTime() < Date.now();

  return (
    <button
      type="button"
      className="card material-card plan-card"
      onClick={() => navigate(`#/assignments/${assignment.id}`)}
    >
      <span className="material-card-title">
        {assignment.title}
        <span className={`status-badge status-${assignment.status}`}>
          {STATUS_LABELS[assignment.status]}
        </span>
        {overdue && <span className="status-badge status-overdue">Просрочено</span>}
      </span>
      <span className="material-card-meta">
        {assignment.class_name && <span>{assignment.class_name}</span>}
        {assignment.subject && <span>{assignment.subject}</span>}
        {assignment.due_at && (
          <span>до {formatDateTime(assignment.due_at)}</span>
        )}
        <span>изменено {relativeDate(assignment.updated_at)}</span>
      </span>
    </button>
  );
}

function formatDateTime(value: string): string {
  const date = new Date(value);
  return date.toLocaleString("ru-RU", {
    day: "numeric",
    month: "short",
    hour: "2-digit",
    minute: "2-digit",
  });
}
