import { useCallback, useEffect, useState, type FormEvent } from "react";
import { useDebounced } from "../../shared/hooks/useDebounced";
import { api, ApiError } from "../../shared/api/client";
import { useApiToken, useAuth } from "../../shared/hooks/auth";
import { useAsync } from "../../shared/hooks/useAsync";
import { Button } from "../../shared/ui/Button";
import { relativeDate } from "../../shared/lib/dates";
import { navigate } from "../../shared/lib/routes";
import { clearSafeToken, getSafeToken, setSafeToken } from "../../shared/lib/safeToken";
import { MaterialsList } from "../materials/MaterialsList";

/**
 * «Сейф» — защищённые материалы и проверочные за вторым фактором.
 *
 * Честная модель (documented in api/routes/safe.py): the factor is a
 * dedicated SAFE PASSWORD — it is set on first unlock and only its scrypt
 * hash is stored. The unlock is a short-lived token; «Заблокировать» forgets
 * it here and then — «закрыть вкладку» — the same.
 */
export function SafePage() {
  const token = useApiToken();
  const [search, setSearch] = useState("");
  const debouncedSearch = useDebounced(search);
  const [unlocked, setUnlocked] = useState(() => getSafeToken() !== null);

  const status = useAsync(() => {
    if (token === null) return Promise.reject(new Error("no token"));
    return api.safeStatus(token);
  }, [token, unlocked]);

  // A 403 from any protected listing means the token died (expired) —
  // fall back to the locked screen so the teacher sees why.
  const lockNow = useCallback(() => {
    clearSafeToken();
    setUnlocked(false);
  }, []);

  const retry = status.reload;

  return (
    <>
      <div className="page-header">
        <div>
          <p className="eyebrow">ЗАЩИЩЁННОЕ ХРАНИЛИЩЕ</p>
          <h1>Сейф</h1>
          <p className="page-description">
            Материалы, которые вы отметили для защищённого хранения.
          </p>
        </div>
      </div>

      {unlocked ? (
        <UnlockedHero onLock={lockNow} />
      ) : (
        <LockedHero
          hasPassword={status.data?.has_password ?? false}
          onUnlocked={() => setUnlocked(true)}
          onRetryStatus={retry}
          statusError={status.error}
          statusLoading={status.loading}
        />
      )}

      {unlocked && (
        <>
          <div className="search-row">
            <input
              type="search"
              className="search-input"
              placeholder="Поиск в Сейфе…"
              aria-label="Поиск в Сейфе"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
            />
          </div>

          <MaterialsList
            search={debouncedSearch}
            onlyProtected
            onSafeLocked={lockNow}
            emptyTitle="В Сейфе пусто"
            emptyDescription="Отметьте материал «Добавить в Сейф» — и он появится здесь."
            emptyIcon="lock"
          />

          <ProtectedAssessments onSafeLocked={lockNow} />
        </>
      )}
    </>
  );
}

function SafeHeroIcon({ open }: { open: boolean }) {
  return (
    <span className="safe-hero-icon" aria-hidden="true">
      <svg
        width="27"
        height="27"
        viewBox="0 0 24 24"
        fill="none"
        stroke="currentColor"
        strokeWidth="1.7"
        strokeLinecap="round"
        strokeLinejoin="round"
      >
        <rect x="4.5" y="10" width="15" height="11" rx="2.5" />
        {open ? <path d="M8 10V7a4 4 0 0 1 7.7-1.5" /> : <path d="M8 10V7a4 4 0 0 1 8 0v3" />}
      </svg>
    </span>
  );
}

function UnlockedHero({ onLock }: { onLock: () => void }) {
  return (
    <section className="safe-hero" aria-labelledby="safe-hero-title">
      <SafeHeroIcon open />
      <div>
        <p className="eyebrow">ПРОВЕРКА ПРОЙДЕНА</p>
        <h2 id="safe-hero-title">Сейф разблокирован</h2>
        <p>
          Защищённые материалы открыты, пока активна разблокировка. Она
          короткая: минуты, не дни.
        </p>
      </div>
      <Button variant="secondary" onClick={onLock}>
        Заблокировать
      </Button>
    </section>
  );
}

function LockedHero(props: {
  hasPassword: boolean;
  onUnlocked: () => void;
  onRetryStatus: () => void;
  statusError: unknown;
  statusLoading: boolean;
}) {
  const token = useApiToken();
  const { handleUnauthorized } = useAuth();
  const [password, setPassword] = useState("");
  const [visible, setVisible] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  if (props.statusLoading && !props.statusError) {
    return (
      <section className="safe-hero" aria-busy="true">
        <SafeHeroIcon open={false} />
        <div>
          <p className="eyebrow">ПРОВЕРКА ПРИ ОТКРЫТИИ</p>
          <h2>Сейф заблокирован</h2>
        </div>
        <span className="spinner" aria-hidden="true" />
      </section>
    );
  }

  if (props.statusError) {
    const err = props.statusError;
    if (err instanceof ApiError && err.isUnauthorized) {
      handleUnauthorized();
      return null;
    }
    return (
      <section className="safe-hero">
        <SafeHeroIcon open={false} />
        <div>
          <p className="eyebrow">ПРОВЕРКА ПРИ ОТКРЫТИИ</p>
          <h2>Сейф заблокирован</h2>
          <p>Не удалось получить состояние Сейфа.</p>
        </div>
        <Button variant="secondary" onClick={props.onRetryStatus}>
          Повторить
        </Button>
      </section>
    );
  }

  async function submit(e: FormEvent) {
    e.preventDefault();
    if (token === null || busy) return;
    setBusy(true);
    setError(null);
    try {
      const result = await api.safeUnlock(token, password);
      setSafeToken(result.token, result.expires_in_seconds);
      props.onUnlocked();
    } catch (err) {
      if (err instanceof ApiError && err.isUnauthorized) {
        handleUnauthorized();
        return;
      }
      if (err instanceof ApiError && (err.status === 403 || err.status === 422)) {
        setError(err.serverMessage ?? "Проверка не пройдена.");
      } else {
        setError("Не удалось проверить пароль. Попробуйте ещё раз.");
      }
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="safe-hero" aria-labelledby="safe-hero-title">
      <SafeHeroIcon open={false} />
      <div>
        <p className="eyebrow">ПРОВЕРКА ПРИ ОТКРЫТИИ</p>
        <h2 id="safe-hero-title">Сейф заблокирован</h2>
        <p>
          {props.hasPassword
            ? "Введите пароль Сейфа, чтобы открыть защищённые материалы."
            : "Первый вход: придумайте пароль Сейфа (не менее 4 символов). Он будет храниться только в виде хеша и станет проверкой при каждом открытии Сейфа."}
        </p>
        <p>
          Пароль не отправляется по SMS и не восстанавливается автоматически:
          неверный пароль ничего не ломает — защищённые данные остаются на
          месте.
        </p>
      </div>
      <form className="safe-unlock-form" onSubmit={submit}>
        <div className="field safe-password-field">
          <label htmlFor="safe-password">Пароль Сейфа</label>
          <div className="safe-password-row">
            <input
              id="safe-password"
              type={visible ? "text" : "password"}
              autoComplete={props.hasPassword ? "current-password" : "new-password"}
              minLength={4}
              maxLength={128}
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
            />
            <button
              type="button"
              className="text-action"
              aria-label={visible ? "Скрыть пароль" : "Показать пароль"}
              aria-pressed={visible}
              onClick={() => setVisible((v) => !v)}
            >
              {visible ? "Скрыть" : "Показать"}
            </button>
          </div>
        </div>
        <Button type="submit" busy={busy}>
          {props.hasPassword ? "Разблокировать" : "Создать и открыть"}
        </Button>
        {error !== null && (
          <p className="form-error" role="alert">
            {error}
          </p>
        )}
      </form>
    </section>
  );
}

/** Safe section two: assessments the teacher flagged as protected. */
function ProtectedAssessments({ onSafeLocked }: { onSafeLocked: () => void }) {
  const token = useApiToken();
  const { handleUnauthorized } = useAuth();
  const { data, error, loading } = useAsync(() => {
    if (token === null) return Promise.reject(new Error("no token"));
    return api.listAssessments(token, { onlyProtected: true, limit: 20 });
  }, [token]);

  // Expired safe token: the parent flips back to the locked screen, so the
  // 403 never lingers as a scary error banner.
  const safeLocked = error instanceof ApiError && error.status === 403;
  useEffect(() => {
    if (safeLocked) onSafeLocked();
  }, [safeLocked, onSafeLocked]);

  if (loading || safeLocked) return null;

  if (error) {
    if (error instanceof ApiError && error.isUnauthorized) {
      handleUnauthorized();
    }
    // The materials section already shows a retryable error; this section
    // degrades quietly instead of duplicating an error banner.
    return null;
  }

  if (!data || data.items.length === 0) return null;

  return (
    <section aria-labelledby="safe-assessments-title">
      <div className="section-head">
        <h2 id="safe-assessments-title">Проверочные в Сейфе</h2>
      </div>
      <div className="material-list">
        {data.items.map((assessment) => (
          <button
            type="button"
            className="card material-card plan-card"
            key={assessment.id}
            onClick={() => navigate(`#/assessments/${assessment.id}`)}
          >
            <span className="material-card-title">{assessment.title}</span>
            <span className="material-card-meta">
              {assessment.class_name && <span>{assessment.class_name}</span>}
              {assessment.subject && <span>{assessment.subject}</span>}
              <span>изменено {relativeDate(assessment.updated_at)}</span>
            </span>
          </button>
        ))}
      </div>
    </section>
  );
}
