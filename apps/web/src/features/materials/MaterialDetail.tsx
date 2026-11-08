import { useState } from "react";
import {
  api,
  ApiError,
  type ApiMaterial,
} from "../../shared/api/client";
import { AttachedFiles } from "../../shared/ui/AttachedFiles";
import { useApiToken, useAuth } from "../../shared/hooks/auth";
import { useAsync } from "../../shared/hooks/useAsync";
import { Button } from "../../shared/ui/Button";
import { ConfirmDialog } from "../../shared/ui/ConfirmDialog";
import { ErrorState } from "../../shared/ui/ErrorState";
import { Skeleton } from "../../shared/ui/Skeleton";
import { detectPlatform } from "../../platform";
import { splitContentUrls } from "../../shared/lib/links";
import { relativeDate } from "../../shared/lib/dates";
import { navigate } from "../../shared/lib/routes";

/**
 * Material detail — the per-item workspace: read, quick-toggle the Safety
 * Box flag, share into a chat (real platform call), edit, delete.
 */
export function MaterialDetail({ id }: { id: string }) {
  const token = useApiToken();
  const { handleUnauthorized } = useAuth();
  const { data, error, loading, reload } = useAsync(
    () => api.getMaterial(token, id),
    [token, id],
  );
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState<string | null>(null);
  const [confirmOpen, setConfirmOpen] = useState(false);

  if (loading && !data) return <Skeleton lines={4} />;

  if (error) {
    if (error instanceof ApiError && error.isUnauthorized) {
      handleUnauthorized();
      return null;
    }
    if (error instanceof ApiError && error.status === 404) {
      return (
        <ErrorState
          message="Материал не найден. Возможно, он был удалён."
          onRetry={() => navigate("#/materials")}
        />
      );
    }
    if (error instanceof ApiError && error.status === 403) {
      return (
        <ErrorState
          message="Материал в Сейфе: сначала разблокируйте Сейф паролем."
          onRetry={() => navigate("#/safe")}
        />
      );
    }
    return (
      <ErrorState
        message="Не удалось загрузить материал."
        onRetry={reload}
      />
    );
  }

  if (!data) return null;

  async function toggleProtected(material: ApiMaterial) {
    setBusy(true);
    setNotice(null);
    try {
      await api.updateMaterial(token, material.id, {
        is_protected: !material.is_protected,
      });
      reload();
    } catch (err) {
      if (err instanceof ApiError && err.isUnauthorized) handleUnauthorized();
      else setNotice("Не удалось изменить статус. Попробуйте ещё раз.");
    } finally {
      setBusy(false);
    }
  }

  async function share(material: ApiMaterial) {
    const platform = detectPlatform();
    const text = `${material.title}${material.content ? `\n\n${material.content}` : ""}`;
    setNotice(null);
    try {
      const result = await platform.shareText(text);
      if (result === "copied") setNotice("Скопировано — можно вставить в чат.");
    } catch {
      // shareContent unsupported in MAX web client / user cancelled share
      // sheet / clipboard blocked: an inline hint beats a dead button.
      setNotice("Не получилось отправить. Откройте меню материала и скопируйте текст.");
    }
  }

  async function remove() {
    setBusy(true);
    try {
      await api.deleteMaterial(token, data!.id);
      navigate("#/materials");
    } catch (err) {
      if (err instanceof ApiError && err.isUnauthorized) handleUnauthorized();
      else setNotice("Не удалось удалить материал.");
    } finally {
      setBusy(false);
      setConfirmOpen(false);
    }
  }

  return (
    <article className="material-detail">
      <h1 className="detail-title">
        {data.is_protected && <span className="lock-tag">Сейф</span>}
        {data.title}
      </h1>
      <p className="detail-meta">
        {data.subject && <span>{data.subject} · </span>}
        изменён {relativeDate(data.updated_at)}
      </p>

      <div className="detail-content">
        {data.content ? (
          renderContent(data.content)
        ) : (
          <p className="detail-empty">В этом материале пока нет текста.</p>
        )}
      </div>

      {notice && (
        <p className="inline-notice" role="status">
          {notice}
        </p>
      )}

      <AttachedFiles
        target={{ kind: "material", id: data.id }}
        emptyText="К этому материалу файлов пока нет."
      />

      <div className="detail-actions">
        <Button variant="secondary" onClick={() => navigate(`#/materials/${data.id}/edit`)}>
          Редактировать
        </Button>
        <Button variant="secondary" busy={busy} onClick={() => void toggleProtected(data)}>
          {data.is_protected ? "Убрать из Сейфа" : "Добавить в Сейф"}
        </Button>
        <Button variant="ghost" onClick={() => void share(data)}>
          Отправить в чат
        </Button>
        <Button variant="ghost" className="danger-link" onClick={() => setConfirmOpen(true)}>
          Удалить
        </Button>
      </div>

      <ConfirmDialog
        open={confirmOpen}
        title="Удалить материал?"
        description={`«${data.title}» будет удалён без возможности восстановления.`}
        confirmLabel="Удалить"
        busy={busy}
        onConfirm={() => void remove()}
        onCancel={() => setConfirmOpen(false)}
      />
    </article>
  );
}


function renderContent(content: string) {
  return (
    <>
      {splitContentUrls(content).map((part, i) =>
        part.kind === "text" ? (
          <span key={i}>{part.value}</span>
        ) : (
          <a
            key={i}
            href={part.value}
            onClick={(e) => {
              // Routing link opening through the platform adapter is the
              // MAX-correct behaviour (openLink); browsers open a tab.
              e.preventDefault();
              void detectPlatform().openExternalLink(part.value);
            }}
          >
            {part.value}
          </a>
        ),
      )}
    </>
  );
}
