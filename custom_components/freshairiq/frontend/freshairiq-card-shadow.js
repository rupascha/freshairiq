// The section "Experimentell" at the end of "Wie gut FreshAirIQ aktuell vorhersagt" (0.26.5.5, status since
// 0.26.7.1): the new base formula and its forecasts were evaluated on 23,000 real airings and adopted; no
// experimental formula runs at the moment. One renderer for the house map, Classic and Freshy. Older
// st.forecast_shadow_comparison data is no longer shown. Loaded by freshairiq-card-data.js.

export const SHADOW_HEAD = ["Experimentell", "Experimental"];
export const SHADOW_NOTE = [
  "Die neue Grundformel inklusive der Prognosen wurde anhand von 23.000 realen Lüftungen ausgewertet und übernommen. Aktuell gibt es keine neue experimentelle Formel.",
  "The new base formula and its forecasts were evaluated using 23,000 real ventilation sessions and have been adopted. There is currently no new experimental formula.",
];

// ``cmp`` (the old comparison payload) is accepted and ignored: no comparison numbers, no running test
export function shadowSection(cmp, en) {
  const pick = pair => pair[en ? 1 : 0];
  return `<div class="learning-overview-note faiq-shadow-test" style="overflow-wrap:anywhere"><ha-icon icon="mdi:flask-outline"></ha-icon><span><b>${pick(SHADOW_HEAD)}</b><br>${pick(SHADOW_NOTE)}</span></div>`;
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
