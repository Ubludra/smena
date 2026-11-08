import type { ApiState } from "../api";

interface HeaderProps {
  api: ApiState;
  onRefresh: () => void;
}

const LABELS: Record<ApiState["kind"], string> = {
  checking: "Проверка API…",
  ok: "API доступен",
  error: "API недоступен",
};

export default function Header({ api, onRefresh }: HeaderProps) {
  return (
    <header className="header">
      <div className="brand">
        <span className="brand-mark" aria-hidden="true">
          △
        </span>
        <div>
          <div className="brand-title">Смена</div>
          <div className="brand-subtitle">
            Защищённая образовательная платформа
          </div>
        </div>
      </div>
      <div className="header-right">
        <button type="button" className="btn-ghost" onClick={onRefresh}>
          Обновить статус
        </button>
        <span className={`pill pill-${api.kind}`} role="status">
          {LABELS[api.kind]}
          {api.kind === "ok" && ` · БД: ${api.database}`}
        </span>
      </div>
    </header>
  );
}
