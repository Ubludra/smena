import { api, ApiError } from "../../shared/api/client";
import { greetingFor } from "../../shared/lib/dates";
import { navigate } from "../../shared/lib/routes";
import { useApiToken, useAuth } from "../../shared/hooks/auth";
import { useAsync } from "../../shared/hooks/useAsync";
import { ErrorState } from "../../shared/ui/ErrorState";
import { MaterialCard } from "../materials/MaterialCard";
import { Skeleton } from "../../shared/ui/Skeleton";

/**
 * Dashboard answers «что делать сейчас» (product rule §13): greeting,
 * the nearest commitments from the real DB (plans dated ahead + active
 * assignment deadlines via /reports/summary), attention on overdue work,
 * one primary action, recent items. Nothing here is invented — when the
 * week is empty the dashboard says so instead of showing filler.
 */
export function DashboardPage() {
  const { status } = useAuth();
  const token = useApiToken();
  const displayName = status.state === "authed" ? status.user.display_name : "";

  const { data, error, loading, reload } = useAsync(async () => {
    const [all, safe, report] = await Promise.all([
      api.listMaterials(token, { limit: 4 }),
      // A locked Safe legitimately answers 403 (api/routes/safe.py): that is
      // a normal dashboard state, not a failure — same tolerance rule as
      // MaterialsList. Any other error still breaks the whole load.
      api
        .listMaterials(token, { onlyProtected: true, limit: 1 })
        .then((res) => ({ locked: false, total: res.total }))
        .catch((err: unknown) => {
          if (err instanceof ApiError && err.status === 403) {
            return { locked: true, total: 0 };
          }
          throw err;
        }),
      api.reportSummary(token, { period: "7d" }),
    ]);
    return {
      recent: all.items,
      total: all.total,
      safeTotal: safe.total,
      safeLocked: safe.locked,
      report,
    };
  }, [token]);

  if (loading && !data) return <Skeleton lines={5} />;

  if (error) {
    return (
      <ErrorState
        message="Не удалось загрузить главную."
        onRetry={reload}
      />
    );
  }

  if (!data) return null;

  const noMaterials = data.total === 0;
  const { overdue, dueSoon } = {
    overdue: data.report.assignments.overdue,
    dueSoon: data.report.assignments.due_soon,
  };
  const nothingAhead =
    data.report.upcoming.length === 0 && overdue === 0 && dueSoon === 0;

  return (
    <div className="dashboard-page">
      <header className="dashboard-heading">
        <div>
          <p className="eyebrow">РАБОЧЕЕ МЕСТО ПЕДАГОГА</p>
          <h1 className="greeting">{greetingFor(displayName)}</h1>
        </div>
        <div className="dashboard-avatar" aria-hidden="true">
          {displayName.trim().charAt(0).toLocaleUpperCase("ru-RU") || "С"}
        </div>
      </header>

      <section className="now-section" aria-label="Текущие дела">
        {overdue > 0 && (
          <button
            type="button"
            className="attention-card"
            onClick={() => navigate("#/assignments")}
          >
            <strong>
              {overdue} просроченн{overdue === 1 ? "ое задание" : "ых задания"}
            </strong>
            <span>Стоит разобраться сегодня</span>
          </button>
        )}

        {!nothingAhead && (
          <div className="now-list">
            {data.report.upcoming.slice(0, 3).map((item) => (
              <button
                type="button"
                className="card now-item"
                key={`${item.type}-${item.id}`}
                onClick={() =>
                  navigate(
                    item.type === "lesson_plan"
                      ? `#/plans/${item.id}`
                      : `#/assignments/${item.id}`,
                  )
                }
              >
                <span
                  className={`now-dot now-dot-${item.type}`}
                  aria-hidden="true"
                />
                <span className="now-item-copy">
                  <strong>{item.title}</strong>
                  <span>
                    {item.type === "lesson_plan" ? "Урок" : "Срок задания"} ·{" "}
                    {upcomingDate(item.date)}
                  </span>
                </span>
                <span className="stat-arrow" aria-hidden="true">→</span>
              </button>
            ))}
          </div>
        )}

        {dueSoon > 0 && overdue === 0 && (
          <p className="dashboard-quiet-note">
            Ещё {dueSoon} задани{dueSoon === 1 ? "е" : "я"} со сроком на этой
            неделе.
          </p>
        )}

        <div className="quick-actions" aria-label="Быстрые действия">
          <button type="button" onClick={() => navigate("#/plans/new")}>
            Новый план
          </button>
          <button type="button" onClick={() => navigate("#/assignments/new")}>
            Новое задание
          </button>
          <button type="button" onClick={() => navigate("#/files")}>
            Загрузить файл
          </button>
        </div>
      </section>

      <section className="workspace-section" aria-labelledby="workspace-title">
        <div className="section-title-row">
          <div>
            <p className="eyebrow">ВАША БИБЛИОТЕКА</p>
            <h2 id="workspace-title">Материалы</h2>
          </div>
          <button
            type="button"
            className="text-action"
            onClick={() => navigate("#/materials")}
          >
            Все материалы <span aria-hidden="true">→</span>
          </button>
        </div>

        <div className="stat-row">
        <button
          type="button"
          className="stat-card stat-card-materials"
          onClick={() => navigate("#/materials")}
        >
          <span className="stat-icon" aria-hidden="true"><FolderIcon /></span>
          <span className="stat-card-copy">
            <strong>{data.total}</strong>
            <span>материал{plural(data.total)}</span>
          </span>
          <span className="stat-arrow" aria-hidden="true">↗</span>
        </button>
        <button
          type="button"
          className="stat-card stat-card-safe"
          onClick={() => navigate("#/safe")}
        >
          <span className="stat-icon" aria-hidden="true"><LockIcon /></span>
          <span className="stat-card-copy">
            {data.safeLocked ? (
              <>
                <strong>Закрыт</strong>
                <span>нужен пароль — откройте</span>
              </>
            ) : (
              <>
                <strong>{data.safeTotal}</strong>
                <span>в Сейфе</span>
              </>
            )}
          </span>
          <span className="stat-arrow" aria-hidden="true">↗</span>
        </button>
        </div>
      </section>

      <button
        className="new-material-card"
        type="button"
        onClick={() => navigate("#/materials/new")}
      >
        <span className="new-material-icon" aria-hidden="true">＋</span>
        <span className="new-material-copy">
          <strong>Создать материал</strong>
          <span>Добавить материал в личную библиотеку</span>
        </span>
        <span className="new-material-arrow" aria-hidden="true">→</span>
      </button>

      <section className="recent-section" aria-label="Последние материалы">
        <div className="section-title-row">
          <div>
            <p className="eyebrow">БЫСТРЫЙ ДОСТУП</p>
            <h2>Недавно изменённые</h2>
          </div>
          {!noMaterials && (
            <button
              type="button"
              className="text-action"
              onClick={() => navigate("#/materials")}
            >
              Смотреть все <span aria-hidden="true">→</span>
            </button>
          )}
        </div>
        {noMaterials ? (
          <p className="dashboard-empty-hint">
            Начните с первого материала: конспект, карточки или текст
            контрольной. Здесь появятся последние изменения.
          </p>
        ) : (
          <div className="material-list">
            {data.recent.map((material) => (
              <MaterialCard
                key={material.id}
                material={material}
                onOpen={(id) => navigate(`#/materials/${id}`)}
              />
            ))}
          </div>
        )}
      </section>
    </div>
  );
}

function FolderIcon() {
  return (
    <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <path d="M3 7.5A2.5 2.5 0 0 1 5.5 5H10l2 2h6.5A2.5 2.5 0 0 1 21 9.5v8a2.5 2.5 0 0 1-2.5 2.5h-13A2.5 2.5 0 0 1 3 17.5z" />
    </svg>
  );
}

function LockIcon() {
  return (
    <svg width="21" height="21" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <rect x="4.5" y="10" width="15" height="11" rx="2.5" />
      <path d="M8 10V7a4 4 0 0 1 8 0v3" />
    </svg>
  );
}

function plural(n: number): string {
  const mod10 = n % 10;
  const mod100 = n % 100;
  if (mod10 === 1 && mod100 !== 11) return "";
  if (mod10 >= 2 && mod10 <= 4 && (mod100 < 12 || mod100 > 14)) return "а";
  return "ов";
}

/** Human date for the «сейчас» list: сегодня / завтра / 25 октября. */
function upcomingDate(iso: string, now: Date = new Date()): string {
  const date = new Date(`${iso}T00:00:00`);
  const startOfDay = (d: Date) =>
    new Date(d.getFullYear(), d.getMonth(), d.getDate()).getTime();
  const days = Math.round(
    (startOfDay(date) - startOfDay(now)) / 86_400_000,
  );
  if (days === 0) return "сегодня";
  if (days === 1) return "завтра";
  return date.toLocaleDateString("ru-RU", { day: "numeric", month: "long" });
}
