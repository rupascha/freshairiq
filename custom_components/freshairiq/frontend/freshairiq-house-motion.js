// FreshAirIQ house map – how much moves (0.26.7.0(2)). One place decides the animation of the card: the level the user chose,
// what the device and the card's size allow, whether anything is seen at all and how long nobody touched the card. Pure
// functions only; the card applies the result (its one animation loop, a few CSS switches on its host).
//
// Levels: off (no decorative motion – a still picture), minimal (very calm, few elements, low frame rate – saves energy),
// normal (the balanced default), intense (more weather and wind, still bounded), auto (by the device: reduced motion → off,
// a phone or a small card → minimal, otherwise normal). The parts – wind, weather, light, ambient – can be switched one by one
// (animation_parts); the profile carries each part separately so further single options need no new structure.

export const ANIMATION_LEVELS = ["off", "minimal", "normal", "intense", "auto"];
export const MOTION_PARTS = ["wind", "weather", "light", "ambient"];
// after this long without a touch, a click, a key or the card coming into view the motion steps down, then rests (a still
// picture) – a dashboard left open on a wall or a phone keeps its information, not its CPU
export const CALM_AFTER_MS = 2 * 60 * 1000;
export const REST_AFTER_MS = 10 * 60 * 1000;

const list = v => (v == null ? null : (Array.isArray(v) ? v : String(v).split(",")).map(x => String(x).trim()).filter(Boolean));

// What the loop and the drawing may do at each level. fps: how often the wind is drawn (the browser's 60 is never needed for
// soft air); streams / strands: decorative wind ribbons around the house and the layers of each (more in strong wind, fewer in
// calm air); routeParts: the share of the canvas air through an open window (there are no threads around the house any more); pace: how fast the air seems to move (calmer < 1).
export const PROFILES = {
  off: { dpr: 1, fps: 0, streams: 7, strands: 1, routeParts: 0, pace: 0 },
  minimal: { dpr: 1, fps: 12, streams: 3, strands: 1, routeParts: 0.4, pace: 0.7 },
  normal: { dpr: 1.5, fps: 20, streams: 5, strands: 2, routeParts: 0.65, pace: 0.8 },
  // 0.26.7.0 UI hotfix: "intense" is the lively picture again – more ribbons in three layers (the stream, a bright companion,
  // the broad air mass), a stronger swing and brightness, a quicker pace; still no shooting-star strokes and 30 frames a second
  intense: { dpr: 2, fps: 30, streams: 8, strands: 3, routeParts: 1, pace: 1.1, amp: 1.35, glow: 1.25 },
};

// The level the user asked for. ``animation: false`` (older cards) means off; nothing chosen means auto.
export const chosenLevel = (config = {}) => (config.animation === false ? "off" : ANIMATION_LEVELS.includes(config.animation_level) ? config.animation_level : "auto");
export const chosenParts = (config = {}) => { const l = list(config.animation_parts); return l == null ? MOTION_PARTS.slice() : l.filter(p => MOTION_PARTS.includes(p)); };

// The level in effect now. ``small``: a narrow card (< 520 px) or a phone (coarse pointer and a small screen).
export function effectiveLevel({ config = {}, reduced = false, small = false, idleMs = 0 } = {}) {
  let level = chosenLevel(config);
  if (reduced) return "off";                       // the system asks for reduced motion: still, always
  // 0.26.7.0 UI hotfix: only "auto" adapts by itself (device, card size, untouched time); a level the user chose explicitly
  // stays what it is while the card is seen – hidden pages, cards out of view and reduced motion still pause or stop it
  if (level !== "auto") return level;
  level = small ? "minimal" : "normal";
  if (idleMs >= REST_AFTER_MS) return "rest";      // long untouched: a still picture until the next touch
  if (idleMs >= CALM_AFTER_MS && level !== "minimal") return "minimal";
  return level;
}
// The full profile: the level's numbers plus each part on or off ("rest" draws like "off" but says why)
export function motionProfile(args = {}) {
  const level = effectiveLevel(args), parts = chosenParts(args.config), still = level === "off" || level === "rest";
  const base = PROFILES[still ? "off" : level];
  return { level, still, ...base, parts: Object.fromEntries(MOTION_PARTS.map(p => [p, !still && parts.includes(p)])) };
}
// A phone or a small card: a narrow card, or a touch screen of phone size
export function isSmallDevice(width, env = typeof window !== "undefined" ? window : null) {
  if (width > 0 && width < 520) return true;
  if (!env) return false;
  const coarse = !!(env.matchMedia && env.matchMedia("(pointer: coarse)").matches);
  const screen = Math.min((env.screen && env.screen.width) || env.innerWidth || 1024, (env.screen && env.screen.height) || env.innerHeight || 1024);
  return coarse && screen < 600;
}

// ---- wind without repetition: every stream its own character, the same for the same house and wind (no flicker on redraw)
const seeded = seed => { let x = (seed >>> 0) || 7; return () => ((x = (x * 1664525 + 1013904223) >>> 0) / 4294967296); };
// ``count`` streams across the house: their positions are spread, never on an even grid; each has its own length (start and end
// along its line), amplitude, wave length, pace, phase offset, opacity and width – so no two look alike or move in step.
export function streamVariety(count, seed = 1) {
  const rnd = seeded(Math.round(seed * 9973) + count * 31), out = [];
  for (let i = 0; i < count; i++) {
    const slot = count > 1 ? -1 + (2 * i) / (count - 1) : 0;
    out.push({
      lane: Math.max(-1, Math.min(1, slot + (rnd() - 0.5) * (1.4 / Math.max(count, 2)))),   // jittered, never an even grid
      start: rnd() * 0.22, end: 0.72 + rnd() * 0.28,                                          // its own length
      amp: 0.55 + rnd() * 0.85, wave: 0.7 + rnd() * 0.8, pace: 0.6 + rnd() * 0.65,            // its own wave and speed
      offset: rnd(), opacity: 0.45 + rnd() * 0.45, width: 0.75 + rnd() * 0.6,
    });
  }
  return out;
}

// ---- one animation loop for every house map on the page (several cards never start several loops). Each card asks for its
// own frame rate; between frames nothing runs – the loop sleeps until the next card is due (a timer, then one animation frame),
// instead of waking the browser 60 times a second for air that moves softly.
const LOOP = { subs: new Map(), timer: null, raf: null };
function schedule() {
  if (LOOP.raf || LOOP.timer || !LOOP.subs.size) return;
  const now = performance.now();
  let wait = Infinity;
  for (const s of LOOP.subs.values()) wait = Math.min(wait, s.last ? s.last + 1000 / s.fps - now : 0);
  const go = () => { LOOP.timer = null; LOOP.raf = requestAnimationFrame(run); };
  if (wait <= 14) go(); else LOOP.timer = setTimeout(go, wait - 10);
}
function run(now) {
  LOOP.raf = null;
  for (const [owner, s] of [...LOOP.subs]) {
    if (!LOOP.subs.has(owner) || (s.last && now - s.last < 1000 / s.fps - 6)) continue;
    const dt = s.last ? now - s.last : 0;
    s.last = now;
    try { s.fn(now, dt); } catch (err) { console.error("FreshAirIQ house map animation", err); }
  }
  schedule();
}
// register ``owner``'s frame function at ``fps``; returns a handle (truthy) – the same owner registered again replaces itself
export function tick(owner, fn, fps) {
  const old = LOOP.subs.get(owner);
  const handle = { fps, fn, last: old ? old.last : 0 };
  LOOP.subs.set(owner, handle);
  schedule();
  return handle;
}
export function untick(owner) {
  LOOP.subs.delete(owner);
  if (!LOOP.subs.size) { clearTimeout(LOOP.timer); LOOP.timer = null; if (LOOP.raf) cancelAnimationFrame(LOOP.raf); LOOP.raf = null; }
}
export const loopSize = () => LOOP.subs.size;   // for the tests: one entry per animating card, none left behind
