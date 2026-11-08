/**
 * Minimal typings for the official MAX bridge object (`window.WebApp`),
 * loaded from https://st.max.ru/js/max-web-app.js.
 *
 * Only the members we actually call are declared — every entry here is
 * copied from the official API reference (dev.max.ru/docs/webapps/bridge,
 * accessed 2026-10-22). Undocumented members from the shipped bundle are
 * deliberately NOT declared so they can't be used by accident.
 */

export interface MaxBridge {
  /** URL-encoded launch payload intended for server-side validation. */
  readonly initData: string;
  readonly platform: "ios" | "android" | "desktop" | "web";
  readonly version: string;
  openLink(url: string): void;
  shareContent(params: { text?: string; link?: string }): void;
}

declare global {
  interface Window {
    /** Present whenever the official script loaded — inside MAX *and* in
     *  plain browsers (the bundle defines it unconditionally). Never use
     *  its mere presence to detect the MAX client; use the launch data
     *  fragment instead (see platform/max.ts). */
    WebApp?: MaxBridge;
  }
}

export {};
