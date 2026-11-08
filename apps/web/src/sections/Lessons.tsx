import type { Tone } from "../ui";

interface SessionStateInfo {
  name: string;
  tone: Tone;
  desc: string;
}

const STATES: readonly SessionStateInfo[] = [
  {
    name: "ACTIVE",
    tone: "ok",
    desc: "Свежие доказательства присутствия (менее 15 с назад). Разрешённый доступ работает полностью.",
  },
  {
    name: "DEGRADED",
    tone: "warn",
    desc: "Доказательства устарели (менее 90 с). Уже открытые материалы остаются, новый чувствительный доступ запрещён.",
  },
  {
    name: "LOCKED",
    tone: "err",
    desc: "Присутствие потеряно или нажата PANIC. Все capability урока отозваны сервером, любое действие — DENY.",
  },
  {
    name: "ENDED",
    tone: "muted",
    desc: "Урок штатно завершён. Терминал не хранит ничего: ни прав, ни контента.",
  },
];

export default function Lessons() {
  return (
    <section className="section">
      <div className="section-head">
        <h2>Уроки</h2>
        <span className="stage-badge">API раздела — Этап 2</span>
      </div>
      <p className="section-desc">
        Урок — контекст доступа: пара «преподаватель × терминал». Состояние
        урока выводится сервером из свежести криптографических доказательств
        присутствия с доверенного устройства (телефона). Активность мыши,
        клавиатуры или открытая вкладка доказательством присутствия не
        являются.
      </p>
      <div className="state-list">
        {STATES.map((state) => (
          <div className="state" key={state.name}>
            <span className={`state-name tone-${state.tone}`}>{state.name}</span>
            <span className="state-desc">{state.desc}</span>
          </div>
        ))}
      </div>
    </section>
  );
}
