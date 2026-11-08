interface EventInfo {
  name: string;
  critical?: boolean;
}

/** Exactly the AuditEventType vocabulary of the backend (core/enums.py). */
const EVENTS: readonly EventInfo[] = [
  { name: "LOGIN" },
  { name: "LOGOUT" },
  { name: "DEVICE_REGISTER" },
  { name: "DEVICE_REVOKE", critical: true },
  { name: "TERMINAL_REGISTER" },
  { name: "LESSON_START" },
  { name: "LESSON_END" },
  { name: "RESOURCE_OPEN" },
  { name: "CAPABILITY_ISSUED" },
  { name: "CAPABILITY_REJECTED", critical: true },
  { name: "CAPABILITY_REVOKED", critical: true },
  { name: "STEP_UP_REQUEST" },
  { name: "STEP_UP_APPROVED" },
  { name: "STEP_UP_DENIED", critical: true },
  { name: "PRESENCE_ACTIVE" },
  { name: "PRESENCE_DEGRADED" },
  { name: "PRESENCE_LOST", critical: true },
  { name: "SESSION_LOCK", critical: true },
  { name: "PANIC", critical: true },
  { name: "POLICY_DENY", critical: true },
];

export default function AuditSection() {
  return (
    <section className="section">
      <div className="section-head">
        <h2>Журнал</h2>
        <span className="stage-badge">Запись событий — Этап 2</span>
      </div>
      <p className="section-desc">
        Append-only журнал безопасности: каждое решение ALLOW/DENY и каждое
        значимое действие записывается с машиночитаемым reason-кодом и
        структурированным контекстом (без секретов). Записи не изменяются и не
        удаляются прикладным кодом; ссылки на сущности — с ON DELETE SET NULL,
        чтобы история переживала удаление объектов. Красным выделены события,
        требующие внимания.
      </p>
      <ul className="chips">
        {EVENTS.map((event) => (
          <li
            key={event.name}
            className={event.critical ? "chip chip-critical" : "chip"}
          >
            {event.name}
          </li>
        ))}
      </ul>
    </section>
  );
}
