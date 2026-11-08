import { useState } from "react";
import { ApiError } from "../../shared/api/client";
import { useAuth } from "../../shared/hooks/auth";
import { Button } from "../../shared/ui/Button";
import { TextField } from "../../shared/ui/Field";

/**
 * Pre-auth screens. Two honest variants chosen by the platform layer:
 *
 * dev-login — development/browser demo: "who is this workspace for?";
 * locked    — production build in a plain browser: the product lives in MAX,
 *             and we say so instead of inventing a parallel login.
 *
 * Also renders the MAX authentication error state with retry.
 */
export function LoginScreen({ variant }: { variant: "dev-login" | "locked" }) {
  if (variant === "locked") return <LockedScreen />;
  return <DevLogin />;
}

function DevLogin() {
  const { loginDev } = useAuth();
  const [name, setName] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function submit() {
    setBusy(true);
    setError(null);
    try {
      await loginDev(name.trim());
    } catch (err) {
      setError(
        err instanceof ApiError && err.status === 0
          ? "Сервер недоступен. Убедитесь, что backend запущен (make up)."
          : "Не удалось войти. Попробуйте ещё раз.",
      );
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="login-screen">
      <div className="login-card">
        <h1 className="brand-title">Смена</h1>
        <p className="brand-subtitle">Рабочее место преподавателя</p>

        <form
          aria-label="Вход в браузерное демо"
          onSubmit={(e) => {
            e.preventDefault();
            void submit();
          }}
        >
          <TextField
            label="Как вас зовут?"
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="Имя Отчество"
            maxLength={120}
            autoComplete="name"
          />
          {error && (
            <p className="form-error" role="alert">
              {error}
            </p>
          )}
          <Button
            type="submit"
            className="full-width"
            busy={busy}
            disabled={name.trim().length === 0}
          >
            Продолжить
          </Button>
        </form>

        <p className="dev-note">
          Браузерный режим для разработки. В мессенджере MAX вход выполняется
          автоматически при открытии.
        </p>
      </div>
    </div>
  );
}

function LockedScreen() {
  return (
    <div className="login-screen">
      <div className="login-card">
        <h1 className="brand-title">Смена</h1>
        <p className="brand-subtitle">
          Это мини-приложение работает внутри мессенджера MAX — вход
          выполняется автоматически по вашему аккаунту.
        </p>
        <p className="dev-note">
          Если вы открыли ссылку в обычном браузере — откройте её через чат
          бота в MAX.
        </p>
      </div>
    </div>
  );
}

export function MaxAuthErrorScreen({
  code,
  onRetry,
}: {
  code: string | null;
  onRetry: () => void;
}) {
  if (code === "NETWORK") {
    return (
      <div className="login-screen">
        <div className="login-card">
          <h1 className="brand-title">Нет соединения</h1>
          <p className="brand-subtitle">
            Не удалось связаться с сервером Смены.
          </p>
          <Button className="full-width" onClick={onRetry}>
            Повторить
          </Button>
        </div>
      </div>
    );
  }
  return (
    <div className="login-screen">
      <div className="login-card">
        <h1 className="brand-title">Смена пока не готова</h1>
        <p className="brand-subtitle">
          {code === "MAX_NOT_CONFIGURED"
            ? "Сервер ещё не подключён к MAX (нет токена бота). Команда разработки уже настраивает этот шаг."
            : "Не удалось подтвердить ваш аккаунт MAX."}
        </p>
        <Button variant="secondary" className="full-width" onClick={onRetry}>
          Попробовать снова
        </Button>
      </div>
    </div>
  );
}
