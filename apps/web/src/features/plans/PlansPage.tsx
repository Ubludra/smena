import { useState } from "react";
import { api, ApiError } from "../../shared/api/client";
import { useApiToken, useAuth } from "../../shared/hooks/auth";
import { useAsync } from "../../shared/hooks/useAsync";
import { useDebounced } from "../../shared/hooks/useDebounced";
import { Button } from "../../shared/ui/Button";
import { EmptyState } from "../../shared/ui/EmptyState";
import { ErrorState } from "../../shared/ui/ErrorState";
import { MaterialListSkeleton } from "../../shared/ui/Skeleton";
import { navigate } from "../../shared/lib/routes";
import { relativeDate } from "../../shared/lib/dates";

/**
 * Lesson plans list: search (title/topic) + filter chips for class, subject
 * and a date range. Same state discipline as materials: skeleton → error →
 * two distinct empty states (nothing at all vs nothing matches the filters).
 */
export function PlansPage() {
  const [search, setSearch] = useState("");
  const [className, setClassName] = useState("");
  const [subject, setSubject] = useState("");
  const [dateFrom, setDateFrom] = useState("");
  const [dateTo, setDateTo] = useState("");
  const debouncedSearch = useDebounced(search);

  const hasFilters =
    className !== "" || subject !== "" || dateFrom !== "" || dateTo !== "";

  function clearFilters() {
    setClassName("");
    setSubject("");
    setDateFrom("");
    setDateTo("");
  }

  return (
    <>
      <div className="page-header page-intro">
        <div>
          <p className="eyebrow">РАСПИСАНИЕ И ПОДГОТОВКА</p>
          <h1>Планы уроков</h1>
        </div>
        <button
          type="button"
          className="header-create page-create"
          onClick={() => navigate("#/plans/new")}
        >
          <span aria-hidden="true">＋</span>
          Новый план
        </button>
      </div>

      <div className="search-row">
        <input
          type="search"
          className="search-input"
          placeholder="Поиск по названию или теме…"
          aria-label="Поиск планов"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
        />
      </div>

      <div className="filter-row" aria-label="Фильтры планов">
        <input
          className="filter-input"
          aria-label="Фильтр по классу"
          placeholder="Класс"
          value={className}
          onChange={(e) => setClassName(e.target.value)}
          maxLength={32}
        />
        <input
          className="filter-input"
          aria-label="Фильтр по предмету"
          placeholder="Предмет"
          value={subject}
          onChange={(e) => setSubject(e.target.value)}
          maxLength={120}
        />
        <label className="filter-label">
          с
          <input
            className="filter-input"
            aria-label="Дата с"
            type="date"
            value={dateFrom}
            onChange={(e) => setDateFrom(e.target.value)}
          />
        </label>
        <label className="filter-label">
          по
          <input
            className="filter-input"
            aria-label="Дата по"
            type="date"
            value={dateTo}
            onChange={(e) => setDateTo(e.target.value)}
          />
        </label>
        {hasFilters && (
          <button type="button" className="link-button" onClick={clearFilters}>
            Сбросить
          </button>
        )}
      </div>

      <PlanList
        search={debouncedSearch}
        className={className}
        subject={subject}
        dateFrom={dateFrom}
        dateTo={dateTo}
        onEmptyAction={() => navigate("#/plans/new")}
      />
    </>
  );
}

function PlanList(props: {
  search: string;
  className: string;
  subject: string;
  dateFrom: string;
  dateTo: string;
  onEmptyAction: () => void;
}) {
  const token = useApiToken();
  const { handleUnauthorized } = useAuth();
  const { data, error, loading, reload } = usePlans(token, props);

  if (loading && !data) return <MaterialListSkeleton />;

  if (error) {
    if (error instanceof ApiError && error.isUnauthorized) {
      handleUnauthorized();
      return null;
    }
    return (
      <ErrorState
        message="Не удалось загрузить планы. Проверьте соединение и попробуйте ещё раз."
        onRetry={reload}
      />
    );
  }

  if (!data) return null;

  const filtered = props.search !== "" || props.className !== "" || props.subject !== "" ||
    props.dateFrom !== "" || props.dateTo !== "";

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
        title="У вас пока нет планов уроков"
        description="Составьте первый план — он появится здесь и на Главной."
        action={<Button onClick={props.onEmptyAction}>Создать план</Button>}
      />
    );
  }

  return (
    <div className="material-list">
      {data.items.map((plan) => (
        <button
          type="button"
          className="card material-card plan-card"
          key={plan.id}
          onClick={() => navigate(`#/plans/${plan.id}`)}
        >
          <span className="material-card-title">{plan.title}</span>
          <span className="material-card-meta">
            {plan.class_name && <span>{plan.class_name}</span>}
            {plan.subject && <span>{plan.subject}</span>}
            {plan.lesson_date && (
              <span>{formatDate(plan.lesson_date, plan.start_time)}</span>
            )}
            <span>изменён {relativeDate(plan.updated_at)}</span>
          </span>
        </button>
      ))}
    </div>
  );
}

function usePlans(
  token: string | null,
  props: {
    search: string;
    className: string;
    subject: string;
    dateFrom: string;
    dateTo: string;
  },
) {
  return useAsync(() => {
    if (token === null) return Promise.reject(new Error("no token"));
    return api.listLessonPlans(token, {
      search: props.search,
      className: props.className,
      subject: props.subject,
      dateFrom: props.dateFrom,
      dateTo: props.dateTo,
    });
  }, [token, props.search, props.className, props.subject, props.dateFrom, props.dateTo]);
}

function formatDate(date: string, time: string | null): string {
  const [y, m, d] = date.split("-").map(Number);
  const base = `${d} ${MONTHS[(m ?? 1) - 1] ?? ""} ${y}`;
  return time === null ? base : `${base}, ${time.slice(0, 5)}`;
}

const MONTHS = [
  "января", "февраля", "марта", "апреля", "мая", "июня",
  "июля", "августа", "сентября", "октября", "ноября", "декабря",
] as const;
