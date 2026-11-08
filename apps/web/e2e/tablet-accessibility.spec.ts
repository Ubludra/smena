import { expect, test } from "@playwright/test";

test("tablet and desktop layouts keep named landmarks and usable controls", async ({ page }) => {
  await page.setViewportSize({ width: 768, height: 1024 });
  await page.goto("/");

  await page.getByLabel("Как вас зовут?").fill("Планшетный учитель");
  await page.getByRole("button", { name: "Продолжить" }).click();
  await expect(page.getByRole("main", { name: "Основное содержимое" })).toBeVisible();

  await expect(page.getByRole("navigation", { name: "Разделы" })).toBeVisible();
  await expect(page.getByRole("navigation", { name: "Разделы" })).toHaveCount(1);
  await expect(page.getByRole("button", { name: "Главная" }).first()).toHaveAttribute(
    "aria-current",
    "page",
  );
  await expect(page.getByRole("button", { name: /Создать материал/ })).toBeVisible();
  await expect(page.getByRole("button", { name: /Создать материал/ })).toHaveCSS(
    "min-height",
    "82px",
  );

  await page.getByRole("button", { name: /Создать материал/ }).click();
  const materialForm = page.getByRole("form", { name: "Новый материал" });
  await expect(materialForm).toBeVisible();
  await expect(page.getByRole("textbox", { name: "Название" })).toHaveAttribute(
    "required",
    "",
  );
  await expect(page.getByRole("textbox", { name: "Содержание (необязательно)" })).toBeVisible();

  await page.route("**/api/v1/materials", async (route) => {
    if (route.request().method() === "POST") {
      await route.fulfill({
        status: 422,
        contentType: "application/json",
        body: JSON.stringify({ detail: "Некорректное название" }),
      });
      return;
    }
    await route.continue();
  });
  await page.getByRole("textbox", { name: "Название" }).fill("Проверка доступности");
  await page.getByRole("button", { name: "Сохранить материал" }).click();
  const formError = page.getByRole("alert");
  await expect(formError).toBeVisible();
  await expect(page.getByRole("textbox", { name: "Название" })).toHaveAttribute(
    "aria-invalid",
    "true",
  );
  await expect(page.getByRole("textbox", { name: "Название" })).toHaveAttribute(
    "aria-describedby",
    "material-form-error",
  );

  await assertNoHorizontalOverflow(page);

  await page.setViewportSize({ width: 800, height: 1024 });
  await expect(page.locator(".app-tabs")).toBeVisible();
  await expect(page.locator(".bottom-nav")).toBeHidden();
  await expect(page.getByRole("navigation", { name: "Разделы" })).toHaveCount(1);
  await expect(page.getByRole("button", { name: "Поиск по материалам" })).toBeVisible();
  const tabletColumns = await page.locator(".material-form").evaluate(
    (element) => getComputedStyle(element).gridTemplateColumns.split(" ").length,
  );
  expect(tabletColumns).toBe(1);
  await assertNoHorizontalOverflow(page);

  await page.setViewportSize({ width: 1024, height: 768 });
  await expect(page.locator(".app-tabs")).toBeVisible();
  await expect(page.locator(".bottom-nav")).toBeHidden();
  await expect(page.getByRole("navigation", { name: "Разделы" })).toBeVisible();
  await expect(page.getByRole("navigation", { name: "Разделы" })).toHaveCount(1);
  const desktopColumns = await page.locator(".material-form").evaluate(
    (element) => getComputedStyle(element).gridTemplateColumns.split(" ").length,
  );
  expect(desktopColumns).toBe(2);
  await assertNoHorizontalOverflow(page);
});

async function assertNoHorizontalOverflow(page: import("@playwright/test").Page) {
  const dimensions = await page.evaluate(() => ({
    viewportWidth: document.documentElement.clientWidth,
    documentWidth: document.documentElement.scrollWidth,
  }));
  expect(dimensions.documentWidth).toBeLessThanOrEqual(dimensions.viewportWidth);
}
