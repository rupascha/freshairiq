// Hotfix 31.10.: "Experiment: Neue Feuchteformel (passiver Test)" was missing in the iOS detail view.
// The real loading path: the card is loaded as Home Assistant registers it (freshairiq-card.js?v=<version>&b=<build>),
// every part it imports must carry the same query. Reproduced cause: under the unchanged URL ?v=0.26.5.5 a cached
// freshairiq-card-data.js of an older build (without the section) is used. Also a failed or delayed download,
// repeated updates and only the quality view.
import { test, expect } from '@playwright/test';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const FRONTEND = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../custom_components/freshairiq/frontend');
const ORIGIN = 'http://freshairiq.test';
const DATA = fs.readFileSync(path.join(FRONTEND, 'freshairiq-card-data.js'), 'utf8');
// freshairiq-card-data.js as built before the section existed: the same file without the section import.
const STALE_DATA = DATA.slice(0, DATA.indexOf('// 0.26.5.5: passive test of a new moisture formula'));

async function load(page, query, { serve = null } = {}) {
  const requests = [];
  page.on('pageerror', err => requests.push(`pageerror ${err}`));
  await page.route(`${ORIGIN}/**`, async route => {
    const url = new URL(route.request().url());
    if (url.pathname === '/') return route.fulfill({ contentType: 'text/html', body: '<!doctype html><html><head><meta name="viewport" content="width=device-width, initial-scale=1"></head><body><freshairiq-card id="card"></freshairiq-card></body></html>' });
    requests.push(path.basename(url.pathname) + url.search);
    const custom = serve && await serve(path.basename(url.pathname), url.search, route);
    if (custom === 'handled') return;
    if (custom) return route.fulfill({ contentType: 'text/javascript', body: custom });
    const file = path.join(FRONTEND, path.basename(url.pathname));
    if (!fs.existsSync(file)) return route.fulfill({ status: 404, body: '' });
    return route.fulfill({ path: file, contentType: 'text/javascript' });
  });
  await page.goto(`${ORIGIN}/`);
  await page.addScriptTag({ url: `${ORIGIN}/freshairiq-card.js${query}`, type: 'module' });
  await page.waitForFunction(() => !!customElements.get('freshairiq-card'));
  return requests;
}

// Open "Details → Aktuell lernt FreshAirIQ → Wie gut FreshAirIQ aktuell vorhersagt" with the given comparison.
const quality = (page, { comparison = undefined, language = 'de', info = 'learning:quality' } = {}) => page.evaluate(async ({ comparison, language, info }) => {
  const attributes = { freshairiq_transport: 'status_v2', freshairiq_version: '0.26.5.5', rooms: {}, room_sort_order: [],
    learning_components: { overall_maturity_percent: 10, components: [] }, forecast_backtest: { reliability: { score_percent: 44 } },
    learning_effectiveness: { samples: 4, independent_sessions: 2 }, diagnostics: { retention_days: 30 } };
  if (comparison !== undefined) attributes.forecast_shadow_comparison = comparison;
  const card = document.getElementById('card');
  card.setConfig({});
  card.hass = { language, locale: { language }, states: { 'sensor.freshairiq_status': { entity_id: 'sensor.freshairiq_status', state: 'ok', attributes } } };
  card._info = info;
  card._render();
  if (language === 'en') { await new Promise(r => setTimeout(r, 500)); card._render(); }
  const panel = card.shadowRoot.querySelector('.learning-detail-panel');
  const sections = panel ? [...panel.querySelectorAll('.faiq-shadow-test')] : [];
  return { count: sections.length, text: sections.map(s => s.textContent.replace(/\s+/g, ' ').trim()).join(' | '),
    last: !!(sections.length && panel.lastElementChild === sections[0]), failed: sections.some(s => s.classList.contains('faiq-shadow-failed')),
    overflow: panel ? Math.max(0, panel.scrollWidth - panel.clientWidth, document.documentElement.scrollWidth - window.innerWidth) : -1 };
}, { comparison, language, info });

const BUILD = '?v=0.26.5.5&b=3f2a9c1d0b7e';

test('every module of the card carries the version and build of the registered resource URL', async ({ page }) => {
  const requests = await load(page, BUILD);
  await quality(page, { language: 'en' });  // also the English text module
  await page.evaluate(() => document.body.appendChild(document.createElement('freshairiq-house-card')));  // and the house map parts
  await page.waitForFunction(() => !!customElements.get('freshairiq-house-card-impl'));
  const modules = requests.filter(r => r.includes('.js'));
  for (const name of ['freshairiq-card.js', 'freshairiq-card-data.js', 'freshairiq-card-shadow.js', 'freshairiq-card-style.js', 'freshairiq-card-i18n-en.js',
    'freshairiq-card-house.js', 'freshairiq-house-card.js', 'freshairiq-house-geometry.js', 'freshairiq-house-view.js']) expect(modules).toContain(name + BUILD);
  expect(modules.filter(r => !r.endsWith(BUILD))).toEqual([]);
  expect(requests.filter(r => r.startsWith('pageerror'))).toEqual([]);
});

test('reproduced cause: a cached older data module under the unchanged URL hides the section – a new build URL does not', async ({ page, browser }) => {
  // The "cache" answers the old URL ?v=0.26.5.5 with the older build of the data module, as WebKit did.
  const serve = (name, search) => (name === 'freshairiq-card-data.js' && search === '?v=0.26.5.5' ? STALE_DATA : null);
  await load(page, '?v=0.26.5.5', { serve });
  expect((await quality(page, { comparison: null })).count).toBe(0);  // what the screenshot shows
  const fresh = await browser.newPage();
  await load(fresh, BUILD, { serve });
  const out = await quality(fresh, { comparison: null });
  expect(out.count).toBe(1);
  expect(out.text).toContain('Noch kein Vergleich');
  await fresh.close();
});

for (const [language, head, empty, pairs] of [['de', 'Experiment: Neue Feuchteformel (passiver Test)', 'Noch kein Vergleich', '85 vergleichbare Lüftungen'],
                                                ['en', 'Experiment: new moisture formula (passive test)', 'No comparison yet', '85 comparable airings']]) {
  test(`iPhone width, ${language}: the section shows with no payload, 0 samples and real samples, also after repeated updates`, async ({ page }) => {
    await page.setViewportSize({ width: 390, height: 844 });
    await load(page, BUILD);
    for (const comparison of [undefined, null, { samples: 0, status: 'no_data' }]) {
      const out = await quality(page, { comparison, language });
      expect(out.count, JSON.stringify(comparison)).toBe(1);
      expect(out.text).toContain(head);
      expect(out.text).toContain(empty);
      expect(out.last && out.overflow <= 2).toBe(true);
    }
    const better = { samples: 85, status: 'candidate_better', production_mae_ml: 24, candidate_mae_ml: 21, mae_difference_ml: -3, improvement_percent: 12.5 };
    for (let i = 0; i < 5; i += 1) {  // repeated live updates and re-renders: one section, current numbers
      const out = await quality(page, { comparison: { ...better, samples: 81 + i }, language });
      expect(out.count).toBe(1);
      expect(out.text).toContain(pairs.replace('85', String(81 + i)));
    }
    // leaving the view and coming back
    expect((await quality(page, { comparison: better, language, info: 'learning:home' })).count).toBe(0);  // only the quality view
    expect((await quality(page, { comparison: better, language })).text).toContain(pairs);
  });
}

test('a delayed section module: the card waits for it and the section is there from the first render', async ({ page }) => {
  const serve = async name => {
    if (name !== 'freshairiq-card-shadow.js') return null;
    await new Promise(r => setTimeout(r, 1500));
    return null;
  };
  await load(page, BUILD, { serve });
  const out = await quality(page, { comparison: { samples: 0, status: 'no_data' } });
  expect(out.count).toBe(1);
  expect(out.failed).toBe(false);
});

for (const language of ['de', 'en']) {
  test(`a failed download of the section shows why instead of hiding it (${language})`, async ({ page }) => {
    const serve = async (name, search, route) => {
      if (name !== 'freshairiq-card-shadow.js') return null;
      await route.fulfill({ status: 404, body: '' });
      return 'handled';
    };
    await page.setViewportSize({ width: 390, height: 844 });
    const requests = await load(page, BUILD, { serve });
    const out = await quality(page, { comparison: { samples: 3, status: 'collecting' }, language });
    expect(out.count).toBe(1);
    expect(out.failed && out.last && out.overflow <= 2).toBe(true);
    expect(out.text).toContain(language === 'de' ? 'Experiment: Neue Feuchteformel (passiver Test)' : 'Experiment: new moisture formula (passive test)');
    expect(out.text).toContain(language === 'de' ? 'konnte auf diesem Gerät nicht geladen werden' : 'could not be loaded on this device');
    expect(out.text).toContain('FAIQ-UI-SHADOW-001');
    expect((await quality(page, { info: 'learning:home', language })).count).toBe(0);
    expect(requests.filter(r => r.startsWith('pageerror'))).toEqual([]);
  });
}
