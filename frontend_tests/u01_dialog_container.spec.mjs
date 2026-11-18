// U01 (0.26.7.1): the detail window follows its own width (#20, Vivaldi report: a narrow window inside a wide browser
// kept four tightly packed statistic columns). The layout rules of narrow screens now also apply to a narrow window.
import { test, expect } from '@playwright/test';
import fs from 'node:fs';
import { loadCard } from './harness.mjs';

async function mount(page) {
  const errors = [];
  page.on('pageerror', err => errors.push(String(err)));
  await loadCard(page, '<!doctype html><html><head><meta name="viewport" content="width=device-width, initial-scale=1"></head><body><main><freshairiq-card id="card"></freshairiq-card></main></body></html>');
  await page.evaluate(() => {
    const rooms = {};
    for (let i = 0; i < 6; i++) rooms[`r${i}`] = { key: `r${i}`, name: `Wohn- und Arbeitszimmer ${i + 1}`, calculation_enabled: true, data_quality: 'ok',
      temperature: 21.2, humidity: 61, absolute_humidity: 11.0, action: i % 2 ? 'Ventilate' : 'Okay', potential_ml: 12345 + i, surface_rh: 72, mould_level: 'Low', active: false };
    const status = { entity_id: 'sensor.freshairiq_status', state: 'ok', attributes: { freshairiq_transport: 'status_v2', rooms, room_sort_order: Object.keys(rooms), diagnostics: { retention_days: 30 } } };
    const card = document.getElementById('card'); card.setConfig({}); card.hass = { language: 'de', locale: { language: 'de' }, states: { [status.entity_id]: status } };
  });
  await page.waitForTimeout(80);
  await page.locator('#details').click();
  await page.waitForTimeout(120);
  return errors;
}

// every grid in the window: no column narrower than its content, no two cells overlapping, nothing wider than the window
const layout = (page, width) => page.locator('#card').evaluate((card, width) => {
  const dlg = card.shadowRoot.querySelector('.dialog');
  if (width) dlg.style.width = `${width}px`;
  void dlg.offsetWidth;
  const box = dlg.getBoundingClientRect();
  const grids = [...dlg.querySelectorAll('.metrics,.overview,.info-grid,.history-grid,.learn-quality-strip,.result-metrics')].filter(g => g.offsetParent);
  const problems = [];
  let maxCols = 0;
  for (const g of grids) {
    const cols = getComputedStyle(g).gridTemplateColumns.split(' ').filter(Boolean).length;
    maxCols = Math.max(maxCols, cols);
    const cells = [...g.children].filter(c => c.offsetParent).map(c => [c, c.getBoundingClientRect()]);
    for (const [c, r] of cells) {
      if (r.right > box.right + 1 || r.left < box.left - 1) problems.push(`${g.className}: outside`);
      if (c.scrollWidth > c.clientWidth + 2) problems.push(`${g.className}: content wider than its cell (${c.scrollWidth}>${c.clientWidth})`);
    }
    for (let i = 0; i < cells.length; i++) for (let j = i + 1; j < cells.length; j++) {
      const a = cells[i][1], b = cells[j][1];
      if (a.left < b.right - 1 && b.left < a.right - 1 && a.top < b.bottom - 1 && b.top < a.bottom - 1) problems.push(`${g.className}: overlap`);
    }
  }
  return { width: Math.round(box.width), grids: grids.length, maxCols, problems, scrollX: dlg.querySelector('.dialog-scroll').scrollWidth > dlg.querySelector('.dialog-scroll').clientWidth + 1 };
}, width);

test('U01: a 420 px detail window inside a 1440 px browser uses the narrow layout', async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 900 });
  const errors = await mount(page);
  const wide = await layout(page, null);
  const narrow = await layout(page, 420);
  expect(wide.grids).toBeGreaterThan(0);
  expect(narrow.maxCols).toBeLessThanOrEqual(2);
  expect(narrow.problems).toEqual([]);
  expect(narrow.scrollX).toBe(false);
  fs.mkdirSync('test-results/u01', { recursive: true });
  await page.screenshot({ path: 'test-results/u01/dialog-420-in-1440.png' });
  expect(errors).toEqual([]);
});

for (const width of [320, 375, 420, 768, 1024]) {
  test(`U01: detail window at ${width} px container width – no overlap, nothing outside, no sideways scroll`, async ({ page }) => {
    await page.setViewportSize({ width: Math.max(width + 40, 1280), height: 900 });
    await mount(page);
    const r = await layout(page, width);
    expect(r.problems).toEqual([]);
    expect(r.scrollX).toBe(false);
    if (width <= 650) expect(r.maxCols).toBeLessThanOrEqual(2);
    fs.mkdirSync('test-results/u01', { recursive: true });
    await page.screenshot({ path: `test-results/u01/container-${width}.png` });
  });
}
