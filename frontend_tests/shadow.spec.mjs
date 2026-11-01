// Passive test of a new moisture formula: compact section at the end of "Wie gut FreshAirIQ aktuell
// vorhersagt" (DE/EN, empty / collecting / better / worse), no overflow on phones and tablets, the
// existing quality tiles unchanged, numbers only from the published comparison.
import { test, expect } from '@playwright/test';
import { loadCard } from './harness.mjs';

const BASE = { samples: 0, status: 'no_data', production_mae_ml: null, candidate_mae_ml: null, mae_difference_ml: null, improvement_percent: null };
const CASES = {
  empty: null,
  none: BASE,
  collecting: { samples: 3, status: 'collecting', production_mae_ml: 24.4, candidate_mae_ml: 21.0, mae_difference_ml: -3.4, improvement_percent: 13.9 },
  better: { samples: 85, status: 'candidate_better', production_mae_ml: 24.0, candidate_mae_ml: 21.0, mae_difference_ml: -3.0, improvement_percent: 12.5, null_mae_ml: 30.0, candidate_beats_null: true, production_beats_null: true },
  worse: { samples: 40, status: 'candidate_worse', production_mae_ml: 18.0, candidate_mae_ml: 27.0, mae_difference_ml: 9.0, improvement_percent: -50.0, null_mae_ml: 17.0, candidate_beats_null: false, production_beats_null: false },
  mixed: { samples: 0, status: 'no_data', production_mae_ml: null, candidate_mae_ml: null, other_formula_samples: 4 },
  nullish: { samples: 20, status: 'inconclusive', production_mae_ml: 22.0, candidate_mae_ml: 16.0, mae_difference_ml: -6.0, improvement_percent: 27.3, null_mae_ml: 16.4, candidate_beats_null: false, production_beats_null: true },
};

async function render(page, comparison, language) {
  await loadCard(page, `<!doctype html><html><head><meta name="viewport" content="width=device-width, initial-scale=1"></head><body><freshairiq-card id="card"></freshairiq-card></body></html>`);
  return page.evaluate(async ({ comparison, language }) => {
    const attributes = {
      freshairiq_transport: 'status_v2', freshairiq_version: '0.26.5.5', rooms: {}, room_sort_order: [],
      learning_components: { overall_maturity_percent: 10, stage_label: 'Grundmodell', components: [] },
      forecast_backtest: { reliability: { score_percent: 44, direction_accuracy_percent: 50, magnitude_accuracy_percent: 66 } },
      learning_effectiveness: { samples: 4, independent_sessions: 2, distinct_days: 1, production_mae_ml: 12, baseline_mae_ml: 15 },
      diagnostics: { retention_days: 30 },
    };
    if (comparison) attributes.forecast_shadow_comparison = comparison;
    const card = document.getElementById('card');
    card.setConfig({});
    card.hass = { language, locale: { language }, states: { 'sensor.freshairiq_status': { entity_id: 'sensor.freshairiq_status', state: 'ok', attributes } } };
    card._info = 'learning:quality';
    card._render();
    if (language === 'en') {  // the English text module loads first
      await new Promise(resolve => setTimeout(resolve, 500));
      card._render();
    }
    const panel = card.shadowRoot.querySelector('.learning-detail-panel');
    const section = panel && panel.querySelector('.faiq-shadow-test');
    return {
      section: section ? section.textContent.replace(/\s+/g, ' ').trim() : null,
      last: !!(section && panel.lastElementChild === section),
      tiles: panel ? panel.querySelectorAll('.learning-quality-grid > div').length : 0,
      overflow: panel ? Math.max(0, panel.scrollWidth - panel.clientWidth, document.documentElement.scrollWidth - window.innerWidth) : -1,
    };
  }, { comparison, language });
}

for (const [label, width, height] of [['iPhone', 390, 844], ['iPad', 768, 1024]]) {
  test(`${label}: German section for every state`, async ({ page }) => {
    await page.setViewportSize({ width, height });
    for (const [name, comparison] of Object.entries(CASES)) {
      const out = await render(page, comparison, 'de');
      expect(out.section, name).toContain('Experiment: Neue Feuchteformel (passiver Test)');
      expect(out.section).toContain('ändert keine Lüftungs- oder Schließempfehlung');
      expect(out.last && out.tiles === 15 && out.overflow <= 2, name).toBe(true);
      if (name === 'empty' || name === 'none' || name === 'mixed') expect(out.section).toContain('Noch kein Vergleich');
      if (name === 'mixed') expect(out.section).toContain('4 Lüftungen mit anderer Formelversion nicht eingerechnet');
      if (name !== 'mixed') expect(out.section).not.toContain('anderer Formelversion');
      if (name === 'better') {
        expect(out.section).toContain('Bestehende Formel: 24 ml MAE · Testformel: 21 ml MAE');
        expect(out.section).toContain('Unterschied: –3 ml (12,5 % geringerer Fehler) · 85 vergleichbare Lüftungen');
        expect(out.section).toContain('keine automatische Übernahme');
        expect(out.section).toContain('Ohne Vorhersage (immer 0 ml): 30 ml MAE');
        expect(out.section).not.toContain('noch nicht klar besser');
      }
      if (name === 'collecting') expect(out.section).not.toContain('immer 0 ml');  // older summaries without the field
      if (name === 'nullish') expect(out.section).toContain('16 ml MAE – Testformel noch nicht klar besser');
      if (name === 'collecting') expect(out.section).toContain('Sammelt Vergleichsdaten – vorläufig');
      if (name === 'worse') {
        expect(out.section).toContain('Unterschied: +9 ml (50,0 % höherer Fehler) · 40 vergleichbare Lüftungen');
        expect(out.section).toContain('Testformel schlechter als die bestehende Formel');
        expect(out.section).toContain('Ohne Vorhersage (immer 0 ml): 17 ml MAE – noch keine Formel klar besser');
      }
    }
  });
}

test('English section', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  const better = await render(page, CASES.better, 'en');
  expect(better.section).toContain('Experiment: new moisture formula (passive test)');
  expect(better.section).toContain('Current formula: 24 ml MAE · test formula: 21 ml MAE');
  expect(better.section).toContain('Difference: –3 ml (12.5 % lower error) · 85 comparable airings');
  expect(better.section).toContain('changes no ventilation or close recommendation');
  expect(better.section).toContain('Without a forecast (always 0 ml): 30 ml MAE');
  expect(better.section).not.toMatch(/Bestehende|Testformel|Unterschied|Vorhersage/);
  const mixed = await render(page, CASES.mixed, 'en');
  expect(mixed.section).toContain('4 airings with another formula version not included');
  const nullish = await render(page, CASES.nullish, 'en');
  expect(nullish.section).toContain('– the test formula is not clearly better yet');
  const empty = await render(page, null, 'en');
  expect(empty.section).toContain('No comparison yet');
  expect(better.overflow).toBeLessThanOrEqual(2);
});
