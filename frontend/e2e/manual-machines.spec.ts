import { test, expect } from '@playwright/test';

test('manual machine, multiple CIDR addresses and header logout', async ({ page }, info) => {
  await page.goto('/');
  await page.getByLabel('نام کاربری', { exact: true }).fill('demo-admin');
  await page.getByLabel('رمز عبور', { exact: true }).fill('Isolated-Demo-Password-2026!');
  await page.getByRole('button', { name: 'ورود امن' }).click();
  await expect(page.locator('header').getByRole('button', { name: 'خروج از حساب' })).toBeVisible();
  await page.getByRole('button', { name: 'پروژه‌ها و محیط‌ها' }).click();
  const project = `Manual check ${Date.now()} ${info.project.name}`;
  await page.getByLabel('نام پروژه', { exact: true }).fill(project);
  await page.getByRole('button', { name: 'ذخیره پروژه', exact: true }).click();
  await expect(page.getByRole('heading', { name: project, exact: true })).toBeVisible();
  await page.getByLabel('انتخاب پروژه').selectOption({ label: project });
  await page.getByRole('button', { name: 'موجودی ماشین‌ها' }).click();
  await page.getByRole('button', { name: 'افزودن دستی ماشین', exact: true }).click();
  await page.getByLabel('Server Name', { exact: true }).fill('manual-network-check');
  await page.getByLabel('نام محیط جدید', { exact: true }).fill('Test');
  await page.getByLabel('Server IP Addr', { exact: true }).fill('192.0.2.10/24');
  await page.getByRole('button', { name: '＋ IP دیگر', exact: true }).click();
  await page.getByLabel('Server IP Addr 2', { exact: true }).fill('198.51.100.10/25');
  await page.getByRole('button', { name: /^ذخیره تغییرات/ }).click();
  await expect(page.getByRole('button', { name: 'مشخصات ماشین manual-network-check', exact: true })).toBeVisible();
  await expect(page.getByText('198.51.100.10', { exact: true })).toBeVisible();
  await page.locator('header').getByRole('button', { name: 'خروج از حساب' }).click();
  await expect(page.getByRole('heading', { name: 'ورود به فضای مدیریت موجودی' })).toBeVisible();
});
