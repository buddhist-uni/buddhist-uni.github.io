import { test, expect, Page } from '@playwright/test';

async function waitForSearchResults(page: Page) {
  await expect(page.getByText('filter your results by')).toHaveCount(0);
  await expect(page.locator('#search-loading')).toBeInViewport();
  await expect(page.locator('#search-loading')).toBeHidden({ timeout: 10000 });
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

test('a sutta we do not have links to its SuttaCentral translation', async ({ page }) => {
  await page.route('https://suttacentral.net/api/suttaplex/**', route => route.fulfill({
    json: [{
      uid: 'mn37', acronym: 'MN 37', original_title: 'Cūḷataṇhāsaṅkhayasutta', translated_title: 'The Shorter Discourse on the Ending of Craving',
      blurb: 'Sakka asks the Buddha how a mendicant is freed.',
      translations: [{ lang: 'en', author_uid: 'sujato' }, { lang: 'en', author_uid: 'bodhi' }],
    }],
  }));
  await page.goto('/search/?q=MN+37');
  await waitForSearchResults(page);

  const link = page.locator('#sc-direct-link-title');
  await expect(link).toHaveText('MN 37 Cūḷataṇhāsaṅkhayasutta: The Shorter Discourse on the Ending of Craving');
  await expect(link).toHaveAttribute('href', 'https://suttacentral.net/mn37/en/bodhi');
  await expect(page.locator('#sc-direct-link-blurb')).toHaveText('Sakka asks the Buddha how a mendicant is freed.');
});

test('a verse inside a range text keeps its link to the verse', async ({ page }) => {
  // SuttaCentral has no suttaplex of its own for Dhp 5, which lives in dhp1-20
  await page.route('https://suttacentral.net/api/suttaplex/**', route => route.fulfill({
    json: [{ uid: null, acronym: null, original_title: null, translated_title: null, blurb: null, translations: [] }],
  }));
  await page.goto('/search/?q=Dhp+5');
  await waitForSearchResults(page);

  const link = page.locator('#sc-direct-link-title');
  await expect(link).toHaveText('Dhp 5');
  await expect(link).toHaveAttribute('href', 'https://suttacentral.net/dhp5/en/sujato');
  await expect(page.locator('#sc-direct-link-blurb')).toContainText('find it on SuttaCentral');
});
