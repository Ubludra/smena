import { expect, test } from "@playwright/test";

/**
 * Template flow: save an existing plan as a template → use it → the new
 * plan form arrives prefilled → save as a normal object.
 */
test("template: save plan as template, use it, form is prefilled", async ({ page }) => {
  const sourceTitle = `E2E план-источник ${Date.now()}`;

  await page.goto("/");
  await page.getByLabel("Как вас зовут?").fill("E2E Учитель");
  await page.getByRole("button", { name: "Продолжить" }).click();
  await expect(page.getByRole("main", { name: "Основное содержимое" })).toBeVisible();

  // Create a source plan.
  await page.getByRole("button", { name: "Планы" }).first().click();
  await page.getByRole("button", { name: "Новый план" }).first().click();
  await page.getByRole("textbox", { name: "Название" }).fill(sourceTitle);
  await page
    .getByRole("textbox", { name: "Тема (необязательно)" })
    .fill("Тема из шаблона");
  await page.getByRole("button", { name: "Создать план" }).click();
  await expect(page.locator(".plan-detail")).toContainText(sourceTitle);

  // Save as template.
  await page.getByRole("button", { name: "Сохранить как шаблон" }).click();
  await expect(page.getByText("Шаблон сохранён")).toBeVisible();

  // Open Templates via «Ещё» and use it.
  await page.getByRole("button", { name: "Ещё" }).first().click();
  await page.getByRole("button", { name: /Шаблоны/ }).click();
  await expect(page.getByRole("heading", { name: "Шаблоны" })).toBeVisible();
  await page
    .getByRole("button", { name: new RegExp(sourceTitle) })
    .first()
    .click();

  // The create form is prefilled from the template.
  const heading = page.getByRole("heading", { name: /Новый план из шаблона/ });
  await expect(heading).toBeVisible();
  await expect(page.getByRole("textbox", { name: "Название" })).toHaveValue(
    sourceTitle,
  );
  await expect(page.getByRole("textbox", { name: "Тема (необязательно)" })).toHaveValue(
    "Тема из шаблона",
  );

  // Edit and save as a normal plan.
  const uniqueTitle = `План из шаблона ${Date.now()}`;
  await page.getByRole("textbox", { name: "Название" }).fill(uniqueTitle);
  await page.getByRole("button", { name: "Создать план" }).click();
  await expect(page.locator(".plan-detail")).toContainText(uniqueTitle);
  await expect(page.locator(".plan-detail")).toContainText("Тема из шаблона");

  // Reload: persisted.
  await page.reload();
  await expect(page.locator(".plan-detail")).toContainText(uniqueTitle);

  // Cleanup: delete both plans.
  await page.getByRole("button", { name: "Удалить" }).first().click();
  await page.getByRole("button", { name: "Удалить", exact: true }).last().click();
  await page.getByRole("button", { name: new RegExp(sourceTitle) }).click();
  await page.getByRole("button", { name: "Удалить" }).first().click();
  await page.getByRole("button", { name: "Удалить", exact: true }).last().click();
  await expect(page.getByRole("button", { name: new RegExp(sourceTitle) })).toHaveCount(0);

  // Cleanup: delete the template.
  await page.getByRole("button", { name: "Ещё" }).first().click();
  await page.getByRole("button", { name: /Шаблоны/ }).click();
  await page.getByRole("button", { name: "Удалить" }).click();
  await page.getByRole("button", { name: "Удалить", exact: true }).last().click();
  await expect(
    page.getByRole("button", { name: new RegExp(sourceTitle) }),
  ).toHaveCount(0);
});
