import { test, expect } from '@playwright/test';
import { readFileSync } from 'fs';

// Primer styles that an upgrade could change without a visible diff

test('root font size follows the browser setting', async ({ page }) => {
  const cdp = await page.context().newCDPSession(page);
  await cdp.send('Page.setFontSizes', { fontSizes: { standard: 20 } });
  await page.goto('/');
  await expect(page.locator('html')).toHaveCSS('font-size', '20px');
});

test('headings keep our sizes', async ({ page }) => {
  await page.goto('/');
  await expect(page.getByRole('heading', { name: 'A Free Buddhist Education' })).toHaveCSS('font-size', '36px');
  await expect(page.getByRole('heading', { name: 'Featuring:' })).toHaveCSS('font-size', '26px');
  await page.goto('/courses/');
  const course = page.locator('a.f3').first();
  await expect(course).toHaveCSS('font-size', '22px');
  await page.setViewportSize({ width: 375, height: 667 });
  await expect(course).toHaveCSS('font-size', '22px');
});

test('buttons and tag labels keep their shape', async ({ page }) => {
  await page.goto('/content/articles/ancient-indian-education_analayo');
  const button = page.locator('a.btn').first();
  await expect(button).toHaveCSS('padding', '5px 16px');
  await expect(button).toHaveCSS('background-color', 'rgb(246, 248, 250)');
  await expect(button).toHaveCSS('border-color', 'rgba(31, 35, 40, 0.15)');
  const tag = page.locator('.TagLabel').first();
  await expect(tag).toHaveCSS('padding', '0px 10px');
  await expect(tag).toHaveCSS('border', '1px solid rgb(10, 81, 194)');
  await expect(page.locator('.dropdown-caret').first()).toHaveCSS('border-top-width', '4px');
  await expect(page.locator('details.bibtex > div')).toHaveCSS('display', 'none');
});

test('search form keeps its look', async ({ page }) => {
  await page.goto('/search/');
  await expect(page.locator('#search-box')).toHaveCSS('font-size', '20px');
  const select = page.locator('#search-filter');
  await expect(select).toHaveCSS('appearance', 'auto');
  await expect(select).toHaveCSS('background-image', 'none');
});

test('search result labels keep their look', async ({ page }) => {
  await page.goto('/search/?q=abhidhamma');
  const label = page.locator('#search-results .Label').first();
  await expect(label).toHaveCSS('padding', '0px 7px');
  await expect(label).toHaveCSS('border', '1px solid rgb(208, 215, 222)');
  await expect(page.locator('#search-results .Counter').first()).toHaveCSS('background-color', 'rgba(175, 184, 193, 0.2)');
});

test('toasts keep their shadow', async ({ page }) => {
  await page.goto('/courses/imagery/tanha');
  await expect(page.locator('.Toast').first()).toHaveCSS('box-shadow', 'rgb(208, 215, 222) 0px 0px 0px 1px inset, rgba(140, 149, 159, 0.2) 0px 8px 24px 0px');
});

// purgecss -v drops variables nothing reads, so this fails if Primer stops reading one of our tokens
test('Primer still reads every token we set', async ({ page }) => {
  const tokens = readFileSync('_sass/primer.scss', 'utf8').match(/^\s+--[\w-]+(?=:)/gm)!.map(t => t.trim());
  await page.goto('/');
  const unread = await page.evaluate(ts => ts.filter(t => !getComputedStyle(document.documentElement).getPropertyValue(t)), tokens);
  expect(unread).toEqual([]);
});
