/**
 * Platform detection and singleton.
 *
 * Detection rule documentary basis: MAX passes launch data in the URL
 * fragment (#WebAppData=…); no userAgent sniffing exists in the official
 * docs, so we do not invent one.
 */

import type { PlatformAdapter } from "./platform";
import { BrowserPlatformAdapter } from "./browser";
import { MaxPlatformAdapter, hasMaxLaunchData } from "./max";

let singleton: PlatformAdapter | null = null;

export function detectPlatform(): PlatformAdapter {
  if (singleton) return singleton;
  const inMax = hasMaxLaunchData(window.location.hash);
  singleton = inMax
    ? new MaxPlatformAdapter()
    : new BrowserPlatformAdapter(
        import.meta.env.DEV || import.meta.env.VITE_ENABLE_BROWSER_DEMO === "true",
      );
  return singleton;
}

/** Test seam: reset the singleton between tests. */
export function __resetPlatformForTests(): void {
  singleton = null;
}
