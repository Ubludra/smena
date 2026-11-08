import { useRef, useState } from "react";
import {
  api,
  ApiError,
  type ApiFile,
  type FileTarget,
} from "../api/client";
import { useApiToken, useAuth } from "../hooks/auth";
import { useAsync } from "../hooks/useAsync";
import { relativeDate } from "../lib/dates";
import { Button } from "./Button";
import { ConfirmDialog } from "./ConfirmDialog";
import { MaterialListSkeleton } from "./Skeleton";

/** Server limit mirror (settings.upload_max_bytes); checked before upload. */
export const MAX_UPLOAD_BYTES = 20 * 1024 * 1024;

export function formatSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} Б`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(0)} КБ`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} МБ`;
}

/**
 * Files attached to any workspace entity (material, plan, assessment,
 * assignment, report). Uploads carry the entity id, so the server links the
 * blob after checking ownership; deleting the host entity keeps the file in
 * the «Файлы» drawer (SET NULL) — never silently lost.
 */
export function AttachedFiles({
  target,
  emptyText = "Файлов пока нет.",
}: {
  target: FileTarget;
  emptyText?: string;
}) {
  const token = useApiToken();
  const { handleUnauthorized } = useAuth();
  const { data, error, loading, reload } = useAsync(
    () => api.listFiles(token, { target }),
    [token, target.kind, target.id],
  );
  const inputRef = useRef<HTMLInputElement>(null);
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState<string | null>(null);
  const [deleting, setDeleting] = useState<ApiFile | null>(null);

  async function onPick(file: File) {
    setNotice(null);
    if (file.size > MAX_UPLOAD_BYTES) {
      setNotice("Файл больше 20 МБ");
      return;
    }
    setBusy(true);
    try {
      await api.uploadFile(token, file, target);
      reload();
    } catch (err) {
      if (err instanceof ApiError && err.isUnauthorized) handleUnauthorized();
      else if (err instanceof ApiError && err.serverMessage !== null)
        setNotice(err.serverMessage);
      else setNotice("Не удалось загрузить файл. Попробуйте ещё раз.");
    } finally {
      setBusy(false);
    }
  }

  async function download(file: ApiFile) {
    try {
      const blob = await api.downloadFile(token, file.id);
      // Same behaviour as <a download>, but with the auth header attached.
      const url = URL.createObjectURL(blob);
      const anchor = document.createElement("a");
      anchor.href = url;
      anchor.download = file.original_name;
      anchor.click();
      URL.revokeObjectURL(url);
    } catch (err) {
      if (err instanceof ApiError && err.isUnauthorized) handleUnauthorized();
      else setNotice("Не удалось скачать файл. Попробуйте ещё раз.");
    }
  }

  async function removeFile() {
    if (deleting === null) return;
    setBusy(true);
    setNotice(null);
    try {
      await api.deleteFile(token, deleting.id);
      setDeleting(null);
      reload();
    } catch (err) {
      if (err instanceof ApiError && err.isUnauthorized) handleUnauthorized();
      else setNotice("Не удалось удалить файл.");
      setBusy(false);
    }
  }

  return (
    <section className="material-files" aria-label="Файлы">
      <div className="section-title-row">
        <h2>Файлы</h2>
        <button
          type="button"
          className="text-action"
          disabled={busy}
          onClick={() => inputRef.current?.click()}
        >
          {busy ? "Загрузка…" : "Загрузить файл"}
        </button>
      </div>
      <input
        ref={inputRef}
        type="file"
        hidden
        aria-hidden="true"
        tabIndex={-1}
        onChange={(e) => {
          const file = e.target.files?.[0];
          if (file !== undefined) void onPick(file);
          // Reset so picking the same file again re-fires onChange.
          e.target.value = "";
        }}
      />

      {loading && !data && <MaterialListSkeleton />}

      {!loading && data && data.items.length === 0 && (
        <p className="detail-empty">{emptyText}</p>
      )}

      {error ? <p className="detail-empty">Не удалось загрузить файлы.</p> : null}

      {data && data.items.length > 0 && (
        <div className="material-list">
          {data.items.map((file) => (
            <div key={file.id} className="template-card-row">
              <button
                type="button"
                className="card material-card plan-card"
                onClick={() => void download(file)}
                aria-label={`Скачать ${file.original_name}`}
              >
                <span className="material-card-title">{file.original_name}</span>
                <span className="material-card-meta">
                  <span>{formatSize(file.size_bytes)}</span>
                  <span>{relativeDate(file.created_at)}</span>
                </span>
              </button>
              <Button variant="ghost" onClick={() => setDeleting(file)}>
                Удалить
              </Button>
            </div>
          ))}
        </div>
      )}

      <ConfirmDialog
        open={deleting !== null}
        title="Удалить файл?"
        description={
          deleting ? `«${deleting.original_name}» будет удалён без возврата.` : ""
        }
        confirmLabel="Удалить"
        busy={busy}
        onConfirm={() => void removeFile()}
        onCancel={() => setDeleting(null)}
      />
      {notice !== null && (
        <p className="form-error" role="alert">
          {notice}
        </p>
      )}
    </section>
  );
}

/** Upload files staged during creation. Returns the number of failures. */
export async function uploadStagedFiles(
  token: string,
  target: FileTarget,
  files: File[],
): Promise<number> {
  let failed = 0;
  for (const file of files) {
    try {
      await api.uploadFile(token, file, target);
    } catch {
      failed += 1;
    }
  }
  return failed;
}

/**
 * File picker for CREATE forms: files cannot be attached before the entity
 * exists, so they are staged here and uploaded right after creation via
 * uploadStagedFiles. Selected files live in memory only until then.
 */
export function FileStager({
  files,
  onChange,
}: {
  files: File[];
  onChange: (next: File[]) => void;
}) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [notice, setNotice] = useState<string | null>(null);

  function add(picked: FileList) {
    setNotice(null);
    const next = [...files];
    for (const file of Array.from(picked)) {
      if (file.size > MAX_UPLOAD_BYTES) {
        setNotice(`«${file.name}» больше 20 МБ — не добавлен.`);
        continue;
      }
      // Same file picked twice is pointless in a staging list.
      if (next.some((f) => f.name === file.name && f.size === file.size))
        continue;
      next.push(file);
    }
    onChange(next);
  }

  return (
    <div className="file-stager">
      <div className="section-title-row">
        <h2>Файлы</h2>
        <button
          type="button"
          className="text-action"
          onClick={() => inputRef.current?.click()}
        >
          Прикрепить файлы
        </button>
      </div>
      <input
        ref={inputRef}
        type="file"
        hidden
        aria-hidden="true"
        tabIndex={-1}
        multiple
        onChange={(e) => {
          if (e.target.files !== null && e.target.files.length > 0)
            add(e.target.files);
          e.target.value = "";
        }}
      />
      {files.length > 0 && (
        <ul className="file-stager-list">
          {files.map((file, index) => (
            <li key={`${file.name}-${index}`}>
              <span>{file.name}</span>
              <span className="file-stager-size">{formatSize(file.size)}</span>
              <button
                type="button"
                className="text-action"
                aria-label={`Убрать ${file.name}`}
                onClick={() => onChange(files.filter((_, i) => i !== index))}
              >
                Убрать
              </button>
            </li>
          ))}
        </ul>
      )}
      {notice !== null && (
        <p className="form-error" role="alert">
          {notice}
        </p>
      )}
    </div>
  );
}
