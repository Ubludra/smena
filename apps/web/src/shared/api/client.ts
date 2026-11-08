/**
 * Typed API client.
 *
 * One place that knows: the base URL, the auth header, error shapes, and
 * timeouts. Components never call fetch directly — so adding retries,
 * request ids or telemetry later changes exactly one file.
 *
 * Error contract with the backend:
 *   - non-2xx JSON may carry {detail: string | {code, message}};
 *   - network failures become ApiError(status=0, code="NETWORK") so the UI
 *     can offer a retry instead of a white screen.
 */

import { getSafeToken } from "../lib/safeToken";

export interface ApiUser {
  id: string;
  display_name: string;
}

export interface ApiMaterial {
  id: string;
  title: string;
  subject: string;
  content: string;
  is_protected: boolean;
  created_at: string;
  updated_at: string;
}

export interface MaterialInput {
  title: string;
  subject: string;
  content: string;
  is_protected: boolean;
}

export interface MaterialListParams {
  search?: string;
  onlyProtected?: boolean;
  limit?: number;
  offset?: number;
}

export class ApiError extends Error {
  constructor(
    readonly status: number,
    /** Stable machine code when the backend provides one (MAX_*, NETWORK…). */
    readonly code: string | null,
    /** Human-readable Russian message from the server, if any. */
    readonly serverMessage: string | null,
  ) {
    super(`API error ${status}${code ? ` ${code}` : ""}`);
    this.name = "ApiError";
  }

  get isUnauthorized(): boolean {
    return this.status === 401;
  }
}

const REQUEST_TIMEOUT_MS = 15_000;

function baseUrl(): string {
  // VITE_API_BASE_URL is baked in at build time (compose build arg).
  // Empty string ⇒ same-origin, for a future deployment behind one proxy.
  const raw = import.meta.env.VITE_API_BASE_URL ?? "";
  return String(raw).replace(/\/+$/, "");
}

interface RequestOptions {
  method?: "GET" | "POST" | "PATCH" | "DELETE";
  body?: unknown;
  /** Multipart body: sent as-is (the browser sets the boundary header). */
  formData?: FormData;
  /** Return the raw body as a Blob (file downloads) instead of parsed JSON. */
  asBlob?: boolean;
  token?: string | null;
}

async function request<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const headers: Record<string, string> = {};
  if (options.body !== undefined) headers["Content-Type"] = "application/json";
  if (options.token) headers["Authorization"] = `Bearer ${options.token}`;
  // A live Safe unlock rides along on every call; routes that do not gate
  // on it simply ignore the header (server: api/routes/safe.py).
  const safeToken = getSafeToken();
  if (safeToken) headers["X-Safe-Token"] = safeToken;

  let response: Response;
  try {
    response = await fetch(`${baseUrl()}/api/v1${path}`, {
      method: options.method ?? "GET",
      headers,
      body:
        options.formData ??
        (options.body !== undefined ? JSON.stringify(options.body) : undefined),
      signal: AbortSignal.timeout(REQUEST_TIMEOUT_MS),
    });
  } catch {
    // DNS/offline/timeout: distinguish from server errors for retry UX.
    throw new ApiError(0, "NETWORK", "Не удалось связаться с сервером");
  }

  if (response.status === 204) return undefined as T;

  if (options.asBlob) {
    if (!response.ok) throw await errorFrom(response, null);
    return (await response.blob()) as T;
  }

  let payload: unknown = null;
  try {
    payload = await response.json();
  } catch {
    // Non-JSON body (proxy error page etc.) — treat as unnamed failure.
  }

  if (!response.ok) throw await errorFrom(response, payload);

  return payload as T;
}

/** Map an error response to ApiError (reused by the JSON and Blob paths). */
async function errorFrom(response: Response, payload: unknown): Promise<ApiError> {
  let code: string | null = null;
  let message: string | null = null;
  const detail = (payload as { detail?: unknown } | null)?.detail;
  if (typeof detail === "string") {
    message = detail;
  } else if (detail && typeof detail === "object") {
    const d = detail as { code?: string; message?: string };
    code = d.code ?? null;
    message = d.message ?? null;
  }
  return new ApiError(response.status, code, message);
}

// --- Lesson plans -------------------------------------------------------------

export interface ApiStage {
  title: string;
  minutes: number | null;
  description: string;
}

export interface ApiLessonPlan {
  id: string;
  title: string;
  subject: string;
  class_name: string;
  lesson_date: string | null;
  start_time: string | null;
  duration_minutes: number | null;
  topic: string;
  goal: string;
  objectives: string[];
  stages: ApiStage[];
  homework: string;
  notes: string;
  created_at: string;
  updated_at: string;
}

export interface LessonPlanInput {
  title: string;
  subject: string;
  class_name: string;
  lesson_date: string | null;
  start_time: string | null;
  duration_minutes: number | null;
  topic: string;
  goal: string;
  objectives: string[];
  stages: ApiStage[];
  homework: string;
  notes: string;
}

export interface LessonPlanListParams {
  search?: string;
  className?: string;
  subject?: string;
  dateFrom?: string;
  dateTo?: string;
  limit?: number;
  offset?: number;
}

// --- Assignments ---------------------------------------------------------------

export type AssignmentStatus = "active" | "done" | "archived";

export interface ApiAssignment {
  id: string;
  title: string;
  description: string;
  subject: string;
  class_name: string;
  due_at: string | null;
  status: AssignmentStatus;
  related_material_id: string | null;
  created_at: string;
  updated_at: string;
}

export interface AssignmentInput {
  title: string;
  description: string;
  subject: string;
  class_name: string;
  due_at: string | null;
  status: AssignmentStatus;
  related_material_id: string | null;
}

export interface AssignmentListParams {
  search?: string;
  status?: AssignmentStatus | "";
  className?: string;
  subject?: string;
  limit?: number;
  offset?: number;
}

// --- Assessments ---------------------------------------------------------------

export type QuestionType = "single" | "multi" | "text";

export interface ApiQuestion {
  id: string;
  text: string;
  type: QuestionType;
  options: (string | number)[];
  correct: (string | number)[];
}

export interface ApiAssessment {
  id: string;
  title: string;
  description: string;
  subject: string;
  class_name: string;
  scheduled_at: string | null;
  duration_minutes: number | null;
  is_protected: boolean;
  questions: ApiQuestion[];
  created_at: string;
  updated_at: string;
}

export interface QuestionInput {
  text: string;
  type: QuestionType;
  options: string[];
  correct: (string | number)[];
}

export interface AssessmentInput {
  title: string;
  description: string;
  subject: string;
  class_name: string;
  scheduled_at: string | null;
  duration_minutes: number | null;
  is_protected: boolean;
  questions: QuestionInput[];
}

export interface AssessmentListParams {
  search?: string;
  className?: string;
  subject?: string;
  onlyProtected?: boolean;
  limit?: number;
  offset?: number;
}

// --- Templates ---------------------------------------------------------------

export type TemplateEntityType =
  | "lesson_plan"
  | "assignment"
  | "assessment"
  | "report";

export interface ApiTemplate {
  id: string;
  name: string;
  entity_type: TemplateEntityType;
  payload: Record<string, unknown>;
  /** Seeded system row (report skeleton): read-only for every user. */
  is_system: boolean;
  created_at: string;
  updated_at: string;
}

// --- Reports ---------------------------------------------------------------

export interface ApiReport {
  period: { start: string; end: string };
  created: {
    materials: number;
    lesson_plans: number;
    assignments: number;
    assessments: number;
  };
  safe: { materials: number; assessments: number };
  assignments: { active: number; overdue: number; due_soon: number };
  materials_by_subject: { subject: string; count: number }[];
  upcoming: {
    type: "lesson_plan" | "assignment";
    id: string;
    title: string;
    date: string;
  }[];
}

// --- Report documents (the Отчёты editor) -------------------------------------

export interface ApiReportDoc {
  id: string;
  title: string;
  subject: string;
  /** Report requisite: the class covered ("4 «Б»" …), free text. */
  class_name: string;
  /** Report requisite: the reporting period, free text. */
  period: string;
  content: string;
  created_at: string;
  updated_at: string;
}

export interface ReportDocInput {
  title: string;
  subject: string;
  class_name: string;
  period: string;
  content: string;
}

// --- Safe unlock ---------------------------------------------------------------

export interface ApiSafeStatus {
  has_password: boolean;
}

export interface ApiSafeUnlock {
  token: string;
  expires_in_seconds: number;
}

export interface ApiSafeSecurityStatus {
  registered: boolean;
  pending_change: boolean;
  configured: boolean;
}

// --- Report chat (E2E-encrypted) ----------------------------------------------

export interface ApiReportRoom {
  id: string;
  name: string;
  created_at: string;
}

export interface ApiReportRoomCreated extends ApiReportRoom {
  /** Client hash route carrying the invite secret — shown exactly once. */
  invite_path: string;
}

export interface ApiReportMessage {
  id: string;
  sender_id: string;
  /** base64 AES-GCM payload; the server never sees plaintext. */
  ciphertext: string;
  created_at: string;
}

// --- Files -----------------------------------------------------------------

/** Workspace entities a file can be attached to (client-side kind names). */
export type FileTargetKind =
  | "material"
  | "lesson_plan"
  | "assessment"
  | "assignment"
  | "report";

/** Server form/query field for each kind — mirrors api routes/files.py. */
export const FILE_TARGET_FIELDS: Record<FileTargetKind, string> = {
  material: "material_id",
  lesson_plan: "lesson_plan_id",
  assessment: "assessment_id",
  assignment: "assignment_id",
  report: "report_id",
};

export interface FileTarget {
  kind: FileTargetKind;
  id: string;
}

export interface ApiFile {
  id: string;
  original_name: string;
  mime_type: string;
  size_bytes: number;
  created_at: string;
  /** Set when the file is attached to the corresponding entity. */
  material_id: string | null;
  lesson_plan_id: string | null;
  assessment_id: string | null;
  assignment_id: string | null;
  report_id: string | null;
}

export interface ApiFileList {
  items: ApiFile[];
  total: number;
}

// --- Calendar ---------------------------------------------------------------

export type CalendarEventType = "lesson_plan" | "assignment" | "assessment";

export interface ApiCalendarEvent {
  type: CalendarEventType;
  id: string;
  title: string;
  /** Plain calendar date, "YYYY-MM-DD". */
  date: string;
  /** "HH:MM" when the source carries a time. */
  time: string | null;
  status: string | null;
}

export interface ApiCalendar {
  year: number;
  month: number;
  events: ApiCalendarEvent[];
}

// --- Endpoints ---------------------------------------------------------------

export interface TokenResponse {
  access_token: string;
  token_type: string;
  user: ApiUser;
}

export const api = {
  devLogin: (displayName: string) =>
    request<TokenResponse>("/auth/dev-login", {
      method: "POST",
      body: { display_name: displayName },
    }),

  maxLaunch: (initData: string) =>
    request<TokenResponse>("/auth/max-launch", {
      method: "POST",
      body: { init_data: initData },
    }),

  me: (token: string) => request<ApiUser>("/auth/me", { token }),

  listMaterials: (token: string, params: MaterialListParams = {}) => {
    const query = new URLSearchParams();
    if (params.search) query.set("search", params.search);
    if (params.onlyProtected) query.set("only_protected", "true");
    query.set("limit", String(params.limit ?? 50));
    if (params.offset) query.set("offset", String(params.offset));
    return request<{ items: ApiMaterial[]; total: number }>(
      `/materials?${query.toString()}`,
      { token },
    );
  },

  getMaterial: (token: string, id: string) =>
    request<ApiMaterial>(`/materials/${id}`, { token }),

  createMaterial: (token: string, input: MaterialInput) =>
    request<ApiMaterial>("/materials", { method: "POST", body: input, token }),

  updateMaterial: (
    token: string,
    id: string,
    patch: Partial<MaterialInput>,
  ) =>
    request<ApiMaterial>(`/materials/${id}`, {
      method: "PATCH",
      body: patch,
      token,
    }),

  deleteMaterial: (token: string, id: string) =>
    request<void>(`/materials/${id}`, { method: "DELETE", token }),

  listLessonPlans: (token: string, params: LessonPlanListParams = {}) => {
    const query = new URLSearchParams();
    if (params.search) query.set("search", params.search);
    if (params.className) query.set("class_name", params.className);
    if (params.subject) query.set("subject", params.subject);
    if (params.dateFrom) query.set("date_from", params.dateFrom);
    if (params.dateTo) query.set("date_to", params.dateTo);
    query.set("limit", String(params.limit ?? 50));
    if (params.offset) query.set("offset", String(params.offset));
    return request<{ items: ApiLessonPlan[]; total: number }>(
      `/lesson-plans?${query.toString()}`,
      { token },
    );
  },

  getLessonPlan: (token: string, id: string) =>
    request<ApiLessonPlan>(`/lesson-plans/${id}`, { token }),

  createLessonPlan: (token: string, input: LessonPlanInput) =>
    request<ApiLessonPlan>("/lesson-plans", {
      method: "POST",
      body: input,
      token,
    }),

  updateLessonPlan: (
    token: string,
    id: string,
    patch: Partial<LessonPlanInput>,
  ) =>
    request<ApiLessonPlan>(`/lesson-plans/${id}`, {
      method: "PATCH",
      body: patch,
      token,
    }),

  duplicateLessonPlan: (token: string, id: string) =>
    request<ApiLessonPlan>(`/lesson-plans/${id}/duplicate`, {
      method: "POST",
      token,
    }),

  deleteLessonPlan: (token: string, id: string) =>
    request<void>(`/lesson-plans/${id}`, { method: "DELETE", token }),

  listAssignments: (token: string, params: AssignmentListParams = {}) => {
    const query = new URLSearchParams();
    if (params.search) query.set("search", params.search);
    if (params.status) query.set("status", params.status);
    if (params.className) query.set("class_name", params.className);
    if (params.subject) query.set("subject", params.subject);
    query.set("limit", String(params.limit ?? 50));
    if (params.offset) query.set("offset", String(params.offset));
    return request<{ items: ApiAssignment[]; total: number }>(
      `/assignments?${query.toString()}`,
      { token },
    );
  },

  getAssignment: (token: string, id: string) =>
    request<ApiAssignment>(`/assignments/${id}`, { token }),

  createAssignment: (token: string, input: AssignmentInput) =>
    request<ApiAssignment>("/assignments", { method: "POST", body: input, token }),

  updateAssignment: (
    token: string,
    id: string,
    patch: Partial<AssignmentInput>,
  ) =>
    request<ApiAssignment>(`/assignments/${id}`, {
      method: "PATCH",
      body: patch,
      token,
    }),

  deleteAssignment: (token: string, id: string) =>
    request<void>(`/assignments/${id}`, { method: "DELETE", token }),

  listAssessments: (token: string, params: AssessmentListParams = {}) => {
    const query = new URLSearchParams();
    if (params.search) query.set("search", params.search);
    if (params.className) query.set("class_name", params.className);
    if (params.subject) query.set("subject", params.subject);
    if (params.onlyProtected) query.set("only_protected", "true");
    query.set("limit", String(params.limit ?? 50));
    if (params.offset) query.set("offset", String(params.offset));
    return request<{ items: ApiAssessment[]; total: number }>(
      `/assessments?${query.toString()}`,
      { token },
    );
  },

  getAssessment: (token: string, id: string) =>
    request<ApiAssessment>(`/assessments/${id}`, { token }),

  createAssessment: (token: string, input: AssessmentInput) =>
    request<ApiAssessment>("/assessments", { method: "POST", body: input, token }),

  updateAssessment: (
    token: string,
    id: string,
    patch: Partial<AssessmentInput>,
  ) =>
    request<ApiAssessment>(`/assessments/${id}`, {
      method: "PATCH",
      body: patch,
      token,
    }),

  duplicateAssessment: (token: string, id: string) =>
    request<ApiAssessment>(`/assessments/${id}/duplicate`, {
      method: "POST",
      token,
    }),

  deleteAssessment: (token: string, id: string) =>
    request<void>(`/assessments/${id}`, { method: "DELETE", token }),

  listTemplates: (
    token: string,
    params: { entityType?: string; limit?: number } = {},
  ) => {
    const query = new URLSearchParams();
    if (params.entityType) query.set("entity_type", params.entityType);
    query.set("limit", String(params.limit ?? 50));
    return request<{ items: ApiTemplate[]; total: number }>(
      `/templates?${query.toString()}`,
      { token },
    );
  },

  getTemplate: (token: string, id: string) =>
    request<ApiTemplate>(`/templates/${id}`, { token }),

  createTemplate: (
    token: string,
    input: {
      name: string;
      entity_type: TemplateEntityType;
      payload: Record<string, unknown>;
    },
  ) => request<ApiTemplate>("/templates", { method: "POST", body: input, token }),

  deleteTemplate: (token: string, id: string) =>
    request<void>(`/templates/${id}`, { method: "DELETE", token }),

  reportSummary: (
    token: string,
    params: {
      period: "7d" | "30d" | "month" | "custom";
      dateFrom?: string;
      dateTo?: string;
    },
  ) => {
    const query = new URLSearchParams();
    query.set("period", params.period);
    if (params.dateFrom) query.set("date_from", params.dateFrom);
    if (params.dateTo) query.set("date_to", params.dateTo);
    return request<ApiReport>(`/reports/summary?${query.toString()}`, { token });
  },

  listFiles: (
    token: string,
    params: { offset?: number; target?: FileTarget } = {},
  ) => {
    const query = new URLSearchParams();
    if (params.offset !== undefined) query.set("offset", String(params.offset));
    if (params.target !== undefined)
      query.set(FILE_TARGET_FIELDS[params.target.kind], params.target.id);
    const suffix = query.toString() ? `?${query.toString()}` : "";
    return request<ApiFileList>(`/files${suffix}`, { token });
  },

  uploadFile: (token: string, file: File, target?: FileTarget) => {
    const form = new FormData();
    form.append("upload", file);
    if (target !== undefined)
      form.append(FILE_TARGET_FIELDS[target.kind], target.id);
    return request<ApiFile>("/files", { method: "POST", formData: form, token });
  },

  downloadFile: (token: string, id: string) =>
    request<Blob>(`/files/${id}/download`, { asBlob: true, token }),

  deleteFile: (token: string, id: string) =>
    request<void>(`/files/${id}`, { method: "DELETE", token }),

  getCalendar: (token: string, params: { year: number; month: number }) =>
    request<ApiCalendar>(
      `/calendar?year=${params.year}&month=${params.month}`,
      { token },
    ),

  // --- Safe ------------------------------------------------------------------

  safeStatus: (token: string) => request<ApiSafeStatus>("/safe/status", { token }),

  safeUnlock: (token: string, password: string) =>
    request<ApiSafeUnlock>("/safe/unlock", {
      method: "POST",
      body: { password },
      token,
    }),

  safeSecurityStatus: (token: string) =>
    request<ApiSafeSecurityStatus>("/safe/security/status", { token }),

  safePasskeyEnrollOptions: (token: string, currentPassword: string) =>
    request<import("../lib/passkey").RegistrationJSON>("/safe/security/enroll/options", {
      method: "POST", token, body: { current_password: currentPassword },
    }),

  safePasskeyEnrollFinish: (token: string, credential: Record<string, unknown>) =>
    request<{ registered: boolean }>("/safe/security/enroll/finish", {
      method: "POST", token, body: { credential },
    }),

  safePasswordChangeRequest: (token: string) =>
    request<{ pending: boolean }>("/safe/security/change/request", {
      method: "POST", token,
    }),

  safePasswordChangeOptions: (token: string) =>
    request<import("../lib/passkey").AuthenticationJSON>("/safe/security/change/options", {
      method: "POST", token,
    }),

  safePasswordChangeFinish: (
    token: string, newPassword: string, credential: Record<string, unknown>,
  ) => request<{ changed: boolean }>("/safe/security/change/finish", {
    method: "POST", token, body: { new_password: newPassword, credential },
  }),

  // --- Report documents --------------------------------------------------------

  listReportDocs: (
    token: string,
    params: { search?: string; limit?: number; offset?: number } = {},
  ) => {
    const query = new URLSearchParams();
    if (params.search) query.set("search", params.search);
    query.set("limit", String(params.limit ?? 50));
    if (params.offset) query.set("offset", String(params.offset));
    return request<{ items: ApiReportDoc[]; total: number }>(
      `/reports?${query.toString()}`,
      { token },
    );
  },

  getReportDoc: (token: string, id: string) =>
    request<ApiReportDoc>(`/reports/${id}`, { token }),

  createReportDoc: (token: string, input: ReportDocInput) =>
    request<ApiReportDoc>("/reports", { method: "POST", body: input, token }),

  updateReportDoc: (token: string, id: string, patch: Partial<ReportDocInput>) =>
    request<ApiReportDoc>(`/reports/${id}`, { method: "PATCH", body: patch, token }),

  deleteReportDoc: (token: string, id: string) =>
    request<void>(`/reports/${id}`, { method: "DELETE", token }),

  // --- Report chat (the API only ever relays ciphertext) -----------------------

  createReportRoom: (token: string, name: string) =>
    request<ApiReportRoomCreated>("/report-rooms", {
      method: "POST",
      body: { name },
      token,
    }),

  listReportRooms: (token: string) =>
    request<ApiReportRoom[]>("/report-rooms", { token }),

  joinReportRoom: (token: string, roomId: string, inviteToken: string) =>
    request<ApiReportRoom>("/report-rooms/join", {
      method: "POST",
      body: { room_id: roomId, invite_token: inviteToken },
      token,
    }),

  listReportMessages: (token: string, roomId: string) =>
    request<ApiReportMessage[]>(`/report-rooms/${roomId}/messages`, { token }),

  postReportMessage: (token: string, roomId: string, ciphertext: string) =>
    request<ApiReportMessage>(`/report-rooms/${roomId}/messages`, {
      method: "POST",
      body: { ciphertext },
      token,
    }),
};
