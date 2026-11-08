import { useAuth } from "../shared/hooks/auth";
import { useRoute, navigate, type Route } from "../shared/lib/routes";
import { detectPlatform } from "../platform";
import { LoginScreen, MaxAuthErrorScreen } from "../features/auth/LoginScreen";
import { DashboardPage } from "../features/dashboard/DashboardPage";
import { MaterialsPage } from "../features/materials/MaterialsPage";
import { MaterialDetail } from "../features/materials/MaterialDetail";
import { MaterialCreatePage } from "../features/materials/MaterialCreatePage";
import { MaterialEditPage } from "../features/materials/MaterialEditPage";
import { SafePage } from "../features/safe/SafePage";
import { PlansPage } from "../features/plans/PlansPage";
import { PlanDetail } from "../features/plans/PlanDetail";
import { PlanCreatePage } from "../features/plans/PlanCreatePage";
import { PlanEditPage } from "../features/plans/PlanEditPage";
import { AssignmentsPage } from "../features/assignments/AssignmentsPage";
import { AssignmentDetail } from "../features/assignments/AssignmentDetail";
import { AssignmentForm } from "../features/assignments/AssignmentForm";
import { AssignmentEditPage } from "../features/assignments/AssignmentEditPage";
import { AssessmentsPage } from "../features/assessments/AssessmentsPage";
import { AssessmentDetail } from "../features/assessments/AssessmentDetail";
import { AssessmentForm } from "../features/assessments/AssessmentForm";
import { AssessmentEditPage } from "../features/assessments/AssessmentEditPage";
import { TemplatesPage } from "../features/templates/TemplatesPage";
import { ReportsPage } from "../features/reports/ReportsPage";
import { ReportEditorPage } from "../features/reports/ReportEditorPage";
import { ChatPage } from "../features/reports/ChatPage";
import { FilesPage } from "../features/files/FilesPage";
import { CalendarPage } from "../features/calendar/CalendarPage";

/**
 * Root component: authentication gate + navigation shell.
 *
 * Layout (product rule §16): one component tree; CSS switches presentation
 * between phone (header + bottom nav) and desktop (header + tab strip) —
 * not two apps.
 */
export function App() {
  const { status, retryBoot } = useAuth();

  switch (status.state) {
    case "booting":
      return (
        <div className="splash" role="status" aria-label="Загрузка Смены">
          <span className="spinner spinner-large" aria-hidden="true" />
        </div>
      );
    case "anonymous":
      return <LoginScreen variant={status.launch} />;
    case "max-error":
      return <MaxAuthErrorScreen code={status.code} onRetry={retryBoot} />;
    case "authed":
      return <Shell />;
  }
}

// Desktop tab strip holds every section; the phone bottom nav keeps five
// items and moves the rest behind «Ещё» (product rule §8: never 8 items).
const NAV_ITEMS = [
  { label: "Главная", hash: "#/", icon: "home" },
  { label: "Материалы", hash: "#/materials", icon: "folder" },
  { label: "Планы", hash: "#/plans", icon: "calendar" },
  { label: "Задания", hash: "#/assignments", icon: "check" },
  { label: "Проверочные", hash: "#/assessments", icon: "clipboard" },
  { label: "Сейф", hash: "#/safe", icon: "lock" },
  { label: "Ещё", hash: "#/more", icon: "dots" },
] as const;

const MOBILE_NAV_ITEMS = [
  { label: "Главная", hash: "#/", icon: "home" },
  { label: "Материалы", hash: "#/materials", icon: "folder" },
  { label: "Планы", hash: "#/plans", icon: "calendar" },
  { label: "Задания", hash: "#/assignments", icon: "check" },
  { label: "Ещё", hash: "#/more", icon: "dots" },
] as const;

function Shell() {
  const route = useRoute();
  const { status, logout } = useAuth();
  const displayName = status.state === "authed" ? status.user.display_name : "";
  // Logout is a dev/browser concept: inside MAX the session follows the
  // messenger account, there is nothing to "sign out" of.
  const showLogout = detectPlatform().environment === "browser";

  function openMaterialSearch() {
    navigate("#/materials");
    window.requestAnimationFrame(() => {
      window.requestAnimationFrame(() => {
        document.querySelector<HTMLInputElement>('[aria-label="Поиск материалов"]')?.focus();
      });
    });
  }

  return (
    <div className="app-shell">
      <a className="skip-link" href="#main">
        Перейти к содержимому
      </a>
      <header className="app-header">
        <div className="header-top">
          <div className="header-brand">
            <span className="app-brand">Смена</span>
            <span className="header-brand-caption">Рабочее место педагога</span>
          </div>
          <div className="header-tools">
            <button
              type="button"
              className="header-search"
              aria-label="Поиск по материалам"
              onClick={openMaterialSearch}
            >
              <SearchIcon />
              <span>Поиск по материалам</span>
            </button>
            <button
              type="button"
              className="header-create"
              onClick={() => navigate("#/materials/new")}
            >
              <span aria-hidden="true">＋</span>
              Создать
            </button>
          </div>
          <span className="app-user" title={displayName}>
            {displayName}
          </span>
          {showLogout && (
            <button type="button" className="link-button header-logout" onClick={logout}>
              Выйти
            </button>
          )}
        </div>
        <nav className="app-tabs" aria-label="Разделы">
          {NAV_ITEMS.map((item) => (
            <NavLink key={item.hash} {...item} route={route} tab />
          ))}
        </nav>
      </header>

      <main
        className="content"
        id="main"
        tabIndex={-1}
        aria-label="Основное содержимое"
      >
        <Screen route={route} />
      </main>

      <nav className="bottom-nav" aria-label="Разделы">
        {MOBILE_NAV_ITEMS.map((item) => (
          <NavLink key={item.hash} {...item} route={route} />
        ))}
      </nav>
    </div>
  );
}

function Screen({ route }: { route: Route }) {
  switch (route.name) {
    case "dashboard":
      return <DashboardPage />;
    case "materials":
      return <MaterialsPage />;
    case "safe":
      return <SafePage />;
    case "material-new":
      return <MaterialCreatePage templateId={route.templateId} />;
    case "material-detail":
      return <MaterialDetail id={route.id} />;
    case "material-edit":
      return <MaterialEditPage id={route.id} />;
    case "plans":
      return <PlansPage />;
    case "plan-detail":
      return <PlanDetail id={route.id} />;
    case "plan-edit":
      return <PlanEditPage id={route.id} />;
    case "plan-new":
      return (
        <PlanCreatePage templateId={route.templateId} />
      );
    case "assignments":
      return <AssignmentsPage />;
    case "assignment-detail":
      return <AssignmentDetail id={route.id} />;
    case "assignment-edit":
      return <AssignmentEditPage id={route.id} />;
    case "assignment-new":
      return (
        <>
          <div className="page-header">
            <div>
              <p className="eyebrow">ЗАДАНИЕ</p>
              <h1>Новое задание</h1>
            </div>
          </div>
          <AssignmentForm
            onSaved={() => undefined}
            onCancel={() => navigate("#/assignments")}
          />
        </>
      );
    case "assessments":
      return <AssessmentsPage />;
    case "assessment-detail":
      return <AssessmentDetail id={route.id} />;
    case "assessment-edit":
      return <AssessmentEditPage id={route.id} />;
    case "assessment-new":
      return (
        <>
          <div className="page-header">
            <div>
              <p className="eyebrow">ПРОВЕРОЧНАЯ</p>
              <h1>Новая проверочная</h1>
            </div>
          </div>
          <AssessmentForm
            onSaved={() => undefined}
            onCancel={() => navigate("#/assessments")}
          />
        </>
      );
    case "more":
      return <MorePage />;
    case "templates":
      return <TemplatesPage />;
    case "reports":
      return <ReportsPage />;
    case "report-new":
      return <ReportEditorPage templateId={route.templateId} />;
    case "report-edit":
      return <ReportEditorPage id={route.id} />;
    case "chat":
      return <ChatPage roomId={route.roomId} inviteToken={route.inviteToken} />;
    case "files":
      return <FilesPage />;
    case "calendar":
      return <CalendarPage />;
  }
}

/** Phone-only «Ещё» screen: the sections that did not fit the bottom nav. */
function MorePage() {
  const sections = [
    {
      label: "Проверочные",
      description: "Контрольные и самостоятельные работы",
      hash: "#/assessments",
    },
    {
      label: "Шаблоны",
      description: "Заготовки для планов, заданий и проверочных",
      hash: "#/templates",
    },
    {
      label: "Отчёты",
      description: "Отчётные документы и защищённый чат для их отправки",
      hash: "#/reports",
    },
    {
      label: "Календарь",
      description: "Уроки, сроки и проверочные по дням",
      hash: "#/calendar",
    },
    {
      label: "Файлы",
      description: "Загруженные документы и материалы",
      hash: "#/files",
    },
    {
      label: "Сейф",
      description: "Защищённые материалы и проверочные",
      hash: "#/safe",
    },
  ];
  return (
    <>
      <div className="page-header page-intro">
        <div>
          <p className="eyebrow">ЕЩЁ</p>
          <h1>Все разделы</h1>
        </div>
      </div>
      <div className="material-list">
        {sections.map((section) => (
          <button
            type="button"
            className="card material-card plan-card"
            key={section.hash}
            onClick={() => navigate(section.hash)}
          >
            <span className="material-card-title">{section.label}</span>
            <span className="material-card-meta">{section.description}</span>
          </button>
        ))}
      </div>
    </>
  );
}

function NavLink({
  label,
  hash,
  icon,
  route,
  tab = false,
}: {
  label: string;
  hash: string;
  icon: "home" | "folder" | "calendar" | "check" | "clipboard" | "dots" | "lock";
  route: Route;
  /** Tab strip presentation (desktop header) vs bottom-nav item (phone). */
  tab?: boolean;
}) {
  const current = isNavCurrent(hash, route);
  const className = tab
    ? `tab-item${current ? " tab-item-active" : ""}`
    : `nav-item${current ? " nav-item-active" : ""}`;
  return (
    <button
      type="button"
      className={className}
      aria-current={current ? "page" : undefined}
      onClick={() => navigate(hash)}
    >
      <NavIcon icon={icon} />
      <span>{label}</span>
    </button>
  );
}

function isNavCurrent(hash: string, route: Route): boolean {
  return (
    (hash === "#/" && route.name === "dashboard") ||
    (hash === "#/materials" && route.name.startsWith("material")) ||
    (hash === "#/plans" && route.name.startsWith("plan")) ||
    (hash === "#/assignments" && route.name.startsWith("assignment")) ||
    (hash === "#/assessments" && route.name.startsWith("assessment")) ||
    (hash === "#/safe" && route.name === "safe") ||
    // «Ещё» is active while the teacher is inside the sections it contains.
    (hash === "#/more" &&
      (route.name === "more" ||
        route.name === "templates" ||
        route.name === "reports" ||
        route.name === "report-new" ||
        route.name === "report-edit" ||
        route.name === "chat" ||
        route.name === "files" ||
        route.name === "calendar" ||
        route.name === "safe"))
  );
}

function NavIcon({
  icon,
}: {
  icon: "home" | "folder" | "calendar" | "check" | "clipboard" | "dots" | "lock";
}) {
  const common = {
    width: 22,
    height: 22,
    viewBox: "0 0 24 24",
    fill: "none",
    stroke: "currentColor",
    strokeWidth: 1.8,
    strokeLinecap: "round" as const,
    strokeLinejoin: "round" as const,
    "aria-hidden": true,
  };
  if (icon === "home") {
    return (
      <svg {...common}>
        <path d="M4 10.5 12 4l8 6.5V20a1 1 0 0 1-1 1h-4v-6h-6v6H5a1 1 0 0 1-1-1v-9.5Z" />
      </svg>
    );
  }
  if (icon === "folder") {
    return (
      <svg {...common}>
        <path d="M3 7a2 2 0 0 1 2-2h4l2 2h8a2 2 0 0 1 2 2v9a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V7Z" />
      </svg>
    );
  }
  if (icon === "check") {
    return (
      <svg {...common}>
        <circle cx="12" cy="12" r="8.5" />
        <path d="m8.5 12.2 2.4 2.4 4.6-5" />
      </svg>
    );
  }
  if (icon === "clipboard") {
    return (
      <svg {...common}>
        <rect x="5" y="4" width="14" height="17" rx="2" />
        <path d="M9 4.5V3h6v1.5M9 10h6m-6 4h6m-6 4h3.5" />
      </svg>
    );
  }
  if (icon === "dots") {
    return (
      <svg {...common}>
        <circle cx="5" cy="12" r="1.6" fill="currentColor" stroke="none" />
        <circle cx="12" cy="12" r="1.6" fill="currentColor" stroke="none" />
        <circle cx="19" cy="12" r="1.6" fill="currentColor" stroke="none" />
      </svg>
    );
  }
  if (icon === "calendar") {
    return (
      <svg {...common}>
        <rect x="3.5" y="5" width="17" height="16" rx="2" />
        <path d="M3.5 10h17M8 2.5V6m8-3.5V6" />
      </svg>
    );
  }
  return (
    <svg {...common}>
      <rect x="4" y="10" width="16" height="10" rx="2" />
      <path d="M8 10V7a4 4 0 0 1 8 0v3" />
    </svg>
  );
}

function SearchIcon() {
  return (
    <svg
      width="18"
      height="18"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.8"
      strokeLinecap="round"
      aria-hidden="true"
    >
      <circle cx="10.8" cy="10.8" r="6.8" />
      <path d="m16 16 4.5 4.5" />
    </svg>
  );
}
