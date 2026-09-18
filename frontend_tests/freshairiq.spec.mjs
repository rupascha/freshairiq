import { test, expect } from '@playwright/test';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const HERE = path.dirname(fileURLToPath(import.meta.url));
const CARD = path.resolve(HERE, '../custom_components/freshairiq/frontend/freshairiq-card.js');
const viewports = [
  ['iPhone', 430, 932],
  ['iPad', 768, 1024],
  ['Android', 412, 915],
  ['Desktop', 1440, 1000],
];

async function mount(page, roomCount = 12) {
  const pageErrors = [];
  page.on('pageerror', err => pageErrors.push(String(err)));
  await page.setContent(`<!doctype html><html><head><meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover"></head><body><main><freshairiq-card id="card"></freshairiq-card></main></body></html>`);
  await page.addScriptTag({ path: CARD });
  await page.evaluate(({ roomCount }) => {
    const rooms = {};
    for (let i = 0; i < roomCount; i++) {
      rooms[`room_${i}`] = {
        key: `room_${i}`, name: `Raum ${i + 1}`, calculation_enabled: true,
        data_quality: 'ok', temperature: 21.2, humidity: 61 + (i % 5),
        absolute_humidity: 11.0, reference_absolute_humidity: 7.2,
        action: i % 3 === 0 ? 'Ventilate' : 'Okay', potential_ml: 120 + i,
        surface_rh: 72, mould_level: 'Low', active: false,
      };
    }
    const components = [
      ['room_physics', 'Raumphysik', 8, 73, '0 unterschiedliche Tage · 73 Lernlüftungen'],
      ['post_close', 'Feuchtepuffer', 20, 10, '4 unterschiedliche Tage'],
      ['house_strategy', 'Hausstrategie', 0, 61, '0 unterschiedliche Tage'],
      ['live_forecast', 'Live-Prognosemodell', 0, 12000, 'Messpunkte'],
      ['forecast_feedback', 'Prognosefeedback', 1, 10, 'Ergebnisvergleiche'],
      ['shadow_learning', 'Learning 3.0 Shadow', 0, 1, 'Realvergleich'],
      ['forecast_validation', 'Prognosevalidierung', 4, 4, '2 unterschiedliche Tage'],
      ['routines', 'Tagesroutinen', 0, 0, '0 unterschiedliche Tage'],
      ['user_strategy', 'Nutzerstrategie', 0, 10, '0 unterschiedliche Tage'],
      ['personal_context', 'Persönlicher Kontext', 0, 177, '0 unterschiedliche Tage'],
      ['seasonality', 'Saisonalität', 0, 0, '0/4 Jahreszeiten vollständig'],
      ['night_model', 'Nachtmodell', 0, 0, '122 Messupdates aus 0 unterschiedlichen Nächten'],
    ].map(([key, label, maturity_percent, samples, evidence_text]) => ({
      key, label, maturity_percent, samples, evidence_text, status: 'Grundmodell', raw_samples: key === 'night_model' ? 122 : samples,
      seasons: key === 'seasonality' ? { spring: {}, summer: {}, autumn: {}, winter: {} } : undefined,
      calendar_span_days: 0,
    }));
    const status = {
      entity_id: 'sensor.freshairiq_status', state: 'ok',
      attributes: {
        freshairiq_transport: 'status_v2', freshairiq_version: '0.25.0.35',
        rooms, room_sort_order: Object.keys(rooms),
        learning_components: { overall_maturity_percent: 0, stage_label: 'Grundmodell', components },
        forecast_backtest: { reliability: { score_percent: 44, direction_accuracy_percent: 50, magnitude_accuracy_percent: 66, mae_ml: 16 } },
        presence_confidence: 80, adult_occupants: 2, child_occupants: 2,
        diagnostics: { retention_days: 30 },
      },
    };
    const card = document.getElementById('card');
    card.setConfig({});
    card.hass = { states: { [status.entity_id]: status } };
  }, { roomCount });
  await page.waitForTimeout(80);
  return pageErrors;
}

for (const [label, width, height] of viewports) {
  test(`${label}: overview + learning drill-downs render without overflow or exceptions`, async ({ page }) => {
    await page.setViewportSize({ width, height });
    const errors = await mount(page, 12);
    await expect(page.locator('freshairiq-card')).toBeVisible();
    const overview = await page.locator('freshairiq-card').evaluate(el => el.shadowRoot.textContent);
    expect(overview).toContain('FreshAirIQ');

    for (const info of ['learning:home', 'learning:forecast', 'learning:habits', 'learning:longterm', 'learning:quality']) {
      const metrics = await page.locator('freshairiq-card').evaluate((el, target) => {
        el._info = target;
        el._render();
        const panel = el.shadowRoot.querySelector('.info-panel, .learning-detail-panel, .model-quality-panel');
        return {
          text: el.shadowRoot.textContent,
          overflow: panel ? Math.max(0, panel.scrollWidth - panel.clientWidth) : -1,
        };
      }, info);
      expect(metrics.text.length).toBeGreaterThan(40);
      expect(metrics.overflow).toBeLessThanOrEqual(2);
    }
    expect(errors).toEqual([]);
  });
}

test('50-room dashboard smoke render remains responsive', async ({ page }) => {
  await page.setViewportSize({ width: 430, height: 932 });
  const errors = await mount(page, 50);
  const timing = await page.locator('freshairiq-card').evaluate(el => {
    const samples = [];
    for (let i = 0; i < 8; i++) {
      const start = performance.now();
      el._render();
      samples.push(performance.now() - start);
    }
    samples.sort((a, b) => a - b);
    return { medianMs: samples[Math.floor(samples.length / 2)], maxMs: Math.max(...samples) };
  });
  expect(timing.medianMs).toBeLessThan(500);
  expect(timing.maxMs).toBeLessThan(1000);
  expect(errors).toEqual([]);
});


test('timestamp evidence drives truthful live learning wording', async ({ page }) => {
  await page.setViewportSize({ width: 412, height: 915 });
  const errors = await mount(page, 1);
  const waitingText = await page.locator('freshairiq-card').evaluate(el => {
    const status = el._hass.states['sensor.freshairiq_status'];
    status.attributes.rooms.room_0.active = true;
    status.attributes.rooms.room_0.session_measurement_quality = { timestamp_gate_passed: false };
    el._render();
    return el.shadowRoot.textContent;
  });
  expect(waitingText).toContain('LÜFTUNG WIRD BEOBACHTET');
  expect(waitingText).not.toContain('LERNT JETZT: IQ lernt gerade den realen Luftaustausch');

  const learningText = await page.locator('freshairiq-card').evaluate(el => {
    const status = el._hass.states['sensor.freshairiq_status'];
    status.attributes.rooms.room_0.session_measurement_quality = { timestamp_gate_passed: true };
    el._render();
    return el.shadowRoot.textContent;
  });
  expect(learningText).toContain('LERNT JETZT: IQ lernt gerade den realen Luftaustausch');
  expect(errors).toEqual([]);
});

test('Android Home Assistant WebView emulation is mobile, touch-capable and overflow-safe', async ({ page }, testInfo) => {
  test.skip(testInfo.project.name !== 'android-webview', 'Dedicated Android WebView project only');
  const errors = await mount(page, 12);
  const client = await page.locator('freshairiq-card').evaluate(el => el._fieldTestClientContext());
  expect(client.platform_family).toBe('Android');
  expect(client.device_class).toBe('phone');
  expect(client.companion_app).toBe(true);
  expect(client.touch_points).toBeGreaterThan(0);
  expect(client.device_pixel_ratio).toBeGreaterThan(1);

  for (const [width, height] of [[360, 800], [412, 915], [600, 960], [800, 1280]]) {
    await page.setViewportSize({ width, height });
    const metrics = await page.locator('freshairiq-card').evaluate(el => {
      el._render();
      const root = el.shadowRoot.querySelector('.app, .wrap, .card') || el.shadowRoot.firstElementChild;
      return {
        innerWidth: Math.round(window.innerWidth),
        documentWidth: Math.round(document.documentElement.clientWidth),
        hostOverflow: Math.max(0, el.scrollWidth - el.clientWidth),
        rootOverflow: root ? Math.max(0, root.scrollWidth - root.clientWidth) : 0,
      };
    });
    expect(metrics.innerWidth).toBe(width);
    expect(metrics.documentWidth).toBe(width);
    expect(metrics.hostOverflow).toBeLessThanOrEqual(2);
    expect(metrics.rootOverflow).toBeLessThanOrEqual(2);
  }
  expect(errors).toEqual([]);
});
