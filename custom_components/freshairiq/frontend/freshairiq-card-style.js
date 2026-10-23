// FreshAirIQ card colours and themes (0.26.5.3, GitHub #17).
//
// Every colour of the card stylesheet and of inline styles reads a
// --freshairiq-* variable whose fallback is the original colour. The default
// design therefore stays identical, while Home Assistant themes, card-mod and
// UIX can override it down to the tiles. "theme: auto" fills the variables from
// the active Home Assistant theme (FAIQ_THEME_AUTO_CSS) and mixes coloured text
// with the theme's text colour so it stays readable on light and dark themes.
//
// Variables: --freshairiq-card-background, -card-border-radius, -card-border-width,
// -card-border-color, -card-box-shadow, -card-backdrop-filter, -surface,
// -dialog-background, -text-color, -secondary-text-color, -overlay-rgb (tiles and
// lines), -accent, -accent-rgb, -color-ventilate/-ok/-close/-wait/-alert/-neutral,
// -tone (auto only; 100% keeps the pure colours).
//
// Loaded by freshairiq-card.js with the card version (?v=), like the English module.
export const FAIQ_STATUS_COLORS = {"#62e889":"ventilate","#67df92":"ok","#73df99":"ok","#ffb45f":"close","#e2bd69":"wait","#f0b357":"wait","#f2c45d":"wait","#ff7770":"alert","#ff7b7b":"alert","#ff9b7a":"alert","#9aa7b3":"neutral"};
export const faiqParseColor = token => {
    const t = String(token).trim().toLowerCase();
    let m = /^#([0-9a-f]{3,4})$/.exec(t);
    if (m) { const h = m[1].split("").map(x => parseInt(x + x, 16)); return { r: h[0], g: h[1], b: h[2], a: h.length > 3 ? h[3] / 255 : 1 }; }
    m = /^#([0-9a-f]{6})([0-9a-f]{2})?$/.exec(t);
    if (m) { const n = parseInt(m[1], 16); return { r: n >> 16 & 255, g: n >> 8 & 255, b: n & 255, a: m[2] ? parseInt(m[2], 16) / 255 : 1 }; }
    m = /^rgba?\(\s*([\d.]+)\s*,\s*([\d.]+)\s*,\s*([\d.]+)\s*(?:,\s*([\d.]+)\s*)?\)$/.exec(t);
    return m ? { r: +m[1], g: +m[2], b: +m[3], a: m[4] === undefined ? 1 : +m[4] } : null;
};
export const faiqAlpha = a => String(Math.round(a * 1e4) / 1e4);
// theme: auto mixes coloured text with the theme's text colour so it stays readable (--freshairiq-tone:100% = pure)
export const faiqTone = (color, auto) => auto ? `color-mix(in srgb,${color} var(--freshairiq-tone,62%),var(--freshairiq-text-color,#e1e1e1))` : color;
export const faiqThemeColor = (token, auto = false) => {
    const status = FAIQ_STATUS_COLORS[String(token).toLowerCase()];
    if (status) return faiqTone(`var(--freshairiq-color-${status},${token})`, auto);
    const c = faiqParseColor(token);
    if (!c) return token;
    const { r, g, b, a } = c, max = Math.max(r, g, b), min = Math.min(r, g, b);
    if (r === 255 && g === 255 && b === 255 && a < 1) return `rgba(var(--freshairiq-overlay-rgb,255,255,255),${faiqAlpha(a)})`;
    if (max === 0) return token;
    if (b >= 230 && g >= 180 && r <= 140 && b - r >= 100) return a < 1 ? `rgba(var(--freshairiq-accent-rgb,${r},${g},${b}),${faiqAlpha(a)})` : faiqTone(`var(--freshairiq-accent,${token})`, auto);
    if (max < 64 && a >= 0.75) return `var(--freshairiq-surface,${token})`;
    if (a === 1 && max - min <= 45 && max >= 110) return `var(--freshairiq-${max >= 215 ? "" : "secondary-"}text-color,${token})`;
    return a === 1 && max >= 110 ? faiqTone(token, auto) : token;
};
export const FAIQ_COLOR_TOKEN = /#[0-9a-fA-F]{8}\b|#[0-9a-fA-F]{6}\b|#[0-9a-fA-F]{3,4}\b|rgba?\([\d.\s,]+\)/g;
export const faiqThemeCss = (css, auto = false) => css.replace(/\{([^{}]*)\}/g, (all, body) => `{${body.replace(FAIQ_COLOR_TOKEN, t => faiqThemeColor(t, auto))}}`); // declarations only, never #id selectors
export const faiqThemeInline = (html, auto = false) => String(html).replace(/style="([^"]*)"/g, (all, body) => `style="${body.replace(FAIQ_COLOR_TOKEN, t => faiqThemeColor(t, auto))}"`);
// The card frame reads the variables too (fallbacks = the FreshAirIQ design); appended after the card CSS.
export const FAIQ_THEME_AUTO_CSS = `ha-card{border-radius:var(--freshairiq-card-border-radius,22px);border-style:solid;border-width:var(--freshairiq-card-border-width,1px);border-color:var(--freshairiq-card-border-color,rgba(80,205,245,.13));background:var(--freshairiq-card-background,radial-gradient(circle at 92% 0%,rgba(60,205,255,.10),transparent 34%),linear-gradient(135deg,rgba(22,29,38,.99),rgba(17,23,30,.99)));-webkit-backdrop-filter:var(--freshairiq-card-backdrop-filter,none);backdrop-filter:var(--freshairiq-card-backdrop-filter,none);box-shadow:var(--freshairiq-card-box-shadow,0 10px 30px rgba(0,0,0,.20))}:host([data-freshairiq-theme="auto"]){color-scheme:light dark;--freshairiq-card-background:var(--ha-card-background,var(--card-background-color,#1c1c1c));--freshairiq-card-border-radius:var(--ha-card-border-radius,12px);--freshairiq-card-border-width:var(--ha-card-border-width,1px);--freshairiq-card-border-color:var(--ha-card-border-color,var(--divider-color,rgba(127,127,127,.24)));--freshairiq-card-box-shadow:var(--ha-card-box-shadow,none);--freshairiq-card-backdrop-filter:var(--ha-card-backdrop-filter,none);--freshairiq-surface:var(--card-background-color,var(--primary-background-color,#1c1c1c));--freshairiq-dialog-background:var(--primary-background-color,var(--card-background-color,#1c1c1c));--freshairiq-text-color:var(--primary-text-color,#e1e1e1);--freshairiq-secondary-text-color:var(--secondary-text-color,#9b9b9b);--freshairiq-overlay-rgb:var(--rgb-primary-text-color,255,255,255);--freshairiq-accent:var(--primary-color,#03a9f4);--freshairiq-accent-rgb:var(--rgb-primary-color,3,169,244)}:host([data-freshairiq-theme="auto"]) :is(.dialog,.dialog-scroll,.dialog-head,.subdialog,.info-nav){background:var(--freshairiq-dialog-background)}`;
