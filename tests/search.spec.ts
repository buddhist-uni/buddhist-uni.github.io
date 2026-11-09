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

for (const q of ['anguttara', 'tag:anguttara', 'tag:aṅguttara']) {
  test(`${q} matches the Aṅguttara Nikāya tag`, async ({ page }) => {
    await page.goto('/search/?q=' + encodeURIComponent(q));
    await waitForSearchResults(page);

    await expect(page.getByText('Perhaps you meant')).toHaveCount(0);
    await expect(page.locator('.Label:has(.fa-tag) strong', { hasText: 'Aṅguttara' }).first()).toBeVisible();
  });
}

test('tag:an finds AN suttas', async ({ page }) => {
  await page.goto('/search/?q=tag%3Aan');
  await waitForSearchResults(page);

  await expect(page.locator('h3 a[href^="/content/canon/an"]').nth(49)).toBeVisible();
});

// Each result's tag labels
function tagLabels(page: Page) {
  return page.locator('#search-results li:has(h3)').evaluateAll(lis =>
    lis.map(li => Array.from(li.querySelectorAll('.Label:has(.fa-tag)'), l => l.textContent!.trim())));
}

for (const [q, titles] of [
  ['tag:nibbāna', ['Nibbāna', 'Nibbāna: The Goal of Buddhist Practice']], // tagged, and in the course
  ['tag:pitaka', ['The Vinaya']], // only a word of the raw tag vinaya-pitaka
  ['tag:higher-ed', ['higher ed']], // no tag page
] as const) {
  test(`${q} labels each result's tags once, by title`, async ({ page }) => {
    await page.goto('/search/?q=' + encodeURIComponent(q));
    await waitForSearchResults(page);

    const labels = await tagLabels(page);
    for (const l of labels) expect(l.length > 0 && new Set(l).size == l.length, JSON.stringify(l)).toBe(true);
    for (const t of titles) expect(labels.flat()).toContain(t);
  });
}

for (const q of ['tag:pali-canon', 'rawtag:pali-canon']) {
  test(`${q} only finds items tagged pali-canon`, async ({ page }) => {
    await page.goto('/search/?q=' + encodeURIComponent(q));
    await waitForSearchResults(page);

    const labels = await tagLabels(page);
    expect(labels.length).toBeGreaterThan(50);
    for (const l of labels) expect(l).toEqual(['The Pāli Canon']);
  });
}
