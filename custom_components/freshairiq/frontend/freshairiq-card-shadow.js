// Passive test of a new moisture formula (0.26.5.5).
//
// A compact section at the end of "Wie gut FreshAirIQ aktuell vorhersagt". Every number comes from
// st.forecast_shadow_comparison – sessions where the active forecast and the candidate formula were
// computed from the same frozen start and scored against the same measurement. The candidate never
// changes a recommendation, learns nothing and switches nothing. Loaded by freshairiq-card-data.js.

const STATUS = {
  collecting: ["Sammelt Vergleichsdaten – vorläufig", "Collecting comparison data – preliminary"],
  inconclusive: ["Noch kein eindeutiger Unterschied", "No clear difference yet"],
  candidate_better: ["Testformel im Vergleich besser – keine automatische Übernahme", "Test formula better in the comparison – no automatic switch"],
  candidate_worse: ["Testformel schlechter als die bestehende Formel", "Test formula worse than the current formula"],
};
const NOTE = [
  "Die neue Formel wird nur parallel berechnet und mit gemessenen Ergebnissen verglichen. Sie ändert keine Lüftungs- oder Schließempfehlung, lernt nichts und steuert keine Geräte. Die Werte sind vorläufig.",
  "The new formula is only calculated in parallel and compared with measured results. It changes no ventilation or close recommendation, learns nothing and controls no devices. The values are preliminary.",
];

const finite = value => value !== null && value !== undefined && value !== "" && Number.isFinite(Number(value));
const number = (value, digits, en) => {
  const text = Math.abs(Number(value)).toFixed(digits);
  return en ? text : text.replace(".", ",");
};

// Formula study 2026-10-31: "always 0 ml" was almost as good as the candidate; say when a formula does not beat it.
const nullNote = (cmp, en) => {
  if (cmp.candidate_beats_null !== false) return "";
  return cmp.production_beats_null === false
    ? (en ? " – neither formula is clearly better yet" : " – noch keine Formel klar besser")
    : (en ? " – the test formula is not clearly better yet" : " – Testformel noch nicht klar besser");
};

export function shadowSection(cmp, en) {
  const pick = pair => pair[en ? 1 : 0];
  const head = `<b>${en ? "Experiment: new moisture formula (passive test)" : "Experiment: Neue Feuchteformel (passiver Test)"}</b>`;
  const samples = Number((cmp && cmp.samples) || 0);
  let body;
  if (!cmp || !samples || !finite(cmp.production_mae_ml) || !finite(cmp.candidate_mae_ml)) {
    body = en ? "No comparison yet – no airing with a complete pair so far." : "Noch kein Vergleich – bisher keine Lüftung mit vollständigem Paar.";
  } else {
    const diff = Number(cmp.mae_difference_ml);
    const pct = finite(cmp.improvement_percent) ? Number(cmp.improvement_percent) : null;
    const sign = diff > 0 ? "+" : diff < 0 ? "–" : "±";
    const rel = pct === null || pct === 0 ? "" : ` (${number(pct, 1, en)} % ${pct > 0 ? (en ? "lower error" : "geringerer Fehler") : (en ? "higher error" : "höherer Fehler")})`;
    body = `${en ? "Current formula" : "Bestehende Formel"}: <b>${number(cmp.production_mae_ml, 0, en)} ml MAE</b> · ${en ? "test formula" : "Testformel"}: <b>${number(cmp.candidate_mae_ml, 0, en)} ml MAE</b><br>`
      + `${en ? "Difference" : "Unterschied"}: <b>${sign}${number(diff, 0, en)} ml${rel}</b> · <b>${samples}</b> ${en ? "comparable airings" : "vergleichbare Lüftungen"}`
      + (finite(cmp.null_mae_ml) ? `<br>${en ? "Without a forecast (always 0 ml)" : "Ohne Vorhersage (immer 0 ml)"}: <b>${number(cmp.null_mae_ml, 0, en)} ml MAE</b>${nullNote(cmp, en)}` : "")
      + (STATUS[cmp.status] ? `<br>${pick(STATUS[cmp.status])}` : "");
  }
  // audit N04: other formula revisions are never mixed into the numbers above
  const others = Number((cmp && cmp.other_formula_samples) || 0);
  if (others > 0) body += `<br>${others} ${en ? "airings with another formula version not included" : "Lüftungen mit anderer Formelversion nicht eingerechnet"}`;
  return `<div class="learning-overview-note faiq-shadow-test" style="overflow-wrap:anywhere"><ha-icon icon="mdi:flask-outline"></ha-icon><span>${head}<br>${body}<br><small>${pick(NOTE)}</small></span></div>`;
}

function patchCard(cls) {
  const proto = cls.prototype;
  if (proto.__faiqShadow || typeof proto._learningPanel !== "function") return;
  proto.__faiqShadow = true;
  const learningPanel = proto._learningPanel;
  proto._learningPanel = function (st) {
    const html = learningPanel.call(this, st);
    // only the quality view ("Wie gut FreshAirIQ aktuell vorhersagt"), not the other learning views
    if (this._info !== "learning:quality" || typeof html !== "string" || !html.includes("learning-detail-panel")) return html;
    const end = html.lastIndexOf("</section>");
    if (end < 0) return html;
    const en = typeof this._uiLanguage === "function" && this._uiLanguage() === "en";
    return html.slice(0, end) + shadowSection((st || {}).forecast_shadow_comparison, en) + html.slice(end);
  };
}

customElements.whenDefined("freshairiq-card").then(() => patchCard(customElements.get("freshairiq-card")));
