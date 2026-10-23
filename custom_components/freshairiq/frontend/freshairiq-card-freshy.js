// Freshy, the FreshAirIQ mascot (split out of freshairiq-card.js in 0.26.5.3).
// Loaded by the card with the card version (?v=), like the English module.
const esc = v => String(v !== null && v !== void 0 ? v : "").split("&").join("&amp;").split("<").join("&lt;").split(">").join("&gt;").split('"').join("&quot;").split("'").join("&#039;");
// Freshy (0.26.4.8): the FreshAirIQ mascot as an animated vector character.
// One drawing, nineteen moods plus a night cap that combines with any mood.
// The mood only switches CSS classes; every motion lives in FAIQ_FRESHY_CSS,
// loops seamlessly and stops under prefers-reduced-motion.
// ---------------------------------------------------------------------------
export const FRESHY_MOODS = ["ok", "act", "run", "done", "night", "sleepy", "morning", "rain", "rain_soon", "snow", "frost", "heat", "wait", "cool", "mould", "sensor", "pollen", "dust", "learn"];
export const FRESHY_EPOCH = (typeof performance !== "undefined" && performance.now) ? performance.now() : Date.now();
export const freshyClock = () => ((typeof performance !== "undefined" && performance.now) ? performance.now() : Date.now());
export const FRESHY_LABELS = {
    de: { ok: "Freshy ist zufrieden", act: "Freshy möchte, dass du lüftest", run: "Freshy lüftet mit", done: "Freshy nickt: Ziel erreicht", night: "Freshy schläft", sleepy: "Freshy wird müde – bald ist Nacht", morning: "Freshy wacht auf: Guten Morgen", rain: "Freshy hält ein Blatt als Schirm: es regnet", rain_soon: "Freshy sieht Regen kommen", snow: "Freshy schaut dem Schnee zu", frost: "Freshy friert – kurz lüften reicht", heat: "Freshy trägt Sonnenbrille: draußen ist es heiß", wait: "Freshy wartet auf den besseren Zeitpunkt", cool: "Freshy fächelt sich Luft zu", mould: "Freshy ist besorgt", sensor: "Freshy vermisst einen Sensor", pollen: "Freshy niest", dust: "Freshy trägt eine Maske: Feinstaub draußen", learn: "Freshy denkt nach" },
    en: { ok: "Freshy is happy", act: "Freshy wants you to air the rooms", run: "Freshy is airing with you", done: "Freshy nods: goal reached", night: "Freshy is asleep", sleepy: "Freshy is getting sleepy – night is coming", morning: "Freshy wakes up: good morning", rain: "Freshy holds a leaf as an umbrella: it is raining", rain_soon: "Freshy sees rain coming", snow: "Freshy watches the snow", frost: "Freshy is cold – a short airing is enough", heat: "Freshy wears sunglasses: it is hot outside", wait: "Freshy waits for a better moment", cool: "Freshy fans itself", mould: "Freshy is worried", sensor: "Freshy misses a sensor", pollen: "Freshy sneezes", dust: "Freshy wears a mask: fine dust outside", learn: "Freshy is thinking" },
};
// Both eyes of one face always use the same drawing (left at x=89, right at x=111).
export const freshyEyes = (left, right = left) => left + right;
export const freshyEyePair = draw => freshyEyes(draw(89), draw(111));
export function freshySvg(mood, size = 150, lang = "de", progress = null, options = {}) {
    const m = FRESHY_MOODS.includes(mood) ? mood : "ok";
    const w = Math.round(size), h = Math.round(size * 140 / 160);
    const label = (FRESHY_LABELS[lang] || FRESHY_LABELS.de)[m];
    // Progress ring (mood "run"): circumference of r=49 is ~308.
    const p = Math.max(0, Math.min(1, Number.isFinite(Number(progress)) ? Number(progress) : 0.6));
    const dash = `${Math.round(308 * p)} 308`;
    const sec = value => `${(Number.isFinite(Number(value)) ? Number(value) : 0).toFixed(2)}s`;
    // --frp: shared animation clock; --frin: fade-in only right after a mood change.
    const style = `--frp:${sec(options.phase)};--frin:${sec(options.since == null ? -9 : options.since)}`;
    const cap = options.cap ? " fr-cap" : "";
    const smile = `<path d="M93 81 C 97 86.5, 103 86.5, 107 81" fill="none" stroke="#9FEFFF" stroke-width="2.5" stroke-linecap="round"></path>`;
    const pupil = (x, dx = 1.6, dy = -2.6, r = 1.7) => `<circle cx="${x + dx}" cy="${66 + dy}" r="${r}" fill="#06141E"></circle>`;
    // One eye = white + pupil (+ extra) in one blinking group, so the pupil blinks too.
    const awakeEye = (x, inner = pupil(x)) => `<g class="fr-eye"><ellipse cx="${x}" cy="66" rx="5.2" ry="7" fill="#CFF8FF"></ellipse>${inner}</g>`;
    return `<svg class="fr fr-${m}${cap}" style="${style}" width="${w}" height="${h}" viewBox="0 0 160 140" role="img" aria-label="${esc(label)}">
<defs>
<radialGradient id="frBody" cx="38%" cy="32%" r="75%"><stop offset="0%" stop-color="#123447"></stop><stop offset="45%" stop-color="#06141E"></stop><stop offset="100%" stop-color="#020609"></stop></radialGradient>
<filter id="frGlow" x="-40%" y="-40%" width="180%" height="180%"><feGaussianBlur stdDeviation="4.2" result="b"></feGaussianBlur><feMerge><feMergeNode in="b"></feMergeNode><feMergeNode in="SourceGraphic"></feMergeNode></feMerge></filter>
<filter id="frSoft" x="-40%" y="-40%" width="180%" height="180%"><feGaussianBlur stdDeviation="1.4" result="b"></feGaussianBlur><feMerge><feMergeNode in="b"></feMergeNode><feMergeNode in="SourceGraphic"></feMergeNode></feMerge></filter>
</defs>
<g class="frx frx-sun"><g class="frx-sun-rays" stroke="#FFD27A" stroke-width="2.4" stroke-linecap="round"><path d="M142 4 V 0"></path><path d="M142 36 V 40"></path><path d="M126 20 H 122"></path><path d="M158 20 H 162"></path><path d="M131 9 L 128 6"></path><path d="M153 31 L 156 34"></path><path d="M153 9 L 156 6"></path><path d="M131 31 L 128 34"></path></g><circle cx="142" cy="20" r="10" fill="#FFD27A"></circle><circle cx="142" cy="20" r="10" fill="none" stroke="#FFF1C9" stroke-opacity=".7" stroke-width="1.5"></circle></g>
<g class="frx frx-heatwave" fill="none" stroke="#FFB45F" stroke-width="1.8" stroke-linecap="round"><path d="M128 50 C 132 46, 136 54, 140 50 C 144 46, 148 54, 152 50"></path><path d="M126 62 C 130 58, 134 66, 138 62 C 142 58, 146 66, 150 62"></path></g>
<g class="frx frx-rain" stroke="#7DD3E8" stroke-width="2" stroke-linecap="round" opacity=".85"><path d="M14 14v9"></path><path d="M30 2v9"></path><path d="M150 10v9"></path><path d="M140 0v9"></path><path d="M6 34v9"></path><path d="M156 34v9"></path></g>
<g class="frx frx-snow" fill="none" stroke="#EAF6FF" stroke-width="1.6" stroke-linecap="round"><g><path d="M18 8 v8 M14 12 h8 M15.2 9.2 l5.6 5.6 M20.8 9.2 l-5.6 5.6"></path></g><g><path d="M146 4 v8 M142 8 h8 M143.2 5.2 l5.6 5.6 M148.8 5.2 l-5.6 5.6"></path></g><g><path d="M36 0 v6 M33 3 h6"></path></g><g><path d="M128 14 v6 M125 17 h6"></path></g></g>
<g class="frx frx-cloud"><g class="frx-cloud-body"><path d="M122 26 C 116 26, 114 18, 120 16 C 120 9, 130 7, 133 12 C 136 6, 147 8, 146 15 C 153 15, 154 26, 147 26 Z" fill="#C9D9E4"></path><path d="M124 23 H 145" stroke="#AFC3D0" stroke-width="1.4" stroke-linecap="round"></path></g><path class="frx-cloud-drop" d="M134 29 C 134 29, 131 33, 131 35 a3 3 0 0 0 6 0 C 137 33, 134 29, 134 29 Z" fill="#7DD3E8"></path></g>
<g class="fr-whole">
<g class="fr-leaves">
<path d="M55 76 C 46 82, 38 92, 29 104" fill="none" stroke="#6EE7B7" stroke-width="3" stroke-linecap="round"></path>
<g class="fr-leaf-big"><path d="M53 69 C 28 66, 9 45, 13 15 C 41 19, 58 41, 53 69 Z" fill="#6EE7B7"></path><path d="M51 65 C 40 52, 27 36, 16 19" fill="none" stroke="#A8F5D6" stroke-width="1.6" stroke-linecap="round"></path></g>
<path d="M31 101 C 17 97, 8 106, 10 120 C 25 122, 34 113, 31 101 Z" fill="#6EE7B7"></path>
<path d="M29 104 C 23 109, 17 113, 12 118" fill="none" stroke="#A8F5D6" stroke-width="1.3" stroke-linecap="round"></path>
</g>
<g class="fr-body">
<circle class="fr-halo" cx="96" cy="70" r="49.5" fill="none" stroke-width="5" stroke-opacity=".35" filter="url(#frGlow)"></circle>
<circle class="fr-halo" cx="96" cy="70" r="49" fill="none" stroke-width="3.4" filter="url(#frGlow)"></circle>
<g class="fr-halo-run"><circle cx="96" cy="70" r="49" fill="none" stroke="#1E3A4C" stroke-width="5"></circle><circle cx="96" cy="70" r="49" fill="none" stroke="#7DD3E8" stroke-width="5" stroke-linecap="round" stroke-dasharray="${dash}" transform="rotate(-90 96 70)" filter="url(#frGlow)"></circle></g>
<circle cx="96" cy="70" r="45" fill="url(#frBody)"></circle>
<circle cx="96" cy="70" r="44" fill="none" stroke="#7FE3FF" stroke-opacity=".22" stroke-width="1.5"></circle>
<path d="M66 44 C 74 34, 88 29, 100 29" fill="none" stroke="#BFF3FF" stroke-opacity=".18" stroke-width="3" stroke-linecap="round"></path>
<g class="fr-face fr-face-happy" filter="url(#frSoft)">${freshyEyePair(x => `<path class="fr-eye" d="M${x - 6} 69 C ${x - 6} 60.5, ${x + 6} 60.5, ${x + 6} 69" fill="none" stroke="#D6FAFF" stroke-width="3.4" stroke-linecap="round"></path>`)}${smile}</g>
<g class="fr-face fr-face-awake" filter="url(#frSoft)">${freshyEyePair(x => awakeEye(x))}${smile}</g>
<g class="fr-face fr-face-morning" filter="url(#frSoft)">${freshyEyePair(x => awakeEye(x, pupil(x, 1.4, -2.8, 1.5) + `<circle cx="${x - 1.8}" cy="62.4" r="1.1" fill="#FFFFFF"></circle>`))}<path d="M92 80 C 95 89, 105 89, 108 80 Z" fill="#9FEFFF" fill-opacity=".85" stroke="#9FEFFF" stroke-width="1.6" stroke-linejoin="round"></path></g>
<g class="fr-face fr-face-sleep" filter="url(#frSoft)">${freshyEyePair(x => `<path d="M${x - 6} 66 C ${x - 3} 71, ${x + 3} 71, ${x + 6} 66" fill="none" stroke="#9FEFFF" stroke-width="2.6" stroke-linecap="round"></path>`)}<circle cx="100" cy="83" r="2.4" fill="none" stroke="#9FEFFF" stroke-width="2"></circle></g>
<g class="fr-face fr-face-sleepy" filter="url(#frSoft)">${freshyEyePair(x => `<g class="fr-sleepy-lid"><path d="M${x - 5.8} 65.2 a5.8 5.2 0 0 0 11.6 0 Z" fill="#CFF8FF"></path></g><path d="M${x - 6.6} 64.4 Q ${x} 67.4, ${x + 6.6} 64.4" fill="none" stroke="#9FEFFF" stroke-width="2.4" stroke-linecap="round"></path>`)}<ellipse class="fr-yawn" cx="100" cy="84" rx="3.2" ry="2.6" fill="#0A2230" stroke="#9FEFFF" stroke-width="2"></ellipse></g>
<g class="fr-face fr-face-worry" filter="url(#frSoft)"><path d="M82 57 L 95 54" stroke="#9FEFFF" stroke-width="2.2" stroke-linecap="round"></path><path d="M105 54 L 118 57" stroke="#9FEFFF" stroke-width="2.2" stroke-linecap="round"></path>${freshyEyePair(x => `<g class="fr-eye"><ellipse cx="${x}" cy="67" rx="4.5" ry="5.5" fill="#CFF8FF"></ellipse></g>`)}<path d="M92 85 C 95 82, 98 82, 100 85 C 102 88, 105 88, 108 85" fill="none" stroke="#9FEFFF" stroke-width="2.2" stroke-linecap="round"></path></g>
<g class="fr-face fr-face-squint" filter="url(#frSoft)"><path d="M83 61 L 94 66 L 83 71" fill="none" stroke="#9FEFFF" stroke-width="2.6" stroke-linecap="round" stroke-linejoin="round"></path><path d="M117 61 L 106 66 L 117 71" fill="none" stroke="#9FEFFF" stroke-width="2.6" stroke-linecap="round" stroke-linejoin="round"></path><ellipse cx="100" cy="84" rx="4" ry="3.4" fill="#9FEFFF"></ellipse></g>
<g class="fr-face fr-face-lookup" filter="url(#frSoft)">${freshyEyePair(x => awakeEye(x, `<g class="fr-pupils">${pupil(x, 1.2, -3.6, 2)}</g>`))}<path d="M96 83 C 98 85, 102 85, 104 83" fill="none" stroke="#9FEFFF" stroke-width="2.3" stroke-linecap="round"></path></g>
<g class="fr-face fr-face-side" filter="url(#frSoft)">${freshyEyePair(x => awakeEye(x, pupil(x, 2.4, -1.4, 1.9)))}<path d="M94 83 L 106 83" stroke="#9FEFFF" stroke-width="2.4" stroke-linecap="round"></path></g>
<g class="fr-face fr-face-shades" filter="url(#frSoft)">${freshyEyePair(x => `<rect x="${x - 8}" y="59.5" width="16" height="11" rx="4.5" fill="#0B1820" stroke="#9FEFFF" stroke-width="1.6"></rect><path d="M${x - 5} 62.5 L ${x - 1} 62.5" stroke="#9FEFFF" stroke-opacity=".7" stroke-width="1.3" stroke-linecap="round"></path>`)}<path d="M97 63 L 103 63" stroke="#9FEFFF" stroke-width="1.6"></path><path d="M92 81 C 96 87.5, 104 87.5, 108 81" fill="none" stroke="#9FEFFF" stroke-width="2.5" stroke-linecap="round"></path></g>
<g class="fr-face fr-face-cold" filter="url(#frSoft)">${freshyEyePair(x => `<g class="fr-eye"><ellipse cx="${x}" cy="66" rx="4.6" ry="5.4" fill="#CFF8FF"></ellipse></g>`)}<path d="M91 84 L 94 82 L 97 84 L 100 82 L 103 84 L 106 82 L 109 84" fill="none" stroke="#9FEFFF" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"></path></g>
<g class="frx frx-mask"><path d="M79 78 L 58 72" stroke="#DDF6FA" stroke-width="1.6" stroke-linecap="round"></path><path d="M121 78 L 140 72" stroke="#DDF6FA" stroke-width="1.6" stroke-linecap="round"></path><path d="M80 76 C 87 72, 113 72, 120 76 L 118 89 C 110 95, 90 95, 82 89 Z" fill="#DDF6FA"></path><path d="M84 81 H 116 M85 86 H 115" stroke="#AFCBD3" stroke-width="1.2" stroke-linecap="round"></path></g>
</g>
<g class="frx frx-scarf"><path d="M60 98 C 78 112, 114 112, 132 98 L 135 106 C 116 121, 76 121, 57 106 Z" fill="#FF7A7A"></path><path d="M70 106 L 74 114 M84 110 L 86 118 M100 111 L 100 119 M114 110 L 112 118" stroke="#FFD0D0" stroke-width="2" stroke-linecap="round"></path><g class="frx-scarf-end"><path d="M114 108 L 124 108 L 128 132 L 114 132 Z" fill="#FF6464"></path><path d="M116 132 V 136 M120 132 V 136 M124 132 V 136" stroke="#FF7A7A" stroke-width="1.6" stroke-linecap="round"></path></g></g>
<g class="frx frx-cap"><g class="frx-cap-tip"><path d="M70 38 C 74 16, 96 4, 116 6 C 134 8, 148 24, 152 46 C 153 52, 152 58, 150 62 C 146 50, 138 40, 128 35 C 110 33, 90 35, 70 38 Z" fill="#6F63FF"></path><path d="M84 30 C 94 16, 112 11, 128 16 M100 33 C 112 24, 128 24, 140 34" fill="none" stroke="#9D95FF" stroke-width="2" stroke-linecap="round"></path><circle cx="150" cy="64" r="6.2" fill="#F4F6FF"></circle></g><path d="M64 44 C 74 30, 118 26, 132 38 L 130 45 C 116 35, 80 36, 66 50 Z" fill="#EEF2FF"></path></g>
<g class="frx frx-umbrella"><path d="M96 10 C 76 12, 60 30, 54 64" fill="none" stroke="#6EE7B7" stroke-width="2.6" stroke-linecap="round"></path><path d="M56 24 C 68 2, 124 2, 136 24 C 120 17, 72 17, 56 24 Z" fill="#6EE7B7"></path><path d="M60 22 C 78 11, 114 11, 132 22" fill="none" stroke="#A8F5D6" stroke-width="1.4" stroke-linecap="round"></path></g>
</g>
<g class="frx frx-wind" fill="none" stroke="#B9EEFA" stroke-width="2.2" stroke-linecap="round"><path d="M158 40 C 150 36, 144 44, 136 40"></path><path d="M160 70 C 152 66, 146 74, 140 70"></path><path d="M156 100 C 148 96, 142 104, 134 100"></path></g>
<g class="frx frx-out" fill="#7DD3E8"><path d="M128 46 C 128 46, 123 52, 123 55 a5 5 0 0 0 10 0 C 133 52, 128 46, 128 46 Z"></path><path d="M134 64 C 134 64, 130 69, 130 71 a4 4 0 0 0 8 0 C 138 69, 134 64, 134 64 Z"></path><path d="M124 30 C 124 30, 120 35, 120 37 a4 4 0 0 0 8 0 C 128 35, 124 30, 124 30 Z"></path></g>
<g class="frx frx-check"><circle cx="140" cy="28" r="13" fill="#173A2A" stroke="#8FD8A6" stroke-width="2"></circle><path d="M134 28 L 139 33 L 147 23" fill="none" stroke="#8FD8A6" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"></path></g>
<g class="frx frx-clock"><circle cx="140" cy="27" r="13" fill="#2A2112" stroke="#F0B357" stroke-width="2"></circle><path d="M140 16.5 V 18.5 M140 35.5 V 37.5 M129.5 27 H 131.5 M148.5 27 H 150.5" stroke="#F0B357" stroke-width="1.6" stroke-linecap="round"></path><path class="frx-clock-hand-slow" d="M140 27 L 145 27" stroke="#F7D69A" stroke-width="2" stroke-linecap="round"></path><path class="frx-clock-hand" d="M140 27 L 140 19" stroke="#F7D69A" stroke-width="2" stroke-linecap="round"></path><circle cx="140" cy="27" r="1.6" fill="#F7D69A"></circle></g>
<g class="frx frx-z" fill="#9FC3E6" font-weight="800"><text x="132" y="34" font-size="15">z</text><text x="142" y="22" font-size="11">z</text></g>
<g class="frx frx-sweat"><path d="M140 46 C 140 46, 136 51, 136 54 a4 4 0 0 0 8 0 C 144 51, 140 46, 140 46 Z" fill="#7DD3E8"></path></g>
<g class="frx frx-breath" fill="#E6F4FF"><circle cx="114" cy="86" r="3.2"></circle><circle cx="117" cy="84" r="2.6"></circle></g>
<g class="frx frx-q" fill="#C9D6DE" font-weight="800"><text x="134" y="34" font-size="24">?</text></g>
<g class="frx frx-pollen" fill="#F0D36B"><circle cx="146" cy="78" r="3"></circle><circle cx="138" cy="94" r="2.4"></circle><circle cx="150" cy="56" r="2.2"></circle></g>
<g class="frx frx-dust" fill="#9AA7B0"><circle cx="144" cy="40" r="2.6"></circle><circle cx="152" cy="62" r="2"></circle><circle cx="140" cy="84" r="2.8"></circle><circle cx="150" cy="104" r="2.2"></circle><circle cx="146" cy="22" r="1.8"></circle></g>
<g class="frx frx-think" fill="#BFF3FF"><circle cx="132" cy="36" r="3"></circle><circle cx="141" cy="25" r="4"></circle><circle cx="152" cy="12" r="5"></circle></g>
</svg>`;
}
