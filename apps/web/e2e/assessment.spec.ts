import { expect, test } from "@playwright/test";

/**
 * Assessment full flow against the real compose stack:
 * open the Safe with a new password → create with questions → save
 * → appears in Safe → reload → persisted → delete leaves no residue.
 *
 * Reading a protected assessment requires the Safe unlock (API 403
 * otherwise), so the password is set first; a unique display name makes
 * that first-run unlock deterministic.
 */
test("assessment: create with questions, protect, appears in Safe", async ({ page }) => {
  const title = `E2E проверочная ${Date.now()}`;
  const teacherName = `E2E Проверочная ${Date.now()}`;

  await page.goto("/");
  await page.getByLabel("Как вас зовут?").fill(teacherName);
  await page.getByRole("button", { name: "Продолжить" }).click();
  await expect(page.getByRole("main", { name: "Основное содержимое" })).toBeVisible();

  // Open the Safe first: protected details are unreadable before that.
  await page.getByRole("button", { name: "Сейф" }).first().click();
  await expect(
    page.getByRole("heading", { name: "Сейф заблокирован" }),
  ).toBeVisible();
  await page.getByLabel("Пароль Сейфа").fill("e2e-prover-2026");
  await page.getByRole("button", { name: "Создать и открыть" }).click();
  await expect(page.getByLabel("Поиск в Сейфе")).toBeVisible();

  // Desktop tab strip has a «Проверочные» tab.
  await page.getByRole("button", { name: "Проверочные" }).first().click();
  await expect(page.getByRole("heading", { name: "Проверочные" })).toBeVisible();

  // Create.
  await page.getByRole("button", { name: "Новая проверочная" }).first().click();
  const form = page.getByRole("form", { name: "Новая проверочная" });
  await expect(form).toBeVisible();

  await page.getByRole("textbox", { name: "Название" }).fill(title);
  await page.getByRole("textbox", { name: "Класс (необязательно)" }).fill("8А");

  // Add a single-choice question with options and a marked key.
  await page.getByRole("button", { name: "＋ Один ответ" }).click();
  await page
    .getByRole("textbox", { name: "Текст вопроса 1" })
    .fill("Столица Франции?");
  await page.getByRole("textbox", { name: "Вариант 1", exact: true }).fill("Лондон");
  await page.getByRole("textbox", { name: "Вариант 2", exact: true }).fill("Париж");
  await page.getByRole("radio", { name: "Вариант 2 правильный" }).check();

  // Protect and save.
  await page.getByRole("checkbox", { name: /Добавить в Сейф/ }).check();
  await page.getByRole("button", { name: "Создать проверочную" }).click();

  const detail = page.locator(".plan-detail");
  await expect(detail).toBeVisible();
  await expect(detail).toContainText(title);
  await expect(detail).toContainText("Столица Франции?");

  // Answer key hidden by default, visible on demand.
  await expect(detail).not.toContainText("Ответ:");
  await page.getByRole("button", { name: "Показать ответы" }).click();
  await expect(detail).toContainText("Ответ: Париж");

  // Reload: really on the server.
  await page.reload();
  await expect(page.locator(".plan-detail")).toContainText(title);

  // It appears in the Safe.
  await page.getByRole("button", { name: "Сейф" }).first().click();
  if (await page.getByRole("button", { name: "Разблокировать" }).count()) {
    await page.getByLabel("Пароль Сейфа").fill("e2e-prover-2026");
    await page.getByRole("button", { name: "Разблокировать" }).click();
  }
  await expect(page.getByRole("button", { name: new RegExp(title) })).toBeVisible();
  await expect(
    page.getByRole("heading", { name: "Проверочные в Сейфе" }),
  ).toBeVisible();

  // Delete to leave no test residue.
  await page.getByRole("button", { name: new RegExp(title) }).click();
  await page.getByRole("button", { name: "Удалить" }).first().click();
  await page.getByRole("button", { name: "Удалить", exact: true }).last().click();
  await expect(page.getByRole("heading", { name: "Проверочные" })).toBeVisible();
  await expect(page.getByRole("button", { name: new RegExp(title) })).toHaveCount(0);
});
