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
  // 0.26.5.4 (audit S14): a named Home Assistant theme ("whatever") is no longer read as the FreshAirIQ design
  expect(results).toEqual(['12px', '22px', 'freshairiq', 'auto', 'auto', 'auto']);
});

// 0.26.5.4 (audit S14): "theme" is Lovelace's key for a named Home Assistant theme. The FreshAirIQ look is
// "freshairiq_design"; the old values theme: auto / native / freshairiq keep working.
test('a named Home Assistant theme stays the theme, the FreshAirIQ look is freshairiq_design', async ({ page }) => {
  await mount(page, {}, LIGHT);
  const results = await page.locator('#card').evaluate(card => {
    const read = config => { card.setConfig(config); return [card.getAttribute('data-freshairiq-theme'), card._config.theme, card._config.freshairiq_design]; };
    return [
      read({ theme: 'FrostedGlass' }),
      read({ theme: 'FrostedGlass', freshairiq_design: 'freshairiq' }),
      read({ freshairiq_design: 'auto' }),
      read({ theme: 'freshairiq' }),
      read({}),
    ];
  });
  expect(results).toEqual([
    ['auto', 'FrostedGlass', 'auto'],
    ['freshairiq', 'FrostedGlass', 'freshairiq'],
    ['auto', 'auto', 'auto'],
    ['freshairiq', 'freshairiq', 'freshairiq'],
    ['freshairiq', 'freshairiq', 'freshairiq'],
  ]);
});

test('the editor keeps a named Home Assistant theme when the design is changed', async ({ page }) => {
  await loadCard(page, '<!doctype html><html><body><freshairiq-card-editor id="ed"></freshairiq-card-editor></body></html>');
  const result = await page.evaluate(async () => {
    const editor = document.getElementById('ed');
    editor.hass = { language: 'de', states: {} };
    editor.setConfig({ theme: 'FrostedGlass' });
    await new Promise(r => setTimeout(r, 50));
    const select = editor.shadowRoot.getElementById('card-theme');
    const events = [];
    editor.addEventListener('config-changed', e => events.push([e.detail.config.theme, e.detail.config.freshairiq_design]));
    const before = select.value;
    select.value = 'freshairiq';
    select.dispatchEvent(new Event('change'));
    return { before, events };
  });
  expect(result.before).toBe('auto');
  expect(result.events).toEqual([['FrostedGlass', 'freshairiq']]);
});

// 0.26.5.4 (support case support-ff65eea96f68094a0640aec0): with a glass theme,
// UIX or card-mod styles on the card (blur, transform) the dialogs stayed inside
// the card. They now cover the screen and keep the theme and the foreign styles.
for (const [name, config, theme] of [['FreshAirIQ design', {}, {}], ['theme: auto with a glass theme', { theme: 'auto' }, GLASS], ['theme: auto with a light theme', { theme: 'auto' }, LIGHT]]) {
  test(`dialogs cover the screen with UIX / card-mod styles – ${name}`, async ({ page }) => {
    await page.setViewportSize({ width: 390, height: 844 });
    const errors = await mount(page, config, theme);
    const result = await page.locator('#card').evaluate(async card => {
      const style = document.createElement('style');
      style.id = 'uix-style';
      style.textContent = 'ha-card{transform:translateZ(0);backdrop-filter:blur(18px);contain:paint;overflow:hidden!important}';
      card.shadowRoot.appendChild(style);
      const haCard = card.shadowRoot.querySelector('ha-card');
      haCard.appendChild(document.createElement('card-mod'));
      const read = () => {
        const sub = card.shadowRoot.querySelector('.submodal');
        const box = sub.getBoundingClientRect();
        const dialog = card.shadowRoot.querySelector('.subdialog');
        return { full: Math.round(box.height) === innerHeight && Math.round(box.width) === innerWidth && Math.round(box.top) === 0,
          background: getComputedStyle(sub).backgroundColor, dialogColor: getComputedStyle(dialog).color, border: getComputedStyle(sub).borderTopWidth };
      };
      const out = {};
      for (const view of ['rooms', 'room:bad', 'support', 'guests', 'settings']) {
        card._info = view; card._render();
        await new Promise(r => setTimeout(r, 60));
        out[view] = read();
        if (view === 'room:bad') {
          // the explanation window of a tile lies above the room dialog, also after a refresh
          card.shadowRoot.querySelector('[data-explain]').click();
          await new Promise(r => setTimeout(r, 30));
          card._render();
          await new Promise(r => setTimeout(r, 30));
          const sheet = card.shadowRoot.querySelector('.explain-backdrop');
          const box = sheet.getBoundingClientRect();
          const hit = card.shadowRoot.elementFromPoint(innerWidth / 2, innerHeight - 30);
          out.explain = { full: Math.round(box.height) === innerHeight, onTop: !!(hit && hit.closest('.explain-backdrop')) };
          card.shadowRoot.querySelector('[data-explain-close]').click();
          out.explainClosed = !card.shadowRoot.querySelector('.explain-backdrop');
        }
      }
      card._info = null; card._render();
      out.after = { overlays: card.shadowRoot.querySelectorAll('.modal,.submodal').length, sameCard: card.shadowRoot.querySelector('ha-card') === haCard,
        uix: !!card.shadowRoot.getElementById('uix-style'), cardMod: !!haCard.querySelector(':scope > card-mod'),
        transform: getComputedStyle(haCard).transform !== 'none' };
      out.cardColor = getComputedStyle(haCard).color;
      return out;
    });
    for (const view of ['rooms', 'room:bad', 'support', 'guests', 'settings']) {
      expect(result[view].full).toBe(true);
      expect(result[view].border).toBe('0px');  // no browser frame around the dialog
      expect(result[view].background).not.toBe('rgb(255, 255, 255)');  // the dialog's own backdrop, not the browser default
    }
    expect(result.explain).toEqual({ full: true, onTop: true });
    expect(result.explainClosed).toBe(true);
    expect(result.after).toEqual({ overlays: 0, sameCard: true, uix: true, cardMod: true, transform: true });
    expect(errors).toEqual([]);
  });
}

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
