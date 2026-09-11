import { test, expect, Page } from '@playwright/test';

test('big content table loads', async ({ page, isMobile }) => {
  await page.goto('/content/all/'); // The long table loading all happens in this call

  await expect(page).toHaveTitle(/All Content/);
  await expect(page.locator('#table-loading')).toBeHidden();

  const row = page.locator('#mainContentList tbody tr').filter({ hasText: 'Path of Purification' }).first();
  await expect(row).toBeInViewport();

  if (isMobile) {
    await expect(row.locator('td')).toHaveCount(2);
  } else {
    await expect(row.locator('td').nth(2)).toHaveText("1956");
    const dlColText = await row.locator('td').nth(7).textContent();
    expect(parseInt(dlColText || "0")).toBeGreaterThan(500);
  }
});
