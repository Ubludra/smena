import { expect, test } from "@playwright/test";

/**
 * Files flow: Ещё → Файлы → upload via the hidden file input → the file
 * appears with its name → delete with confirmation → empty state again.
 */
test("files: upload, list, delete", async ({ page }) => {
  const fileName = `e2e-конспект-${Date.now()}.txt`;

  await page.goto("/");
  // Fresh teacher per run: the empty-state assertion below must not see
  // files left behind by an earlier interrupted run.
  await page.getByLabel("Как вас зовут?").fill(`E2E Файлы ${Date.now()}`);
  await page.getByRole("button", { name: "Продолжить" }).click();
  await expect(page.getByRole("main", { name: "Основное содержимое" })).toBeVisible();

  await page.getByRole("button", { name: "Ещё" }).first().click();
  await page.getByRole("button", { name: /Файлы/ }).click();
  await expect(page.getByRole("heading", { name: "Файлы" })).toBeVisible();

  // A fresh teacher sees the honest empty state before uploading.
  await expect(page.getByText("Пока нет загруженных файлов")).toBeVisible();

  await page.locator('input[type="file"][hidden]').setInputFiles({
    name: fileName,
    mimeType: "text/plain",
    buffer: Buffer.from("Содержимое файла для E2E"),
  });

  await expect(page.getByRole("button", { name: new RegExp(fileName) })).toBeVisible({
    timeout: 10_000,
  });

  // Delete with confirmation; the file disappears from the list.
  await page.getByRole("button", { name: "Удалить" }).first().click();
  await expect(page.getByText("Удалить файл?")).toBeVisible();
  await page.getByRole("button", { name: "Удалить" }).last().click();

  await expect(page.getByText("Пока нет загруженных файлов")).toBeVisible({
    timeout: 10_000,
  });
});
