import type { ApiState } from "../api";

interface OverviewProps {
  api: ApiState;
}

export default function Overview({ api }: OverviewProps) {
  return (
    <section className="section">
      <div className="section-head">
        <h2>Обзор</h2>
        <span className="stage-badge stage-badge-ok">Этап 1 — фундамент готов</span>
      </div>

      <div className="grid">
        <article className="card">
          <h3>Состояние стека</h3>
          <dl className="kv">
            <dt>API</dt>
            <dd>
              {api.kind === "checking" && "проверка…"}
              {api.kind === "ok" && <>работает · БД: {api.database}</>}
              {api.kind === "error" && <>недоступен: {api.message}</>}
            </dd>
            <dt>База данных</dt>
            <dd>PostgreSQL 17 · 8 таблиц (alembic)</dd>
            <dt>Проверки качества</dt>
            <dd>31 тест · ruff · mypy strict · eslint · tsc — зелёные</dd>
          </dl>
        </article>

        <article className="card">
          <h3>Три инварианта безопасности</h3>
          <ol className="invariants">
            <li>Компрометация школьного ПК не даёт прав преподавателя.</li>
            <li>Разрешения минимальны, контекстны, временны и отзывны.</li>
            <li>
              После LOCK/PANIC старые разрешения не работают даже при прямом
              повторе HTTP-запроса.
            </li>
          </ol>
        </article>

        <article className="card">
          <h3>Модель доступа</h3>
          <p>
            Школьный терминал недоверен: доступ к материалам выдаётся только
            через capability — разрешение, привязанное к комбинации «учитель ×
            терминал × урок × ресурс × действие», с коротким сроком жизни и
            серверным отзывом. Каждое предъявление перепроверяется по базе
            данных.
          </p>
        </article>

        <article className="card">
          <h3>Следующий этап (2)</h3>
          <ul>
            <li>Аутентификация преподавателя</li>
            <li>Регистрация устройств (Ed25519) и терминалов</li>
            <li>Policy Engine: выдача и проверка capability</li>
            <li>Presence, LOCK/PANIC, step-up подтверждения</li>
          </ul>
        </article>
      </div>
    </section>
  );
}
