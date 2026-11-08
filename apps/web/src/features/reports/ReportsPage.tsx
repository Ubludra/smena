import { useState, type FormEvent } from "react";
import { api, ApiError, type ApiReportRoom } from "../../shared/api/client";
import { useApiToken, useAuth } from "../../shared/hooks/auth";
import { useAsync } from "../../shared/hooks/useAsync";
import { Button } from "../../shared/ui/Button";
import { EmptyState } from "../../shared/ui/EmptyState";
import { ErrorState } from "../../shared/ui/ErrorState";
import { TextField } from "../../shared/ui/Field";
import { Skeleton } from "../../shared/ui/Skeleton";
import { navigate } from "../../shared/lib/routes";
import { relativeDate } from "../../shared/lib/dates";
import { getChatKey, saveChatKey } from "./chatKeys";

type Period = "7d" | "30d" | "month" | "custom";

const PERIODS: { value: Period; label: string }[] = [
  { value: "7d", label: "7 дней" },
  { value: "30d", label: "30 дней" },
  { value: "month", label: "Месяц" },
  { value: "custom", label: "Свой период" },
];

/**
 * Отчёты — рабочая область: отчётные документы (редактор), защищённый чат
 * для их отправки и сводка активности. Сводка считается сервером по
 * реальным данным; «успеваемости» здесь нет — в модели нет оценок (§12).
 */
export function ReportsPage() {
  return (
    <>
      <div className="page-header page-intro">
        <div>
          <p className="eyebrow">ОТЧЁТЫ</p>
          <h1>Отчёты</h1>
          <p className="page-description">
            Отчётные документы, их отправка в чат со сквозным шифрованием и
            сводка работы за период.
          </p>
        </div>
      </div>

      <ReportDocsSection />
      <ChatRoomsSection />
      <StatisticsSection />
    </>
  );
}

// --- Отчётные документы --------------------------------------------------------

function ReportDocsSection() {
  const token = useApiToken();
  const { handleUnauthorized } = useAuth();
  const { data, error, loading, reload } = useAsync(() => {
    if (token === null) return Promise.reject(new Error("no token"));
    return api.listReportDocs(token, { limit: 50 });
  }, [token]);

  let body: JSX.Element | null = null;
  if (loading && !data) {
    body = <Skeleton lines={3} />;
  } else if (error) {
    if (error instanceof ApiError && error.isUnauthorized) {
      handleUnauthorized();
    } else {
      body = <ErrorState message="Не удалось загрузить отчёты." onRetry={reload} />;
    }
  } else if (data && data.items.length === 0) {
    body = (
      <EmptyState
        icon="folder"
        title="Пока нет отчётных документов"
        description="Создайте отчёт с нуля или начните с готового шаблона в «Шаблонах»."
        action={
          <Button onClick={() => navigate("#/reports/new")}>Создать отчёт</Button>
        }
      />
    );
  } else if (data) {
    body = (
      <div className="material-list">
        {data.items.map((doc) => (
          <button
            type="button"
            className="card material-card plan-card"
            key={doc.id}
            onClick={() => navigate(`#/reports/${doc.id}`)}
          >
            <span className="material-card-title">{doc.title}</span>
            <span className="material-card-meta">
              {doc.subject && <span>{doc.subject}</span>}
              <span>изменён {relativeDate(doc.updated_at)}</span>
            </span>
          </button>
        ))}
      </div>
    );
  }

  return (
    <section aria-labelledby="report-docs-title">
      <div className="section-head">
        <h2 id="report-docs-title">Отчётные документы</h2>
        <button
          type="button"
          className="text-action"
          onClick={() => navigate("#/reports/new")}
        >
          Новый отчёт <span aria-hidden="true">→</span>
        </button>
      </div>
      {body}
    </section>
  );
}

// --- Чаты со сквозным шифрованием ----------------------------------------------

function ChatRoomsSection() {
  const token = useApiToken();
  const { handleUnauthorized } = useAuth();
  const [name, setName] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [inviteLink, setInviteLink] = useState<string | null>(null);
  const { data, error: listError, loading, reload } = useAsync(() => {
    if (token === null) return Promise.reject(new Error("no token"));
    return api.listReportRooms(token);
  }, [token, inviteLink]);

  async function create(e: FormEvent) {
    e.preventDefault();
    if (token === null || busy) return;
    setBusy(true);
    setError(null);
    try {
      const room = await api.createReportRoom(token, name.trim());
      // The invite secret exists only in this response: keep it locally
      // (that is the chat's encryption key — see chatKeys.ts) and show the
      // link exactly once for handing over to the other participant.
      const secret = room.invite_path.split("/").pop() ?? "";
      saveChatKey(room.id, secret);
      setInviteLink(
        `${window.location.origin}${window.location.pathname}${room.invite_path}`,
      );
      setName("");
      reload();
    } catch (err) {
      if (err instanceof ApiError && err.isUnauthorized) handleUnauthorized();
      else if (err instanceof ApiError && err.status === 422) {
        setError(err.serverMessage ?? "Проверьте название чата.");
      } else {
        setError("Не удалось создать чат. Попробуйте ещё раз.");
      }
    } finally {
      setBusy(false);
    }
  }

  async function copyLink() {
    if (inviteLink === null) return;
    try {
      await navigator.clipboard.writeText(inviteLink);
    } catch {
      // Clipboard refused (permissions/webview): the link stays selectable.
    }
  }

  let roomsBody: JSX.Element | null = null;
  if (loading && !data) {
    roomsBody = <Skeleton lines={2} />;
  } else if (listError) {
    if (listError instanceof ApiError && listError.isUnauthorized) {
      handleUnauthorized();
    } else {
      roomsBody = <ErrorState message="Не удалось загрузить чаты." onRetry={reload} />;
    }
  } else if (data && data.length === 0) {
    roomsBody = <p className="field-hint">Пока нет ни одного чата.</p>;
  } else if (data) {
    roomsBody = (
      <div className="material-list">
        {data.map((room: ApiReportRoom) => {
          const secret = getChatKey(room.id);
          return (
            <button
              type="button"
              className="card material-card plan-card"
              key={room.id}
              disabled={secret === null}
              onClick={() =>
                secret !== null && navigate(`#/chat/${room.id}/${secret}`)
              }
            >
              <span className="material-card-title">{room.name}</span>
              <span className="material-card-meta">
                {secret === null
                  ? "нужна ссылка-приглашение — ключ хранится только у участников"
                  : `создан ${relativeDate(room.created_at)}`}
              </span>
            </button>
          );
        })}
      </div>
    );
  }

  return (
    <section aria-labelledby="report-rooms-title">
      <div className="section-head">
        <h2 id="report-rooms-title">Чаты для отправки отчётов</h2>
      </div>
      <p className="page-description">
        Сообщения в этих чатах шифруются на вашем устройстве. Сервер хранит
        только шифр; ключ — в ссылке-приглашении, которую вы передаёте
        собеседнику сами.
      </p>

      <form className="chat-form" onSubmit={create}>
        <TextField
          label="Новый чат"
          placeholder="Например: отчёт завучу"
          value={name}
          onChange={(e) => setName(e.target.value)}
          maxLength={200}
          required
        />
        <Button type="submit" busy={busy}>
          Создать
        </Button>
      </form>
      {error !== null && (
        <p className="form-error" role="alert">
          {error}
        </p>
      )}

      {inviteLink !== null && (
        <div className="invite-link-box" role="status">
          <span>Ссылка-приглашение (покажите её только собеседнику):</span>
          <code>{inviteLink}</code>
          <Button variant="secondary" onClick={copyLink}>
            Скопировать
          </Button>
        </div>
      )}

      {roomsBody}
    </section>
  );
}

// --- Сводка за период -----------------------------------------------------------

function StatisticsSection() {
  const [period, setPeriod] = useState<Period>("30d");
  const [dateFrom, setDateFrom] = useState("");
  const [dateTo, setDateTo] = useState("");

  return (
    <section aria-labelledby="report-stats-title">
      <div className="section-head">
        <h2 id="report-stats-title">Сводка за период</h2>
      </div>

      <div className="filter-row" aria-label="Период отчёта">
        <div className="chip-row" role="group" aria-label="Период">
          {PERIODS.map((item) => (
            <button
              type="button"
              key={item.value}
              className={`chip${period === item.value ? " chip-active" : ""}`}
              aria-pressed={period === item.value}
              onClick={() => setPeriod(item.value)}
            >
              {item.label}
            </button>
          ))}
        </div>
        {period === "custom" && (
          <div className="filter-row">
            <label className="filter-label">
              с
              <input
                className="filter-input"
                aria-label="Дата начала периода"
                type="date"
                value={dateFrom}
                onChange={(e) => setDateFrom(e.target.value)}
              />
            </label>
            <label className="filter-label">
              по
              <input
                className="filter-input"
                aria-label="Дата конца периода"
                type="date"
                value={dateTo}
                onChange={(e) => setDateTo(e.target.value)}
              />
            </label>
          </div>
        )}
      </div>

      <ReportView period={period} dateFrom={dateFrom} dateTo={dateTo} />
    </section>
  );
}

function ReportView(props: {
  period: Period;
  dateFrom: string;
  dateTo: string;
}) {
  const token = useApiToken();
  const { handleUnauthorized } = useAuth();
  const customReady =
    props.period !== "custom" || (props.dateFrom !== "" && props.dateTo !== "");
  const { data, error, loading, reload } = useAsync(() => {
    if (token === null) return Promise.reject(new Error("no token"));
    if (!customReady) return Promise.resolve(null); // wait for both dates
    return api.reportSummary(token, {
      period: props.period,
      dateFrom: props.dateFrom === "" ? undefined : props.dateFrom,
      dateTo: props.dateTo === "" ? undefined : props.dateTo,
    });
  }, [token, props.period, props.dateFrom, props.dateTo, customReady]);

  if (loading && !data) return <Skeleton lines={5} />;

  if (error) {
    if (error instanceof ApiError && error.isUnauthorized) {
      handleUnauthorized();
      return null;
    }
    return (
      <ErrorState
        message={
          error instanceof ApiError && error.status === 422
            ? error.serverMessage ?? "Проверьте выбранный период."
            : "Не удалось загрузить отчёт. Проверьте соединение и попробуйте ещё раз."
        }
        onRetry={reload}
      />
    );
  }

  if (!data) return null;

  const totalCreated =
    data.created.materials +
    data.created.lesson_plans +
    data.created.assignments +
    data.created.assessments;

  return (
    <div className="report-view">
      <section className="report-cards" aria-label="Создано за период">
        <ReportCard label="Материалы" value={data.created.materials} />
        <ReportCard label="Планы уроков" value={data.created.lesson_plans} />
        <ReportCard label="Задания" value={data.created.assignments} />
        <ReportCard label="Проверочные" value={data.created.assessments} />
      </section>

      <section className="plan-section" aria-label="Состояние заданий">
        <h2>Задания сейчас</h2>
        <p>
          Активных: <strong>{data.assignments.active}</strong> · просроченных:{" "}
          <strong>{data.assignments.overdue}</strong> · срок в течение недели:{" "}
          <strong>{data.assignments.due_soon}</strong>
        </p>
      </section>

      <section className="plan-section" aria-label="Сейф">
        <h2>Сейф</h2>
        <p>
          Материалов: <strong>{data.safe.materials}</strong> · проверочных:{" "}
          <strong>{data.safe.assessments}</strong>
        </p>
      </section>

      {totalCreated === 0 && data.upcoming.length === 0 ? (
        <EmptyState
          icon="folder"
          title="За выбранный период пусто"
          description="Создавайте материалы, планы и задания — они появятся здесь."
        />
      ) : (
        <>
          {data.materials_by_subject.length > 0 && (
            <section className="plan-section" aria-label="Материалы по предметам">
              <h2>Материалы по предметам</h2>
              <ul className="report-list">
                {data.materials_by_subject.map((item) => (
                  <li key={item.subject}>
                    {item.subject} — <strong>{item.count}</strong>
                  </li>
                ))}
              </ul>
            </section>
          )}

          {data.upcoming.length > 0 && (
            <section className="plan-section" aria-label="Ближайшие события">
              <h2>Ближайшие события</h2>
              <ul className="report-list">
                {data.upcoming.map((item) => (
                  <li key={`${item.type}-${item.id}`}>
                    <button
                      type="button"
                      className="link-button"
                      onClick={() =>
                        navigate(
                          item.type === "lesson_plan"
                            ? `#/plans/${item.id}`
                            : `#/assignments/${item.id}`,
                        )
                      }
                    >
                      {item.title}
                    </button>{" "}
                    — {formatDate(item.date)}
                    {item.type === "assignment" ? " (срок задания)" : " (план урока)"}
                  </li>
                ))}
              </ul>
            </section>
          )}
        </>
      )}
    </div>
  );
}

function ReportCard({ label, value }: { label: string; value: number }) {
  return (
    <div className="card report-card">
      <span className="report-value">{value}</span>
      <span className="report-label">{label}</span>
    </div>
  );
}

function formatDate(value: string): string {
  return new Date(value).toLocaleString("ru-RU", {
    day: "numeric",
    month: "long",
    hour: "2-digit",
    minute: "2-digit",
  });
}
