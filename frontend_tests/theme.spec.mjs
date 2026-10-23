// 0.26.5.3 (GitHub #17 + community): theme support and styles of card-mod / UIX.
//
// * The default design is unchanged; every colour reads a --freshairiq-* variable
//   with the original colour as fallback, so themes can override it.
// * "theme: auto" takes background, border, radius, shadow, text and accent from
//   the active Home Assistant theme and keeps coloured text readable.
// * Styles that card-mod / UIX add to the card survive every refresh: the
//   <ha-card> element stays the same and foreign nodes are not removed.
import { test, expect } from '@playwright/test';
import { loadCard } from './harness.mjs';

const LIGHT = {
  '--primary-text-color': '#212121', '--secondary-text-color': '#727272', '--primary-color': '#03a9f4',
  '--rgb-primary-color': '3,169,244', '--rgb-primary-text-color': '33,33,33', '--card-background-color': '#ffffff',
  '--primary-background-color': '#fafafa', '--divider-color': 'rgba(0,0,0,.12)',
};
const GLASS = {
  '--primary-text-color': '#ffffff', '--secondary-text-color': 'rgba(255,255,255,.7)', '--primary-color': '#8fe3c3',
  '--rgb-primary-color': '143,227,195', '--rgb-primary-text-color': '255,255,255', '--card-background-color': 'rgba(30,60,50,.55)',
  '--primary-background-color': '#24423a', '--ha-card-background': 'rgba(255, 255, 255, 0.07)', '--ha-card-border-width': '0.5px',
  '--ha-card-border-color': 'rgba(255, 255, 255, 0.22)', '--ha-card-border-radius': '18px', '--ha-card-backdrop-filter': 'blur(18px)',
};

async function mount(page, config = {}, theme = {}) {
  const errors = [];
  page.on('pageerror', err => errors.push(String(err)));
  await loadCard(page, `<!doctype html><html><head><meta name="viewport" content="width=device-width, initial-scale=1"></head><body><main><freshairiq-card id="card"></freshairiq-card></main></body></html>`);
  await page.evaluate(({ config, theme }) => {
    // Stand-in for Home Assistant's ha-card (its own :host styles read the theme).
    if (!customElements.get('ha-card')) customElements.define('ha-card', class extends HTMLElement {
      constructor() { super(); this.attachShadow({ mode: 'open' }).innerHTML = '<style>:host{display:block;background:var(--ha-card-background,var(--card-background-color,#fff));border-radius:var(--ha-card-border-radius,12px);border:var(--ha-card-border-width,1px) solid var(--ha-card-border-color,#e0e0e0)}</style><slot></slot>'; }
    });
    Object.entries(theme).forEach(([key, value]) => document.documentElement.style.setProperty(key, value));
    const rooms = {
      bad: { key: 'bad', name: 'Bad', calculation_enabled: true, data_quality: 'ok', temperature: 21, humidity: 68, absolute_humidity: 12,
        action: 'Ventilate', potential_ml: 180, surface_rh: 82, mould_level: 'High', active: false },
      flur: { key: 'flur', name: 'Flur', calculation_enabled: true, data_quality: 'ok', temperature: 20, humidity: 55, absolute_humidity: 9,
        action: 'Okay', potential_ml: 20, surface_rh: 60, mould_level: 'Low', active: false },
    };
    const status = { entity_id: 'sensor.freshairiq_status', state: 'ventilate', attributes: {
      freshairiq_transport: 'status_v2', freshairiq_version: '0.26.5.3', rooms, room_sort_order: Object.keys(rooms),
      intelligent_recommendation: { kind: 'ventilate', title: 'Jetzt lüften', room_keys: ['bad'] },
    } };
    const card = document.getElementById('card');
    card.setConfig(config);
    card.hass = { states: { [status.entity_id]: status } };
    window.__status = status;
  }, { config, theme });
  await page.waitForTimeout(80);
  return errors;
}

const refresh = page => page.locator('#card').evaluate(card => {
  const status = { ...window.__status, attributes: { ...window.__status.attributes, refreshed: Date.now() } };
  card.hass = { states: { [status.entity_id]: status } };
  card._render();
});

test('styles added by card-mod / UIX survive every refresh', async ({ page }) => {
  const errors = await mount(page);
  await page.locator('#card').evaluate(card => {
    window.__haCard = card.shadowRoot.querySelector('ha-card');
    const style = document.createElement('style');
    style.id = 'uix-style';
    style.textContent = 'ha-card{border-radius:5px!important;background:rgb(10, 20, 30)!important}.card{padding:3px!important}';
    card.shadowRoot.appendChild(style);
    window.__haCard.appendChild(document.createElement('card-mod'));
    window.__haCard.setAttribute('style', 'outline:1px solid red');
  });
  for (let i = 0; i < 3; i++) await refresh(page);
  const state = await page.locator('#card').evaluate(card => {
    const haCard = card.shadowRoot.querySelector('ha-card');
    return {
      same: haCard === window.__haCard, cards: card.shadowRoot.querySelectorAll('ha-card').length,
      style: !!card.shadowRoot.getElementById('uix-style'), cardMod: !!haCard.querySelector(':scope > card-mod'),
      inline: haCard.getAttribute('style'), radius: getComputedStyle(haCard).borderTopLeftRadius,
      background: getComputedStyle(haCard).backgroundColor, padding: getComputedStyle(card.shadowRoot.querySelector('.card')).paddingTop,
      content: card.shadowRoot.querySelectorAll('.card').length,
    };
  });
  expect(state).toEqual({ same: true, cards: 1, style: true, cardMod: true, inline: 'outline:1px solid red', radius: '5px',
    background: 'rgb(10, 20, 30)', padding: '3px', content: 1 });
  expect(errors).toEqual([]);
});

test('the default design keeps its own look and offers override variables', async ({ page }) => {
  await mount(page, {}, LIGHT);
  const look = await page.locator('#card').evaluate(card => {
    const haCard = card.shadowRoot.querySelector('ha-card');
    const cs = getComputedStyle(haCard);
    return { theme: card.getAttribute('data-freshairiq-theme'), radius: cs.borderTopLeftRadius, color: cs.color, image: cs.backgroundImage.slice(0, 15) };
  });
  // a light HA theme does not change the FreshAirIQ design
  expect(look).toEqual({ theme: 'freshairiq', radius: '22px', color: 'rgb(233, 240, 244)', image: 'radial-gradient' });
  const overridden = await page.locator('#card').evaluate(card => {
    card.style.setProperty('--freshairiq-text-color', 'rgb(1, 2, 3)');
    card.style.setProperty('--freshairiq-card-background', 'rgb(4, 5, 6)');
    card.style.setProperty('--freshairiq-card-border-radius', '7px');
    const haCard = card.shadowRoot.querySelector('ha-card');
    const cs = getComputedStyle(haCard);
    return { color: cs.color, background: cs.backgroundColor, radius: cs.borderTopLeftRadius };
  });
  expect(overridden).toEqual({ color: 'rgb(1, 2, 3)', background: 'rgb(4, 5, 6)', radius: '7px' });
});

const luminance = ([r, g, b]) => {
  const f = c => { c /= 255; return c <= 0.03928 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4; };
  return 0.2126 * f(r) + 0.7152 * f(g) + 0.0722 * f(b);
};

test('theme: auto follows a light theme and keeps text readable', async ({ page }) => {
  const errors = await mount(page, { theme: 'auto' }, LIGHT);
  const look = await page.locator('#card').evaluate(card => {
    const haCard = card.shadowRoot.querySelector('ha-card');
    const cs = getComputedStyle(haCard);
    const colours = [...card.shadowRoot.querySelectorAll('.card *')]
      .filter(el => el.childElementCount === 0 && (el.textContent || '').trim() && el.getClientRects().length)
      .map(el => ({ text: el.textContent.trim().slice(0, 30), color: getComputedStyle(el).color }));
    return { theme: card.getAttribute('data-freshairiq-theme'), background: cs.backgroundColor, image: cs.backgroundImage, radius: cs.borderTopLeftRadius, color: cs.color, colours };
  });
  expect(look.theme).toBe('auto');
  expect(look.background).toBe('rgb(255, 255, 255)');
  expect(look.image).toBe('none');
  expect(look.radius).toBe('12px');
  expect(look.color).toBe('rgb(33, 33, 33)');
  const parse = c => (c.match(/[\d.]+/g) || []).slice(0, 3).map(Number);
  const white = luminance([255, 255, 255]);
  const weak = look.colours.filter(({ color }) => {
    const alpha = Number((color.match(/[\d.]+/g) || [])[3] ?? 1);
    if (alpha < 0.5) return false;
    return (white + 0.05) / (luminance(parse(color)) + 0.05) < 3;
  });
  expect(look.colours.length).toBeGreaterThan(5);
  expect(weak).toEqual([]);
  expect(errors).toEqual([]);
});

test('theme: auto takes a transparent glass theme incl. border and blur', async ({ page }) => {
  await mount(page, { theme: 'auto' }, GLASS);
  const look = await page.locator('#card').evaluate(card => {
    const cs = getComputedStyle(card.shadowRoot.querySelector('ha-card'));
    // Chromium rounds a 0.5px border up to 1px on 1x screens: read the value handed over
    const border = getComputedStyle(card).getPropertyValue('--freshairiq-card-border-width').trim();
    return { background: cs.backgroundColor, radius: cs.borderTopLeftRadius, border, borderColor: cs.borderTopColor,
      blur: cs.backdropFilter || cs.webkitBackdropFilter, color: cs.color };
  });
  expect(look).toEqual({ background: 'rgba(255, 255, 255, 0.07)', radius: '18px', border: '0.5px', borderColor: 'rgba(255, 255, 255, 0.22)',
    blur: 'blur(18px)', color: 'rgb(255, 255, 255)' });
});

test('switching the theme back restores the FreshAirIQ design; aliases are accepted', async ({ page }) => {
  await mount(page, { theme: 'auto' }, LIGHT);
  const results = await page.locator('#card').evaluate(card => {
    const read = () => getComputedStyle(card.shadowRoot.querySelector('ha-card')).borderTopLeftRadius;
    const out = [read()];
    card.setConfig({}); out.push(read(), card.getAttribute('data-freshairiq-theme'));
    card.setConfig({ theme: 'native' }); out.push(card.getAttribute('data-freshairiq-theme'));
    card.setConfig({ transparent_background: true }); out.push(card.getAttribute('data-freshairiq-theme'));
    card.setConfig({ theme: 'whatever' }); out.push(card.getAttribute('data-freshairiq-theme'));
    return out;
  });
  expect(results).toEqual(['12px', '22px', 'freshairiq', 'auto', 'auto', 'freshairiq']);
});

test('the card editor offers the theme', async ({ page }) => {
  await loadCard(page, '<!doctype html><html><body><freshairiq-card-editor id="ed"></freshairiq-card-editor></body></html>');
  const result = await page.evaluate(async () => {
    const editor = document.getElementById('ed');
    editor.hass = { language: 'de', states: {} };
    editor.setConfig({});
    await new Promise(r => setTimeout(r, 50));
    const select = editor.shadowRoot.getElementById('card-theme');
    const events = [];
    editor.addEventListener('config-changed', e => events.push(e.detail.config.theme));
    select.value = 'auto';
    select.dispatchEvent(new Event('change'));
    return { options: [...select.options].map(o => o.value), selected: select.value, events };
  });
  expect(result.options).toEqual(['freshairiq', 'auto']);
  expect(result.events).toEqual(['auto']);
});
