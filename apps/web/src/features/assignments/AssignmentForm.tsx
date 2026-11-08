import { useState } from "react";
import {
  api,
  ApiError,
  type ApiAssignment,
  type ApiMaterial,
  type AssignmentInput,
} from "../../shared/api/client";
import { useApiToken, useAuth } from "../../shared/hooks/auth";
import { useAsync } from "../../shared/hooks/useAsync";
import {
  FileStager,
  uploadStagedFiles,
} from "../../shared/ui/AttachedFiles";
import { Button } from "../../shared/ui/Button";
import { TextAreaField, TextField } from "../../shared/ui/Field";
import { navigate } from "../../shared/lib/routes";

interface AssignmentFormProps {
  /** Absent ⇒ create mode. */
  assignment?: ApiAssignment;
  onSaved: (saved: ApiAssignment) => void;
  onCancel: () => void;
}

/**
 * Create/edit form for an assignment: one calm section — class, deadline,
 * description, optional link to the teacher's own material. While the
 * request is in flight the submit is blocked; on failure the typed data
 * stays on screen.
 */
export function AssignmentForm({ assignment, onSaved, onCancel }: AssignmentFormProps) {
  const token = useApiToken();
  const { handleUnauthorized } = useAuth();
  const isEdit = assignment !== undefined;

  const [title, setTitle] = useState(assignment?.title ?? "");
  const [subject, setSubject] = useState(assignment?.subject ?? "");
  const [className, setClassName] = useState(assignment?.class_name ?? "");
  const [dueDate, setDueDate] = useState(
    assignment?.due_at === null || assignment?.due_at === undefined
      ? ""
      : assignment.due_at.slice(0, 10),
  );
  const [dueTime, setDueTime] = useState(
    assignment?.due_at === null || assignment?.due_at === undefined
      ? "23:59"
      : assignment.due_at.slice(11, 16),
  );
  const [description, setDescription] = useState(assignment?.description ?? "");
  const [relatedId, setRelatedId] = useState(assignment?.related_material_id ?? "");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  // Create-mode staging: files upload right after the assignment exists.
  const [stagedFiles, setStagedFiles] = useState<File[]>([]);

  // Materials for the optional link; loading failure must not block the form.
  const materials = useAsync(
    () => (token === null ? Promise.reject(new Error("no token")) : api.listMaterials(token)),
    [token],
  );

  const trimmedTitle = title.trim();

  function buildInput(): AssignmentInput {
    const materialOptions = materials.data?.items ?? [];
    const chosen = materialOptions.find((m) => m.id === relatedId);
    return {
      title: trimmedTitle,
      description,
      subject: subject.trim(),
      class_name: className.trim(),
      due_at:
        dueDate === ""
          ? null
          : `${dueDate}T${dueTime === "" ? "23:59" : dueTime}:00`,
      status: assignment?.status ?? "active",
      // null unlinks; only ids from the owner's own library are ever sent.
      related_material_id: chosen ? chosen.id : null,
    };
  }

  async function save() {
    setBusy(true);
    setError(null);
    const input = buildInput();
    try {
      const saved = isEdit
        ? await api.updateAssignment(token, assignment.id, input)
        : await api.createAssignment(token, input);
      if (!isEdit && stagedFiles.length > 0) {
        await uploadStagedFiles(
          token,
          { kind: "assignment", id: saved.id },
          stagedFiles,
        );
      }
      onSaved(saved);
      navigate(`#/assignments/${saved.id}`);
    } catch (err) {
      if (err instanceof ApiError) {
        if (err.isUnauthorized) {
          handleUnauthorized();
          return;
        }
        setError(
          err.status === 422
            ? "Проверьте поля: название обязательно (до 200 символов), срок — корректные дата и время."
            : (err.serverMessage ?? "Не удалось сохранить задание. Попробуйте ещё раз."),
        );
      } else {
        setError("Не удалось сохранить задание. Попробуйте ещё раз.");
      }
    } finally {
      setBusy(false);
    }
  }

  return (
    <form
      className="plan-form"
      aria-label={isEdit ? "Редактирование задания" : "Новое задание"}
      onSubmit={(e) => {
        e.preventDefault();
        void save();
      }}
    >
      <fieldset className="form-section">
        <legend>Основное</legend>
        <TextField
          label="Название"
          id="assignment-title"
          value={title}
          onChange={(e) => setTitle(e.target.value)}
          placeholder="Например: Задание: упр. 120"
          maxLength={200}
          required
          autoComplete="off"
          aria-describedby={error ? "assignment-form-error" : undefined}
          aria-invalid={error ? true : undefined}
        />
        <div className="field-grid">
          <TextField
            label="Предмет (необязательно)"
            id="assignment-subject"
            value={subject}
            onChange={(e) => setSubject(e.target.value)}
            placeholder="Русский язык"
            maxLength={120}
            autoComplete="off"
          />
          <TextField
            label="Класс (необязательно)"
            id="assignment-class"
            value={className}
            onChange={(e) => setClassName(e.target.value)}
            placeholder="6А"
            maxLength={32}
            autoComplete="off"
          />
          <TextField
            label="Срок — дата (необязательно)"
            id="assignment-due-date"
            type="date"
            value={dueDate}
            onChange={(e) => setDueDate(e.target.value)}
          />
          <TextField
            label="Срок — время"
            id="assignment-due-time"
            type="time"
            value={dueTime}
            onChange={(e) => setDueTime(e.target.value)}
          />
        </div>
        <TextAreaField
          label="Описание (необязательно)"
          id="assignment-description"
          rows={4}
          value={description}
          onChange={(e) => setDescription(e.target.value)}
          placeholder="Что задано, какие страницы, упражнения…"
        />
        <div className="field">
          <label htmlFor="assignment-related">Связать с материалом (необязательно)</label>
          <select
            id="assignment-related"
            value={relatedId}
            onChange={(e) => setRelatedId(e.target.value)}
          >
            <option value="">Без материала</option>
            {(materials.data?.items ?? []).map((material: ApiMaterial) => (
              <option key={material.id} value={material.id}>
                {material.title}
              </option>
            ))}
          </select>
        </div>
      </fieldset>

      {!isEdit && <FileStager files={stagedFiles} onChange={setStagedFiles} />}

      {error && (
        <p className="form-error" id="assignment-form-error" role="alert">
          {error}
        </p>
      )}

      <div className="form-actions">
        <Button type="submit" busy={busy}>
          {isEdit ? "Сохранить задание" : "Создать задание"}
        </Button>
        <Button type="button" variant="ghost" onClick={onCancel}>
          Отмена
        </Button>
      </div>
    </form>
  );
}
