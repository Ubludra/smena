/**
 * Plain-browser adapter: the same app outside MAX (development, demos,
 * any browser). Uses only standard web APIs — this is what proves the
 * cross-platform invariant: business logic never changes, only this file.
 */

import type { LaunchContext, PlatformAdapter, ShareResult } from "./platform";

export class BrowserPlatformAdapter implements PlatformAdapter {
  readonly environment = "browser" as const;

  constructor(
    /** Vite injects DEV=true for development builds. A production build
     *  opened in a plain browser has no trustworthy identity source, so it
     *  must not offer the dev login (fail closed, mirrors the backend). */
    private readonly isDevBuild: boolean,
  ) {}

  async getLaunchContext(): Promise<LaunchContext> {
    return this.isDevBuild ? { kind: "browser-dev" } : { kind: "browser-locked" };
  }

  async openExternalLink(url: string): Promise<void> {
    window.open(url, "_blank", "noopener,noreferrer");
  }

  async shareText(text: string): Promise<ShareResult> {
    if (navigator.share) {
      try {
        await navigator.share({ text });
        return "shared";
      } catch (error) {
        // AbortError = user dismissed the sheet: stop, don't copy silently.
        if (error instanceof DOMException && error.name === "AbortError") {
          throw error;
        }
        // Anything else: fall through to clipboard.
      }
    }
    await navigator.clipboard.writeText(text);
    return "copied";
  }
}
