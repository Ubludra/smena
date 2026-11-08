import { expect, test } from "@playwright/test";

test("mobile layout stays usable and supports keyboard skip navigation", async ({ page }) => {
  await page.setViewportSize({ width: 320, height: 740 });
  await page.goto("/");

  await expect(page.getByRole("form", { name: "Вход в браузерное демо" })).toBeVisible();
  const nameField = page.getByRole("textbox", { name: "Как вас зовут?" });
  await nameField.fill("Мобильный учитель");
  await nameField.press("Enter");
  await expect(page.getByRole("heading", { name: /Мобильный учитель/ })).toBeVisible();
  await expect(page.getByRole("main", { name: "Основное содержимое" })).toBeVisible();
  await expect(page.getByRole("button", { name: "Поиск по материалам" })).toHaveCount(1);

  await page.keyboard.press("Tab");
  const skipLink = page.getByRole("link", { name: "Перейти к содержимому" });
  await expect(skipLink).toBeFocused();
  await expect(skipLink).toHaveCSS("outline-style", "solid");
  await expect(skipLink).toHaveCSS("outline-width", "3px");
  await page.keyboard.press("Enter");
  await expect(page.locator("#main")).toBeFocused();

  await expect(page.getByRole("navigation", { name: "Разделы" })).toBeVisible();
  const dimensions = await page.evaluate(() => ({
    viewportWidth: document.documentElement.clientWidth,
    documentWidth: document.documentElement.scrollWidth,
  }));
  expect(dimensions.documentWidth).toBeLessThanOrEqual(dimensions.viewportWidth);

  const navButtons = page.getByRole("navigation", { name: "Разделы" }).getByRole("button");
  await expect(navButtons).toHaveCount(5);
  // Phone bottom nav keeps five items; the rest live behind «Ещё».
  await expect(page.getByRole("button", { name: "Ещё" }).last()).toBeVisible();
  for (const button of await navButtons.all()) {
    const box = await button.boundingBox();
    expect(box).not.toBeNull();
    expect(box!.height).toBeGreaterThanOrEqual(44);
  }

  await page.getByRole("button", { name: "Поиск по материалам" }).click();
  await expect(page.getByRole("heading", { name: "Мои материалы" })).toBeVisible();
  await expect(page.getByRole("searchbox", { name: "Поиск материалов" })).toBeFocused();
});
