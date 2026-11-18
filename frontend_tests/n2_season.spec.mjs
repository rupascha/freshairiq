// N2 (0.26.7.1): the season card separates observed days, minimum amount and missing season coverage (photo case:
// autumn 61 days, "61/60 · learning" read as if 60 days were the only condition). The real card method renders it.
import { test, expect } from '@playwright/test';
import { loadCard } from './harness.mjs';

const ST = { learning_components: { components: [
  { key: 'seasonality', label: 'Saisonalität', samples: 0, maturity_percent: 16, calendar_span_days: 61, season_breakdown: [
    { key: 'spring', label: 'Frühling', optimized: false, observed_days: 0, covers_start: false, covers_end: false, min_days: 60 },
    { key: 'summer', label: 'Sommer', optimized: false, observed_days: 0, covers_start: false, covers_end: false, min_days: 60 },
    { key: 'autumn', label: 'Herbst', optimized: false, observed_days: 61, covers_start: false, covers_end: false, min_days: 60 },
    { key: 'winter', label: 'Winter', optimized: false, observed_days: 0, covers_start: false, covers_end: false, min_days: 60 }] },
  { key: 'night_model', label: 'Nachtmodell', samples: 50, raw_samples: 935, maturity_percent: 41, status: 'Muster erkannt', detail: '935 Messupdates aus 50 unterschiedlichen Nächten' }] } };

async function panel(page, language) {
  await loadCard(page, '<!doctype html><html><body><freshairiq-card id="card"></freshairiq-card></body></html>');
  return page.evaluate(([st, language]) => {
    const c = document.getElementById('card'); c.setConfig({});
    c.hass = { language, locale: { language }, states: {} };
    c._info = 'learning:longterm';
    const box = document.createElement('div'); box.innerHTML = c._localizeHtml ? c._localizeHtml(c._learningPanel(st)) : c._learningPanel(st);
    document.body.appendChild(box);
    return [...box.querySelectorAll('.season-card')].map(n => n.textContent.replace(/\s+/g, ' ').trim()).concat([box.textContent.replace(/\s+/g, ' ')]);
  }, [ST, language]);
}

test('N2: 61 observed autumn days say what is still missing; 60 days are not the only condition; texts are spaced', async ({ page }) => {
  const out = await panel(page, 'de');
  const autumn = out.find(t => t.startsWith('Herbst'));
  expect(autumn).toContain('61 Beobachtungstage');
  expect(autumn).toContain('Mindestmenge erreicht');
  expect(autumn).toContain('Saisonbeginn nicht beobachtet');
  expect(autumn).toContain('Saisonende noch nicht beobachtet');
  expect(autumn).not.toContain('61 / 60');
  expect(out.find(t => t.startsWith('Winter'))).toContain('Noch keine Beobachtungstage');
  const all = out[out.length - 1];
  expect(all).not.toContain('Saisonalität0/4');
  expect(all).not.toContain('120Nächte');
  expect(all).toContain('50 / 120 Nächte gelernt');
  expect(all).toContain('935');
});
