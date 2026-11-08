import { useRef, useState } from "react";
import { api, ApiError, type ApiFile } from "../../shared/api/client";
import { useApiToken, useAuth } from "../../shared/hooks/auth";
import { useAsync } from "../../shared/hooks/useAsync";
import { Button } from "../../shared/ui/Button";
import { ConfirmDialog } from "../../shared/ui/ConfirmDialog";
import { EmptyState } from "../../shared/ui/EmptyState";
import { ErrorState } from "../../shared/ui/ErrorState";
import { MaterialListSkeleton } from "../../shared/ui/Skeleton";
import { relativeDate } from "../../shared/lib/dates";

/**
 * Files: the teacher's cloud drawer. Uploads are streamed to the server,
 * which stores them under generated names (never client-controlled) and
 * answers downloads only for the owner. Downloads go through the API with
 * the access token, so the browser gets an authenticated Blob we hand to
 * the platform share/save dialog — no unauthenticated static links exist.
 */

const MAX_UPLOAD_BYTES = 20 * 1024 * 1024;

export function FilesPage() {
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState<string | null>(null);
  const [deleting, setDeleting] = useState<ApiFile | null>(null);
  const [listNonce, setListNonce] = useState(0);
  const inputRef = useRef<HTMLInputElement>(null);
  const token = useApiToken();

  async function onPick(file: File) {
    if (token === null) return;
    setNotice(null);
    if (file.size > MAX_UPLOAD_BYTES) {
      setNotice("Файл больше 20 МБ");
      return;
    }
    setBusy(true);
    try {
      await api.uploadFile(token, file);
      setListNonce((n) => n + 1);
    } catch (err) {
      setNotice(userMessage(err));
    } finally {
      setBusy(false);
    }
  }

  async function removeFile() {
    if (deleting === null || token === null) return;
    setBusy(true);
    setNotice(null);
    try {
      await api.deleteFile(token, deleting.id);
      setDeleting(null);
      setListNonce((n) => n + 1);
    } catch (err) {
      setNotice(userMessage(err));
      setBusy(false);
    }
  }

  return (
    <>
      <div className="page-header page-intro">
        <div>
          <p className="eyebrow">ФАЙЛЫ</p>
          <h1>Файлы</h1>
        </div>
        <button
          type="button"
          className="header-create page-create"
          disabled={busy}
          onClick={() => inputRef.current?.click()}
        >
          <span aria-hidden="true">↑</span>
          Загрузить файл
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

      {notice !== null && (
        <p className="form-error" role="alert">
          {notice}
        </p>
      )}

      <FileList listNonce={listNonce} onDelete={(file) => setDeleting(file)} />

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
    </>
  );
}

function userMessage(err: unknown): string {
  if (err instanceof ApiError) {
    if (err.isUnauthorized) return "Сессия истекла. Войдите заново.";
    if (err.serverMessage !== null) return err.serverMessage;
  }
  return "Не удалось выполнить действие. Попробуйте ещё раз.";
}

function FileList(props: {
  listNonce: number;
  onDelete: (file: ApiFile) => void;
}) {
  const token = useApiToken();
  const { handleUnauthorized } = useAuth();
  const { data, error, loading, reload } = useAsync(() => {
    if (token === null) return Promise.reject(new Error("no token"));
    return api.listFiles(token);
  }, [token, props.listNonce]);

  if (loading && !data) return <MaterialListSkeleton />;

  if (error) {
    if (error instanceof ApiError && error.isUnauthorized) {
      handleUnauthorized();
      return null;
    }
    return (
      <ErrorState
        message="Не удалось загрузить файлы. Проверьте соединение и попробуйте ещё раз."
        onRetry={reload}
      />
    );
  }

  if (!data) return null;

  if (data.items.length === 0) {
    return (
      <EmptyState
        icon="folder"
        title="Пока нет загруженных файлов"
      />
    );
  }

  return (
    <div className="material-list">
      {data.items.map((file) => (
        <FileRow key={file.id} file={file} onDelete={() => props.onDelete(file)} />
      ))}
    </div>
  );
}

function FileRow(props: { file: ApiFile; onDelete: () => void }) {
  const token = useApiToken();
  const { handleUnauthorized } = useAuth();
  const [downloading, setDownloading] = useState(false);

  async function download() {
    if (token === null) return;
    setDownloading(true);
    try {
      const blob = await api.downloadFile(token, props.file.id);
      // Same behaviour as <a download>, but with the auth header attached.
      const url = URL.createObjectURL(blob);
      const anchor = document.createElement("a");
      anchor.href = url;
      anchor.download = props.file.original_name;
      anchor.click();
      URL.revokeObjectURL(url);
    } catch (err) {
      if (err instanceof ApiError && err.isUnauthorized) {
        handleUnauthorized();
        return;
      }
      window.alert("Не удалось скачать файл. Попробуйте ещё раз.");
    } finally {
      setDownloading(false);
    }
  }

  return (
    <div className="template-card-row">
      <button
        type="button"
        className="card material-card plan-card"
        disabled={downloading}
        onClick={() => void download()}
        aria-label={`Скачать ${props.file.original_name}`}
      >
        <span className="material-card-title">{props.file.original_name}</span>
        <span className="material-card-meta">
          <span>{formatSize(props.file.size_bytes)}</span>
          <span>{relativeDate(props.file.created_at)}</span>
        </span>
      </button>
      <Button variant="ghost" onClick={props.onDelete}>
        Удалить
      </Button>
    </div>
  );
}

function formatSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} Б`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(0)} КБ`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} МБ`;
}
