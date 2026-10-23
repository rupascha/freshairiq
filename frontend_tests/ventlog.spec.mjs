// 0.26.5.3 (user feedback): ventilation log per day and as CSV in the details view.
import { test, expect } from '@playwright/test';
import { loadCard } from './harness.mjs';

async function mount(page, language = 'de') {
  const errors = [];
  page.on('pageerror', err => errors.push(String(err)));
  await loadCard(page, '<!doctype html><html><body><main><freshairiq-card id="card"></freshairiq-card></main></body></html>');
  await page.evaluate(language => {
    window.__calls = [];
    window.__downloads = [];
    URL.createObjectURL = blob => { window.__downloads.push({ type: blob.type, size: blob.size }); return 'blob:x'; };
    URL.revokeObjectURL = () => {};
    HTMLAnchorElement.prototype.click = function () { window.__downloads.push({ name: this.download }); };
    const rooms = { bad: { key: 'bad', name: 'Bad', calculation_enabled: true, data_quality: 'ok', temperature: 21, humidity: 60,
      absolute_humidity: 11, action: 'Okay', potential_ml: 20, surface_rh: 60, mould_level: 'Low', active: false } };
    const status = { entity_id: 'sensor.freshairiq_status', state: 'ok', attributes: {
      freshairiq_transport: 'status_v2', freshairiq_entry_id: 'entry1', freshairiq_version: '0.26.5.3', output_language: language,
      rooms, room_sort_order: ['bad'] } };
    const card = document.getElementById('card');
    card.setConfig({ dashboard_variant: 'classic' });
    card.hass = { states: { [status.entity_id]: status }, language, locale: { language },
      callApi: async (method, path) => {
        window.__calls.push(path);
        if (path.includes('format=csv')) return { filename: 'FreshAirIQ-Lueftungsprotokoll-pro-Tag.csv', csv: '﻿Datum;Lüftungen\r\n' };
        return { filename: 'FreshAirIQ-Lueftungsprotokoll.pdf', pdf_base64: btoa('%PDF-1.4') };
      } };
    card._dialogOpen = true;
    card._render();
  }, language);
  await page.waitForTimeout(150);
  return errors;
}

const html = page => page.locator('#card').evaluate(card => card.shadowRoot.querySelector('#ventlog-csv')?.closest('div').innerHTML || '');

test('per day and CSV controls sit next to the PDF button and build the right request', async ({ page }) => {
  const errors = await mount(page);
  const controls = await html(page);
  expect(controls).toContain('Pro Tag zusammenfassen');
  expect(controls).toContain('Als CSV');
  expect(controls).toContain('id="ventlog-export"');
  await page.locator('#card').evaluate(async card => {
    const box = card.shadowRoot.getElementById('ventlog-daily');
    box.checked = true; box.dispatchEvent(new Event('change'));
    card.shadowRoot.getElementById('ventlog-csv').click();
  });
  await page.waitForTimeout(100);
  const calls = await page.evaluate(() => window.__calls.filter(p => p.startsWith('freshairiq/ventilation-log/')));
  expect(calls).toHaveLength(1);
  expect(calls[0]).toMatch(/^freshairiq\/ventilation-log\/entry1\?start=\d{4}-\d\d-\d\d&end=\d{4}-\d\d-\d\d&group=day&format=csv$/);
  expect(await page.evaluate(() => window.__downloads)).toEqual([{ type: 'text/csv;charset=utf-8', size: 21 }, { name: 'FreshAirIQ-Lueftungsprotokoll-pro-Tag.csv' }]);  // BOM + 2 lines
  // the choice survives a re-render, and the PDF button uses it too
  await page.locator('#card').evaluate(card => card._render());
  expect(await page.locator('#card').evaluate(card => card.shadowRoot.getElementById('ventlog-daily').checked)).toBe(true);
  await page.locator('#card').evaluate(card => card.shadowRoot.getElementById('ventlog-export').click());
  await page.waitForTimeout(100);
  const pdfCall = (await page.evaluate(() => window.__calls.filter(p => p.startsWith('freshairiq/ventilation-log/'))))[1];
  expect(pdfCall).toMatch(/&group=day$/);
  expect((await page.evaluate(() => window.__downloads))[2]).toEqual({ type: 'application/pdf', size: 8 });
  expect(errors).toEqual([]);
});

test('English dashboards get English controls', async ({ page }) => {
  await mount(page, 'en');
  const controls = await html(page);
  expect(controls).toContain('Summarise per day');
  expect(controls).toContain('As CSV');
});
