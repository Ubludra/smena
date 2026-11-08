import { expect, test } from "@playwright/test";

/**
 * Assignment full flow against the real compose stack:
 * create with a due date → dashboard visibility is a later step, here:
 * create → reload → mark done → reload → persisted → delete.
 */
test("assignment: create with due date, mark done, persists, delete", async ({ page }) => {
  const title = `E2E задание ${Date.now()}`;

  await page.goto("/");
  await page.getByLabel("Как вас зовут?").fill("E2E Учитель");
  await page.getByRole("button", { name: "Продолжить" }).click();
  await expect(page.getByRole("main", { name: "Основное содержимое" })).toBeVisible();

  await page.getByRole("button", { name: "Задания" }).first().click();
  await expect(page.getByRole("heading", { name: "Задания" })).toBeVisible();

  // Create.
  await page.getByRole("button", { name: "Новое задание" }).first().click();
  const form = page.getByRole("form", { name: "Новое задание" });
  await expect(form).toBeVisible();

  await page.getByRole("textbox", { name: "Название" }).fill(title);
  await page.getByRole("textbox", { name: "Класс (необязательно)" }).fill("8А");
  await page
    .getByLabel("Срок — дата (необязательно)")
    .fill("2026-11-10");
  await page
    .getByRole("textbox", { name: "Описание (необязательно)" })
    .fill("Параграф 7, задачи 1–5");
  await page.getByRole("button", { name: "Создать задание" }).click();

  // Detail shows saved content and the active badge.
  const detail = page.locator(".plan-detail");
  await expect(detail).toBeVisible();
  await expect(detail).toContainText(title);
  await expect(detail).toContainText("Активно");
  await expect(detail).toContainText("Параграф 7");

  // Reload: really on the server.
  await page.reload();
  await expect(page.locator(".plan-detail")).toContainText(title);

  // Mark done.
  await page.getByRole("button", { name: "Отметить выполненным" }).click();
  await expect(page.locator(".plan-detail").getByText("Готово")).toBeVisible();

  // Reload: status persisted.
  await page.reload();
  await expect(page.locator(".plan-detail").getByText("Готово")).toBeVisible();

  // List shows it under the «Готовые» chip filter.
  await page.getByRole("button", { name: "Задания" }).first().click();
  await page.getByRole("button", { name: "Готовые" }).click();
  await expect(page.getByRole("button", { name: new RegExp(title) })).toBeVisible();

  // Delete to leave no test residue.
  await page.getByRole("button", { name: new RegExp(title) }).click();
  await page.getByRole("button", { name: "Удалить" }).first().click();
  await page.getByRole("button", { name: "Удалить", exact: true }).last().click();
  await expect(page.getByRole("heading", { name: "Задания" })).toBeVisible();
  await expect(page.getByRole("button", { name: new RegExp(title) })).toHaveCount(0);
});
