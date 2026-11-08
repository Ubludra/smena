import { useState } from "react";
import { api, ApiError, type ApiMaterial, type MaterialInput } from "../../shared/api/client";
import { useApiToken, useAuth } from "../../shared/hooks/auth";
import { Button } from "../../shared/ui/Button";
import {
  FileStager,
  uploadStagedFiles,
} from "../../shared/ui/AttachedFiles";
import { TextAreaField, TextField } from "../../shared/ui/Field";
import { navigate } from "../../shared/lib/routes";

interface MaterialFormProps {
  /** Absent ⇒ create mode. */
  material?: ApiMaterial;
  /**
   * Template payload (the MaterialCreate shape the server guarantees for
   * report templates) used to prefill create mode. Ignored in edit mode.
   */
  preset?: Record<string, unknown>;
  /** Called after a successful save (parent refreshes its lists). */
  onSaved: (saved: ApiMaterial) => void;
}

function presetStr(preset: Record<string, unknown> | undefined, key: string): string {
  const value = preset?.[key];
  return typeof value === "string" ? value : "";
}

function presetBool(preset: Record<string, unknown> | undefined, key: string): boolean {
  const value = preset?.[key];
  return typeof value === "boolean" ? value : false;
}

/**
 * Create/edit form. One primary action («Сохранить»), busy-state while the
 * request is in flight; on failure the user stays on the form with a
 * readable message and the typed text is NOT lost (§30/§31).
 */
export function MaterialForm({ material, preset, onSaved }: MaterialFormProps) {
  const token = useApiToken();
  const { handleUnauthorized } = useAuth();
  const isEdit = material !== undefined;

  const [title, setTitle] = useState(
    material?.title ?? presetStr(preset, "title"),
  );
  const [subject, setSubject] = useState(
    material?.subject ?? presetStr(preset, "subject"),
  );
  const [content, setContent] = useState(
    material?.content ?? presetStr(preset, "content"),
  );
  const [isProtected, setIsProtected] = useState(
    material?.is_protected ?? presetBool(preset, "is_protected"),
  );
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  // Create-mode staging: files upload right after the material exists.
  const [stagedFiles, setStagedFiles] = useState<File[]>([]);

  const trimmedTitle = title.trim();

  async function save() {
    setBusy(true);
    setError(null);
    const input: MaterialInput = {
      title: trimmedTitle,
      subject: subject.trim(),
      content,
      is_protected: isProtected,
    };
    try {
      const saved = isEdit
        ? await api.updateMaterial(token, material.id, input)
        : await api.createMaterial(token, input);
      // Staged files upload right after creation; per-file failures are
      // visible on the detail page (the file list shows what landed) —
      // uploadStagedFiles itself never throws.
      if (!isEdit && stagedFiles.length > 0) {
        await uploadStagedFiles(
          token,
          { kind: "material", id: saved.id },
          stagedFiles,
        );
      }
      onSaved(saved);
      navigate(`#/materials/${saved.id}`);
    } catch (err) {
      if (err instanceof ApiError) {
        if (err.isUnauthorized) {
          handleUnauthorized();
          return;
        }
        setError(
          err.status === 422
            ? "Проверьте поля: название обязательно и не длиннее 200 символов."
            : (err.serverMessage ?? "Не удалось сохранить материал. Попробуйте ещё раз."),
        );
      } else {
        setError("Не удалось сохранить материал. Попробуйте ещё раз.");
      }
    } finally {
      setBusy(false);
    }
  }

  return (
    <form
      className="material-form"
      aria-label={isEdit ? "Редактирование материала" : "Новый материал"}
      onSubmit={(e) => {
        e.preventDefault();
        void save();
      }}
    >
      <div className="material-editor-main">
        <TextField
          label="Название"
          id="material-title"
          value={title}
          onChange={(e) => setTitle(e.target.value)}
          placeholder="Например: Карточки по падежам"
          maxLength={200}
          required
          autoComplete="off"
          aria-describedby={error ? "material-form-error" : undefined}
          aria-invalid={error ? true : undefined}
        />
        <TextField
          label="Предмет (необязательно)"
          id="material-subject"
          value={subject}
          onChange={(e) => setSubject(e.target.value)}
          placeholder="Например: Русский язык"
          maxLength={120}
          autoComplete="off"
        />
        <TextAreaField
          label="Содержание (необязательно)"
          id="material-content"
          value={content}
          onChange={(e) => setContent(e.target.value)}
          rows={12}
          placeholder="Конспект, план, текст задания…"
        />
        {!isEdit && <FileStager files={stagedFiles} onChange={setStagedFiles} />}
      </div>

      <aside className="material-editor-side" aria-label="Параметры хранения">
        <p className="eyebrow">ХРАНИЛИЩЕ</p>
        <h2>Доступ и хранение</h2>
        <label className="checkbox-row">
          <input
            type="checkbox"
            checked={isProtected}
            onChange={(e) => setIsProtected(e.target.checked)}
          />
          <span>
            <strong>Добавить в Сейф</strong>
            <small>Материал будет показан в вашем разделе «Сейф».</small>
          </span>
        </label>
        <p className="editor-note">
          Доступ к материалам Сейфа проверяется сервером для вашей учётной
          записи.
        </p>
      </aside>

      {error && (
        <p className="form-error" id="material-form-error" role="alert">
          {error}
        </p>
      )}

      <div className="form-actions">
        <Button type="submit" busy={busy} disabled={trimmedTitle.length === 0}>
          {isEdit ? "Сохранить изменения" : "Сохранить материал"}
        </Button>
        <Button
          type="button"
          variant="ghost"
          onClick={() => window.history.back()}
          disabled={busy}
        >
          Отмена
        </Button>
      </div>
    </form>
  );
}
