import { NAV_ITEMS, type SectionId } from "../ui";

interface SidebarProps {
  active: SectionId;
  onSelect: (id: SectionId) => void;
}

export default function Sidebar({ active, onSelect }: SidebarProps) {
  return (
    <aside className="sidebar">
      <nav className="nav" aria-label="Разделы платформы">
        {NAV_ITEMS.map((item) => (
          <button
            key={item.id}
            type="button"
            className={
              item.id === active ? "nav-item nav-item-active" : "nav-item"
            }
            onClick={() => onSelect(item.id)}
            aria-current={item.id === active ? "page" : undefined}
          >
            {item.title}
          </button>
        ))}
      </nav>
      <div className="sidebar-bottom">
        <button
          type="button"
          className="panic-btn"
          disabled
          title="Активируется на Этапе 2: сервер переводит урок в LOCKED и атомарно отзывает все разрешения терминалов"
        >
          PANIC
        </button>
        <p className="panic-note">
          Мгновенная блокировка урока и серверный отзыв всех разрешений —
          с доверенного устройства (Этап 2).
        </p>
      </div>
    </aside>
  );
}
