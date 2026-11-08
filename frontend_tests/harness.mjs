// Serve the dashboard from a real http origin, the way Home Assistant does
// (/freshairiq_static/...). The card is an ES module that resolves its English
// text module relative to import.meta.url; about:blank pages cannot do that.
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const HERE = path.dirname(fileURLToPath(import.meta.url));
const FRONTEND = path.resolve(HERE, '../custom_components/freshairiq/frontend');
const ORIGIN = 'http://freshairiq.test';

export async function loadCard(page, html) {
  await page.route(`${ORIGIN}/**`, route => {
    const url = new URL(route.request().url());
    if (url.pathname === '/') return route.fulfill({ contentType: 'text/html', body: html });
    // HA serves the frontend directory under its own static prefix; resolve by file name.
    const file = path.join(FRONTEND, path.basename(url.pathname));
    if (!fs.existsSync(file)) return route.fulfill({ status: 404, body: '' });
    const type = file.endsWith('.js') ? 'text/javascript' : file.endsWith('.png') ? 'image/png' : 'application/octet-stream';
    return route.fulfill({ path: file, contentType: type });
  });
  await page.goto(`${ORIGIN}/`);
  await page.addScriptTag({ url: `${ORIGIN}/freshairiq-card.js`, type: 'module' });
  await page.waitForFunction(() => !!customElements.get('freshairiq-card'));
}

// Home Assistant's page font (html { font-family: var(--ha-font-family-body) } = Roboto, Noto, sans-serif) – here its last,
// always present step, sans-serif. Without it every engine fell back to its own default serif font (Chromium "Times New
// Roman", Firefox "serif", WebKit "-webkit-standard") with different widths; the house map's editor inherits the page font
// (0.26.7.0 CI fix, cross-browser). Roboto/Noto are not named: on a machine without Roboto fontconfig resolved them to
// unsuitable fonts (seen locally: the colour emoji font – Chromium hung, Firefox drew emoji widths, WebKit no text).
const HA_FONT = '<style>html{font-family:sans-serif}</style>';
const withHaFont = html => (/<head>/i.test(html) ? html.replace(/<head>/i, `<head>${HA_FONT}`) : html.replace(/<html>/i, `<html><head>${HA_FONT}</head>`));

// Any frontend module (e.g. the loader with the optional house map card).
export async function loadModule(page, html, file, tag) {
  await page.route(`${ORIGIN}/**`, route => {
    const url = new URL(route.request().url());
    if (url.pathname === '/') return route.fulfill({ contentType: 'text/html', body: withHaFont(html) });
    const target = path.join(FRONTEND, path.basename(url.pathname));
    if (!fs.existsSync(target)) return route.fulfill({ status: 404, body: '' });
    return route.fulfill({ path: target, contentType: target.endsWith('.js') ? 'text/javascript' : 'application/octet-stream' });
  });
  await page.goto(`${ORIGIN}/`);
  await page.addScriptTag({ url: `${ORIGIN}/${file}`, type: 'module' });
  await page.waitForFunction(name => !!customElements.get(name), tag);
}

// 0.26.7.0 CI fix (cross-browser): the house map draws a live update in its next animation frame (requestAnimationFrame).
// A fixed pause stood for "drawn" – true while a frame costs a few ms (Chromium), not in software-rendered WebKit or
// Firefox, where a frame of the animated plan took 50–150 ms and the tests read the picture before the update. ``settle``
// waits the same pause as before and then until no house map (and no plan editor in it) has a frame pending for three
// frames in a row – never shorter than the old pause.
export async function settle(page, ms) {
  await page.waitForTimeout(ms);
  // quiet for three frames in a row: a redraw the card asks for from inside a frame (a new width, the drawing's size) is
  // only queued in the next one
  await page.evaluate(() => new Promise(resolve => {
    const busy = () => [...document.querySelectorAll('freshairiq-house-card-impl')].some(el => el._frame
      || [...el.shadowRoot.querySelectorAll('freshairiq-house-layout-editor')].some(ed => ed._resizeRaf))
      || [...document.querySelectorAll('freshairiq-house-layout-editor')].some(ed => ed._resizeRaf);
    const until = performance.now() + 5000;
    let quiet = 0;
    const tick = () => { quiet = busy() ? 0 : quiet + 1; if (quiet >= 3 || performance.now() > until) resolve(); else requestAnimationFrame(tick); };
    requestAnimationFrame(tick);
  })).catch(() => { /* page gone: the test's own checks decide */ });
}
