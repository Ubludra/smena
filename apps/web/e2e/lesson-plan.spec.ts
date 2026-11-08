import { expect, test } from "@playwright/test";

/**
 * Lesson plan full flow against the real compose stack:
 * login → plans → create → save → reload → exists → edit → reload → persisted.
 */
test("lesson plan: create, reload, edit, changes persist", async ({ page }) => {
  const title = `E2E план ${Date.now()}`;

  await page.goto("/");
  await page.getByLabel("Как вас зовут?").fill("E2E Учитель");
  await page.getByRole("button", { name: "Продолжить" }).click();
  await expect(page.getByRole("main", { name: "Основное содержимое" })).toBeVisible();

  // Nav: the «Планы» tab exists in the header strip.
  await page.getByRole("button", { name: "Планы" }).first().click();
  await expect(page.getByRole("heading", { name: "Планы уроков" })).toBeVisible();

  // Create.
  await page.getByRole("button", { name: "Новый план" }).first().click();
  const form = page.getByRole("form", { name: "Новый план урока" });
  await expect(form).toBeVisible();

  // Sections exist (не одна огромная форма).
  await expect(page.getByText("Цель и задачи")).toBeVisible();
  await expect(page.getByText("Ход урока")).toBeVisible();

  await page.getByRole("textbox", { name: "Название" }).fill(title);
  await page.getByRole("textbox", { name: "Предмет (необязательно)" }).fill("Математика");
  await page.getByRole("textbox", { name: "Класс (необязательно)" }).fill("7Б");
  await page
    .getByRole("textbox", { name: "Тема (необязательно)" })
    .fill("Сложение дробей");

  // Add one stage with minutes.
  await page.getByRole("button", { name: "＋ Добавить этап" }).click();
  await page.getByRole("textbox", { name: "Этап 1" }).fill("Актуализация");
  await page
    .getByRole("spinbutton", { name: "Минуты этапа 1" })
    .fill("10");

  await page.getByRole("button", { name: "Создать план" }).click();

  // Detail page shows saved content.
  const detail = page.locator(".plan-detail");
  await expect(detail).toBeVisible();
  await expect(detail).toContainText(title);
  await expect(detail).toContainText("Ход урока");
  await expect(detail).toContainText("Актуализация — 10 мин");

  // Reload: the plan is really on the server, not just in client state.
  await page.reload();
  await expect(page.locator(".plan-detail")).toContainText(title);

  // Edit.
  await page.getByRole("button", { name: "Редактировать" }).click();
  const editForm = page.getByRole("form", { name: "Редактирование плана урока" });
  await expect(editForm).toBeVisible();
  await expect(page.getByRole("textbox", { name: "Название" })).toHaveValue(title);
  await page.getByRole("textbox", { name: "Тема (необязательно)" }).fill("Вычитание дробей");
  await page.getByRole("button", { name: "Сохранить план" }).click();

  await expect(page.locator(".plan-detail")).toContainText("Вычитание дробей");

  // Reload again: edit persisted.
  await page.reload();
  await expect(page.locator(".plan-detail")).toContainText("Вычитание дробей");

  // List shows the plan; delete it to leave no test residue.
  await page.getByRole("button", { name: "Планы" }).first().click();
  await expect(page.getByRole("button", { name: new RegExp(title) })).toBeVisible();

  await page.getByRole("button", { name: new RegExp(title) }).click();
  await page.getByRole("button", { name: "Удалить" }).first().click();
  await page.getByRole("button", { name: "Удалить", exact: true }).last().click();
  await expect(page.getByRole("heading", { name: "Планы уроков" })).toBeVisible();
  await expect(page.getByRole("button", { name: new RegExp(title) })).toHaveCount(0);
});
