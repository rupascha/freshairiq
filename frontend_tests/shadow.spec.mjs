// Section "Experimentell" at the end of "Wie gut FreshAirIQ aktuell vorhersagt": the status of the adopted base
// formula (DE/EN) instead of the former formula comparison – once, in Classic and Freshy, with or without older
// comparison data; no overflow on phones and tablets, the existing quality tiles unchanged.
import { test, expect } from '@playwright/test';
import { loadCard } from './harness.mjs';

const BASE = { samples: 0, status: 'no_data', production_mae_ml: null, candidate_mae_ml: null, mae_difference_ml: null, improvement_percent: null };
// older comparison payloads a Home Assistant may still publish – none of it is shown any more
const CASES = {
  empty: null,
  none: BASE,
  collecting: { samples: 3, status: 'collecting', production_mae_ml: 24.4, candidate_mae_ml: 21.0, mae_difference_ml: -3.4, improvement_percent: 13.9 },
  better: { samples: 85, status: 'candidate_better', production_mae_ml: 24.0, candidate_mae_ml: 21.0, mae_difference_ml: -3.0, improvement_percent: 12.5, null_mae_ml: 30.0, candidate_beats_null: true, production_beats_null: true },
  worse: { samples: 40, status: 'candidate_worse', production_mae_ml: 18.0, candidate_mae_ml: 27.0, mae_difference_ml: 9.0, improvement_percent: -50.0, null_mae_ml: 17.0, candidate_beats_null: false, production_beats_null: false },
  mixed: { samples: 0, status: 'no_data', production_mae_ml: null, candidate_mae_ml: null, other_formula_samples: 4 },
};
const NOTE = {   // heading and note (textContent: no space at the line break)
  de: 'ExperimentellDie neue Grundformel inklusive der Prognosen wurde anhand von 23.000 realen Lüftungen ausgewertet und übernommen. Aktuell gibt es keine neue experimentelle Formel.',
  en: 'ExperimentalThe new base formula and its forecasts were evaluated using 23,000 real ventilation sessions and have been adopted. There is currently no new experimental formula.',
};
// nothing of the former comparison or of a running test
const OLD = /MAE|Testformel|test formula|Bestehende Formel|Current formula|vergleichbare|comparable|Sammelt|Collecting|passiver Test|passive test|Noch kein Vergleich|No comparison|anderer Formelversion|another formula version|ändert keine|changes no/;
const VARIANTS = [['Classic', { dashboard_variant: 'classic' }], ['Freshy', { dashboard_variant: 'iq' }]];

async function render(page, comparison, language, config = {}) {
  await loadCard(page, `<!doctype html><html><head><meta name="viewport" content="width=device-width, initial-scale=1"></head><body><freshairiq-card id="card"></freshairiq-card></body></html>`);
  return page.evaluate(async ({ comparison, language, config }) => {
    const attributes = {
      freshairiq_transport: 'status_v2', freshairiq_version: '0.26.5.5', rooms: {}, room_sort_order: [],
      learning_components: { overall_maturity_percent: 10, stage_label: 'Grundmodell', components: [] },
      forecast_backtest: { reliability: { score_percent: 44, direction_accuracy_percent: 50, magnitude_accuracy_percent: 66 } },
      learning_effectiveness: { samples: 4, independent_sessions: 2, distinct_days: 1, production_mae_ml: 12, baseline_mae_ml: 15 },
      diagnostics: { retention_days: 30 },
    };
    if (comparison) attributes.forecast_shadow_comparison = comparison;
    const card = document.getElementById('card');
    card.setConfig(config);
    card.hass = { language, locale: { language }, states: { 'sensor.freshairiq_status': { entity_id: 'sensor.freshairiq_status', state: 'ok', attributes } } };
    card._info = 'learning:quality';
    card._render();
    if (language === 'en') {  // the English text module loads first
      await new Promise(resolve => setTimeout(resolve, 500));
      card._render();
    }
    const panel = card.shadowRoot.querySelector('.learning-detail-panel');
    const sections = panel ? panel.querySelectorAll('.faiq-shadow-test') : [], section = sections[0];
    return {
      count: sections.length,
      section: section ? section.textContent.replace(/\s+/g, ' ').trim() : null,
      last: !!(section && panel.lastElementChild === section),
      tiles: panel ? panel.querySelectorAll('.learning-quality-grid > div').length : 0,
      overflow: panel ? Math.max(0, panel.scrollWidth - panel.clientWidth, document.documentElement.scrollWidth - window.innerWidth) : -1,
    };
  }, { comparison, language, config });
}

for (const [label, width, height] of [['iPhone', 390, 844], ['iPad', 768, 1024]]) {
  for (const [variant, config] of VARIANTS) {
    test(`${label}, ${variant}: the note on the adopted base formula, once, with and without older comparison data`, async ({ page }) => {
      await page.setViewportSize({ width, height });
      for (const [name, comparison] of Object.entries(CASES)) {
        const out = await render(page, comparison, 'de', config);
        expect(out.count, name).toBe(1);
        expect(out.section, name).toBe(NOTE.de);
        expect(out.section, name).not.toMatch(OLD);
        expect(out.last && out.tiles === 15 && out.overflow <= 2, name).toBe(true);
      }
    });
  }
}

for (const [variant, config] of VARIANTS) {
  test(`English, ${variant}: the note on the adopted base formula, once, with and without older comparison data`, async ({ page }) => {
    await page.setViewportSize({ width: 390, height: 844 });
    for (const comparison of [CASES.better, CASES.mixed, null]) {
      const out = await render(page, comparison, 'en', config);
      expect(out.count).toBe(1);
      expect(out.section).toBe(NOTE.en);
      expect(out.section).not.toMatch(OLD);
      expect(out.section).not.toMatch(/Grundformel|Lüftungen|übernommen/);
      expect(out.last && out.tiles === 15 && out.overflow <= 2).toBe(true);
    }
  });
}
