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
