import { describe, expect, it } from "vitest";
import { parseHash } from "./routes";

describe("parseHash", () => {
  it.each([
    ["", { name: "dashboard" }],
    ["#/", { name: "dashboard" }],
    ["#/materials", { name: "materials" }],
    ["#/materials/new", { name: "material-new" }],
    ["#/materials/from/t-1", { name: "material-new", templateId: "t-1" }],
    ["#/materials/abc-123", { name: "material-detail", id: "abc-123" }],
    ["#/materials/abc-123/edit", { name: "material-edit", id: "abc-123" }],
    ["#/plans", { name: "plans" }],
    ["#/plans/new", { name: "plan-new" }],
    ["#/plans/from/t-1", { name: "plan-new", templateId: "t-1" }],
    ["#/plans/abc-123", { name: "plan-detail", id: "abc-123" }],
    ["#/plans/abc-123/edit", { name: "plan-edit", id: "abc-123" }],
    ["#/assignments", { name: "assignments" }],
    ["#/assignments/new", { name: "assignment-new" }],
    ["#/assignments/abc-123", { name: "assignment-detail", id: "abc-123" }],
    ["#/assignments/abc-123/edit", { name: "assignment-edit", id: "abc-123" }],
    ["#/assessments", { name: "assessments" }],
    ["#/assessments/new", { name: "assessment-new" }],
    ["#/assessments/abc-123", { name: "assessment-detail", id: "abc-123" }],
    ["#/assessments/abc-123/edit", { name: "assessment-edit", id: "abc-123" }],
    ["#/more", { name: "more" }],
    ["#/templates", { name: "templates" }],
    ["#/reports", { name: "reports" }],
    ["#/reports/new", { name: "report-new" }],
    ["#/reports/from/t-1", { name: "report-new", templateId: "t-1" }],
    ["#/reports/abc-123", { name: "report-edit", id: "abc-123" }],
    [
      "#/chat/r-1/secret-32-chars",
      { name: "chat", roomId: "r-1", inviteToken: "secret-32-chars" },
    ],
    ["#/chat/r-1", { name: "dashboard" }],
    ["#/files", { name: "files" }],
    ["#/calendar", { name: "calendar" }],
    ["#/safe", { name: "safe" }],
    ["#/unknown", { name: "dashboard" }],
  ])("parses %s", (hash, expected) => {
    expect(parseHash(hash)).toEqual(expected);
  });
});
