import { test, expect } from "@playwright/test";

test("management report filters and explicit project XLSX export", async ({
  page,
}, info) => {
  await page.goto("/");
  await page.getByLabel("نام کاربری", { exact: true }).fill("demo-admin");
  await page
    .getByLabel("رمز عبور", { exact: true })
    .fill("Isolated-Demo-Password-2026!");
  await page.getByRole("button", { name: "ورود امن" }).click();
  await page
    .getByRole("button", { name: "گزارش مدیریتی", exact: true })
    .click();
  await expect(
    page.getByRole("heading", { name: "داشبورد گزارش مدیریتی" }),
  ).toBeVisible();
  await expect(
    page.getByRole("heading", { name: "جزئیات پروژه‌ها", exact: true }),
  ).toBeVisible();
  await page
    .getByLabel("پروژه گزارش", { exact: true })
    .selectOption({ label: "پروژه نمونه" });
  await page
    .getByLabel("محیط گزارش", { exact: true })
    .selectOption({ label: "Develop" });
  await expect(
    page.getByRole("heading", { name: "سرویس‌ها و Applicationها" }),
  ).toBeVisible();
  await expect(page.getByLabel("پروژه خروجی", { exact: true })).toHaveValue(
    await page.getByLabel("پروژه گزارش", { exact: true }).inputValue(),
  );
  const download = page.waitForEvent("download");
  await page.getByRole("button", { name: "دریافت XLSX", exact: true }).click();
  expect((await download).suggestedFilename()).toBe("infrahub.xlsx");
  await page.screenshot({
    path: `/tmp/infrahub-reports-${info.project.name}.png`,
    fullPage: true,
  });
  await page
    .getByRole("button", { name: "مرکز خروجی Excel", exact: true })
    .click();
  await page
    .getByLabel("پروژه خروجی", { exact: true })
    .selectOption({ label: "پروژه نمونه" });
  await expect(
    page.getByRole("button", { name: "دریافت XLSX", exact: true }),
  ).toBeEnabled();
});
