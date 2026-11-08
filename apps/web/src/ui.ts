/** Shared UI vocabulary: navigation and visual tones. */

export type SectionId =
  | "overview"
  | "lessons"
  | "materials"
  | "vault"
  | "terminals"
  | "devices"
  | "audit";

export interface NavItem {
  id: SectionId;
  title: string;
}

export const NAV_ITEMS: readonly NavItem[] = [
  { id: "overview", title: "Обзор" },
  { id: "lessons", title: "Уроки" },
  { id: "materials", title: "Материалы" },
  { id: "vault", title: "Сейф" },
  { id: "terminals", title: "Терминалы" },
  { id: "devices", title: "Устройства" },
  { id: "audit", title: "Журнал" },
];

/** Semantic tone mapped to CSS classes tone-ok / tone-warn / tone-err / tone-muted. */
export type Tone = "ok" | "warn" | "err" | "muted";
