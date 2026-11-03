// FreshAirIQ house map – the visible air (0.26.6.0, order 8): a canvas over the plan on which fine, softly glowing
// threads travel with the modelled wind field (freshairiq-house-flow.js) and leave fading trails, a few brighter
// motes give depth, and – through an open window – part of the outside air flows into the house: narrow at the
// window, widening in the room, narrow again at each door, out through the other window. Labels, walls and symbols
// stay clear (cut out every frame). Drawn at most ~30 times a second by the card's single animation loop; nothing is
// computed per frame that does not move. A modelled picture, not a measurement.

// The field functions come from the card (the same module instance the card loaded with its version query).
let velocity, eddiesAt, gustAt, insideHouse, routePoint, hash;

const FADE = { calm: 0.045, weak: 0.05, moderate: 0.065, strong: 0.085 };
const MAX_DPR = 2;

export class FlowLayer {
  constructor(canvas, F) {
    ({ velocity, eddiesAt, gustAt, insideHouse, routePoint, hash } = F);
    this.canvas = canvas; this.ctx = canvas.getContext("2d");
    this.t = 0; this.field = null; this.routes = []; this.fading = []; this.n = 0; this.stats = { drawn: 0, inside: 0 };
  }
  // The scene of one render: the field, the view box, the routes through the house, the label boxes to keep clear,
  // the rooms (for the wall outline). Particles survive a redraw as long as the wind and the plan are the same.
  setScene({ field, vb, routes = [], clear = [], rooms = [], key = "" }) {
    const cv = this.canvas, w = cv.clientWidth || 0, h = cv.clientHeight || 0, dpr = Math.min(window.devicePixelRatio || 1, MAX_DPR);
    const size = `${Math.round(w * dpr)}x${Math.round(h * dpr)}`;
    if (cv.width !== Math.round(w * dpr) || cv.height !== Math.round(h * dpr)) { cv.width = Math.round(w * dpr); cv.height = Math.round(h * dpr); }
    const k = Math.min(cv.width / vb[2], cv.height / vb[3]) || 1;
    this.map = { k, ox: (cv.width - vb[2] * k) / 2 - vb[0] * k, oy: (cv.height - vb[3] * k) / 2 - vb[1] * k, dpr };
    this.vb = vb; this.clear = clear; this.rooms = rooms; this.field = field;
    const same = key === this.key && size === this.size;
    this.key = key; this.size = size;
    // routes: keep those that stay, let the others fade out for a few seconds (the air settles after closing)
    const next = new Map(routes.map(r => [r.id, r]));
    for (const r of this.routes) if (!next.has(r.id)) this.fading.push({ ...r, gone: this.t });
    this.fading = this.fading.filter(r => !next.has(r.id) && this.t - r.gone < 4);
    const old = new Map(this.routes.map(r => [r.id, r]));
    this.routes = routes.map(r => { const o = old.get(r.id); return o && o.parts && o.profile.length === r.profile.length ? { ...r, parts: o.parts } : { ...r, parts: this._routeParts(r) }; });
    if (!same) this._seed();
    this._paths();
  }
  _routeParts(r) {
    const count = r.tilted ? 16 : 34, parts = [];
    for (let i = 0; i < count; i++) parts.push({ s: hash(i, 3) * r.profile.length, u: hash(i, 5) * 2 - 1, du: 0, spark: hash(i, 9) < 0.08, life: 0 });
    return parts;
  }
  _seed() {
    const f = this.field;
    if (!f) { this.n = 0; this.ctx.clearRect(0, 0, this.canvas.width, this.canvas.height); return; }
    const area = (this.canvas.width * this.canvas.height) / (this.map.dpr * this.map.dpr);
    this.n = Math.round(Math.min(Math.max(area / 1100, 120), 520) * f.density);
    this.px = new Float32Array(this.n); this.py = new Float32Array(this.n); this.age = new Float32Array(this.n); this.life = new Float32Array(this.n);
    for (let i = 0; i < this.n; i++) this._spawn(i, true);
  }
  _spawn(i, anywhere) {
    const f = this.field, vb = this.vb, minX = vb[0], maxX = vb[0] + vb[2], minY = -(vb[1] + vb[3]), maxY = -vb[1];
    for (let tries = 0; tries < 8; tries++) {
      let x, y;
      if (anywhere || Math.random() < 0.45) { x = minX + Math.random() * (maxX - minX); y = minY + Math.random() * (maxY - minY); }
      else {  // on the upwind edge of the drawing
        const along = -1.2 * Math.max(vb[2], vb[3]) / 2, side = (Math.random() * 2 - 1) * Math.max(vb[2], vb[3]) * 0.75;
        x = (minX + maxX) / 2 + f.dir[0] * along + f.perp[0] * side; y = (minY + maxY) / 2 + f.dir[1] * along + f.perp[1] * side;
        x = Math.min(Math.max(x, minX), maxX); y = Math.min(Math.max(y, minY), maxY);
      }
      if (!insideHouse(f, x, y)) { this.px[i] = x; this.py[i] = y; break; }
    }
    this.age[i] = anywhere ? Math.random() * 3 : 0; this.life[i] = 2.5 + Math.random() * 4.5;
  }
  // Path2D of the house outline (canvas pixels) – erased each frame, so walls, windows and doors stay clear.
  _paths() {
    const m = this.map, P = p => [p[0] * m.k + m.ox, -p[1] * m.k + m.oy];
    this.outline = new Path2D();
    for (const r of this.rooms) { r.polygon.forEach((p, j) => { const q = P(p); if (j) this.outline.lineTo(q[0], q[1]); else this.outline.moveTo(q[0], q[1]); }); this.outline.closePath(); }
    this.clearPx = this.clear.map(b => ({ x: b.x * m.k + m.ox - 3 * m.dpr, y: b.y * m.k + m.oy - 3 * m.dpr, w: b.w * m.k + 6 * m.dpr, h: b.h * m.k + 6 * m.dpr }));
  }
  wipe() { this.ctx.clearRect(0, 0, this.canvas.width, this.canvas.height); }
  // Advance by dt seconds and draw. Returns quietly without a field.
  frame(dt) {
    const f = this.field, ctx = this.ctx, m = this.map;
    if (!f && !this.routes.length && !this.fading.length) return;
    this.t += dt;
    if (this.fading.length) this.fading = this.fading.filter(r => this.t - r.gone < 4);
    const W = this.canvas.width, H = this.canvas.height;
    ctx.globalCompositeOperation = "destination-out";
    ctx.fillStyle = `rgba(0,0,0,${f ? (f.mood && f.mood.fade) || FADE[f.cls] : 0.08})`;   // trail length by mood
    ctx.fillRect(0, 0, W, H);
    ctx.globalCompositeOperation = "source-over";
    ctx.lineCap = "round";
    const X = x => x * m.k + m.ox, Y = y => -y * m.k + m.oy;
    let drawn = 0;
    if (f && dt > 0) {
      const gust = gustAt(f, this.t), eddies = eddiesAt(f, this.t), vis = f.vis * (1 + gust * f.gust.amp);
      const buckets = [new Path2D(), new Path2D(), new Path2D()], sparks = new Path2D();
      for (let i = 0; i < this.n; i++) {
        const x = this.px[i], y = this.py[i];
        const v = velocity(f, x, y, this.t, eddies, gust);
        this.age[i] += dt;
        if (!v || this.age[i] > this.life[i]) { this._spawn(i, false); continue; }
        // midpoint step: the threads follow the curves of the field smoothly
        const mx = x + v[0] * dt * 0.5, my = y + v[1] * dt * 0.5, v2 = velocity(f, mx, my, this.t, eddies, gust) || v;
        const nx = x + v2[0] * dt, ny = y + v2[1] * dt;
        if (nx < this.vb[0] || nx > this.vb[0] + this.vb[2] || -ny < this.vb[1] || -ny > this.vb[1] + this.vb[3]) { this._spawn(i, false); continue; }
        const sp = Math.hypot(v2[0], v2[1]) / (vis || 1), env = Math.sin(Math.PI * Math.min(this.age[i] / this.life[i], 1));
        if (sp < 0.12) this.age[i] += dt * 4;                      // caught in an inside corner: let it fade quickly instead of stepping
        const b = buckets[sp * env > 0.95 ? 2 : sp * env > 0.55 ? 1 : 0];
        b.moveTo(X(x), Y(y)); b.lineTo(X(nx), Y(ny));
        if (hash(i, 17) < 0.05) { sparks.moveTo(X(x), Y(y)); sparks.lineTo(X(nx), Y(ny)); }   // a brighter head: depth
        this.px[i] = nx; this.py[i] = ny; drawn++;
      }
      const mood = f.mood || { width: 1.05, colors: ["rgba(214,238,255,.22)", "rgba(226,244,255,.42)", "rgba(240,250,255,.66)"], spark: "rgba(250,253,255,.5)" };
      ctx.lineWidth = mood.width * m.dpr;
      mood.colors.forEach((c, j) => { ctx.strokeStyle = c; ctx.stroke(buckets[j]); });
      ctx.lineWidth = 1.9 * m.dpr; ctx.strokeStyle = mood.spark; ctx.stroke(sparks);
      ctx.save(); ctx.globalCompositeOperation = "destination-out"; ctx.lineWidth = 6 * m.dpr; ctx.stroke(this.outline); ctx.restore();   // the walls stay clear
    }
    // the air through the house: travels along each route, narrow at the openings, wide in the rooms
    let inside = 0;
    if (dt > 0) {
      const vis = f ? f.vis : 1;
      const paths = { open: new Path2D(), calm: new Path2D(), sparks: new Path2D() };
      const runRoute = (r, alpha) => {
        for (const p of r.parts) {
          const was = routePoint(r.profile, p.s, p.u);
          const roomFactor = was[2] >= 0 ? (r.tilted ? 0.32 : 0.55) * (r.closing && r.closing.has(was[2]) ? 0.45 : 1) : 1;
          p.s += vis * roomFactor * dt * (0.85 + 0.3 * hash(Math.round(p.u * 1000), 1));
          p.du += (hash(Math.floor(this.t * 2 + p.u * 50), 23) - 0.5) * 0.15 * dt; p.du *= 0.96; p.u = Math.max(-0.95, Math.min(0.95, p.u + p.du));
          if (p.s >= r.profile.length) { p.s = 0; p.u = hash(Math.floor(this.t * 7 + p.u * 100), 29) * 2 - 1; continue; }
          const now = routePoint(r.profile, p.s, p.u);
          if (Math.hypot(now[0] - was[0], now[1] - was[1]) > vis * dt * 3 + r.profile.length * 0.02) continue;   // never a jump across the room
          if (alpha < 1 && hash(Math.floor(p.s * 13), 31) > alpha) continue;   // fading: fewer threads each moment
          const target = r.closing && now[2] >= 0 && r.closing.has(now[2]) ? paths.calm : paths.open;
          target.moveTo(X(was[0]), Y(was[1])); target.lineTo(X(now[0]), Y(now[1]));
          if (p.spark) { paths.sparks.moveTo(X(was[0]), Y(was[1])); paths.sparks.lineTo(X(now[0]), Y(now[1])); }
          if (now[2] >= 0) inside++;
        }
      };
      for (const r of this.routes) runRoute(r, 1);
      for (const r of this.fading) runRoute(r, Math.max(0, 1 - (this.t - r.gone) / 4));
      ctx.lineWidth = 1.2 * m.dpr;
      ctx.strokeStyle = "rgba(200,244,255,.6)"; ctx.stroke(paths.open);
      ctx.strokeStyle = "rgba(255,226,196,.32)"; ctx.stroke(paths.calm);                 // a room told to close: calmer, warmer
      ctx.lineWidth = 2 * m.dpr; ctx.strokeStyle = "rgba(240,253,255,.6)"; ctx.stroke(paths.sparks);
    }
    // labels stay readable: their boxes are kept clear
    if (this.clearPx.length) { ctx.save(); ctx.globalCompositeOperation = "destination-out"; ctx.fillStyle = "#000"; for (const b of this.clearPx) ctx.fillRect(b.x, b.y, b.w, b.h); ctx.restore(); }
    this.stats = { drawn, inside };
  }
  // With "reduce motion" or the animation off: one calm, still picture of the streamlines (no motion at all).
  still() {
    const f = this.field, ctx = this.ctx, m = this.map;
    this.wipe();
    if (!f) return;
    const X = x => x * m.k + m.ox, Y = y => -y * m.k + m.oy, path = new Path2D(), eddies = eddiesAt(f, 0);
    for (let i = 0; i < 46; i++) {
      this._spawn(i % Math.max(this.n, 1), true);
      let x = this.px[i % Math.max(this.n, 1)], y = this.py[i % Math.max(this.n, 1)];
      path.moveTo(X(x), Y(y));
      for (let s = 0; s < 26; s++) { const v = velocity(f, x, y, 0, eddies, 0); if (!v) break; x += v[0] * 0.04; y += v[1] * 0.04; path.lineTo(X(x), Y(y)); }
    }
    ctx.lineWidth = 1 * m.dpr; ctx.strokeStyle = "rgba(220,242,255,.28)"; ctx.stroke(path);
    ctx.save(); ctx.globalCompositeOperation = "destination-out"; ctx.lineWidth = 6 * m.dpr; ctx.stroke(this.outline); ctx.restore();
    if (this.clearPx.length) { ctx.save(); ctx.globalCompositeOperation = "destination-out"; for (const b of this.clearPx) ctx.fillRect(b.x, b.y, b.w, b.h); ctx.restore(); }
  }
}
