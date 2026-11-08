import type { Tone } from "../ui";

interface ClassificationInfo {
  name: string;
  tone: Tone;
  ttl: string;
  desc: string;
}

const CLASSES: readonly ClassificationInfo[] = [
  {
    name: "NORMAL",
    tone: "ok",
    ttl: "TTL: минуты",
    desc: "Планы уроков, презентации, раздаточные материалы. Открываются в активном уроке без дополнительных подтверждений.",
  },
  {
    name: "SENSITIVE",
    tone: "warn",
    ttl: "TTL: минуты + свежий presence",
    desc: "Контрольные работы, выписки из журнала. Требуют валидного контекста урока и свежего присутствия преподавателя.",
  },
  {
    name: "VAULT",
    tone: "err",
    ttl: "TTL: 60 с + step-up",
    desc: "Ответы к контрольным, экзаменационные ключи. Только свежее присутствие и явное подтверждение на телефоне; каждое открытие аудируется.",
  },
];

export default function Materials() {
  return (
    <section className="section">
      <div className="section-head">
        <h2>Материалы</h2>
        <span className="stage-badge">API раздела — Этап 2</span>
      </div>
      <p className="section-desc">
        Каждый материал имеет классификацию чувствительности — она определяет
        строгость политики доступа, срок жизни разрешения (TTL) и необходимость
        step-up подтверждения. Классификация хранится в базе данных и
        защищена CHECK-ограничением.
      </p>
      <div className="state-list">
        {CLASSES.map((item) => (
          <div className="state" key={item.name}>
            <div className="state-head">
              <span className={`state-name tone-${item.tone}`}>{item.name}</span>
              <span className="state-ttl">{item.ttl}</span>
            </div>
            <span className="state-desc">{item.desc}</span>
          </div>
        ))}
      </div>
    </section>
  );
}
