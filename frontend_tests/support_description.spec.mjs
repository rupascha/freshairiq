// 0.26.5.5 (owner request): a support diagnostic is sent only with a description of the problem –
// files without one cannot be assigned to a case. The backend refuses it as well.
import { test, expect } from '@playwright/test';
import { loadCard } from './harness.mjs';

test('the support diagnostic is sent only with a description of at least 10 characters', async ({ page }) => {
  const errors = [];
  page.on('pageerror', err => errors.push(String(err)));
  await loadCard(page, '<!doctype html><html><body><main id="m"></main></body></html>');
  const send = text => page.evaluate(async text => {
    const card = window.__card || (window.__card = document.createElement('freshairiq-card'));
    window.__alerts = []; window.__calls = [];
    window.alert = msg => window.__alerts.push(String(msg));
    card._hass = { states: {}, language: 'de', locale: { language: 'de' }, callApi: async (method, path, body) => { window.__calls.push([method, path, body]); return { accepted: true, cooldown_until: null, support_case_id: 'support-1' }; } };
    card._registerFieldTestClient = async () => {};
    card.shadowRoot.innerHTML = `<textarea id="diagnostics-message"></textarea><button id="diagnostics-send">x</button>`;
    card.shadowRoot.getElementById('diagnostics-message').value = text;
    card._supportCooldownUntil = null;
    await card._sendDiagnosticsToDeveloper();
    return { alerts: window.__alerts, calls: window.__calls };
  }, text);
  for (const text of ['', '   ', 'kaputt', '  123456789  ']) {
    const result = await send(text);
    expect(result.calls, JSON.stringify(text)).toEqual([]);
    expect(result.alerts[0]).toContain('ohne Beschreibung lässt sich die Diagnose nicht zuordnen');
  }
  const ok = await send('  Bad bleibt nach dem Lüften rot  ');
  expect(ok.calls).toEqual([['POST', 'freshairiq/support-diagnostics', { message: 'Bad bleibt nach dem Lüften rot' }]]);
  expect((await send('x'.repeat(4001))).calls).toEqual([]);
  expect(errors).toEqual([]);
});

test('the support form marks the description as required', async ({ page }) => {
  await loadCard(page, '<!doctype html><html><body></body></html>');
  const source = await page.evaluate(async () => (await fetch('/freshairiq-card.js')).text());
  expect(source).toContain('<b>Fehlerbeschreibung (Pflicht)</b>');
  expect(source).toMatch(/id="diagnostics-message"[^>]*minlength="10"[^>]*required/);
});
