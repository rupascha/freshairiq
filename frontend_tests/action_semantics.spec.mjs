// Re-audit 31.10. (D03): the canonical house action looks the same in the Classic room tile, the room
// detail, the IQ room cards and the house map. Rooms come from the backend-derived fixture
// (tests/test_display_semantics_026505.py); a real or protective close keeps the close colour.
import { test, expect } from '@playwright/test';
import fs from 'node:fs';
import { loadCard } from './harness.mjs';

const SEMANTICS = JSON.parse(fs.readFileSync(new URL('./fixtures/display_semantics.json', import.meta.url), 'utf8')).scenarios;
const CYAN = 'rgb(99, 210, 247)', WAIT = 'rgb(226, 189, 105)', CLOSE = 'rgb(255, 180, 95)';

async function mount(page, scenario, variant, info = 'rooms', language = 'de') {
  const errors = [];
  page.on('pageerror', err => errors.push(String(err)));
  await loadCard(page, '<!doctype html><html><body><main><freshairiq-card id="card"></freshairiq-card></main></body></html>');
  await page.evaluate(({ s, variant, info, language }) => {
    const status = { entity_id: 'sensor.freshairiq_status', state: 'ok', attributes: {
      freshairiq_transport: 'status_v2', freshairiq_entry_id: 'entry1', freshairiq_version: '0.26.5.5', output_language: language,
      status: s.recommendation.status, intelligent_recommendation: s.recommendation, rooms: s.rooms, room_sort_order: Object.keys(s.rooms) } };
    const card = document.getElementById('card');
    card.setConfig({ dashboard_variant: variant });
    card.hass = { states: { [status.entity_id]: status }, language, locale: { language } };
    card._info = info;
    card._render();
  }, { s: SEMANTICS[scenario], variant, info, language });
  await page.waitForTimeout(150);
  return errors;
}

// Classic room tile: chip text and the --status colour of the tile.
const tile = (page, key) => page.locator('#card').evaluate((card, key) => {
  const el = card.shadowRoot.querySelector(`article.room[data-room="${key}"]`);
  const probe = document.createElement('i'); probe.style.color = el.style.getPropertyValue('--status'); document.body.appendChild(probe);
  const color = getComputedStyle(probe).color; probe.remove();
  return { chip: el.querySelector('.room-status').textContent, color };
}, key);
// Room detail: the action headline and the --room-iq colour.
const detail = page => page.locator('#card').evaluate(card => {
  const hero = card.shadowRoot.querySelector('.room-iq-hero');
  const probe = document.createElement('i'); probe.style.color = hero.style.getPropertyValue('--room-iq'); document.body.appendChild(probe);
  const color = getComputedStyle(probe).color; probe.remove();
  return { text: hero.querySelector('strong').textContent, icon: hero.querySelector('ha-icon').getAttribute('icon'), color };
});

test('Classic: a tolerated long opening is a supervised opening in the tile and the detail, never the close colour', async ({ page }) => {
  const errors = await mount(page, 'monitor_open', 'classic');
  expect(await tile(page, 'bad')).toEqual({ chip: 'Daueröffnung überwachen', color: CYAN });
  await mount(page, 'monitor_open', 'classic', 'room:bad');
  expect(await detail(page)).toEqual({ text: 'Daueröffnung überwachen', icon: 'mdi:window-open', color: CYAN });
  expect(errors).toEqual([]);
});

test('Classic: a room the house holds back waits in the tile and the detail', async ({ page }) => {
  await mount(page, 'ventilate_later', 'classic');
  expect(await tile(page, 'wohnen')).toEqual({ chip: 'Lüften möglich · noch warten', color: WAIT });
  await mount(page, 'ventilate_later', 'classic', 'room:wohnen');
  expect(await detail(page)).toMatchObject({ text: 'Lüften möglich · noch warten', color: WAIT });
});

for (const scenario of ['close', 'protection_close']) {
  test(`Classic: a ${scenario === 'close' ? 'normal' : 'protective'} close keeps the close colour and word`, async ({ page }) => {
    await mount(page, scenario, 'classic');
    expect(await tile(page, 'bad')).toEqual({ chip: 'Schließen', color: CLOSE });
    await mount(page, scenario, 'classic', 'room:bad');
    expect(await detail(page)).toMatchObject({ text: 'Schließen', color: CLOSE });
  });
}

test('IQ: the room cards show the same supervised opening and the same close as Classic', async ({ page }) => {
  const errors = await mount(page, 'monitor_open', 'iq', null);
  const card = await page.locator('#card').evaluate(c => { const r = c.shadowRoot.querySelector('.ai-room'); return r ? { text: r.querySelector('small').textContent, icon: r.querySelector('ha-icon').getAttribute('icon'), accent: r.style.getPropertyValue('--room') } : null; });
  expect(card).toMatchObject({ text: 'Daueröffnung überwachen', icon: 'mdi:window-open' });
  expect(card.accent).toContain('#63d2f7');  // the same cyan as the Classic tile (theme variable around it)
  await mount(page, 'protection_close', 'iq', null);
  const closing = await page.locator('#card').evaluate(c => { const r = c.shadowRoot.querySelector('.ai-room'); return r ? r.style.getPropertyValue('--room') : null; });
  expect(closing).toContain('#ffb45f');  // close colour, as in Classic
  expect(errors).toEqual([]);
});
