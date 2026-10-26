// 0.26.5.4: a fan FreshAirIQ switches itself shows what the automation does,
// not a task for the user ("Lüfter ausschalten"); a fan switched on by hand keeps
// the manual instruction.
import { test, expect } from '@playwright/test';
import { loadCard } from './harness.mjs';

async function mount(page, rooms, language = 'de') {
  const errors = [];
  page.on('pageerror', err => errors.push(String(err)));
  await loadCard(page, '<!doctype html><html><body><main><freshairiq-card id="card"></freshairiq-card></main></body></html>');
  await page.evaluate(({ rooms, language }) => {
    const status = { entity_id: 'sensor.freshairiq_status', state: 'ok', attributes: {
      freshairiq_transport: 'status_v2', freshairiq_entry_id: 'entry1', freshairiq_version: '0.26.5.4', output_language: language,
      rooms, room_sort_order: Object.keys(rooms) } };
    const card = document.getElementById('card');
    card.setConfig({ dashboard_variant: 'classic' });
    card.hass = { states: { [status.entity_id]: status }, language, locale: { language } };
    card._info = 'rooms';
    card._render();
  }, { rooms, language });
  await page.waitForTimeout(150);
  return errors;
}

const garage = (automation, extra = {}) => ({ key: 'garage', name: 'Garage', calculation_enabled: true, data_quality: 'ok', temperature: 18,
  humidity: 80, absolute_humidity: 12, action: 'Close', potential_ml: 0, surface_rh: 90, mould_level: 'High', active: true,
  configured_actuators: { exhaust_fan: 'switch.garage', exhaust_fan_control: 'recommendation', mechanical_exhaust_active: true, window_open: false },
  fan_automation: automation, ...extra });

const text = page => page.locator('#card').evaluate(card => card.shadowRoot.querySelector('.subdialog').textContent);

test('an automatic fan shows the automation wording instead of a task', async ({ page }) => {
  const errors = await mount(page, { garage: garage({ state: 'stopping', label: 'Lüftungsziel erreicht – FreshAirIQ beendet die Lüftung' }) });
  const content = await text(page);
  expect(content).toContain('Lüftungsziel erreicht – FreshAirIQ beendet die Lüftung');
  expect(content).not.toContain('Lüfter ausschalten');
  expect(errors).toEqual([]);
});

test('a fan switched on by hand keeps the manual instruction', async ({ page }) => {
  await mount(page, { garage: garage({ state: 'manual', label: null }) });
  expect(await text(page)).toContain('Lüfter ausschalten');
});

test('English dashboards get the English automation wording', async ({ page }) => {
  await mount(page, { garage: garage({ state: 'running', label: 'Automatische Lüftung läuft' }, { action: 'Continue ventilating' }) }, 'en');
  const content = await text(page);
  expect(content).toContain('Automatic airing is running');
  expect(content).not.toContain('Automatische Lüftung läuft');
});

// 0.26.5.4 (support case): a fan room without a window contact is not told to "air via a connected room"
test('a fan room without a window asks for the fan', async ({ page }) => {
  const laundry = { key: 'wk', name: 'Waschküche', calculation_enabled: true, data_quality: 'ok', temperature: 24.4, humidity: 62,
    absolute_humidity: 13.8, action: 'Ventilate indirectly', action_hint: 'Ablüfter einschalten', contact_count: 0, potential_ml: 80,
    surface_rh: 70, mould_level: 'Low', active: false, configured_actuators: { exhaust_fan: 'switch.wk', mechanical_exhaust_active: false } };
  const errors = await mount(page, { wk: laundry });
  const content = await text(page);
  expect(content).toContain('Ablüfter einschalten');
  expect(content).not.toContain('Über Nachbarraum lüften');
  expect(errors).toEqual([]);
  await mount(page, { wk: laundry }, 'en');
  expect(await text(page)).toContain('Switch on the exhaust fan');
});
