import { test, expect } from '@playwright/test';

test('old topic URL redirects, keeping its query and hash', async ({ page }) => {
  await page.goto('/tags/meditation?x=1#children');
  await expect(page).toHaveURL('/topics/meditation?x=1#children');
});

test('old topic index redirects', async ({ page }) => {
  await page.goto('/tags/');
  await expect(page).toHaveURL('/topics/');
});
