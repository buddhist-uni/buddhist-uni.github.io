import { test, expect } from '@playwright/test';

test('has title', async ({ page }) => {
  await page.goto('');

  // Expect a title "to contain" a substring.
  await expect(page).toHaveTitle(/Buddhist University/);
});

test('library link', async ({ page }) => {
  await page.goto('');

  // Click the get started link.
  const liblinks = page.getByRole('link', { name: 'Library' });
  await expect(liblinks).toHaveCount(2);
  await liblinks.last().click();

  // Expects page to have a heading with the name of Installation.
  await expect(page.getByRole('heading', { name: 'Topics' })).toBeVisible();
});
