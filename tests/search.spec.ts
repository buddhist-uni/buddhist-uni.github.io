import { test, expect, Page } from '@playwright/test';

async function waitForSearchResults(page: Page) {
  await expect(page.getByText('filter your results by')).toHaveCount(0);
  await expect(page.locator('#search-loading')).toBeInViewport();
  await expect(page.locator('#search-loading')).toBeHidden();
  await expect(page.getByText('results (')).toBeInViewport();
}

test('blank search page', async ({ page }) => {
  await page.goto('/search/');

  await expect(page).toHaveTitle(/Search/);
  await expect(page.getByText('filter your results by')).toBeVisible();
  await expect(page.locator('#search-loading')).toBeHidden();
});

test('search agamas by analayo and not', async ({ page }) => {
  await page.goto('/search/?q=%2Bagama%20-author%3Aanalayo&filter=%2Bin%3Aarticles');
  await waitForSearchResults(page);

  const searchBox = page.locator('#search-box');
  const inputValue = await searchBox.inputValue();
  expect(inputValue).toEqual('+agama -author:analayo');

  let kuanResults = page.locator('.Label', { hasText: 'Tse-fu Kuan' }).nth(3);
  await expect(kuanResults).toBeVisible();

  let resultsWithAnalayo = page.locator('.Label', { hasText: 'Anālayo' });
  await expect(resultsWithAnalayo).toHaveCount(0);

  await searchBox.fill('+agama +author:analayo');
  // No need to waitForSearchResults here because the index is already loaded.
  // This .nth await will wait the few milliseconds it takes for the results
  // to update according to the new query.
  resultsWithAnalayo = page.locator('.Label', { hasText: 'Anālayo' }).nth(20);
  await expect(resultsWithAnalayo).toBeVisible();

  kuanResults = page.locator('.Label', { hasText: 'Tse-fu Kuan' });
  await expect(kuanResults).toHaveCount(0);
});

test('bodhi translations in canon filter', async ({ page }) => {
  await page.goto('/search/?q=%2Btranslator%3Abodhi&filter=%2Bin%3Acanon');
  await waitForSearchResults(page);

  const searchBox = page.locator('#search-box');
  const inputValue = await searchBox.inputValue();
  expect(inputValue).toEqual('+translator:bodhi');

  const searchFilter = page.locator('#search-filter');
  const filterValue = await searchFilter.inputValue();
  expect(filterValue).toEqual('+in:canon');
  const filterLabel = await searchFilter.locator('option:checked').textContent();
  expect(filterLabel).toEqual('Canon');

  const resultTypes = page.locator('.Counter');
  const count = await resultTypes.count();
  expect(count).toBeGreaterThanOrEqual(100);
  for (let i = 0; i < count; i++) {
    await expect(resultTypes.nth(i)).toContainText('Canonical Work');
  }

  const translatorPill = page.locator('.Label', { hasText: 'Translator: Bhikkhu Bodhi' }).nth(99);
  await expect(translatorPill).toBeVisible();
});

test('empty query shows no results', async ({ page }) => {
  await page.goto('/search/?q=');
  await expect(page.getByText('filter your results by')).toBeVisible();
  await expect(page.getByText('results (')).toHaveCount(0);
});

test('search with no matches shows zero results', async ({ page }) => {
  await page.goto('/search/?q=zzznonexistentterm99999');
  await waitForSearchResults(page);
  await expect(page.getByText('results (0)')).toBeVisible();
});

test('search results update live on typing', async ({ page }) => {
  await page.goto('/search/?q=mindfulness');
  await waitForSearchResults(page);

  const resultsText = page.getByText('results (');
  await expect(resultsText).toBeVisible();

  // Change query and verify results update without page reload
  const searchBox = page.locator('#search-box');
  await searchBox.fill('dependent origination');
  // Wait for at least one result to appear with new content
  await expect(page.locator('.Label', { hasText: 'Dependent' }).first()).toBeVisible();
});

test('filter dropdown changes result types', async ({ page }) => {
  await page.goto('/search/?q=meditation&filter=%2Bin%3Aav');
  await waitForSearchResults(page);

  const searchFilter = page.locator('#search-filter');
  const filterLabel = await searchFilter.locator('option:checked').textContent();
  expect(filterLabel).toEqual('Audio/Video');

  // All results should be AV type
  const resultTypes = page.locator('.Counter');
  const count = await resultTypes.count();
  expect(count).toBeGreaterThan(0);
  for (let i = 0; i < count; i++) {
    await expect(resultTypes.nth(i)).toContainText(/Audio|Video/);
  }
});

test('search preserves query params in URL', async ({ page }) => {
  await page.goto('/search/');
  const searchBox = page.locator('#search-box');
  await searchBox.fill('heart sutra');
  await waitForSearchResults(page);

  // URL should contain the query
  expect(page.url()).toContain('q=heart');
});
