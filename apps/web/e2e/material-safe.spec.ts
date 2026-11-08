import { expect, test } from "@playwright/test";

/**
 * Safe flow against the real stack: open the Safe with a brand-new password
 * («Создать и открыть» — first-run UI), create a protected material, see it
 * in the Safe, reload — it is still there and still readable.
 *
 * A unique display name per run means a fresh teacher: no password yet, no
 * residue from earlier runs (the first-run unlock UI is then deterministic).
 */
test("material remains in the Safe after a reload", async ({ page }) => {
  const uniqueTitle = `Проверка Сейфа ${Date.now()}`;
  const teacherName = `E2E Сейф ${Date.now()}`;

  await page.goto("/");
  await page.getByLabel("Как вас зовут?").fill(teacherName);
  await page.getByRole("button", { name: "Продолжить" }).click();

  // Step one: set the Safe password. Before this, protected content is
  // deliberately unreadable (API answers 403 without an unlock token).
  await page.getByRole("button", { name: "Сейф", exact: true }).click();
  await expect(
    page.getByRole("heading", { name: "Сейф заблокирован" }),
  ).toBeVisible();
  await page.getByLabel("Пароль Сейфа").fill("e2e-seyf-2026");
  await page.getByRole("button", { name: "Создать и открыть" }).click();
  await expect(page.getByLabel("Поиск в Сейфе")).toBeVisible();

  // Step two: create a protected material while unlocked.
  await page.getByRole("button", { name: "Главная" }).first().click();
  await page.getByRole("button", { name: /Создать материал/ }).click();
  await page.getByLabel("Название", { exact: true }).fill(uniqueTitle);
  await page.getByLabel("Предмет (необязательно)").fill("Проверка");
  await page.getByLabel("Содержание (необязательно)").fill("Данные после обновления");
  await page.getByLabel("Добавить в Сейф").check();
  await page.getByRole("button", { name: "Сохранить материал" }).click();

  await expect(page.getByRole("heading", { name: uniqueTitle })).toBeVisible();

  await page.getByRole("button", { name: "Сейф", exact: true }).click();
  await expect(
    page.getByRole("button", { name: new RegExp(uniqueTitle) }),
  ).toBeVisible();

  await page.reload();
  // exact:true: while unlocked the page also shows the «Сейф разблокирован»
  // hero heading, which a substring match would ambiguously hit.
  await expect(
    page.getByRole("heading", { name: "Сейф", exact: true }),
  ).toBeVisible();
  // The unlock lives in sessionStorage, so a reload keeps it; re-unlock
  // deterministically if a browser dropped the storage instead.
  if (await page.getByRole("button", { name: "Разблокировать" }).count()) {
    await page.getByLabel("Пароль Сейфа").fill("e2e-seyf-2026");
    await page.getByRole("button", { name: "Разблокировать" }).click();
  }
  await page.getByRole("button", { name: new RegExp(uniqueTitle) }).click();
  await expect(page.getByText("Данные после обновления")).toBeVisible();
});
