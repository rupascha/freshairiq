// Loader proxies (A-83): Lovelace, dashboard add-ons and card collections create cards with
// document.createElement. A custom element constructor must not add attributes there (Chrome:
// NotSupportedError), so the proxies set their display style only when they are connected.
import { test, expect } from '@playwright/test';
import { loadModule } from './harness.mjs';

test('every loader proxy can be created with document.createElement and is a block once shown', async ({ page }) => {
  const errors = [];
  page.on('pageerror', err => errors.push(String(err)));
  await loadModule(page, '<!doctype html><html><body><main id="m"></main></body></html>', 'freshairiq-loader.js', 'freshairiq-card');
  const result = await page.evaluate(() => ['freshairiq-card', 'freshairiq-card-editor', 'freshairiq-house-card', 'freshairiq-house-card-editor'].map(tag => {
    try {
      const el = document.createElement(tag);
      const before = el.getAttribute('style');
      document.getElementById('m').appendChild(el);
      return { tag, ok: true, before, display: getComputedStyle(el).display };
    } catch (err) { return { tag, ok: false, error: String(err) }; }
  }));
  for (const r of result) {
    expect(r, r.tag).toMatchObject({ ok: true, before: null, display: 'block' });
  }
  expect(errors.filter(e => /NotSupportedError|must not have attributes/.test(e))).toEqual([]);
});
