import {
  useEffect,
  useMemo,
  useRef,
  useState,
  type FormEvent,
  type ReactNode,
  type RefObject,
} from "react";
import {
  api,
  ApiError,
  type ApiReportRoom,
  type ReportDocInput,
} from "../../shared/api/client";
import { useApiToken, useAuth } from "../../shared/hooks/auth";
import { useAsync } from "../../shared/hooks/useAsync";
import { documentStats, renderMarkdown } from "../../shared/lib/markdown";
import { navigate } from "../../shared/lib/routes";
import { deriveChatKey, encryptText } from "../../shared/lib/e2ee";
import {
  AttachedFiles,
  FileStager,
  uploadStagedFiles,
} from "../../shared/ui/AttachedFiles";
import { Button } from "../../shared/ui/Button";
import { ConfirmDialog } from "../../shared/ui/ConfirmDialog";
import { ErrorState } from "../../shared/ui/ErrorState";
import { TextField } from "../../shared/ui/Field";
import { Skeleton } from "../../shared/ui/Skeleton";
import { getChatKey } from "./chatKeys";

type ViewMode = "write" | "split" | "read";

const VIEW_LABELS: Record<ViewMode, string> = {
  write: "Текст",
  split: "Два окна",
  read: "Просмотр",
};

/**
 * Report document editor — create and edit, formatted like a document.
 *
 * Working model: the body is Markdown with a toolbar, a live preview
 * (split view) and device-local draft autosave — a closed tab never eats a
 * half-written report. Report requisites (класс, период, направление) are
 * structured fields, so documents stay comparable. «Отправить в чат»
 * encrypts the finished document on this device and posts the ciphertext to
 * the chosen room; files attach through the same owner-checked pipeline as
 * every other entity.
 *
 * The preview HTML is safe to mount: renderMarkdown escapes the source
 * first and allowlists link schemes (see shared/lib/markdown.ts).
 */
export function ReportEditorPage({
  id,
  templateId,
}: {
  id?: string;
  templateId?: string;
}) {
  const token = useApiToken();
  const { handleUnauthorized } = useAuth();

  const { data, error, loading, reload } = useAsync(async () => {
    if (token === null) throw new Error("no token");
    if (id !== undefined) return { doc: await api.getReportDoc(token, id), tpl: null };
    if (templateId !== undefined)
      return { doc: null, tpl: await api.getTemplate(token, templateId) };
    return { doc: null, tpl: null };
  }, [token, id, templateId]);

  const initial = data?.doc ?? null;
  const templatePayload =
    data?.tpl && data.tpl.entity_type === "report" ? data.tpl.payload : null;

  const [title, setTitle] = useState<string | null>(null);
  const [subject, setSubject] = useState<string | null>(null);
  const [className, setClassName] = useState<string | null>(null);
  const [period, setPeriod] = useState<string | null>(null);
  const [content, setContent] = useState<string | null>(null);

  // Seed the form once the async source lands (null = untouched yet).
  const seededTitle =
    title ?? initial?.title ?? stringOf(templatePayload?.title) ?? "";
  const seededSubject =
    subject ??
    initial?.subject ??
    stringOf(templatePayload?.subject) ??
    "Отчётность";
  const seededClass =
    className ?? initial?.class_name ?? stringOf(templatePayload?.class_name) ?? "";
  const seededPeriod =
    period ?? initial?.period ?? stringOf(templatePayload?.period) ?? "";
  const seededContent =
    content ?? initial?.content ?? stringOf(templatePayload?.content) ?? "";

  const [view, setView] = useState<ViewMode>("write");
  const [busy, setBusy] = useState(false);
  const [dirty, setDirty] = useState(false);
  const [notice, setNotice] = useState<string | null>(null);
  const [formError, setFormError] = useState<string | null>(null);
  const [confirmDelete, setConfirmDelete] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [stagedFiles, setStagedFiles] = useState<File[]>([]);

  const formRef = useRef<HTMLFormElement>(null);
  const textRef = useRef<HTMLTextAreaElement>(null);

  // Unsaved draft lives on this device only, keyed per document.
  const draftKey = `smena-report-draft:${id ?? templateId ?? "new"}`;
  const [draftRestorable, setDraftRestorable] = useState(false);
  const draftChecked = useRef(false);
  const currentDraft = {
    title: seededTitle,
    subject: seededSubject,
    class_name: seededClass,
    period: seededPeriod,
    content: seededContent,
  };

  useEffect(() => {
    if (loading || !data || draftChecked.current) return;
    draftChecked.current = true;
    try {
      const raw = window.localStorage.getItem(draftKey);
      if (raw === null) return;
      const draft = JSON.parse(raw) as Partial<ReportDocInput>;
      if ((draft.content ?? "") !== seededContent) setDraftRestorable(true);
    } catch {
      // A corrupt draft is worth exactly nothing.
    }
  }, [data, loading, draftKey, seededContent]);

  // Debounced autosave while there are unsaved edits.
  useEffect(() => {
    if (!dirty) return;
    const timer = window.setTimeout(() => {
      window.localStorage.setItem(draftKey, JSON.stringify(currentDraft));
    }, 600);
    return () => window.clearTimeout(timer);
  }, [dirty, draftKey, currentDraft]);

  // Ctrl/Cmd+S saves through the real submit path.
  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "s") {
        e.preventDefault();
        formRef.current?.requestSubmit();
      }
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  const stats = useMemo(() => documentStats(seededContent), [seededContent]);

  if (loading && !data) return <Skeleton lines={5} />;

  if (error) {
    if (error instanceof ApiError && error.isUnauthorized) {
      handleUnauthorized();
      return null;
    }
    if (error instanceof ApiError && error.status === 404) {
      return (
        <ErrorState
          message="Документ не найден. Возможно, он был удалён."
          onRetry={() => navigate("#/reports")}
        />
      );
    }
    return <ErrorState message="Не удалось загрузить документ." onRetry={reload} />;
  }

  async function save(e: FormEvent) {
    e.preventDefault();
    if (token === null || busy) return;
    setBusy(true);
    setFormError(null);
    setNotice(null);
    const input: ReportDocInput = {
      title: seededTitle.trim(),
      subject: seededSubject.trim(),
      class_name: seededClass.trim(),
      period: seededPeriod.trim(),
      content: seededContent,
    };
    try {
      if (id !== undefined) {
        await api.updateReportDoc(token, id, input);
        window.localStorage.removeItem(draftKey);
        setDirty(false);
        setNotice("Сохранено.");
      } else {
        const created = await api.createReportDoc(token, input);
        // Staged files upload right after creation (never throws).
        if (stagedFiles.length > 0) {
          await uploadStagedFiles(
            token,
            { kind: "report", id: created.id },
            stagedFiles,
          );
        }
        window.localStorage.removeItem(draftKey);
        navigate(`#/reports/${created.id}`);
      }
    } catch (err) {
      if (err instanceof ApiError && err.isUnauthorized) handleUnauthorized();
      else if (err instanceof ApiError && err.status === 422) {
        setFormError(err.serverMessage ?? "Проверьте заполнение полей.");
      } else {
        setFormError("Не удалось сохранить. Попробуйте ещё раз.");
      }
    } finally {
      setBusy(false);
    }
  }

  async function remove() {
    if (token === null || id === undefined || deleting) return;
    setDeleting(true);
    try {
      await api.deleteReportDoc(token, id);
      window.localStorage.removeItem(draftKey);
      navigate("#/reports");
    } catch (err) {
      if (err instanceof ApiError && err.isUnauthorized) handleUnauthorized();
      else setNotice("Не удалось удалить документ.");
      setDeleting(false);
      setConfirmDelete(false);
    }
  }

  function restoreDraft() {
    try {
      const raw = window.localStorage.getItem(draftKey);
      if (raw === null) return;
      const draft = JSON.parse(raw) as Partial<ReportDocInput>;
      setTitle(draft.title ?? seededTitle);
      setSubject(draft.subject ?? seededSubject);
      setClassName(draft.class_name ?? seededClass);
      setPeriod(draft.period ?? seededPeriod);
      setContent(draft.content ?? seededContent);
      setDirty(true);
    } catch {
      window.localStorage.removeItem(draftKey);
    }
    setDraftRestorable(false);
  }

  function discardDraft() {
    window.localStorage.removeItem(draftKey);
    setDraftRestorable(false);
  }

  const isEdit = id !== undefined;

  return (
    <>
      <div className="page-header">
        <div>
          <p className="eyebrow">ОТЧЁТ</p>
          <h1>{isEdit ? "Документ отчёта" : "Новый отчёт"}</h1>
        </div>
        <div className="segmented" role="group" aria-label="Режим редактора">
          {(Object.keys(VIEW_LABELS) as ViewMode[]).map((mode) => (
            <button
              key={mode}
              type="button"
              className="segmented-button"
              aria-pressed={view === mode}
              onClick={() => setView(mode)}
            >
              {VIEW_LABELS[mode]}
            </button>
          ))}
        </div>
      </div>

      {draftRestorable && (
        <div className="draft-banner" role="status">
          <span>На этом устройстве есть несохранённый черновик.</span>
          <span className="draft-banner-actions">
            <Button variant="secondary" onClick={restoreDraft}>
              Восстановить
            </Button>
            <Button variant="ghost" onClick={discardDraft}>
              Убрать черновик
            </Button>
          </span>
        </div>
      )}

      <form
        ref={formRef}
        className="report-editor"
        aria-label={isEdit ? "Редактор отчёта" : "Новый отчёт"}
        onSubmit={save}
      >
        <div className="report-editor-main">
          <TextField
            label="Название"
            value={seededTitle}
            onChange={(e) => {
              setTitle(e.target.value);
              setDirty(true);
            }}
            placeholder="Например: Отчёт по самообразованию, IV четверть"
            maxLength={200}
            required
          />

          {view !== "read" && (
            <div className="md-toolbar" role="toolbar" aria-label="Форматирование">
              <MdButton title="Раздел (заголовок)" onClick={() => insertLinePrefix(textRef, "## ", "Раздел")} bold>
                H2
              </MdButton>
              <MdButton title="Полужирный (выделите текст)" onClick={() => wrapSelection(textRef, "**", "**", "текст")} bold>
                Ж
              </MdButton>
              <MdButton title="Курсив" onClick={() => wrapSelection(textRef, "*", "*", "текст")} italic>
                К
              </MdButton>
              <MdButton title="Строчный код" onClick={() => wrapSelection(textRef, "`", "`", "код")}>
                &lt;/&gt;
              </MdButton>
              <MdButton title="Маркированный список" onClick={() => insertLinePrefix(textRef, "- ", "пункт")}>
                • Список
              </MdButton>
              <MdButton title="Нумерованный список" onClick={() => insertLinePrefix(textRef, "1. ", "пункт")}>
                1. Список
              </MdButton>
              <MdButton title="Цитата / выноска" onClick={() => insertLinePrefix(textRef, "> ", "выноска")}>
                ❝ Цитата
              </MdButton>
              <MdButton title="Ссылка" onClick={() => wrapSelection(textRef, "[", "](https://)", "текст ссылки")}>
                🔗 Ссылка
              </MdButton>
              <MdButton
                title="Таблица"
                onClick={() =>
                  insertBlock(
                    textRef,
                    "\n| Параметр | Значение |\n| --- | --- |\n|  |  |\n",
                  )
                }
              >
                ▦ Таблица
              </MdButton>
              <MdButton title="Разделитель" onClick={() => insertBlock(textRef, "\n---\n")}>
                — Разделитель
              </MdButton>
            </div>
          )}

          <div className={`report-editor-body view-${view}`}>
            {view !== "read" && (
              <textarea
                ref={textRef}
                className="report-editor-textarea"
                aria-label="Текст отчёта (Markdown)"
                rows={20}
                value={seededContent}
                placeholder={"## Выводы\n- что сделали\n- что дальше\n\n| Показатель | Значение |\n| --- | --- |"}
                onChange={(e) => {
                  setContent(e.target.value);
                  setDirty(true);
                }}
              />
            )}
            {view !== "write" && (
              <div
                className="md-preview"
                aria-label="Предпросмотр отчёта"
                dangerouslySetInnerHTML={{ __html: renderMarkdown(seededContent) }}
              />
            )}
          </div>

          <p className="report-stats">
            <span>
              {stats.words} сл. · {stats.characters} зн.
            </span>
            <span className={dirty ? "report-stats-dirty" : "report-stats-clean"}>
              {dirty ? "● Не сохранено" : "Сохранённая версия актуальна"}
            </span>
            <span className="report-stats-hint">Ctrl+S — сохранить</span>
          </p>

          {formError !== null && (
            <p className="form-error" role="alert">
              {formError}
            </p>
          )}
          {notice !== null && (
            <p className="inline-notice" role="status">
              {notice}
            </p>
          )}

          <div className="form-actions">
            <Button type="submit" busy={busy}>
              {isEdit ? "Сохранить" : "Создать отчёт"}
            </Button>
            <Button variant="ghost" onClick={() => navigate("#/reports")}>
              К списку
            </Button>
            {isEdit && (
              <Button variant="danger" onClick={() => setConfirmDelete(true)}>
                Удалить
              </Button>
            )}
          </div>
        </div>

        <aside className="material-editor-side" aria-label="Реквизиты и вложения">
          <p className="eyebrow">РЕКВИЗИТЫ</p>
          <h2>Реквизиты документа</h2>
          <TextField
            label="Предмет / направление"
            value={seededSubject}
            onChange={(e) => {
              setSubject(e.target.value);
              setDirty(true);
            }}
            maxLength={120}
          />
          <TextField
            label="Класс"
            value={seededClass}
            onChange={(e) => {
              setClassName(e.target.value);
              setDirty(true);
            }}
            placeholder="Например: 4 «Б»"
            maxLength={64}
          />
          <TextField
            label="Период"
            value={seededPeriod}
            onChange={(e) => {
              setPeriod(e.target.value);
              setDirty(true);
            }}
            placeholder="Например: I четверть 2026/27"
            maxLength={120}
          />
          <p className="editor-note">
            Текст отчёта — Markdown: заголовки ##, списки «-», таблицы
            вертикальными чертами. Кнопки сверху вставляют шаблоны.
          </p>

          {isEdit && initial !== null ? (
            <AttachedFiles
              target={{ kind: "report", id: initial.id }}
              emptyText="К отчёту файлов пока нет."
            />
          ) : (
            <FileStager files={stagedFiles} onChange={setStagedFiles} />
          )}
        </aside>
      </form>

      {isEdit && initial !== null && (
        <SendToChat
          title={seededTitle}
          subject={seededSubject}
          className={seededClass}
          period={seededPeriod}
          content={seededContent}
        />
      )}

      <ConfirmDialog
        open={confirmDelete}
        title="Удалить отчёт?"
        description="Документ будет удалён без возможности восстановления."
        confirmLabel="Удалить"
        busy={deleting}
        onConfirm={remove}
        onCancel={() => setConfirmDelete(false)}
      />
    </>
  );
}

// --- Markdown toolbar helpers -------------------------------------------------
// Both mutate the textarea through its value + selection, then restore the
// caret. React owns the value, so the change flows through setContent/dirty.

function wrapSelection(
  ref: RefObject<HTMLTextAreaElement | null>,
  before: string,
  after: string,
  placeholder: string,
): void {
  const el = ref.current;
  if (el === null) return;
  const { selectionStart: start, selectionEnd: end, value } = el;
  const selected = value.slice(start, end) === "" ? placeholder : value.slice(start, end);
  const next = value.slice(0, start) + before + selected + after + value.slice(end);
  applyValue(el, next);
  requestAnimationFrame(() => {
    el.focus();
    el.setSelectionRange(start + before.length, start + before.length + selected.length);
  });
}

function insertLinePrefix(
  ref: RefObject<HTMLTextAreaElement | null>,
  prefix: string,
  placeholder: string,
): void {
  const el = ref.current;
  if (el === null) return;
  const { selectionStart: start, selectionEnd: end, value } = el;
  const lineStart = value.lastIndexOf("\n", start - 1) + 1;
  const lineEndRaw = value.indexOf("\n", Math.max(end, start));
  const lineEnd = lineEndRaw === -1 ? value.length : lineEndRaw;
  const block = value.slice(lineStart, lineEnd);
  const lines = block === "" ? [placeholder] : block.split("\n");
  const prefixed = lines
    .map((line, index) =>
      prefix.startsWith("1.")
        ? `${index + 1}. ${line.replace(/^\s*\d+[.)]\s+/, "")}`
        : prefix + line.replace(/^(\s*)([-*+]\s+|\d+[.)]\s+|#{1,6}\s+|>\s+)?/, "$1"),
    )
    .join("\n");
  const next = value.slice(0, lineStart) + prefixed + value.slice(lineEnd);
  applyValue(el, next);
  requestAnimationFrame(() => {
    el.focus();
    el.setSelectionRange(lineStart, lineStart + prefixed.length);
  });
}

function insertBlock(
  ref: RefObject<HTMLTextAreaElement | null>,
  block: string,
): void {
  const el = ref.current;
  if (el === null) return;
  const { selectionStart: start, selectionEnd: end, value } = el;
  const next = value.slice(0, start) + block + value.slice(end);
  applyValue(el, next);
  requestAnimationFrame(() => {
    el.focus();
    el.setSelectionRange(start + block.length, start + block.length);
  });
}

/** Write through the native setter so React's onChange fires (controlled input). */
function applyValue(el: HTMLTextAreaElement, next: string): void {
  const setter = Object.getOwnPropertyDescriptor(
    HTMLTextAreaElement.prototype,
    "value",
  )?.set;
  if (setter) setter.call(el, next);
  el.dispatchEvent(new Event("input", { bubbles: true }));
}

function MdButton({
  title,
  onClick,
  children,
  bold,
  italic,
}: {
  title: string;
  onClick: () => void;
  children: ReactNode;
  bold?: boolean;
  italic?: boolean;
}) {
  return (
    <button
      type="button"
      className="md-button"
      title={title}
      aria-label={title}
      onClick={onClick}
      style={bold ? { fontWeight: 700 } : italic ? { fontStyle: "italic" } : undefined}
    >
      {children}
    </button>
  );
}

/** Encrypt-and-post the current report text into a chosen chat (server sees ciphertext only). */
function SendToChat(props: {
  title: string;
  subject: string;
  className: string;
  period: string;
  content: string;
}) {
  const token = useApiToken();
  const { handleUnauthorized } = useAuth();
  const [status, setStatus] = useState<"idle" | "sending" | "sent">("idle");
  const [error, setError] = useState<string | null>(null);
  const [roomId, setRoomId] = useState("");

  const { data } = useAsync(async () => {
    if (token === null) throw new Error("no token");
    return api.listReportRooms(token);
  }, [token]);

  const joinable: ApiReportRoom[] = (data ?? []).filter(
    (room) => getChatKey(room.id) !== null,
  );

  if (!data || joinable.length === 0) return null;
  const rooms = data;

  async function send() {
    if (token === null || roomId === "" || status === "sending") return;
    setStatus("sending");
    setError(null);
    try {
      const secret = getChatKey(roomId);
      if (secret === null) throw new Error("no key");
      const key = await deriveChatKey(secret);
      const requisites = [props.className, props.period]
        .filter((part) => part !== "")
        .join(" · ");
      const plaintext =
        `📄 Отчёт: ${props.title}` +
        (props.subject ? `\n${props.subject}` : "") +
        (requisites !== "" ? `\n${requisites}` : "") +
        `\n\n${props.content}`;
      await api.postReportMessage(token, roomId, await encryptText(key, plaintext));
      setStatus("sent");
    } catch (err) {
      if (err instanceof ApiError && err.isUnauthorized) handleUnauthorized();
      else setError("Не удалось отправить отчёт в чат. Попробуйте ещё раз.");
      setStatus("idle");
    }
  }

  return (
    <section className="plan-section" aria-labelledby="report-send-title">
      <h2 id="report-send-title">Отправить в чат</h2>
      <p>
        Текущий текст (включая несохранённые правки) будет зашифрован на этом
        устройстве; сервер передаст только шифр.
      </p>
      <div className="chat-form">
        <div className="field">
          <label htmlFor="report-send-room">Чат</label>
          <select
            id="report-send-room"
            value={roomId}
            onChange={(e) => setRoomId(e.target.value)}
          >
            <option value="">Выберите чат…</option>
            {rooms.map((room) => (
              <option key={room.id} value={room.id}>
                {room.name}
              </option>
            ))}
          </select>
        </div>
        <Button
          onClick={send}
          busy={status === "sending"}
          disabled={roomId === ""}
        >
          Отправить
        </Button>
      </div>
      {status === "sent" && (
        <p className="inline-notice" role="status">
          Отчёт отправлен в чат.
        </p>
      )}
      {error !== null && (
        <p className="form-error" role="alert">
          {error}
        </p>
      )}
    </section>
  );
}

function stringOf(value: unknown): string | null {
  return typeof value === "string" ? value : null;
}
