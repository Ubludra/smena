import { useState } from "react";
import {
  api,
  ApiError,
  type ApiLessonPlan,
  type ApiStage,
  type LessonPlanInput,
} from "../../shared/api/client";
import { useApiToken, useAuth } from "../../shared/hooks/auth";
import {
  FileStager,
  uploadStagedFiles,
} from "../../shared/ui/AttachedFiles";
import { Button } from "../../shared/ui/Button";
import { TextAreaField, TextField } from "../../shared/ui/Field";
import { navigate } from "../../shared/lib/routes";

interface PlanFormProps {
  /** Absent ⇒ create mode. */
  plan?: ApiLessonPlan;
  /** Template payload for create mode: pre-fills the empty form. */
  preset?: Record<string, unknown>;
  onSaved: (saved: ApiLessonPlan) => void;
  onCancel: () => void;
}

/** One step of «Ход урока»; minutes may stay empty (преподаватель решает). */
interface StageDraft {
  title: string;
  minutes: string;
  description: string;
}

function toDrafts(stages: ApiStage[]): StageDraft[] {
  return stages.map((s) => ({
    title: s.title,
    minutes: s.minutes === null ? "" : String(s.minutes),
    description: s.description,
  }));
}

function parseMinutes(raw: string): number | null {
  const trimmed = raw.trim();
  if (trimmed === "") return null;
  const value = Number(trimmed);
  return Number.isInteger(value) && value > 0 ? value : NaN;
}

// Template-payload accessors: the payload was server-validated, but the UI
// still reads it defensively (template may predate a schema change).
function str(preset: Record<string, unknown> | undefined, key: string): string {
  const value = preset?.[key];
  return typeof value === "string" ? value : "";
}

function strList(
  preset: Record<string, unknown> | undefined,
  key: string,
): string[] {
  const value = preset?.[key];
  return Array.isArray(value) ? value.filter((v): v is string => typeof v === "string") : [];
}

function stagesFromPreset(
  preset: Record<string, unknown> | undefined,
): StageDraft[] {
  const value = preset?.stages;
  if (!Array.isArray(value)) return [];
  return value.flatMap((stage) => {
    if (typeof stage !== "object" || stage === null) return [];
    const record = stage as Record<string, unknown>;
    const minutes = record.minutes;
    return [
      {
        title: typeof record.title === "string" ? record.title : "",
        minutes: minutes === null || minutes === undefined ? "" : String(minutes),
        description: typeof record.description === "string" ? record.description : "",
      },
    ];
  });
}

/**
 * Create/edit form for a lesson plan, split into logical sections per the
 * product spec («Основное → Цель и задачи → Ход урока → ДЗ → Заметки») —
 * never one huge screen. While a request is in flight the submit is blocked,
 * and on failure everything the teacher typed stays on screen (§14/§15).
 */
export function PlanForm({ plan, preset, onSaved, onCancel }: PlanFormProps) {
  const token = useApiToken();
  const { handleUnauthorized } = useAuth();
  const isEdit = plan !== undefined;

  const [title, setTitle] = useState(plan?.title ?? str(preset, "title"));
  const [subject, setSubject] = useState(plan?.subject ?? str(preset, "subject"));
  const [className, setClassName] = useState(
    plan?.class_name ?? str(preset, "class_name"),
  );
  const [lessonDate, setLessonDate] = useState(plan?.lesson_date ?? "");
  const [startTime, setStartTime] = useState(plan?.start_time?.slice(0, 5) ?? "");
  const [duration, setDuration] = useState(() => {
    if (plan?.duration_minutes !== null && plan?.duration_minutes !== undefined) {
      return String(plan.duration_minutes);
    }
    const presetValue = preset?.duration_minutes;
    return presetValue === null || presetValue === undefined
      ? ""
      : String(presetValue);
  });
  const [topic, setTopic] = useState(plan?.topic ?? str(preset, "topic"));
  const [goal, setGoal] = useState(plan?.goal ?? str(preset, "goal"));
  const [objectives, setObjectives] = useState<string[]>(
    plan?.objectives ?? strList(preset, "objectives"),
  );
  const [stages, setStages] = useState<StageDraft[]>(
    plan ? toDrafts(plan.stages) : stagesFromPreset(preset),
  );
  const [homework, setHomework] = useState(plan?.homework ?? str(preset, "homework"));
  const [notes, setNotes] = useState(plan?.notes ?? str(preset, "notes"));
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  // Create-mode staging: files upload right after the plan exists.
  const [stagedFiles, setStagedFiles] = useState<File[]>([]);

  const trimmedTitle = title.trim();

  function addObjective() {
    setObjectives((list) => [...list, ""]);
  }

  function updateObjective(index: number, value: string) {
    setObjectives((list) => list.map((o, i) => (i === index ? value : o)));
  }

  function removeObjective(index: number) {
    setObjectives((list) => list.filter((_, i) => i !== index));
  }

  function addStage() {
    setStages((list) => [...list, { title: "", minutes: "", description: "" }]);
  }

  function updateStage(index: number, patch: Partial<StageDraft>) {
    setStages((list) => list.map((s, i) => (i === index ? { ...s, ...patch } : s)));
  }

  function removeStage(index: number) {
    setStages((list) => list.filter((_, i) => i !== index));
  }

  function buildInput(): LessonPlanInput | null {
    const parsedStages = stages.map((s) => ({
      title: s.title.trim(),
      minutes: parseMinutes(s.minutes),
      description: s.description,
    }));
    if (parsedStages.some((s) => Number.isNaN(s.minutes))) return null;
    const parsedDuration = parseMinutes(duration);
    if (Number.isNaN(parsedDuration)) return null;
    return {
      title: trimmedTitle,
      subject: subject.trim(),
      class_name: className.trim(),
      lesson_date: lessonDate === "" ? null : lessonDate,
      start_time: startTime === "" ? null : `${startTime}:00`,
      duration_minutes: parsedDuration,
      topic: topic.trim(),
      goal,
      // Drop objectives the teacher left empty instead of sending blanks.
      objectives: objectives.map((o) => o.trim()).filter((o) => o !== ""),
      stages: parsedStages,
      homework,
      notes,
    };
  }

  async function save() {
    const input = buildInput();
    if (input === null) {
      setError("Этапы и длительность: укажите целое число минут больше нуля.");
      return;
    }
    setBusy(true);
    setError(null);
    try {
      const saved = isEdit
        ? await api.updateLessonPlan(token, plan.id, input)
        : await api.createLessonPlan(token, input);
      if (!isEdit && stagedFiles.length > 0) {
        await uploadStagedFiles(
          token,
          { kind: "lesson_plan", id: saved.id },
          stagedFiles,
        );
      }
      onSaved(saved);
      navigate(`#/plans/${saved.id}`);
    } catch (err) {
      if (err instanceof ApiError) {
        if (err.isUnauthorized) {
          handleUnauthorized();
          return;
        }
        setError(
          err.status === 422
            ? "Проверьте поля: название обязательно (до 200 символов), длительность — от 1 до 600 минут."
            : (err.serverMessage ?? "Не удалось сохранить план урока. Попробуйте ещё раз."),
        );
      } else {
        setError("Не удалось сохранить план урока. Попробуйте ещё раз.");
      }
    } finally {
      setBusy(false);
    }
  }

  return (
    <form
      className="plan-form"
      aria-label={isEdit ? "Редактирование плана урока" : "Новый план урока"}
      onSubmit={(e) => {
        e.preventDefault();
        void save();
      }}
    >
      <fieldset className="form-section">
        <legend>Основное</legend>
        <TextField
          label="Название"
          id="plan-title"
          value={title}
          onChange={(e) => setTitle(e.target.value)}
          placeholder="Например: Урок: дроби"
          maxLength={200}
          required
          autoComplete="off"
          aria-describedby={error ? "plan-form-error" : undefined}
          aria-invalid={error ? true : undefined}
        />
        <div className="field-grid">
          <TextField
            label="Предмет (необязательно)"
            id="plan-subject"
            value={subject}
            onChange={(e) => setSubject(e.target.value)}
            placeholder="Математика"
            maxLength={120}
            autoComplete="off"
          />
          <TextField
            label="Класс (необязательно)"
            id="plan-class"
            value={className}
            onChange={(e) => setClassName(e.target.value)}
            placeholder="7Б"
            maxLength={32}
            autoComplete="off"
          />
          <TextField
            label="Дата урока (необязательно)"
            id="plan-date"
            type="date"
            value={lessonDate}
            onChange={(e) => setLessonDate(e.target.value)}
          />
          <TextField
            label="Начало (необязательно)"
            id="plan-start"
            type="time"
            value={startTime}
            onChange={(e) => setStartTime(e.target.value)}
          />
          <TextField
            label="Длительность, мин (необязательно)"
            id="plan-duration"
            type="number"
            min={1}
            max={600}
            value={duration}
            onChange={(e) => setDuration(e.target.value)}
            placeholder="45"
          />
        </div>
        <TextField
          label="Тема (необязательно)"
          id="plan-topic"
          value={topic}
          onChange={(e) => setTopic(e.target.value)}
          placeholder="Сложение дробей с разными знаменателями"
          maxLength={200}
          autoComplete="off"
        />
      </fieldset>

      <fieldset className="form-section">
        <legend>Цель и задачи</legend>
        <TextAreaField
          label="Цель урока (необязательно)"
          id="plan-goal"
          rows={2}
          value={goal}
          onChange={(e) => setGoal(e.target.value)}
          placeholder="Чего должны достичь ученики за этот урок?"
        />
        <div className="repeat-list" aria-label="Задачи урока">
          <p className="repeat-list-title">Задачи (необязательно)</p>
          {objectives.map((objective, index) => (
            <div className="repeat-row" key={index}>
              <TextField
                label={`Задача ${index + 1}`}
                id={`plan-objective-${index}`}
                value={objective}
                onChange={(e) => updateObjective(index, e.target.value)}
                maxLength={500}
                autoComplete="off"
              />
              <button
                type="button"
                className="repeat-remove"
                onClick={() => removeObjective(index)}
                aria-label={`Удалить задачу ${index + 1}`}
              >
                ✕
              </button>
            </div>
          ))}
          <button type="button" className="repeat-add" onClick={addObjective}>
            ＋ Добавить задачу
          </button>
        </div>
      </fieldset>

      <fieldset className="form-section">
        <legend>Ход урока</legend>
        <div className="repeat-list" aria-label="Этапы урока">
          {stages.map((stage, index) => (
            <div className="stage-row" key={index}>
              <div className="stage-row-head">
                <span className="stage-number" aria-hidden="true">
                  {index + 1}
                </span>
                <TextField
                  label={`Этап ${index + 1}`}
                  id={`plan-stage-${index}`}
                  value={stage.title}
                  onChange={(e) => updateStage(index, { title: e.target.value })}
                  placeholder="Название этапа"
                  maxLength={200}
                  autoComplete="off"
                />
                <TextField
                  label={`Минуты этапа ${index + 1}`}
                  id={`plan-stage-minutes-${index}`}
                  type="number"
                  min={1}
                  max={240}
                  value={stage.minutes}
                  onChange={(e) => updateStage(index, { minutes: e.target.value })}
                  placeholder="мин"
                />
                <button
                  type="button"
                  className="repeat-remove"
                  onClick={() => removeStage(index)}
                  aria-label={`Удалить этап ${index + 1}`}
                >
                  ✕
                </button>
              </div>
              <TextAreaField
                label={`Описание этапа ${index + 1}`}
                id={`plan-stage-description-${index}`}
                rows={2}
                value={stage.description}
                onChange={(e) => updateStage(index, { description: e.target.value })}
                placeholder="Что происходит на этом этапе?"
              />
            </div>
          ))}
          <button type="button" className="repeat-add" onClick={addStage}>
            ＋ Добавить этап
          </button>
        </div>
      </fieldset>

      <fieldset className="form-section">
        <legend>Домашнее задание</legend>
        <TextAreaField
          label="Домашнее задание (необязательно)"
          id="plan-homework"
          rows={2}
          value={homework}
          onChange={(e) => setHomework(e.target.value)}
          placeholder="Например: упр. 120, задачи 5–8"
        />
      </fieldset>

      <fieldset className="form-section">
        <legend>Заметки</legend>
        <TextAreaField
          label="Заметки (необязательно)"
          id="plan-notes"
          rows={2}
          value={notes}
          onChange={(e) => setNotes(e.target.value)}
          placeholder="Оборудование, напоминания…"
        />
      </fieldset>

      {!isEdit && <FileStager files={stagedFiles} onChange={setStagedFiles} />}

      {error && (
        <p className="form-error" id="plan-form-error" role="alert">
          {error}
        </p>
      )}

      <div className="form-actions">
        <Button type="submit" busy={busy}>
          {isEdit ? "Сохранить план" : "Создать план"}
        </Button>
        <Button type="button" variant="ghost" onClick={onCancel}>
          Отмена
        </Button>
      </div>
    </form>
  );
}
