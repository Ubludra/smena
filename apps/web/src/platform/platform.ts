/**
 * Platform abstraction — the single seam between «Смена» and its host.
 *
 * Business logic and UI never talk to MAX (or any other host) directly;
 * they use this interface. Two implementations exist:
 *
 *   platform/max.ts      — MAX mini app (official WebApp bridge,
 *                          https://dev.max.ru/docs/webapps/bridge)
 *   platform/browser.ts  — plain browser (standard web APIs)
 *
 * CROSS-PLATFORM INVARIANT (project rule §10): no core feature may require
 * a specific OS or the MAX bridge; MAX capabilities are progressive
 * enhancement and every optional call must tolerate failure.
 *
 * Only methods the app actually uses live here — no speculative surface.
 */

export type LaunchContext =
  /** Running inside MAX: signed launch payload for backend verification. */
  | { kind: "max"; initData: string }
  /** Plain browser, development build: dev-login is available. */
  | { kind: "browser-dev" }
  /** Plain browser, production build: MAX identity is required. */
  | { kind: "browser-locked" };

export type ShareResult = "shared" | "copied";

export interface PlatformAdapter {
  readonly environment: "max" | "browser";

  /** How this session was started (drives the authentication flow). */
  getLaunchContext(): Promise<LaunchContext>;

  /** Open an external URL. In MAX this uses the documented openLink call,
   *  which must happen within a user click — we only call it from handlers. */
  openExternalLink(url: string): Promise<void>;

  /** Share material text. In MAX uses the native share sheet (shareContent);
   *  in browsers falls back to navigator.share, then the clipboard. */
  shareText(text: string): Promise<ShareResult>;
}
