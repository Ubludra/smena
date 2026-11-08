import { useState } from "react";
import {
  api,
  ApiError,
  type ApiAssessment,
  type AssessmentInput,
  type QuestionInput,
  type QuestionType,
} from "../../shared/api/client";
import { useApiToken, useAuth } from "../../shared/hooks/auth";
import {
  FileStager,
  uploadStagedFiles,
} from "../../shared/ui/AttachedFiles";
import { Button } from "../../shared/ui/Button";
import { TextAreaField, TextField } from "../../shared/ui/Field";
import { navigate } from "../../shared/lib/routes";

interface AssessmentFormProps {
  /** Absent ⇒ create mode. */
  assessment?: ApiAssessment;
  onSaved: (saved: ApiAssessment) => void;
  onCancel: () => void;
}

const TYPE_LABELS: Record<QuestionType, string> = {
  single: "Один ответ",
  multi: "Несколько ответов",
  text: "Короткий текст",
};

/** One question under edit: options as text fields, key as checkboxes. */
interface QuestionDraft {
  text: string;
  type: QuestionType;
  options: string[];
  correct: (string | number)[];
}

function toDrafts(assessment: ApiAssessment): QuestionDraft[] {
  return assessment.questions.map((question) => ({
    text: question.text,
    type: question.type,
    options: question.options.map(String),
    correct: [...question.correct],
  }));
}

/**
 * Create/edit form for an assessment. Questions are edited one by one:
 * add a question, pick its type, enter options, mark correct answers.
 * While saving, the submit is blocked; typed content stays on failure.
 */
export function AssessmentForm({ assessment, onSaved, onCancel }: AssessmentFormProps) {
  const token = useApiToken();
  const { handleUnauthorized } = useAuth();
  const isEdit = assessment !== undefined;

  const [title, setTitle] = useState(assessment?.title ?? "");
  const [subject, setSubject] = useState(assessment?.subject ?? "");
  const [className, setClassName] = useState(assessment?.class_name ?? "");
  const [duration, setDuration] = useState(
    assessment?.duration_minutes === null || assessment?.duration_minutes === undefined
      ? ""
      : String(assessment.duration_minutes),
  );
  const [isProtected, setIsProtected] = useState(assessment?.is_protected ?? false);
  const [description, setDescription] = useState(assessment?.description ?? "");
  const [questions, setQuestions] = useState<QuestionDraft[]>(
    assessment ? toDrafts(assessment) : [],
  );
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  // Create-mode staging: files upload right after the assessment exists.
  const [stagedFiles, setStagedFiles] = useState<File[]>([]);

  function updateQuestion(index: number, patch: Partial<QuestionDraft>) {
    setQuestions((list) => list.map((q, i) => (i === index ? { ...q, ...patch } : q)));
  }

  function addQuestion(type: QuestionType) {
    setQuestions((list) => [
      ...list,
      type === "text"
        ? { text: "", type, options: [], correct: [""] }
        : { text: "", type, options: ["", ""], correct: type === "single" ? [0] : [] },
    ]);
  }

  function removeQuestion(index: number) {
    setQuestions((list) => list.filter((_, i) => i !== index));
  }

  function toggleOptionKey(questionIndex: number, optionIndex: number) {
    const question = questions[questionIndex];
    if (question.type === "single") {
      updateQuestion(questionIndex, { correct: [optionIndex] });
      return;
    }
    const current = question.correct as number[];
    const next = current.includes(optionIndex)
      ? current.filter((k) => k !== optionIndex)
      : [...current, optionIndex].sort((a, b) => a - b);
    updateQuestion(questionIndex, { correct: next });
  }

  function buildInput(): AssessmentInput | null {
    const parsedDuration = duration.trim() === "" ? null : Number(duration);
    if (parsedDuration !== null && (!Number.isInteger(parsedDuration) || parsedDuration < 1)) {
      return null;
    }
    const parsedQuestions: QuestionInput[] = questions.map((question) => {
      const options =
        question.type === "text"
          ? []
          : question.options.map((option) => option.trim());
      if (question.type === "text") {
        return {
          text: question.text.trim(),
          type: question.type,
          options,
          // Only non-empty key strings are sent.
          correct: (question.correct as string[])
            .map((k) => k.trim())
            .filter((k) => k !== ""),
        };
      }
      return {
        text: question.text.trim(),
        type: question.type,
        options,
        correct: (question.correct as number[]).filter((k) => k < options.length),
      };
    });
    return {
      title: title.trim(),
      description,
      subject: subject.trim(),
      class_name: className.trim(),
      scheduled_at: null,
      duration_minutes: parsedDuration,
      is_protected: isProtected,
      questions: parsedQuestions,
    };
  }

  async function save() {
    const input = buildInput();
    if (input === null) {
      setError("Длительность: укажите целое число минут от 1 до 600.");
      return;
    }
    setBusy(true);
    setError(null);
    try {
      const saved = isEdit
        ? await api.updateAssessment(token, assessment.id, input)
        : await api.createAssessment(token, input);
      if (!isEdit && stagedFiles.length > 0) {
        await uploadStagedFiles(
          token,
          { kind: "assessment", id: saved.id },
          stagedFiles,
        );
      }
      onSaved(saved);
      navigate(`#/assessments/${saved.id}`);
    } catch (err) {
      if (err instanceof ApiError) {
        if (err.isUnauthorized) {
          handleUnauthorized();
          return;
        }
        setError(
          err.status === 422
            ? "Проверьте вопросы: у выбора — минимум 2 варианта и отмеченный правильный, у текста — эталон ответа."
            : (err.serverMessage ?? "Не удалось сохранить проверочную. Попробуйте ещё раз."),
        );
      } else {
        setError("Не удалось сохранить проверочную. Попробуйте ещё раз.");
      }
    } finally {
      setBusy(false);
    }
  }

  return (
    <form
      className="plan-form"
      aria-label={isEdit ? "Редактирование проверочной" : "Новая проверочная"}
      onSubmit={(e) => {
        e.preventDefault();
        void save();
      }}
    >
      <fieldset className="form-section">
        <legend>Основное</legend>
        <TextField
          label="Название"
          id="assessment-title"
          value={title}
          onChange={(e) => setTitle(e.target.value)}
          placeholder="Например: Контрольная по истории, 8А"
          maxLength={200}
          required
          autoComplete="off"
          aria-describedby={error ? "assessment-form-error" : undefined}
          aria-invalid={error ? true : undefined}
        />
        <div className="field-grid">
          <TextField
            label="Предмет (необязательно)"
            id="assessment-subject"
            value={subject}
            onChange={(e) => setSubject(e.target.value)}
            placeholder="История"
            maxLength={120}
            autoComplete="off"
          />
          <TextField
            label="Класс (необязательно)"
            id="assessment-class"
            value={className}
            onChange={(e) => setClassName(e.target.value)}
            placeholder="8А"
            maxLength={32}
            autoComplete="off"
          />
          <TextField
            label="Длительность, мин (необязательно)"
            id="assessment-duration"
            type="number"
            min={1}
            max={600}
            value={duration}
            onChange={(e) => setDuration(e.target.value)}
            placeholder="45"
          />
        </div>
        <TextAreaField
          label="Описание (необязательно)"
          id="assessment-description"
          rows={2}
          value={description}
          onChange={(e) => setDescription(e.target.value)}
          placeholder="Тема, структура работы…"
        />
        <label className="checkbox-row">
          <input
            type="checkbox"
            checked={isProtected}
            onChange={(e) => setIsProtected(e.target.checked)}
          />
          <span>
            <strong>Добавить в Сейф</strong>
            <small>Проверочная будет показана в вашем разделе «Сейф».</small>
          </span>
        </label>
      </fieldset>

      <fieldset className="form-section">
        <legend>Вопросы</legend>
        <div className="repeat-list" aria-label="Вопросы проверочной">
          {questions.map((question, index) => (
            <div className="question-editor" key={index}>
              <div className="question-editor-head">
                <span className="stage-number" aria-hidden="true">
                  {index + 1}
                </span>
                <div className="field">
                  <label htmlFor={`question-type-${index}`}>Тип вопроса {index + 1}</label>
                  <select
                    id={`question-type-${index}`}
                    value={question.type}
                    onChange={(e) =>
                      updateQuestion(index, {
                        type: e.target.value as QuestionType,
                        options: e.target.value === "text" ? [] : ["", ""],
                        correct: e.target.value === "single" ? [0] : [],
                      })
                    }
                  >
                    {(Object.keys(TYPE_LABELS) as QuestionType[]).map((type) => (
                      <option key={type} value={type}>
                        {TYPE_LABELS[type]}
                      </option>
                    ))}
                  </select>
                </div>
                <button
                  type="button"
                  className="repeat-remove"
                  onClick={() => removeQuestion(index)}
                  aria-label={`Удалить вопрос ${index + 1}`}
                >
                  ✕
                </button>
              </div>

              <TextAreaField
                label={`Текст вопроса ${index + 1}`}
                id={`question-text-${index}`}
                rows={2}
                value={question.text}
                onChange={(e) => updateQuestion(index, { text: e.target.value })}
                placeholder="Сформулируйте вопрос"
              />

              {question.type !== "text" && (
                <div className="option-list">
                  {question.options.map((option, optionIndex) => (
                    <div className="option-row" key={optionIndex}>
                      <label className="option-key">
                        <input
                          type={question.type === "single" ? "radio" : "checkbox"}
                          name={`question-key-${index}`}
                          checked={(question.correct as number[]).includes(optionIndex)}
                          onChange={() => toggleOptionKey(index, optionIndex)}
                          aria-label={`Вариант ${optionIndex + 1} правильный`}
                        />
                      </label>
                      <TextField
                        label={`Вариант ${optionIndex + 1}`}
                        id={`question-option-${index}-${optionIndex}`}
                        value={option}
                        onChange={(e) =>
                          updateQuestion(index, {
                            options: question.options.map((o, i) =>
                              i === optionIndex ? e.target.value : o,
                            ),
                          })
                        }
                        maxLength={300}
                        autoComplete="off"
                      />
                      {question.options.length > 2 && (
                        <button
                          type="button"
                          className="repeat-remove"
                          onClick={() =>
                            updateQuestion(index, {
                              options: question.options.filter((_, i) => i !== optionIndex),
                              correct: (question.correct as number[])
                                .filter((k) => k !== optionIndex)
                                .map((k) => (k > optionIndex ? k - 1 : k)),
                            })
                          }
                          aria-label={`Удалить вариант ${optionIndex + 1}`}
                        >
                          ✕
                        </button>
                      )}
                    </div>
                  ))}
                  {question.options.length < 10 && (
                    <button
                      type="button"
                      className="repeat-add"
                      onClick={() =>
                        updateQuestion(index, {
                          options: [...question.options, ""],
                        })
                      }
                    >
                      ＋ Вариант
                    </button>
                  )}
                </div>
              )}

              {question.type === "text" && (
                <TextField
                  label={`Эталон ответа ${index + 1}`}
                  id={`question-correct-${index}`}
                  value={String(question.correct[0] ?? "")}
                  onChange={(e) => updateQuestion(index, { correct: [e.target.value] })}
                  placeholder="Ожидаемый ответ (сравнение без учёта регистра)"
                  maxLength={300}
                  autoComplete="off"
                />
              )}
            </div>
          ))}

          <div className="question-add-row">
            <button type="button" className="repeat-add" onClick={() => addQuestion("single")}>
              ＋ Один ответ
            </button>
            <button type="button" className="repeat-add" onClick={() => addQuestion("multi")}>
              ＋ Несколько ответов
            </button>
            <button type="button" className="repeat-add" onClick={() => addQuestion("text")}>
              ＋ Текстовый
            </button>
          </div>
        </div>
      </fieldset>

      {!isEdit && <FileStager files={stagedFiles} onChange={setStagedFiles} />}

      {error && (
        <p className="form-error" id="assessment-form-error" role="alert">
          {error}
        </p>
      )}

      <div className="form-actions">
        <Button type="submit" busy={busy}>
          {isEdit ? "Сохранить проверочную" : "Создать проверочную"}
        </Button>
        <Button type="button" variant="ghost" onClick={onCancel}>
          Отмена
        </Button>
      </div>
    </form>
  );
}
