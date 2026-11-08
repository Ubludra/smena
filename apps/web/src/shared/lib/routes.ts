/**
 * Tiny hash router.
 *
 * Why hash-based instead of react-router: MAX mini-apps and messenger
 * webviews handle in-page hash navigation more reliably than History API
 * pushes, it survives the webview's own URL rewriting, and the whole
 * "router" stays ~40 dependency-free lines. If routes ever grow complex,
 * swapping in a real router touches only this module and <App/>.
 */

import { useEffect, useState } from "react";

export type Route =
  | { name: "dashboard" }
  | { name: "materials" }
  | { name: "safe" }
  | { name: "material-new"; templateId?: string }
  | { name: "material-detail"; id: string }
  | { name: "material-edit"; id: string }
  | { name: "plans" }
  | { name: "plan-new"; templateId?: string }
  | { name: "plan-detail"; id: string }
  | { name: "plan-edit"; id: string }
  | { name: "assignments" }
  | { name: "assignment-new" }
  | { name: "assignment-detail"; id: string }
  | { name: "assignment-edit"; id: string }
  | { name: "assessments" }
  | { name: "assessment-new" }
  | { name: "assessment-detail"; id: string }
  | { name: "assessment-edit"; id: string }
  | { name: "templates" }
  | { name: "reports" }
  | { name: "report-new"; templateId?: string }
  | { name: "report-edit"; id: string }
  | { name: "chat"; roomId: string; inviteToken: string }
  | { name: "files" }
  | { name: "calendar" }
  | { name: "more" };

export function parseHash(hash: string): Route {
  const path = hash.replace(/^#/, "") || "/";
  const parts = path.split("/").filter(Boolean);
  if (parts.length === 0) return { name: "dashboard" };
  if (parts[0] === "materials") {
    if (parts.length === 1) return { name: "materials" };
    if (parts[1] === "new") return { name: "material-new" };
    // Create from a template: #/materials/from/<templateId>.
    if (parts[1] === "from" && parts.length === 3) {
      return { name: "material-new", templateId: parts[2] };
    }
    if (parts.length === 2) return { name: "material-detail", id: parts[1] };
    if (parts[2] === "edit") return { name: "material-edit", id: parts[1] };
  }
  if (parts[0] === "plans") {
    if (parts.length === 1) return { name: "plans" };
    if (parts[1] === "new") return { name: "plan-new" };
    // Create from a template: #/plans/from/<templateId>.
    if (parts[1] === "from" && parts.length === 3) {
      return { name: "plan-new", templateId: parts[2] };
    }
    if (parts.length === 2) return { name: "plan-detail", id: parts[1] };
    if (parts[2] === "edit") return { name: "plan-edit", id: parts[1] };
  }
  if (parts[0] === "assignments") {
    if (parts.length === 1) return { name: "assignments" };
    if (parts[1] === "new") return { name: "assignment-new" };
    if (parts.length === 2) return { name: "assignment-detail", id: parts[1] };
    if (parts[2] === "edit") return { name: "assignment-edit", id: parts[1] };
  }
  if (parts[0] === "assessments") {
    if (parts.length === 1) return { name: "assessments" };
    if (parts[1] === "new") return { name: "assessment-new" };
    if (parts.length === 2) return { name: "assessment-detail", id: parts[1] };
    if (parts[2] === "edit") return { name: "assessment-edit", id: parts[1] };
  }
  if (parts[0] === "templates") return { name: "templates" };
  if (parts[0] === "reports") {
    if (parts.length === 1) return { name: "reports" };
    if (parts[1] === "new") return { name: "report-new" };
    // Create from a template: #/reports/from/<templateId>.
    if (parts[1] === "from" && parts.length === 3) {
      return { name: "report-new", templateId: parts[2] };
    }
    if (parts.length === 2) return { name: "report-edit", id: parts[1] };
  }
  // Chat link: #/chat/<room-id>/<invite-secret>. The secret lives in the
  // hash fragment, which browsers never send to the server — that is what
  // makes it usable as end-to-end key material (shared/lib/e2ee.ts).
  if (parts[0] === "chat" && parts.length >= 3) {
    return { name: "chat", roomId: parts[1], inviteToken: parts[2] };
  }
  if (parts[0] === "files") return { name: "files" };
  if (parts[0] === "calendar") return { name: "calendar" };
  if (parts[0] === "more") return { name: "more" };
  if (parts[0] === "safe") return { name: "safe" };
  // Unknown addresses land on the dashboard instead of a dead end —
  // a teacher must never see a broken page.
  return { name: "dashboard" };
}

export function navigate(hash: string): void {
  if (window.location.hash === hash) {
    // Same hash: hashchange won't fire; re-sync manually.
    window.dispatchEvent(new HashChangeEvent("hashchange"));
  } else {
    window.location.hash = hash;
  }
}

export function useRoute(): Route {
  const [route, setRoute] = useState<Route>(() => parseHash(window.location.hash));
  useEffect(() => {
    const onChange = () => setRoute(parseHash(window.location.hash));
    window.addEventListener("hashchange", onChange);
    return () => window.removeEventListener("hashchange", onChange);
  }, []);
  return route;
}
