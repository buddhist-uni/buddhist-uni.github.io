import { test, expect, Page } from '@playwright/test';

// Partial readings of larger works, which the course files mark notime
const NOTIME = [
  'booklets/fundamentals_santina-peter',
  'monographs/being-nobody-going-nowhere_khema',
  'monographs/biography-of-shakyamuni_hsing-yun',
  'booklets/noble-eightfold-path_bodhi',
  'booklets/i-wonder-why_thubten-chodron',
];

const PARTS = [
  'mindfulness', 'hearing', 'refuge', 'love', 'four-noble-truths', 'the-path',
  'karma', 'bhavana', 'anatta', 'renunciation', 'path-revisited', 'samadhi',
  'wisdom', 'conclusion',
];

const boxes = (page: Page) => page.locator('.content_box:not(.with_border)');
const timeOf = (page: Page, contentPath: string) =>
  boxes(page).filter({ has: page.locator(`[data-content-path="${contentPath}"]`) }).locator('.assignment_time');

test('assignment time integration page has no failures', async ({ page }) => {
  await page.goto('/tests/assignment-time');
  const text = await page.locator('article').innerText();
  expect(text.match(/Pass ✅/g)?.length, 'test is valid: the page has test rows').toBeGreaterThan(15);
  expect(text).not.toContain('FAIL');
});

test('Buddhism 101 assignments show their time', async ({ page }) => {
  await page.goto('/courses/buddhism/bhavana');
  await expect(timeOf(page, 'av/how-to-love-your-problems_courtin-robina')).toHaveText('(1 hr 10 mins)');
  await expect(timeOf(page, 'canon/sn42.6')).toHaveText('(15 mins)');
  await page.goto('/courses/buddhism/wisdom');
  await expect(timeOf(page, 'av/buddhism-and-the-world_bodhi')).toHaveText('(2 hrs 20 mins)');
  await page.goto('/courses/buddhism/conclusion');
  await expect(timeOf(page, 'articles/buddhism-and-modernity_powers-doug')).toHaveText('(20 mins)');
});

test('time also shows on the content_box and inline_content assignments', async ({ page }) => {
  await page.goto('/courses/buddhism/mindfulness');
  await expect(timeOf(page, 'monographs/miracle-of-mindfulness_tnh')).toHaveText('(1 hr 42 mins)');
  await page.goto('/courses/buddhism/karma');
  await expect(page.locator('.assignment_time', { hasText: '(1 hr 6 mins)' })).toHaveCount(1);
  await page.goto('/courses/buddhism/path-revisited');
  await expect(page.locator('.assignment_time', { hasText: '(1 hr 12 mins)' })).toHaveCount(1);
});

for (const part of PARTS) {
  test(`every assignment in "${part}" is timed unless marked notime`, async ({ page }) => {
    await page.goto(`/courses/buddhism/${part}`);
    const n = await boxes(page).count();
    expect(n, 'test is valid: the page has assignments').toBeGreaterThan(0);
    for (let i = 0; i < n; i++) {
      const box = boxes(page).nth(i);
      const path = (await box.locator('[data-content-path]').first().getAttribute('data-content-path')) ?? '';
      const times = box.locator('.assignment_time');
      if (NOTIME.includes(path)) await expect(times, path).toHaveCount(0);
      else await expect(times, path).toHaveText(/^\((\d+ hrs?( \d+ mins?)?|\d+ mins?)\)$/);
    }
  });
}

test('the time does not wrap on a phone', async ({ page }) => {
  await page.setViewportSize({ width: 375, height: 800 });
  await page.goto('/courses/buddhism/love');
  const lines = await page.locator('.assignment_time').evaluateAll(
    els => els.map(el => el.getClientRects().length));
  expect(lines.length).toBeGreaterThan(3);
  expect(Math.max(...lines)).toBe(1);
});

for (const url of ['/courses/function/intro', '/courses/function/bhavana', '/courses/imagery/intro', '/courses/ebts', '/courses/buddha']) {
  test(`no assignment times outside Buddhism 101: ${url}`, async ({ page }) => {
    await page.goto(url);
    await expect(page.locator('.content_box, .inline_content').first(), 'test is valid: the page has content').toBeAttached();
    await expect(page.locator('.assignment_time')).toHaveCount(0);
  });
}
