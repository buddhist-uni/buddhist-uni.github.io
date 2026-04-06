import { test, expect, Page } from '@playwright/test';

/**
 * Wait for the DataTable to finish loading.
 * The tables show a #table-loading indicator while fetching data,
 * then render rows into #mainContentList.
 */
async function waitForTableLoaded(page: Page) {
  // Wait for loading indicator to appear then disappear
  await expect(page.locator('#table-loading')).toBeHidden({ timeout: 30000 });
  // Table should have at least one data row
  await expect(page.locator('#mainContentList tbody tr').first()).toBeVisible({ timeout: 15000 });
}

// Content type pages and their expected column headers
const contentPages = [
  { path: '/content/canon/', name: 'Canonical Works', minRows: 50 },
  { path: '/content/monographs/', name: 'Monographs', minRows: 50 },
  { path: '/content/articles/', name: 'Articles', minRows: 50, extraColumn: 'Journal' },
  { path: '/content/booklets/', name: 'Booklets', minRows: 10 },
  { path: '/content/essays/', name: 'Essays', minRows: 20 },
  { path: '/content/papers/', name: 'Papers', minRows: 10 },
  { path: '/content/excerpts/', name: 'Excerpts', minRows: 10 },
  { path: '/content/av/', name: 'Audio/Video', minRows: 20 },
  { path: '/content/reference/', name: 'Reference Shelf', minRows: 5 },
];

test('content index page lists all types', async ({ page }) => {
  await page.goto('/content/');
  await expect(page).toHaveTitle(/Content/i);

  // Verify all content type links exist
  for (const { name } of contentPages) {
    await expect(page.getByRole('link', { name })).toBeVisible();
  }
});

for (const { path, name, minRows, extraColumn } of contentPages) {
  test(`${name} table loads with data`, async ({ page }) => {
    await page.goto(path);
    await waitForTableLoaded(page);

    // Standard columns should be present
    const headers = page.locator('#mainContentList th');
    await expect(headers.filter({ hasText: 'Name' })).toBeVisible();
    await expect(headers.filter({ hasText: 'Year' })).toBeVisible();
    await expect(headers.filter({ hasText: 'Author' })).toBeVisible();

    // Check type-specific extra column
    if (extraColumn) {
      await expect(headers.filter({ hasText: extraColumn })).toBeVisible();
    }

    // Verify minimum row count
    const rows = page.locator('#mainContentList tbody tr');
    const count = await rows.count();
    expect(count).toBeGreaterThanOrEqual(minRows);
  });
}

test('canon table has clickable entry links', async ({ page }) => {
  await page.goto('/content/canon/');
  await waitForTableLoaded(page);

  // First row should have a link in the Name column
  const firstLink = page.locator('#mainContentList tbody tr').first().locator('a').first();
  await expect(firstLink).toBeVisible();
  const href = await firstLink.getAttribute('href');
  expect(href).toBeTruthy();
});

test('articles table sorting by year', async ({ page }) => {
  await page.goto('/content/articles/');
  await waitForTableLoaded(page);

  // Click the Year header to sort
  const yearHeader = page.locator('#mainContentList th', { hasText: 'Year' });
  await yearHeader.click();

  // After sorting, first visible year should be a number
  const firstYearCell = page.locator('#mainContentList tbody tr').first().locator('td').nth(2);
  const yearText = await firstYearCell.textContent();
  expect(yearText?.trim()).toMatch(/^\d{4}$/);
});

test('datatable search/filter works', async ({ page }) => {
  await page.goto('/content/monographs/');
  await waitForTableLoaded(page);

  const initialCount = await page.locator('#mainContentList tbody tr').count();

  // DataTables adds a search input — find and use it
  const dtSearch = page.locator('input[type="search"]');
  if (await dtSearch.isVisible()) {
    await dtSearch.fill('meditation');
    // Wait for filtering to apply
    await page.waitForTimeout(500);
    const filteredCount = await page.locator('#mainContentList tbody tr').count();
    // Filtered results should be fewer (or equal if all match)
    expect(filteredCount).toBeLessThanOrEqual(initialCount);
    // At least one result should mention meditation
    if (filteredCount > 0) {
      const firstRow = page.locator('#mainContentList tbody tr').first();
      await expect(firstRow).toContainText(/[Mm]editation/);
    }
  }
});

test('all content page loads total count', async ({ page }) => {
  await page.goto('/content/all');
  await waitForTableLoaded(page);

  // Should have a large number of entries
  const rows = page.locator('#mainContentList tbody tr');
  const count = await rows.count();
  expect(count).toBeGreaterThanOrEqual(200);
});
