import { expect, test } from "@playwright/test";

/**
 * Calendar flow: create a plan dated today → open Ещё → Календарь → the
 * event appears in the day's cell → clicking it opens the plan detail.
 *
 * Cell lookup uses the gridcell's accessible name ("25 октября 2026"),
 * not text matching: Playwright's hasText matches raw textContent, where
 * the day number and event titles are glued together ("25E2E урок…"),
 * which breaks word-boundary regexes.
 */
test("calendar: dated plan appears on the grid and opens its detail", async ({ page }) => {
  const title = `E2E урок ${Date.now()}`;
  const now = new Date();
  const day = now.getDate();
  const GENITIVE = [
    "января", "февраля", "марта", "апреля", "мая", "июня",
    "июля", "августа", "сентября", "октября", "ноября", "декабря",
  ];
  const cellName = `${day} ${GENITIVE[now.getMonth()]} ${now.getFullYear()}`;

  await page.goto("/");
  await page.getByLabel("Как вас зовут?").fill("E2E Учитель");
  await page.getByRole("button", { name: "Продолжить" }).click();
  await expect(page.getByRole("main", { name: "Основное содержимое" })).toBeVisible();

  // Create a plan dated today (lands in the default calendar month).
  await page.getByRole("button", { name: "Планы" }).first().click();
  await page.getByRole("button", { name: "Новый план" }).first().click();
  await page.getByRole("textbox", { name: "Название" }).fill(title);
  await page.locator('input[type="date"]').first().fill(now.toISOString().slice(0, 10));
  await page.getByRole("button", { name: "Создать план" }).click();
  await expect(page.locator(".plan-detail")).toContainText(title);

  await page.getByRole("button", { name: "Ещё" }).first().click();
  await page.getByRole("button", { name: /Календарь/ }).click();
  await expect(page.getByRole("grid", { name: /Календарь на/ })).toBeVisible();

  // The event is inside the cell for the created day.
  const cell = page.getByRole("gridcell", { name: cellName });
  await expect(cell.locator(".calendar-event", { hasText: title })).toBeVisible();

  // Clicking the event opens the plan it came from.
  await cell.locator(".calendar-event", { hasText: title }).click();
  await expect(page.locator(".plan-detail")).toContainText(title);
});
