/**
 * MAX mini-app adapter.
 *
 * Environment detection uses the documented launch-data mechanism: when MAX
 * opens мини-app it appends `#WebAppData=…` to the URL (the same payload the
 * bridge exposes as `initData`). The bridge script itself defines
 * `window.WebApp` in any browser, so its presence proves nothing — the
 * fragment does.
 */

import type { LaunchContext, PlatformAdapter, ShareResult } from "./platform";
import type { MaxBridge } from "./max-bridge";

export const MAX_LAUNCH_FRAGMENT_PARAM = "WebAppData";

/** Pure for testing: does this URL carry MAX launch data? */
export function hasMaxLaunchData(hash: string): boolean {
  return new URLSearchParams(hash.replace(/^#/, "")).has(MAX_LAUNCH_FRAGMENT_PARAM);
}

function bridge(): MaxBridge {
  const app = window.WebApp;
  if (!app) {
    // Bridge script failed to load inside MAX (offline / blocked CDN).
    throw new Error("MAX Bridge недоступен");
  }
  return app;
}

export class MaxPlatformAdapter implements PlatformAdapter {
  readonly environment = "max" as const;

  async getLaunchContext(): Promise<LaunchContext> {
    const initData = window.WebApp?.initData ?? "";
    if (!initData) {
      // Fragment existed but the bridge exposes no payload: the session is
      // not trustworthy; let the caller fall back to a visible error screen.
      return { kind: "browser-locked" };
    }
    return { kind: "max", initData };
  }

  async openExternalLink(url: string): Promise<void> {
    // Documented: opens in the system browser; requires a user gesture.
    bridge().openLink(url);
  }

  async shareText(text: string): Promise<ShareResult> {
    // Documented: native share sheet on iOS/Android. Explicitly NOT
    // supported by the MAX web client; callers keep the browser fallback
    // path for that runtime (the platform detector still classifies it as
    // MAX — shareContent simply rejects there).
    bridge().shareContent({ text });
    return "shared";
  }
}
