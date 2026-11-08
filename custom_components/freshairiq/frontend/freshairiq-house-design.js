// FreshAirIQ house map: the card's look (0.26.7.0 UI/theme order) – pure helpers and the style of the three designs.
//   freshairiq  the FreshAirIQ design (default – every card without the option keeps its look)
//   ha          the dashboard's Home Assistant theme for the card frame and its windows
//   custom      the user's own colours, border and corner radius
// Only the frame and the windows change. The plan (sky, weather, light, wind) and the state colours of the rooms
// (ventilate, wait, close, critical) are the same in every design – their meaning never depends on a theme.
// Every colour shown is checked against its background: text at least 4.5:1, controls at least 3:1. A theme or a
// choice that would miss this gets a readable replacement (and the card editor says so) instead of unreadable text.

export const DESIGN_MODES = ["freshairiq", "ha", "custom"];
export const TEXT_MODES = ["auto", "light", "dark"];
export const BORDER_MAX = 6;
export const RADIUS_MAX = 32;
const INK = [10, 31, 56], WHITE = [255, 255, 255], BLACK = [0, 0, 0];
const NAVY = [11, 47, 87];                    // the window colour of a custom design without an own choice
const ACCENT = { dark: [0, 216, 240], light: [11, 110, 168] };

// ---- colours: "#rgb", "#rrggbb" and the "rgb()/rgba()" strings a browser reports
export const parseHex = text => {
  const m = /^#([0-9a-f]{3}|[0-9a-f]{6})$/i.exec(String(text == null ? "" : text).trim());
  if (!m) return null;
  const h = m[1].length === 3 ? m[1].split("").map(c => c + c).join("") : m[1];
  return [0, 2, 4].map(i => parseInt(h.slice(i, i + 2), 16));
};
export const parseRgb = text => {
  const m = /rgba?\(([^)]+)\)/.exec(String(text || ""));
  if (!m) return null;
  const v = m[1].split(/[ ,/]+/).filter(Boolean).map(x => (x.endsWith("%") ? Number(x.slice(0, -1)) / 100 : Number(x)));
  if (v.length < 3 || v.slice(0, 3).some(x => !Number.isFinite(x))) return null;
  return [v[0], v[1], v[2], v.length > 3 && Number.isFinite(v[3]) ? v[3] : 1];
};
export const css = c => (c.length > 3 && c[3] < 1 ? `rgba(${c.slice(0, 3).map(Math.round).join(",")},${Math.round(c[3] * 1000) / 1000})` : `rgb(${c.slice(0, 3).map(Math.round).join(",")})`);
export const luminance = c => { const f = x => { x /= 255; return x <= 0.03928 ? x / 12.92 : ((x + 0.055) / 1.055) ** 2.4; }; return 0.2126 * f(c[0]) + 0.7152 * f(c[1]) + 0.0722 * f(c[2]); };
export const contrast = (a, b) => { const x = luminance(a), y = luminance(b); return (Math.max(x, y) + 0.05) / (Math.min(x, y) + 0.05); };
// a translucent colour laid over an opaque one
export const over = (top, base) => { const a = top.length > 3 ? top[3] : 1; return [0, 1, 2].map(i => top[i] * a + base[i] * (1 - a)); };
// the more readable of the house map's ink and white on a background (black/white as the last resort)
export const onColor = bg => {
  const c = Array.isArray(bg) ? bg : parseHex(bg) || parseRgb(bg);
  if (!c) return css(INK);
  const best = [INK, WHITE].sort((p, q) => contrast(q, c) - contrast(p, c))[0];
  return css(contrast(best, c) >= 4.5 ? best : contrast(BLACK, c) >= contrast(WHITE, c) ? BLACK : WHITE);
};

// ---- the stored options (card config): invalid values are not used – the editor names them
const int = (v, max) => { const n = Number(v); return Number.isFinite(n) ? Math.min(Math.max(Math.round(n), 0), max) : null; };
export function designMode(config) { const m = config && config.design; return DESIGN_MODES.includes(m) ? m : "freshairiq"; }
export function customChoice(config) {
  const c = config || {}, issues = [];
  const colour = key => { if (c[key] == null || c[key] === "") return null; const v = parseHex(c[key]); if (!v) issues.push(`${key}_invalid`); return v; };
  const background = c.design_background === "transparent" ? "transparent" : colour("design_background");
  const text = TEXT_MODES.includes(c.design_text) ? c.design_text : "auto";
  if (c.design_text != null && !TEXT_MODES.includes(c.design_text)) issues.push("design_text_invalid");
  return { accent: colour("design_accent"), background, dialog: colour("design_dialog"), text,
    border: c.design_border == null || c.design_border === "" ? null : int(c.design_border, BORDER_MAX),
    radius: c.design_radius == null || c.design_radius === "" ? null : int(c.design_radius, RADIUS_MAX), issues };
}

// ---- the palette of the windows from a background, a wanted text colour and accent (all checked)
// ``base`` is what lies behind a translucent window colour (the theme's page colour) – a window is always opaque.
export function palette({ dialog, text = null, muted = null, accent = null, onAccent = null, base = null, textMode = "auto" }) {
  const issues = [];
  let bg = dialog || NAVY;
  if (bg.length > 3 && bg[3] < 0.98) { bg = over(bg, base && (base.length < 4 || base[3] >= 0.98) ? base : luminance(bg) < 0.2 ? NAVY : WHITE); issues.push("dialog_translucent"); }
  const scheme = contrast(WHITE, bg) >= contrast(INK, bg) ? "dark" : "light";
  const own = scheme === "dark" ? WHITE : INK;
  const auto = contrast(own, bg) >= 4.5 ? own : [WHITE, BLACK].sort((p, q) => contrast(q, bg) - contrast(p, bg))[0];
  let fg = textMode === "light" ? WHITE : textMode === "dark" ? INK : text || auto;
  if (contrast(fg, bg) < 4.5) { if (text || textMode !== "auto") issues.push("text_contrast"); fg = auto; }
  // text sits on the window or on up to two tinted layers (a tile in a section): it must be readable on the darkest one
  const veilRgb = scheme === "dark" ? [0, 0, 0] : [10, 31, 56], tint = scheme === "dark" ? 0.22 : 0.05;
  const deepest = over([...veilRgb, tint], over([...veilRgb, tint], bg)), readable = c => c && contrast(c, bg) >= 4.5 && contrast(c, deepest) >= 4.5;
  if (!readable(fg)) fg = [WHITE, BLACK].sort((p, q) => Math.min(contrast(q, bg), contrast(q, deepest)) - Math.min(contrast(p, bg), contrast(p, deepest)))[0];
  const quiet = scheme === "dark" ? [169, 203, 230] : [51, 73, 93];
  const soft = readable(muted) ? muted : readable(quiet) ? quiet : fg;
  let acc = accent || ACCENT[scheme], on = onAccent && contrast(onAccent, acc) >= 4.5 ? onAccent : null;
  if (!on) on = parseRgb(onColor(acc));
  if (contrast(on, acc) < 4.5) { if (accent) issues.push("accent_contrast"); acc = ACCENT[scheme]; on = parseRgb(onColor(acc)); }
  // a button must stand out from the window: an accent too close to the window colour gets the text colour as its edge
  const edge = contrast(acc, bg) >= 3 ? acc : fg;
  const focus = scheme === "dark" ? (contrast([255, 210, 122], bg) >= 3 ? [255, 210, 122] : fg) : (contrast([154, 77, 0], bg) >= 3 ? [154, 77, 0] : fg);
  const good = scheme === "dark" ? (contrast([191, 240, 211], bg) >= 4.5 ? [191, 240, 211] : fg) : (contrast([11, 107, 54], bg) >= 4.5 ? [11, 107, 54] : fg);
  const veil = scheme === "dark" ? "0,0,0" : "10,31,56";
  return {
    scheme, issues, bg, fg,
    vars: {
      "--fq-dlg-bg": css(bg), "--fq-fg": css(fg), "--fq-strong": css(fg), "--fq-soft": css(fg), "--fq-muted": css(soft), "--fq-muted2": css(soft),
      "--fq-good": css(good), "--fq-focus": css(focus), "--fq-icon": css(soft), "--fq-accent": css(acc), "--fq-on-accent": css(on), "--fq-edge": css(edge),
      "--fq-surface": `rgba(${veil},${tint})`, "--fq-line2": css([...fg, 0.28]), "--fq-track": css([...fg, 0.16]),
      "--fq-btn": `rgba(${veil},${scheme === "dark" ? 0.3 : 0.07})`, "--fq-btn-fg": css(fg), "--fq-line": css([...fg, 0.35]),
    },
  };
}

// ---- the style of the designs: active only with data-design on the card (the FreshAirIQ design sets nothing)
export const DESIGN_STYLE = `
:host([data-design]) ha-card{background:var(--fq-card-bg);color:var(--fq-card-fg,inherit);border:var(--fq-border-w,1px) solid var(--fq-card-line,var(--fq-line));border-radius:var(--fq-radius,12px);box-shadow:var(--fq-card-shadow,none)}
:host([data-design][data-glass]) ha-card{-webkit-backdrop-filter:var(--fq-card-blur,none);backdrop-filter:var(--fq-card-blur,none)}
:host([data-design]) dialog .dlg:not(.wxdlg){--fq-fg:var(--fq-fg-d);--fq-strong:var(--fq-fg-d);--fq-soft:var(--fq-fg-d);--fq-muted:var(--fq-muted-d);--fq-muted2:var(--fq-muted-d);--fq-good:var(--fq-good-d);
  --fq-focus:var(--fq-focus-d);--fq-icon:var(--fq-muted-d);--fq-accent:var(--fq-accent-d);--fq-on-accent:var(--fq-on-accent-d);--fq-surface:var(--fq-surface-d);--fq-line2:var(--fq-line2-d);--fq-track:var(--fq-track-d);
  --fq-btn:var(--fq-btn-d);--fq-btn-fg:var(--fq-fg-d);
  background:var(--fq-dlg-bg-d);color:var(--fq-fg-d);border:var(--fq-border-w,1px) solid var(--fq-line-d);border-radius:var(--fq-radius,16px);box-shadow:0 12px 36px rgba(0,0,0,.35)}
:host([data-design]) dialog .dlg:not(.wxdlg) header{border-bottom:var(--fq-border-w,1px) solid var(--fq-line-d)}
:host([data-design]) dialog .dlg:not(.wxdlg) .foot button,:host([data-design]) dialog .dlg:not(.wxdlg) button[aria-pressed="true"]{border:2px solid var(--fq-edge-d);box-shadow:none}
:host([data-design]) dialog .dlg:not(.wxdlg) button{border-color:var(--fq-line-d);box-shadow:none}
:host([data-design]) dialog .dlg:not(.wxdlg) .ptile strong,:host([data-design]) dialog .dlg:not(.wxdlg) .classic h2,:host([data-design]) dialog .dlg:not(.wxdlg) .classic h3{color:var(--fq-fg-d)}
:host([data-design]) dialog .dlg:not(.wxdlg) .mitem .mi{background:var(--fq-surface-d);border:1px solid var(--fq-line2-d)}
:host([data-design]) dialog .dlg:not(.wxdlg) .kpi{background:var(--fq-surface-d);border:1px solid var(--fq-line2-d);box-shadow:none;color:var(--fq-fg-d)}
:host([data-design]) dialog .dlg:not(.wxdlg) .kpi .lbl{color:var(--fq-muted-d);opacity:1}:host([data-design]) dialog .dlg:not(.wxdlg) .kpi .sub{opacity:1;color:var(--fq-muted-d)}
:host([data-design][data-scheme="light"]) dialog .dlg:not(.wxdlg) .mdot{box-shadow:0 0 0 1.5px var(--fq-fg-d)}
:host([data-design][data-scheme="light"]) dialog .dlg:not(.wxdlg) button.rcard,:host([data-design][data-scheme="light"]) dialog .dlg:not(.wxdlg) .rcard .ract{background:var(--fq-surface-d)}
`;

// the host's custom properties for a palette (the window ones end in -d: they are set on the windows only, so the plan
// and its controls keep their own colours)
export const paletteVars = p => Object.fromEntries(Object.entries(p.vars).map(([k, v]) => [k === "--fq-dlg-bg" ? "--fq-dlg-bg-d" : `${k}-d`, v]));
