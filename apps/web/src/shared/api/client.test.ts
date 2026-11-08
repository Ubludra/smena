import { afterEach, describe, expect, it, vi } from "vitest";
import { api, ApiError } from "./client";

afterEach(() => vi.unstubAllGlobals());

describe("API client", () => {
  it("sends protected material filters and the bearer token", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      Response.json({ items: [], total: 0 }),
    );
    vi.stubGlobal("fetch", fetchMock);

    await api.listMaterials("session-token", {
      search: "biology",
      onlyProtected: true,
      limit: 10,
      offset: 20,
    });

    const [url, options] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(url).toContain("/api/v1/materials?");
    expect(url).toContain("search=biology");
    expect(url).toContain("only_protected=true");
    expect(url).toContain("limit=10");
    expect(url).toContain("offset=20");
    expect(new Headers(options.headers).get("Authorization")).toBe(
      "Bearer session-token",
    );
  });

  it("maps unauthorized responses to ApiError", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(Response.json({ detail: "Unauthorized" }, { status: 401 })),
    );

    await expect(api.me("expired-token")).rejects.toMatchObject({
      status: 401,
      isUnauthorized: true,
    } satisfies Partial<ApiError>);
  });

  it("maps network failures to a retryable network error", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new TypeError("offline")));

    await expect(api.me("session-token")).rejects.toMatchObject({
      status: 0,
      code: "NETWORK",
    });
  });

  it("sends lesson plan filters as backend query params", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      Response.json({ items: [], total: 0 }),
    );
    vi.stubGlobal("fetch", fetchMock);

    await api.listLessonPlans("session-token", {
      search: "дроби",
      className: "7Б",
      subject: "Математика",
      dateFrom: "2026-11-01",
      dateTo: "2026-11-30",
    });

    const [url, options] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(url).toContain("/api/v1/lesson-plans?");
    expect(url).toContain("search=");
    expect(url).toContain("class_name=7");
    expect(url).toContain("date_from=2026-11-01");
    expect(new Headers(options.headers).get("Authorization")).toBe(
      "Bearer session-token",
    );
  });

  it("duplicates a lesson plan with POST to the verb route", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      Response.json({ id: "copy-id", title: "копия" }),
    );
    vi.stubGlobal("fetch", fetchMock);

    const copy = await api.duplicateLessonPlan("session-token", "plan-1");

    const [url, options] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(url).toContain("/api/v1/lesson-plans/plan-1/duplicate");
    expect(options.method).toBe("POST");
    expect(copy).toMatchObject({ id: "copy-id" });
  });
});
