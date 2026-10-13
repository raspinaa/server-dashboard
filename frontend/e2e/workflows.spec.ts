import { test, expect } from "@playwright/test";
// Isolated real backend with the synthetic seed_dev command; no production credentials.
test("login, independent columns, inline editing, comments and export", async ({
  page,
}, testInfo) => {
  await page.goto("/");
  await page.getByLabel("نام کاربری", { exact: true }).fill("demo-admin");
  await page
    .getByLabel("رمز عبور", { exact: true })
    .fill("Isolated-Demo-Password-2026!");
  await page.getByRole("button", { name: "ورود امن" }).click();
  await expect(
    page.getByRole("heading", { name: "موجودی ماشین‌ها" }),
  ).toBeVisible();
  await expect(
    page.getByRole("columnheader", { name: "Application", exact: true }),
  ).toBeVisible();
  await expect(
    page.getByRole("columnheader", { name: "VMs", exact: true }),
  ).toBeVisible();
  await page.screenshot({
    path: `../docs/screenshots/inventory-${testInfo.project.name}.png`,
    fullPage: true,
  });
  await page
    .getByRole("button", { name: "مشخصات ماشین sample-node-1", exact: true })
    .click();
  await page
    .getByLabel("متن نظر یا کار انجام‌شده")
    .fill("فعالیت آزمایشی مرورگر");
  await page.getByRole("button", { name: "ثبت فعالیت" }).click();
  await expect(
    page.getByText("فعالیت آزمایشی مرورگر", { exact: true }).first(),
  ).toBeVisible();
  await page
    .getByRole("button", { name: "مشخصات و ویرایش", exact: true })
    .click();
  const cpuInput = page.getByLabel("CPU (Core)", { exact: true });
  await cpuInput.fill(String(Number(await cpuInput.inputValue()) + 1));
  await page.getByRole("button", { name: /ذخیره تغییرات/ }).click();
  await expect(cpuInput).toHaveCount(0);
  await page.getByRole("button", { name: "مرکز خروجی Excel" }).click();
  const download = page.waitForEvent("download");
  await page.getByRole("button", { name: "دریافت XLSX" }).click();
  expect((await download).suggestedFilename()).toBe("infrahub.xlsx");
  await page.getByRole("button", { name: "خروج از حساب" }).click();
  await expect(
    page.getByRole("heading", { name: "ورود به فضای مدیریت موجودی" }),
  ).toBeVisible();
});

test("create project, mapped XLSX import, resources and scoped viewer access", async ({
  page,
}, testInfo) => {
  const suffix = Date.now() + "-" + testInfo.project.name;
  const projectName = "پروژه آزمون " + suffix;
  const viewer = "viewer-" + suffix;
  await page.goto("/");
  await page.getByLabel("نام کاربری", { exact: true }).fill("demo-admin");
  await page
    .getByLabel("رمز عبور", { exact: true })
    .fill("Isolated-Demo-Password-2026!");
  await page.getByRole("button", { name: "ورود امن" }).click();
  await expect(
    page.getByRole("heading", { name: "موجودی ماشین‌ها" }),
  ).toBeVisible();
  await page.getByRole("button", { name: "پروژه‌ها و محیط‌ها" }).click();
  await page.getByLabel("نام پروژه", { exact: true }).fill(projectName);
  await page.getByRole("button", { name: "ذخیره پروژه", exact: true }).click();
  await expect(
    page.getByRole("heading", { name: projectName, exact: true }),
  ).toBeVisible();
  await page.getByLabel("انتخاب پروژه").selectOption({ label: projectName });
  await page.getByRole("button", { name: "مرکز ورود Excel" }).click();
  await page
    .getByLabel("فایل XLSX")
    .setInputFiles("../templates/infrahub-template.xlsx");
  await page.getByRole("button", { name: "بارگذاری", exact: true }).click();
  await expect(
    page.getByText("4 ردیف آماده ورود است.", { exact: false }),
  ).toBeVisible();
  await expect(
    page.getByRole("combobox", { name: "عمل", exact: true }),
  ).toHaveCount(0);
  await page.screenshot({
    path: `../docs/screenshots/import-${testInfo.project.name}.png`,
    fullPage: true,
  });
  await page.getByRole("button", { name: "تأیید و اعمال تراکنشی" }).click();
  await expect(
    page.getByRole("status").filter({ hasText: "ورود کامل شد: 4 افزوده" }),
  ).toBeVisible();
  await page.getByRole("button", { name: "موجودی ماشین‌ها" }).click();
  await expect(
    page.getByRole("button", {
      name: "مشخصات ماشین sample-node-4",
      exact: true,
    }),
  ).toBeVisible();
  await expect(
    page.getByRole("columnheader", { name: "Disk 4 (GB)", exact: true }),
  ).toBeVisible();
  await page.getByRole("button", { name: "کاربران و دسترسی" }).click();
  await page.getByLabel("نام کاربری", { exact: true }).fill(viewer);
  await page
    .getByLabel("رمز حساب", { exact: true })
    .fill("Isolated-Viewer-Password-2026!");
  await page.getByRole("button", { name: "ذخیره حساب", exact: true }).click();
  await expect(
    page.getByRole("button", { name: new RegExp(viewer) }),
  ).toBeVisible();
  await page
    .getByRole("combobox", { name: "کاربر", exact: true })
    .selectOption({ label: viewer });
  await page
    .getByRole("combobox", { name: "نقش", exact: true })
    .selectOption("viewer");
  await page.getByRole("button", { name: "ذخیره عضویت", exact: true }).click();
  await expect(
    page.getByText(viewer + " · بیننده", { exact: false }).last(),
  ).toBeVisible();
  await page.getByRole("button", { name: "خروج از حساب" }).click();
  await expect(
    page.getByRole("heading", { name: "ورود به فضای مدیریت موجودی" }),
  ).toBeVisible();
  await page.getByLabel("نام کاربری", { exact: true }).fill(viewer);
  await page
    .getByLabel("رمز عبور", { exact: true })
    .fill("Isolated-Viewer-Password-2026!");
  await page.getByRole("button", { name: "ورود امن" }).click();
  await expect(
    page.getByRole("button", {
      name: "مشخصات ماشین sample-node-4",
      exact: true,
    }),
  ).toBeVisible();
  await expect(
    page.getByRole("button", { name: "افزودن دستی ماشین", exact: true }),
  ).toHaveCount(0);
  await expect(
    page.getByRole("button", { name: "کاربران و دسترسی" }),
  ).toHaveCount(0);
  await page.getByRole("button", { name: "مرکز ورود Excel" }).click();
  await expect(
    page.getByText("ورود Excel به مجوز مدیر پروژه نیاز دارد.", { exact: true }),
  ).toBeVisible();
});

test("credential redaction, timed reveal and clipboard fallback", async ({
  page,
}) => {
  await page.addInitScript(() =>
    Object.defineProperty(navigator, "clipboard", {
      value: {
        writeText: async () => {
          throw new Error("isolated clipboard fallback");
        },
      },
    }),
  );
  await page.goto("/");
  await page.getByLabel("نام کاربری", { exact: true }).fill("demo-admin");
  await page
    .getByLabel("رمز عبور", { exact: true })
    .fill("Isolated-Demo-Password-2026!");
  await page.getByRole("button", { name: "ورود امن" }).click();
  await page
    .getByRole("button", { name: "مشخصات ماشین sample-node-1", exact: true })
    .click();
  await page
    .getByRole("button", { name: "مشخصات و ویرایش", exact: true })
    .click();
  await page.getByRole("button", { name: "ویرایش رمز / مرجع" }).click();
  await page.getByLabel("رمز ماشین جدید").fill("SYNTHETIC-BROWSER-ONLY");
  await page.getByRole("button", { name: "ذخیره اعتبارنامه" }).click();
  await expect(page.getByLabel("رمز ماشین جدید")).toHaveCount(0);
  await expect(
    page.getByRole("button", {
      name: "مشخصات ماشین sample-node-1",
      exact: true,
    }),
  ).toHaveAttribute("aria-expanded", "false");
  await page
    .getByRole("button", { name: "مشخصات ماشین sample-node-1", exact: true })
    .click();
  await page
    .getByRole("button", { name: "مشخصات و ویرایش", exact: true })
    .click();
  await page.clock.install();
  await page.getByRole("button", { name: "نمایش رمز", exact: true }).click();
  await expect(page.getByLabel("رمز بازیابی‌شده")).toHaveValue(
    "SYNTHETIC-BROWSER-ONLY",
  );
  await page.clock.fastForward(16000);
  await expect(page.getByLabel("رمز بازیابی‌شده")).toHaveCount(0);
  await page.getByRole("button", { name: "کپی", exact: true }).click();
  await expect(
    page.getByText("کپی خودکار ممکن نیست؛ متن را انتخاب و دستی کپی کنید."),
  ).toBeVisible();
  await page.getByRole("button", { name: "مرکز خروجی Excel" }).click();
  await expect(page.getByLabel("رمز بازیابی‌شده")).toHaveCount(0);
  const inventory = await page.request.get("/api/projects/1/machines/");
  expect(await inventory.text()).not.toContain("SYNTHETIC-BROWSER-ONLY");
  const audit = await page.request.get("/api/audit/");
  expect(await audit.text()).not.toContain("SYNTHETIC-BROWSER-ONLY");
});
