// 0.26.5.5: Home Assistant loads only freshairiq-card.js. The house map card must be registered
// from there (it used to be registered by the old loader only and never appeared in the card
// picker), and "Darstellung" of the FreshAirIQ card offers it next to Klassisch and FreshAirIQ IQ.
import { test, expect } from '@playwright/test';
import { loadCard } from './harness.mjs';

const PAGE = '<!doctype html><html><body><main id="m"></main></body></html>';

test('the card module registers the house map card for the card picker', async ({ page }) => {
  const errors = [];
  page.on('pageerror', err => errors.push(String(err)));
  await loadCard(page, PAGE);
  await page.waitForFunction(() => !!customElements.get('freshairiq-house-card'));
  const result = await page.evaluate(async () => {
    const el = document.createElement('freshairiq-house-card');
    const before = el.getAttribute('style');
    document.getElementById('m').appendChild(el);
    el.setConfig({ auto_focus: 'hint' });
    await customElements.whenDefined('freshairiq-house-card-impl');
    await new Promise(r => setTimeout(r, 50));
    return {
      picker: (window.customCards || []).filter(c => c.type === 'freshairiq-house-card').length,
      editor: !!customElements.get('freshairiq-house-card-editor'),
      before, display: getComputedStyle(el).display, impl: el.firstElementChild?.localName,
    };
  });
  expect(result).toEqual({ picker: 1, editor: true, before: null, display: 'block', impl: 'freshairiq-house-card-impl' });
  expect(errors).toEqual([]);
});

test('"Darstellung: Hauskarte" shows the house map in place of the dashboard and switches back', async ({ page }) => {
  const errors = [];
  page.on('pageerror', err => errors.push(String(err)));
  await loadCard(page, PAGE);
  await page.evaluate(() => {
    const card = window.__card = document.createElement('freshairiq-card');
    document.getElementById('m').appendChild(card);
    card.setConfig({ dashboard_variant: 'house', layer: 'wind' });
    card.hass = { states: {}, language: 'de', locale: { language: 'de' }, user: { is_admin: true },
      connection: { subscribeMessage: async () => () => {} }, callWS: async () => ({}) };
  });
  const shown = () => page.evaluate(() => [...window.__card.shadowRoot.children].map(c => c.localName));
  await expect.poll(shown).toEqual(['freshairiq-house-card']);
  await expect.poll(() => page.evaluate(() => window.__card.shadowRoot.firstElementChild.firstElementChild?.localName)).toBe('freshairiq-house-card-impl');
  const house = await page.evaluate(() => ({ size: window.__card.getCardSize(), layer: window.__card.shadowRoot.firstElementChild._config.layer, hass: !!window.__card.shadowRoot.firstElementChild.hass }));
  expect(house).toEqual({ size: 8, layer: 'wind', hass: true });
  // A state update keeps the house map (the dashboard does not render over it).
  await page.evaluate(() => { window.__card.hass = Object.assign({}, window.__card.hass); window.__card._render(); });
  await expect.poll(shown).toEqual(['freshairiq-house-card']);
  await page.evaluate(() => window.__card.setConfig({ dashboard_variant: 'classic' }));
  await expect.poll(() => page.evaluate(() => !!window.__card.shadowRoot.querySelector('freshairiq-house-card'))).toBe(false);
  expect(await page.evaluate(() => window.__card.getCardSize())).toBe(5);
  expect(errors).toEqual([]);
});

test('the card editor offers "Hauskarte (Grundriss)" and the house map editor can switch back', async ({ page }) => {
  const errors = [];
  page.on('pageerror', err => errors.push(String(err)));
  await loadCard(page, PAGE);
  await page.evaluate(() => {
    window.__events = [];
    const editor = window.__editor = document.createElement('freshairiq-card-editor');
    editor.addEventListener('config-changed', e => window.__events.push(e.detail.config));
    document.getElementById('m').appendChild(editor);
    editor.setConfig({ dashboard_variant: 'classic' });
    editor.hass = { states: {}, language: 'de', locale: { language: 'de' }, user: { is_admin: true } };
  });
  const options = () => page.evaluate(() => {
    const select = window.__editor.shadowRoot.getElementById('dashboard-variant');
    return select ? [...select.options].map(o => [o.value, o.textContent]) : null;
  });
  const expected = [['classic', 'Klassisch'], ['iq', 'FreshAirIQ IQ'], ['house', 'Hauskarte (Grundriss)']];
  await expect.poll(options).toEqual(expected);
  await page.evaluate(() => {
    const select = window.__editor.shadowRoot.getElementById('dashboard-variant');
    select.value = 'house';
    select.dispatchEvent(new Event('change', { bubbles: true, composed: true }));
  });
  // Exactly one change, to the house map (the classic/IQ handler would have made it "iq").
  const first = await page.evaluate(() => window.__events.map(c => c.dashboard_variant));
  expect(first).toEqual(['house']);
  // Home Assistant answers with the new config.
  await page.evaluate(() => window.__editor.setConfig(window.__events[0]));
  await expect.poll(() => page.evaluate(() => [...window.__editor.shadowRoot.children].map(c => c.localName))).toEqual(['div', 'freshairiq-house-card-editor']);
  await expect.poll(() => page.evaluate(() => window.__editor.shadowRoot.querySelector('freshairiq-house-card-editor').querySelector('[data-k="auto_focus"]') !== null)).toBe(true);
  // An echo of the same config and a hass update keep the house map editor.
  await page.evaluate(() => { window.__editor.setConfig(window.__events[0]); window.__editor.hass = Object.assign({}, window.__editor.hass); });
  const head = await page.evaluate(() => window.__editor.shadowRoot.getElementById('faiq-dashboard-variant').value);
  expect(head).toBe('house');
  await page.evaluate(() => {
    const select = window.__editor.shadowRoot.getElementById('faiq-dashboard-variant');
    select.value = 'iq';
    select.dispatchEvent(new Event('change'));
  });
  expect(await page.evaluate(() => window.__events.at(-1).dashboard_variant)).toBe('iq');
  await page.evaluate(() => window.__editor.setConfig(window.__events.at(-1)));
  await expect.poll(options).toEqual(expected);
  expect(await page.evaluate(() => window.__editor.shadowRoot.getElementById('dashboard-variant').value)).toBe('iq');
  expect(errors).toEqual([]);
});
