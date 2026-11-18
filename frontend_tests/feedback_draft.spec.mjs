// U03 (0.26.7.1): the feedback form of the dashboard card keeps the user's draft.
// Before, a live update reset an unfocused feedback text box to the empty server-rendered value, a full render lost the
// draft and the receipt (feedback ID) vanished at the next render. The draft is now kept per integration entry and
// feedback type for the session (in memory only), deleted only after the Hub confirmed it, and the ID stays visible.
import { test, expect } from '@playwright/test';
import { loadCard } from './harness.mjs';

async function mount(page, { language = 'de' } = {}) {
  const errors = [];
  page.on('pageerror', err => errors.push(String(err)));
  await loadCard(page, '<!doctype html><html><head><meta name="viewport" content="width=device-width, initial-scale=1"></head><body><main><freshairiq-card id="card"></freshairiq-card></main></body></html>');
  await page.evaluate(language => {
    window.__status = n => ({ entity_id: 'sensor.freshairiq_status', state: 'ok', attributes: {
      freshairiq_transport: 'status_v2', freshairiq_entry_id: 'entry-1', status_text: `Stand ${n}`,
      rooms: { bad: { key: 'bad', name: 'Bad', calculation_enabled: true, data_quality: 'ok', temperature: 21 + n / 10, humidity: 61, absolute_humidity: 11, action: 'Okay', potential_ml: 10, surface_rh: 70, mould_level: 'Low', active: false } },
      room_sort_order: ['bad'], diagnostics: { retention_days: 30 } } });
    window.__calls = [];
    window.__reply = { feedback_id: 'FAIQ-FB-TEST01', accepted: true, cooldown_until: new Date(Date.now() + 15 * 60e3).toISOString() };
    const card = document.getElementById('card');
    card.setConfig({});
    window.__n = 0;
    window.__live = () => { window.__n += 1; card.hass = { ...card._hass, states: { 'sensor.freshairiq_status': window.__status(window.__n) } }; };
    card.hass = { language, locale: { language }, states: { 'sensor.freshairiq_status': window.__status(0) },
      callApi: async (method, path, body) => { window.__calls.push([method, path, body]); if (window.__reply instanceof Error) throw window.__reply; return window.__reply; } };
    card._registerFieldTestClient = async () => {};
    card._info = 'support'; card._render();
  }, language);
  await page.waitForTimeout(120);
  return errors;
}
const card = page => page.locator('#card');
const box = page => card(page).evaluate(c => { const t = c.shadowRoot.getElementById('feedback-message'); return t ? t.value : null; });
const type = page => card(page).evaluate(c => c.shadowRoot.getElementById('feedback-type').value);
const result = page => card(page).evaluate(c => c.shadowRoot.getElementById('feedback-result').textContent);
const typeIn = async (page, text) => {
  await card(page).evaluate(c => { c.shadowRoot.getElementById('feedback-message').focus(); });
  await page.keyboard.insertText(text);   // like a paste: one insert, real input events
  await card(page).evaluate(c => c.shadowRoot.getElementById('feedback-message').blur());
};
const live = async page => { await page.evaluate(() => window.__live()); await page.waitForTimeout(60); };
const rerender = async page => { await card(page).evaluate(c => c._render()); await page.waitForTimeout(60); };

test('U03: an unfocused draft survives live updates, a full render and a new card element of the same session', async ({ page }) => {
  const errors = await mount(page);
  await typeIn(page, 'Etwas fällt auf');
  await live(page); await live(page);
  expect(await box(page)).toBe('Etwas fällt auf');
  await rerender(page);
  expect(await box(page)).toBe('Etwas fällt auf');
  // the dashboard rebuilds the card element (view change): same session, same entry – the draft is back
  await page.evaluate(() => { const old = document.getElementById('card'); const fresh = document.createElement('freshairiq-card'); fresh.id = 'card';
    fresh.setConfig({}); fresh.hass = old._hass; fresh._info = 'support'; old.replaceWith(fresh); fresh._render(); });
  await page.waitForTimeout(80);
  expect(await box(page)).toBe('Etwas fällt auf');
  expect(errors).toEqual([]);
});

test('U03: drafts are kept per feedback type and the chosen type survives renders', async ({ page }) => {
  await mount(page);
  const choose = v => card(page).evaluate((c, v) => { const s = c.shadowRoot.getElementById('feedback-type'); s.value = v; s.dispatchEvent(new Event('change', { bubbles: true })); }, v);
  await typeIn(page, 'Ein Fehler');
  await choose('improvement');
  expect(await box(page)).toBe('');                    // each type has its own draft
  await typeIn(page, 'Eine Idee');
  await rerender(page); await live(page);
  expect([await type(page), await box(page)]).toEqual(['improvement', 'Eine Idee']);
  await choose('bug');
  expect(await box(page)).toBe('Ein Fehler');          // nothing is lost by switching
  await choose('improvement');
  expect(await box(page)).toBe('Eine Idee');
});

for (const [label, reply] of [['network error', 'network'], ['401', 401], ['429 cooldown', 429]]) {
  test(`U03: a failed send (${label}) keeps the draft`, async ({ page }) => {
    await mount(page);
    await page.evaluate(reply => {
      const err = new Error(reply === 'network' ? 'Failed to fetch' : 'x');
      if (reply === 401) err.status_code = 401;
      if (reply === 429) { err.status_code = 429; err.body = JSON.stringify({ reason: 'cooldown', retry_after_seconds: 600, cooldown_until: new Date(Date.now() + 600e3).toISOString() }); }
      window.__reply = err;
    }, reply);
    await typeIn(page, 'Bitte nicht verlieren');
    await card(page).evaluate(c => c.shadowRoot.getElementById('feedback-send').click());
    await page.waitForTimeout(80);
    await live(page); await rerender(page);
    expect(await box(page)).toBe('Bitte nicht verlieren');
  });
}

test('U03: after a confirmed send the draft is gone and the feedback ID stays visible across renders', async ({ page }) => {
  await mount(page);
  await typeIn(page, 'Gesendeter Text');
  await card(page).evaluate(c => c.shadowRoot.getElementById('feedback-send').click());
  await expect.poll(() => result(page)).toContain('FAIQ-FB-TEST01');
  for (let i = 0; i < 3; i++) { await live(page); expect(await result(page)).toContain('FAIQ-FB-TEST01'); }
  await rerender(page);
  expect(await result(page)).toContain('FAIQ-FB-TEST01');
  expect(await box(page)).toBe('');
  expect(await card(page).evaluate(c => c.shadowRoot.getElementById('feedback-send').disabled)).toBe(true);   // 15-minute default stays
});

test('U03: pasted lists reach the request unchanged and untrusted text is never parsed as HTML', async ({ page }) => {
  await mount(page);
  const list = 'Mehrere Punkte:\n- Punkt 1\n- Punkt 2\n• Punkt 3\n– Punkt 4\n1. Punkt 5\n<b>kein Fett</b> & "Zitat"';
  await typeIn(page, list);
  await rerender(page); await live(page);
  expect(await box(page)).toBe(list);
  expect(await card(page).evaluate(c => c.shadowRoot.querySelector('#feedback-message b, .settings-panel > b'))).toBeNull();
  await card(page).evaluate(c => c.shadowRoot.getElementById('feedback-send').click());
  const feedbackCalls = () => page.evaluate(() => window.__calls.filter(c => c[1].startsWith('freshairiq/feedback/')));
  await expect.poll(async () => (await feedbackCalls()).length).toBe(1);
  const [method, path, body] = (await feedbackCalls())[0];
  expect([method, path, body.type, body.message]).toEqual(['POST', 'freshairiq/feedback/entry-1', 'bug', list]);
});

test('U03: the English card never translates the user\'s own words in the draft', async ({ page }) => {
  await mount(page, { language: 'en' });
  await typeIn(page, 'Jetzt lüften');
  await rerender(page); await live(page);
  expect(await box(page)).toBe('Jetzt lüften');
});

test('U03: the text box is readable and scrolls on touch devices', async ({ page }) => {
  await mount(page);
  const css = await card(page).evaluate(c => { const s = getComputedStyle(c.shadowRoot.getElementById('feedback-message')); return { size: parseFloat(s.fontSize), overflowY: s.overflowY, touch: s.touchAction }; });
  expect(css.size).toBeGreaterThanOrEqual(16);         // iOS zooms below 16 px; 9 px was hard to read on an iPad
  expect(css.overflowY).toBe('auto');
  expect(['auto', 'pan-y', 'manipulation']).toContain(css.touch);
});

// ---- R03 (0.26.7.2): the confirmation of a send clears exactly the draft that was sent ----------------------------
// The answer arrives asynchronously; meanwhile the user may type on, switch the type, write in another entry or the
// view may be rebuilt. The send context (entry, type, text, revision, draft) is fixed before the request.
const hold = page => page.evaluate(() => { window.__pending = []; window.__card = document.getElementById('card');
  window.__card._hass = { ...window.__card._hass, callApi: (method, path, body) => { window.__calls.push([method, path, body]);
    return new Promise((resolve, reject) => window.__pending.push({ resolve, reject })); } }; });
const answer = async (page, reply) => { await page.evaluate(reply => window.__pending.shift().resolve(reply), reply); await page.waitForTimeout(60); };
const fail = async page => { await page.evaluate(() => { const e = new Error('x'); e.status_code = 401; window.__pending.shift().reject(e); }); await page.waitForTimeout(60); };
const send = page => card(page).evaluate(c => c.shadowRoot.getElementById('feedback-send').click());
const OK = { feedback_id: 'FAIQ-FB-R03', accepted: true };
const choose = (page, v) => card(page).evaluate((c, v) => { const s = c.shadowRoot.getElementById('feedback-type'); s.value = v; s.dispatchEvent(new Event('change', { bubbles: true })); }, v);
const sends = page => page.evaluate(() => window.__calls.filter(c => c[1].startsWith('freshairiq/feedback/')).length);

test('R03: text typed while the send is on its way stays after the confirmation', async ({ page }) => {
  await mount(page); await hold(page);
  await typeIn(page, 'Erster Teil');
  await send(page);
  await typeIn(page, ' und mehr');
  await answer(page, OK);
  expect(await box(page)).toBe('Erster Teil und mehr');
  await rerender(page); await live(page);
  expect(await box(page)).toBe('Erster Teil und mehr');
  expect(await result(page)).toContain('FAIQ-FB-R03');
});

test('R03: a new type and its text written meanwhile are kept; only the sent type\'s unchanged text would go', async ({ page }) => {
  await mount(page); await hold(page);
  await typeIn(page, 'Ein Fehler');
  await send(page);
  await choose(page, 'improvement');
  await typeIn(page, 'Eine neue Idee');
  await answer(page, OK);
  expect([await type(page), await box(page)]).toEqual(['improvement', 'Eine neue Idee']);
  await rerender(page);
  expect(await box(page)).toBe('Eine neue Idee');
});

test('R03: an unchanged sent draft is cleared, also when the view was closed and reopened during the send', async ({ page }) => {
  await mount(page); await hold(page);
  await typeIn(page, 'Gesendet und fertig');
  await send(page);
  await page.evaluate(() => { const old = document.getElementById('card'); const fresh = document.createElement('freshairiq-card'); fresh.id = 'card';
    fresh.setConfig({}); fresh.hass = old._hass; fresh._info = 'support'; old.replaceWith(fresh); fresh._render(); });
  await page.waitForTimeout(80);
  expect(await box(page)).toBe('Gesendet und fertig');      // still the draft while the answer is outstanding
  await answer(page, OK);
  await card(page).evaluate(c => c._render()); await page.waitForTimeout(60);
  expect(await box(page)).toBe('');
  expect(await result(page)).toContain('FAIQ-FB-R03');
});

test('R03: a double click sends once; a failed send (401) keeps the draft and a retry works', async ({ page }) => {
  await mount(page); await hold(page);
  await typeIn(page, 'Nur einmal senden');
  await card(page).evaluate(c => { const b = c.shadowRoot.getElementById('feedback-send'); b.disabled = false; b.click(); b.disabled = false; b.click(); });
  await page.waitForTimeout(40);
  expect(await sends(page)).toBe(1);
  await fail(page);
  expect(await box(page)).toBe('Nur einmal senden');
  expect(await card(page).evaluate(c => c.shadowRoot.getElementById('feedback-send').disabled)).toBe(false);   // no lock after an error
  await send(page);
  expect(await sends(page)).toBe(2);
  await answer(page, OK);
  expect(await box(page)).toBe('');
});

test('R03: a 429 during the send keeps the draft and shows the cooldown', async ({ page }) => {
  await mount(page); await hold(page);
  await typeIn(page, 'Zu schnell');
  await send(page);
  await page.evaluate(() => { const e = new Error('x'); e.status_code = 429; e.body = JSON.stringify({ reason: 'cooldown', retry_after_seconds: 600 }); window.__pending.shift().reject(e); });
  await page.waitForTimeout(60);
  expect(await box(page)).toBe('Zu schnell');
  expect(await result(page)).toMatch(/10/);
});

test('R03: the draft of another entry is never cleared by the confirmation of this one', async ({ page }) => {
  await mount(page); await hold(page);
  await typeIn(page, 'Text von Eintrag 1');
  await send(page);
  // the card now shows a second integration entry and the user writes there
  await page.evaluate(() => { const c = document.getElementById('card'); const s = window.__status(9); s.attributes.freshairiq_entry_id = 'entry-2';
    c.hass = { ...c._hass, states: { 'sensor.freshairiq_status': s } }; c._render(); });
  await page.waitForTimeout(80);
  expect(await box(page)).toBe('');
  await typeIn(page, 'Text von Eintrag 2');
  await answer(page, OK);
  expect(await box(page)).toBe('Text von Eintrag 2');
  await card(page).evaluate(c => c._render()); await page.waitForTimeout(60);
  expect(await box(page)).toBe('Text von Eintrag 2');
});

// ---- B2 (0.26.7.1): receipt and lock of a send belong to the entry that was sent ----------------------------------
const showEntry = (page, id) => page.evaluate(id => { const c = document.getElementById('card'); const s = window.__status(7); s.attributes.freshairiq_entry_id = id;
  c.hass = { ...c._hass, states: { 'sensor.freshairiq_status': s } }; c._render(); }, id);
const button = page => card(page).evaluate(c => c.shadowRoot.getElementById('feedback-send').disabled);

test('B2: a confirmation for entry A shows neither its receipt nor its lock in entry B; back in A both are there', async ({ page }) => {
  await mount(page); await hold(page);
  await typeIn(page, 'Gesendete Meldung');
  await send(page);
  await showEntry(page, 'entry-2'); await page.waitForTimeout(80);
  await typeIn(page, 'Noch nicht gesendeter Entwurf B');
  await answer(page, { feedback_id: 'ID-FOR-A', accepted: true, cooldown_until: new Date(Date.now() + 15 * 60e3).toISOString() });
  expect(await result(page)).not.toContain('ID-FOR-A');
  expect(await button(page)).toBe(false);
  expect(await box(page)).toBe('Noch nicht gesendeter Entwurf B');
  await showEntry(page, 'entry-2'); await rerender(page);         // a live update of entry B, full render
  expect(await result(page)).not.toContain('ID-FOR-A');
  expect(await button(page)).toBe(false);
  await showEntry(page, 'entry-1'); await page.waitForTimeout(80);
  expect(await result(page)).toContain('ID-FOR-A');
  expect(await button(page)).toBe(true);                       // A's own 15-minute lock
  expect(await box(page)).toBe('');
});

test('B2: a failed send of entry A (network) leaves entry B untouched and A keeps its draft', async ({ page }) => {
  await mount(page); await hold(page);
  await typeIn(page, 'Text A');
  await send(page);
  await showEntry(page, 'entry-2'); await page.waitForTimeout(80);
  await page.evaluate(() => window.__pending.shift().reject(new Error('Failed to fetch'))); await page.waitForTimeout(60);
  expect(await result(page)).not.toContain('fehlgeschlagen');
  expect(await button(page)).toBe(false);
  await showEntry(page, 'entry-1'); await page.waitForTimeout(80);
  expect(await box(page)).toBe('Text A');
  expect(await button(page)).toBe(false);
});

test('B2: returning to A while its request is still running, the answer is shown in A', async ({ page }) => {
  await mount(page); await hold(page);
  await typeIn(page, 'Text A');
  await send(page);
  await showEntry(page, 'entry-2'); await page.waitForTimeout(60);
  await showEntry(page, 'entry-1'); await page.waitForTimeout(60);
  await answer(page, { feedback_id: 'ID-A-2', accepted: true, cooldown_until: new Date(Date.now() + 15 * 60e3).toISOString() });
  expect(await result(page)).toContain('ID-A-2');
  expect(await button(page)).toBe(true);
});
