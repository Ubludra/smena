import { useMemo, useState } from "react";
import {
  api,
  ApiError,
  type ApiCalendarEvent,
  type CalendarEventType,
} from "../../shared/api/client";
import { useApiToken, useAuth } from "../../shared/hooks/auth";
import { useAsync } from "../../shared/hooks/useAsync";
import { EmptyState } from "../../shared/ui/EmptyState";
import { ErrorState } from "../../shared/ui/ErrorState";
import { MaterialListSkeleton } from "../../shared/ui/Skeleton";
import { navigate } from "../../shared/lib/routes";

/**
 * Calendar: one month at a glance. Everything on the grid comes from the
 * server's aggregation (plans with a date, active assignment deadlines,
 * scheduled assessments) — the frontend draws dots, it does not invent
 * events. Clicking an event opens the entity it came from.
 */

const WEEKDAYS = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"];

const MONTH_NAMES = [
  "Январь", "Февраль", "Март", "Апрель", "Май", "Июнь",
  "Июль", "Август", "Сентябрь", "Октябрь", "Ноябрь", "Декабрь",
];

/** Genitive case for aria-labels: "25 октября 2026". */
const MONTH_GENITIVE = [
  "января", "февраля", "марта", "апреля", "мая", "июня",
  "июля", "августа", "сентября", "октября", "ноября", "декабря",
];

const TYPE_LABEL: Record<CalendarEventType, string> = {
  lesson_plan: "Урок",
  assignment: "Срок сдачи",
  assessment: "Проверочная",
};

const TYPE_ROUTE: Record<CalendarEventType, string> = {
  lesson_plan: "#/plans",
  assignment: "#/assignments",
  assessment: "#/assessments",
};

interface GridCell {
  day: number;
  iso: string;
  inMonth: boolean;
}

/** Monday-first 6-week grid covering the month (trailing days may be null). */
function buildGrid(year: number, month: number): (GridCell | null)[] {
  const first = new Date(year, month - 1, 1);
  const daysInMonth = new Date(year, month, 0).getDate();
  const lead = (first.getDay() + 6) % 7; // Monday = 0
  const cells: (GridCell | null)[] = [];
  for (let i = 0; i < lead; i += 1) cells.push(null);
  for (let day = 1; day <= daysInMonth; day += 1) {
    const iso = `${year}-${String(month).padStart(2, "0")}-${String(day).padStart(2, "0")}`;
    cells.push({ day, iso, inMonth: true });
  }
  while (cells.length % 7 !== 0) cells.push(null);
  return cells;
}

function shiftMonth(year: number, month: number, delta: number) {
  const next = new Date(year, month - 1 + delta, 1);
  return { year: next.getFullYear(), month: next.getMonth() + 1 };
}

export function CalendarPage() {
  const today = useMemo(() => new Date(), []);
  const [cursor, setCursor] = useState({
    year: today.getFullYear(),
    month: today.getMonth() + 1,
  });
  const token = useApiToken();
  const { handleUnauthorized } = useAuth();
  const { data, error, loading, reload } = useAsync(() => {
    if (token === null) return Promise.reject(new Error("no token"));
    return api.getCalendar(token, cursor);
  }, [token, cursor.year, cursor.month]);

  const grid = useMemo(
    () => buildGrid(cursor.year, cursor.month),
    [cursor.year, cursor.month],
  );

  const eventsByDay = useMemo(() => {
    const map = new Map<string, ApiCalendarEvent[]>();
    for (const event of data?.events ?? []) {
      const list = map.get(event.date) ?? [];
      list.push(event);
      map.set(event.date, list);
    }
    return map;
  }, [data]);

  const todayIso = `${today.getFullYear()}-${String(today.getMonth() + 1).padStart(2, "0")}-${String(today.getDate()).padStart(2, "0")}`;
  const hasEvents = (data?.events.length ?? 0) > 0;

  return (
    <>
      <div className="page-header page-intro">
        <div>
          <p className="eyebrow">КАЛЕНДАРЬ</p>
          <h1>
            {MONTH_NAMES[cursor.month - 1]} {cursor.year}
          </h1>
        </div>
      </div>

      <div className="calendar-toolbar">
        <button
          type="button"
          className="calendar-nav"
          aria-label="Предыдущий месяц"
          onClick={() => setCursor((c) => shiftMonth(c.year, c.month, -1))}
        >
          ‹
        </button>
        <button
          type="button"
          className="calendar-today"
          onClick={() =>
            setCursor({ year: today.getFullYear(), month: today.getMonth() + 1 })
          }
        >
          Сегодня
        </button>
        <button
          type="button"
          className="calendar-nav"
          aria-label="Следующий месяц"
          onClick={() => setCursor((c) => shiftMonth(c.year, c.month, 1))}
        >
          ›
        </button>
      </div>

      {loading && !data && <MaterialListSkeleton />}

      {error && (
        <>
          {error instanceof ApiError && error.isUnauthorized && handleUnauthorized()}
          {!(error instanceof ApiError && error.isUnauthorized) && (
            <ErrorState
              message="Не удалось загрузить календарь. Проверьте соединение и попробуйте ещё раз."
              onRetry={reload}
            />
          )}
        </>
      )}

      {data && (
        <>
          <div className="calendar-grid" role="grid" aria-label={`Календарь на ${MONTH_NAMES[cursor.month - 1]} ${cursor.year}`}>
            {WEEKDAYS.map((weekday) => (
              <div className="calendar-weekday" role="columnheader" key={weekday}>
                {weekday}
              </div>
            ))}
            {grid.map((cell, index) =>
              cell === null ? (
                <div className="calendar-cell calendar-cell-empty" key={`pad-${index}`} />
              ) : (
                <div
                  className={`calendar-cell${cell.iso === todayIso ? " calendar-cell-today" : ""}`}
                  key={cell.iso}
                  role="gridcell"
                  aria-label={`${cell.day} ${MONTH_GENITIVE[cursor.month - 1]} ${cursor.year}`}
                >
                  <span className="calendar-day">{cell.day}</span>
                  <div className="calendar-events">
                    {(eventsByDay.get(cell.iso) ?? []).map((event) => (
                      <button
                        type="button"
                        key={`${event.type}-${event.id}`}
                        className={`calendar-event calendar-event-${event.type}`}
                        title={`${TYPE_LABEL[event.type]}: ${event.title}${event.time !== null ? `, ${event.time}` : ""}`}
                        onClick={() =>
                          navigate(`${TYPE_ROUTE[event.type]}/${event.id}`)
                        }
                      >
                        {event.title}
                      </button>
                    ))}
                  </div>
                </div>
              ),
            )}
          </div>

          {hasEvents && (
            <div className="calendar-legend" aria-hidden="true">
              <span className="calendar-event-lesson_plan">Уроки</span>
              <span className="calendar-event-assignment">Сроки заданий</span>
              <span className="calendar-event-assessment">Проверочные</span>
            </div>
          )}

          {!hasEvents && (
            <EmptyState
              icon="calendar"
              title="В этом месяце ничего не запланировано"
              description="Добавьте дату в план урока, срок в задание или время в проверочную — они появятся здесь."
            />
          )}
        </>
      )}
    </>
  );
}
