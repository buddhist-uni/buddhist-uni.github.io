import { test, expect, Page } from '@playwright/test';

async function waitForSearchResults(page: Page) {
  await expect(page.getByText('filter your results by')).toHaveCount(0);
  await expect(page.locator('#search-loading')).toBeInViewport();
  await expect(page.locator('#search-loading')).toBeHidden({ timeout: 10000 });
  await expect(page.getByText('results (')).toBeInViewport();
}

test('search scripts share a cache-busting token', async ({ page }) => {
  const scripts: string[] = [];
  page.on('request', (r) => { const m = /\/assets\/js\/((?:lunr|search|utils).*)/.exec(r.url()); if (m) scripts.push(m[1]); });
  await page.goto('/search/?q=nibbana');
  await waitForSearchResults(page);

  const token = /\?u=\w{7}$/.exec(scripts[0])![0];
  expect(scripts.sort()).toEqual(['lunr.min.js', 'search.js', 'search_functions.js', 'search_index.js', 'utils.js', 'utils.js'].map((s) => s + token));
});

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

for (const q of ['anguttara', 'topic:anguttara', 'topic:aṅguttara']) {
  test(`${q} matches the Aṅguttara Nikāya topic`, async ({ page }) => {
    await page.goto('/search/?q=' + encodeURIComponent(q));
    await waitForSearchResults(page);

    await expect(page.getByText('Perhaps you meant')).toHaveCount(0);
    await expect(page.locator('.Label:has(.fa-sitemap) strong', { hasText: 'Aṅguttara' }).first()).toBeVisible();
  });
}

// Each result's topic labels
function topicLabels(page: Page) {
  return page.locator('#search-results li:has(h3)').evaluateAll(lis =>
    lis.map(li => Array.from(li.querySelectorAll('.Label:has(.fa-tag, .fa-sitemap)'), l => l.textContent!.trim())));
}

for (const [q, titles, icon] of [
  ['tag:nibbāna', ['Nibbāna', 'Nibbāna: The Goal of Buddhist Practice'], 'fa-sitemap'], // tagged, and in the course
  ['topic:pitaka', ['The Vinaya'], 'fa-sitemap'], // only a word of the slug vinaya-pitaka
  ['tag:higher-ed', ['higher ed'], 'fa-tag'], // no topic page
] as const) {
  test(`${q} labels each result's topics once, by title`, async ({ page }) => {
    await page.goto('/search/?q=' + encodeURIComponent(q));
    await waitForSearchResults(page);

    const labels = await topicLabels(page);
    for (const l of labels) expect(l.length > 0 && new Set(l).size == l.length, JSON.stringify(l)).toBe(true);
    for (const t of titles) expect(labels.flat()).toContain(t);
    await expect(page.locator(`.Label:has(.${icon})`, { hasText: titles[0] }).first()).toBeVisible();
  });
}

for (const [q, title] of [['tag:pali-canon', 'The Pāli Canon'], ['tag:an', 'Aṅguttara Nikāya']]) {
  test(`${q} only finds items tagged ${title}`, async ({ page }) => {
    await page.goto('/search/?q=' + encodeURIComponent(q));
    await waitForSearchResults(page);

    const labels = await topicLabels(page);
    expect(labels.length).toBeGreaterThan(0);
    for (const l of labels) expect(l).toEqual([expect.stringContaining(title)]); // the course is "The Aṅguttara Nikāya"
  });
}

test('quoted search from the URL warns that quotes are ignored', async ({ page }) => {
  await page.goto('/search/?q=%22noble+truths%22');
  await waitForSearchResults(page);

  await expect(page.getByRole('alert')).toContainText('quotation marks were ignored');
  await expect(page.locator('#search-box')).toHaveValue('"noble truths"');
});

test('typing quotes shows the quote warning and removing them hides it', async ({ page }) => {
  await page.goto('/search/?q=noble+truths');
  await waitForSearchResults(page);
  const warning = page.getByRole('alert');
  await expect(warning).toHaveCount(0);

  const searchBox = page.locator('#search-box');
  await searchBox.fill('“noble truths”');
  await expect(warning).toContainText('quotation marks were ignored');

  await searchBox.fill('noble truths');
  await expect(warning).toHaveCount(0);
});

test('each warning gets its own icon', async ({ page }) => {
  await page.goto('/search/?q=this+is+a+exact+query+test');
  await waitForSearchResults(page);
  const warnings = page.locator('#search-results > li', { has: page.locator('.fa-triangle-exclamation') });
  await expect(warnings).toHaveCount(1);
  await expect(warnings).toContainText('matching all of your terms');

  await page.locator('#search-box').fill('this is an "exact query" test');
  await expect(warnings).toHaveCount(2);
  await expect(warnings.nth(0)).toContainText('quotation marks were ignored');
  await expect(warnings.nth(1)).toContainText('matching all of your terms');
  await expect(page).toHaveURL(/\?q=this%20is%20an%20%22exact%20query%22%20test$/);
});

test('finds and highlights a name whose letter has no accent to strip', async ({ page }) => {
  await page.goto('/search/?q=jorn+borup');
  await waitForSearchResults(page);

  await expect(page.locator('.Label strong', { hasText: 'Borup' }).first()).toHaveText('Jørn Borup');
});

test('highlights the right letters after a two-letter fold', async ({ page }) => {
  await page.goto('/search/?q=sangarava');
  await waitForSearchResults(page);

  await expect(page.locator('h3', { hasText: 'Lōvæḍa' }).locator('strong')).toHaveText('Saṅgarāva');
});

test('filtered search from the URL survives going back to it', async ({ page }) => {
  await page.goto('/search/?q=nibbana&filter=%2Bin%3Acanon');
  await waitForSearchResults(page);
  await expect.poll(() => page.evaluate(() => history.state.filterquery)).toBe('+in:canon');

  const searchBox = page.locator('#search-box');
  await searchBox.fill('kamma');
  await expect(page).toHaveURL(/\?q=kamma&filter=%2Bin%3Acanon$/);

  await page.goBack();
  await expect(page).toHaveURL(/\?q=nibbana&filter=%2Bin%3Acanon$/);
  await expect(searchBox).toHaveValue('nibbana');
  await expect(page.locator('#search-filter')).toHaveValue('+in:canon');
  await expect(page.locator('.Counter').first()).toContainText('Canonical Work');
});
