// House map editor – floor plan template: upload, scale, north, room detection by tapping, assignment
// and windows by tapping. The plans are drawn on a canvas here, so every expected area is known exactly.
import { test, expect } from '@playwright/test';
import { loadModule, settle } from './harness.mjs';

const V = '0.26.5.4';
const S = 0.02; // metres per pixel of the drawn plans (800 × 600 px = 16 × 12 m)

// Black walls (8 px) on white paper. Rooms (inner areas):
//   wohnen: L shape x 48..396 × y 48..552 without the bad box x 48..204 × y 396..552 → 151056 px² = 60.42 m²
//   bad:    x 48..196 × y 404..552 → 148 × 148 px = 8.76 m²
//   buero:  x 408..752 × y 48..256 → 344 × 208 px = 28.62 m²
//   kueche: x 408..752 × y 264..552 → 344 × 288 px = 39.63 m²
// Optional: a door gap (14 px) between wohnen and buero, an outside door gap, furniture/text, noise and blur.
function drawPlan({ doorGap = false, outsideGap = false, furniture = false, photo = false } = {}) {
  const canvas = document.createElement('canvas');
  canvas.width = 800; canvas.height = 600;
  const ctx = canvas.getContext('2d');
  ctx.fillStyle = '#fff'; ctx.fillRect(0, 0, 800, 600);
  ctx.fillStyle = '#111';
  const wall = (x0, y0, x1, y1) => ctx.fillRect(x0, y0, x1 - x0, y1 - y0);
  wall(40, 40, 760, 48); wall(40, 552, 760, 560); wall(40, 40, 48, 560); wall(752, 40, 760, 560);
  if (outsideGap) { ctx.fillStyle = '#fff'; ctx.fillRect(100, 552, 30, 8); ctx.fillStyle = '#111'; }
  if (doorGap) { wall(396, 40, 408, 150); wall(396, 164, 408, 560); } else wall(396, 40, 408, 560);
  wall(408, 256, 760, 264);
  wall(40, 396, 204, 404); wall(196, 396, 204, 560);
  if (furniture) {
    ctx.strokeStyle = '#333'; ctx.lineWidth = 2; ctx.strokeRect(120, 120, 120, 50); ctx.strokeRect(260, 260, 60, 60);
    ctx.font = '22px sans-serif'; ctx.fillText('Wohnen 60 m²', 150, 230); ctx.fillText('4,20', 480, 150);
  }
  if (photo) {
    const img = ctx.getImageData(0, 0, 800, 600);
    let seed = 7;
    const rnd = () => { seed = (seed * 16807) % 2147483647; return seed / 2147483647; };
    for (let i = 0; i < img.data.length; i += 4) {
      const shade = 225 + 25 * (i / img.data.length) + (rnd() - 0.5) * 50;  // uneven light + grain
      for (let c = 0; c < 3; c++) img.data[i + c] = img.data[i + c] < 128 ? 40 + rnd() * 40 : Math.min(255, shade);
    }
    ctx.putImageData(img, 0, 0);
    const blurred = document.createElement('canvas');
    blurred.width = 800; blurred.height = 600;
    const b = blurred.getContext('2d');
    b.filter = 'blur(1.2px)'; b.drawImage(canvas, 0, 0);
    return blurred;
  }
  return canvas;
}

async function setup(page) {
  const errors = [];
  page.on('pageerror', err => errors.push(String(err)));
  await loadModule(page, '<!doctype html><html><body><main id="m"></main></body></html>', 'freshairiq-house-editor.js', 'freshairiq-house-layout-editor');
  await page.evaluate(`window.__draw = ${drawPlan.toString()}`);
  await page.evaluate(async v => { window.T = await import(`/freshairiq-house-trace.js?v=${v}`); }, V);
  return errors;
}

const ROOMS = [
  { key: 'wohnen', name: 'Wohnen', floor: 'eg', length: 7.8, width: 7.8, height: 2.5 },
  { key: 'bad', name: 'Bad', floor: 'eg', volume: 22, height: 2.5 },
  { key: 'buero', name: 'Büro', floor: 'eg', length: 7, width: 4.1 },
  { key: 'kueche', name: 'Küche', floor: 'eg', volume: 100 },
];

test('detection: clean plan with L shape, furniture and text gives the right areas and corners', async ({ page }) => {
  await setup(page);
  const r = await page.evaluate(S => {
    const c = window.__draw({ furniture: true }), image = c.getContext('2d').getImageData(0, 0, 800, 600);
    const at = seed => window.T.detectRoom(image, seed, { scale: S });
    return { wohnen: at([300, 100]), sofa: at([100, 300]), bad: at([120, 470]), buero: at([600, 150]), kueche: at([600, 400]) };
  }, S);
  for (const [key, expected] of [['wohnen', 60.42], ['sofa', 60.42], ['bad', 8.76], ['buero', 28.62], ['kueche', 39.63]]) {
    expect(r[key].ok, key).toBe(true);
    expect(Math.abs(r[key].areaM2 - expected) / expected, key).toBeLessThan(0.03);
  }
  expect(r.wohnen.pixels.length).toBe(6); // L shape
  expect(r.bad.pixels.length).toBe(4);
  expect(r.buero.pixels.length).toBe(4);
  // plan metres: y points up, origin bottom left of the picture
  const ys = r.buero.plan.map(p => p[1]);
  expect(Math.max(...ys)).toBeCloseTo((600 - 48) * S, 0);
});

test('detection: wall, outside, small area and missing scale are reported, not guessed', async ({ page }) => {
  await setup(page);
  const r = await page.evaluate(S => {
    const image = window.__draw({ outsideGap: true }).getContext('2d').getImageData(0, 0, 800, 600);
    const tiny = window.__draw();
    const t = tiny.getContext('2d'); t.fillStyle = '#111'; t.fillRect(600, 100, 20, 2); t.fillRect(600, 108, 20, 2); t.fillRect(600, 100, 2, 10); t.fillRect(618, 100, 2, 10);
    const tinyImage = t.getImageData(0, 0, 800, 600);
    return {
      wall: window.T.detectRoom(image, [44, 300], { scale: S }).reason,
      leak: window.T.detectRoom(image, [120, 470], { scale: S }).reason,
      closedNeighbour: window.T.detectRoom(image, [300, 100], { scale: S }).ok,
      outside: window.T.detectRoom(image, [10, 10], { scale: S }).reason,
      small: window.T.detectRoom(tinyImage, [610, 105], { scale: S, closePx: 0 }).reason,
      scale: window.T.detectRoom(image, [600, 150], {}),
    };
  }, S);
  expect(r.wall).toBe('wall');
  expect(r.leak).toBe('open');      // the outside door lets the room run out of the plan
  expect(r.outside).toBe('open');
  expect(r.closedNeighbour).toBe(true);
  expect(r.small).toBe('small');
  expect(r.scale.ok).toBe(false);
  expect(r.scale.reason).toBe('scale');
  expect(r.scale.pixels.length).toBe(4); // the outline is still shown
});

test('detection: an open door merges two rooms until the gap is closed or a separator is drawn', async ({ page }) => {
  await setup(page);
  const r = await page.evaluate(S => {
    const image = window.__draw({ doorGap: true }).getContext('2d').getImageData(0, 0, 800, 600);
    const at = opts => window.T.detectRoom(image, [600, 150], Object.assign({ scale: S }, opts)).areaM2;
    return { merged: at({ closePx: 2 }), closed: at({ closePx: 8 }), separator: at({ closePx: 2, walls: [[402, 145, 402, 170]] }) };
  }, S);
  expect(r.merged).toBeGreaterThan(80);           // wohnen + buero
  expect(Math.abs(r.closed - 28.62) / 28.62).toBeLessThan(0.03);
  expect(Math.abs(r.separator - 28.62) / 28.62).toBeLessThan(0.03);
});

test('detection: a photo-like template (grain, uneven light, blur) still gives the room', async ({ page }) => {
  await setup(page);
  const r = await page.evaluate(S => {
    const image = window.__draw({ photo: true, furniture: true }).getContext('2d').getImageData(0, 0, 800, 600);
    return [window.T.detectRoom(image, [600, 400], { scale: S, closePx: 2 }), window.T.detectRoom(image, [300, 100], { scale: S, closePx: 2 })];
  }, S);
  expect(r[0].ok).toBe(true);
  expect(Math.abs(r[0].areaM2 - 39.63) / 39.63).toBeLessThan(0.05);
  expect(r[1].ok).toBe(true);
  expect(Math.abs(r[1].areaM2 - 60.42) / 60.42).toBeLessThan(0.05);
});

test('template helpers: scale, north arrow, plan mapping, suggestions, assignment keeps openings', async ({ page }) => {
  await setup(page);
  const r = await page.evaluate(() => {
    const T = window.T;
    const u = { width: 800, height: 600, scale_m_per_px: 0.02 };
    const layout = { rooms: [{ id: 'r_buero', room_key: 'buero', floor_id: 'f', polygon: [[0, 0], [4, 0], [4, 3], [0, 3]], provenance: 'config' }],
      openings: [{ id: 'o1', room_id: 'r_buero', edge: 1, offset: 0.5, contacts: ['binary_sensor.f'] }], floors: [] };
    const plan = [[10, 10], [10, 14], [16, 14], [16, 10]]; // clockwise on purpose
    const id = T.assignTraced(layout, { key: 'buero', floorId: 'f', plan });
    const added = T.assignTraced(layout, { key: 'bad', floorId: 'f', plan: [[0, 0], [2, 0], [2, 2], [0, 2]] });
    return {
      scale: T.scaleFromCalibration([0, 0], [300, 400], 10), noScale: T.scaleFromCalibration([0, 0], [1, 0], 10),
      north: [T.northFromArrow([0, 100], [0, 0]), T.northFromArrow([0, 0], [100, 0]), T.northFromArrow([0, 0], [0, 100]), T.northFromArrow([0, 0], [1, 0])],
      plan: T.toPlan(u, [100, 100]), image: T.toImage(u, [2, 10]), provisional: T.displayScale({ width: 1500, height: 900 }),
      match: T.matchRooms(28.6, [{ key: 'a', name: 'A', volume: 50, height: 2.5 }, { key: 'b', name: 'B', length: 7, width: 4.1 }, { key: 'c', name: 'C' }], []).map(m => m.key),
      taken: T.matchRooms(28.6, [{ key: 'a', length: 1, width: 1 }, { key: 'b', length: 7, width: 4.1 }], ['b']).map(m => m.key),
      id, added, room: layout.rooms[0], opening: layout.openings[0], count: layout.rooms.length,
      window: T.openingAt(layout, 'f', [16.2, 12]), far: T.openingAt(layout, 'f', [30, 30]), size: T.scaledSize(4000, 1000),
    };
  });
  expect(r.scale).toBeCloseTo(0.02, 6);
  expect(r.noScale).toBeNull();
  expect(r.north).toEqual([0, 270, 180, null]); // arrow to the right: "up" is west
  expect(r.plan).toEqual([2, 10]);
  expect(r.image).toEqual([100, 100]);
  expect(r.provisional).toBeCloseTo(0.01, 6);
  expect(r.match).toEqual(['b', 'a', 'c']);
  expect(r.taken).toEqual(['a']);
  expect(r.id).toBe('r_buero');
  expect(r.added).toBe('r_bad');
  expect(r.count).toBe(2);
  expect(r.room.provenance).toBe('traced');
  expect(r.room.polygon).toEqual([[16, 10], [16, 14], [10, 14], [10, 10]]); // counter-clockwise
  // the window on the old east wall (x = 4) moves to the new east wall (x = 16), keeping its facade and contact
  expect(r.opening.contacts).toEqual(['binary_sensor.f']);
  expect(r.opening.edge).toBe(0);
  expect(r.opening.offset).toBeCloseTo(0.5, 2);
  expect(r.window.room_id).toBe('r_buero');
  expect(r.window.edge).toBe(0);
  expect(r.far).toBeNull();
  expect(r.size).toEqual([2000, 500]);
});

async function mountEditor(page, { failSave = false, stored = null } = {}) {
  await page.evaluate(({ ROOMS, failSave, stored }) => {
    window.__calls = []; window.__ul = stored ? { f_eg: stored } : {};
    const callWS = async msg => {
      window.__calls.push({ type: msg.type, floor_id: msg.floor_id, underlay: msg.underlay ? Object.assign({}, msg.underlay, { data: msg.underlay.data.length }) : undefined });
      if (msg.type === 'freshairiq/house_map/underlay_get') return { underlay: window.__ul[msg.floor_id] || null };
      if (msg.type === 'freshairiq/house_map/underlay_save') {
        if (failSave) { const e = new Error('E_UNDERLAY_DATA'); e.code = 'invalid_underlay'; throw e; }
        window.__ul[msg.underlay.floor_id] = msg.underlay;
        return { underlays: Object.fromEntries(Object.keys(window.__ul).map(k => [k, {}])) };
      }
      if (msg.type === 'freshairiq/house_map/underlay_delete') { delete window.__ul[msg.floor_id]; return { underlays: {} }; }
      if (msg.type === 'freshairiq/house_map/save') return { revision: msg.base_revision + 1, issues: [] };
      throw new Error('unexpected');
    };
    const el = document.createElement('freshairiq-house-layout-editor');
    el.hass = { callWS, language: 'de' };
    document.getElementById('m').appendChild(el);
    el.setup({ entryId: 'e1', layout: { schema_version: 1, revision: 0, building: { north_deg: 0, units: 'm', north_confirmed: false },
      floors: [{ id: 'f_eg', name: 'EG', level_key: 'eg', order: 0 }], rooms: [], openings: [], connections: [], shading: [] },
      revision: 0, rooms: ROOMS, liveRooms: {}, language: 'de', floor: 'f_eg', underlays: stored ? { f_eg: {} } : {} });
  }, { ROOMS, failSave, stored });
  return page.locator('freshairiq-house-layout-editor');
}
const pngOf = async (page, opts) => Buffer.from(await page.evaluate(o => window.__draw(o).toDataURL('image/png').split(',')[1], opts), 'base64');
// Click a point of the template picture (its own pixels) on the screen, as a user would.
async function tapImage(page, editor, q) {
  const xy = await editor.evaluate((el, q) => {
    const u = el._ul[el._floor], p = window.T.toPlan(u, q), svg = el.shadowRoot.querySelector('svg');
    // Test note 0.26.7.0 CI fix (cross-browser): WebKit ignores scrollIntoView({ block: 'center' }) on an <svg> element; its
    // drawing area (div.canvas, the same box) scrolls in every engine
    (svg.closest('.canvas') || svg).scrollIntoView({ block: 'center' });
    const m = svg.getScreenCTM();
    return [m.a * p[0] + m.c * -p[1] + m.e, m.b * p[0] + m.d * -p[1] + m.f];
  }, q);
  await page.mouse.click(xy[0], xy[1]);
  await settle(page, 60);
}
const click = (editor, selector) => editor.evaluate((el, s) => el.shadowRoot.querySelector(s).click(), selector);

test('editor: upload, calibrate, north, tap rooms, assign, tap a window, save', async ({ page }) => {
  const errors = await setup(page);
  const editor = await mountEditor(page);
  expect(await editor.evaluate(el => el.shadowRoot.textContent)).toContain('PDF bitte vorher als Bild');
  await editor.locator('input[data-f="ul_file"]').setInputFiles({ name: 'plan.png', mimeType: 'image/png', buffer: await pngOf(page, { furniture: true }) });
  await page.waitForFunction(() => window.__calls.some(c => c.type === 'freshairiq/house_map/underlay_save'));
  await settle(page, 150);
  const saved = await page.evaluate(() => window.__calls.find(c => c.type === 'freshairiq/house_map/underlay_save').underlay);
  expect(saved).toMatchObject({ floor_id: 'f_eg', mime: 'image/jpeg', width: 800, height: 600, scale_m_per_px: null, close_px: 2 });
  expect(await editor.evaluate(el => el._tool)).toBe('calibrate');
  expect(await editor.evaluate(el => !!el.shadowRoot.querySelector('image.ul'))).toBe(true);

  // detection before the scale is known: outline yes, assignment no
  await click(editor, '[data-tool="trace"]');
  await tapImage(page, editor, [600, 150]);
  expect(await editor.evaluate(el => el.shadowRoot.textContent)).toContain('zuerst den Maßstab');

  // scale: the outer wall 40..760 px is 14.4 m
  await click(editor, '[data-tool="calibrate"]');
  await tapImage(page, editor, [40, 580]);
  await tapImage(page, editor, [760, 580]);
  await editor.evaluate(el => { el.shadowRoot.querySelector('[data-f="ul_meters"]').value = '14.4'; el.shadowRoot.querySelector('[data-a="ul-calibrate"]').click(); });
  await settle(page, 150);
  const scale = await editor.evaluate(el => el._ul.f_eg.scale_m_per_px);
  expect(Math.abs(scale - 0.02) / 0.02).toBeLessThan(0.03); // clicks land on screen pixels
  expect(await editor.evaluate(el => el._tool)).toBe('trace');

  // tap a room → suggestion by area → assign
  await tapImage(page, editor, [600, 150]);
  const trace = await editor.evaluate(el => ({ ok: el._trace.ok, area: el._trace.areaM2, first: el._trace.matches[0].key }));
  expect(trace.ok).toBe(true);
  expect(Math.abs(trace.area - 28.62) / 28.62).toBeLessThan(0.05);
  expect(trace.first).toBe('buero');
  expect(await editor.evaluate(el => el.shadowRoot.textContent)).toMatch(/Erkannt: 2\d,\d m²/); // German decimal comma
  await click(editor, '[data-assign="buero"]');
  await tapImage(page, editor, [300, 100]);
  expect(await editor.evaluate(el => el._trace.matches[0].key)).toBe('wohnen');
  await editor.evaluate(el => { const s = el.shadowRoot.querySelector('[data-f="ul_assign"]'); s.value = 'wohnen'; s.dispatchEvent(new Event('change')); });
  const rooms = await editor.evaluate(el => el._layout.rooms.map(r => ({ key: r.room_key, n: r.polygon.length, p: r.provenance, floor: r.floor_id })));
  expect(rooms).toEqual([{ key: 'buero', n: 4, p: 'traced', floor: 'f_eg' }, { key: 'wohnen', n: 6, p: 'traced', floor: 'f_eg' }]);
  expect(await editor.evaluate(el => el.shadowRoot.textContent)).toContain('aus der Vorlage erkannt');

  // north: the arrow points to the right of the picture → "up" is west
  await click(editor, '[data-tool="north"]');
  await tapImage(page, editor, [500, 30]);
  await tapImage(page, editor, [700, 30]);
  expect(await editor.evaluate(el => el._layout.building)).toMatchObject({ north_deg: 270, north_confirmed: true });

  // a window by tapping the outer wall of the office
  await click(editor, '[data-tool="window"]');
  await tapImage(page, editor, [755, 150]);
  const opening = await editor.evaluate(el => el._layout.openings[0]);
  expect(opening).toMatchObject({ room_id: 'r_buero', kind: 'window', provenance: 'user' });
  await tapImage(page, editor, [580, 420]);
  expect(await editor.evaluate(el => el._layout.openings.length)).toBe(1);

  // the layout save carries the traced rooms; the picture itself is never part of it
  await click(editor, '[data-a="save"]');
  await settle(page, 100);
  const calls = await page.evaluate(() => window.__calls.map(c => c.type));
  expect(calls).toContain('freshairiq/house_map/save');
  expect(errors).toEqual([]);
});

test('editor: separator line and gap slider are stored; stored template loads; delete; refused upload', async ({ page }) => {
  await setup(page);
  const data = (await pngOf(page, { doorGap: true })).toString('base64');
  const stored = { floor_id: 'f_eg', mime: 'image/png', data, width: 800, height: 600, scale_m_per_px: 0.02, calibration: null, walls: [], close_px: 2, opacity: 0.55 };
  const editor = await mountEditor(page, { stored });
  await page.waitForFunction(() => window.__calls.some(c => c.type === 'freshairiq/house_map/underlay_get'));
  await settle(page, 150);
  expect(await editor.evaluate(el => !!el.shadowRoot.querySelector('image.ul'))).toBe(true);
  await click(editor, '[data-tool="trace"]');
  await tapImage(page, editor, [600, 150]);
  expect(await editor.evaluate(el => el._trace.areaM2)).toBeGreaterThan(80); // runs into the living room
  await click(editor, '[data-tool="separator"]');
  await tapImage(page, editor, [402, 140]);
  await tapImage(page, editor, [402, 175]);
  await settle(page, 100);
  expect(await page.evaluate(() => window.__ul.f_eg.walls.length)).toBe(1);
  await click(editor, '[data-tool="trace"]');
  await tapImage(page, editor, [600, 150]);
  expect(Math.abs((await editor.evaluate(el => el._trace.areaM2)) - 28.62) / 28.62).toBeLessThan(0.05);
  await editor.evaluate(el => { const s = el.shadowRoot.querySelector('[data-f="ul_close"]'); s.value = '6'; s.dispatchEvent(new Event('change')); });
  await settle(page, 100);
  expect(await page.evaluate(() => window.__ul.f_eg.close_px)).toBe(6);
  await editor.evaluate(el => { const s = el.shadowRoot.querySelector('[data-f="ul_show"]'); s.checked = false; s.dispatchEvent(new Event('change')); });
  expect(await editor.evaluate(el => !!el.shadowRoot.querySelector('image.ul'))).toBe(false);
  page.once('dialog', d => d.accept());
  await click(editor, '[data-a="ul-delete"]');
  await settle(page, 100);
  expect(await page.evaluate(() => window.__ul)).toEqual({});
  expect(await editor.evaluate(el => el.shadowRoot.textContent)).toContain('Bild hochladen');

  // a PDF is refused in the browser; a refused save is reported
  await editor.locator('input[data-f="ul_file"]').setInputFiles({ name: 'plan.pdf', mimeType: 'application/pdf', buffer: Buffer.from('%PDF-1.7') });
  await settle(page, 100);
  expect(await editor.evaluate(el => el.shadowRoot.textContent)).toContain('Nur PNG, JPEG oder WebP');
});

test('editor: a refused template upload is shown and nothing is kept', async ({ page }) => {
  await setup(page);
  const editor = await mountEditor(page, { failSave: true });
  await editor.locator('input[data-f="ul_file"]').setInputFiles({ name: 'plan.png', mimeType: 'image/png', buffer: await pngOf(page, {}) });
  await page.waitForFunction(() => window.__calls.some(c => c.type === 'freshairiq/house_map/underlay_save'));
  await settle(page, 100);
  expect(await editor.evaluate(el => el.shadowRoot.textContent)).toContain('Vorlage konnte nicht gespeichert werden');
  expect(await editor.evaluate(el => Object.keys(el._ul))).toEqual([]);
});
