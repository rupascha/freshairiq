const FAIQ_VERSION = "0.25.0.72";
const FAIQ_CARD = "freshairiq-card";
const FAIQ_STRATEGY = "freshairiq";
const esc = v => String(v !== null && v !== void 0 ? v : "").split("&").join("&amp;").split("<").join("&lt;").split(">").join("&gt;").split('"').join("&quot;").split("'").join("&#039;");
const lastItem = arr => (arr && arr.length ? arr[arr.length - 1] : undefined);
const fmt = (v, d = 1) => { const n = Number(v); return Number.isFinite(n) ? n.toFixed(d).replace(".", ",") : "–"; };
const whenDE = v => { if (!v)
    return "noch keine Messung"; const d = new Date(v); return Number.isNaN(d.getTime()) ? "–" : d.toLocaleString("de-DE", { day: "2-digit", month: "2-digit", hour: "2-digit", minute: "2-digit" }); };
const signed = (v, unit = "") => { const n = Number(v || 0); if (Math.abs(n) < .05)
    return `±0,0${unit ? " " + unit : ""}`; return `${n > 0 ? "+" : "−"}${fmt(Math.abs(n), 1)}${unit ? " " + unit : ""}`; };
const moisture = (physicalRemovedMl, zero = "0 ml") => {
    const n = Number(physicalRemovedMl || 0);
    if (Math.abs(n) < .5)
        return { text: zero, color: "#9aa7b3", kind: "neutral" };
    return n > 0
        ? { text: `−${Math.abs(Math.round(n))} ml`, color: "#67df92", kind: "removed" }
        : { text: `+${Math.abs(Math.round(n))} ml`, color: "#ff7770", kind: "added" };
};
const actionDE = v => ({ "Ventilate": "Lüften", "Continue ventilating": "Weiterlüften", "Close": "Schließen", "Do not ventilate": "Nicht lüften", "Wait": "Warten", "Okay": "Alles okay", "Check sensor": "Sensor prüfen", "Ventilate for cooling": "Zum Kühlen lüften", "Monitor only": "Nur anzeigen" }[v] || v || "–");
const mouldDE = v => ({ "Very high": "Sehr hoch", "High": "Hoch", "Elevated": "Erhöht", "Slightly elevated": "Leicht erhöht", "Low": "Niedrig", "Unknown": "Unbekannt" }[v] || v || "Unbekannt");
const learnDE = v => ({ "Very stable": "Sehr stabil", "Stable": "Stabil", "Usable": "Brauchbar", "Learning": "Lernt", "Base estimate": "Grundschätzung" }[v] || v || "–");
const profileDE = v => ({ dehumidify: "Entfeuchten", comfort: "Komfort", summer_cooling: "Sommer kühlen" }[v] || v || "Komfort");
const floorDE = v => ({ basement: "Kellergeschoss", base_floor: "Kellergeschoss", "base floor": "Kellergeschoss", Basement: "Kellergeschoss", ground_floor: "Erdgeschoss", "ground floor": "Erdgeschoss", "Ground Floor": "Erdgeschoss", upper_floor: "Obergeschoss", "upper floor": "Obergeschoss", "Upper Floor": "Obergeschoss", attic: "Dachgeschoss", Attic: "Dachgeschoss", other: "Sonstige", Other: "Sonstige" }[String(v || "")] || v || "Unzugeordnet");
const propertyDE = v => ({ house: "Haus", detached: "Freistehendes Haus", semi_detached: "Doppelhaushälfte", row_mid: "Reihenmittelhaus", row_end: "Reihenendhaus", apartment: "Wohnung", maisonette: "Maisonette", multi_family: "Mehrfamilienhaus", other: "Sonstiges" }[v] || v || "–");
const heatingDE = v => ({ heat_pump: "Wärmepumpe", gas: "Gas", district_heating: "Fernwärme", electric: "Elektro", oil: "Öl" }[v] || v || "–");
const orientationDE = v => ({ unknown: "–", n: "Nord", ne: "Nordost", e: "Ost", se: "Südost", s: "Süd", sw: "Südwest", w: "West", nw: "Nordwest" }[String(v || "unknown").toLowerCase()] || "–");
const roomVisual = r => {
    const name = String((r === null || r === void 0 ? void 0 : r.name) || (r === null || r === void 0 ? void 0 : r.key) || "").toLowerCase();
    if (name.includes("wohn") || name.includes("küche") || name.includes("kueche"))
        return ["mdi:pot-steam-outline", "#f2c45d", "rgba(242,196,93,.13)"];
    if (name.includes("gäste wc") || name.includes("gaeste wc") || name.includes("gästewc") || name.includes("gaestewc") || name.includes("toilet"))
        return ["mdi:toilet", "#42a5ff", "rgba(66,165,255,.13)"];
    if (name.includes("flur") || name.includes("diele") || name.includes("treppe"))
        return ["mdi:stairs", "#b47cff", "rgba(180,124,255,.13)"];
    if (name.includes("schlaf"))
        return ["mdi:bed-king-outline", "#39d6d0", "rgba(57,214,208,.13)"];
    if (name.includes("kinder"))
        return ["mdi:teddy-bear", "#ff8eb4", "rgba(255,142,180,.13)"];
    if (name.includes("bad") || name.includes("bade"))
        return ["mdi:bathtub-outline", "#61b6ff", "rgba(97,182,255,.13)"];
    if (name.includes("arbeits") || name.includes("büro") || name.includes("buero"))
        return ["mdi:desk", "#69d19b", "rgba(105,209,155,.13)"];
    if (name.includes("fitness"))
        return ["mdi:dumbbell", "#f28d64", "rgba(242,141,100,.13)"];
    if (name.includes("wellness") || name.includes("sauna"))
        return ["mdi:spa-outline", "#c98cff", "rgba(201,140,255,.13)"];
    if (name.includes("lager") || name.includes("abstell"))
        return ["mdi:archive-outline", "#a6b4bf", "rgba(166,180,191,.11)"];
    if (name.includes("gast") || name.includes("gäste") || name.includes("gaeste"))
        return ["mdi:bed-outline", "#61b6ff", "rgba(97,182,255,.13)"];
    return ["mdi:home-outline", "#5bd4ff", "rgba(91,212,255,.11)"];
};
const reasonDE = value => {
    var _a, _b;
    const s = String(value || "");
    if (s.startsWith("Short-term 5-minute close check expects")) {
        const n = ((_a = s.match(/(\d+)\s*ml/)) === null || _a === void 0 ? void 0 : _a[1]) || "–";
        return `Kurzfristiger Schließcheck (5 min): voraussichtlich ${n} ml Feuchteabbau`;
    }
    if (s.startsWith("About") && s.includes("moisture can be removed")) {
        const n = ((_b = s.match(/About\s+(\d+)\s+ml/)) === null || _b === void 0 ? void 0 : _b[1]) || "–";
        return `Etwa ${n} ml Feuchtigkeit können entfernt werden`;
    }
    if (s.startsWith("Pollen load")) {
        return "Pollenbelastung liegt über dem eingestellten Grenzwert";
    }
    return ({ "Target reached or additional ventilation benefit is too low": "Ziel erreicht oder zusätzlicher Lüftungsnutzen zu gering", "Reference air would add moisture": "Referenzluft würde zusätzliche Feuchtigkeit eintragen", "Potential exists, but ventilation threshold is not reached": "Potenzial vorhanden, Lüftungsschwelle noch nicht erreicht", "No meaningful ventilation demand": "Kein sinnvoller Lüftungsbedarf", "Missing or implausible measurements": "Messwerte fehlen oder sind unplausibel", "Room is visible but excluded from FreshAirIQ calculations": "Raum wird angezeigt, beeinflusst die Berechnungen aber nicht" }[s] || s);
};
const statusTextDE = value => {
    var _a, _b;
    const s = String(value || "");
    if (s === "Keep windows closed")
        return "Fenster geschlossen lassen";
    if (s.startsWith("Ventilate now")) {
        const n = ((_a = s.match(/(\d+)\s*ml/)) === null || _a === void 0 ? void 0 : _a[1]) || "–";
        return `Jetzt lüften · etwa ${n} ml entfernbar`;
    }
    if (s.startsWith("Ventilation running")) {
        const n = ((_b = s.match(/(\d+)\s*ml/)) === null || _b === void 0 ? void 0 : _b[1]) || "–";
        return s.includes("added") ? `Lüftung läuft · ${n} ml Feuchtigkeit eingetragen` : `Lüftung läuft · ${n} ml Feuchtigkeit entfernt`;
    }
    if (s.startsWith("Close "))
        return "Fenster jetzt schließen";
    if (s.startsWith("Check "))
        return "Raumsensoren prüfen";
    if (s.startsWith("Pollen load"))
        return "Pollenbelastung zu hoch · Lüften verschoben";
    if (s.startsWith("Summer cooling"))
        return "Sommerkühlung sinnvoll";
    return s;
};
const mouldStyle = v => ({ "Very high": ["#ff6868", "rgba(255,80,80,.12)"], "High": ["#ffb45f", "rgba(255,180,95,.10)"], "Elevated": ["#e2bd69", "rgba(226,189,105,.08)"], "Slightly elevated": ["#d7c982", "rgba(215,201,130,.06)"], "Low": ["#67df92", "rgba(103,223,146,.05)"], "Unknown": ["#9aa7b3", "rgba(255,255,255,.025)"] }[v] || ["#9aa7b3", "rgba(255,255,255,.025)"]);
const diagnosisDE = value => String(value || "Noch keine Lernmessung").replace(/^Learned:/, "Gelernt:").replace(/^Rejected:/, "Verworfen:").replace(/^Paused:/, "Pausiert:").replace("No learning session evaluated yet", "Noch keine Lernsession ausgewertet").replace("learning disabled", "Lernmodus deaktiviert").replace("duration", "Dauer").replace("start delta", "Startdifferenz").replace("humidity reduction", "Feuchteabbau").replace("learning rate", "Lernrate").replace("sample", "Probe").replace("reduction", "Abbau").replace("rate", "Rate");
const styleFor = a => ({
    "Close": ["#ffb45f", "rgba(255,180,95,.08)", "mdi:window-closed-variant"],
    "Continue ventilating": ["#5bcaff", "rgba(70,190,235,.07)", "mdi:weather-windy"],
    "Ventilate": ["#62e889", "rgba(80,210,125,.07)", "mdi:weather-windy"],
    "Ventilate for cooling": ["#63d2f7", "rgba(70,190,235,.07)", "mdi:snowflake"],
    "Do not ventilate": ["#ff7770", "rgba(220,90,80,.07)", "mdi:water-plus"],
    "Wait": ["#e2bd69", "rgba(210,175,95,.06)", "mdi:progress-clock"],
    "Check sensor": ["#ff7770", "rgba(220,90,80,.07)", "mdi:alert-circle-outline"],
    "Monitor only": ["#9aa7b3", "rgba(255,255,255,.025)", "mdi:eye-outline"]
}[a] || ["#9aa7b3", "rgba(255,255,255,.025)", "mdi:check-circle-outline"]);
const normalizeDashboardConfig = input => {
    const raw = input || {};
    const inherited = (key, legacyKey, fallback = true) => raw[key] !== undefined ? raw[key] : (legacyKey && raw[legacyKey] !== undefined ? raw[legacyKey] : fallback);
    const out = Object.assign({}, raw, {
        info_moisture: inherited("info_moisture", "show_moisture", true),
        info_temperature: inherited("info_temperature", "show_temperature", true),
        info_time: inherited("info_time", "show_time", true),
        info_forecast: inherited("info_forecast", "show_next5", true),
        info_night: inherited("info_night", "show_night", true),
        info_mould: inherited("info_mould", "show_mould", true),
        info_energy: inherited("info_energy", "show_energy", true),
        info_pollen: inherited("info_pollen", "show_pollen", true),
        info_voc: inherited("info_voc", null, true),
        info_pm25: inherited("info_pm25", null, true),
        info_illuminance: inherited("info_illuminance", null, true),
        info_cross_ventilation: inherited("info_cross_ventilation", "show_cross_ventilation", true),
        show_branding: inherited("show_branding", null, true),
        show_profile_badge: inherited("show_profile_badge", null, true),
        show_iq_process: inherited("show_iq_process", null, true),
        show_details_button: inherited("show_details_button", null, true),
        show_guests_button: inherited("show_guests_button", null, true),
        show_rooms_button: inherited("show_rooms_button", null, true),
    });
    ["show_moisture", "show_temperature", "show_time", "show_next5", "show_night", "show_mould", "show_energy", "show_pollen", "show_cross_ventilation"].forEach(key => delete out[key]);
    return out;
};
const FAIQ_CARD_CSS = `
      :host{display:block}*{box-sizing:border-box}ha-card{overflow:visible;border-radius:22px;border:1px solid rgba(80,205,245,.13);background:radial-gradient(circle at 92% 0%,rgba(60,205,255,.10),transparent 34%),linear-gradient(135deg,rgba(22,29,38,.99),rgba(17,23,30,.99));color:var(--primary-text-color,#f3f7fa);box-shadow:0 10px 30px rgba(0,0,0,.20)}.card{padding:13px;font-family:inherit}.top{display:grid;grid-template-columns:48px minmax(0,1fr) auto;gap:11px;align-items:center}.logo{width:48px;height:48px;border-radius:14px;object-fit:cover}.brand{font-size:20px;font-weight:950}.iq{color:#56d5ff}.hero{font-size:10px;font-weight:800;color:var(--faiq-hero-color);margin-top:3px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.pill{padding:6px 9px;border-radius:999px;font-size:9px;font-weight:850;color:var(--faiq-hero-color);background:var(--faiq-hero-bg);border:1px solid var(--faiq-hero-border)}.recommendations{margin-top:11px;padding:10px;border-radius:14px;background:rgba(255,255,255,.022);border:1px solid rgba(255,255,255,.065)}.recommendations-title{display:flex;align-items:end;justify-content:space-between;gap:10px;margin-bottom:7px}.recommendations-title b{font-size:12px}.recommendations-title span{font-size:8px;color:#82929e;text-align:right}.recommendation-row{display:grid;grid-template-columns:34px minmax(0,1fr);gap:9px;padding:9px 8px;border-radius:11px;border:1px solid rgba(255,255,255,.10);border:1px solid color-mix(in srgb,var(--rec) 25%,transparent);background:rgba(255,255,255,.025);background:color-mix(in srgb,var(--rec) 5%,transparent)}.recommendation-row+.recommendation-row{margin-top:6px}.rec-icon{width:34px;height:34px;border-radius:10px;display:flex;align-items:center;justify-content:center;color:var(--rec);background:rgba(255,255,255,.045);background:color-mix(in srgb,var(--rec) 10%,transparent)}.rec-icon ha-icon{--mdc-icon-size:20px}.rec-head{display:flex;justify-content:space-between;gap:8px;align-items:baseline}.rec-head b{font-size:11px}.rec-head strong{font-size:9px;color:var(--rec);white-space:nowrap}.rec-reasons{display:grid;gap:2px;margin-top:4px}.rec-reasons span{font-size:9px;line-height:12px;color:#b4c0c8}.rec-reasons span:before{content:"• ";color:var(--rec)}.recommendation-empty{display:grid;grid-template-columns:28px minmax(0,1fr);gap:8px;align-items:center;color:#67df92}.recommendation-empty ha-icon{--mdc-icon-size:22px}.recommendation-empty b,.recommendation-empty span{display:block}.recommendation-empty b{font-size:10px}.recommendation-empty span{font-size:8px;line-height:11px;color:#84939e;margin-top:2px}.decision-card{margin-top:12px;padding:15px;border-radius:18px;background:rgba(255,255,255,.025);background:linear-gradient(145deg,color-mix(in srgb,var(--decision) 9%,transparent),rgba(255,255,255,.018));border:1px solid rgba(255,255,255,.10);border:1px solid color-mix(in srgb,var(--decision) 34%,transparent);box-shadow:inset 0 1px 0 rgba(255,255,255,.025)}.decision-kicker{display:flex;align-items:center;gap:7px;font-size:8px;font-weight:950;letter-spacing:.9px;color:var(--decision)}.decision-dot{width:7px;height:7px;border-radius:50%;background:var(--decision);box-shadow:0 0 12px rgba(91,212,255,.35);box-shadow:0 0 12px color-mix(in srgb,var(--decision) 75%,transparent)}.decision-main{display:grid;grid-template-columns:44px minmax(0,1fr);gap:11px;align-items:center;margin-top:10px}.decision-icon{width:44px;height:44px;border-radius:13px;display:flex;align-items:center;justify-content:center;color:var(--decision);background:rgba(255,255,255,.045);background:color-mix(in srgb,var(--decision) 12%,transparent);border:1px solid rgba(255,255,255,.10);border:1px solid color-mix(in srgb,var(--decision) 22%,transparent)}.decision-icon ha-icon{--mdc-icon-size:26px}.decision-main h2{font-size:18px;line-height:22px;margin:0;color:#f2f7fa}.decision-action{font-size:11px;line-height:15px;font-weight:900;color:var(--decision);margin-top:3px}.decision-rooms{display:flex;gap:5px;flex-wrap:wrap;margin-top:9px}.decision-rooms span{font-size:8.5px;font-weight:850;padding:4px 7px;border-radius:999px;background:rgba(255,255,255,.045);border:1px solid rgba(255,255,255,.075)}.decision-summary{font-size:10px;line-height:14px;color:#b7c3ca;margin:10px 0 0}.decision-impacts{display:grid;grid-template-columns:repeat(auto-fit,minmax(115px,1fr));gap:6px;margin-top:11px}.decision-impact{padding:8px;border-radius:11px;background:rgba(255,255,255,.028);border:1px solid rgba(255,255,255,.065);min-width:0}.decision-impact span{display:block;font-size:6.8px;font-weight:900;letter-spacing:.5px;color:#82929e}.decision-impact b{display:block;font-size:11px;line-height:14px;margin-top:3px;white-space:normal;overflow-wrap:anywhere;color:#e9f0f4}.night-context b{font-size:10.5px}.night-comparison{grid-column:1/-1}.night-comparison-grid{display:grid;grid-template-columns:minmax(0,1fr) auto minmax(0,1fr);gap:8px;align-items:center;margin-top:7px}.night-comparison-side{min-width:0;padding:7px;border-radius:9px;background:rgba(255,255,255,.025)}.night-comparison-side span{font-size:7px}.night-comparison-side b{font-size:12px;line-height:15px}.night-comparison-arrow{font-size:16px;color:var(--decision);font-weight:900}.night-comparison-benefit{margin-top:7px;font-size:9px;line-height:12px;font-weight:850;color:var(--decision)}.decision-compare{display:grid;grid-template-columns:1fr 24px 1fr;gap:6px;align-items:center;margin-top:10px;padding:9px;border-radius:12px;background:rgba(255,255,255,.025);border:1px solid rgba(255,255,255,.06);text-align:center}.decision-compare ha-icon{--mdc-icon-size:18px;color:#82929e}.decision-compare span,.decision-compare b{display:block}.decision-compare span{font-size:7px;color:#82929e;font-weight:900}.decision-compare b{font-size:11px;margin-top:2px}.decision-section-title{font-size:7px!important;font-weight:950!important;letter-spacing:.65px;color:#82929e!important;margin-bottom:4px}.decision-why{display:grid;gap:4px;margin-top:10px;padding-top:9px;border-top:1px solid rgba(255,255,255,.06)}.decision-why>div:not(.decision-section-title){display:grid;grid-template-columns:16px minmax(0,1fr);gap:5px;align-items:start}.decision-why ha-icon{--mdc-icon-size:14px;color:var(--decision);margin-top:1px}.decision-why span{font-size:9px;line-height:12px;color:#c2ccd2}.decision-alternative{font-size:8.5px;line-height:12px;color:#8797a2;margin-top:9px;padding:7px 8px;border-radius:9px;background:rgba(255,255,255,.022)}.decision-footer{display:flex;justify-content:space-between;gap:8px;margin-top:9px;font-size:7px;color:#647580}.decision-footer span:last-child{text-align:right}.metrics{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:7px;margin-top:11px}.active-metrics{grid-template-columns:repeat(6,minmax(0,1fr))}.metric,.mini,.summary,.history,.learn-panel{background:rgba(255,255,255,.026);border:1px solid rgba(255,255,255,.065)}.metric{padding:9px;border-radius:12px;min-width:0}.tiny{font-size:8px;line-height:10px;font-weight:900;letter-spacing:.7px;color:#82929e}.value{font-size:16px;font-weight:950;margin-top:3px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.muted{font-size:8.5px;line-height:11px;color:#84939e;font-weight:650;margin-top:2px}.actions{margin-top:9px;display:flex;gap:7px;flex-wrap:wrap}.details-btn,.close{appearance:none;border:1px solid rgba(255,255,255,.10);background:rgba(255,255,255,.04);color:inherit;border-radius:10px;padding:8px 11px;font:inherit;font-size:9px;font-weight:850;cursor:pointer}.modal{position:fixed;top:0;right:0;bottom:0;left:0;inset:0;z-index:9999;background:rgba(4,8,12,.72);-webkit-backdrop-filter:blur(8px);backdrop-filter:blur(8px);display:flex;align-items:flex-start;justify-content:center;padding:calc(env(safe-area-inset-top,0px) + 58px) 16px 16px;overflow:hidden}.dialog{width:calc(100vw - 28px);width:min(1240px,calc(100vw - 28px));margin:0 auto;height:calc(100vh - env(safe-area-inset-top,0px) - 74px);height:calc(100dvh - env(safe-area-inset-top,0px) - 74px);max-height:calc(100vh - env(safe-area-inset-top,0px) - 74px);max-height:calc(100dvh - env(safe-area-inset-top,0px) - 74px);display:flex;flex-direction:column;overflow:hidden;border-radius:22px;background:linear-gradient(145deg,#171f28,#10171e);border:1px solid rgba(91,212,255,.18);box-shadow:0 30px 80px rgba(0,0,0,.55)}.dialog-head{display:grid;grid-template-columns:42px minmax(0,1fr) 42px 42px;align-items:center;gap:8px;position:relative;flex:0 0 auto;padding:12px 16px;min-height:62px;background:#151d25;border-bottom:1px solid rgba(255,255,255,.07);border-radius:22px 22px 0 0;z-index:30}.dialog-scroll{min-height:0;flex:1 1 0;overflow-y:auto;overflow-x:hidden;touch-action:pan-y pinch-zoom;-webkit-overflow-scrolling:touch;overscroll-behavior:contain;overscroll-behavior-y:contain;overflow-anchor:none;scroll-behavior:auto;padding:10px 16px 16px;background:linear-gradient(145deg,#171f28,#10171e)}.dialog-scroll{touch-action:pan-y pinch-zoom}.dialog-head-copy{min-width:0}.dialog-title{font-size:20px;font-weight:950}.dialog-back{appearance:none;width:42px;height:42px;display:flex;align-items:center;justify-content:center;border:1px solid rgba(255,255,255,.08);border-radius:11px;background:rgba(10,18,24,.78);color:#d9e2e8;cursor:pointer;justify-self:start}.dialog-back ha-icon{--mdc-icon-size:20px}.settings-gear{appearance:none;width:42px;height:42px;display:flex;align-items:center;justify-content:center;border:1px solid rgba(91,212,255,.16);border-radius:11px;background:rgba(91,212,255,.055);color:#86defb;cursor:pointer}.settings-gear ha-icon{--mdc-icon-size:20px}.close{font-size:18px;width:42px;height:42px;padding:0;display:flex;align-items:center;justify-content:center}.overview{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:8px}.summary{padding:11px;border-radius:13px}.summary strong{display:block;font-size:19px;margin-top:3px}.summary span{font-size:8px;color:#84939e}.history-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:8px;margin-top:8px}.history{padding:11px;border-radius:14px}.history-head{display:flex;justify-content:space-between;gap:10px}.history-head strong{color:#67df92}.chart{height:110px;margin:8px 0}.chart svg{width:100%;height:100%}.last-vent{display:grid;grid-template-columns:minmax(0,1fr) auto auto;gap:12px;align-items:center;margin-top:8px;padding:11px;border-radius:14px;background:rgba(255,255,255,.026);border:1px solid rgba(255,255,255,.065)}.last-vent b,.last-vent span{display:block}.last-vent span{font-size:8.5px;color:#84939e}.learn-panel{display:grid;grid-template-columns:1fr 2fr;gap:12px;padding:11px;border-radius:14px;margin-top:8px}.learn-status{display:grid;grid-template-columns:52px 1fr;gap:12px;align-items:center;text-align:center;padding:14px;border-radius:14px;margin-top:8px;background:rgba(255,255,255,.026);border:1px solid rgba(255,255,255,.065)}.learn-status ha-icon{--mdc-icon-size:34px;color:#67df92;justify-self:center}.learn-status strong{display:block;font-size:20px;color:#67df92;margin:2px 0}.learn-status span{display:block;font-size:10px;color:#a7b1b8;font-weight:700}.last-learning{display:grid;grid-template-columns:24px 1fr;gap:7px;align-items:center;margin-top:7px;padding:7px;border-radius:9px;border:1px solid rgba(255,255,255,.10);border:1px solid color-mix(in srgb,var(--learn) 35%,transparent);background:rgba(255,255,255,.025);background:color-mix(in srgb,var(--learn) 7%,transparent);color:var(--learn)}.last-learning ha-icon{--mdc-icon-size:17px}.last-learning b{font-size:8.5px;line-height:11px;display:block;margin-top:2px}.floor-title{display:none}.rooms-overview{padding:15px}.rooms-overview h3{font-size:18px;margin:4px 34px 2px 0}.rooms-subtitle{margin:0 0 12px!important;font-size:11px!important;color:#9aabb8!important}.rooms{display:grid;grid-template-columns:1fr;gap:10px}.room{padding:11px 12px;border-radius:15px;background:rgba(255,255,255,.018);border:1px solid rgba(255,255,255,.085)}.room-head{display:grid;grid-template-columns:44px minmax(0,1fr) auto 18px;gap:9px;align-items:center}.room-ident{min-width:0}.room-icon{width:44px;height:44px;border-radius:12px;display:flex;align-items:center;justify-content:center;color:var(--accent);background:var(--icon-bg)}.room-icon ha-icon{--mdc-icon-size:26px}.room-title{font-size:15px;font-weight:950;line-height:19px}.room-head .muted{font-size:9.5px;line-height:12px;margin-top:2px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.room-water{display:flex;align-items:center;justify-content:flex-end;gap:6px;white-space:nowrap}.room-water ha-icon{--mdc-icon-size:23px;color:#379dff}.room-water strong{font-size:14px;font-weight:950}.room-chevron{--mdc-icon-size:20px;color:#8da2b2}.room-summary-grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:7px;margin-top:9px}.room-stat{display:grid;grid-template-columns:28px minmax(0,1fr);gap:7px;align-items:center;padding:8px 8px;border-radius:11px;min-width:0;background:rgba(255,255,255,.025);border:1px solid rgba(255,255,255,.07)}.room-stat .stat-icon{--mdc-icon-size:21px;color:#e9eff3}.room-stat .tiny{font-size:7.2px;line-height:9px;white-space:nowrap;letter-spacing:.45px}.room-stat .room-value{font-size:11.5px;font-weight:900;margin-top:2px;white-space:nowrap}.room-stat .muted{font-size:8px;line-height:10px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.learning-bars{color:#f0f3f5!important}.room-action{font-size:9px;font-weight:850;color:var(--accent)}.room-climate{margin-top:9px;padding:8px;border-radius:10px;background:rgba(255,255,255,.022);border:1px solid rgba(255,255,255,.055)}.room-main{display:grid;grid-template-columns:1fr auto;gap:8px;margin-top:8px}.right{text-align:right}.room-value{font-size:12px;font-weight:850;margin-top:2px}.room-big{font-size:17px;font-weight:950}.mini-grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:5px;margin-top:7px}.mini{padding:6px;border-radius:9px;min-width:0}.mini-value{font-size:11px;font-weight:900;margin-top:2px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.reason{display:grid;gap:2px;font-size:8.5px;line-height:11px;color:#95a2ab;margin-top:7px;min-height:22px}.reason span:before{content:"• ";color:var(--accent)}.clickable,.metric{cursor:pointer}.clickable:hover,.metric:hover{border-color:rgba(91,212,255,.25)}.info-panel{position:relative;margin:0 0 10px;padding:13px;border-radius:14px;background:rgba(72,188,230,.07);border:1px solid rgba(91,212,255,.18)}.info-panel h3{margin:4px 0 7px;font-size:16px}.info-panel p{margin:6px 0;font-size:10px;line-height:14px;color:#b4c0c8}.info-nav{position:sticky;top:0;z-index:30;display:grid;grid-template-columns:42px minmax(0,1fr) 42px;align-items:center;gap:10px;min-height:62px;padding:10px 12px;background:rgba(16,24,30,.96);-webkit-backdrop-filter:blur(12px);backdrop-filter:blur(12px);border-bottom:1px solid rgba(255,255,255,.07);border-radius:20px 20px 0 0}.info-nav-label{text-align:center;font-size:10px;font-weight:900;letter-spacing:1.1px;color:#8fa4b2;text-transform:uppercase;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.info-close{position:static;width:42px;height:42px;display:flex;align-items:center;justify-content:center;border:1px solid rgba(255,255,255,.08);border-radius:11px;background:rgba(10,18,24,.78);color:#d9e2e8;font-size:23px;line-height:1;cursor:pointer;z-index:3;-webkit-backdrop-filter:blur(8px);backdrop-filter:blur(8px);justify-self:end}.info-back{position:static;width:42px;height:42px;display:flex;align-items:center;justify-content:center;border:1px solid rgba(255,255,255,.08);border-radius:11px;background:rgba(10,18,24,.78);color:#d9e2e8;cursor:pointer;justify-self:start}.info-back ha-icon{--mdc-icon-size:20px}.info-kicker{padding-right:0}.room-iq-hero{display:grid;grid-template-columns:44px minmax(0,1fr) auto;gap:10px;align-items:center;margin:12px 0;padding:12px;border-radius:14px;border:1px solid color-mix(in srgb,var(--room-iq) 30%,transparent);background:color-mix(in srgb,var(--room-iq) 7%,transparent)}.room-iq-icon{width:44px;height:44px;border-radius:12px;display:flex;align-items:center;justify-content:center;background:color-mix(in srgb,var(--room-iq) 12%,transparent);color:var(--room-iq)}.room-iq-icon ha-icon{--mdc-icon-size:25px}.room-iq-hero strong,.room-iq-hero span{display:block}.room-iq-hero strong{font-size:15px;color:var(--room-iq)}.room-iq-hero span{font-size:9px;color:#aebbc4;margin-top:3px;line-height:13px}.room-iq-quality{padding:6px 8px;border-radius:999px;font-size:8px;font-weight:850;white-space:nowrap}.room-iq-quality.ok{color:#67df92;background:rgba(103,223,146,.08)}.room-iq-quality.warn{color:#ff9b7a;background:rgba(255,155,122,.08)}.room-iq-why{display:grid;gap:5px;margin:9px 0;padding:10px;border-radius:12px;background:rgba(255,255,255,.025)}.room-iq-why>div:not(.tiny){display:grid;grid-template-columns:18px 1fr;gap:6px;align-items:start;font-size:9px;line-height:13px;color:#bac5cc}.room-iq-why ha-icon{--mdc-icon-size:15px;color:#63d2f7}.room-iq-context{margin-top:10px;padding:10px;border-radius:12px;background:rgba(255,255,255,.025)}.room-iq-context span{display:block;margin-top:4px;font-size:9px;line-height:13px;color:#98a8b3}.info-grid{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:6px}.info-grid>div{padding:7px 8px;border-radius:10px;background:rgba(255,255,255,.025);min-height:0}.info-grid b,.info-grid span{display:block}.info-grid b{font-size:12px;line-height:15px}.info-grid span{font-size:7.5px;line-height:10px;color:#84939e;margin-top:2px}.dialog-scroll,.dialog-scroll *{touch-action:pan-y pinch-zoom}.measurement{font-size:7.5px;margin-top:6px;padding:4px 6px;border-radius:7px;border:1px solid transparent}.measure-ok{color:#7ea98c;background:rgba(75,150,95,.045);border-color:rgba(90,170,110,.10)}.measure-bad{color:#b77f7f;background:rgba(170,70,70,.045);border-color:rgba(190,80,80,.10)}.floor-room-group{margin-top:12px}.floor-room-group:first-child{margin-top:4px}.floor-room-heading{display:flex;align-items:center;gap:6px;padding:4px 3px 6px;color:#8fa4b2;font-size:9px;font-weight:900;letter-spacing:.7px;text-transform:uppercase}.floor-room-heading ha-icon{--mdc-icon-size:15px}.floor-room-content{display:grid;gap:5px}.rooms-overview .floor-room-content{gap:8px}.breakdown{display:grid;gap:5px;margin-top:9px}.breakdown-row{display:grid;grid-template-columns:minmax(0,1fr) auto 70px;gap:8px;align-items:center;padding:8px;border-radius:9px;background:rgba(255,255,255,.025)}.breakdown-row span{font-size:8px;color:#84939e}.breakdown-row strong{text-align:right}.room-detail{scroll-margin-top:70px}.dialog{min-height:min-content}.submodal{position:fixed;top:0;right:0;bottom:0;left:0;inset:0;z-index:10010;background:rgba(4,9,13,.74);display:flex;align-items:flex-start;justify-content:center;padding:calc(env(safe-area-inset-top,0px) + 58px) 16px 16px;box-sizing:border-box;overflow:hidden}.subdialog{width:100%;width:min(920px,100%);min-height:0;height:calc(100vh - env(safe-area-inset-top,0px) - 76px);height:calc(100dvh - env(safe-area-inset-top,0px) - 76px);max-height:calc(100vh - env(safe-area-inset-top,0px) - 76px);max-height:calc(100dvh - env(safe-area-inset-top,0px) - 76px);overflow-y:auto;overflow-x:hidden;touch-action:pan-y pinch-zoom;-webkit-overflow-scrolling:touch;overscroll-behavior:contain;overscroll-behavior-y:contain;overflow-anchor:none;scroll-behavior:auto;scrollbar-gutter:stable;border-radius:20px;background:var(--ha-card-background,var(--card-background-color,#10181e));box-shadow:0 20px 80px rgba(0,0,0,.55)}.subdialog .info-panel{margin:0;border:0}.profile-options{display:grid;gap:9px;padding:0 14px 16px}.profile-option{text-align:left;border:1px solid rgba(255,255,255,.12);border-radius:14px;background:rgba(255,255,255,.04);padding:12px;color:inherit}.profile-option.selected{border-color:#67df92}.profile-option span{display:block;margin-top:4px;color:var(--secondary-text-color)}

      .brand-subtitle{font-size:9px;letter-spacing:1.6px;font-weight:800;color:#7e919f;margin-top:1px}.ai-top{padding-bottom:2px}.top.profile-only{display:flex;justify-content:flex-end;min-height:0}.top.profile-only .pill{justify-self:auto}.ai-card{position:relative;overflow:hidden;background:linear-gradient(145deg,rgba(19,32,40,.98),rgba(8,16,22,.98))}.ai-card:before{content:"";position:absolute;top:0;right:0;bottom:0;left:0;inset:0;pointer-events:none;background:radial-gradient(circle at 85% 0%,rgba(91,212,255,.08),transparent 36%);background:radial-gradient(circle at 85% 0%,color-mix(in srgb,var(--decision) 14%,transparent),transparent 36%)}.context-impacts{position:relative}.decision-impact small{display:block;margin-top:3px;font-size:9px;color:var(--secondary-text-color);font-weight:500;line-height:1.25}.decision-impact.clickable{cursor:pointer;border-color:rgba(91,212,255,.20)}.decision-impact.clickable:after{content:"›";position:absolute;right:7px;top:6px;color:#6f8797;font-size:13px}.decision-impact{position:relative}.decision-impact.forecast{cursor:pointer;border-color:rgba(91,212,255,.22);border-color:color-mix(in srgb,var(--decision) 45%,rgba(255,255,255,.10))}.iq-process{margin-top:12px;padding:10px 11px;border:1px solid rgba(106,215,255,.14);border-radius:13px;background:rgba(68,178,219,.045)}.iq-process-head{display:grid;grid-template-columns:auto auto 1fr;gap:7px;align-items:center;font-size:9px;letter-spacing:.7px;color:#85dfff}.iq-process-head>span:last-child{text-align:right;color:var(--secondary-text-color);letter-spacing:0}.iq-pulse{width:7px;height:7px;border-radius:50%;background:#67df92;box-shadow:0 0 0 0 rgba(103,223,146,.5);animation:iqpulse 2s infinite}.iq-process-text{font-size:10px;color:var(--secondary-text-color);margin-top:5px;line-height:1.4}@keyframes iqpulse{0%{box-shadow:0 0 0 0 rgba(103,223,146,.45)}70%{box-shadow:0 0 0 7px rgba(103,223,146,0)}100%{box-shadow:0 0 0 0 rgba(103,223,146,0)}}.compact-actions{margin-top:7px;padding-top:7px;border-top:1px solid rgba(255,255,255,.055)}.compact-actions .details-btn{min-height:30px;padding:6px 12px;font-size:10px;opacity:.82}.detail-quick{display:flex;align-items:center;justify-content:space-between;gap:12px;padding:12px 14px;margin:4px 0 12px;border:1px solid rgba(99,210,247,.14);border-radius:15px;background:rgba(99,210,247,.045)}.detail-quick b,.detail-quick span{display:block}.detail-quick span{font-size:10px;color:var(--secondary-text-color);margin-top:2px}.quick-forecast{display:grid;grid-template-columns:auto auto;gap:2px 6px;align-items:center;border:1px solid rgba(99,210,247,.22);border-radius:12px;background:rgba(99,210,247,.08);color:inherit;padding:8px 10px;cursor:pointer}.quick-forecast ha-icon{grid-row:1/3;--mdc-icon-size:19px;color:#63d2f7}.quick-forecast b{font-size:13px}.quick-forecast span{font-size:8px;margin:0;text-align:left}.last-vent-tile{--result:#63d2f7;display:grid;grid-template-columns:42px minmax(0,1fr) 22px;gap:10px;align-items:center;margin-top:12px;padding:12px 13px;border-radius:15px;border:1px solid color-mix(in srgb,var(--result) 22%,rgba(255,255,255,.08));background:color-mix(in srgb,var(--result) 5%,rgba(255,255,255,.018));cursor:pointer}.last-vent-tile-icon{width:42px;height:42px;border-radius:12px;display:flex;align-items:center;justify-content:center;color:var(--result);background:color-mix(in srgb,var(--result) 10%,transparent);border:1px solid color-mix(in srgb,var(--result) 18%,transparent)}.last-vent-tile-icon ha-icon{--mdc-icon-size:23px}.last-vent-tile b,.last-vent-tile span{display:block}.last-vent-tile b{font-size:11px;margin-top:2px}.last-vent-tile span{font-size:8px;line-height:11px;color:#82929e;margin-top:2px}.last-vent-tile-chevron{--mdc-icon-size:20px;color:var(--result);justify-self:end}.vent-result{margin-top:12px;padding:14px;border-radius:18px;border:1px solid color-mix(in srgb,var(--result) 32%,rgba(255,255,255,.10));background:linear-gradient(145deg,color-mix(in srgb,var(--result) 8%,rgba(255,255,255,.018)),rgba(255,255,255,.015))}.vent-result-hero{box-shadow:0 0 0 1px color-mix(in srgb,var(--result) 8%,transparent),0 12px 35px rgba(0,0,0,.16)}.result-head{display:grid;grid-template-columns:42px minmax(0,1fr) auto;gap:10px;align-items:center}.result-icon{width:42px;height:42px;border-radius:13px;display:flex;align-items:center;justify-content:center;color:var(--result);background:color-mix(in srgb,var(--result) 12%,transparent);border:1px solid color-mix(in srgb,var(--result) 22%,transparent)}.result-icon ha-icon{--mdc-icon-size:25px}.result-head h3{font-size:15px;line-height:19px;margin:2px 0 0}.result-head span{font-size:8.5px;color:var(--secondary-text-color)}.result-countdown{justify-self:end;padding:5px 8px;border-radius:999px;border:1px solid color-mix(in srgb,var(--result) 25%,transparent);background:color-mix(in srgb,var(--result) 8%,transparent);color:var(--result)!important;font-weight:850;white-space:nowrap}.result-metrics{display:grid;grid-template-columns:repeat(auto-fit,minmax(105px,1fr));gap:6px;margin-top:11px}.result-metrics>div{padding:9px;border-radius:11px;background:rgba(255,255,255,.028);border:1px solid rgba(255,255,255,.07)}.result-metrics span,.result-metrics b,.result-metrics small{display:block}.result-metrics span{font-size:7px;letter-spacing:.5px;color:#82929e}.result-metrics b{font-size:12px;margin-top:2px}.result-metrics small{font-size:7.5px;color:#82929e;margin-top:1px}.result-iq{display:grid;grid-template-columns:27px minmax(0,1fr);gap:8px;margin-top:9px;padding:9px;border-radius:11px;background:rgba(91,212,255,.04);border:1px solid rgba(91,212,255,.12)}.result-iq ha-icon{--mdc-icon-size:20px;color:#63d2f7}.result-iq b,.result-iq span{display:block}.result-iq b{font-size:9.5px}.result-iq span{font-size:8px;line-height:11px;color:#8fa0ac;margin-top:2px}.result-rooms{display:grid;gap:5px;margin-top:9px}.result-room{display:grid;grid-template-columns:minmax(0,1fr) auto;gap:9px;align-items:center;padding:8px 9px;border-radius:10px;background:rgba(255,255,255,.025);border:1px solid rgba(255,255,255,.055)}.result-room b,.result-room span{display:block}.result-room b{font-size:9.5px}.result-room span{font-size:7.5px;line-height:10px;color:#84939e;margin-top:2px}.result-room strong{font-size:10px;white-space:nowrap}.result-footer{display:flex;justify-content:space-between;gap:10px;align-items:center;margin-top:8px;font-size:7.5px;color:#82929e}.result-footer b{font-size:8.5px;color:var(--result);white-space:nowrap}.result-complete{font-size:7.5px;color:#718490;white-space:nowrap}.metrics{display:none!important}
      @media(max-width:900px){.metrics{grid-template-columns:repeat(3,minmax(0,1fr))}.rooms{grid-template-columns:1fr}.overview{grid-template-columns:repeat(2,minmax(0,1fr))}}@media(max-width:650px){.decision-impacts{grid-template-columns:repeat(auto-fit,minmax(120px,1fr))}.decision-footer{display:grid;gap:3px}.decision-footer span:last-child{text-align:left}.metrics{grid-template-columns:repeat(2,minmax(0,1fr))}.history-grid,.learn-panel{grid-template-columns:1fr}.info-grid{grid-template-columns:repeat(2,minmax(0,1fr));gap:5px}.info-grid>div{padding:7px}.info-grid b{font-size:11px;line-height:14px}.info-grid span{font-size:7.2px;line-height:9.5px}.result-head{grid-template-columns:38px minmax(0,1fr)}.result-countdown{grid-column:2;justify-self:start}.result-metrics{grid-template-columns:repeat(auto-fit,minmax(105px,1fr))}.rooms-overview{padding:13px}.rooms-overview h3{font-size:17px}.rooms-subtitle{font-size:10px!important;margin-bottom:10px!important}.room{padding:10px}.room-head{grid-template-columns:42px minmax(0,1fr) auto 16px;gap:7px}.room-icon{width:42px;height:42px}.room-title{font-size:14px}.room-head .muted{font-size:8.5px}.room-water{gap:4px}.room-water strong{font-size:12.5px}.room-water ha-icon{--mdc-icon-size:20px}.room-chevron{--mdc-icon-size:18px}.room-summary-grid{grid-template-columns:repeat(3,minmax(0,1fr));gap:5px;margin-top:8px}.room-stat{grid-template-columns:22px minmax(0,1fr);gap:5px;padding:7px 5px}.room-stat .stat-icon{--mdc-icon-size:18px}.room-stat .tiny{font-size:6.5px;letter-spacing:.3px}.room-stat .room-value{font-size:10px}.room-stat .muted{font-size:7px}.top{grid-template-columns:44px minmax(0,1fr) auto}.pill{justify-self:end}.room-iq-hero{grid-template-columns:38px minmax(0,1fr)}.room-iq-quality{grid-column:2;justify-self:start}.info-close{width:42px;height:42px}.info-back{width:42px;height:42px}.modal{padding:calc(env(safe-area-inset-top,0px) + 58px) 7px 12px}.dialog{--dialog-pad:12px;width:100%;max-height:calc(100vh - env(safe-area-inset-top,0px) - 70px);max-height:calc(100dvh - env(safe-area-inset-top,0px) - 70px)}}
    .breakdown-row.vent-active{background:rgba(80,220,150,.10)!important;border:1px solid rgba(80,220,150,.26)!important;box-shadow:inset 3px 0 0 rgba(80,220,150,.75)}.vent-passive{background:rgba(91,212,255,.07)!important;border:1px solid rgba(91,212,255,.20)!important;box-shadow:inset 3px 0 0 rgba(91,212,255,.65)}.breakdown-row.vent-passive b,.breakdown-row.vent-passive span{color:#dff6ff}.breakdown-row.vent-inactive{opacity:.58}.breakdown-row b{display:flex;align-items:center;gap:8px}.breakdown-row b ha-icon{--mdc-icon-size:19px}.breakdown-row.vent-active b,.breakdown-row.vent-active span{color:#dff8e8}.house-live{display:grid;grid-template-columns:minmax(0,1fr) auto;gap:6px 12px;align-items:center;margin:12px 0;padding:12px;border-radius:14px;background:rgba(91,212,255,.07);border:1px solid rgba(91,212,255,.18)}.house-live b,.house-live span{display:block}.monitor-only-detail .room-iq-hero{grid-template-columns:54px minmax(0,1fr) auto}.monitor-only-grid{grid-template-columns:repeat(2,minmax(0,1fr))}.monitor-only-empty{display:grid;grid-template-columns:28px minmax(0,1fr);gap:9px;align-items:center;margin-top:10px;padding:11px;border-radius:12px;background:rgba(255,255,255,.025);border:1px solid rgba(255,255,255,.06)}.monitor-only-empty>ha-icon{--mdc-icon-size:22px;color:#82929e}.monitor-only-empty b,.monitor-only-empty span{display:block}.monitor-only-empty b{font-size:10px}.monitor-only-empty span{font-size:8px;line-height:11px;color:#8fa1ad;margin-top:2px}.house-live>span{grid-column:1/-1;color:#8fa4b1;font-size:8.5px}.settings-panel{padding:14px!important;background:linear-gradient(145deg,rgba(35,57,72,.50),rgba(16,24,30,.98))!important}.settings-hero{display:grid;grid-template-columns:48px minmax(0,1fr);gap:12px;align-items:start;margin-bottom:13px}.settings-hero-icon{width:48px;height:48px;border-radius:14px;display:flex;align-items:center;justify-content:center;background:rgba(91,212,255,.10);color:#63d2f7;border:1px solid rgba(91,212,255,.18)}.settings-hero-icon ha-icon{--mdc-icon-size:27px}.settings-hero h3{margin:2px 0 3px}.settings-category-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:8px}.settings-category{appearance:none;display:grid;grid-template-columns:38px minmax(0,1fr) 20px;gap:10px;align-items:center;text-align:left;padding:11px;border-radius:13px;border:1px solid rgba(255,255,255,.08);background:rgba(255,255,255,.026);color:inherit;cursor:pointer}.settings-category>ha-icon:first-child{--mdc-icon-size:23px;color:#63d2f7}.settings-category b,.settings-category span{display:block}.settings-category b{font-size:11px}.settings-category span{font-size:8.5px;line-height:12px;color:#8fa1ad;margin-top:2px}.settings-category.resident-feature{border-color:rgba(91,212,255,.20);background:linear-gradient(135deg,rgba(91,212,255,.075),rgba(138,107,255,.035));box-shadow:inset 0 1px 0 rgba(255,255,255,.035)}.resident-feature-badge{display:block;width:max-content;margin-bottom:3px;color:#76dbff;font-size:6px;line-height:8px;font-weight:950;letter-spacing:.55px}.resident-profile-spotlight{appearance:none;width:100%;display:grid;grid-template-columns:56px minmax(0,1fr);gap:12px;align-items:center;text-align:left;margin:10px 0 12px;padding:14px;border-radius:17px;border:1px solid rgba(91,212,255,.24);background:radial-gradient(circle at 8% 20%,rgba(91,212,255,.18),transparent 38%),linear-gradient(135deg,rgba(91,212,255,.08),rgba(138,107,255,.07));color:inherit;box-shadow:inset 0 1px 0 rgba(255,255,255,.05),0 8px 26px rgba(0,0,0,.12);cursor:pointer}.resident-profile-spotlight-icon{position:relative;width:54px;height:54px;border-radius:17px;display:flex;align-items:center;justify-content:center;background:rgba(91,212,255,.11);border:1px solid rgba(91,212,255,.23);color:#73dcff}.resident-profile-spotlight-icon>ha-icon:first-child{--mdc-icon-size:29px}.resident-profile-spotlight-brain{position:absolute;right:-4px;bottom:-4px;--mdc-icon-size:18px;padding:4px;border-radius:9px;background:#17242d;color:#8b7cff;border:1px solid rgba(138,107,255,.28)}.resident-profile-spotlight h4{margin:2px 0 4px;font-size:14px}.resident-profile-spotlight p{margin:0;color:#9eafb9;font-size:8.5px;line-height:12px}.resident-profile-spotlight-link{display:flex!important;align-items:center;gap:4px;margin-top:8px!important;color:#74dcff!important;font-size:8px!important;font-weight:900}.resident-profile-spotlight-link ha-icon{--mdc-icon-size:14px}.settings-chevron{--mdc-icon-size:18px;color:#718490}.settings-group{margin-top:10px;border:1px solid rgba(255,255,255,.075);border-radius:14px;overflow:hidden;background:rgba(255,255,255,.016)}.settings-group-head{padding:10px 11px;background:rgba(91,212,255,.035);border-bottom:1px solid rgba(255,255,255,.055)}.settings-group-head span{display:block;font-size:8.5px;line-height:12px;color:#91a2ad;margin-top:3px}.settings-field{display:grid;grid-template-columns:minmax(0,1fr) minmax(190px,42%);gap:14px;align-items:center;padding:11px;border-top:1px solid rgba(255,255,255,.052)}.settings-group .settings-field:first-of-type{border-top:0}.settings-field-copy b,.settings-field-copy span,.settings-field-copy small{display:block}.settings-field-copy b{font-size:10.5px}.settings-field-copy span{font-size:8.5px;line-height:12px;color:#a6b4bd;margin-top:3px}.settings-field-copy small{font-size:7.5px;line-height:11px;color:#6f828f;margin-top:4px}.settings-control{min-width:0}.settings-input-wrap{display:flex;align-items:center;gap:7px}.settings-input-wrap>span{font-size:8px;color:#81939f;white-space:nowrap}.settings-input{width:100%;min-height:38px;padding:8px 9px;border-radius:10px;border:1px solid rgba(255,255,255,.12);background:#0f181f;color:#eaf1f5;font:inherit;font-size:9px;outline:none}.settings-input:focus{border-color:rgba(91,212,255,.55);box-shadow:0 0 0 2px rgba(91,212,255,.08)}.settings-textarea{resize:vertical;line-height:14px}.settings-multi{min-height:92px}.settings-switch{position:relative;display:inline-flex;justify-self:end;width:44px;height:24px}.settings-switch input{opacity:0;width:0;height:0}.settings-switch span{position:absolute;inset:0;border-radius:999px;background:#35424b;border:1px solid rgba(255,255,255,.10);transition:.18s}.settings-switch span:after{content:"";position:absolute;width:18px;height:18px;left:2px;top:2px;border-radius:50%;background:#dbe4e9;transition:.18s}.settings-switch input:checked+span{background:rgba(91,212,255,.28);border-color:rgba(91,212,255,.45)}.settings-switch input:checked+span:after{transform:translateX(20px);background:#70dafa}.settings-field-stack{grid-template-columns:1fr;align-items:stretch}.resident-profile-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:8px;padding:10px}.resident-profile-card{position:relative;overflow:hidden;padding:12px;border-radius:16px;border:1px solid rgba(91,212,255,.20);background:linear-gradient(145deg,rgba(91,212,255,.075),rgba(138,107,255,.035) 48%,rgba(255,255,255,.018));box-shadow:inset 0 1px 0 rgba(255,255,255,.045),0 8px 24px rgba(0,0,0,.12)}.resident-profile-glow{position:absolute;right:-34px;top:-42px;width:120px;height:120px;border-radius:50%;background:radial-gradient(circle,rgba(91,212,255,.13),transparent 68%);pointer-events:none}.resident-profile-badge{position:relative;display:flex;align-items:center;gap:5px;width:max-content;padding:4px 7px;border-radius:999px;background:rgba(91,212,255,.075);border:1px solid rgba(91,212,255,.15);color:#78dcff;font-size:6.7px;font-weight:950;letter-spacing:.55px;margin-bottom:9px}.resident-profile-badge ha-icon{--mdc-icon-size:12px}.resident-profile-head{position:relative;display:grid;grid-template-columns:38px minmax(0,1fr) 26px;gap:9px;align-items:center;margin-bottom:10px}.resident-avatar{width:38px;height:38px;border-radius:12px;display:flex;align-items:center;justify-content:center;background:linear-gradient(145deg,rgba(91,212,255,.16),rgba(138,107,255,.09));color:#74ddff;border:1px solid rgba(91,212,255,.24);box-shadow:inset 0 1px 0 rgba(255,255,255,.05)}.resident-profile-spark{--mdc-icon-size:18px;color:#70d9fb;opacity:.72;justify-self:end}.resident-avatar ha-icon{--mdc-icon-size:19px}.resident-profile-head b,.resident-profile-head span{display:block}.resident-profile-head b{font-size:10px}.resident-profile-head span{font-size:7.5px;color:#8395a0;margin-top:2px;overflow:hidden;text-overflow:ellipsis}.resident-profile-card label{display:block;margin-top:8px}.resident-profile-card label>span{display:block;font-size:7.5px;color:#8fa1ad;margin-bottom:4px}.settings-save,.settings-delete,.settings-danger button,.settings-error button{appearance:none;border:1px solid rgba(91,212,255,.22);border-radius:11px;background:rgba(91,212,255,.08);color:#dff6ff;padding:9px 11px;font:inherit;font-size:9px;font-weight:850;cursor:pointer;display:flex;align-items:center;justify-content:center;gap:6px}.settings-save ha-icon,.settings-delete ha-icon{--mdc-icon-size:17px}.settings-delete,.settings-danger button{border-color:rgba(255,119,112,.23);background:rgba(255,119,112,.07);color:#ffaaa5}.settings-toast{position:sticky;top:63px;z-index:35;width:max-content;max-width:calc(100% - 24px);margin:8px auto -2px;padding:6px 10px;border-radius:999px;background:#19382d;color:#78e8a1;border:1px solid rgba(103,223,146,.23);font-size:8.5px;font-weight:850}.settings-inline-error{display:flex;align-items:center;gap:7px;margin:9px 12px;padding:8px 10px;border-radius:10px;background:rgba(255,119,112,.09);color:#ffaaa5;border:1px solid rgba(255,119,112,.20);font-size:8.5px}.settings-inline-error ha-icon{--mdc-icon-size:17px}.settings-loading{display:flex;align-items:center;justify-content:center;gap:9px;min-height:140px;color:#9fb0ba}.settings-error{display:grid;grid-template-columns:30px minmax(0,1fr);gap:9px;align-items:center;padding:12px}.settings-error>ha-icon{color:#ff7770}.settings-error b,.settings-error span{display:block}.settings-error span{font-size:8.5px;color:#a6b4bd;margin-top:3px}.settings-error button{grid-column:2;justify-self:start}.settings-room-list{display:grid;gap:7px;margin-top:12px}.settings-room-row{display:grid;grid-template-columns:minmax(0,1fr) auto;gap:7px}.settings-room-main{appearance:none;display:grid;grid-template-columns:30px minmax(0,1fr) 18px;gap:9px;align-items:center;text-align:left;padding:10px;border-radius:12px;border:1px solid rgba(255,255,255,.08);background:rgba(255,255,255,.026);color:inherit;cursor:pointer}.settings-room-main b,.settings-room-main span{display:block}.settings-room-main b{font-size:10.5px}.settings-room-main span{font-size:8px;color:#8799a5;margin-top:2px}.settings-room-index{width:28px;height:28px;border-radius:9px;display:flex!important;align-items:center;justify-content:center;background:rgba(91,212,255,.08);color:#63d2f7!important;font-weight:900}.settings-room-order{display:grid;grid-template-columns:34px 34px;gap:4px}.settings-room-order button{appearance:none;border:1px solid rgba(255,255,255,.08);border-radius:9px;background:rgba(255,255,255,.03);color:#b9c6cd}.settings-room-order button:disabled{opacity:.25}.settings-room-order ha-icon{--mdc-icon-size:17px}.settings-add-room{margin-top:10px;width:100%}.settings-empty{padding:14px;text-align:center;font-size:9px;color:#82929e}.settings-dim-grid{display:grid;grid-template-columns:repeat(3,1fr);gap:7px;padding:11px;border-top:1px solid rgba(255,255,255,.052)}.settings-dim-grid label{font-size:8px;color:#81939f}.settings-dim-grid input{margin-top:4px}.settings-contact-box{padding:11px;border-top:1px solid rgba(255,255,255,.052)}.settings-contact-row{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:8px;align-items:end;margin-top:10px;padding:10px;border-radius:12px;background:rgba(255,255,255,.022);border:1px solid rgba(255,255,255,.055)}.settings-contact-title{grid-column:1/-1}.settings-contact-row label>span{display:block;margin:0 0 4px;font-size:7.5px;color:#81939f}.settings-contact-help{grid-column:1/-1;font-size:7.2px;line-height:10px;color:#718490}.settings-contact-row b,.settings-contact-row span{display:block}.settings-contact-row b{font-size:9px}.settings-contact-row span{font-size:7.5px;color:#718490;margin-top:2px;overflow:hidden;text-overflow:ellipsis}.settings-room-actions{display:flex;gap:8px;padding:11px;border-top:1px solid rgba(255,255,255,.052)}.settings-danger-grid{display:grid;gap:9px;margin-top:12px}.settings-danger{display:grid;grid-template-columns:36px minmax(0,1fr) auto;gap:10px;align-items:center;padding:11px;border-radius:12px;border:1px solid rgba(255,255,255,.08);background:rgba(255,255,255,.025)}.settings-danger>ha-icon{color:#e7b86a}.settings-danger b,.settings-danger span{display:block}.settings-danger b{font-size:10px}.settings-danger span{font-size:8px;line-height:11px;color:#8fa1ad;margin-top:2px}@media(max-width:700px){.resident-profile-grid{grid-template-columns:1fr}.settings-category-grid{grid-template-columns:1fr}.settings-field{grid-template-columns:1fr;gap:8px}.settings-switch{justify-self:start}.settings-contact-row{grid-template-columns:1fr}.settings-danger{grid-template-columns:30px minmax(0,1fr)}.settings-danger button{grid-column:1/-1}.settings-room-row{grid-template-columns:1fr}.settings-room-order{grid-template-columns:1fr 1fr}.settings-dim-grid{grid-template-columns:1fr}.dialog-head{grid-template-columns:42px minmax(0,1fr) 42px 42px}.dialog-title{font-size:16px}}.learning-overview-card{margin-top:8px;padding:13px;border-radius:18px;background:linear-gradient(145deg,rgba(91,212,255,.065),rgba(255,255,255,.018));border:1px solid rgba(91,212,255,.18);box-shadow:inset 0 1px 0 rgba(255,255,255,.035)}.learning-overview-hero{display:grid;grid-template-columns:66px minmax(0,1fr);gap:13px;align-items:center}.learning-overview-copy h2{margin:3px 0 4px;font-size:17px}.learning-overview-copy p{margin:0;color:#9fb1bc;font-size:8.5px;line-height:12px}.learning-overview-title{display:flex;align-items:center;justify-content:space-between;gap:8px}.learning-overview-title span{font-size:7px;font-weight:900;color:#67df92;border:1px solid rgba(103,223,146,.3);background:rgba(103,223,146,.08);border-radius:999px;padding:4px 7px;white-space:nowrap}.learning-kpis{display:grid;grid-template-columns:1fr 1fr;gap:8px;margin-top:12px}.learning-kpis>div{padding:10px;border-radius:13px;background:rgba(255,255,255,.025);border:1px solid rgba(91,212,255,.12)}.learning-kpis span,.learning-kpis b{display:flex;align-items:center;gap:5px}.learning-kpis span{font-size:8px;font-weight:800;color:#a7b7c1}.learning-kpis span ha-icon{--mdc-icon-size:14px;color:#63d2f7}.learning-kpis b{font-size:18px;margin:5px 0}.learning-kpis i,.learning-area-score i,.learning-detail-progress i,.season-card i,.season-total i,.night-grid i{display:block;height:5px;border-radius:999px;background:rgba(255,255,255,.07);overflow:hidden}.learning-kpis em,.learning-area-score em,.learning-detail-progress em,.season-card em,.season-total em,.night-grid em{display:block;height:100%;border-radius:inherit;background:#63d2f7}.learning-now{width:100%;display:grid;grid-template-columns:28px minmax(0,1fr) 18px;gap:8px;align-items:center;text-align:left;margin-top:10px;padding:10px;border-radius:12px;border:1px solid rgba(91,212,255,.2);background:rgba(91,212,255,.045);color:inherit}.learning-now>ha-icon:first-child{color:#e8d765}.learning-now b,.learning-now small{display:block}.learning-now b{font-size:9px}.learning-now small{font-size:7.5px;color:#63d2f7;margin-top:2px}.learning-area-head{margin:13px 2px 7px}.learning-area-head b,.learning-area-head span{display:block}.learning-area-head b{font-size:12px}.learning-area-head span{font-size:7.5px;color:#8296a2;margin-top:2px}.learning-area-list{display:grid;gap:7px}.learning-area{appearance:none;width:100%;display:grid;grid-template-columns:38px minmax(0,1fr) 72px 16px;gap:9px;align-items:center;text-align:left;padding:9px;border-radius:13px;background:rgba(255,255,255,.024);border:1px solid rgba(255,255,255,.065);color:inherit}.learning-area-icon{width:36px;height:36px;border-radius:11px;display:flex;align-items:center;justify-content:center;background:rgba(91,212,255,.08);border:1px solid rgba(91,212,255,.15);color:#63d2f7}.learning-area-icon ha-icon{--mdc-icon-size:20px}.learning-area-copy b,.learning-area-copy small{display:block}.learning-area-copy b{font-size:9.5px}.learning-area-copy small{font-size:7px;color:#8296a2;margin-top:3px}.learning-area-score b{display:block;text-align:right;font-size:9px;margin-bottom:5px}.learning-area-chevron{--mdc-icon-size:17px;color:#63d2f7}.learning-overview-note{display:grid;grid-template-columns:18px minmax(0,1fr);gap:7px;align-items:start;margin-top:10px;padding:9px;border-radius:11px;background:rgba(91,212,255,.035);border:1px solid rgba(91,212,255,.1);color:#8296a2}.learning-overview-note ha-icon{--mdc-icon-size:16px;color:#63d2f7}.learning-overview-note span{font-size:7.3px;line-height:10px}.learning-detail-panel{padding-bottom:16px}.learning-group-hero,.longterm-hero{display:grid;grid-template-columns:48px minmax(0,1fr) auto;gap:10px;align-items:center;margin:10px 0 12px;padding:12px;border-radius:15px;background:rgba(91,212,255,.045);border:1px solid rgba(91,212,255,.14)}.learning-group-hero>ha-icon,.longterm-hero>ha-icon{--mdc-icon-size:28px;color:#63d2f7}.learning-group-hero h3{margin:0}.learning-group-hero p,.longterm-hero span{margin:2px 0 0;font-size:7.5px;color:#8ea1ad}.learning-group-hero strong{font-size:16px}.learning-detail-list{display:grid;gap:8px}.learning-detail-card{display:grid;grid-template-columns:38px minmax(0,1fr);gap:9px;padding:10px;border-radius:13px;background:rgba(255,255,255,.024);border:1px solid rgba(255,255,255,.06)}.learning-detail-icon{width:36px;height:36px;border-radius:11px;display:flex;align-items:center;justify-content:center;background:rgba(91,212,255,.08);color:#63d2f7}.learning-detail-icon ha-icon{--mdc-icon-size:20px}.learning-detail-head{display:flex;justify-content:space-between;gap:8px}.learning-detail-head b{font-size:9.5px}.learning-detail-head strong{font-size:7px;color:#67df92}.learning-detail-card p{font-size:7.3px;line-height:10px;color:#8fa1ad;margin:3px 0 7px}.learning-detail-card small{display:block;font-size:6.8px;color:#788c98;margin-top:4px}.learning-detail-progress{display:grid;grid-template-columns:minmax(0,1fr) auto;gap:8px;align-items:center}.learning-detail-progress b{font-size:7px}.learning-quality-grid{display:grid;grid-template-columns:1fr 1fr;gap:7px;margin:10px 0}.learning-quality-grid>div{padding:10px;border-radius:12px;background:rgba(255,255,255,.025);border:1px solid rgba(255,255,255,.06)}.learning-quality-grid span,.learning-quality-grid b{display:block}.learning-quality-grid span{font-size:7px;color:#8296a2}.learning-quality-grid b{font-size:16px;margin-top:3px}.learning-section-title{display:flex;justify-content:space-between;gap:8px;align-items:center;margin:13px 2px 7px}.learning-section-title b{font-size:11px}.learning-section-title span{font-size:7px;color:#63d2f7}.season-grid{display:grid;grid-template-columns:1fr 1fr;gap:7px}.season-card{display:grid;gap:5px;padding:10px;border-radius:13px;background:rgba(255,255,255,.024);border:1px solid rgba(255,255,255,.06)}.season-card>ha-icon{--mdc-icon-size:20px;color:#e7bd58}.season-card b{font-size:9px}.season-card strong{font-size:8px}.season-card small{font-size:6.8px;color:#8296a2}.season-card.done{border-color:rgba(103,223,146,.22)}.season-card.done>ha-icon{color:#67df92}.season-total{padding:10px;margin-top:8px;border-radius:13px;background:rgba(91,212,255,.035);border:1px solid rgba(91,212,255,.13)}.season-total span,.season-total b{display:block}.season-total span{font-size:7px;color:#8296a2}.season-total b{font-size:9px;margin:3px 0 7px}.night-grid{display:grid;grid-template-columns:1fr 1fr;gap:7px}.night-grid>div{padding:11px;border-radius:13px;background:rgba(255,255,255,.024);border:1px solid rgba(255,255,255,.06)}.night-grid strong,.night-grid b,.night-grid small{display:block}.night-grid strong{font-size:18px}.night-grid b{font-size:8px;margin:3px 0 7px}.night-grid small{font-size:6.8px;line-height:9px;color:#8296a2}.learning-empty{padding:12px;color:#8296a2;font-size:8px}@media(max-width:650px){.learning-overview-title{align-items:flex-start;flex-direction:column}.learning-area{grid-template-columns:36px minmax(0,1fr) 62px 14px}.season-grid,.night-grid{grid-template-columns:1fr 1fr}}.intelligence-hero{display:grid;grid-template-columns:66px minmax(0,1fr);gap:14px;align-items:center;padding:16px;margin-bottom:12px;border-radius:18px;background:radial-gradient(circle at 8% 20%,rgba(91,212,255,.16),transparent 34%),linear-gradient(135deg,rgba(91,212,255,.09),rgba(138,107,255,.07));border:1px solid rgba(91,212,255,.22);box-shadow:inset 0 1px 0 rgba(255,255,255,.05)}.intelligence-orbit{width:62px;height:62px;border-radius:20px;display:flex;align-items:center;justify-content:center;background:rgba(91,212,255,.10);border:1px solid rgba(91,212,255,.28);box-shadow:0 0 28px rgba(91,212,255,.10)}.intelligence-orbit ha-icon{--mdc-icon-size:34px;color:#6bdcff}.intelligence-copy h2{margin:3px 0 5px;font-size:18px;line-height:22px}.intelligence-copy p{margin:0;color:#a9bac4;font-size:9px;line-height:13px}.intelligence-meta{display:flex;flex-wrap:wrap;gap:6px;margin-top:9px}.intelligence-meta span{padding:5px 7px;border-radius:999px;background:rgba(255,255,255,.035);border:1px solid rgba(255,255,255,.07);font-size:7.5px;color:#8fa3af}.intelligence-meta b{color:#e9f8ff}.intelligence-v2.personal-ready .intelligence-hero{background:radial-gradient(circle at 8% 20%,rgba(91,212,255,.22),transparent 34%),linear-gradient(135deg,rgba(91,212,255,.13),rgba(138,107,255,.12));border-color:rgba(117,220,255,.38);box-shadow:inset 0 1px 0 rgba(255,255,255,.07),0 0 30px rgba(91,212,255,.07)}.learning-components-card{margin-top:8px;padding:13px;border-radius:16px;background:linear-gradient(145deg,rgba(91,212,255,.055),rgba(255,255,255,.018));border:1px solid rgba(91,212,255,.14);box-shadow:inset 0 1px 0 rgba(255,255,255,.025)}.learning-components-head{display:grid;grid-template-columns:minmax(0,1fr) auto;gap:12px;align-items:start}.learning-components-title{display:grid;grid-template-columns:40px minmax(0,1fr);gap:10px;align-items:center}.learning-components-icon{width:40px;height:40px;border-radius:12px;display:flex;align-items:center;justify-content:center;background:rgba(91,212,255,.10);border:1px solid rgba(91,212,255,.18);color:#63d2f7}.learning-components-icon ha-icon{--mdc-icon-size:23px}.learning-components-title h3{margin:2px 0 2px;font-size:14px}.learning-components-title span{display:block;font-size:8px;line-height:11px;color:#8fa1ad}.learning-overall{text-align:right;padding:7px 9px;border-radius:11px;background:rgba(91,212,255,.06);border:1px solid rgba(91,212,255,.12);min-width:74px}.learning-overall span,.learning-overall b{display:block}.learning-overall span{font-size:6.5px;font-weight:900;letter-spacing:.45px;color:#7f929e}.learning-overall b{font-size:17px;color:#dff7ff;margin-top:2px}.learn-quality-strip{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:6px;margin-top:10px}.learn-quality-strip>div{padding:7px 8px;border-radius:10px;background:rgba(255,255,255,.025);border:1px solid rgba(255,255,255,.055)}.learn-quality-strip span,.learn-quality-strip b{display:block}.learn-quality-strip span{font-size:6.2px;font-weight:900;letter-spacing:.4px;color:#788c99}.learn-quality-strip b{font-size:9px;line-height:12px;margin-top:2px;color:#dbe8ee}.learning-components-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:7px;margin-top:10px}.learn-component{display:grid;grid-template-columns:34px minmax(0,1fr);gap:8px;padding:9px;border-radius:12px;background:rgba(255,255,255,.024);border:1px solid rgba(255,255,255,.06);--learn-accent:#82929e}.learn-component.very{--learn-accent:#67df92}.learn-component.stable{--learn-accent:#7bd7b0}.learn-component.learning{--learn-accent:#63d2f7}.learn-component.early{--learn-accent:#d7b56c}.learn-component-icon{width:34px;height:34px;border-radius:10px;display:flex;align-items:center;justify-content:center;color:var(--learn-accent);background:color-mix(in srgb,var(--learn-accent) 10%,transparent);border:1px solid color-mix(in srgb,var(--learn-accent) 18%,transparent)}.learn-component-icon ha-icon{--mdc-icon-size:19px}.learn-component-head{display:grid;grid-template-columns:minmax(0,1fr) auto;gap:7px;align-items:start}.learn-component-head b,.learn-component-head span{display:block}.learn-component-head b{font-size:9.5px}.learn-component-head span{font-size:7px;line-height:9.5px;color:#7f929e;margin-top:2px}.learn-component-head strong{font-size:7.5px;color:var(--learn-accent);white-space:nowrap;padding:3px 5px;border-radius:999px;background:color-mix(in srgb,var(--learn-accent) 8%,transparent);border:1px solid color-mix(in srgb,var(--learn-accent) 16%,transparent)}.learn-progress{height:4px;border-radius:999px;background:rgba(255,255,255,.055);overflow:hidden;margin-top:7px}.learn-progress i{display:block;height:100%;border-radius:inherit;background:var(--learn-accent)}.learn-component-foot{display:flex;align-items:center;justify-content:space-between;gap:6px;margin-top:5px;font-size:6.8px;color:#768995}.learn-component-detail{font-size:7px;line-height:9.5px;color:#9cabb4;margin-top:5px}.learning-components-note{display:grid;grid-template-columns:16px minmax(0,1fr);gap:6px;align-items:start;margin-top:9px;padding-top:8px;border-top:1px solid rgba(255,255,255,.055);color:#7d909c}.learning-components-note ha-icon{--mdc-icon-size:14px}.learning-components-note span{font-size:7px;line-height:10px}.learn-components-empty{grid-column:1/-1;display:flex;gap:8px;align-items:center;padding:12px;color:#8395a0;font-size:8px}@media(max-width:650px){.learning-components-head{grid-template-columns:1fr}.learning-overall{justify-self:start;text-align:left}.learn-quality-strip{grid-template-columns:repeat(2,minmax(0,1fr))}.learning-components-grid{grid-template-columns:1fr}.learn-component-head{grid-template-columns:minmax(0,1fr) auto}}.learning-detail-card{padding:10px!important;gap:9px!important}.learning-detail-card p{margin:3px 0 5px!important}.learning-detail-progress{margin-top:5px!important}.longterm-hero{grid-template-columns:48px minmax(0,1fr)!important;gap:12px!important;align-items:center!important}.longterm-hero-copy{min-width:0;display:flex;flex-direction:column;gap:4px}.longterm-hero-copy b,.longterm-hero-copy span{display:block!important;position:static!important;white-space:normal!important}.longterm-hero-copy b{font-size:15px;line-height:19px}.longterm-hero-copy span{font-size:8px;line-height:11px;color:#8fa1ad}`;
class FreshAirIQCard extends HTMLElement {
    static getStubConfig() { return {}; }
    constructor() { super(); this.attachShadow({ mode: "open" }); this._config = {}; this._pageScrollSnapshot = null; this._hass = null; this._dialogOpen = false; this._info = null; this._infoStack = []; this._infoScrollStack = []; this._dialogScrollTop = 0; this._subdialogScrollTop = 0; this._pendingSubdialogScrollTop = null; this._forceDialogTop = false; this._postResultTimer = null; this._settingsData = null; this._settingsLoading = false; this._settingsSaving = false; this._settingsError = null; this._settingsNotice = null; this._renderFrame = null; this._renderFrameIsRaf = false; this._liveRefreshFrame = null; this._liveRefreshFrameIsRaf = false; this._statusEntityId = null; this._statusRescanNeeded = false; this._relevantStateIds = null; this._roomEntityIds = null; this._roomConfigSignature = null; this._entityCache = {}; this._profileOverride = null; this._forecastOverride = null; this._fieldTestRegistrationPromise = null; this._fieldTestSessionClientId = null; this._liveViewSnapshot = null; this._liveHtmlCache = {}; this._chartCache = { bars: new WeakMap(), line: new WeakMap() }; this._learningCardCache = null; }
    _captureOverlayViewport() {
        const nodes = [];
        let node = this;
        while (node) {
            const root = node.getRootNode?.();
            const parent = node.parentElement || (root && root.host) || null;
            if (!parent) break;
            try { const cs = getComputedStyle(parent); if (/(auto|scroll)/.test(`${cs.overflowY} ${cs.overflow}`) && parent.scrollHeight > parent.clientHeight) nodes.push([parent, parent.scrollTop, parent.scrollLeft]); } catch (_) {}
            node = parent;
        }
        this._pageScrollSnapshot = { x: window.scrollX, y: window.scrollY, nodes };
    }
    _restoreOverlayViewport() {
        const snap = this._pageScrollSnapshot; this._pageScrollSnapshot = null; if (!snap) return;
        const restore = () => { for (const [node, top, left] of snap.nodes || []) { if (node?.isConnected) { node.scrollTop = top; node.scrollLeft = left; } } window.scrollTo(snap.x || 0, snap.y || 0); };
        restore(); requestAnimationFrame(restore);
    }
    _rememberInfoViewport(view = this._info) {
        if (!this._infoScrollByView) this._infoScrollByView = new Map();
        if (!view) return 0;
        const current = this.shadowRoot?.querySelector(".subdialog");
        const top = current ? current.scrollTop : (this._infoScrollByView.get(view) ?? this._subdialogScrollTop ?? 0);
        this._infoScrollByView.set(view, top);
        return top;
    }
    _pushInfoViewport() {
        if (this._info) {
            this._infoStack.push(this._info);
            this._infoScrollStack.push(this._rememberInfoViewport(this._info));
        }
    }
    _resetInfoNavigation() { this._infoStack = []; this._infoScrollStack = []; if (this._infoScrollByView) this._infoScrollByView.clear(); this._subdialogScrollTop = 0; this._pendingSubdialogScrollTop = null; }
    _installAndroidTouchScroll(scroller) {
        if (!scroller || !/Android/i.test(navigator.userAgent || "")) return;
        let startY = 0, startTop = 0, dragging = false;
        scroller.addEventListener("touchstart", e => {
            if (!e.touches || e.touches.length !== 1) return;
            startY = e.touches[0].clientY; startTop = scroller.scrollTop; dragging = false;
        }, { passive: true });
        scroller.addEventListener("touchmove", e => {
            if (!e.touches || e.touches.length !== 1 || scroller.scrollHeight <= scroller.clientHeight) return;
            const delta = startY - e.touches[0].clientY;
            if (!dragging && Math.abs(delta) < 4) return;
            dragging = true;
            const max = Math.max(0, scroller.scrollHeight - scroller.clientHeight);
            const next = Math.max(0, Math.min(max, startTop + delta));
            if (next !== scroller.scrollTop) scroller.scrollTop = next;
            if (e.cancelable) e.preventDefault();
            e.stopPropagation();
        }, { passive: false });
    }
    _closeOverlayToCard() {
        this._dialogOpen = false; this._info = null; this._resetInfoNavigation();
        this._render(); this._restoreOverlayViewport();
    }
    _feedbackClientContext() {
        const ua = navigator.userAgent || ""; const platform = navigator.platform || "";
        const android = /Android/i.test(ua); const ipad = /iPad/i.test(ua) || (/MacIntel/.test(platform) && navigator.maxTouchPoints > 1); const ios = !android && (/iPhone|iPod/i.test(ua) || ipad);
        const deviceClass = ipad ? "tablet" : (/Mobile|Android|iPhone|iPod/i.test(ua) ? "phone" : "desktop");
        return { platform_family: android ? "Android" : (ipad ? "iPadOS" : (ios ? "iOS" : "Web")), device_class: deviceClass, companion_app: /Home Assistant/i.test(ua), browser_family: /wv|WebView|Home Assistant/i.test(ua) ? "Home Assistant WebView" : "Browser", viewport_css_px: { width: window.innerWidth, height: window.innerHeight }, device_pixel_ratio: window.devicePixelRatio || 1 };
    }
    _ensureStaticStyle() {
        if (!this.shadowRoot) return null;
        let style = this.shadowRoot.getElementById("faiq-static-style");
        if (!style) {
            style = document.createElement("style");
            style.id = "faiq-static-style";
            style.textContent = FAIQ_CARD_CSS;
            this.shadowRoot.prepend(style);
        }
        return style;
    }
    _replaceRenderedContent(html) {
        const style = this._ensureStaticStyle();
        if (!style || !this.shadowRoot) return;
        let node = style.nextSibling;
        while (node) {
            const next = node.nextSibling;
            this.shadowRoot.removeChild(node);
            node = next;
        }
        const template = document.createElement("template");
        template.innerHTML = html;
        this.shadowRoot.appendChild(template.content);
    }
    disconnectedCallback() { if (this._postResultTimer) clearTimeout(this._postResultTimer); this._postResultTimer = null; this._cancelQueuedRender(); this._cancelQueuedLiveRefresh(); }
    _fieldTestClientId() {
        const storageKey = "freshairiq.field_test.client_id";
        try {
            let value = window.localStorage.getItem(storageKey);
            if (!value || !value.startsWith("faiq-client-")) {
                const token = (window.crypto && typeof window.crypto.randomUUID === "function")
                    ? window.crypto.randomUUID().replaceAll("-", "")
                    : `${Date.now().toString(36)}${Math.random().toString(36).slice(2, 18)}`;
                value = `faiq-client-${token}`;
                window.localStorage.setItem(storageKey, value);
            }
            return { id: value, persistence: "localStorage" };
        }
        catch (_) {
            if (!this._fieldTestSessionClientId) {
                const token = (window.crypto && typeof window.crypto.randomUUID === "function")
                    ? window.crypto.randomUUID().replaceAll("-", "")
                    : `${Date.now().toString(36)}${Math.random().toString(36).slice(2, 18)}`;
                this._fieldTestSessionClientId = `faiq-client-session-${token}`;
            }
            return { id: this._fieldTestSessionClientId, persistence: "session" };
        }
    }
    _fieldTestClientContext() {
        const nav = window.navigator || {};
        const ua = String(nav.userAgent || "");
        const rawPlatform = String((nav.userAgentData && nav.userAgentData.platform) || nav.platform || "");
        const touchPoints = Number(nav.maxTouchPoints || 0);
        const isIPad = /iPad/i.test(ua) || (/MacIntel/i.test(rawPlatform) && touchPoints > 1);
        const isIPhone = /iPhone|iPod/i.test(ua);
        const isAndroid = /Android/i.test(ua);
        let platformFamily = "Other", deviceClass = "other", deviceFamily = null, deviceModel = null, osVersion = null;
        if (isIPad) {
            platformFamily = "iPadOS"; deviceClass = "tablet"; deviceFamily = "iPad"; deviceModel = "iPad";
        } else if (isIPhone) {
            platformFamily = "iOS"; deviceClass = "phone"; deviceFamily = "iPhone"; deviceModel = "iPhone";
        } else if (isAndroid) {
            platformFamily = "Android";
            deviceClass = /Mobile/i.test(ua) ? "phone" : "tablet";
            deviceFamily = deviceClass === "phone" ? "Android phone" : "Android tablet";
            const androidDetails = ua.match(/\(Linux;\s*Android\s+[^;\)]+;\s*([^\)]+)\)/i);
            if (androidDetails && androidDetails[1]) {
                const segments = androidDetails[1].split(";").map(part => part.trim()).filter(Boolean);
                const candidate = segments.find(part =>
                    !/^wv$/i.test(part) &&
                    !/^[a-z]{2}[-_][A-Z]{2}$/i.test(part) &&
                    !/^Build\//i.test(part)
                );
                if (candidate && candidate !== "K") deviceModel = candidate.replace(/\s+Build\/.*$/i, "").trim() || null;
            }
        } else if (/Windows/i.test(ua) || /Win/i.test(rawPlatform)) {
            platformFamily = "Windows"; deviceClass = "desktop"; deviceFamily = "PC";
        } else if (/Macintosh|Mac OS X/i.test(ua) || /Mac/i.test(rawPlatform)) {
            platformFamily = "macOS"; deviceClass = "desktop"; deviceFamily = "Mac";
        } else if (/Linux/i.test(ua) || /Linux/i.test(rawPlatform)) {
            platformFamily = "Linux"; deviceClass = "desktop"; deviceFamily = "Linux PC";
        }
        if (platformFamily === "iOS" || platformFamily === "iPadOS") {
            const match = ua.match(/(?:CPU(?: iPhone)? OS|iPhone OS)\s+([0-9_]+)/i);
            if (match) osVersion = match[1].replaceAll("_", ".");
        } else if (platformFamily === "Android") {
            const match = ua.match(/Android\s+([0-9.]+)/i);
            if (match) osVersion = match[1];
        } else if (platformFamily === "Windows") {
            const match = ua.match(/Windows NT\s+([0-9.]+)/i);
            if (match) osVersion = match[1];
        } else if (platformFamily === "macOS") {
            const match = ua.match(/Mac OS X\s+([0-9_]+)/i);
            if (match) osVersion = match[1].replaceAll("_", ".");
        }
        const companionMatch = ua.match(/Home Assistant\/([^\s;(]+)/i);
        const companionApp = !!companionMatch;
        let browserFamily = companionApp ? "Home Assistant WebView" : "Other";
        let browserVersion = null;
        const browserPatterns = [
            ["Edge", /(?:Edg|EdgiOS|EdgA)\/([0-9.]+)/],
            ["Chrome", /(?:Chrome|CriOS)\/([0-9.]+)/],
            ["Firefox", /(?:Firefox|FxiOS)\/([0-9.]+)/],
            ["Safari", /Version\/([0-9.]+).*Safari\//],
        ];
        for (const [name, pattern] of browserPatterns) {
            const match = ua.match(pattern);
            if (match) { if (!companionApp) browserFamily = name; browserVersion = match[1]; break; }
        }
        const webkit = ua.match(/AppleWebKit\/([0-9.]+)/i);
        const chromium = ua.match(/(?:Chrome|CriOS)\/([0-9.]+)/i);
        const client = this._fieldTestClientId();
        return {
            client_id: client.id,
            client_id_persistence: client.persistence,
            platform_family: platformFamily,
            os_version: osVersion,
            device_class: deviceClass,
            device_family: deviceFamily,
            device_model: deviceModel,
            companion_app: companionApp,
            companion_app_version: companionMatch ? companionMatch[1] : null,
            browser_family: browserFamily,
            browser_version: browserVersion,
            webview_engine_version: chromium ? chromium[1] : (webkit ? webkit[1] : null),
            home_assistant_version_reported_by_frontend: this._hass && this._hass.config ? this._hass.config.version : null,
            freshairiq_frontend_version: FAIQ_VERSION,
            viewport_css_px: { width: Math.round(window.innerWidth || 0), height: Math.round(window.innerHeight || 0) },
            screen_css_px: { width: Math.round((window.screen && window.screen.width) || 0), height: Math.round((window.screen && window.screen.height) || 0) },
            device_pixel_ratio: Number(window.devicePixelRatio || 1),
            touch_points: touchPoints,
            standalone_display_mode: !!(window.matchMedia && window.matchMedia("(display-mode: standalone)").matches),
        };
    }
    async _registerFieldTestClient(force = false) {
        if (!this._hass || typeof this._hass.callApi !== "function") return null;
        if (this._fieldTestRegistrationPromise) return this._fieldTestRegistrationPromise;
        const lastKey = "freshairiq.field_test.client_last_sync";
        if (!force) {
            try {
                const last = Number(window.localStorage.getItem(lastKey) || 0);
                if (Number.isFinite(last) && Date.now() - last < 24 * 60 * 60 * 1000) return null;
            } catch (_) { /* session-only registration remains possible */ }
        }
        const context = this._fieldTestClientContext();
        this._fieldTestRegistrationPromise = this._hass.callApi("POST", "freshairiq/diagnostics", context)
            .then(result => {
                if (result && result.registered) {
                    try { window.localStorage.setItem(lastKey, String(Date.now())); } catch (_) { /* privacy/storage mode */ }
                }
                return result;
            })
            .catch(err => { console.debug("FreshAirIQ field-test client registration skipped", err); return null; })
            .finally(() => { this._fieldTestRegistrationPromise = null; });
        return this._fieldTestRegistrationPromise;
    }
    _cancelQueuedRender() {
        if (this._renderFrame == null) return;
        if (this._renderFrameIsRaf && typeof cancelAnimationFrame === "function") cancelAnimationFrame(this._renderFrame);
        else clearTimeout(this._renderFrame);
        this._renderFrame = null;
        this._renderFrameIsRaf = false;
    }
    _queueRender() {
        if (this._renderFrame != null) return;
        const run = () => { this._renderFrame = null; this._renderFrameIsRaf = false; this._render(); };
        if (typeof requestAnimationFrame === "function") {
            this._renderFrameIsRaf = true;
            this._renderFrame = requestAnimationFrame(run);
        } else {
            this._renderFrameIsRaf = false;
            this._renderFrame = setTimeout(run, 0);
        }
    }
    _cancelQueuedLiveRefresh() {
        if (this._liveRefreshFrame == null) return;
        if (this._liveRefreshFrameIsRaf && typeof cancelAnimationFrame === "function") cancelAnimationFrame(this._liveRefreshFrame);
        else clearTimeout(this._liveRefreshFrame);
        this._liveRefreshFrame = null;
        this._liveRefreshFrameIsRaf = false;
    }
    _queueLiveRefresh() {
        if (this._liveRefreshFrame != null) return;
        const run = () => {
            this._liveRefreshFrame = null;
            this._liveRefreshFrameIsRaf = false;
            this._refreshOpenViewsLive();
        };
        if (typeof requestAnimationFrame === "function") {
            this._liveRefreshFrameIsRaf = true;
            this._liveRefreshFrame = requestAnimationFrame(run);
        } else {
            this._liveRefreshFrameIsRaf = false;
            this._liveRefreshFrame = setTimeout(run, 0);
        }
    }
    _collectLiveViewData() {
        const entity = this._statusEntity();
        if (!entity) return null;
        this._ensureRelevantStateIds(entity);
        const st = Object.assign({}, entity.attributes || {});
        let rooms = Object.values(st.rooms || {}).filter(r => r && typeof r === "object");
        const byKey = new Map(rooms.map(r => [String(r.key || ""), r]));
        const activeEntryId = st.freshairiq_entry_id || null;
        const roomStateIds = this._roomEntityIds && this._roomEntityIds.size ? this._roomEntityIds : null;
        const roomStates = roomStateIds
            ? Array.from(roomStateIds, id => this._hass.states[id]).filter(Boolean)
            : Object.values((this._hass && this._hass.states) || {});
        for (const state of roomStates) {
            const attrs = (state && state.attributes) || {};
            const room = attrs.freshairiq_room_payload;
            if (!room || !["room_v1", "room_v2"].includes(attrs.freshairiq_transport)) continue;
            if (activeEntryId && (attrs.freshairiq_transport !== "room_v2" || attrs.freshairiq_entry_id !== activeEntryId)) continue;
            const key = String(room.key || attrs.freshairiq_room_key || "");
            if (!key) continue;
            byKey.set(key, Object.assign({}, byKey.get(key) || {}, room));
        }
        rooms = Array.from(byKey.values()).filter(r => r && r.key);
        if (rooms.length && !Number(st.total_water_ml)) {
            st.total_water_ml = rooms
                .filter(r => r.calculation_enabled !== false && r.data_quality === "ok")
                .reduce((sum, r) => sum + Number(r.water_in_air_ml || 0), 0);
        }
        rooms = this._orderedRooms(rooms);
        return { st, rooms };
    }
    _liveNodesCompatible(current, fresh) {
        if (!current || !fresh || current.nodeType !== fresh.nodeType) return false;
        if (current.nodeType !== 1) return true;
        return current.tagName === fresh.tagName;
    }
    _patchLiveNode(current, fresh) {
        if (!this._liveNodesCompatible(current, fresh)) return;
        if (current.nodeType === 1) {
            const tag = String(current.tagName || "").toUpperCase();
            const isUnsavedRoomControl = ["INPUT", "SELECT", "TEXTAREA"].includes(tag) &&
                current.closest && current.closest(".room-form");
            // A room editor is a draft until the user presses “Raum speichern”.
            // Live HA state refreshes must never restore another select to the
            // last persisted value while the user is configuring its pair.
            if (isUnsavedRoomControl) return;
        }
        if (current.nodeType === 3) {
            if (current.nodeValue !== fresh.nodeValue) current.nodeValue = fresh.nodeValue;
            return;
        }
        if (current.nodeType !== 1) return;
        const active = current.getRootNode && current.getRootNode().activeElement === current;
        for (const attr of Array.prototype.slice.call(current.attributes || [])) {
            if (!fresh.hasAttribute(attr.name)) current.removeAttribute(attr.name);
        }
        for (const attr of Array.prototype.slice.call(fresh.attributes || [])) {
            if (current.getAttribute(attr.name) !== attr.value) current.setAttribute(attr.name, attr.value);
        }
        if (!active) {
            const tag = String(current.tagName || "").toUpperCase();
            if (tag === "INPUT") {
                if (current.type === "checkbox" || current.type === "radio") current.checked = fresh.checked;
                else if (current.value !== fresh.value) current.value = fresh.value;
            } else if (tag === "TEXTAREA" || tag === "SELECT") {
                if (current.value !== fresh.value) current.value = fresh.value;
            }
        }
        const currentChildren = Array.prototype.slice.call(current.childNodes || []);
        const freshChildren = Array.prototype.slice.call(fresh.childNodes || []);
        const sameShape = currentChildren.length === freshChildren.length && currentChildren.every((child, index) => this._liveNodesCompatible(child, freshChildren[index]));
        if (sameShape) {
            currentChildren.forEach((child, index) => this._patchLiveNode(child, freshChildren[index]));
            return;
        }
        const interactiveSelector = 'button,a,input,select,textarea,[data-info],[data-room],[data-settings-category],[data-settings-section],[data-settings-action],[data-profile],[data-forecast],[data-guest-kind]';
        const containsInteraction = current.matches(interactiveSelector) || !!current.querySelector(interactiveSelector);
        if (!containsInteraction) {
            current.innerHTML = fresh.innerHTML;
            return;
        }
        const count = Math.min(currentChildren.length, freshChildren.length);
        for (let i = 0; i < count; i++) {
            if (this._liveNodesCompatible(currentChildren[i], freshChildren[i])) this._patchLiveNode(currentChildren[i], freshChildren[i]);
        }
    }
    _liveViewStateSnapshot(key) {
        const ids = Array.from(this._relevantStateIds || []).sort();
        const refs = ids.map(id => (this._hass && this._hass.states ? this._hass.states[id] || null : null));
        const previous = this._liveViewSnapshot;
        const unchanged = !!previous && previous.key === key && previous.ids.length === ids.length &&
            ids.every((id, index) => id === previous.ids[index] && refs[index] === previous.refs[index]);
        this._liveViewSnapshot = { key, ids, refs };
        return unchanged;
    }
    _freshLiveNode(cacheKey, html, selector) {
        if (this._liveHtmlCache[cacheKey] === html) return null;
        this._liveHtmlCache[cacheKey] = html;
        const template = document.createElement("template");
        template.innerHTML = html;
        return template.content.querySelector(selector);
    }
    _refreshOpenViewsLive() {
        if (!this.shadowRoot || (!this._dialogOpen && !this._info)) return;
        const data = this._collectLiveViewData();
        if (!data) return;
        const viewKey = `${this._dialogOpen ? "dialog" : ""}|${this._info || ""}`;
        if (this._liveViewStateSnapshot(viewKey)) {
            this._roomViewUpdatePending = false;
            return;
        }
        const { st, rooms } = data;
        if (this._dialogOpen) {
            const current = this.shadowRoot.querySelector(".modal");
            const html = this._details(st, rooms);
            const fresh = current ? this._freshLiveNode("dialog", html, ".modal") : null;
            if (fresh) this._patchLiveNode(current, fresh);
        }
        if (this._info) {
            const current = this.shadowRoot.querySelector(".subdialog");
            const html = `<div class="subdialog">${this._infoNav()}${this._infoPanel(st, rooms)}${this._info === "profile" ? this._profileControls(st) : ""}${this._info === "next5" ? this._forecastControls(st) : ""}${this._info === "guests" ? this._guestControls(st) : ""}</div>`;
            const fresh = current ? this._freshLiveNode(`info:${this._info}`, html, ".subdialog") : null;
            if (fresh) this._patchLiveNode(current, fresh);
        }
        this._roomViewUpdatePending = false;
    }
    _relevantStateChanged(previous, next) {
        if (!previous || !next || !previous.states || !next.states) return true;
        if (!this._relevantStateIds || !this._relevantStateIds.size) return true;
        for (const id of this._relevantStateIds) {
            if (previous.states[id] !== next.states[id]) {
                const state = next.states[id];
                const a = (state && state.attributes) || {};
                if (id !== this._statusEntityId && (a.freshairiq_transport === "status_v2" || a.freshairiq_entity_key === "status"))
                    this._statusRescanNeeded = true;
                return true;
            }
        }
        return false;
    }
    _invalidateEntityCaches() { this._statusEntityId = null; this._statusRescanNeeded = false; this._relevantStateIds = null; this._roomEntityIds = null; this._roomConfigSignature = null; this._entityCache = {}; this._liveViewSnapshot = null; this._liveHtmlCache = {}; this._learningCardCache = null; }
    _ensureRelevantStateIds(status = null) {
        if (!this._hass) return;
        const current = status || this._statusEntity();
        const attrs = (current && current.attributes) || {};
        const rawRooms = attrs.rooms || {};
        const keys = (Array.isArray(rawRooms) ? rawRooms.map(r => String((r && r.key) || "")) : Object.keys(rawRooms)).filter(Boolean).sort();
        const signature = `${attrs.freshairiq_entry_id || ""}|${keys.join("|")}`;
        if (this._relevantStateIds && this._roomConfigSignature === signature) return;
        const entryId = attrs.freshairiq_entry_id || null;
        const ids = new Set();
        const roomIds = new Set();
        if (current && current.entity_id) ids.add(current.entity_id);
        if (this._config.entity) ids.add(this._config.entity);
        for (const state of Object.values(this._hass.states || {})) {
            if (!state || !state.entity_id) continue;
            const a = state.attributes || {};
            const sameEntry = !entryId || a.freshairiq_entry_id === entryId;
            const roomTransport = sameEntry && ["room_v1", "room_v2"].includes(a.freshairiq_transport);
            const taggedControl = sameEntry && !!a.freshairiq_entity_key;
            const legacyFresh = !entryId && String(state.entity_id).includes("freshairiq");
            if (roomTransport) roomIds.add(state.entity_id);
            if (roomTransport || taggedControl || legacyFresh) ids.add(state.entity_id);
        }
        this._relevantStateIds = ids;
        this._roomEntityIds = roomIds;
        this._roomConfigSignature = signature;
    }
    _freshAirIQStates(status = null) {
        if (!this._hass) return [];
        const current = status || this._statusEntity();
        this._ensureRelevantStateIds(current);
        if (!this._relevantStateIds || !this._relevantStateIds.size) return [];
        return Array.from(this._relevantStateIds, id => this._hass.states[id]).filter(Boolean);
    }
    setConfig(c) { this._config = normalizeDashboardConfig(c); this._invalidateEntityCaches(); this._render(); }
    set hass(h) {
        const previous = this._hass;
        this._hass = h;
        void this._registerFieldTestClient(false);
        const relevantChanged = this._relevantStateChanged(previous, h);
        // Home Assistant replaces the hass object for every state event. Most of
        // those events are unrelated to FreshAirIQ. Ignore them entirely instead
        // of rebuilding a large Shadow DOM. Relevant FreshAirIQ entities are
        // tracked by object identity, so genuine dashboard changes remain live.
        if (!relevantChanged) return;
        // Hotfix 0.20.1.2: every open FreshAirIQ window keeps its existing
        // scroll container and receives live value patches inside that DOM. This
        // keeps numbers/text/statuses current without recreating .modal/.subdialog
        // and therefore without resetting native iOS/Android WebView scrolling.
        if (this._info || this._dialogOpen) {
            this._queueLiveRefresh();
            return;
        }
        this._queueRender();
    }
    getCardSize() { return 5; }
    _statusEntity() {
        if (!this._hass)
            return null;
        const cached = this._statusEntityId ? this._hass.states[this._statusEntityId] : null;
        if (!this._statusRescanNeeded && cached && cached.attributes && cached.attributes.freshairiq_transport === "status_v2")
            return cached;
        const remember = state => { if (state && state.entity_id) this._statusEntityId = state.entity_id; this._statusRescanNeeded = false; return state; };
        const states = Object.values(this._hass.states);
        const isFreshAirIQ = s => {
            var _a;
            if (!((_a = s === null || s === void 0 ? void 0 : s.entity_id) === null || _a === void 0 ? void 0 : _a.startsWith("sensor.")))
                return false;
            const a = s.attributes || {};
            // Do not rely on the generated entity_id/friendly_name here. Home Assistant
            // can retain/rename registry entities after an update. The status sensor is
            // uniquely identifiable by FreshAirIQ's dashboard payload itself.
            const payloadSignature = (a.rooms != null &&
                (a.intelligent_recommendation != null || a.cross_ventilation != null ||
                    a.overnight_forecast_ml != null || a.ventilation_threshold_ml != null));
            return payloadSignature || s.entity_id.includes("freshairiq") ||
                String(a.friendly_name || "").toLowerCase().includes("freshairiq");
        };
        const roomCount = s => {
            var _a;
            const rooms = (_a = s === null || s === void 0 ? void 0 : s.attributes) === null || _a === void 0 ? void 0 : _a.rooms;
            return Array.isArray(rooms) ? rooms.length : (rooms && typeof rooms === "object" ? Object.keys(rooms).length : 0);
        };
        const hasDashboardPayload = s => {
            const a = (s === null || s === void 0 ? void 0 : s.attributes) || {};
            return roomCount(s) > 0 || a.total_water_ml != null || a.intelligent_recommendation != null || a.history_summary != null;
        };
        const usefulScore = s => {
            const a = s.attributes || {};
            let score = 0;
            // Current transport/version identity outranks payload size. This prevents
            // a stale registry entity with more historic rooms from winning.
            if (a.freshairiq_transport === "status_v2")
                score += 1000000;
            if (String(a.freshairiq_version || a.version || "") === FAIQ_VERSION)
                score += 500000;
            if (a.freshairiq_entry_id)
                score += 100000;
            if (a.total_water_ml != null)
                score += 5000;
            if (a.intelligent_recommendation != null)
                score += 2500;
            if (a.history_summary != null)
                score += 1000;
            if (a.status != null)
                score += 500;
            score += Math.min(roomCount(s), 100);
            if (s.entity_id === "sensor.freshairiq_status")
                score += 1;
            return score;
        };
        // A Home Assistant entity registry can retain an older sensor.freshairiq_status
        // while the current integration receives a suffixed entity id. Always select
        // the FreshAirIQ status sensor that actually carries the room/dashboard payload.
        const configured = this._config.entity && this._hass.states[this._config.entity];
        // If the card explicitly points at a current FreshAirIQ status_v2 entity,
        // that config-entry choice is authoritative. This also keeps multiple
        // FreshAirIQ instances separated.
        if (configured && configured.attributes &&
            configured.attributes.freshairiq_transport === "status_v2" &&
            hasDashboardPayload(configured))
            return remember(configured);
        const payloadCandidates = states.filter(s => isFreshAirIQ(s) && hasDashboardPayload(s));
        if (configured && hasDashboardPayload(configured))
            payloadCandidates.push(configured);
        if (payloadCandidates.length) {
            return remember([...new Set(payloadCandidates)].sort((a, b) => usefulScore(b) - usefulScore(a))[0]);
        }
        // During startup the current status sensor may exist before its attributes
        // arrive. Prefer the configured/canonical status entity only as a fallback.
        if (configured)
            return remember(configured);
        const canonical = this._hass.states["sensor.freshairiq_status"];
        if (canonical)
            return remember(canonical);
        return remember(states.find(s => {
            var _a;
            return isFreshAirIQ(s) &&
                (/(^|_)status(_\d+)?$/.test(s.entity_id.split(".")[1] || "") || /\bstatus\b/i.test(String(((_a = s.attributes) === null || _a === void 0 ? void 0 : _a.friendly_name) || "")));
        }) || null);
    }
    _num(id, f = 0) { var _a, _b, _c; const n = Number((_c = (_b = (_a = this._hass) === null || _a === void 0 ? void 0 : _a.states) === null || _b === void 0 ? void 0 : _b[id]) === null || _c === void 0 ? void 0 : _c.state); return Number.isFinite(n) ? n : f; }
    _profileEntity() {
        var _a;
        const cached = this._entityCache.profile && this._hass && this._hass.states[this._entityCache.profile];
        if (cached) return cached;
        const wanted = ["dehumidify", "comfort", "summer_cooling"];
        const status = this._statusEntity();
        const indexedStates = this._freshAirIQStates(status);
        const entryId = status && status.attributes ? status.attributes.freshairiq_entry_id : null;
        const tagged = indexedStates.find(s => {
            var _a;
            const a = (s === null || s === void 0 ? void 0 : s.attributes) || {};
            return ((_a = s === null || s === void 0 ? void 0 : s.entity_id) === null || _a === void 0 ? void 0 : _a.startsWith("select.")) &&
                a.freshairiq_entity_key === "operating_profile" &&
                (!entryId || a.freshairiq_entry_id === entryId);
        });
        if (tagged) { this._entityCache.profile = tagged.entity_id; return tagged; }
        // Backward-compatible fallback for installations that have not yet exposed
        // the identity attributes. Restrict it to FreshAirIQ-named entities.
        const legacyStates = Object.values((this._hass && this._hass.states) || {});
        const fallback = legacyStates.find(s => {
            var _a, _b;
            if (!((_a = s === null || s === void 0 ? void 0 : s.entity_id) === null || _a === void 0 ? void 0 : _a.startsWith("select.")))
                return false;
            const a = s.attributes || {};
            const opts = Array.isArray((_b = s.attributes) === null || _b === void 0 ? void 0 : _b.options) ? s.attributes.options : [];
            const name = `${s.entity_id} ${String(a.friendly_name || "")}`.toLowerCase();
            return name.includes("freshairiq") && wanted.every(v => opts.includes(v));
        }) || null;
        if (fallback) this._entityCache.profile = fallback.entity_id;
        return fallback;
    }
    _forecastEntity() {
        var _a;
        const cached = this._entityCache.forecast && this._hass && this._hass.states[this._entityCache.forecast];
        if (cached) return cached;
        const status = this._statusEntity();
        const indexedStates = this._freshAirIQStates(status);
        const entryId = status && status.attributes ? status.attributes.freshairiq_entry_id : null;
        const tagged = indexedStates.find(s => {
            var _a;
            const a = (s === null || s === void 0 ? void 0 : s.attributes) || {};
            return ((_a = s === null || s === void 0 ? void 0 : s.entity_id) === null || _a === void 0 ? void 0 : _a.startsWith("number.")) &&
                a.freshairiq_entity_key === "forecast_horizon_min" &&
                (!entryId || a.freshairiq_entry_id === entryId);
        });
        if (tagged) { this._entityCache.forecast = tagged.entity_id; return tagged; }
        // Backward-compatible fallback: never bind a generic 1..120 minute helper.
        const legacyStates = Object.values((this._hass && this._hass.states) || {});
        const fallback = legacyStates.find(s => {
            var _a;
            if (!((_a = s === null || s === void 0 ? void 0 : s.entity_id) === null || _a === void 0 ? void 0 : _a.startsWith("number.")))
                return false;
            const a = s.attributes || {};
            const name = `${s.entity_id} ${String(a.friendly_name || "")}`.toLowerCase();
            return name.includes("freshairiq") && (name.includes("prognosezeitraum") || name.includes("forecast_horizon"));
        }) || null;
        if (fallback) this._entityCache.forecast = fallback.entity_id;
        return fallback;
    }
    _guestEntity(kind) {
        const key = kind === "child" ? "guest_children" : "guest_adults";
        const cacheKey = `guest:${key}`;
        const cachedId = this._entityCache[cacheKey];
        const cached = cachedId && this._hass && this._hass.states[cachedId];
        if (cached) return cached;
        const status = this._statusEntity();
        const indexedStates = this._freshAirIQStates(status);
        const entryId = status && status.attributes ? status.attributes.freshairiq_entry_id : null;
        const tagged = indexedStates.find(state => {
            const a = (state && state.attributes) || {};
            return state && String(state.entity_id || "").startsWith("number.") &&
                a.freshairiq_entity_key === key &&
                (!entryId || a.freshairiq_entry_id === entryId);
        });
        if (tagged) { this._entityCache[cacheKey] = tagged.entity_id; return tagged; }
        // Legacy fallback only. New versions use the stable entity metadata above,
        // so renaming an entity in Home Assistant cannot break guest controls.
        const needle = kind === "child" ? "übernachtungsgäste kinder" : "übernachtungsgäste erwachsene";
        const legacyStates = Object.values((this._hass && this._hass.states) || {});
        const fallback = legacyStates.find(state => {
            const a = (state && state.attributes) || {};
            const name = `${state && state.entity_id || ""} ${String(a.friendly_name || "")}`.toLowerCase();
            return String(state && state.entity_id || "").startsWith("number.") &&
                name.includes("freshairiq") && name.includes(needle);
        }) || null;
        if (fallback) this._entityCache[cacheKey] = fallback.entity_id;
        return fallback;
    }
    _profileValue(st) { var _a; const actual = String(((_a = this._profileEntity()) === null || _a === void 0 ? void 0 : _a.state) || st.operating_profile || "comfort"); if (this._profileOverride != null) { if (actual === this._profileOverride) this._profileOverride = null; else return this._profileOverride; } return actual; }
    _forecastValue(st) { var _a; const n = Number((_a = this._forecastEntity()) === null || _a === void 0 ? void 0 : _a.state); const actual = Number.isFinite(n) ? n : Number(st.forecast_horizon_min || 5); if (this._forecastOverride != null) { if (Math.round(actual) === Math.round(this._forecastOverride)) this._forecastOverride = null; else return this._forecastOverride; } return actual; }
    _svgBars(history) {
        const rows = Array.isArray(history) ? history : [];
        if (!rows.length) return "";
        const cache = this._chartCache && this._chartCache.bars;
        if (cache && cache.has(rows)) return cache.get(rows);
        const signedValues = rows.map(r => Number((r.water_ml ?? r.removed_ml) ?? 0));
        const vals = signedValues.map(v => Math.abs(v));
        const max = Math.max(...vals, 1), w = 560, h = 112, g = 3, b = (w - g * (vals.length - 1)) / vals.length;
        const html = `<svg viewBox="0 0 ${w} ${h}" preserveAspectRatio="none">${vals.map((v, i) => { const bh = Math.max(2, (v / max) * 86), x = i * (b + g), y = 98 - bh, fill = signedValues[i] < 0 ? "#ff7770" : "#67df92"; return `<rect x="${x.toFixed(1)}" y="${y.toFixed(1)}" width="${b.toFixed(1)}" height="${bh.toFixed(1)}" rx="3" fill="${fill}" opacity="${v ? 0.9 : .18}"/>`; }).join("")}</svg>`;
        if (cache) cache.set(rows, html);
        return html;
    }
    _svgLine(points) {
        const rows = Array.isArray(points) ? points : [];
        if (!rows.length) return "";
        const cache = this._chartCache && this._chartCache.line;
        if (cache && cache.has(rows)) return cache.get(rows);
        const vals = rows.map(r => Number(r.temperature_c)).filter(Number.isFinite);
        if (vals.length < 2) { if (cache) cache.set(rows, ""); return ""; }
        const min = Math.min(...vals), max = Math.max(...vals), span = Math.max(max - min, .5), w = 560, h = 112, p = 8;
        const path = vals.map((v, i) => `${i ? "L" : "M"}${(p + i / Math.max(vals.length - 1, 1) * (w - 2 * p)).toFixed(1)},${(h - p - (v - min) / span * (h - 2 * p)).toFixed(1)}`).join(" ");
        const html = `<svg viewBox="0 0 ${w} ${h}" preserveAspectRatio="none"><path d="${path}" fill="none" stroke="#61d6ff" stroke-width="3" stroke-linecap="round"/></svg>`;
        if (cache) cache.set(rows, html);
        return html;
    }
    _recentVentilation(st) {
        const last = st && st.last_ventilation ? st.last_ventilation : null;
        if (!last || !last.ended_at) return null;
        const ended = Date.parse(last.ended_at);
        if (!Number.isFinite(ended)) return null;
        const explicitUntil = Date.parse(last.display_until || "");
        const until = Number.isFinite(explicitUntil) ? explicitUntil : ended + 5 * 60 * 1000;
        const remainingMs = until - Date.now();
        return remainingMs > 0 ? Object.assign({}, last, { _remainingMs: remainingMs }) : null;
    }
    _ventilationResultRows(last, respectPreferences = false) {
        const rows = Array.isArray(last && last.room_results) ? last.room_results : [];
        if (!rows.length) {
            const names = Array.isArray(last && last.rooms) ? last.rooms : [];
            return names.map(name => `<div class="result-room"><div><b>${esc(name)}</b><span>Einzelergebnis aus älterem Datenformat nicht verfügbar</span></div></div>`).join("");
        }
        const prefs = respectPreferences ? this._config : {};
        const showMoisture = !respectPreferences || prefs.info_moisture !== false;
        const showTemperature = !respectPreferences || prefs.info_temperature !== false;
        const showTime = !respectPreferences || prefs.info_time !== false;
        const showForecast = !respectPreferences || prefs.info_forecast !== false;
        const showEnergy = !respectPreferences || prefs.info_energy !== false;
        return rows.map(r => {
            const moistureValid = r.moisture_result_complete !== false && r.removed_ml != null;
            const m = moistureValid ? moisture(r.removed_ml, "±0 ml") : { text: "Messwert nicht belastbar", color: "#9aa7b3", kind: "unknown" };
            const meta = [];
            if (showTime) meta.push(`${fmt(r.duration_min || 0, 1)} min`);
            if (showTemperature) meta.push(r.temp_delta_c == null ? "Temperatur –" : signed(r.temp_delta_c, "°C"));
            if (showEnergy) meta.push(`${fmt(r.cost || 0, 2)} €`);
            const roomPrediction = r.aligned_predicted_removed_ml != null ? r.aligned_predicted_removed_ml : r.predicted_removed_ml;
            if (showForecast && roomPrediction != null) meta.push(`Startprognose ${moisture(roomPrediction, "±0 ml").text}`);
            const attrs = r.key ? ` class="result-room clickable" data-room="${esc(r.key)}"` : ` class="result-room"`;
            return `<div${attrs}><div><b>${esc(r.name || r.key || "Raum")}</b>${meta.length ? `<span>${meta.join(" · ")}</span>` : ""}</div>${showMoisture ? `<strong style="color:${m.color}">${m.text}</strong>` : ""}</div>`;
        }).join("");
    }
    _lastVentilationTile(last) {
        if (!last)
            return `<section class="last-vent-tile clickable" data-info="lastvent"><div class="last-vent-tile-icon"><ha-icon icon="mdi:history"></ha-icon></div><div><div class="tiny">LETZTE LÜFTUNG</div><b>Noch keine abgeschlossene Lüftung</b><span>Sobald eine Lüftung abgeschlossen ist, bleibt ihr Ergebnis hier abrufbar.</span></div><ha-icon class="last-vent-tile-chevron" icon="mdi:chevron-right"></ha-icon></section>`;
        const moistureValid = last.moisture_result_complete !== false && last.removed_ml != null;
        const m = moistureValid ? moisture(last.removed_ml, "±0 ml") : { text: "Feuchte nicht belastbar", color: "#9aa7b3", kind: "unknown" };
        return `<section class="last-vent-tile clickable" data-info="lastvent" style="--result:${m.color}"><div class="last-vent-tile-icon"><ha-icon icon="mdi:history"></ha-icon></div><div><div class="tiny">LETZTE LÜFTUNG</div><b>${m.text} · ${fmt(last.duration_min || 0, 1)} min</b><span>${esc(whenDE(last.ended_at))} · vollständiges Ergebnis öffnen</span></div><ha-icon class="last-vent-tile-chevron" icon="mdi:chevron-right"></ha-icon></section>`;
    }
    _ventilationResultCard(last, variant = "detail") {
        if (!last) return `<div class="last-vent"><div><div class="tiny">LETZTE LÜFTUNG</div><b>Noch keine abgeschlossene Lüftung</b></div></div>`;
        const moistureValid = last.moisture_result_complete !== false && last.removed_ml != null;
        const m = moistureValid ? moisture(last.removed_ml, "±0 ml") : { text: "nicht belastbar", color: "#9aa7b3", kind: "unknown" };
        const hero = variant === "hero";
        const respectPreferences = hero;
        const showMoisture = !respectPreferences || this._config.info_moisture !== false;
        const showTemperature = !respectPreferences || this._config.info_temperature !== false;
        const showTime = !respectPreferences || this._config.info_time !== false;
        const showForecast = !respectPreferences || this._config.info_forecast !== false;
        const showEnergy = !respectPreferences || this._config.info_energy !== false;
        const showCrossVentilation = !respectPreferences || this._config.info_cross_ventilation !== false;
        const alignmentQuality = String(last.prediction_alignment_quality || "");
        const scoreValidated = alignmentQuality
            ? ["validated", "partial_validated", "legacy_validated"].includes(alignmentQuality)
            : last.prediction_accuracy_percent != null;
        const displayAccuracy = scoreValidated ? last.prediction_accuracy_percent : null;
        const displayPredicted = scoreValidated ? last.predicted_removed_ml : null;
        const displayMeasured = scoreValidated ? last.prediction_actual_removed_ml : null;
        const displayError = scoreValidated ? last.prediction_error_ml : null;
        const accuracy = displayAccuracy == null
            ? (last.prediction_status_text || "Für diese Lüftung konnte beim Start keine belastbar auswertbare Prognose eingefroren werden")
            : `Prognosegenauigkeit ${Math.round(Number(displayAccuracy))} % · Startprognose gegen Ergebnis bei gleicher Messdauer`;
        const predicted = displayPredicted == null ? "" : ` · beim Start vorhergesagt ${moisture(displayPredicted, "±0 ml").text}`;
        const predictionMeasured = displayMeasured == null ? null : moisture(displayMeasured, "±0 ml");
        const qualityBits = [];
        if (!moistureValid) qualityBits.push("Feuchteergebnis nicht in Lernen oder Feuchtestatistik übernommen · Sensorzeitstempel während der Lüftung nicht vollständig");
        if (showCrossVentilation && last.cross_ventilation) qualityBits.push("Querlüftung erkannt");
        if (Number(last.recommendation_followed_count || 0) > 0) qualityBits.push(`${Number(last.recommendation_followed_count)} Raumempfehlung(en) befolgt`);
        if (Number(last.learning_valid_count || 0) > 0) qualityBits.push(`${Number(last.learning_valid_count)} Lernmessung(en) verwertbar`);
        if (Number(last.moisture_source_contaminated_rooms || 0) > 0) qualityBits.push(`${Number(last.moisture_source_contaminated_rooms)} Raum/Räume mit aktiver Feuchtequelle`);
        if (Number(last.prediction_time_aligned_rooms || 0) > 0) qualityBits.push(`${Number(last.prediction_time_aligned_rooms)} Raum/Räume mit zeitgleichem Startvergleich`);
        if (alignmentQuality === "partial_validated") {
            qualityBits.push(`${Number(last.prediction_comparable_rooms || 0)} von ${Number(last.prediction_time_aligned_rooms || 0)} Raum/Räumen für Genauigkeitswertung verwertbar`);
            if (Number(last.prediction_excluded_rooms || 0) > 0) qualityBits.push(`${Number(last.prediction_excluded_rooms)} Raum/Räume wegen nicht ausreichend synchroner Messdaten ausgeschlossen`);
        } else if (Number(last.prediction_time_aligned_sessions || 0) > Number(last.prediction_comparable_sessions || 0)) qualityBits.push("Keine Genauigkeitswertung · Messdaten nicht streng genug synchronisiert");
        else if (Number(last.prediction_comparable_rooms || 0) > 0) qualityBits.push(`${Number(last.prediction_comparable_rooms)} Raum/Räume für Genauigkeitswertung verwertbar`);
        const remaining = hero && Number(last._remainingMs) > 0 ? `<span class="result-countdown">Ergebnis noch ${Math.max(1, Math.ceil(Number(last._remainingMs) / 60000))} min im Dashboard</span>` : "";
        const resultHeadline = showMoisture ? (!moistureValid ? "Lüftung beendet · Feuchteergebnis nicht belastbar" : m.kind === "removed" ? "Feuchtigkeit erfolgreich reduziert" : m.kind === "added" ? "Feuchtigkeit ist angestiegen" : "Lüftung ausgewertet") : "Lüftung ausgewertet";
        const metrics = [];
        if (showMoisture) metrics.push(`<div><span>FEUCHTE</span><b style="color:${m.color}">${m.text}</b>${!moistureValid ? `<small>nicht als Messwert gespeichert</small>` : ""}</div>`);
        if (showTime) metrics.push(`<div><span>DAUER</span><b>${fmt(last.duration_min || 0, 1)} min</b></div>`);
        if (showTemperature) metrics.push(`<div><span>TEMPERATUR</span><b>${last.temp_delta_c == null ? "–" : signed(last.temp_delta_c, "°C")}</b></div>`);
        if (showEnergy) metrics.push(`<div><span>WIEDERAUFHEIZEN</span><b>${fmt(last.cost || 0, 2)} €</b><small>${fmt(last.energy_kwh || 0, 2)} kWh</small></div>`);
        const learningFeedback = alignmentQuality === "informational"
            ? `<span class="result-learning-feedback">FreshAirIQ wartet bei zeitversetzt meldenden Sensoren auf einen belastbaren Messvergleich. Die Lern-Auswertung kann deshalb verzögert erscheinen. Dieser Vergleich wird wegen nicht ausreichend synchroner Messdaten nicht als Prognosegenauigkeit gewertet.${last.learning_feedback_text ? ` ${esc(last.learning_feedback_text)}` : ""}</span>`
            : alignmentQuality === "partial_validated"
                ? `<span class="result-learning-feedback">Die Genauigkeit wird ausschließlich aus den streng vergleichbaren Raummessungen berechnet. Asynchrone Räume bleiben sichtbar, beeinflussen diese Wertung aber nicht.${last.learning_feedback_text ? ` ${esc(last.learning_feedback_text)}` : ""}</span>`
                : (last.learning_feedback_text ? `<span class="result-learning-feedback">${esc(last.learning_feedback_text)}</span>` : "");
        const iqMoistureSummary = !moistureValid ? "Feuchtevergleich nicht belastbar" : (predictionMeasured ? `Vergleichsmessung ${predictionMeasured.text}` : `Gesamtergebnis ${m.text}`);
        const iqEvaluation = showForecast ? `<div class="result-iq"><ha-icon icon="mdi:brain"></ha-icon><div><div class="tiny">IQ-AUSWERTUNG</div><b>${esc(accuracy)}</b><span>${showMoisture ? iqMoistureSummary : "Ergebnis gemessen"}${predicted}${displayError == null ? "" : ` · Abweichung ${signed(displayError, "ml")}`}</span>${learningFeedback}${qualityBits.length ? `<span>${qualityBits.map(esc).join(" · ")}</span>` : ""}</div></div>` : "";
        const openAttr = hero ? ` data-info="lastvent"` : "";
        return `<section class="vent-result ${hero ? "vent-result-hero clickable" : "vent-result-panel"}"${openAttr} style="--result:${m.color}"><div class="result-head"><div class="result-icon"><ha-icon icon="mdi:check-circle-outline"></ha-icon></div><div><div class="tiny">${hero ? "LÜFTUNG ABGESCHLOSSEN" : "LETZTE LÜFTUNG"}</div><h3>${resultHeadline}</h3><span>${esc(whenDE(last.ended_at))} · ${Number(last.room_count || (last.rooms || []).length || 0)} Raum/Räume</span></div>${remaining}</div>${metrics.length ? `<div class="result-metrics">${metrics.join("")}</div>` : ""}${iqEvaluation}<div class="result-rooms">${this._ventilationResultRows(last, respectPreferences)}</div><div class="result-footer"><span>Vom Öffnen des ersten bis zum Schließen des letzten Lüftungsfensters zusammengefasst.</span>${hero ? `<b>Ergebnis öffnen ›</b>` : `<span class="result-complete">Vollständige Auswertung</span>`}</div></section>`;
    }
    _hero(st, rooms, live, potential) {
        const iq = st.intelligent_recommendation || {};
        const passiveOpenMonitor = String(iq.status || st.status || "") === "passive_open_monitor";
        const iqColor = passiveOpenMonitor ? "#63d2f7" : iq.severity === "good" ? "#62e889" : iq.severity === "warning" ? "#e2bd69" : iq.severity === "danger" ? "#ff7770" : "#8fa0ac";
        if (iq.title)
            return { color: iqColor, title: iq.title, sub: iq.instruction || iq.summary || "" };
        if (passiveOpenMonitor)
            return { color: "#63d2f7", title: "Daueröffnung wird überwacht", sub: "Fenster kann vorerst offen/gekippt bleiben" };
        const active = rooms.filter(r => r.active && r.calculation_enabled !== false), close = rooms.filter(r => r.action === "Close"), vent = rooms.filter(r => r.action === "Ventilate"), bad = rooms.filter(r => r.data_quality !== "ok" && r.calculation_enabled !== false);
        if (bad.length)
            return { color: "#ff7770", title: "Sensoren prüfen", sub: `${bad.length} Raum/Räume mit ungültigen Messwerten` };
        if (close.length)
            return { color: "#ffb45f", title: "Jetzt schließen", sub: close.map(r => r.name).join(", ") };
        if (active.length) {
            const m = moisture(live);
            return { color: m.color, title: "Lüftung läuft", sub: `${active.length} Raum/Räume aktiv · ${m.text}` };
        }
        if (st.status === "pollen_warning")
            return { color: "#ffb45f", title: "Pollen beachten", sub: `Index ${fmt(st.pollen_index, 1)} · Grenzwert ${fmt(st.pollen_limit, 1)}` };
        if (st.status === "cooling_recommended")
            return { color: "#63d2f7", title: "Sommerkühlung sinnvoll", sub: "Kühlere Außenluft kann genutzt werden" };
        if (st.status === "ventilate")
            return { color: "#62e889", title: "Jetzt lüften", sub: `Hausweit ${moisture(potential).text} möglich` };
        if (vent.length)
            return { color: "#62e889", title: "Raumweise lüften", sub: vent.map(r => r.name).join(", ") };
        const roomProblem = rooms.find(r => ["Do not ventilate", "Wait"].includes(r.action) && (r.recommendation_reasons || []).some(x => /Raumluftfeuchte|Oberflächenfeuchte|CO₂/.test(String(x))));
        if (roomProblem)
            return { color: roomProblem.action === "Do not ventilate" ? "#ff7770" : "#e2bd69", title: roomProblem.action === "Do not ventilate" ? "Feuchteproblem · noch nicht lüften" : "Feuchteproblem · abwarten", sub: roomProblem.name };
        const fallbackH = Math.max(1, Math.round(this._forecastValue(st) || 5));
        const incoming = Math.max(0, -Number(st.forecast_moisture_effect_ml || 0));
        if (incoming >= 1)
            return { color: "#ff7770", title: "Nicht lüften", sub: `Außenluft würde in ${fallbackH} min ca. +${Math.round(incoming)} ml Feuchtigkeit eintragen` };
        return { color: "#8fa0ac", title: "Alles okay", sub: statusTextDE(st.status_text) || "Fenster geschlossen lassen" };
    }
    _intelligentPanel(st, rooms = []) {
        let iq = st.intelligent_recommendation || {};
        const brain = iq.decision_brain || {};
        const state = st.iq_state || {};
        if (!brain.headline && !iq.title && rooms.length) {
            const calc = rooms.filter(r => r.calculation_enabled !== false);
            const active = calc.filter(r => r.active);
            const close = calc.filter(r => r.action === "Close");
            const vent = calc.filter(r => r.action === "Ventilate" || r.action === "Ventilate for cooling");
            if (close.length)
                iq = { kind: "close", severity: "warning", title: "Jetzt schließen", instruction: close.map(r => r.name).join(", ") };
            else if (active.length)
                iq = { kind: "continue", severity: "good", title: "Lüftung läuft", instruction: active.map(r => r.name).join(", ") };
            else if (vent.length)
                iq = { kind: "ventilate", severity: "good", title: "Jetzt lüften", instruction: vent.map(r => r.name).join(", ") };
        }
        const calcRooms = rooms.filter(r => r.calculation_enabled !== false);
        const active = calcRooms.filter(r => r.active);
        const finalizing = st.finalizing_measurements || {};
        const activelyVentilating = active.filter(r => !r.session_finalization_pending);
        if (finalizing.active && !activelyVentilating.length) {
            const roomNames = Array.isArray(finalizing.room_names) ? finalizing.room_names.filter(Boolean) : [];
            const remaining = Math.max(0, Math.ceil(Number(finalizing.wait_remaining_s || 0)));
            const roomText = roomNames.length ? roomNames.slice(0, 3).join(" + ") : `${Number(finalizing.room_count || 1)} Raum/Räume`;
            const waitText = remaining > 0 ? `Noch maximal ${remaining} s` : "Rückmeldung wird geprüft";
            return `<section class="decision-card ai-card" style="--decision:#63d2f7">
      <div class="decision-kicker"><span class="decision-dot"></span>ABSCHLUSSMESSUNG</div>
      <div class="decision-main">
        <div class="decision-icon"><ha-icon icon="mdi:progress-clock"></ha-icon></div>
        <div><h2>Warte kurz auf die Klimasensoren</h2><div class="decision-action">Fenster geschlossen · ${esc(roomText)}</div></div>
      </div>
      <p class="decision-summary">FreshAirIQ hat die Lüftung beendet und fordert jetzt noch einmal die bereits konfigurierten Temperatur- und Feuchtesensoren an. Erst danach wird das Ergebnis angezeigt.</p>
      <div class="decision-impacts context-impacts"><div class="decision-impact forecast"><span>STATUS</span><b>${esc(waitText)}</b><small>frische Abschlusswerte werden eingesammelt</small></div></div>
      <div class="iq-process"><div class="iq-process-head"><span class="iq-pulse"></span><b>IQ AKTIV</b><span>Abschlussauswertung</span></div><div class="iq-process-text">Kein Stillstand: FreshAirIQ wartet bewusst kurz auf eine aktuelle Sensor-Rückmeldung. Antwortet ein Batteriesensor nicht, endet die Gnadenfrist automatisch und die Messqualität wird aus den tatsächlich während der Lüftung beobachteten Meldungen bewertet.</div></div>
    </section>`;
        }
        const recentVentilation = active.length ? null : this._recentVentilation(st);
        if (recentVentilation) return this._ventilationResultCard(recentVentilation, "hero");
        const bad = calcRooms.filter(r => r.data_quality !== "ok");
        const mouldRooms = calcRooms.filter(r => ["Elevated", "High", "Very high"].includes(r.mould_level));
        const kind = String(iq.kind || "okay");
        const passiveOpenMonitor = String(iq.status || st.status || "") === "passive_open_monitor";
        const nightStrategy = st.night_strategy || brain.night_strategy || {};
        const nightPrimary = Boolean(iq.night_strategy_primary || brain.night_strategy_primary);
        const color = nightPrimary ? "#7ec8ff" : iq.severity === "danger" ? "#ff7770" : iq.severity === "warning" ? "#e2bd69" :
            ["ventilate", "continue"].includes(kind) ? "#62e889" : passiveOpenMonitor || kind === "prepare" ? "#63d2f7" : "#8fa0ac";
        const icon = nightPrimary ? (nightStrategy.action === "close" ? "mdi:weather-night-partly-cloudy" : "mdi:weather-night") :
            kind === "ventilate" ? "mdi:weather-windy" : kind === "continue" ? "mdi:weather-windy-variant" :
                kind === "close" ? "mdi:window-closed-variant" : kind === "sensor" ? "mdi:alert-circle-outline" :
                    kind === "wait" || kind === "pollen_wait" ? "mdi:clock-outline" : passiveOpenMonitor ? "mdi:window-open" : kind === "prepare" ? "mdi:weather-sunset-up" : "mdi:brain";
        const headline = brain.headline || iq.title || state.headline || "FreshAirIQ überwacht";
        const action = brain.action_line || iq.instruction || state.summary || "";
        const label = brain.decision_label || (passiveOpenMonitor ? "DAUER-/KIPPLÜFTUNG" : (["continue", "close"].includes(kind) ? "LIVE-OPTIMIERUNG" : "FRESHAIRIQ ENTSCHEIDUNG"));
        const summary = brain.summary || iq.summary || state.summary || "";
        const why = (brain.why || iq.reasons || state.explanation || []).filter(Boolean).slice(0, 4);
        const impact = brain.impact || {};
        const comparison = brain.comparison || {};
        const selected = (brain.selected_rooms || []).filter(Boolean);
        const forecastH = Math.max(1, Math.round(this._forecastValue(st) || 5));
        const forecastDataH = Math.max(1, Math.round(Number(st.forecast_horizon_min || 5)));
        const forecastPending = forecastH !== forecastDataH;
        const selectedRoomObjs = selected.length ? calcRooms.filter(r => selected.includes(r.name) || selected.includes(r.key)) : [];
        const idleForecastRooms = selectedRoomObjs.length ? selectedRoomObjs : calcRooms.filter(r => r.data_quality === "ok" && r.ventilation_candidate);
        const forecastRooms = active.length ? active : idleForecastRooms;
        const houseShortEffect = st.house_ventilation_mode && iq.house_next_5_min_moisture_effect_ml != null ? Number(iq.house_next_5_min_moisture_effect_ml) : null;
        const forecastEffect = active.length ? (forecastH === 5 && houseShortEffect != null ? houseShortEffect : Number(st.forecast_moisture_effect_ml || 0)) : forecastRooms.reduce((a, r) => a + Number(r.forecast_moisture_effect_ml || 0), 0);
        const forecastUncappedEffect = active.length ? Number(st.forecast_uncapped_moisture_effect_ml != null ? st.forecast_uncapped_moisture_effect_ml : forecastEffect) : forecastRooms.reduce((a, r) => a + Number(r.forecast_uncapped_moisture_effect_ml != null ? r.forecast_uncapped_moisture_effect_ml : r.forecast_moisture_effect_ml || 0), 0);
        const forecastTargetLimited = active.length ? Boolean(st.forecast_target_limited) : forecastRooms.some(r => Boolean(r.forecast_target_limited));
        const forecastLiveAdapted = active.length ? Boolean(st.forecast_live_adapted) : forecastRooms.some(r => Boolean(r.forecast_live_adapted));
        const forecastCost = active.length ? Number(st.forecast_cost || 0) : forecastRooms.reduce((a, r) => a + Number(r.forecast_cost || 0), 0);
        const forecastVolume = forecastRooms.reduce((a, r) => a + Number(r.volume_m3 || 0), 0);
        const forecastTemp = active.length ? Number(st.forecast_temperature_change_c || 0) : (forecastVolume > 0 ? forecastRooms.reduce((a, r) => a + Number(r.forecast_temperature_change_c || 0) * Number(r.volume_m3 || 0), 0) / forecastVolume : 0);
        const forecastConfidence = active.length ? Number(st.forecast_confidence || 0) : (forecastVolume > 0 ? forecastRooms.reduce((a, r) => a + Number(r.forecast_confidence || 0) * Number(r.volume_m3 || 0), 0) / forecastVolume : 0);
        const liveBalance = Number(st.live_balance_ml || 0);
        const potential = Number(st.potential_total_ml || 0);
        const night = Number(st.overnight_forecast_ml || 0);
        const remaining = Number(st.remaining_duration_min || 0);
        const currentTemp = Number(st.temperature_change_live_c || 0);
        const showMoisture = this._config.info_moisture !== false;
        const showTemperature = this._config.info_temperature !== false;
        const showTime = this._config.info_time !== false;
        const showForecast = this._config.info_forecast !== false;
        const showNight = this._config.info_night !== false;
        const showMould = this._config.info_mould !== false;
        const showEnergy = this._config.info_energy !== false;
        const showPollen = this._config.info_pollen !== false;
        const showCrossVentilation = this._config.info_cross_ventilation !== false;
        const contextCards = [];
        const forecastMeta = (includeConfidence = false) => {
            const parts = [];
            if (active.length && forecastLiveAdapted) parts.push("Live-Messverlauf berücksichtigt");
            if (active.length && forecastTargetLimited && Math.abs(forecastUncappedEffect - forecastEffect) >= 1) parts.push("am Feuchteziel begrenzt");
            if (showTemperature) parts.push(signed(forecastTemp, "°C"));
            if (showEnergy) parts.push(`${fmt(forecastCost, 2)} €`);
            if (active.length && forecastH > 5) {
                const optimum = Number(st.forecast_optimal_close_in_min);
                if (Number.isFinite(optimum) && optimum > 0 && optimum <= forecastH) parts.push(`optimal noch ca. ${Math.round(optimum)} min`);
                else if (st.forecast_optimal_close_in_min == null) parts.push(`Endpunkt > ${forecastH} min`);
            }
            if (includeConfidence) parts.push(`IQ ${Math.round(forecastConfidence)} %`);
            return parts.join(" · ") || "modellierte Wirkung";
        };
        if (active.length) {
            const m = moisture(liveBalance);
            if (showMoisture)
                contextCards.push(`<div class="decision-impact live clickable" data-info="moisture"><span>BISHER</span><b style="color:${m.color}">${m.text}</b><small>seit Lüftungsbeginn</small></div>`);
            if (showForecast) {
                if (forecastPending) {
                    contextCards.push(`<div class="decision-impact forecast clickable" data-info="next5"><span>WEITERE ${forecastH} MIN</span><b>Wird berechnet …</b><small>FreshAirIQ aktualisiert Feuchte, Temperatur und Kosten für den neuen Zeitraum.</small></div>`);
                } else {
                    const forecastDisplayEffect = forecastEffect;
                    const f = moisture(forecastDisplayEffect);
                    contextCards.push(`<div class="decision-impact forecast clickable" data-info="next5"><span>WEITERE ${forecastH} MIN</span><b style="color:${f.color}">${f.text}</b><small>${forecastMeta(false)}</small></div>`);
                }
            }
            if (showTemperature && Math.abs(currentTemp) >= .01)
                contextCards.push(`<div class="decision-impact clickable" data-info="temperature"><span>TEMPERATUR LIVE</span><b>${signed(currentTemp, "°C")}</b><small>seit Start</small></div>`);
            if (showTime && Number.isFinite(remaining)) {
                if (passiveOpenMonitor)
                    contextCards.push(`<div class="decision-impact clickable" data-info="time"><span>DAUERÖFFNUNG</span><b>wird überwacht</b><small>Temperatur & Feuchte werden laufend geprüft</small></div>`);
                else
                    contextCards.push(`<div class="decision-impact clickable" data-info="time"><span>IQ-ZEIT</span><b>${remaining > 0 ? `${Math.ceil(remaining)} min` : remaining < 0 ? `+${Math.ceil(Math.abs(remaining))} min` : "0 min"}</b><small>${remaining > 0 ? "bis Ziel" : remaining < 0 ? "über Ziel" : "Ziel erreicht"}</small></div>`);
            }
        }
        else {
            const p = moisture(potential);
            if (showMoisture)
                contextCards.push(`<div class="decision-impact clickable" data-info="moisture"><span>JETZT ENTFERNBAR</span><b style="color:${p.color}">${p.text}</b><small>Schwelle ${Math.round(Number(st.ventilation_threshold_ml || 0))} ml</small></div>`);
            // v0.20.4.2: Vor Lüftungsbeginn keine zeitgebundene Lüftungsprognose anzeigen.
            // Die Prognose bleibt intern vollständig berechnet und erscheint erst bei aktiver Lüftung
            // als "WEITERE <Horizont> MIN". So bleibt die Vorher-Ansicht eine reine Entscheidungshilfe.
            if (showMoisture)
                contextCards.push(`<div class="decision-impact clickable" data-info="water"><span>WASSER IN DER LUFT</span><b>${Math.round(Number(st.total_water_ml || 0))} ml</b><small>${calcRooms.length} berechnete Räume</small></div>`);
            const nightWithoutRaw = nightStrategy.forecast_without_action_ml;
            const nightWithRaw = nightStrategy.forecast_with_strategy_ml;
            const nightWithout = Number(nightWithoutRaw);
            const nightWith = Number(nightWithRaw);
            const hasNightComparison = nightWithoutRaw !== null && nightWithoutRaw !== undefined && nightWithRaw !== null && nightWithRaw !== undefined && Number.isFinite(nightWithout) && Number.isFinite(nightWith);
            if (showNight && nightStrategy.active && hasNightComparison && Math.abs(nightWith - nightWithout) >= 1) {
                const nightBenefit = Math.round(nightWithout - nightWith);
                const strategyText = nightStrategy.action === "open_selected" ? "kontrolliert über Nacht lüften" : nightStrategy.action === "pre_ventilate" ? "vor dem Schlafengehen kurz lüften, dann schließen" : "empfohlenen Fensterzustand nutzen";
                const benefitText = nightBenefit >= 10 ? `Mit der Empfehlung erwartet FreshAirIQ morgen rund ${nightBenefit} ml weniger Feuchte.` : nightBenefit > 0 ? `Die Empfehlung bringt voraussichtlich nur einen kleinen Vorteil von rund ${nightBenefit} ml.` : `Für diese Nacht ist kein messbarer Feuchtevorteil durch zusätzliches Lüften zu erwarten.`;
                contextCards.push(`<div class="decision-impact night-context night-comparison clickable" data-info="night"><span>WAS BRINGT LÜFTEN VOR DEM SCHLAFEN?</span><div class="night-comparison-grid"><div class="night-comparison-side"><span>OHNE ZUSÄTZLICHES LÜFTEN</span><b>${nightWithout >= 0 ? "+" : ""}${Math.round(nightWithout)} ml</b><small>bis morgen früh</small></div><div class="night-comparison-arrow">→</div><div class="night-comparison-side"><span>MIT EMPFEHLUNG</span><b>${nightWith >= 0 ? "+" : ""}${Math.round(nightWith)} ml</b><small>${esc(strategyText)}</small></div></div><div class="night-comparison-benefit">${esc(benefitText)}</div></div>`);
            }
            else if (showNight && Number.isFinite(night)) {
                contextCards.push(`<div class="decision-impact clickable" data-info="night"><span>NACHTPROGNOSE</span><b>${night >= 0 ? "+" : ""}${Math.round(night)} ml</b><small>bis Nachtende · IQ ${Math.round(Number(st.overnight_confidence || 0))} %</small></div>`);
            }
            if (showMould)
                contextCards.push(`<div class="decision-impact clickable" data-info="mould"><span>SCHIMMEL</span><b>${mouldRooms.length ? `${mouldRooms.length} auffällig` : "unauffällig"}</b><small>max. ${Math.round(Number(st.max_surface_rh || 0))} % Oberflächen-RH</small></div>`);
        }
        if (showMoisture && !active.length && Number(impact.moisture_ml || 0) > 0 && Math.abs(Number(impact.moisture_ml) - Math.abs(forecastEffect)) > 1)
            contextCards.push(`<div class="decision-impact clickable" data-info="decision"><span>ENTSCHEIDUNGSWIRKUNG</span><b>−${Math.round(Number(impact.moisture_ml))} ml</b><small>${Number(impact.duration_min || 0) > 0 ? `${fmt(Number(impact.duration_min), 0)} min` : "bewertete Option"}</small></div>`);
        if (showNight && nightStrategy.active && !nightPrimary) {
            const delta = Number(nightStrategy.outside_minus_inside_ah_g_m3);
            const nightRooms = Array.isArray(nightStrategy.selected_rooms) ? nightStrategy.selected_rooms.filter(Boolean) : [];
            const nightAction = nightStrategy.action === "close" ? "geschlossen" : nightStrategy.action === "open_selected" ? (nightRooms.length ? `${nightRooms.join(" + ")} teilweise offen` : "teilweise offen") : nightStrategy.action === "pre_ventilate" ? (nightRooms.length ? `${nightRooms.join(" + ")} kurz vorlüften` : "vorher lüften") : "beobachten";
            contextCards.push(`<div class="decision-impact night-context clickable" data-info="night"><span>NACHTSTRATEGIE</span><b>${esc(nightAction)}</b><small>${Number.isFinite(delta) ? `${delta >= 0 ? "+" : ""}${fmt(delta, 1)} g/m³ außen` : "Wetter wird bewertet"} · IQ ${Math.round(Number(nightStrategy.confidence || 0))} %</small></div>`);
        }
        let compareHtml = "";
        if (showForecast && (Number(comparison.future_ml || 0) > 0 || Number(comparison.now_ml || 0) > 0)) {
            compareHtml = `<div class="decision-compare"><div><span>JETZT</span><b>${Math.round(Number(comparison.now_ml || 0))} ml</b></div><ha-icon icon="mdi:arrow-right"></ha-icon><div><span>${esc(comparison.alternative_label || "SPÄTER")}</span><b>${Math.round(Number(comparison.future_ml || 0))} ml</b></div></div>`;
        }

        const analysisBits = [];
        analysisBits.push(`${calcRooms.length} Räume`);
        if (showForecast && st.future_weather_available)
            analysisBits.push("Wetterprognose");
        if (showNight && nightStrategy.active)
            analysisBits.push("Nachtstrategie");
        if (showMoisture && showTemperature) analysisBits.push("Feuchte & Temperatur");
        else if (showMoisture) analysisBits.push("Feuchte");
        else if (showTemperature) analysisBits.push("Temperatur");
        if (showCrossVentilation && st.cross_ventilation)
            analysisBits.push("Querlüftung");
        if (showPollen && st.pollen_enabled)
            analysisBits.push("Pollen");
        if (Number(st.house_strategy_samples || 0) > 0)
            analysisBits.push("Lernmodell");
        const optionCount = Number(brain.short_term_options || 0) + Number(brain.long_term_options || 0);
        const learningActive = active.filter(r => r.session_measurement_quality?.timestamp_gate_passed === true);
        const learningWaiting = active.filter(r => r.session_measurement_quality?.timestamp_gate_passed !== true);
        const learningNames = learningActive.slice(0,2).map(r => r.name).join(" + ");
        const processText = passiveOpenMonitor
            ? `DAUER-/KIPPLÜFTUNG WIRD ÜBERWACHT: FreshAirIQ prüft Temperatur, Feuchtebilanz und Außenbedingungen fortlaufend und empfiehlt das Schließen, sobald die Daueröffnung ungünstig wird.`
            : active.length
            ? learningActive.length
                ? `LERNT JETZT: IQ lernt gerade den realen Luftaustausch${learningNames ? ` in ${learningNames}` : ""} · Feuchtewirkung · Temperaturreaktion · optimale Schließzeit · ${learningActive.length} verwertbare Messrahmen${learningWaiting.length ? ` · ${learningWaiting.length} Raum/Räume warten noch auf passende Sensordaten` : ""}`
                : `LÜFTUNG WIRD BEOBACHTET: FreshAirIQ sammelt aktuelle Temperatur- und Feuchtemeldungen · für eine Modellanpassung fehlen noch zeitlich passende Sensordaten`
            : bad.length
                ? `${bad.length} Datenquelle(n) prüfen · verbleibende Daten werden weiter bewertet`
                : showNight && nightStrategy.active
                    ? (() => {
                        const n0 = Number(nightStrategy.forecast_without_action_ml);
                        const n1 = Number(nightStrategy.forecast_with_strategy_ml);
                        const gain = Number.isFinite(n0) && Number.isFinite(n1) ? Math.round(n0 - n1) : 0;
                        if (gain > 0) return `FreshAirIQ erwartet mit der empfohlenen Nachtstrategie morgen früh etwa ${gain} ml weniger Feuchte. Wetter, Außenluft und deine gelernten Raumverläufe fließen in diesen Vergleich ein.`;
                        return `FreshAirIQ vergleicht die erwartete Nachtentwicklung mit und ohne Eingriff. Aktuell ergibt sich kein belastbarer zusätzlicher Feuchtegewinn durch eine andere Strategie.`;
                    })()
                    : `${analysisBits.join(" · ")} analysiert${optionCount ? ` · ${optionCount} Optionen bewertet` : ""}`;
        return `<section class="decision-card ai-card" style="--decision:${color}">
      <div class="decision-kicker"><span class="decision-dot"></span>${esc(label)}</div>
      <div class="decision-main">
        <div class="decision-icon"><ha-icon icon="${icon}"></ha-icon></div>
        <div><h2>${esc(headline)}</h2><div class="decision-action">${esc(action)}</div></div>
      </div>
      ${selected.length ? `<div class="decision-rooms">${selected.map(x => `<span>${esc(x)}</span>`).join("")}</div>` : ""}
      <p class="decision-summary">${esc(summary)}</p>
      ${contextCards.length ? `<div class="decision-impacts context-impacts">${contextCards.join("")}</div>` : ""}
      ${compareHtml}
      ${why.length ? `<div class="decision-why"><div class="decision-section-title">WARUM DIESE ENTSCHEIDUNG?</div>${why.map(x => `<div><ha-icon icon="mdi:check-circle-outline"></ha-icon><span>${esc(x)}</span></div>`).join("")}</div>` : ""}
      ${brain.alternative ? `<div class="decision-alternative"><b>Alternative:</b> ${esc(brain.alternative)}</div>` : ""}
      ${this._config.show_iq_process === false ? "" : `<div class="iq-process"><div class="iq-process-head"><span class="iq-pulse"></span><b>IQ AKTIV</b><span>${active.length && showForecast ? `Prognose ${forecastH} min · ` : ""}${Math.round(forecastConfidence || Number(impact.confidence || 0))} % Sicherheit</span></div><div class="iq-process-text">${esc(processText)}</div></div>`}
    </section>`;
    }
    _recommendationRows(rooms) {
        const important = rooms.filter(r => {
            if (r.calculation_enabled === false || r.data_quality !== "ok")
                return false;
            if (["Ventilate", "Continue ventilating", "Close", "Ventilate for cooling", "Check sensor"].includes(r.action))
                return true;
            if (["Do not ventilate", "Wait"].includes(r.action))
                return (r.recommendation_reasons || []).some(x => /Raumluftfeuchte|Oberflächenfeuchte|CO₂|Pollen/.test(String(x)));
            return false;
        });
        if (!important.length)
            return `<div class="recommendation-empty"><ha-icon icon="mdi:check-circle-outline"></ha-icon><div><b>Keine raumspezifische Maßnahme nötig</b><span>FreshAirIQ überwacht die Räume weiter. Die Hausschwelle entscheidet separat über eine allgemeine Lüftungsempfehlung.</span></div></div>`;
        return important.map(r => { const [accent, , icon] = styleFor(r.action); const reasons = (r.recommendation_reasons || []).filter(Boolean); return `<article class="recommendation-row clickable" data-room="${esc(r.key)}" style="--rec:${accent}"><div class="rec-icon"><ha-icon icon="${icon}"></ha-icon></div><div class="rec-body"><div class="rec-head"><b>${esc(r.name)}</b><strong>${esc(actionDE(r.action))}</strong></div><div class="rec-reasons">${reasons.map(x => `<span>${esc(x)}</span>`).join("") || `<span>${esc(reasonDE(r.reason))}</span>`}</div></div></article>`; }).join("");
    }
    _roomCard(r) {
        const [icon, accent, iconBg] = roomVisual(r);
        const [mouldColor, mouldBg] = mouldStyle(r.mould_level);
        const waterMl = Math.max(0, Number(r.water_in_air_ml || 0));
        const contactDirs = Object.values(r.contact_orientations || {}).map(orientationDE).filter(x => x !== "–");
        const dirText = contactDirs.length ? [...new Set(contactDirs)].join(" / ") : orientationDE(r.window_orientation);
        const samples = Number(r.learning_samples || 0);
        const structureOnly = r.calculation_enabled === false;
        const summary = structureOnly
            ? `<div class="room-summary-grid"><div class="room-stat" style="grid-column:1/-1"><ha-icon class="stat-icon" icon="mdi:home-floor-0"></ha-icon><div><div class="tiny">STRUKTURRAUM</div><div class="room-value">Keine Klimasensoren erforderlich</div><div class="muted">Wird für Gebäude, Etage, Volumen und Bewohnerzuordnung geführt – ohne erfundene Klimawerte.</div></div></div></div>`
            : `<div class="room-summary-grid"><div class="room-stat"><ha-icon class="stat-icon" icon="mdi:thermometer"></ha-icon><div><div class="tiny">RAUMKLIMA</div><div class="room-value">${fmt(r.temperature, 1)} °C · ${Math.round(Number(r.humidity || 0))} %</div><div class="muted">${fmt(r.absolute_humidity, 1)} g/m³ absolut</div></div></div><div class="room-stat mould-mini" style="border-color:${mouldColor}55;background:${mouldBg}"><ha-icon class="stat-icon" icon="mdi:shield-outline" style="color:${mouldColor}"></ha-icon><div><div class="tiny">SCHIMMELRISIKO</div><div class="room-value" style="color:${mouldColor}">${Math.round(Number(r.surface_rh || 0))} %</div><div class="muted" style="color:${mouldColor}">${esc(mouldDE(r.mould_level))}</div></div></div><div class="room-stat"><ha-icon class="stat-icon learning-bars" icon="mdi:chart-bar"></ha-icon><div><div class="tiny">LERNSTATUS</div><div class="room-value">${esc(learnDE(r.learning_status))}</div><div class="muted">${samples} ${samples === 1 ? "Probe" : "Proben"} · ${fmt(Number(r.learned_exchange_rate_per_min || 0) * 100, 1)} %/min</div></div></div></div>`;
        return `<article class="room clickable" data-room="${esc(r.key)}" style="--accent:${accent};--icon-bg:${iconBg}"><div class="room-head"><div class="room-icon"><ha-icon icon="${icon}"></ha-icon></div><div class="room-ident"><div class="room-title">${esc(r.name || r.key)}</div><div class="muted">${esc(floorDE(r.floor))} · ${fmt(r.volume_m3, 1)} m³ · Fenster ${esc(dirText)}${structureOnly ? " · nur Struktur" : ""}</div></div>${structureOnly ? "" : `<div class="room-water"><ha-icon icon="mdi:water"></ha-icon><strong>${Math.round(waterMl)} ml</strong></div>`}<ha-icon class="room-chevron" icon="mdi:chevron-right"></ha-icon></div>${summary}</article>`;
    }
    _infoBackButton() {
        return `<button class="info-back" id="info-back" aria-label="Zurück"><ha-icon icon="mdi:arrow-left"></ha-icon></button>`;
    }
    _infoNav() {
        const label = this._info && this._info.startsWith("settings") ? "FreshAirIQ Einstellungen" : "FreshAirIQ";
        return `<div class="info-nav" role="toolbar" aria-label="Fensternavigation">${this._infoBackButton()}<div class="info-nav-label">${esc(label)}</div><button class="info-close" id="info-close" aria-label="Schließen">×</button></div>`;
    }
    _settingsEntryId() {
        const s = this._statusEntity();
        return s && s.attributes ? s.attributes.freshairiq_entry_id : null;
    }
    async _loadSettings(force = false) {
        const entryId = this._settingsEntryId();
        if (!entryId) {
            this._settingsError = "Die FreshAirIQ-Konfiguration konnte nicht eindeutig zugeordnet werden.";
            this._settingsLoading = false;
            this._render();
            return;
        }
        if (this._settingsLoading || (this._settingsData && !force)) return;
        this._settingsLoading = true;
        this._settingsError = null;
        this._render();
        try {
            this._settingsData = await this._hass.callApi("GET", `freshairiq/settings/${entryId}`);
        } catch (err) {
            this._settingsError = (err && err.message) ? err.message : "Einstellungen konnten nicht geladen werden.";
        } finally {
            this._settingsLoading = false;
            this._render();
        }
    }
    async _settingsPost(payload, preserveViewport = false) {
        const entryId = this._settingsEntryId();
        if (!entryId) return false;
        const currentSubdialog = this.shadowRoot && this.shadowRoot.querySelector(".subdialog");
        if (currentSubdialog) this._subdialogScrollTop = currentSubdialog.scrollTop;
        this._settingsSaving = true;
        this._settingsNotice = "Wird gespeichert …";
        this._settingsError = null;
        // Ordinary form controls already show the user's new value. Do not rebuild
        // the complete settings DOM while saving: on iOS/Android that destroys the
        // focused control and snaps the modal to the top. Structural actions still
        // use the normal render path below.
        if (!preserveViewport) this._render();
        try {
            const result = await this._hass.callApi("POST", `freshairiq/settings/${entryId}`, payload);
            if (result && result.error) throw new Error(result.error);
            if (result && result.data) this._settingsData = result;
            this._invalidateEntityCaches();
            this._settingsNotice = "Gespeichert";
            if (!preserveViewport) {
                setTimeout(() => { if (this._settingsNotice === "Gespeichert") { this._settingsNotice = null; this._render(); } }, 1600);
            } else {
                setTimeout(() => { if (this._settingsNotice === "Gespeichert") this._settingsNotice = null; }, 1600);
            }
            return true;
        } catch (err) {
            this._settingsError = (err && err.message) ? err.message : "Einstellung konnte nicht gespeichert werden.";
            this._settingsNotice = null;
            // Errors are rare and must remain visible; the renderer restores the
            // remembered settings viewport instead of intentionally resetting it.
            this._render();
            return false;
        } finally {
            this._settingsSaving = false;
            if (!preserveViewport) this._render();
        }
    }
    _settingsDefaultText(key, explicit = undefined) {
        const raw = explicit !== undefined ? explicit : (this._settingsData && this._settingsData.defaults ? this._settingsData.defaults[key] : undefined);
        if (raw === undefined || raw === null || raw === "") return "nicht gesetzt";
        if (raw === true) return "ein";
        if (raw === false) return "aus";
        if (Array.isArray(raw)) return raw.length ? raw.join(", ") : "leer";
        return String(raw).replace(".", ",");
    }
    _settingsEntities(domains, selected = [], deviceClass = null) {
        const wanted = Array.isArray(domains) ? domains : [domains];
        const selectedSet = new Set(Array.isArray(selected) ? selected : [selected].filter(Boolean));
        const states = Object.values((this._hass && this._hass.states) || {});
        return states.filter(s => {
            const domain = String(s.entity_id || "").split(".")[0];
            if (!wanted.includes(domain)) return false;
            if (!deviceClass || domain !== "sensor") return true;
            const attrs = s.attributes || {};
            const dc = String(attrs.device_class || "");
            const unit = String(attrs.unit_of_measurement || "").trim().toLowerCase();
            const compatibleUnit =
                (deviceClass === "temperature" && ["°c","°f","c","f","k"].includes(unit)) ||
                (deviceClass === "humidity" && ["%","%rh","rh%"].includes(unit));
            return dc === deviceClass || compatibleUnit || selectedSet.has(s.entity_id);
        }).sort((a,b) => String((a.attributes||{}).friendly_name || a.entity_id).localeCompare(String((b.attributes||{}).friendly_name || b.entity_id), "de"));
    }
    _settingsOptions(options, value) {
        return options.map(opt => {
            const item = typeof opt === "string" ? { value: opt, label: opt } : opt;
            return `<option value="${esc(item.value)}" ${String(value) === String(item.value) ? "selected" : ""}>${esc(item.label)}</option>`;
        }).join("");
    }
    _settingsField({scope="option", key, label, description, type="number", unit="", options=[], domains=[], deviceClass=null, multiple=false, example="", defaultValue=undefined, min=null, max=null, step=null}) {
        const source = scope === "data" ? ((this._settingsData && this._settingsData.data) || {}) : ((this._settingsData && this._settingsData.options) || {});
        const value = source[key];
        let control = "";
        const attrs = `data-setting-control data-setting-scope="${esc(scope)}" data-setting-key="${esc(key)}" data-setting-type="${esc(type)}"`;
        if (type === "boolean") {
            control = `<label class="settings-switch"><input ${attrs} type="checkbox" ${value ? "checked" : ""}><span></span></label>`;
        } else if (type === "select") {
            control = `<select class="settings-input" ${attrs}>${this._settingsOptions(options, value)}</select>`;
        } else if (type === "entity") {
            const entities = this._settingsEntities(domains, value, deviceClass);
            control = `<select class="settings-input" ${attrs}><option value="">Nicht gesetzt</option>${entities.map(s => `<option value="${esc(s.entity_id)}" ${s.entity_id === value ? "selected" : ""}>${esc((s.attributes||{}).friendly_name || s.entity_id)} · ${esc(s.entity_id)}</option>`).join("")}</select>`;
        } else if (type === "multi-entity") {
            const current = Array.isArray(value) ? value : [];
            const entities = this._settingsEntities(domains, current, deviceClass);
            control = `<select class="settings-input settings-multi" ${attrs} multiple size="5">${entities.map(s => `<option value="${esc(s.entity_id)}" ${current.includes(s.entity_id) ? "selected" : ""}>${esc((s.attributes||{}).friendly_name || s.entity_id)} · ${esc(s.entity_id)}</option>`).join("")}</select>`;
        } else if (type === "multi-select") {
            const current = Array.isArray(value) ? value : [];
            control = `<select class="settings-input settings-multi" ${attrs} multiple size="5">${options.map(opt => { const item = typeof opt === "string" ? {value:opt,label:opt} : opt; return `<option value="${esc(item.value)}" ${current.includes(item.value) ? "selected" : ""}>${esc(item.label)}</option>`; }).join("")}</select>`;
        } else if (type === "textarea") {
            control = `<textarea class="settings-input settings-textarea" ${attrs} rows="4">${esc(value || "")}</textarea>`;
        } else {
            const inputType = type === "time" ? "time" : (type === "text" ? "text" : "number");
            control = `<div class="settings-input-wrap"><input class="settings-input" ${attrs} type="${inputType}" value="${esc(value !== undefined && value !== null ? value : "")}" ${min !== null ? `min="${min}"` : ""} ${max !== null ? `max="${max}"` : ""} ${step !== null ? `step="${step}"` : ""}>${unit ? `<span>${esc(unit)}</span>` : ""}</div>`;
        }
        return `<div class="settings-field"><div class="settings-field-copy"><b>${esc(label)}</b><span>${esc(description)}</span><small>Standard: ${esc(this._settingsDefaultText(key, defaultValue))}${example ? ` · Beispiel: ${esc(example)}` : ""}</small></div><div class="settings-control">${control}</div></div>`;
    }
    _settingsGroup(title, text, fields) {
        return `<section class="settings-group"><div class="settings-group-head"><div><div class="tiny">${esc(title)}</div><span>${esc(text)}</span></div></div>${fields.join("")}</section>`;
    }
    _orderedRooms(rawRooms) {
        const source = Array.isArray(rawRooms) ? rawRooms : Object.values(rawRooms || {});
        return source.filter(r => r && typeof r === "object").map((room, index) => ({ room, index })).sort((a, b) => {
            const av = Number(a.room.sort_order);
            const bv = Number(b.room.sort_order);
            const ao = Number.isFinite(av) ? av : 9999;
            const bo = Number.isFinite(bv) ? bv : 9999;
            return ao - bo || a.index - b.index || String(a.room.name || a.room.key || "").localeCompare(String(b.room.name || b.room.key || ""), "de");
        }).map(x => x.room);
    }
    _groupRoomsByFloor(rawRooms, renderRoom) {
        const ordered = this._orderedRooms(rawRooms);
        const groups = [];
        const byFloor = new Map();
        ordered.forEach(room => {
            const key = String(room.floor || "");
            if (!byFloor.has(key)) { const group = { key, rooms: [] }; byFloor.set(key, group); groups.push(group); }
            byFloor.get(key).rooms.push(room);
        });
        return groups.map(group => `<section class="floor-room-group"><div class="floor-room-heading"><ha-icon icon="mdi:layers-outline"></ha-icon><span>${esc(floorDE(group.key))}</span></div><div class="floor-room-content">${group.rooms.map(renderRoom).join("")}</div></section>`).join("");
    }
    _residentProfileMap() {
        const raw = (((this._settingsData || {}).options || {}).resident_room_profiles) || "{}";
        if (raw && typeof raw === "object" && !Array.isArray(raw)) return Object.assign({}, raw);
        try {
            const parsed = JSON.parse(String(raw || "{}"));
            return parsed && typeof parsed === "object" && !Array.isArray(parsed) ? parsed : {};
        } catch (_) { return {}; }
    }
    _residentProfilesEditor() {
        const d = (this._settingsData && this._settingsData.data) || {};
        const o = (this._settingsData && this._settingsData.options) || {};
        const rooms = this._orderedRooms(d.rooms || []);
        const profiles = this._residentProfileMap();
        const names = value => String(value || "").replace(/;/g, ",").split(",").map(x => x.trim()).filter(Boolean);
        const adults = names(o.adult_resident_names);
        const children = names(o.child_resident_names);
        const adultTrackers = Array.isArray(o.adult_presence_entities) ? o.adult_presence_entities : [];
        const childTrackers = Array.isArray(o.child_presence_entities) ? o.child_presence_entities : [];
        const residents = [];
        const pushRole = (role, label, count, roleNames, trackers) => {
            const total = Math.max(Number(count || 0), roleNames.length, trackers.length);
            for (let i=0; i<total; i++) residents.push({role, roleLabel:label, index:i, name:roleNames[i] || `${label} ${i+1}`, tracker:trackers[i] || ""});
        };
        pushRole("adult", "Erwachsener", o.adult_occupants, adults, adultTrackers);
        pushRole("child", "Kind", o.child_occupants, children, childTrackers);
        if (!residents.length) return `<div class="settings-empty">Lege zuerst Erwachsene oder Kinder unter „Bewohnerprofil & Anwesenheit“ an.</div>`;
        return `<div class="resident-profile-grid">${residents.map(r => {
            const slot = `${r.role}:${r.index}`;
            const profile = profiles[slot] || {};
            const selectedRooms = Array.isArray(profile.room_keys) ? profile.room_keys : [];
            const thermal = ["inherit","warm","balanced","cool"].includes(profile.thermal_preference) ? profile.thermal_preference : "inherit";
            const trackerLabel = r.tracker ? ` · ${r.tracker}` : " · ohne Tracker";
            const residentTargets = Array.isArray(profile.notification_targets) ? profile.notification_targets : [];
            const notifyOpts = ((this._settingsData && this._settingsData.notify_services) || []).map(x => ({value:x,label:`notify.${x}`}));
            return `<div class="resident-profile-card">
                <div class="resident-profile-glow"></div>
                <div class="resident-profile-badge"><ha-icon icon="mdi:creation"></ha-icon><span>PERSÖNLICHES IQ-PROFIL</span></div>
                <div class="resident-profile-head"><div class="resident-avatar"><ha-icon icon="${r.role === "child" ? "mdi:teddy-bear" : "mdi:account"}"></ha-icon></div><div><b>${esc(r.name)}</b><span>${esc(r.roleLabel + trackerLabel)}</span></div><ha-icon class="resident-profile-spark" icon="mdi:brain"></ha-icon></div>
                <label><span>Zugeordnete Räume</span><select class="settings-input settings-multi" data-resident-profile data-resident-slot="${esc(slot)}" data-resident-name="${esc(r.name)}" data-resident-field="room_keys" multiple size="${Math.min(6, Math.max(3, rooms.length))}">${rooms.map(room => `<option value="${esc(room.key)}" ${selectedRooms.includes(room.key)?"selected":""}>${esc(room.name || room.key)}</option>`).join("")}</select></label>
                <label><span>Temperaturempfinden</span><select class="settings-input" data-resident-profile data-resident-slot="${esc(slot)}" data-resident-name="${esc(r.name)}" data-resident-field="thermal_preference"><option value="inherit" ${thermal==="inherit"?"selected":""}>Haushaltsprofil übernehmen</option><option value="warm" ${thermal==="warm"?"selected":""}>Eher warm</option><option value="balanced" ${thermal==="balanced"?"selected":""}>Ausgewogen</option><option value="cool" ${thermal==="cool"?"selected":""}>Eher kühl</option></select></label>
                <label><span>Persönliche Endgeräte</span><select class="settings-input settings-multi" data-resident-profile data-resident-slot="${esc(slot)}" data-resident-name="${esc(r.name)}" data-resident-field="notification_targets" multiple size="4">${notifyOpts.map(opt => `<option value="${esc(opt.value)}" ${residentTargets.includes(opt.value)?"selected":""}>${esc(opt.label)}</option>`).join("")}</select><small>Diese Geräte erhalten Empfehlungen persönlich für ${esc(r.name)}.</small></label>
            </div>`;
        }).join("")}</div>`;
    }
    _settingsHome() {
        const cards=[["group_basics","mdi:home-outline","Grundlagen","Außenluft, Gebäude, Betriebsprofil und Prognose"],["group_residents","mdi:account-group-outline","Bewohner","Anwesenheit, Namen, Räume, Komfort und persönliche Endgeräte"],["group_rooms","mdi:floor-plan","Räume & Stockwerke","Hausstruktur, Raumgrößen, Sensoren, Kontakte und Luftwege"],["group_intelligence","mdi:brain","Lüftungslogik","Feuchte, Schimmel, Wind, Querlüftung und Lernmodell"],["notifications","mdi:bell-outline","Benachrichtigungen","Allgemeine Ziele, Ereignisse und Cooldown"],["group_data","mdi:chart-timeline-variant","Energie & Daten","Heizkosten, Statistik und Auswertung"],["feedback","mdi:message-alert-outline","Feedback & Fehler melden","Bug beschreiben oder Verbesserungsvorschlag direkt an den Diagnose-Hub senden"],["maintenance","mdi:wrench-cog-outline","Wartung","Lerndaten oder Einstellungen zurücksetzen"]];
        return `<section class="info-panel settings-panel"><div class="settings-hero"><div class="settings-hero-icon"><ha-icon icon="mdi:cog-outline"></ha-icon></div><div><div class="tiny">FRESHAIRIQ KONFIGURATION</div><h3>Einstellungen</h3><p>Die Konfiguration ist in wenige verständliche Bereiche gegliedert. Änderungen werden direkt gespeichert.</p></div></div><div class="settings-category-grid">${cards.map(([key,icon,title,text])=>`<button class="settings-category ${key === "group_residents" ? "resident-feature" : ""}" data-settings-section="${key}"><ha-icon icon="${icon}"></ha-icon><div>${key === "group_residents" ? `<small class="resident-feature-badge">PERSÖNLICHES IQ-PROFIL</small>` : ""}<b>${title}</b><span>${text}</span></div><ha-icon class="settings-chevron" icon="mdi:chevron-right"></ha-icon></button>`).join("")}</div></section>`;
    }
    _settingsGroupMenu(name) {
        const groups={group_basics:[["outdoor","mdi:weather-partly-cloudy","Außenluft & Wetter"],["building","mdi:home-city-outline","Gebäude"],["profile","mdi:tune-variant","Betriebsprofil"],["forecast","mdi:timeline-clock-outline","Prognose"]],group_residents:[["residents","mdi:account-heart-outline","Bewohnerprofil"]],group_rooms:[["levels","mdi:layers-triple-outline","Stockwerke & Bereiche"],["rooms","mdi:floor-plan","Räume & Sensoren"],["cross","mdi:swap-horizontal-bold","Luftwege & Querlüftung"]],group_intelligence:[["air","mdi:air-filter","Optionale Sensoren & Außenluft"],["model","mdi:brain","Lüftungsmodell"]],group_data:[["energy","mdi:lightning-bolt-outline","Energie & Kosten"],["statistics","mdi:chart-timeline-variant","Daten & Statistik"],["diagnostics_sharing","mdi:shield-cloud-outline","Diagnose-Freigabe"]]};
        const items=groups[name]||[]; const titles={group_basics:"Grundlagen",group_residents:"Bewohner",group_rooms:"Räume & Stockwerke",group_intelligence:"Lüftungslogik",group_data:"Energie & Daten"};
        return `<section class="info-panel settings-panel"><div class="tiny info-kicker">EINSTELLUNGEN</div><h3>${titles[name]||"Einstellungen"}</h3><div class="settings-category-grid">${items.map(([key,icon,title])=>`<button class="settings-category ${key === "residents" ? "resident-feature" : ""}" data-settings-section="${key}"><ha-icon icon="${icon}"></ha-icon><div>${key === "residents" ? `<small class="resident-feature-badge">PERSÖNLICHES IQ-PROFIL</small>` : ""}<b>${title}</b><span>${key === "residents" ? "Personen, Anwesenheit, Räume, Komfort und Endgeräte an einer Stelle" : "Öffnen und direkt bearbeiten"}</span></div><ha-icon class="settings-chevron" icon="mdi:chevron-right"></ha-icon></button>`).join("")}</div></section>`;
    }
    _settingsSection(name) {
        const o = (this._settingsData && this._settingsData.options) || {};
        const d = (this._settingsData && this._settingsData.data) || {};
        const select = (value,label) => ({value,label});
        if (name === "feedback") return `<section class="info-panel settings-panel"><div class="tiny info-kicker">FEEDBACK & FEHLER MELDEN</div><h3>Direkt an den Diagnose-Hub</h3><p>Dein Text wird zusammen mit technischen Metadaten wie FreshAirIQ-/Home-Assistant-Version und der anonymen Installations-ID an den konfigurierten Diagnose-Hub übertragen. Zugangsdaten werden nicht übertragen.</p><section class="settings-group"><div class="settings-group-head"><div><div class="tiny">MELDUNG</div><span>Beschreibe möglichst konkret, was passiert ist oder was verbessert werden sollte.</span></div></div><div class="settings-field settings-field-stack"><div class="settings-field-copy"><b>Art der Meldung</b></div><select id="feedback-type" class="settings-input"><option value="bug">Fehler / Bug</option><option value="improvement">Verbesserungsvorschlag</option><option value="other">Sonstiges</option></select></div><div class="settings-field settings-field-stack"><div class="settings-field-copy"><b>Beschreibung</b><span>3–10.000 Zeichen. Bitte keine Passwörter, Tokens, Adressen oder andere persönliche Geheimnisse eintragen.</span></div><textarea id="feedback-message" class="settings-input settings-textarea" rows="7" maxlength="10000" placeholder="Beispiel: Nach dem Schließen des Badezimmerfensters empfiehlt FreshAirIQ noch mehrere Minuten weiterzulüften."></textarea></div><div class="settings-room-actions"><button class="settings-save" id="feedback-send"><ha-icon icon="mdi:send-outline"></ha-icon> Meldung senden</button></div><div id="feedback-result" class="muted"></div></section></section>`;
        if (name === "outdoor") return `<section class="info-panel settings-panel"><div class="tiny info-kicker">AUSSENLUFT & WETTER</div><h3>Referenz für jede Lüftungsentscheidung</h3><p>Diese Sensoren beschreiben die Luft, die beim Lüften in das Haus strömt. Standardmäßig nutzt FreshAirIQ die Außenluft. Für einzelne Räume oder sogar einzelne Fenster/Türen kannst du davon abweichende lokale Referenzen hinterlegen – z. B. einen Wintergarten. Referenztemperatur und Referenzfeuchte müssen immer denselben Luftbereich messen.</p>${this._settingsGroup("DATENQUELLEN", "Änderungen werden nach der Auswahl gespeichert.", [
            this._settingsField({scope:"data",key:"outdoor_weather",label:"Wetter-Entität",description:"Bevorzugte Quelle für Temperatur, Feuchte, Wind und Prognosen.",type:"entity",domains:["weather"],defaultValue:"nicht gesetzt"}),
            this._settingsField({scope:"data",key:"outdoor_temperature",label:"Außentemperatur",description:"Alternative oder ergänzende lokale Temperaturmessung.",type:"entity",domains:["sensor"],deviceClass:"temperature",defaultValue:"nicht gesetzt"}),
            this._settingsField({scope:"data",key:"outdoor_humidity",label:"Außenluftfeuchtigkeit",description:"Alternative oder ergänzende lokale Feuchtemessung.",type:"entity",domains:["sensor"],deviceClass:"humidity",defaultValue:"nicht gesetzt"}),
            this._settingsField({scope:"data",key:"pollen_entity",label:"Pollensensor",description:"Optionaler Sensor für die Pollenbewertung.",type:"entity",domains:["sensor"],defaultValue:"nicht gesetzt"}),
        ])}</section>`;
        if (name === "building") return `<section class="info-panel settings-panel"><div class="tiny info-kicker">GEBÄUDE</div><h3>Grundprofil des Hauses</h3><p>Das Gebäudeprofil liefert FreshAirIQ die passenden Grundannahmen für Luftaustausch und Gebäudehülle. Bewohner und Anwesenheit werden getrennt im Bereich „Bewohner“ verwaltet.</p>${this._settingsGroup("GEBÄUDEPROFIL", "Diese Auswahl beschreibt nur das Gebäude – nicht die Bewohner.", [
            this._settingsField({key:"property_type",label:"Gebäudetyp",description:"Beeinflusst Grundannahmen zu Luftaustausch und Gebäudehülle.",type:"select",options:[select("house","Haus"),select("detached","Freistehendes Haus"),select("semi_detached","Doppelhaushälfte"),select("row_mid","Reihenmittelhaus"),select("row_end","Reihenendhaus"),select("apartment","Wohnung"),select("maisonette","Maisonette"),select("multi_family","Mehrfamilienhaus"),select("other","Sonstiges")]}),
        ])}</section>`;
        if (["residents", "house", "personalisation"].includes(name)) return `<section class="info-panel settings-panel resident-unified"><div class="resident-profile-spotlight resident-static"><div class="resident-profile-spotlight-icon"><ha-icon icon="mdi:account-heart-outline"></ha-icon><ha-icon class="resident-profile-spotlight-brain" icon="mdi:brain"></ha-icon></div><div><div class="tiny">PERSÖNLICHES FRESHAIRIQ PROFIL</div><h3>Dein Bewohnerprofil</h3><p>Alle Bewohnerdaten werden hier genau einmal gepflegt: Personen, Anwesenheit, zugeordnete Räume, Komfortpräferenzen und persönliche Endgeräte.</p></div></div>${this._settingsGroup("BEWOHNERPROFILE", "Regelmäßig im Haushalt lebende Personen. Anzahl, Name und Tracker gehören ausschließlich hierher.", [
            this._settingsField({key:"adult_occupants",label:"Erwachsene",description:"Regelmäßig im Haushalt lebende Erwachsene.",type:"number",min:0,max:20,step:1}),
            this._settingsField({key:"adult_resident_names",label:"Namen Erwachsene",description:"Optional. Kommagetrennt und in derselben Reihenfolge wie die Erwachsenen-Tracker; zusätzliche Namen stehen für Bewohner ohne eigenen Tracker.",type:"text",example:"Paul, Lydia"}),
            this._settingsField({key:"adult_presence_entities",label:"Tracker Erwachsene",description:"Person- oder device_tracker-Entitäten für Erwachsene. Reihenfolge passend zu den Namen wählen.",type:"multi-entity",domains:["person","device_tracker"]}),
            this._settingsField({key:"child_occupants",label:"Kinder",description:"Regelmäßig im Haushalt lebende Kinder.",type:"number",min:0,max:20,step:1}),
            this._settingsField({key:"child_resident_names",label:"Namen Kinder",description:"Optional. Kommagetrennt und in derselben Reihenfolge wie die Kinder-Tracker; Kinder ohne Tracker dürfen ebenfalls benannt werden.",type:"text",example:"Fiona, Maya"}),
            this._settingsField({key:"child_presence_entities",label:"Tracker Kinder",description:"Person- oder device_tracker-Entitäten für Kinder. Kann leer bleiben, wenn ein Kind keinen eigenen Tracker besitzt.",type:"multi-entity",domains:["person","device_tracker"]}),
            this._settingsField({key:"pets_in_household",label:"Haustiere im Haushalt",description:"Schwächt klassische Bewegungssensoren, damit Haustiere nicht als Bewohner interpretiert werden.",type:"boolean"}),
        ])}${this._settingsGroup("ANWESENHEIT", "Zusätzliche Signale für die Belegungsschätzung. Diese Daten legen keine zweite Bewohnerliste an.", [
            this._settingsField({key:"presence_sensor_entities",label:"Präsenz-/Bewegungssensoren",description:"Weiche Zusatzsignale für Anwesenheit.",type:"multi-entity",domains:["binary_sensor"]}),
            this._settingsField({key:"pet_safe_presence_entities",label:"Haustiersichere Präsenzsensoren",description:"Diese Sensoren werden als haustiersichere Anwesenheitssignale berücksichtigt.",type:"multi-entity",domains:["binary_sensor"]}),
            this._settingsField({key:"untracked_follow_household",label:"Personen ohne Tracker folgen dem Haushalt",description:"Wenn aktiv, werden nicht getrackte Bewohner mit dem Haushaltsstatus geschätzt.",type:"boolean"}),
        ])}${this._settingsGroup("HAUSHALTS-KOMFORT", "Gilt als Standard, wenn ein Bewohner im persönlichen Profil keinen eigenen Wert besitzt.", [
            this._settingsField({key:"personalisation_enabled",label:"Persönliche Empfehlungen",description:"Nutzt Haushaltskontext und gelerntes Verhalten für passendere, natürlichere Empfehlungen.",type:"boolean"}),
            this._settingsField({key:"thermal_preference",label:"Standard-Temperaturempfinden",description:"Haushaltsweiter Standard. Einzelne Bewohner können ihn im persönlichen IQ-Profil überschreiben.",type:"select",options:[select("warm","Eher warm"),select("balanced","Ausgewogen"),select("cool","Eher kühl")]}),
            this._settingsField({key:"personal_priority",label:"Persönliche Priorität",description:"Gewichtet nicht sicherheitskritische Erklärungen und Komfortentscheidungen.",type:"select",options:[select("climate","Raumklima"),select("balanced","Ausgewogen"),select("energy","Energie sparen")]}),
            this._settingsField({key:"night_window_preference",label:"Fenster in der Nacht",description:"Persönliche Präferenz für die Nachtstrategie. Automatisch lässt FreshAirIQ rein nach Situation entscheiden.",type:"select",options:[select("automatic","Automatisch entscheiden"),select("closed","Nachts lieber geschlossen"),select("allowed","Nachts offen ist okay")]}),
        ])}<section class="settings-group resident-profile-master"><div class="settings-group-head"><div><div class="tiny">PERSÖNLICHE IQ-PROFILE & ENDGERÄTE</div><span>Hier werden die oben angelegten Bewohner nur noch verfeinert. Es entstehen keine doppelten Personen, Namen oder Tracker.</span></div></div>${this._residentProfilesEditor()}</section>${this._settingsGroup("NACHT", "Zeitraum und Aktivierung der Nachtprognose.", [
            this._settingsField({key:"night_start_hour",label:"Nacht beginnt",description:"Start der Nachtbewertung.",type:"time"}),
            this._settingsField({key:"night_end_hour",label:"Nacht endet",description:"Ende der Nachtbewertung.",type:"time"}),
            this._settingsField({key:"night_forecast_enabled",label:"Nachtprognose aktiv",description:"Berechnet die erwartete Feuchteentwicklung über Nacht.",type:"boolean"}),
        ])}${this._settingsGroup("AUTOMATISCH GELERNT", "Dafür musst du nichts einstellen.", [`<div class="muted">FreshAirIQ lernt Raumreaktionen, Prognosefehler, Routinen und die Reaktion auf Empfehlungen. Gesundheits- und Sicherheitsgrenzen werden dadurch nie überschrieben.</div>`])}</section>`;
        if (name === "profile") {
            const profile = o.operating_profile || "comfort";
            const details = profile === "summer_cooling" ? [
                this._settingsField({key:"cooling_start_temp_c",label:"Kühlung ab Innentemperatur",description:"Sommerkühlung wird erst oberhalb dieses Werts erwogen.",type:"number",unit:"°C",min:18,max:35,step:.5}),
                this._settingsField({key:"cooling_min_outdoor_delta_c",label:"Mindest-Temperaturvorteil außen",description:"Außenluft muss mindestens so viel kühler sein.",type:"number",unit:"°C",min:.5,max:10,step:.5}),
                this._settingsField({key:"cooling_max_indoor_rh",label:"Maximale Innenfeuchte für Kühlung",description:"Verhindert Kühlung durch zu feuchte Luft.",type:"number",unit:"%",min:40,max:90,step:1}),
                this._settingsField({key:"cooling_max_moisture_gain_5min_ml",label:"Maximaler Feuchteeintrag",description:"Zulässiger Feuchteeintrag im Prognosefenster.",type:"number",unit:"ml",min:0,max:500,step:5}),
            ] : [];
            const profileDetails = details.length
                ? this._settingsGroup("PROFILDETAILS", `Feinabstimmung für ${profileDE(profile)}.`, details)
                : `<section class="settings-group"><div class="settings-group-head"><div><div class="tiny">FEINABSTIMMUNG</div><span>Die Effizienz-, Temperaturverlust- und Feuchtegrenzen werden zentral unter „Lüftungsmodell“ gepflegt. Dadurch gibt es keine doppelten Einstellungen.</span></div></div></section>`;
            return `<section class="info-panel settings-panel"><div class="tiny info-kicker">BETRIEBSPROFIL</div><h3>Wie FreshAirIQ priorisiert</h3><p>Das Profil verändert die Gewichtung, nicht die Sicherheitsgrenzen.</p>${this._settingsGroup("MODUS", "Komfort ist der ausgewogene Standard.", [this._settingsField({key:"operating_profile",label:"Betriebsprofil",description:"Entfeuchten priorisiert Feuchteabbau, Komfort balanciert alles, Sommerkühlung nutzt günstige Außenluft zum Kühlen.",type:"select",options:[select("dehumidify","Entfeuchten"),select("comfort","Komfort"),select("summer_cooling","Sommer kühlen")]})])}${profileDetails}</section>`;
        }
        if (name === "forecast") return `<section class="info-panel settings-panel"><div class="tiny info-kicker">PROGNOSE</div><h3>Zeitraum der Live-Vorhersage</h3><p>Der gleiche Wert wird im Dashboard, in den Raumdetails und in der IQ-Simulation verwendet.</p>${this._settingsGroup("ZEITHORIZONT", "Kurze Werte reagieren schneller, längere Werte zeigen den längerfristigen Effekt.", [this._settingsField({key:"forecast_horizon_min",label:"Prognosezeitraum",description:"Intelligenter Kurzzeit-Horizont.",type:"number",unit:"min",min:1,max:120,step:1,example:"5, 10, 15, 20 oder 60 Minuten"})])}</section>`;
        if (name === "air") return `<section class="info-panel settings-panel"><div class="tiny info-kicker">OPTIONALE SENSOREN & AUSSENLUFT</div><h3>Zusatzdaten intelligent nutzen</h3><p>VOC/TVOC, PM2.5 und Helligkeit sind vollständig optional. Sie verändern weder die bestehende Feuchte-/Lüftungsphysik noch die ml-Prognose oder das Lernmodell. Wenn aktiviert und in einem Raum zugeordnet, dürfen sie zusätzliche Empfehlungen erzeugen und werden in der lokalen 30-Tage-Diagnostik für spätere Funktionserweiterungen mitgeführt.</p>${this._settingsGroup("OPTIONALE ZUSATZSENSOREN", "Aus = Sensorwerte dieses Typs werden von FreshAirIQ nicht eingelesen, nicht angezeigt und nicht für Zusatzempfehlungen berücksichtigt. Die Zuordnung im Raum bleibt gespeichert und kann später wieder aktiviert werden.", [
            this._settingsField({key:"voc_sensor_enabled",label:"VOC / TVOC verwenden",description:"Optional. Ermöglicht ergänzende Luftqualitäts- und Luftreiniger-Empfehlungen; keine Änderung der Lüftungsberechnung.",type:"boolean"}),
            this._settingsField({key:"pm25_sensor_enabled",label:"PM2.5 verwenden",description:"Optional. Ermöglicht ergänzende Feinstaub- und Luftreiniger-Empfehlungen; keine Änderung der Lüftungsberechnung.",type:"boolean"}),
            this._settingsField({key:"illuminance_sensor_enabled",label:"Helligkeit verwenden",description:"Optional. Kann Verschattungs-Empfehlungen präzisieren; keine Änderung der Lüftungsberechnung.",type:"boolean"}),
        ])}${this._settingsGroup("AUSSENLUFT", "Pollen benötigt zusätzlich einen Pollensensor unter Außenluft & Wetter.", [
            this._settingsField({key:"pollen_enabled",label:"Pollen berücksichtigen",description:"Aktiviert die Pollenbewertung.",type:"boolean"}),
            this._settingsField({key:"pollen_max",label:"Maximaler Pollenindex",description:"Ab diesem Wert wird Lüften eingeschränkt oder verschoben.",type:"number",min:0,max:10,step:.5}),
            this._settingsField({key:"pollen_strict_veto",label:"Strenges Pollen-Veto",description:"Wenn aktiv, kann hohe Pollenlast eine normale Lüftungsempfehlung blockieren.",type:"boolean"}),
            this._settingsField({key:"wind_orientation_enabled",label:"Wind & Fensterausrichtung nutzen",description:"Berücksichtigt Windrichtung zusammen mit den hinterlegten Fensterseiten.",type:"boolean"}),
        ])}${this._settingsGroup("SCHWELLEN & AKTORIK", "Grenzen für aktivierte Zusatzsensoren und passive/technische Maßnahmen. Diese Werte steuern nur Zusatzempfehlungen – nicht die kanonische Lüftungsphysik.", [
            this._settingsField({key:"voc_warn",label:"VOC-Warnschwelle",description:"Ab hier kann FreshAirIQ einen vorhandenen Luftreiniger empfehlen.",type:"number",min:50,max:5000,step:50}),
            this._settingsField({key:"voc_critical",label:"VOC kritisch",description:"Kritische VOC-Schwelle für zukünftige Priorisierung und Diagnose.",type:"number",min:100,max:10000,step:50}),
            this._settingsField({key:"pm25_warn",label:"PM2.5-Warnschwelle",description:"Feinstaub-Grenze für Luftreiniger-Empfehlungen.",type:"number",unit:"µg/m³",min:1,max:250,step:1}),
            this._settingsField({key:"pm25_critical",label:"PM2.5 kritisch",description:"Kritische Feinstaub-Schwelle.",type:"number",unit:"µg/m³",min:2,max:500,step:1}),
            this._settingsField({key:"humidify_below_rh",label:"Befeuchten unter",description:"Unterhalb dieser relativen Feuchte kann ein vorhandener Befeuchter empfohlen werden.",type:"number",unit:"%",min:20,max:50,step:1}),
            this._settingsField({key:"shade_above_temp_c",label:"Verschattung ab",description:"Ab dieser Raumtemperatur wird vorhandener Sonnenschutz berücksichtigt.",type:"number",unit:"°C",min:18,max:35,step:.5}),
            this._settingsField({key:"shade_min_illuminance_lx",label:"Mindesthelligkeit für Verschattung",description:"Wenn ein Helligkeitssensor vorhanden ist, wird Verschattung erst oberhalb dieses Werts empfohlen.",type:"number",unit:"lx",min:0,max:100000,step:500}),
        ])}</section>`;
        if (name === "cross") return `<section class="info-panel settings-panel"><div class="tiny info-kicker">QUERLÜFTUNG</div><h3>Echte Luftwege definieren</h3><p>Trage nur Paare ein, bei denen zwei geöffnete Räume tatsächlich einen wirksamen Durchzug bilden können. Die Raumschlüssel findest du unter „Räume & Sensoren“.</p>${this._settingsGroup("LUFTWEGE", "Standard ist leer – dann wird kein zusätzlicher Querlüftungsbonus angenommen.", [
            this._settingsField({key:"cross_ventilation_pairs",label:"Querlüftungspaare",description:"Ein Paar pro Zeile oder durch Komma getrennt. Format: raum_a+raum_b.",type:"textarea",example:"wohnzimmer+schlafzimmer"}),
            this._settingsField({key:"cross_zone_connections",label:"Verbindungen über Bereiche",description:"Nur erforderlich, wenn ein Paar über verschiedene Stockwerke/Bereiche physisch verbunden ist. Gleiches Format.",type:"textarea",example:"wohnzimmer+fitnessraum"}),
        ])}</section>`;
        if (name === "model") return `<section class="info-panel settings-panel"><div class="tiny info-kicker">LÜFTUNGSMODELL</div><h3>Technische Feinabstimmung</h3><p>Diese Werte entsprechen den Experteneinstellungen unter Geräte & Dienste. Die Standardwerte sind für die meisten Haushalte die richtige Wahl.</p>${this._settingsGroup("FEUCHTESCHWELLEN", "Wann Lüften beginnt, wie hoch hohe Feuchte ist und wann das Ziel erreicht ist.", [
            this._settingsField({key:"start_rh",label:"Start-Luftfeuchte",description:"Ab dieser relativen Feuchte wird ein normaler Lüftungsbedarf wahrscheinlicher.",type:"number",unit:"%",min:40,max:90,step:1}),
            this._settingsField({key:"high_rh",label:"Hohe Luftfeuchte",description:"Ab hier gelten strengere Feuchteregeln.",type:"number",unit:"%",min:45,max:95,step:1}),
            this._settingsField({key:"target_rh",label:"Ziel-Luftfeuchte",description:"Angestrebter Bereich nach sinnvoller Lüftung.",type:"number",unit:"%",min:35,max:75,step:1}),
            this._settingsField({key:"min_delta",label:"Mindestdifferenz absolute Feuchte",description:"Außenluft muss ausreichend trockener sein.",type:"number",unit:"g/m³",min:.1,max:8,step:.1}),
            this._settingsField({key:"min_delta_high_rh",label:"Mindestdifferenz bei hoher Feuchte",description:"Bei hoher Innenfeuchte darf FreshAirIQ früher reagieren.",type:"number",unit:"g/m³",min:.1,max:5,step:.1}),
            this._settingsField({key:"close_delta",label:"Schließdifferenz",description:"Grenze, ab der zusätzlicher Lüftungsnutzen zu gering wird.",type:"number",unit:"g/m³",min:-1,max:3,step:.1}),
        ])}${this._settingsGroup("EMPFEHLUNGSSCHWELLE", "Bestimmt, ab welchem Gesamtpotenzial FreshAirIQ eine Hauslüftung empfiehlt.", [
            this._settingsField({key:"threshold_mode",label:"Schwellenmodus",description:"Adaptiv berücksichtigt Hausgröße; Prozent nutzt die gesamte Wassermenge; Festwert verwendet ml.",type:"select",options:[select("adaptive_home_size","Adaptiv nach Hausgröße"),select("percent_total_water","Prozent der Wassermenge"),select("fixed_ml","Fester ml-Wert")]}),
            this._settingsField({key:"min_potential_percent_total_water",label:"Mindestpotenzial in Prozent",description:"Nur im Prozentmodus relevant.",type:"number",unit:"%",min:1,max:30,step:.5}),
            this._settingsField({key:"min_potential_total_ml",label:"Mindestpotenzial gesamt",description:"Fester Haus-Schwellenwert bzw. Basiswert.",type:"number",unit:"ml",min:50,max:5000,step:10}),
            this._settingsField({key:"min_potential_room_ml",label:"Mindestpotenzial je Raum",description:"Verhindert Empfehlungen für sehr kleine Einzeleffekte.",type:"number",unit:"ml",min:10,max:1000,step:10}),
        ])}${this._settingsGroup("ZEIT & WIEDERHOLUNG", "Steuert Mindest-/Maximaldauer und Wiederholungsempfehlungen.", [
            this._settingsField({key:"min_duration_min",label:"Mindestdauer",description:"Kürzeste reguläre Lüftungsdauer.",type:"number",unit:"min",min:1,max:30,step:1}),
            this._settingsField({key:"max_duration_min",label:"Maximaldauer",description:"Obergrenze der regulären Empfehlung.",type:"number",unit:"min",min:3,max:90,step:1}),
            this._settingsField({key:"post_ventilation_stabilization_min",label:"Stabilisierungszeit",description:"Wartezeit nach Lüftung, bevor Folgeeffekte bewertet werden.",type:"number",unit:"min",min:1,max:15,step:1}),
            this._settingsField({key:"repeat_recommendation_cooldown_min",label:"Cooldown für erneute Empfehlung",description:"Mindestabstand bis zu einer neuen ähnlichen Empfehlung.",type:"number",unit:"min",min:5,max:120,step:5}),
            this._settingsField({key:"repeat_min_benefit_ml",label:"Mindestnutzen für Wiederholung",description:"Erneute Empfehlung nur bei genügend zusätzlichem Potenzial.",type:"number",unit:"ml",min:10,max:1000,step:10}),
        ])}${this._settingsGroup("EFFIZIENZ", "Grenzen für Nutzen gegenüber Temperaturverlust.", [
            this._settingsField({key:"min_return_next_5_min_ml",label:"Mindest-Feuchtenutzen",description:"Minimaler erwarteter weiterer Feuchteabbau.",type:"number",unit:"ml",min:0,max:500,step:5}),
            this._settingsField({key:"max_temp_loss_next_5_min_c",label:"Maximaler Temperaturverlust",description:"Komfortgrenze des Prognosefensters.",type:"number",unit:"°C",min:.1,max:5,step:.1}),
            this._settingsField({key:"min_efficiency_ml_per_01c",label:"Mindest-Effizienz",description:"Feuchteabbau je 0,1 °C Verlust.",type:"number",unit:"ml/0,1°C",min:0,max:200,step:1}),
        ])}${this._settingsGroup("GESUNDHEIT & LERNEN", "Schimmel-, CO₂- und Lernmodellgrenzen.", [
            this._settingsField({key:"surface_factor",label:"Oberflächenfaktor",description:"Modelliert den Unterschied zwischen Raumluft und kalten Oberflächen.",type:"number",min:.05,max:.8,step:.05}),
            this._settingsField({key:"mould_warn_surface_rh",label:"Schimmelwarnung ab",description:"Oberflächen-RH für erhöhte Warnstufe.",type:"number",unit:"%",min:60,max:95,step:1}),
            this._settingsField({key:"mould_critical_surface_rh",label:"Schimmel kritisch ab",description:"Oberflächen-RH für kritische Warnstufe.",type:"number",unit:"%",min:70,max:100,step:1}),
            this._settingsField({key:"co2_warn",label:"CO₂-Warnung",description:"Warnschwelle für vorhandene CO₂-Sensoren.",type:"number",unit:"ppm",min:600,max:2500,step:50}),
            this._settingsField({key:"co2_critical",label:"CO₂ kritisch",description:"Kritische Schwelle für vorhandene CO₂-Sensoren.",type:"number",unit:"ppm",min:800,max:4000,step:50}),
            this._settingsField({key:"learning_enabled",label:"Lernmodell aktiv",description:"FreshAirIQ lernt reale Raumreaktionen und Prognoseabweichungen.",type:"boolean"}),
            this._settingsField({key:"learning_max_duration_min",label:"Maximale Lernsession",description:"Längere Sessions werden nicht als saubere Lernprobe verwendet.",type:"number",unit:"min",min:15,max:240,step:5}),
        ])}</section>`;
        if (name === "energy") {
            const system = o.heating_system || "heat_pump";
            const details = system === "heat_pump" ? [this._settingsField({key:"electricity_price_per_kwh",label:"Strompreis",description:"Preis für die Wiederaufheizenergie.",type:"number",unit:"€/kWh",min:0,max:5,step:.01}),this._settingsField({key:"heat_pump_cop",label:"Wärmepumpen-COP",description:"Verhältnis von Wärmeleistung zu Stromaufnahme.",type:"number",min:1,max:10,step:.1})] : system === "gas" ? [this._settingsField({key:"gas_price_per_kwh",label:"Gaspreis",description:"Arbeitspreis des Gases.",type:"number",unit:"€/kWh",min:0,max:2,step:.001}),this._settingsField({key:"gas_efficiency",label:"Wirkungsgrad Gasheizung",description:"Nutzbarer Anteil der eingesetzten Energie.",type:"number",min:.5,max:1,step:.01})] : system === "oil" ? [this._settingsField({key:"oil_price_per_liter",label:"Ölpreis",description:"Preis je Liter Heizöl.",type:"number",unit:"€/l",min:0,max:5,step:.01}),this._settingsField({key:"oil_kwh_per_liter",label:"Energiegehalt Heizöl",description:"Thermischer Energiegehalt je Liter.",type:"number",unit:"kWh/l",min:8,max:12,step:.1}),this._settingsField({key:"oil_efficiency",label:"Wirkungsgrad Ölheizung",description:"Nutzbarer Anteil der Brennstoffenergie.",type:"number",min:.5,max:1,step:.01})] : system === "district_heating" ? [this._settingsField({key:"district_price_per_kwh",label:"Fernwärmepreis",description:"Arbeitspreis der gelieferten Wärme.",type:"number",unit:"€/kWh",min:0,max:5,step:.01}),this._settingsField({key:"district_efficiency",label:"Systemwirkungsgrad",description:"Berücksichtigt Verteilverluste im Haus.",type:"number",min:.5,max:1,step:.01})] : [this._settingsField({key:"electricity_price_per_kwh",label:"Strompreis",description:"Preis der elektrischen Heizenergie.",type:"number",unit:"€/kWh",min:0,max:5,step:.01})];
            return `<section class="info-panel settings-panel"><div class="tiny info-kicker">ENERGIE & KOSTEN</div><h3>Wiederaufheizen realistisch bewerten</h3><p>FreshAirIQ schätzt die nach einer Lüftung verlorene Wärme und rechnet sie mit dem gewählten Heizsystem in Kosten um.</p>${this._settingsGroup("HEIZSYSTEM", "Wähle das tatsächlich verwendete Hauptsystem.", [this._settingsField({key:"heating_system",label:"Heizsystem",description:"Bestimmt, welche Kostenparameter verwendet werden.",type:"select",options:[select("heat_pump","Wärmepumpe"),select("gas","Gasheizung"),select("district_heating","Fernwärme"),select("electric","Elektroheizung"),select("oil","Ölheizung")]})])}${this._settingsGroup("KOSTENMODELL", `Parameter für ${heatingDE(system)}.`, details)}</section>`;
        }
        if (name === "notifications") {
            const notifyOpts = ((this._settingsData && this._settingsData.notify_services) || []).map(x => ({value:x,label:`notify.${x}`}));
            const roomOpts = (d.rooms || []).map(r => ({value:r.key,label:r.name || r.key}));
            return `<section class="info-panel settings-panel"><div class="tiny info-kicker">BENACHRICHTIGUNGEN</div><h3>Nur das melden, was wirklich wichtig ist</h3><p>Benachrichtigungen sind standardmäßig aus. Ziele entsprechen den aktuell in Home Assistant registrierten notify-Diensten.</p>${this._settingsGroup("ZIELE", "Lege fest, wohin und für welche Räume FreshAirIQ melden darf.", [
                this._settingsField({key:"notifications_enabled",label:"Benachrichtigungen aktiv",description:"Globaler Hauptschalter.",type:"boolean"}),
                this._settingsField({key:"notification_targets",label:"Benachrichtigungsziele",description:"Ein oder mehrere notify-Dienste.",type:"multi-select",options:notifyOpts}),
                this._settingsField({key:"notification_scope",label:"Geltungsbereich",description:"Raum, Haus oder beides.",type:"select",options:[select("room","Nur ausgewählte Räume"),select("house","Hausweit"),select("both","Hausweit + ausgewählte Räume")]}),
                this._settingsField({key:"notification_room_keys",label:"Ausgewählte Räume",description:"Nur für raumbezogene Meldungen relevant.",type:"multi-select",options:roomOpts}),
                this._settingsField({key:"notification_cooldown_min",label:"Meldungs-Cooldown",description:"Mindestabstand zwischen gleichartigen Meldungen.",type:"number",unit:"min",min:10,max:1440,step:5}),
            ])}${this._settingsGroup("EREIGNISSE", "Jede Meldungsart lässt sich einzeln zulassen.", [
                this._settingsField({key:"notify_ventilate",label:"Lüften empfohlen",description:"Meldung beim sinnvollen Lüftungsstart.",type:"boolean"}),
                this._settingsField({key:"notify_close",label:"Fenster schließen",description:"Meldung wenn der Lüftungsnutzen endet.",type:"boolean"}),
                this._settingsField({key:"notify_complete",label:"Lüftung abgeschlossen",description:"Ergebnis nach einer abgeschlossenen Lüftung.",type:"boolean"}),
                this._settingsField({key:"notify_cooling",label:"Sommerkühlung",description:"Hinweise auf günstige Kühlfenster.",type:"boolean"}),
                this._settingsField({key:"notify_mould",label:"Schimmelwarnung",description:"Hinweis bei relevantem Oberflächenrisiko.",type:"boolean"}),
                this._settingsField({key:"notify_sensor",label:"Sensorproblem",description:"Hinweis bei fehlenden oder unplausiblen Daten.",type:"boolean"}),
                this._settingsField({key:"notify_night",label:"Nachtstrategie",description:"Hinweise zur Nachtlüftung.",type:"boolean"}),
                this._settingsField({key:"notify_learning",label:"Lernstatus",description:"Hinweise auf relevante Lernfortschritte.",type:"boolean"}),
            ])}</section>`;
        }
        if (name === "statistics") return `<section class="info-panel settings-panel"><div class="tiny info-kicker">DATEN & STATISTIK</div><h3>Wie weit FreshAirIQ zurückblickt</h3><p>Der Statistikzeitraum beeinflusst die dargestellte Historie, nicht die Sicherheitsschwellen.</p>${this._settingsGroup("AUSWERTUNG", "Mehr Tage glätten kurzfristige Ausreißer, benötigen aber mehr Historie.", [this._settingsField({key:"statistics_days",label:"Statistikzeitraum",description:"1–365 Tage aggregierte Klima- und Lüftungshistorie; hochaufgelöste Temperaturpunkte bleiben aus Performancegründen auf 30 Tage begrenzt.",type:"number",unit:"Tage",min:1,max:365,step:1})])}</section>`;
        if (name === "diagnostics_sharing") return `<section class="info-panel settings-panel"><div class="tiny info-kicker">DATENSCHUTZ & DIAGNOSE</div><h3>Automatische pseudonymisierte Diagnosen</h3><p>Der Diagnose-Client ist in FreshAirIQ integriert und für analyseäquivalente Übertragung gehärtet. Beim ersten bestätigten Abgleich wird die lokal verfügbare 30-Tage-Diagnostik datenschutzgefiltert und in Chunks übertragen; danach nur neue Datensätze. Diese Staging-Version ist mit dem lokalen Diagnostics Hub im privaten Heimnetz verbunden. Während der öffentlichen Beta ist die tägliche Nachtübertragung standardmäßig aktiv und kann jederzeit auf „Aus“, „Nur bei erkannten Problemen“ oder „Wöchentlich“ geändert werden. Der lokale Testpfad verwendet HTTP ausschließlich im privaten LAN; ein späterer öffentlicher Betrieb wird nur über HTTPS freigegeben.</p>${this._settingsGroup("ÜBERTRAGUNG", "Beta-Standard ist „Täglich nachts“. Technisch analyseäquivalente, aber lokal von direkten Identifikatoren bereinigte und pseudonymisierte Diagnosedaten werden nur entsprechend dieser Auswahl übertragen.", [this._settingsField({key:"diagnostics_reporting_mode",label:"Automatische Diagnoseübertragung",description:"Aus, nur bei erkannten Problemen, täglich nachts oder wöchentlich. Nacht-Uploads werden pro Installation auf 02:00–03:59 Uhr verteilt, damit nicht alle Systeme gleichzeitig senden.",type:"select",options:[select("off","Aus"),select("errors","Nur bei erkannten Problemen"),select("daily","Täglich nachts"),select("weekly","Wöchentlich")]}),this._settingsField({key:"diagnostics_include_client_context",label:"Geräte-/Browser-Kontext mitsenden",description:"Beta-Standard: an. Überträgt nur grobe Plattform-, Browser- und Viewportdaten für Kompatibilitätsfehler. Exakte Gerätenamen und Seriennummern werden nicht übertragen.",type:"boolean"})])}<div class="settings-group"><div class="settings-field-copy"><b>Was wird lokal entfernt?</b><span>Raumnamen, echte Raumschlüssel, Entity-IDs, Bewohnernamen, Benachrichtigungsziele, Netzwerkkennungen, IP-Adressen, E-Mail-Adressen, URLs und exakte Gerätemodelle werden vor jedem Upload entfernt oder pseudonymisiert. Technisch relevante Mess-, Forecast-, Lern- und Konfigurationsdaten bleiben für die Analyse erhalten.</span><small>Hub-Status: lokales Staging verbunden</small></div></div></section>`;
        if (name === "levels") {
            const levels = Array.isArray(d.levels) ? d.levels : [];
            return `<section class="info-panel settings-panel"><div class="tiny info-kicker">STOCKWERKE & BEREICHE</div><h3>Struktur des Hauses</h3><p>Ein Bereich pro Zeile. Bereiche, denen noch Räume zugeordnet sind, können nicht gelöscht werden.</p><div class="settings-group"><div class="settings-field settings-field-stack"><div class="settings-field-copy"><b>Bereiche</b><span>Die Reihenfolge wird auch in der Raumübersicht verwendet.</span><small>Standard: keine feste Vorgabe · Beispiel: Erdgeschoss, Kellergeschoss, Dachgeschoss</small></div><textarea id="settings-levels" class="settings-input settings-textarea" rows="7">${esc(levels.map(floorDE).join("\n"))}</textarea><button class="settings-save" id="settings-save-levels"><ha-icon icon="mdi:content-save-outline"></ha-icon> Bereiche speichern</button></div></div></section>`;
        }
        if (name === "rooms") return this._settingsRooms();
        if (name.startsWith("room:")) return this._settingsRoomEditor(name.slice(5));
        if (name === "maintenance") return `<section class="info-panel settings-panel"><div class="tiny info-kicker">WARTUNG</div><h3>Zurücksetzen mit Bedacht</h3><p>Räume und Sensorzuordnungen bleiben beim Zurücksetzen der Standard-Einstellungen erhalten.</p><div class="settings-danger-grid"><div class="settings-danger"><ha-icon icon="mdi:brain"></ha-icon><div><b>Lerndaten zurücksetzen</b><span>Entfernt gelernte Raumreaktionen, Ergebnisfeedback, Routinen und Strategieproben. Die Konfiguration bleibt erhalten.</span></div><button data-settings-action="reset_learning">Lerndaten löschen</button></div><div class="settings-danger"><ha-icon icon="mdi:restore"></ha-icon><div><b>Einstellungen auf Standard</b><span>Setzt alle Optionen auf dokumentierte Standardwerte. Räume, Sensoren und Statistikdateien bleiben erhalten.</span></div><button data-settings-action="reset_defaults">Standards wiederherstellen</button></div></div></section>`;
        return this._settingsHome();
    }
    _settingsRooms() {
        const d = (this._settingsData && this._settingsData.data) || {};
        const rooms = this._orderedRooms(d.rooms || []);
        return `<section class="info-panel settings-panel"><div class="tiny info-kicker">RÄUME & SENSOREN</div><h3>Räume direkt im Dashboard verwalten</h3><p>Temperatur, Luftfeuchte und ein Lüftungskontakt sind für berechnete Räume die zentrale Basis. Änderungen werden in dieselbe Home-Assistant-Konfiguration geschrieben.</p><div class="settings-room-list">${rooms.map((r,i) => `<div class="settings-room-row"><button class="settings-room-main" data-settings-room="${esc(r.key)}"><span class="settings-room-index">${i+1}</span><div><b>${esc(r.name || r.key)}</b><span>${esc(floorDE(r.floor))} · Schlüssel ${esc(r.key)} · ${(r.contacts||[]).length} Kontakt(e)</span></div><ha-icon icon="mdi:chevron-right"></ha-icon></button><div class="settings-room-order"><button data-room-move="up" data-room-key="${esc(r.key)}" ${i===0?"disabled":""}><ha-icon icon="mdi:chevron-up"></ha-icon></button><button data-room-move="down" data-room-key="${esc(r.key)}" ${i===rooms.length-1?"disabled":""}><ha-icon icon="mdi:chevron-down"></ha-icon></button></div></div>`).join("") || `<div class="settings-empty">Noch keine Räume eingerichtet.</div>`}</div><button class="settings-save settings-add-room" data-settings-room="new"><ha-icon icon="mdi:plus"></ha-icon> Raum hinzufügen</button></section>`;
    }
    _settingsContactRows(contacts, room = {}) {
        const list = Array.isArray(contacts) ? contacts : [];
        if (!list.length) return `<div class="settings-empty">Noch kein Fenster-/Türkontakt ausgewählt.</div>`;
        const orientations = room.contact_orientations || {};
        const delays = room.contact_delays || {};
        const refTemps = room.contact_reference_temperatures || {};
        const refHumidity = room.contact_reference_humidities || {};
        const contactCovers = room.contact_covers || {};
        const entityOptions = (value, deviceClass) => {
            const entities = this._settingsEntities(["sensor"], value || "", deviceClass);
            return `<option value="">Außenluft / Raum-Referenz verwenden</option>${entities.map(x => `<option value="${esc(x.entity_id)}" ${x.entity_id===value?"selected":""}>${esc((x.attributes||{}).friendly_name || x.entity_id)}</option>`).join("")}`;
        };
        const coverOptions = value => {
            const current = Array.isArray(value) ? value : [];
            return this._settingsEntities(["cover"], current).map(x => `<option value="${esc(x.entity_id)}" ${current.includes(x.entity_id)?"selected":""}>${esc((x.attributes||{}).friendly_name || x.entity_id)} · ${esc(x.entity_id)}</option>`).join("");
        };
        return list.map(c => `<div class="settings-contact-row" data-contact="${esc(c)}"><div class="settings-contact-title"><b>${esc((this._hass.states[c]&&this._hass.states[c].attributes.friendly_name)||c)}</b><span>${esc(c)}</span></div><label><span>Ausrichtung</span><select class="settings-input room-contact-orientation"><option value="unknown" ${!orientations[c]||orientations[c]==="unknown"?"selected":""}>Unbekannt</option>${[["n","Nord"],["ne","Nordost"],["e","Ost"],["se","Südost"],["s","Süd"],["sw","Südwest"],["w","West"],["nw","Nordwest"]].map(([v,l])=>`<option value="${v}" ${orientations[c]===v?"selected":""}>${l}</option>`).join("")}</select></label><label><span>Öffnungsverzögerung</span><div class="settings-input-wrap"><input class="settings-input room-contact-delay" type="number" min="0" max="600" step="1" value="${esc(delays[c] ?? 0)}"><span>s</span></div></label><label><span>Referenztemperatur dieser Öffnung</span><select class="settings-input room-contact-ref-temp">${entityOptions(refTemps[c],"temperature")}</select></label><label><span>Referenzfeuchte dieser Öffnung</span><select class="settings-input room-contact-ref-humidity">${entityOptions(refHumidity[c],"humidity")}</select></label><label><span>Rollo / Jalousie dieser Öffnung</span><select class="settings-input settings-multi room-contact-covers" multiple size="4">${coverOptions(contactCovers[c])}</select></label><small class="settings-contact-help">Referenzluft nur setzen, wenn diese Öffnung nicht in die normale Außenluft führt. Ein Rollo/Jalousie wird direkt diesem Fenster bzw. dieser Tür zugeordnet; mehrere sind möglich.</small></div>`).join("");
    }
    _settingsRoomEditor(key) {
        const d = (this._settingsData && this._settingsData.data) || {};
        const levels = Array.isArray(d.levels) ? d.levels : [];
        const existing = key === "new" ? null : (d.rooms || []).find(r => r.key === key);
        const r = existing || {name:"",floor:levels[0]||"Unzugeordnet",include_in_calculations:true,contacts:[],contact_mode:"any",moisture_sources:[],contact_delays:{},contact_orientations:{}};
        const entitySelect = (id, domains, value, deviceClass=null, multiple=false) => {
            const current = multiple ? (Array.isArray(value)?value:[]) : value;
            const entities = this._settingsEntities(domains, current, deviceClass);
            return `<select id="${id}" class="settings-input ${multiple?"settings-multi":""}" ${multiple?"multiple size=\"6\"":""}>${multiple?"":"<option value=\"\">Nicht gesetzt</option>"}${entities.map(s => `<option value="${esc(s.entity_id)}" ${(multiple?current.includes(s.entity_id):s.entity_id===current)?"selected":""}>${esc((s.attributes||{}).friendly_name || s.entity_id)} · ${esc(s.entity_id)}</option>`).join("")}</select>`;
        };
        const contacts = Array.isArray(r.contacts) ? r.contacts : [];
        return `<section class="info-panel settings-panel"><div class="tiny info-kicker">${existing?"RAUM BEARBEITEN":"NEUER RAUM"}</div><h3>${esc(existing ? r.name : "Raum anlegen")}</h3><p>Raumänderungen werden bewusst gemeinsam gespeichert, weil Sensoren, Maße und Kontakte voneinander abhängen.</p><div class="settings-group room-form" data-room-key="${esc(existing?r.key:"")}">
            <div class="settings-field settings-field-stack"><div class="settings-field-copy"><b>Raumname</b><span>Frei wählbarer Anzeigename.</span><small>Standard: erforderlich · Beispiel: Wohnzimmer</small></div><input id="room-name" class="settings-input" value="${esc(r.name||"")}"></div>
            <div class="settings-field settings-field-stack"><div class="settings-field-copy"><b>Stockwerk / Bereich</b><span>Dient Gruppierung und Querlüftungsbewertung.</span><small>Standard: Unzugeordnet</small></div><select id="room-floor" class="settings-input">${[...new Set([...levels,r.floor||"Unzugeordnet"])].map(x=>`<option value="${esc(x)}" ${x===r.floor?"selected":""}>${esc(floorDE(x))}</option>`).join("")}</select></div>
            <div class="settings-field"><div class="settings-field-copy"><b>In Klimaberechnungen einbeziehen</b><span>Aus = Strukturraum ohne Pflichtsensoren. Größe und Stockwerk bleiben im Hausprofil erhalten, es werden aber keine ungemessenen Klimawerte erfunden.</span><small>Standard: ein · Für Räume ohne Sensoren ausschalten</small></div><label class="settings-switch"><input id="room-include" type="checkbox" ${r.include_in_calculations!==false?"checked":""}><span></span></label></div>
            <div class="settings-field settings-field-stack"><div class="settings-field-copy"><b>Individuelle Lüftungsgrenze</b><span>Legt fest, ab welchem entfernbaren Feuchtepotenzial dieser Raum eigenständig priorisiert werden darf. Gesundheits-, Schimmel- und kritische CO₂-Regeln haben immer Vorrang.</span><small>Standard: Automatisch · Prozent bezieht sich auf die aktuelle Wassermenge dieses Raums.</small></div><select id="room-threshold-mode" class="settings-input"><option value="automatic" ${(r.ventilation_threshold_mode||"automatic")==="automatic"?"selected":""}>Automatisch (empfohlen)</option><option value="percent_room_water" ${r.ventilation_threshold_mode==="percent_room_water"?"selected":""}>Prozent der Raum-Wassermenge</option><option value="fixed_ml" ${r.ventilation_threshold_mode==="fixed_ml"?"selected":""}>Fester ml-Wert</option></select></div>
            <div class="settings-field settings-field-stack"><div class="settings-field-copy"><b>Raumgrenze in Prozent</b><span>Nur im Prozentmodus. Beispiel: 5 % von 700 ml Wasser in der Raumluft ergeben 35 ml Schwelle.</span><small>Standard: 5 %</small></div><div class="settings-input-wrap"><input id="room-threshold-percent" class="settings-input" type="number" min="1" max="30" step="0.5" value="${esc(r.ventilation_threshold_percent ?? 5)}"><span>%</span></div></div>
            <div class="settings-field settings-field-stack"><div class="settings-field-copy"><b>Feste Raumgrenze</b><span>Nur im Festwertmodus. Der Raum wird ab diesem entfernbaren Potenzial eigenständig relevant.</span><small>Standard: 100 ml</small></div><div class="settings-input-wrap"><input id="room-threshold-ml" class="settings-input" type="number" min="10" max="1000" step="10" value="${esc(r.ventilation_threshold_ml ?? 100)}"><span>ml</span></div></div>
            <div class="settings-field settings-field-stack"><div class="settings-field-copy"><b>Temperatursensor</b><span>Pflichtsensor für berechnete Räume.</span><small>Standard: keiner</small></div>${entitySelect("room-temp",["sensor"],r.temperature,"temperature")}</div>
            <div class="settings-field settings-field-stack"><div class="settings-field-copy"><b>Luftfeuchtigkeitssensor</b><span>Pflichtsensor für berechnete Räume.</span><small>Standard: keiner</small></div>${entitySelect("room-humidity",["sensor"],r.humidity,"humidity")}</div>
            <div class="settings-field settings-field-stack"><div class="settings-field-copy"><b>Fenster-/Türkontakte</b><span>Mindestens ein Kontakt für berechnete Räume. Mehrfachauswahl möglich.</span><small>Standard: keiner</small></div>${entitySelect("room-contacts",["binary_sensor"],contacts,null,true)}</div>
            <div class="settings-field settings-field-stack"><div class="settings-field-copy"><b>Kontaktmodus</b><span>„Einer offen“ startet Lüften bei einem beliebigen Kontakt; „Alle offen“ erst, wenn alle gewählten Kontakte offen sind.</span><small>Standard: Einer offen · Beispiel: Bei zwei Fenstern für Querlüftung kann „Alle offen“ sinnvoll sein.</small></div><select id="room-contact-mode" class="settings-input"><option value="any" ${r.contact_mode!=="all"?"selected":""}>Einer offen genügt</option><option value="all" ${r.contact_mode==="all"?"selected":""}>Alle müssen offen sein</option></select></div>
            <div class="settings-field settings-field-stack"><div class="settings-field-copy"><b>Direktes Raumvolumen</b><span>Alternativ zu Länge × Breite × Höhe.</span><small>Standard: keiner · Beispiel: 42,5 m³</small></div><input id="room-volume" class="settings-input" type="number" min="2" max="1000" step="0.1" value="${esc(r.volume ?? "")}"></div>
            <div class="settings-dim-grid"><label>Länge<input id="room-length" class="settings-input" type="number" min="0.5" max="100" step="0.01" value="${esc(r.length ?? "")}"></label><label>Breite<input id="room-width" class="settings-input" type="number" min="0.5" max="100" step="0.01" value="${esc(r.width ?? "")}"></label><label>Höhe<input id="room-height" class="settings-input" type="number" min="1" max="20" step="0.01" value="${esc(r.height ?? "")}"></label></div>
            <div class="settings-field settings-field-stack"><div class="settings-field-copy"><b>Raum-Referenztemperatur</b><span>Optionaler Ersatz für die normale Außenluft-Temperatur dieses Raums. Sinnvoll, wenn alle Lüftungsöffnungen des Raums in denselben anderen Luftbereich führen, z. B. Wintergarten.</span><small>Standard: Außenluft · Für gemischte Öffnungen die Referenz besser direkt am jeweiligen Fenster/Türkontakt hinterlegen.</small></div>${entitySelect("room-ref-temp",["sensor"],r.reference_temperature,"temperature")}</div>
            <div class="settings-field settings-field-stack"><div class="settings-field-copy"><b>Raum-Referenzfeuchtigkeit</b><span>Gehört zur Raum-Referenztemperatur und muss denselben Luftbereich messen. FreshAirIQ berechnet daraus die absolute Feuchte der einströmenden Luft.</span><small>Standard: Außenluft · Temperatur und Feuchte immer paarweise aus derselben Referenz verwenden.</small></div>${entitySelect("room-ref-humidity",["sensor"],r.reference_humidity,"humidity")}</div>
            <div class="settings-field settings-field-stack"><div class="settings-field-copy"><b>CO₂-Sensor</b><span>Optional. TVOC gehört nicht in dieses Feld.</span><small>Standard: keiner</small></div>${entitySelect("room-co2",["sensor"],r.co2,"carbon_dioxide")}</div>
            <div class="settings-field settings-field-stack"><div class="settings-field-copy"><b>VOC-/TVOC-Sensor</b><span>Optional. Verändert keine Feuchte-, Lüftungs- oder Prognoseberechnung. Kann zusätzliche Luftqualitäts-/Luftreiniger-Empfehlungen liefern; Messwerte fließen bei aktivierter Nutzung in die lokale Diagnostik für spätere Erweiterungen ein.</span><small>Standard: keiner</small></div>${entitySelect("room-voc",["sensor"],r.voc)}</div>
            <div class="settings-field settings-field-stack"><div class="settings-field-copy"><b>PM2.5-Sensor</b><span>Optional. Verändert keine Feuchte-, Lüftungs- oder Prognoseberechnung. Kann zusätzliche Feinstaub-/Luftreiniger-Empfehlungen liefern; Messwerte fließen bei aktivierter Nutzung in die lokale Diagnostik für spätere Erweiterungen ein.</span><small>Standard: keiner</small></div>${entitySelect("room-pm25",["sensor"],r.pm25)}</div>
            <div class="settings-field settings-field-stack"><div class="settings-field-copy"><b>Helligkeitssensor</b><span>Optional. Verändert keine Feuchte-, Lüftungs- oder Prognoseberechnung. Kann Verschattungs-Empfehlungen präzisieren; Messwerte fließen bei aktivierter Nutzung in die lokale Diagnostik für spätere Erweiterungen ein.</span><small>Standard: keiner</small></div>${entitySelect("room-illuminance",["sensor"],r.illuminance,"illuminance")}</div>
            <div class="settings-field settings-field-stack"><div class="settings-field-copy"><b>Klimaanlage / HVAC</b><span>Optional. Wird als alternative Kühlmaßnahme bewertet; FreshAirIQ erfindet keine Solltemperatur.</span><small>Standard: keiner</small></div>${entitySelect("room-climate",["climate"],r.climate)}</div>
            <div class="settings-field settings-field-stack"><div class="settings-field-copy"><b>Abluftgerät</b><span>Optional. Besonders sinnvoll für Bad, Dusche, Sauna oder Küche.</span><small>Standard: keiner</small></div>${entitySelect("room-exhaust",["fan","switch"],r.exhaust_fan)}</div>
            <div class="settings-field settings-field-stack"><div class="settings-field-copy"><b>Zuluftgerät</b><span>Optional. Kann Frischluftbedarf bei erhöhtem CO₂ unterstützen.</span><small>Standard: keiner</small></div>${entitySelect("room-supply",["fan","switch"],r.supply_fan)}</div>
            <div class="settings-field settings-field-stack"><div class="settings-field-copy"><b>Lüftungs-/WRG-Gerät</b><span>Optional. Zentrale oder dezentrale mechanische Lüftung.</span><small>Standard: keiner</small></div>${entitySelect("room-ventilation-device",["fan","switch"],r.ventilation_device)}</div>
            <div class="settings-field settings-field-stack"><div class="settings-field-copy"><b>Entfeuchter</b><span>Optional. Alternative bei hoher Feuchte oder ungünstiger Außenluft.</span><small>Standard: keiner</small></div>${entitySelect("room-dehumidifier",["humidifier","fan","switch"],r.dehumidifier)}</div>
            <div class="settings-field settings-field-stack"><div class="settings-field-copy"><b>Luftbefeuchter</b><span>Optional. Wird nur bei deutlich trockener Raumluft empfohlen.</span><small>Standard: keiner</small></div>${entitySelect("room-humidifier",["humidifier","fan","switch"],r.humidifier)}</div>
            <div class="settings-field settings-field-stack"><div class="settings-field-copy"><b>Luftreiniger</b><span>Optional. Ergänzung bei Feinstaub, VOC oder Pollen-Veto.</span><small>Standard: keiner</small></div>${entitySelect("room-purifier",["fan","switch"],r.air_purifier)}</div>
            <div class="settings-field settings-field-stack"><div class="settings-field-copy"><b>Feuchtequellen</b><span>Markiere typische Feuchte- und Wärmequellen, die FreshAirIQ bei der Quellenanalyse berücksichtigen darf.</span><small>Standard: leer</small></div><select id="room-sources" class="settings-input settings-multi" multiple size="4"><option value="shower" ${(r.moisture_sources||[]).includes("shower")?"selected":""}>Dusche</option><option value="bath" ${(r.moisture_sources||[]).includes("bath")?"selected":""}>Badewanne</option><option value="sauna" ${(r.moisture_sources||[]).includes("sauna")?"selected":""}>Sauna</option><option value="cooking" ${(r.moisture_sources||[]).includes("cooking")?"selected":""}>Kochen</option></select></div>
            <div class="settings-contact-box" id="settings-contact-details"><div class="settings-field-copy"><b>Kontakte im Detail</b><span>Ausrichtung verbessert Wind-/Querlüftungsbewertung. Zusätzlich kann jede Öffnung ihre eigene Referenzluft und ihren eigenen Sonnenschutz bekommen. So kann FreshAirIQ z. B. zwei Außenfenster und eine Tür zum Wintergarten einschließlich zugehöriger Rollos korrekt unterscheiden.</span><small>Standard: normale Außenluft, kein Rollo · Abweichende Referenz nur paarweise (Temperatur + Feuchte) setzen.</small></div><div id="settings-contact-rows">${this._settingsContactRows(contacts, r)}</div></div>
            <div class="settings-room-actions"><button class="settings-save" id="settings-save-room"><ha-icon icon="mdi:content-save-outline"></ha-icon> Raum speichern</button>${existing?`<button class="settings-delete" id="settings-delete-room"><ha-icon icon="mdi:delete-outline"></ha-icon> Raum löschen</button>`:""}</div>
        </div></section>`;
    }
    _settingsPanel() {
        if (this._settingsLoading) return `<section class="info-panel settings-panel"><div class="settings-loading"><ha-icon icon="mdi:progress-clock"></ha-icon><b>Einstellungen werden geladen …</b></div></section>`;
        if (this._settingsError && !this._settingsData) return `<section class="info-panel settings-panel"><div class="settings-error"><ha-icon icon="mdi:alert-circle-outline"></ha-icon><div><b>Einstellungen konnten nicht geladen werden</b><span>${esc(this._settingsError)}</span></div><button id="settings-retry">Erneut versuchen</button></div></section>`;
        if (!this._settingsData) return `<section class="info-panel settings-panel"><div class="settings-loading"><b>Einstellungen werden vorbereitet …</b></div></section>`;
        const section = this._info === "settings" ? "home" : String(this._info || "settings").replace(/^settings:/, "");
        return `${this._settingsNotice ? `<div class="settings-toast">${esc(this._settingsNotice)}</div>` : ""}${this._settingsError ? `<div class="settings-inline-error"><ha-icon icon="mdi:alert-circle-outline"></ha-icon>${esc(this._settingsError)}</div>` : ""}${section === "home" ? this._settingsHome() : section.startsWith("group_") ? this._settingsGroupMenu(section) : this._settingsSection(section)}`;
    }
    _infoPanel(st, rooms) {
        var _a, _b, _c;
        if (!this._info)
            return "";
        if (this._info === "settings" || this._info.startsWith("settings:"))
            return this._settingsPanel();
        const r = this._info.startsWith("room:") ? rooms.find(x => x.key === this._info.slice(5)) : null;
        if (r) {
            const optionalSensorRows = [];
            if (this._config.info_voc !== false && r.voc_enabled !== false && r.voc_configured)
                optionalSensorRows.push(`<div><b><ha-icon icon="mdi:molecule"></ha-icon> ${r.voc_available ? fmt(r.voc, 0) : "–"}</b><span>VOC / TVOC · ${r.voc_available ? "Zusatzdaten aktiv" : "Sensor aktuell nicht verfügbar"}</span></div>`);
            if (this._config.info_pm25 !== false && r.pm25_enabled !== false && r.pm25_configured)
                optionalSensorRows.push(`<div><b><ha-icon icon="mdi:blur"></ha-icon> ${r.pm25_available ? `${fmt(r.pm25, 1)} µg/m³` : "–"}</b><span>PM2.5 · ${r.pm25_available ? "Zusatzdaten aktiv" : "Sensor aktuell nicht verfügbar"}</span></div>`);
            if (this._config.info_illuminance !== false && r.illuminance_enabled !== false && r.illuminance_configured)
                optionalSensorRows.push(`<div><b><ha-icon icon="mdi:white-balance-sunny"></ha-icon> ${r.illuminance_available ? `${fmt(r.illuminance, 0)} lx` : "–"}</b><span>Helligkeit · ${r.illuminance_available ? "Zusatzdaten aktiv" : "Sensor aktuell nicht verfügbar"}</span></div>`);
            const optionalSensorHtml = optionalSensorRows.length ? `<div class="room-optional-sensors"><div class="tiny">OPTIONALE ZUSATZSENSOREN · KEIN EINFLUSS AUF DIE LÜFTUNGSPHYSIK</div><div class="info-grid">${optionalSensorRows.join("")}</div></div>` : "";
            if (r.calculation_enabled === false) {
                const hasSensors = r.sensor_data_configured === true;
                const hasLiveData = r.sensor_data_available === true && Number.isFinite(Number(r.temperature)) && Number.isFinite(Number(r.humidity));
                const monitorState = hasLiveData ? "Sensorwerte verfügbar" : (hasSensors ? "Sensoren aktuell nicht verfügbar" : "Keine Klimasensoren konfiguriert");
                const monitorClass = hasLiveData ? "ok" : "warn";
                const monitorText = hasLiveData
                    ? "FreshAirIQ zeigt die echten Sensorwerte dieses Raums an. Der Raum ist bewusst von Empfehlungen, Prognosen, Hausbilanz und Lernen ausgeschlossen."
                    : hasSensors
                        ? "Der Raum ist auf „Nur anzeigen“ gestellt, aber mindestens ein zugeordneter Klimasensor liefert aktuell keinen gültigen Wert."
                        : "Dieser Strukturraum bleibt im Gebäudemodell erhalten. Es werden keine Klimawerte geschätzt oder erfunden.";
                const valueBlock = hasLiveData
                    ? `<div class="info-grid monitor-only-grid"><div><b>${fmt(r.temperature, 1)} °C / ${Math.round(Number(r.humidity))} %</b><span>${fmt(r.absolute_humidity, 2)} g/m³ absolut · ${Math.round(Number(r.water_in_air_ml || 0))} ml Wasserdampf</span></div><div><b>${esc(whenDE(r.last_measurement_at))}</b><span>Letzte echte Sensormessung</span></div></div>`
                    : `<div class="monitor-only-empty"><ha-icon icon="mdi:information-outline"></ha-icon><div><b>${esc(monitorState)}</b><span>${hasSensors ? "Bitte Verfügbarkeit und Zuordnung der Temperatur-/Feuchtesensoren prüfen." : "Bei Bedarf können unter Räume & Sensoren Temperatur- und Feuchtesensoren hinterlegt werden."}</span></div></div>`;
                const contactCount = Number(r.contact_count || 0);
                return `<section class="info-panel room-detail monitor-only-detail"><div class="tiny room-detail-label">RAUM-MONITORING</div><h3>${esc(r.name)}</h3><div class="room-iq-hero monitor-only-hero" style="--room-iq:#82929e"><div class="room-iq-icon"><ha-icon icon="mdi:eye-outline"></ha-icon></div><div><div class="tiny">FRESHAIRIQ MODUS</div><strong>Nur anzeigen</strong><span>${esc(monitorText)}</span></div><div class="room-iq-quality ${monitorClass}">${esc(monitorState)}</div></div>${valueBlock}${optionalSensorHtml}<div class="room-iq-context"><div class="tiny">RAUMMODELL</div><span>${esc(floorDE(r.floor))} · ${fmt(r.volume_m3, 1)} m³ · ${contactCount} Fenster-/Türkontakt${contactCount === 1 ? "" : "e"}</span></div></section>`;
            }
            const bal = moisture(r.result_ml), pot = moisture((_a = r.realistic_potential_ml) !== null && _a !== void 0 ? _a : r.potential_ml), eff = moisture((_b = r.forecast_moisture_effect_ml) !== null && _b !== void 0 ? _b : r.moisture_effect_next_5_min_ml);
            const dirs = Object.entries(r.contact_orientations || {}).map(([k, v]) => `${k}: ${orientationDE(v)}`).join(" · ") || "keine Richtung hinterlegt";
            const days = Number(st.statistics_days || 14), hist = r.history_14d || [], sum = hist.reduce((a, x) => ({ removed: a.removed + Number(x.removed_ml || 0), sessions: a.sessions + Number(x.sessions || 0), mins: a.mins + Number(x.ventilation_minutes || 0), cost: a.cost + Number(x.cost || 0) }), { removed: 0, sessions: 0, mins: 0, cost: 0 });
            const monitoredRoomKeys = new Set((st.intelligent_recommendation?.room_keys || []).map(String));
            const passiveOpenRoom = String(st.intelligent_recommendation?.status || st.status || "") === "passive_open_monitor" && r.active && monitoredRoomKeys.has(String(r.key));
            const actionStyle = passiveOpenRoom ? ["#63d2f7", "rgba(99,210,247,.08)", "mdi:window-open"] : styleFor(r.action), roomReasons = (r.recommendation_reasons || []).filter(Boolean);
            const qualityOk = r.data_quality === "ok" && r.last_measurement_valid !== false;
            const roomLead = passiveOpenRoom
                ? `FreshAirIQ behandelt die lange, stabile Öffnung als wahrscheinliche Dauer- oder Kipplüftung und überwacht sie weiter.`
                : r.active ? `FreshAirIQ begleitet die laufende Lüftung in diesem Raum.` : `FreshAirIQ bewertet diesen Raum fortlaufend aus Klima, Außenluft, Lernmodell und Gebäudeeigenschaften.`;
            const roomAction = passiveOpenRoom ? "Daueröffnung überwachen" : actionDE(r.action);
            return `<section class="info-panel room-detail"><div class="tiny room-detail-label">RAUM-INTELLIGENZ · ${days} TAGE</div><h3>${esc(r.name)}</h3><div class="room-iq-hero" style="--room-iq:${actionStyle[0]}"><div class="room-iq-icon"><ha-icon icon="${actionStyle[2]}"></ha-icon></div><div><div class="tiny">FRESHAIRIQ EMPFIEHLT</div><strong>${esc(roomAction)}</strong><span>${esc(roomLead)}</span></div><div class="room-iq-quality ${qualityOk ? "ok" : "warn"}">${qualityOk ? "Daten plausibel" : "Daten prüfen"}</div></div>${roomReasons.length ? `<div class="room-iq-why"><div class="tiny">WARUM?</div>${roomReasons.slice(0,4).map(x => `<div><ha-icon icon="mdi:check-circle-outline"></ha-icon><span>${esc(x)}</span></div>`).join("")}</div>` : ""}<div class="info-grid"><div><b>${fmt(r.temperature, 1)} °C / ${Math.round(Number(r.humidity || 0))} %</b><span>${fmt(r.absolute_humidity, 2)} g/m³ absolut · ${Math.round(Number(r.water_in_air_ml || 0))} ml Wasserdampf</span></div><div><b>${esc(whenDE(r.last_measurement_at))}</b><span>Letzte Messung · ${r.last_measurement_valid === false ? "Messwerte unplausibel" : "Messwerte plausibel"}</span></div><div><b style="color:${r.active ? bal.color : pot.color}">${r.active ? bal.text : pot.text}</b><span>${r.active ? "Bilanz seit Sessionstart" : "aktuell entfernbares Potenzial"}</span></div><div><b>${eff.text}</b><span>weitere ${Number(r.forecast_horizon_min || st.forecast_horizon_min || 5)} min · ${signed((_c = r.forecast_temperature_change_c) !== null && _c !== void 0 ? _c : r.temp_next_5_min_c, "°C")} · ${fmt(r.forecast_cost || 0, 2)} €</span></div><div><b>${Math.round(Number(r.surface_rh || 0))} %</b><span>Oberflächen-RH · ${esc(mouldDE(r.mould_level))}</span></div><div><b style="color:${moisture(sum.removed).color}">${sum.removed > 0 ? "−" : sum.removed < 0 ? "+" : "±"}${fmt(Math.abs(sum.removed) / 1000, 2)} l</b><span>Bilanz in ${days} Tagen</span></div><div><b>${sum.sessions}</b><span>Lüftungen · ${fmt(sum.mins, 0)} min</span></div><div><b>${fmt(sum.cost, 2)} €</b><span>geschätztes Wiederaufheizen</span></div><div><b>${Number(r.learning_samples || 0)} Proben</b><span>${esc(learnDE(r.learning_status))} · ${fmt(Number(r.learned_exchange_rate_per_min || 0) * 100, 1)} %/min</span></div>${Number(r.outcome_feedback_samples || 0) > 0 ? `<div><b>${Number(r.outcome_feedback_samples || 0)} Feedback-Proben</b><span>Prognose ↔ Realität · Treffer ${fmt(r.outcome_success_rate || 0, 0)} % · Feuchtefaktor ${fmt(r.outcome_removed_factor || 1, 2)}</span></div>` : ""}${Number(r.outcome_feedback_samples || 0) > 0 ? `<div><b>Learning 3.0 · ${r.shadow_rollback_active ? "Rollback-Schutz" : "Shadow-Modelle"}</b><span>${esc(r.shadow_learning_status || "Vergleicht Produktionsmodell mit Alternativen")} · Übernahmen ${Number(r.shadow_learning_promotions || 0)} · Rollbacks ${Number(r.shadow_learning_rollbacks || 0)}</span></div>` : ""}${Number(r.routine_source_samples || 0) > 0 ? `<div><b>Routine-IQ ${fmt(r.routine_maturity || 0, 0)} %</b><span>${Number(r.routine_source_samples || 0)} Zeitmuster-Proben${r.routine_expected_source_ml_min != null ? ` · aktuell erwartet ${signed(Number(r.routine_expected_source_ml_min || 0) * 60, " ml/h")}` : ""}</span></div>` : ""}${Number(r.strategy_samples || 0) > 0 ? `<div><b>Strategie-IQ ${fmt(r.strategy_maturity || 0, 0)} %</b><span>${Number(r.strategy_samples || 0)} Empfehlungen ausgewertet · ${Number(r.strategy_outcome_samples || 0)} Ergebnisproben</span></div>` : ""}</div>${optionalSensorHtml}<div class="last-learning" style="--learn:${r.last_learning_valid === false ? "#c97878" : r.last_learning_valid === true ? "#6fbd88" : "#82929e"}"><ha-icon icon="${r.last_learning_valid === false ? "mdi:alert-circle-outline" : r.last_learning_valid === true ? "mdi:check-circle-outline" : "mdi:brain"}"></ha-icon><div><div class="tiny">LETZTE LERNMESSUNG · ${esc(whenDE(r.last_learning_at))}</div><b>${esc(diagnosisDE(r.learning_diagnosis))}</b></div></div><div class="history-grid"><div class="history"><div class="tiny">FEUCHTE · ${days} TAGE</div><div class="chart">${this._svgBars(hist)}</div></div><div class="history"><div class="tiny">TEMPERATUR · ${days} TAGE</div><div class="chart">${this._svgLine(r.temperature_history_14d || [])}</div></div></div>${r.moisture_source_active ? `<div class="last-learning" style="--learn:#e6be62"><ha-icon icon="mdi:water-plus-outline"></ha-icon><div><div class="tiny">AKTIVE FEUCHTEQUELLE · ${Math.round(Number(r.moisture_source_confidence || 0))} % SICHERHEIT</div><b>${esc(r.moisture_source_message || `${r.moisture_source_label || "Feuchtequelle"} erkannt.`)} · ca. +${Math.round(Number(r.moisture_source_rate_ml_min || 0) * 60)} ml/h</b></div></div>` : ""}<div class="room-iq-context"><div class="tiny">RAUMMODELL</div><span>Fenster/Türen: ${esc(dirs)} · Luftstromfaktor ${fmt(r.airflow_factor, 2)} · ${esc(floorDE(r.floor))} · ${fmt(r.volume_m3, 1)} m³</span></div></section>`;
        }
        if (this._info === "moisture" && rooms.some(x => x.active)) {
            const activeRooms = rooms.filter(r => r.active);
            const houseMode = Boolean(st.house_ventilation_mode);
            const houseBalance = moisture(Number(st.live_balance_ml || 0));
            const rows = this._groupRoomsByFloor(rooms, r => {
                const passive = !r.active && Boolean(r.passive_ventilation_active);
                const value = r.active ? Number(r.result_ml || 0) : (passive ? Number(r.passive_ventilation_estimated_ml || 0) : 0);
                const m = moisture(value);
                const state = r.active ? "LÜFTUNG AKTIV" : (passive ? "PASSIV MITGELÜFTET" : "GESCHLOSSEN");
                const icon = r.active ? "mdi:window-open-variant" : (passive ? "mdi:swap-horizontal" : "mdi:window-closed-variant");
                const cls = r.active ? "vent-active" : (passive ? "vent-passive" : "vent-inactive");
                const displayValue = passive ? `≈ ${m.text}` : m.text;
                const confidence = passive ? ` · Schätzung ${Math.round(Number(r.passive_ventilation_confidence || 0))} %` : "";
                return `<div class="breakdown-row clickable ${cls}" data-room="${esc(r.key)}"><b><ha-icon icon="${icon}"></ha-icon>${esc(r.name)}</b><span>${state}${confidence}</span><strong style="color:${m.color}">${displayValue}</strong></div>`;
            });
            const houseHero = houseMode ? `<div class="house-live"><div><div class="tiny">HAUSLÜFTUNG AKTIV</div><b>${activeRooms.length} von ${rooms.filter(r=>r.calculation_enabled!==false).length} Räumen werden gelüftet</b></div><strong style="color:${houseBalance.color}">${houseBalance.text}</strong><span>Live-Bilanz für das ganze Haus</span></div>` : "";
            return `<section class="info-panel"><div class="tiny info-kicker">${houseMode ? "LIVE-FEUCHTEBILANZ · GANZES HAUS" : "LIVE-FEUCHTEBILANZ NACH RÄUMEN"}</div><h3>${houseMode ? "Hausweite Lüftung läuft" : "Wo Feuchtigkeit entweicht oder hinzukommt"}</h3><p>${houseMode ? "Bei einer großen Hauslüftung bewertet FreshAirIQ primär die gemeinsame Hauswirkung. Passiv mitgelüftete Räume werden aus ihrem eigenen Sensorverlauf erkannt und mit ≈ als Schätzung markiert; sie werden nicht doppelt zur Hausbilanz addiert." : "Aktive Lüftungen sind deutlich hervorgehoben. Passiv mitgelüftete Räume werden aus ihrem Sensorverlauf erkannt und als Schätzung markiert. Minus = entfernt, Plus = hinzugekommen."}</p>${houseHero}<div class="breakdown">${rows}</div></section>`;
        }
        if (this._info === "moisture") {
            const calc = this._orderedRooms(rooms.filter(r => r.calculation_enabled !== false && r.data_quality === "ok"));
            const rows = this._groupRoomsByFloor(calc, r => {
                var _a, _b, _c, _d;
                const potential = Number((_b = (_a = r.realistic_potential_ml) !== null && _a !== void 0 ? _a : r.potential_ml) !== null && _b !== void 0 ? _b : 0);
                const shortEffect = Number((_d = (_c = r.forecast_moisture_effect_ml) !== null && _c !== void 0 ? _c : r.moisture_effect_next_5_min_ml) !== null && _d !== void 0 ? _d : 0);
                const value = potential > .5 ? potential : (shortEffect < -.5 ? shortEffect : 0);
                const m = moisture(value);
                const label = potential > .5 ? "aktuell entfernbar" : shortEffect < -.5 ? "würde Feuchtigkeit eintragen" : "kein relevantes Potenzial";
                return `<div class="breakdown-row clickable" data-room="${esc(r.key)}"><b>${esc(r.name)}</b><span>${label}</span><strong style="color:${m.color}">${m.text}</strong></div>`;
            });
            return `<section class="info-panel"><div class="tiny info-kicker">FEUCHTEPOTENZIAL NACH RÄUMEN</div><h3>Welche Räume den Wert verursachen</h3><p>Ohne laufende Lüftung zeigt FreshAirIQ hier raumweise, wo aktuell Feuchtigkeit entfernt werden könnte oder wo Lüften Feuchtigkeit eintragen würde. Minus = entfernbar, Plus = möglicher Eintrag.</p><div class="breakdown">${rows || "<p>Keine gültigen Raumdaten vorhanden.</p>"}</div></section>`;
        }
        if (this._info === "lastvent") {
            const last = st.last_ventilation || null;
            return `<section class="info-panel"><div class="tiny info-kicker">LÜFTUNGSERGEBNIS · DAUERHAFT GESPEICHERT</div><h3>Letzte Lüftung im Detail</h3><p>Hier bleibt die zuletzt vollständig abgeschlossene Hauslüftung erhalten – auch nachdem die 5-Minuten-Ergebnisanzeige auf dem Hauptdashboard beendet ist.</p>${this._ventilationResultCard(last, "panel")}</section>`;
        }
        if (this._info === "mould") {
            const order = { "Very high": 5, "High": 4, "Elevated": 3, "Slightly elevated": 2, "Low": 1, "Unknown": 0 };
            const canonical = this._orderedRooms(rooms);
            const canonicalIndex = new Map(canonical.map((r, i) => [String(r.key || ""), i]));
            const mouldOrdered = [...canonical].sort((a, b) => (order[b.mould_level] || 0) - (order[a.mould_level] || 0) || Number(b.surface_rh || 0) - Number(a.surface_rh || 0) || (canonicalIndex.get(String(a.key || "")) || 0) - (canonicalIndex.get(String(b.key || "")) || 0));
            const rows = mouldOrdered.map(r => { const [c] = mouldStyle(r.mould_level); return `<div class="breakdown-row clickable" data-room="${esc(r.key)}"><b>${esc(r.name)}</b><span>${Math.round(Number(r.surface_rh || 0))} % Oberflächen-RH</span><strong style="color:${c}">${esc(mouldDE(r.mould_level))}</strong></div>`; }).join("");
            return `<section class="info-panel"><div class="tiny info-kicker">SCHIMMEL-IQ · RISIKO NACH RÄUMEN</div><h3>Wo FreshAirIQ genauer hinschaut</h3><p>Die Räume sind nach Risiko sortiert. <b>Wichtig: Das ist nur eine grobe Einschätzung.</b> FreshAirIQ leitet die Oberflächenfeuchte aus dem Raumklima ab. Ohne gemessene Oberflächentemperatur bzw. Taupunkt an der konkreten Bauteiloberfläche lässt sich ein tatsächliches Schimmelrisiko nicht sicher bestimmen. Tippe einen Raum an, um Ursache, Empfehlung und Lernwerte zu sehen.</p><div class="breakdown">${rows}</div></section>`;
        }
        if (this._info === "rooms") {
            const ordered = this._orderedRooms(rooms);
            const cards = this._groupRoomsByFloor(ordered, r => this._roomCard(r));
            const empty = rooms.length ? "" : `<p>Der Statussensor liefert aktuell keine Raumdaten. Bitte Home Assistant nach dem Update einmal neu starten; vorhandene Raumkonfigurationen werden dabei nicht gelöscht.</p>`;
            return `<section class="info-panel rooms-overview"><div class="tiny info-kicker">RÄUME</div><h3>Raumübersicht</h3><p class="rooms-subtitle">Aktuelle Raumwerte auf einen Blick</p>${empty}<div class="rooms">${cards}</div></section>`;
        }
        if (this._info === "guests") {
            const ga = Number(st.guest_adults || 0), gc = Number(st.guest_children || 0);
            return `<section class="info-panel"><div class="tiny info-kicker">ANWESENHEIT & GÄSTEMODUS</div><h3>Wer ist heute Nacht im Haus?</h3><p>FreshAirIQ berücksichtigt aktuell <b>${fmt(st.effective_occupants || 0, 1)} Personen</b>. Davon sind ${Number(st.home_tracked_occupants || 0)} über Home Assistant als zuhause erkannt, ${Number(st.away_tracked_occupants || 0)} als abwesend und ${Number(st.untracked_adults || 0) + Number(st.untracked_children || 0)} ohne eigenes Tracking.</p><p class="muted">Übernachtungsgäste: ${ga} Erwachsene · ${gc} Kinder. Jede Änderung kalkuliert Kurzzeit- und Nachtprognose sofort neu. Anwesenheits-IQ ${Math.round(Number(st.presence_confidence || 0))} %.</p></section>`;
        }
        if (this._info === "water") {
            const calc = rooms.filter(r => r.calculation_enabled !== false && r.data_quality === "ok");
            const total = calc.reduce((a, r) => a + Number(r.water_in_air_ml || 0), 0);
            const rows = this._orderedRooms(calc).map(r => `<div class="breakdown-row clickable" data-room="${esc(r.key)}"><b>${esc(r.name)}</b><span>${fmt(r.absolute_humidity, 1)} g/m³ · ${fmt(r.volume_m3, 1)} m³</span><strong>${Math.round(Number(r.water_in_air_ml || 0))} ml</strong></div>`).join("");
            return `<section class="info-panel"><div class="tiny info-kicker">WASSER IN DER HAUSLUFT</div><h3>${Math.round(total)} ml über ${calc.length} Räume</h3><p>FreshAirIQ berechnet die Wasserdampfmenge je Raum aus absoluter Feuchte × Raumvolumen. So wird aus Prozent Luftfeuchte ein physikalisch vergleichbarer Wert.</p><div class="breakdown">${rows || "<p>Keine gültigen Raumdaten vorhanden.</p>"}</div></section>`;
        }
        if (this._info === "decision") {
            const brain = ((st.intelligent_recommendation || {}).decision_brain || {}), why = (brain.why || (st.intelligent_recommendation || {}).reasons || []).filter(Boolean);
            return `<section class="info-panel"><div class="tiny info-kicker">IQ-ENTSCHEIDUNG</div><h3>${esc(brain.headline || (st.intelligent_recommendation || {}).title || "Aktuelle Entscheidung")}</h3><p>${esc(brain.summary || (st.intelligent_recommendation || {}).summary || "FreshAirIQ kombiniert Raumdaten, Außenluft, Prognosen und Lernwerte.")}</p>${why.length ? `<div class="room-iq-why">${why.slice(0,6).map(x => `<div><ha-icon icon="mdi:check-circle-outline"></ha-icon><span>${esc(x)}</span></div>`).join("")}</div>` : ""}<p class="muted">Die Entscheidung wird aus Gesundheit/Schimmel, Komfort, Feuchtewirkung, Temperatur und Energie priorisiert. Gelernte Gewohnheiten dürfen Sicherheitsentscheidungen nicht überstimmen.</p></section>`;
        }
        if (String(this._info || "").startsWith("learning:")) {
            const learningPanel = this._learningPanel(st);
            if (learningPanel) return learningPanel;
        }
        if (this._info === "threshold") {
            const mode = this._thresholdModeOverride || st.ventilation_threshold_mode || "adaptive_home_size";
            const modeLabel = mode === "percent_total_water" ? "Prozent der gesamten Wassermenge" : mode === "fixed_ml" ? "Fester ml-Wert" : "Automatisch nach Hausgröße & Nutzung";
            const valueControl = mode === "percent_total_water"
                ? `<label><b>Prozentwert</b><div class="settings-input-wrap"><input id="threshold-percent-direct" class="settings-input" type="number" min="1" max="30" step="0.5" value="${esc(st.ventilation_threshold_percent ?? 10)}"><span>%</span></div></label>`
                : mode === "fixed_ml"
                    ? `<label><b>Fester Wert</b><div class="settings-input-wrap"><input id="threshold-ml-direct" class="settings-input" type="number" min="50" max="5000" step="10" value="${esc((this._settingsData&&this._settingsData.options&&this._settingsData.options.min_potential_total_ml) ?? 500)}"><span>ml</span></div></label>`
                    : "";
            const applyControl = mode === "adaptive_home_size" ? "" : `<button class="profile-option" id="threshold-apply"><b>Übernehmen</b></button>`;
            return `<section class="info-panel"><div class="tiny info-kicker">LÜFTUNGSSCHWELLE</div><h3>Intelligente Lüftungsschwelle</h3><p>Lege fest, ab welchem gesamten entfernbaren Feuchtepotenzial FreshAirIQ eine Hauslüftung als sinnvoll bewertet. Aktuell: <b>${Math.round(Number(st.ventilation_threshold_ml||0))} ml</b>.</p><div class="profile-options"><label><b>Modus</b><select id="threshold-mode-direct" class="settings-input"><option value="adaptive_home_size" ${mode==="adaptive_home_size"?"selected":""}>Automatisch (empfohlen)</option><option value="percent_total_water" ${mode==="percent_total_water"?"selected":""}>Prozent der Gesamtwassermenge</option><option value="fixed_ml" ${mode==="fixed_ml"?"selected":""}>Fester ml-Wert</option></select></label>${valueControl}${applyControl}</div><p class="muted">${esc(modeLabel)}. ${mode === "percent_total_water" ? "Der Prozentwert bezieht sich auf die aktuell überwachte Wassermenge des Hauses. " : mode === "fixed_ml" ? "FreshAirIQ verwendet ausschließlich den eingestellten festen ml-Wert. " : "Automatisch: FreshAirIQ teilt die erwartete tägliche Feuchteproduktion durch vier und begrenzt die Schwelle auf 6–12 % der aktuell überwachten Wassermenge. Von Mai bis September wird sie morgens vor 09:00 Uhr bzw. abends ab 19:00 Uhr um 25 % gesenkt, wenn die Außenluft mindestens 2 °C kühler als die mittlere Raumtemperatur ist. "}Individuelle Raumgrenzen können zusätzlich in den jeweiligen Raumeinstellungen gesetzt werden. Gesundheits-, Schimmel- und kritische CO₂-Regeln haben Vorrang.</p></section>`;
        }
        const map = {
            threshold: ["Intelligente Lüftungsschwelle", `Die Lüftungsschwelle legt fest, ab welchem gesamten Feuchtepotenzial FreshAirIQ eine Hauslüftung als sinnvoll bewertet. Aktuell liegt sie bei ${Math.round(Number(st.ventilation_threshold_ml || 0))} ml.`, `Modus: ${st.ventilation_threshold_mode || "–"}. Die Raumempfehlungen können zusätzlich eigene Gesundheits- oder Schimmelgründe haben.`],
            pollen: ["Pollenbewertung", `FreshAirIQ berücksichtigt die konfigurierte Pollenbelastung als möglichen Lüftungs-Veto-Faktor.`, `Aktueller Index ${fmt(st.pollen_index, 1)} · Grenze ${fmt(st.pollen_limit, 1)} · ${st.pollen_blocked ? "Lüftung aktuell eingeschränkt" : "kein Pollen-Veto"}.`],
            moisture: ["Feuchtebilanz / entfernbar", `Während einer Lüftung zeigt der Wert die seit Beginn berechnete Feuchteänderung. Ohne aktive Lüftung zeigt er das aktuell entfernbar geschätzte Potenzial. Die aktuelle Empfehlungsschwelle liegt bei ${Math.round(Number(st.ventilation_threshold_ml || 0))} ml.`, `Schwellenmodus: ${st.ventilation_threshold_mode || "–"} · Minus = Feuchte entfernt, Plus = Feuchte eingetragen.`],
            temperature: ["Temperaturänderung", `Volumengewichtete Temperaturänderung der aktuell gelüfteten Räume seit dem jeweiligen Sessionstart.`, `Nach einem Neustart werden nur plausible, echte Sensorwerte als Startbasis akzeptiert.`],
            time: ["Lüftungszeit", `Empfohlene Dauer aus Außentemperatur, Feuchtedifferenz und den eingestellten Mindest-/Maximalzeiten.`, `Bei aktiver Lüftung wird die verbleibende bzw. überschrittene Zeit live berechnet.`],
            next5: [`Prognose weitere ${Number(st.forecast_horizon_min || 5)} Minuten`, `Rollierende Hybrid-Prognose aus gelerntem Luftwechsel, absoluter Feuchte innen/außen, zukünftiger Wetterentwicklung (falls verfügbar), aktuellem Feuchte- und Temperaturtrend, interner Feuchteproduktion, Wind/Fensterausrichtung und Querlüftung. Heizsystem und Energiepreis beeinflussen nicht die physikalische Feuchteprognose, sondern nur die separate Wärmeverlust- und Kostenschätzung.`, `Bei Horizonten über 5 Minuten simuliert FreshAirIQ den Zustand in 5-Minuten-Schritten und schätzt zusätzlich den effizienten Endpunkt innerhalb des Prognosefensters. Minus = voraussichtlich Feuchte entfernt, Plus = Feuchte kommt hinzu. Modellvertrauen aktuell ${Math.round(Number(st.forecast_confidence || 0))} %.`],
            systemcheck: ["FreshAirIQ Systemcheck", `Aktive Plausibilitäts- und Vollständigkeitsprüfung der konfigurierten Datenquellen.`, `${Number(st.system_check?.valid_rooms || 0)}/${Number(st.system_check?.configured_rooms || 0)} Räume gültig · ${Number(st.system_check?.stale_or_invalid_rooms || 0)} auffällig · Wetter ${st.system_check?.weather_available ? "verfügbar" : "fehlt"} · CO₂ in ${Number(st.system_check?.co2_rooms || 0)} Räumen · ${st.system_check?.overall || "–"}.`],
            night: ["Nachtprognose", `Intelligente Feuchteprognose bis zum relevanten Nachtende (${fmt(st.overnight_hours_remaining || 0, 1)} h).`, `Sie kombiniert aktuell erwartete Bewohner (${fmt(st.effective_occupants || 0, 1)}), Gäste, gelernte Nachtproben, aktuellen Feuchtetrend, absolute Außenfeuchte, offene Fenster, Wind, Fensterausrichtung und gelernten Luftwechsel. Wettereffekt ${Number(st.overnight_weather_effect_ml || 0) >= 0 ? "+" : ""}${Math.round(Number(st.overnight_weather_effect_ml || 0))} ml · Trendkorrektur ${Number(st.overnight_trend_effect_ml || 0) >= 0 ? "+" : ""}${Math.round(Number(st.overnight_trend_effect_ml || 0))} ml · IQ ${Math.round(Number(st.overnight_confidence || 0))} %.`], profile: ["Betriebsmodus", `Aktuell: ${profileDE(st.operating_profile)}`, `Entfeuchten priorisiert Feuchteabbau. Komfort balanciert Feuchte, Temperatur und Energie. Sommer kühlen nutzt kühle Außenluft, solange der Feuchteeintrag vertretbar bleibt.`]
        };
        const x = map[this._info] || ["FreshAirIQ Detail", "Keine weiteren Details verfügbar.", ""];
        return `<section class="info-panel"><div class="tiny info-kicker">ERKLÄRUNG</div><h3>${esc(x[0])}</h3><p>${esc(x[1])}</p><p class="muted">${esc(x[2])}</p></section>`;
    }
    _profileControls(st) { const current = this._profileValue(st); const opts = [["dehumidify", "Entfeuchten", "Feuchteabbau hat Vorrang; FreshAirIQ toleriert dafür etwas mehr Wärmeverlust."], ["comfort", "Komfort", "Ausgewogene Entscheidung aus Feuchte, Temperatur, Luftqualität und Energie."], ["summer_cooling", "Sommer kühlen", "Kühle Außenluft wird gezielt zum Absenken der Raumtemperatur genutzt, solange der Feuchteeintrag vertretbar bleibt."]]; return `<div class="profile-options">${opts.map(([v, n, d]) => `<button class="profile-option ${current === v ? "selected" : ""}" data-profile="${v}"><b>${n}</b><span>${d}</span></button>`).join("")}</div>`; }
    _forecastControls(st) { const h = this._forecastValue(st); const presets = [5, 10, 15, 30, 60]; return `<div class="profile-options"><div class="tiny">PROGNOSEZEITRAUM</div><div style="display:flex;flex-wrap:nowrap;gap:7px">${presets.map(v => `<button class="profile-option ${h === v ? "selected" : ""}" style="width:auto;flex:1 1 0;min-width:0;padding:9px 6px" data-forecast="${v}"><b>${v} min</b></button>`).join("")}</div><div style="display:flex;align-items:center;gap:10px;margin:2px 0"><span style="height:1px;flex:1;background:rgba(255,255,255,.08)"></span><span class="muted" style="font-weight:800">oder</span><span style="height:1px;flex:1;background:rgba(255,255,255,.08)"></span></div><div style="display:flex;gap:8px;align-items:center"><input id="forecast-custom" type="number" min="1" max="120" step="1" value="${h}" style="width:110px;padding:10px;border-radius:10px;border:1px solid rgba(255,255,255,.14);background:rgba(255,255,255,.04);color:inherit"><button class="profile-option" id="forecast-apply" style="width:auto"><b>Übernehmen</b></button></div><span class="muted">Schnellwahl wird sofort übernommen. Für einen beliebigen Wert von 1 bis 120 Minuten Zahl eingeben und „Übernehmen“ wählen.</span></div>`; }
    _guestControls(st) { const ov=this._guestOverride||{}; const row = (kind, label, value) => `<div style="display:grid;grid-template-columns:1fr auto auto auto;gap:8px;align-items:center"><b>${label}</b><button class="profile-option" style="width:46px;text-align:center" data-guest-kind="${kind}" data-guest-delta="-1"><b>−</b></button><strong style="min-width:28px;text-align:center;font-size:20px">${Number(ov[kind] ?? value ?? 0)}</strong><button class="profile-option" style="width:46px;text-align:center" data-guest-kind="${kind}" data-guest-delta="1"><b>+</b></button></div>`; return `<div class="profile-options"><div class="tiny">ÜBERNACHTUNGSGÄSTE</div>${row("adult", "Erwachsene", st.guest_adults)}${row("child", "Kinder", st.guest_children)}<span class="muted">Die Anzeige reagiert sofort; FreshAirIQ berechnet die Nachtprognose anschließend mit der neuen Belegung neu.</span></div>`; }
    _learningComponentsCard(st, rooms) {
        const model = st.learning_components || {};
        const backtest = st.forecast_backtest || {};
        const effectiveness = st.learning_effectiveness || {};
        const cached = this._learningCardCache;
        if (cached && cached.model === model && cached.backtest === backtest && cached.effectiveness === effectiveness) return cached.html;
        const reliability = backtest.reliability || {};
        const components = Array.isArray(model.components) ? model.components : [];
        const byKey = Object.fromEntries(components.map(c => [String(c.key || ""), c]));
        const overall = Math.max(0, Math.min(100, Number(model.overall_maturity_percent || 0)));
        const reliabilityScore = reliability.score_percent == null ? null : Math.max(0, Math.min(100, Number(reliability.score_percent)));
        const stage = model.stage_label || "Grundmodell";
        const stageCopy = model.personal_optimization_ready === true
            ? "Ich kenne inzwischen dein Zuhause und bestätigte Nutzungs- und Komfortmuster. Persönliche Optimierung ist aktiv."
            : overall < 12
                ? "Ich arbeite zunächst mit Gebäudephysik und aktuellen Messwerten. Persönliches Lernen beginnt erst mit belastbaren Beobachtungen."
                : "FreshAirIQ sammelt unabhängige Erfahrungen und bestätigt erkannte Muster Schritt für Schritt an realen Ergebnissen.";
        const pct = v => Math.max(0, Math.min(100, Number(v || 0)));
        const avg = keys => {
            const vals = keys.map(k => byKey[k]).filter(Boolean).map(c => pct(c.maturity_percent));
            return vals.length ? vals.reduce((a,b)=>a+b,0) / vals.length : 0;
        };
        const evidence = key => byKey[key] || {};
        const room = evidence("room_physics"), feedback = evidence("forecast_feedback"), routines = evidence("routines");
        const season = evidence("seasonality"), night = evidence("night_model"), house = evidence("house_strategy");
        const personal = evidence("personal_context"), strategy = evidence("user_strategy"), validation = evidence("forecast_validation");
        const roomDays = (String(room.evidence_text || "").match(/(\d+) unterschiedliche Tage/) || [])[1];
        const routineDays = Number(routines.samples || 0);
        const nightCount = Number(night.samples || 0);
        const seasonDone = Number(season.samples || 0);
        const categories = [
            ["learning:home", "mdi:home-outline", "Dein Zuhause", ["room_physics","post_close","house_strategy"], `${roomDays || 0} unterschiedliche Lerntage · ${Number(room.samples || 0)} Lernlüftungen`],
            ["learning:forecast", "mdi:chart-line", "Prognosen & Lernen", ["live_forecast","forecast_feedback","shadow_learning","forecast_validation"], `${Number(validation.samples || 0)} Realvergleiche · ${Number(effectiveness.independent_sessions || 0)} unabhängige Lüftungen · Lernwirkung ${effectiveness.improvement_percent == null ? "–" : (Number(effectiveness.improvement_percent) >= 0 ? "+" : "") + fmt(effectiveness.improvement_percent, 0) + "%"}`],
            ["learning:habits", "mdi:account-outline", "Deine Gewohnheiten", ["routines","user_strategy","personal_context"], `${routineDays} Tage · ${Number(personal.samples || 0)} Lüftungen`],
            ["learning:longterm", "mdi:leaf", "Langzeitlernen", ["seasonality","night_model"], `${seasonDone}/4 Jahreszeiten · ${nightCount}/120 Nächte`],
        ];
        const categoryHtml = categories.map(([info, icon, label, keys, detail]) => {
            const maturity = avg(keys);
            return `<button class="learning-area clickable" data-info="${info}"><span class="learning-area-icon"><ha-icon icon="${icon}"></ha-icon></span><span class="learning-area-copy"><b>${label}</b><small>${esc(detail)}</small></span><span class="learning-area-score"><b>${Math.round(maturity)} %</b><i><em style="width:${maturity}%"></em></i></span><ha-icon class="learning-area-chevron" icon="mdi:chevron-right"></ha-icon></button>`;
        }).join("");
        const activeLearning = [room, routines, night].filter(c => c && c.label).map(c => c.label).slice(0,3).join(" · ") || "Raumphysik · Prognosemodell";
        const html = `<section class="learning-overview-card"><div class="learning-overview-hero"><div class="intelligence-orbit"><ha-icon icon="mdi:brain"></ha-icon></div><div class="learning-overview-copy"><div class="tiny">FRESHAIRIQ INTELLIGENCE 2.0</div><div class="learning-overview-title"><h2>Lernt dein Zuhause kennen</h2><span>${esc(stage)}</span></div><p>${esc(stageCopy)}</p></div></div><div class="learning-kpis"><div><span><ha-icon icon="mdi:sprout-outline"></ha-icon> Erfahrungsreife</span><b>${Math.round(overall)} %</b><i><em style="width:${overall}%"></em></i></div><div><span><ha-icon icon="mdi:star-outline"></ha-icon> Prognosequalität</span><b>${reliabilityScore == null ? "–" : Math.round(reliabilityScore)+" %"}</b><i><em style="width:${reliabilityScore == null ? 0 : reliabilityScore}%"></em></i></div></div><button class="learning-now clickable" data-info="learning:quality"><ha-icon icon="mdi:lightbulb-outline"></ha-icon><span><b>Aktuell lernt FreshAirIQ</b><small>${esc(activeLearning)}</small></span><ha-icon icon="mdi:chevron-right"></ha-icon></button><div class="learning-area-head"><b>Lernfortschritt nach Bereichen</b><span>Tippe auf einen Bereich, um Details zu sehen.</span></div><div class="learning-area-list">${categoryHtml}</div><div class="learning-overview-note"><ha-icon icon="mdi:information-outline"></ha-icon><span>Reife zeigt unabhängige Erfahrung. Prognosequalität zeigt getrennt davon, wie gut Vorhersagen bisher zur Realität passen.</span></div></section>`;
        this._learningCardCache = { model, backtest, effectiveness, html };
        return html;
    }
    _learningPanel(st) {
        const model = st.learning_components || {};
        const backtest = st.forecast_backtest || {};
        const effectiveness = st.learning_effectiveness || {};
        const reliability = backtest.reliability || {};
        const components = Array.isArray(model.components) ? model.components : [];
        const byKey = Object.fromEntries(components.map(c => [String(c.key || ""), c]));
        const groups = {
            "learning:home": ["Dein Zuhause", "Raumphysik, Feuchtepuffer & Hausstrategie", "mdi:home-outline", ["room_physics","post_close","house_strategy"]],
            "learning:forecast": ["Prognosen & Lernen", "Prognosemodell, Feedback, Shadow-Lernen & Validierung", "mdi:chart-line", ["live_forecast","forecast_feedback","shadow_learning","forecast_validation"]],
            "learning:habits": ["Deine Gewohnheiten", "Tagesroutinen, Nutzerstrategie & persönlicher Kontext", "mdi:account-outline", ["routines","user_strategy","personal_context"]],
        };
        const iconMap = {room_physics:"mdi:home-analytics",post_close:"mdi:water-sync",house_strategy:"mdi:home-lightning-bolt-outline",live_forecast:"mdi:chart-bell-curve-cumulative",forecast_feedback:"mdi:chart-timeline-variant-shimmer",shadow_learning:"mdi:shield-sync-outline",forecast_validation:"mdi:target",routines:"mdi:clock-outline",user_strategy:"mdi:account-check-outline",personal_context:"mdi:account-heart-outline"};
        const componentCard = c => {
            const m = Math.max(0,Math.min(100,Number(c.maturity_percent||0)));
            return `<div class="learning-detail-card"><div class="learning-detail-icon"><ha-icon icon="${iconMap[c.key] || "mdi:brain"}"></ha-icon></div><div><div class="learning-detail-head"><b>${esc(c.label || c.key)}</b><strong>${esc(c.status || "–")}</strong></div><p>${esc(c.description || "")}</p><div class="learning-detail-progress"><i><em style="width:${m}%"></em></i><b>${Math.round(m)} % Reife</b></div><small>${esc(c.evidence_text || `${Number(c.samples||0)} ${c.evidence_label || "Proben"}`)}</small>${c.detail ? `<small>${esc(c.detail)}</small>` : ""}</div></div>`;
        };
        if (this._info === "learning:quality") {
            const score = reliability.score_percent == null ? null : Number(reliability.score_percent);
            const effect = effectiveness.improvement_percent == null ? null : Number(effectiveness.improvement_percent);
            const effectLabel = effectiveness.status_label || "Sammelt Vergleichsdaten";
            const generation = effectiveness.generation_effectiveness || {};
            const generationEffect = generation.improvement_percent == null ? null : Number(generation.improvement_percent);
            return `<section class="info-panel learning-detail-panel"><div class="tiny info-kicker">MODELLQUALITÄT & DIAGNOSE</div><h3>Wie gut FreshAirIQ aktuell vorhersagt</h3><p>Lernreife und Prognosequalität sind getrennt. Zusätzlich vergleicht FreshAirIQ jede neue geeignete Lüftung paarweise mit einem eingefrorenen, ungelernten Grundmodell. Sobald für denselben Raum eine ältere, abweichende Forecast-Generation existiert, wird außerdem die aktuelle Generation gegen diesen unmittelbaren beobachteten Vorgänger unter derselben Startlage und Messdauer replayt.</p><div class="learning-quality-grid"><div><span>Prognosegüte</span><b>${score == null ? "–" : Math.round(score)+" %"}</b></div><div><span>Betragsgenauigkeit</span><b>${reliability.magnitude_accuracy_percent == null ? "–" : fmt(reliability.magnitude_accuracy_percent,0)+" %"}</b></div><div><span>Richtung</span><b>${reliability.direction_accuracy_percent == null ? "–" : fmt(reliability.direction_accuracy_percent,0)+" %"}</b></div><div><span>MAE</span><b>${(backtest.overall||{}).moisture_mae_ml == null ? "–" : fmt((backtest.overall||{}).moisture_mae_ml,0)+" ml"}</b></div><div><span>Lernwirkung vs. Grundmodell</span><b>${effect == null ? "–" : (effect >= 0 ? "+" : "") + fmt(effect,1)+" %"}</b></div><div><span>Aktuell vs. vorherige Generation</span><b>${generationEffect == null ? "–" : (generationEffect >= 0 ? "+" : "") + fmt(generationEffect,1)+" %"}</b></div><div><span>Paarvergleiche</span><b>${Number(effectiveness.samples || 0)}</b></div><div><span>Unabhängige Lüftungen</span><b>${Number(effectiveness.independent_sessions || 0)}</b></div><div><span>Generationenvergleiche</span><b>${Number(generation.independent_sessions || 0)}</b></div><div><span>Unterschiedliche Tage</span><b>${Number(effectiveness.distinct_days || 0)}</b></div><div><span>Gelerntes Modell MAE</span><b>${effectiveness.production_mae_ml == null ? "–" : fmt(effectiveness.production_mae_ml,0)+" ml"}</b></div><div><span>Grundmodell MAE</span><b>${effectiveness.baseline_mae_ml == null ? "–" : fmt(effectiveness.baseline_mae_ml,0)+" ml"}</b></div><div><span>Aktuelle Generation MAE</span><b>${generation.current_model_mae_ml == null ? "–" : fmt(generation.current_model_mae_ml,0)+" ml"}</b></div><div><span>Vorherige Generation MAE</span><b>${generation.previous_model_mae_ml == null ? "–" : fmt(generation.previous_model_mae_ml,0)+" ml"}</b></div><div><span>95-%-Intervall Lerngewinn</span><b>${effectiveness.paired_gain_ci95_low_ml == null || effectiveness.paired_gain_ci95_high_ml == null ? "–" : signed(effectiveness.paired_gain_ci95_low_ml," ml")+" bis "+signed(effectiveness.paired_gain_ci95_high_ml," ml")}</b></div></div><div class="learning-overview-note"><ha-icon icon="mdi:compare-horizontal"></ha-icon><span><b>${esc(effectLabel)}</b> · Belegt wird eine Verbesserung erst nach mindestens ${Number((effectiveness.evidence_rules||{}).minimum_samples || 12)} geeigneten Raumvergleichen aus ${Number((effectiveness.evidence_rules||{}).minimum_independent_sessions || 8)} unabhängigen Lüftungen an ${Number((effectiveness.evidence_rules||{}).minimum_distinct_days || 4)} unterschiedlichen Tagen und einem vollständig positiven, nach Lüftungen geclusterten Fehlerintervall. Der Generationenvergleich verwendet dieselben konservativen Evidenzregeln.</span></div>${byKey.forecast_validation ? componentCard(byKey.forecast_validation) : ""}</section>`;
        }
        if (this._info === "learning:longterm") {
            const season = byKey.seasonality || {}, night = byKey.night_model || {};
            const breakdown = Array.isArray(season.season_breakdown) ? season.season_breakdown : [];
            const seasonIcon = {spring:"mdi:sprout",summer:"mdi:white-balance-sunny",autumn:"mdi:leaf-maple",winter:"mdi:snowflake"};
            const seasonCards = breakdown.length ? breakdown.map(x => `<div class="season-card ${x.optimized ? "done" : ""}"><ha-icon icon="${seasonIcon[x.key] || "mdi:leaf"}"></ha-icon><b>${esc(x.label || x.key)}</b><strong>${Number(x.observed_days||0)} / 60 Tage</strong><i><em style="width:${Math.min(100,Number(x.observed_days||0)/60*100)}%"></em></i><small>${x.optimized ? "Vollständig durchlaufen und ausreichend belegt" : Number(x.observed_days||0)>0 ? "Lernt noch" : "Noch nicht vollständig beobachtet"}</small></div>`).join("") : `<div class="learning-empty">Jahreszeiten werden mit den nächsten Beobachtungstagen aufgebaut.</div>`;
            const seasonM = Math.max(0,Math.min(100,Number(season.maturity_percent||0))), nightM = Math.max(0,Math.min(100,Number(night.maturity_percent||0)));
            return `<section class="info-panel learning-detail-panel"><div class="tiny info-kicker">LANGZEITLERNEN</div><h3>Saisonalität & Nachtmodell</h3><p>Hier zählt Zeit als echte Erfahrung: jede Nacht höchstens einmal und jede Jahreszeit erst, wenn sie vollständig durchlaufen und ausreichend mit brauchbaren Messwerten belegt wurde.</p><div class="longterm-hero"><ha-icon icon="mdi:leaf"></ha-icon><div class="longterm-hero-copy"><b>Langzeitlernen</b><span>${Math.round((seasonM+nightM)/2)} % Reife · ${Number(season.calendar_span_days||0)} Tage Kalenderabdeckung</span></div></div><div class="learning-section-title"><b>Saisonalität</b><span>${Number(season.samples||0)}/4 Jahreszeiten optimiert</span></div><div class="season-grid">${seasonCards}</div><div class="season-total"><span>Gesamtmodell Saisonalität</span><b>${Number(season.samples||0)} / 4 Jahreszeiten · ${Number(season.calendar_span_days||0)} / 365 Tage</b><i><em style="width:${seasonM}%"></em></i></div><div class="learning-section-title"><b>Nachtmodell</b><span>${esc(night.status || "Lernt noch")}</span></div><div class="night-grid"><div><strong>${Number(night.samples||0)} / 120</strong><b>Nächte gelernt</b><i><em style="width:${nightM}%"></em></i></div><div><strong>${Number(night.raw_samples||0)}</strong><b>Messupdates</b><small>${esc(night.detail || "Unterschiedliche Nächte bestimmen die Reife.")}</small></div></div><div class="learning-overview-note"><ha-icon icon="mdi:lightbulb-outline"></ha-icon><span>Hohe Pollingraten beschleunigen die Reife nicht. Entscheidend sind unterschiedliche Nächte, Tage und vollständig beobachtete Jahreszeiten.</span></div></section>`;
        }
        const group = groups[this._info];
        if (!group) return null;
        const [title, subtitle, icon, keys] = group;
        const selected = keys.map(k => byKey[k]).filter(Boolean);
        const maturity = selected.length ? selected.reduce((a,c)=>a+Number(c.maturity_percent||0),0)/selected.length : 0;
        return `<section class="info-panel learning-detail-panel"><div class="tiny info-kicker">FRESHAIRIQ INTELLIGENCE 2.0</div><div class="learning-group-hero"><ha-icon icon="${icon}"></ha-icon><div><h3>${esc(title)}</h3><p>${esc(subtitle)}</p></div><strong>${Math.round(maturity)} %</strong></div><div class="learning-detail-list">${selected.map(componentCard).join("") || `<div class="learning-empty">Noch keine Lerndaten verfügbar.</div>`}</div></section>`;
    }
    _details(st, rooms) {
        var _a, _b, _c, _d, _e, _f, _g;
        const days = Number(st.statistics_days || 14), history = st.history_14d || [], summary = st.history_summary || {};
        const configuredLevels = Array.isArray(st.levels) ? st.levels : [];
        const present = [...new Set(rooms.map(r => r.floor || "Unzugeordnet"))];
        const floors = [...configuredLevels.filter(x => present.includes(x)), ...present.filter(x => !configuredLevels.includes(x))];
        const learningRooms = rooms.filter(r => r.calculation_enabled !== false && r.data_quality === "ok");
        const learningSamples = learningRooms.reduce((a, r) => a + Number(r.learning_samples || 0), 0);
        const stableRooms = learningRooms.filter(r => Number(r.learning_samples || 0) >= 25).length;
        const veryStableRooms = learningRooms.filter(r => Number(r.learning_samples || 0) >= 50).length;
        const learningTitle = learningRooms.length && veryStableRooms === learningRooms.length ? "Sehr stabil" : learningRooms.length && stableRooms === learningRooms.length ? "Stabil" : learningSamples > 0 ? "Lernt noch" : "Grundschätzung";
        const last = st.last_ventilation || null;
        const lastCard = this._lastVentilationTile(last);
        return `<div class="modal" role="dialog" aria-modal="true"><div class="dialog"><div class="dialog-head"><button id="details-back" class="dialog-back" aria-label="Zurück"><ha-icon icon="mdi:arrow-left"></ha-icon></button><div class="dialog-head-copy"><div class="tiny">FRESHAIRIQ DETAILS</div><div class="dialog-title">Hausklima & Lüftungsintelligenz</div></div><button id="settings-gear" class="settings-gear" aria-label="FreshAirIQ Einstellungen"><ha-icon icon="mdi:cog-outline"></ha-icon></button><button id="close" class="close" aria-label="Schließen">✕</button></div><div class="dialog-scroll"><div class="overview"><div class="summary clickable" data-info="water"><div class="tiny">WASSER IN DER LUFT</div><strong>${Math.round(Number(st.total_water_ml || 0))} ml</strong><span>über berechnete Räume</span></div><div class="summary clickable" data-info="threshold"><div class="tiny">LÜFTUNGSSCHWELLE</div><strong>${Math.round(Number(st.ventilation_threshold_ml || 0))} ml</strong><span>${st.ventilation_threshold_mode === "adaptive_home_size" ? "adaptiv · Ziel ca. 3–5×/Tag" : `${fmt(st.ventilation_threshold_percent || 10, 1)} % der Wassermenge`}</span></div><div class="summary clickable" data-info="night"><div class="tiny">NACHTPROGNOSE</div><strong style="color:#ff9b7a">+${Math.round(Number(st.overnight_forecast_ml || 0))} ml</strong><span>${Number(st.night_model_samples || 0)} Lernproben</span></div><div class="summary clickable" data-info="pollen"><div class="tiny">POLLEN</div><strong style="color:${st.pollen_blocked ? "#ff7770" : "#67df92"}">${st.pollen_enabled ? fmt(st.pollen_index, 1) : "aus"}</strong><span>${st.pollen_enabled ? `Grenze ${fmt(st.pollen_limit, 1)}` : "nicht berücksichtigt"}</span></div></div><div class="history-grid"><div class="history"><div class="history-head"><div><div class="tiny">LETZTE ${days} TAGE</div><b>Wasser in der Hausluft · Tagesmittel</b></div><strong>${fmt(Number(((_a = lastItem((st.water_history_14d || []).filter(x => x.samples > 0))) === null || _a === void 0 ? void 0 : _a.water_ml) || 0) / 1000, 2)} l</strong></div><div class="chart">${this._svgBars(st.water_history_14d || [])}</div><div class="muted">Absolute Feuchte × Raumvolumen, über alle überwachten Räume aggregiert. Tageswert = Mittel aller gültigen Messungen; Trend: ${esc(((_b = lastItem((st.water_history_14d || []).filter(x => x.samples > 0))) === null || _b === void 0 ? void 0 : _b.trend) || "stabil")}.</div></div><div class="history"><div class="history-head"><div><div class="tiny">ANWESENHEIT</div><b>Anwesenheit & Bewohner</b></div><strong>${Number(st.presence_confidence || 0) >= 80 ? "sicher erkannt" : Number(st.presence_confidence || 0) >= 55 ? "wahrscheinlich" : "noch unsicher"}</strong></div><div class="muted">${fmt(st.effective_occupants || 0, 1)} Personen aktuell zuhause/erwartet · ${Number(st.adult_occupants || 0)} Erwachsene · ${Number(st.child_occupants || 0)} Kinder · Gäste ${Number(st.guest_adults || 0)}+${Number(st.guest_children || 0)}</div><div class="muted">FreshAirIQ nutzt die Anwesenheit für Nachtprognose und Belegungsmodell.${st.pets_in_household ? " Haustiermodus ist aktiv; reine Bewegung wird vorsichtiger bewertet." : ""}</div></div></div>${this._learningComponentsCard(st, rooms)}${lastCard}<div class="history" style="margin-top:8px"><div class="history-head"><div><div class="tiny">DIAGNOSE & TEST</div><b>FreshAirIQ Testaufzeichnung</b></div><strong style="color:${((_c = st.diagnostics) === null || _c === void 0 ? void 0 : _c.last_error) ? "#ff7770" : "#67df92"}">${((_d = st.diagnostics) === null || _d === void 0 ? void 0 : _d.last_error) ? "Fehler" : "Aktiv"}</strong></div><div class="muted">FreshAirIQ protokolliert anonymisierte Mess-, Prognose-, Entscheidungs- und Lerndaten rollierend für ${Number(((_e = st.diagnostics) === null || _e === void 0 ? void 0 : _e.retention_days) || 30)} Tage. Für Feldtests werden zusätzlich eine dauerhaft zufällige Installationskennung, Home-Assistant-/Systemversionen sowie anonymisierte Geräte-/Plattformdaten erfasst. Keine Home-Assistant Entity-IDs, Zugangsdaten, Koordinaten, Gerätenamen oder Seriennummern werden exportiert. Raumnamen bleiben für die Auswertung erhalten.</div><div style="display:flex;align-items:center;justify-content:space-between;gap:10px;margin-top:10px"><span class="muted">${((_f = st.diagnostics) === null || _f === void 0 ? void 0 : _f.last_recorded_at) ? `Letzter Datensatz ${esc(whenDE(st.diagnostics.last_recorded_at))}` : "Aufzeichnung startet mit dem nächsten Datenzyklus"}</span><button class="quick-forecast" id="diagnostics-export"><ha-icon icon="mdi:download"></ha-icon><b>Diagnosedaten</b><span>exportieren</span></button></div>${((_g = st.diagnostics) === null || _g === void 0 ? void 0 : _g.last_error) ? `<div class="muted" style="color:#ff7770;margin-top:6px">${esc(st.diagnostics.last_error)}</div>` : ""}</div></div></div></div>`;
    }
    async _exportDiagnostics() {
        var _a;
        const button = (_a = this.shadowRoot) === null || _a === void 0 ? void 0 : _a.getElementById("diagnostics-export");
        const original = button === null || button === void 0 ? void 0 : button.innerHTML;
        try {
            if (button)
                button.innerHTML = '<ha-icon icon="mdi:progress-clock"></ha-icon><b>Export wird erstellt</b><span>bitte warten</span>';
            await this._registerFieldTestClient(true);
            const payload = await this._hass.callApi("GET", "freshairiq/diagnostics");
            const stamp = new Date().toISOString().split(":").join("-").replace(/\.\d{3}Z$/, "Z");
            const blob = new Blob([JSON.stringify(payload, null, 2)], { type: "application/json;charset=utf-8" });
            const url = URL.createObjectURL(blob);
            const a = document.createElement("a");
            a.href = url;
            a.download = `FreshAirIQ-diagnostics-${stamp}.json`;
            a.style.display = "none";
            document.body.appendChild(a);
            a.click();
            a.remove();
            setTimeout(() => URL.revokeObjectURL(url), 30000);
            if (button)
                button.innerHTML = '<ha-icon icon="mdi:check-circle-outline"></ha-icon><b>Export erstellt</b><span>Datei ist bereit</span>';
            setTimeout(() => { if (button && original)
                button.innerHTML = original; }, 1800);
        }
        catch (err) {
            console.error("FreshAirIQ diagnostics export failed", err);
            if (button)
                button.innerHTML = '<ha-icon icon="mdi:alert-circle-outline"></ha-icon><b>Export fehlgeschlagen</b><span>erneut versuchen</span>';
            setTimeout(() => { if (button && original)
                button.innerHTML = original; }, 2500);
        }
    }
    _render() {
        this._cancelQueuedRender();
        this._cancelQueuedLiveRefresh();
        this._liveViewSnapshot = null;
        this._liveHtmlCache = {};
        var _a, _b, _c, _d, _e, _f, _g, _h, _j, _k, _l, _m, _o, _p, _q, _r, _s, _t, _u, _v, _w;
        if (!this.shadowRoot)
            return;
        const oldDialog = this.shadowRoot.querySelector(".dialog-scroll");
        if (oldDialog)
            this._dialogScrollTop = oldDialog.scrollTop;
        const oldSubdialog = this.shadowRoot.querySelector(".subdialog");
        if (oldSubdialog) {
            this._subdialogScrollTop = oldSubdialog.scrollTop;
            if (this._info) { if (!this._infoScrollByView) this._infoScrollByView = new Map(); this._infoScrollByView.set(this._info, oldSubdialog.scrollTop); }
        }
        const oldScroll = this._forceDialogTop ? 0 : this._dialogScrollTop;
        const oldSubScroll = this._pendingSubdialogScrollTop !== null
            ? this._pendingSubdialogScrollTop
            : (this._info ? ((this._infoScrollByView && this._infoScrollByView.get(this._info)) ?? this._subdialogScrollTop) : this._subdialogScrollTop);
        this._pendingSubdialogScrollTop = null;
        this._forceDialogTop = false;
        const entity = this._statusEntity();
        if (!entity) {
            this._replaceRenderedContent(`<ha-card><div style="padding:16px">FreshAirIQ wartet auf die Status-Entität.</div></ha-card>`);
            return;
        }
        this._ensureRelevantStateIds(entity);
        const st = Object.assign({}, entity.attributes || {});
        if (this._postResultTimer) { clearTimeout(this._postResultTimer); this._postResultTimer = null; }
        if (!this._info && !this._dialogOpen) {
            const recent = this._recentVentilation(st);
            if (recent && Number(recent._remainingMs) > 0) {
                this._postResultTimer = setTimeout(() => { this._postResultTimer = null; if (!this._info && !this._dialogOpen) this._render(); }, Number(recent._remainingMs) + 80);
            }
        }
        let rooms = Object.values(st.rooms || {}).filter(r => r && typeof r === "object");
        // The coordinator publishes an explicit canonical key order. Never infer
        // presentation order from object insertion order or transient per-room
        // entity updates; that was the reason rooms such as Wintergarten could
        // jump to a different position on mobile clients.
        const configuredOrder = Array.isArray(st.room_sort_order) ? st.room_sort_order.map(String) : [];
        const canonicalOrder = new Map(configuredOrder.map((key, index) => [key, index]));
        if (!canonicalOrder.size) this._orderedRooms(rooms).forEach((room, index) => canonicalOrder.set(String(room.key || ""), index));
        const byKey = new Map(rooms.map(r => [String(r.key || ""), r]));
        const activeEntryId = st.freshairiq_entry_id || null;
        const roomStateIds = this._roomEntityIds && this._roomEntityIds.size ? this._roomEntityIds : null;
        const roomStates = roomStateIds ? Array.from(roomStateIds, id => this._hass.states[id]).filter(Boolean) : Object.values(((_a = this._hass) === null || _a === void 0 ? void 0 : _a.states) || {});
        for (const s of roomStates) {
            const a = (s === null || s === void 0 ? void 0 : s.attributes) || {}, r = a.freshairiq_room_payload;
            if (!r || !["room_v1", "room_v2"].includes(a.freshairiq_transport))
                continue;
            if (activeEntryId) {
                if (a.freshairiq_transport !== "room_v2" || a.freshairiq_entry_id !== activeEntryId)
                    continue;
            }
            const key = String(r.key || a.freshairiq_room_key || "");
            if (!key)
                continue;
            const base = byKey.get(key) || {};
            byKey.set(key, Object.assign({}, base, r));
        }
        rooms = Array.from(byKey.values()).filter(r => r && r.key);
        if (rooms.length && !Number(st.total_water_ml)) {
            st.total_water_ml = rooms.filter(r => r.calculation_enabled !== false && r.data_quality === "ok").reduce((a, r) => a + Number(r.water_in_air_ml || 0), 0);
        }
        rooms.sort((a, b) => {
            const ai = canonicalOrder.has(String(a.key || "")) ? canonicalOrder.get(String(a.key || "")) : Number(a.sort_order ?? 9999);
            const bi = canonicalOrder.has(String(b.key || "")) ? canonicalOrder.get(String(b.key || "")) : Number(b.sort_order ?? 9999);
            return ai - bi || String(a.name || a.key || "").localeCompare(String(b.name || b.key || ""), "de");
        });
        const potential = Number((_b = st.potential_total_ml) !== null && _b !== void 0 ? _b : this._num("sensor.freshairiq_removable_moisture")), live = Number((_c = st.live_balance_ml) !== null && _c !== void 0 ? _c : this._num("sensor.freshairiq_live_moisture_balance")), next5Effect = Number((_e = (_d = st.forecast_moisture_effect_ml) !== null && _d !== void 0 ? _d : st.next_5_min_effect_ml) !== null && _e !== void 0 ? _e : this._num("sensor.freshairiq_next_5_minutes")), duration = Number((_f = st.recommended_duration_min) !== null && _f !== void 0 ? _f : this._num("sensor.freshairiq_recommended_ventilation_duration")), remaining = Number((_g = st.remaining_duration_min) !== null && _g !== void 0 ? _g : this._num("sensor.freshairiq_ventilation_time_remaining")), tempChange = Number((_h = st.temperature_change_live_c) !== null && _h !== void 0 ? _h : this._num("sensor.freshairiq_temperature_change_since_ventilation_start")), overnight = Number((_j = st.overnight_forecast_ml) !== null && _j !== void 0 ? _j : this._num("sensor.freshairiq_overnight_moisture_forecast"));
        const active = rooms.filter(r => r.active && r.calculation_enabled !== false), hero = this._hero(st, rooms, live, potential), balance = moisture(live), pot = moisture(potential), next = moisture(next5Effect), night = { text: `+${Math.abs(Math.round(overnight))} ml`, color: "#ff9b7a" };
        const mouldRooms = rooms.filter(r => r.calculation_enabled !== false && ["Elevated", "High", "Very high"].includes(r.mould_level));
        const mouldWorst = rooms.reduce((a, r) => Number(r.surface_rh || 0) > Number(a.surface_rh || 0) ? r : a, { surface_rh: 0, mould_level: "Low" });
        const [mouldColor] = mouldStyle(mouldWorst.mould_level);
        const profile = this._profileValue(st), forecastH = this._forecastValue(st), activeCosts = Number((_k = st.forecast_cost) !== null && _k !== void 0 ? _k : active.reduce((a, r) => { var _a, _b; return a + Number((_b = (_a = r.forecast_cost) !== null && _a !== void 0 ? _a : r.next_5_min_cost) !== null && _b !== void 0 ? _b : 0); }, 0)), activeTemp = Number((_l = st.forecast_temperature_change_c) !== null && _l !== void 0 ? _l : (active.length ? active.reduce((a, r) => { var _a, _b; return a + Number((_b = (_a = r.forecast_temperature_change_c) !== null && _a !== void 0 ? _a : r.temp_next_5_min_c) !== null && _b !== void 0 ? _b : 0) * Number(r.volume_m3 || 0); }, 0) / Math.max(active.reduce((a, r) => a + Number(r.volume_m3 || 0), 0), 1) : 0));
        const timeText = active.length ? (remaining >= 0 ? `${Math.ceil(remaining)} min übrig` : `${Math.abs(Math.round(remaining))} min drüber`) : `${Math.round(duration)} min`;
        const moistureMain = active.length ? balance : pot;
        const rec = st.intelligent_recommendation || {};
        const intelligentPanel = this._intelligentPanel(st, rooms);
        const showBranding = this._config.show_branding !== false;
        const showProfileBadge = this._config.show_profile_badge !== false;
        const topBar = showBranding || showProfileBadge ? `<div class="top ai-top${showBranding ? "" : " profile-only"}">${showBranding ? `<img class="logo" src="/freshairiq/frontend/freshairiq-icon.png" alt="FreshAirIQ"><div><div class="brand">FreshAir<span class="iq">IQ</span></div><div class="brand-subtitle">INTELLIGENT HOME CLIMATE</div></div>` : ""}${showProfileBadge ? `<div class="pill" data-info="profile">${esc(profileDE(profile))}</div>` : ""}</div>` : "";
        this.style.setProperty("--faiq-hero-color", hero.color);
        this.style.setProperty("--faiq-hero-bg", `${hero.color}12`);
        this.style.setProperty("--faiq-hero-border", `${hero.color}2a`);
        this._replaceRenderedContent(`<ha-card><div class="card">${topBar}${intelligentPanel}${(this._config.show_details_button !== false || this._config.show_guests_button !== false || this._config.show_rooms_button !== false) ? `<div class="actions compact-actions">${this._config.show_details_button === false ? "" : `<button class="details-btn" id="details">Details</button>`}${this._config.show_guests_button === false ? "" : `<button class="details-btn" id="guests">Gäste</button>`}${this._config.show_rooms_button === false ? "" : `<button class="details-btn" id="rooms">Räume</button>`}</div>` : ""}</div>${this._dialogOpen ? this._details(st, rooms) : ""}${this._info ? `<div class="submodal" id="submodal"><div class="subdialog">${this._infoNav()}${this._infoPanel(st, rooms)}${this._info === "profile" ? this._profileControls(st) : ""}${this._info === "next5" ? this._forecastControls(st) : ""}${this._info === "guests" ? this._guestControls(st) : ""}</div></div>` : ""}</ha-card>`);
        (_m = this.shadowRoot.getElementById("details")) === null || _m === void 0 ? void 0 : _m.addEventListener("click", e => { e.stopPropagation(); this._captureOverlayViewport(); this._dialogOpen = true; this._info = null; this._render(); });
        (_o = this.shadowRoot.getElementById("rooms")) === null || _o === void 0 ? void 0 : _o.addEventListener("click", e => { e.stopPropagation(); this._captureOverlayViewport(); clearTimeout(this._deferredRender); this._deferredRender = null; this._resetInfoNavigation(); this._info = "rooms"; this._render(); });
        (_p = this.shadowRoot.getElementById("guests")) === null || _p === void 0 ? void 0 : _p.addEventListener("click", e => { e.stopPropagation(); this._captureOverlayViewport(); this._resetInfoNavigation(); this._info = "guests"; this._render(); });
        (_q = this.shadowRoot.getElementById("close")) === null || _q === void 0 ? void 0 : _q.addEventListener("click", e => { e.stopPropagation(); this._dialogOpen = false; this._info = null; this._infoStack = []; this._render(); this._restoreOverlayViewport(); });
        const detailsBack = this.shadowRoot.getElementById("details-back");
        if (detailsBack) detailsBack.addEventListener("click", e => { e.stopPropagation(); this._dialogOpen = false; this._info = null; this._infoStack = []; this._render(); this._restoreOverlayViewport(); });
        (_r = this.shadowRoot.getElementById("diagnostics-export")) === null || _r === void 0 ? void 0 : _r.addEventListener("click", async (e) => { e.stopPropagation(); await this._exportDiagnostics(); });
        const settingsGear = this.shadowRoot.getElementById("settings-gear");
        if (settingsGear) settingsGear.addEventListener("click", async (e) => {
            e.stopPropagation();
            this._infoStack = [];
            this._subdialogScrollTop = 0;
            this._settingsError = null;
            this._settingsNotice = null;
            this._settingsData = null;
            this._info = "settings";
            this._render();
            await this._loadSettings(true);
        });
        const feedbackSend = this.shadowRoot.getElementById("feedback-send");
        if (feedbackSend) feedbackSend.addEventListener("click", async (e) => {
            e.stopPropagation(); const entryId=this._settingsEntryId(); const type=this.shadowRoot.getElementById("feedback-type")?.value||"bug"; const message=(this.shadowRoot.getElementById("feedback-message")?.value||"").trim(); const result=this.shadowRoot.getElementById("feedback-result");
            if (!entryId || message.length < 3) { if(result) result.textContent="Bitte eine Beschreibung mit mindestens 3 Zeichen eingeben."; return; }
            feedbackSend.disabled=true; if(result) result.textContent="Wird sicher an den Diagnose-Hub übertragen …";
            try { const response=await this._hass.callApi("POST", `freshairiq/feedback/${entryId}`, {type,message,client_context:this._fieldTestClientContext()}); if(response?.error) throw new Error(response.error); if(result) result.textContent=`Gesendet · Feedback-ID ${response.feedback_id||"erstellt"}`; const box=this.shadowRoot.getElementById("feedback-message"); if(box) box.value=""; } catch(err) { if(result) result.textContent=`Senden fehlgeschlagen: ${err?.message||err}`; } finally { feedbackSend.disabled=false; }
        });
        const settingsRetry = this.shadowRoot.getElementById("settings-retry");
        if (settingsRetry) settingsRetry.addEventListener("click", async (e) => { e.stopPropagation(); await this._loadSettings(true); });
        this.shadowRoot.querySelectorAll("[data-settings-section]").forEach(el => el.addEventListener("click", e => {
            e.stopPropagation();
            const section = el.dataset.settingsSection;
            if (!section) return;
            if (this._info) this._infoStack.push(this._info);
            this._subdialogScrollTop = 0;
            this._settingsError = null;
            this._info = `settings:${section}`;
            this._render();
        }));
        this.shadowRoot.querySelectorAll("[data-setting-control]").forEach(el => el.addEventListener("change", async e => {
            e.stopPropagation();
            const scope = el.dataset.settingScope;
            const key = el.dataset.settingKey;
            const type = el.dataset.settingType;
            let value;
            if (type === "boolean") value = !!el.checked;
            else if (type === "multi-entity" || type === "multi-select") value = Array.from(el.selectedOptions || []).map(x => x.value);
            else if (type === "number") value = el.value === "" ? null : Number(el.value);
            else value = el.value;
            await this._settingsPost({ action: scope === "data" ? "set_data" : "set_option", key, value }, true);
        }));
        this.shadowRoot.querySelectorAll("[data-resident-profile]").forEach(el => el.addEventListener("change", async e => {
            e.stopPropagation();
            const slot = el.dataset.residentSlot;
            const field = el.dataset.residentField;
            if (!slot || !field) return;
            const profiles = this._residentProfileMap();
            const profile = Object.assign({name:"", room_keys:[], thermal_preference:"inherit", notification_targets:[]}, profiles[slot] || {});
            profile.name = el.dataset.residentName || profile.name || "";
            if (field === "room_keys") profile.room_keys = Array.from(el.selectedOptions || []).map(x => x.value);
            else if (field === "notification_targets") profile.notification_targets = Array.from(el.selectedOptions || []).map(x => x.value);
            else profile.thermal_preference = el.value || "inherit";
            profiles[slot] = profile;
            await this._settingsPost({action:"set_option", key:"resident_room_profiles", value:JSON.stringify(profiles)}, true);
        }));
        this.shadowRoot.querySelectorAll("[data-settings-room]").forEach(el => el.addEventListener("click", e => {
            e.stopPropagation();
            const key = el.dataset.settingsRoom || "new";
            if (this._info) this._infoStack.push(this._info);
            this._subdialogScrollTop = 0;
            this._settingsError = null;
            this._info = `settings:room:${key}`;
            this._render();
        }));
        this.shadowRoot.querySelectorAll("[data-room-move]").forEach(el => el.addEventListener("click", async e => {
            e.stopPropagation();
            const d = (this._settingsData && this._settingsData.data) || {};
            const roomsOrder = this._orderedRooms(d.rooms || []).map(r => r.key);
            const index = roomsOrder.indexOf(el.dataset.roomKey);
            const next = el.dataset.roomMove === "up" ? index - 1 : index + 1;
            if (index < 0 || next < 0 || next >= roomsOrder.length) return;
            [roomsOrder[index], roomsOrder[next]] = [roomsOrder[next], roomsOrder[index]];
            await this._settingsPost({ action: "reorder_rooms", order: roomsOrder });
        }));
        const saveLevels = this.shadowRoot.getElementById("settings-save-levels");
        if (saveLevels) saveLevels.addEventListener("click", async e => {
            e.stopPropagation();
            const input = this.shadowRoot.getElementById("settings-levels");
            const entered = String(input ? input.value : "").split(/\r?\n/).map(x => x.trim()).filter(Boolean);
            const currentLevels = Array.isArray((((this._settingsData || {}).data || {}).levels)) ? this._settingsData.data.levels : [];
            const levels = entered.map(label => currentLevels.find(raw => floorDE(raw) === label) || label);
            await this._settingsPost({ action: "set_levels", levels });
        });
        const roomContacts = this.shadowRoot.getElementById("room-contacts");
        if (roomContacts) roomContacts.addEventListener("change", e => {
            e.stopPropagation();
            const rowsHost = this.shadowRoot.getElementById("settings-contact-rows");
            if (!rowsHost) return;
            const root = this.shadowRoot.querySelector(".room-form");
            const roomKey = root && root.dataset.roomKey ? root.dataset.roomKey : "";
            const saved = ((((this._settingsData || {}).data || {}).rooms) || []).find(r => String(r.key) === roomKey) || {};
            const orientations = Object.assign({}, saved.contact_orientations || {});
            const delays = Object.assign({}, saved.contact_delays || {});
            const refTemps = Object.assign({}, saved.contact_reference_temperatures || {});
            const refHumidity = Object.assign({}, saved.contact_reference_humidities || {});
            const contactCovers = Object.assign({}, saved.contact_covers || {});
            rowsHost.querySelectorAll(".settings-contact-row").forEach(row => {
                const contact = row.dataset.contact;
                if (!contact) return;
                const orient = row.querySelector(".room-contact-orientation");
                const delay = row.querySelector(".room-contact-delay");
                const refTemp = row.querySelector(".room-contact-ref-temp");
                const refHum = row.querySelector(".room-contact-ref-humidity");
                const covers = row.querySelector(".room-contact-covers");
                orientations[contact] = orient ? orient.value : "unknown";
                delays[contact] = delay ? Number(delay.value || 0) : 0;
                refTemps[contact] = refTemp ? refTemp.value : "";
                refHumidity[contact] = refHum ? refHum.value : "";
                contactCovers[contact] = covers ? Array.from(covers.selectedOptions || []).map(x => x.value) : [];
            });
            const contacts = Array.from(roomContacts.selectedOptions || []).map(x => x.value);
            rowsHost.innerHTML = this._settingsContactRows(contacts, {contact_orientations: orientations, contact_delays: delays, contact_reference_temperatures: refTemps, contact_reference_humidities: refHumidity, contact_covers: contactCovers});
        });
        const saveRoom = this.shadowRoot.getElementById("settings-save-room");
        if (saveRoom) saveRoom.addEventListener("click", async e => {
            e.stopPropagation();
            const root = this.shadowRoot.querySelector(".room-form");
            const get = id => this.shadowRoot.getElementById(id);
            const multi = id => Array.from((get(id) && get(id).selectedOptions) || []).map(x => x.value);
            const room = {
                key: root && root.dataset.roomKey ? root.dataset.roomKey : undefined,
                name: get("room-name") ? get("room-name").value.trim() : "",
                floor: get("room-floor") ? get("room-floor").value : "Unzugeordnet",
                include_in_calculations: !!(get("room-include") && get("room-include").checked),
                ventilation_threshold_mode: get("room-threshold-mode") ? get("room-threshold-mode").value : "automatic",
                ventilation_threshold_percent: get("room-threshold-percent") ? Number(get("room-threshold-percent").value || 5) : 5,
                ventilation_threshold_ml: get("room-threshold-ml") ? Number(get("room-threshold-ml").value || 100) : 100,
                temperature: get("room-temp") ? get("room-temp").value : "",
                humidity: get("room-humidity") ? get("room-humidity").value : "",
                contacts: multi("room-contacts"),
                contact_mode: get("room-contact-mode") ? get("room-contact-mode").value : "any",
                volume: get("room-volume") && get("room-volume").value !== "" ? Number(get("room-volume").value) : null,
                length: get("room-length") && get("room-length").value !== "" ? Number(get("room-length").value) : null,
                width: get("room-width") && get("room-width").value !== "" ? Number(get("room-width").value) : null,
                height: get("room-height") && get("room-height").value !== "" ? Number(get("room-height").value) : null,
                reference_temperature: get("room-ref-temp") ? get("room-ref-temp").value : "",
                reference_humidity: get("room-ref-humidity") ? get("room-ref-humidity").value : "",
                co2: get("room-co2") ? get("room-co2").value : "",
                voc: get("room-voc") ? get("room-voc").value : "",
                pm25: get("room-pm25") ? get("room-pm25").value : "",
                illuminance: get("room-illuminance") ? get("room-illuminance").value : "",
                climate: get("room-climate") ? get("room-climate").value : "",
                exhaust_fan: get("room-exhaust") ? get("room-exhaust").value : "",
                supply_fan: get("room-supply") ? get("room-supply").value : "",
                ventilation_device: get("room-ventilation-device") ? get("room-ventilation-device").value : "",
                dehumidifier: get("room-dehumidifier") ? get("room-dehumidifier").value : "",
                humidifier: get("room-humidifier") ? get("room-humidifier").value : "",
                air_purifier: get("room-purifier") ? get("room-purifier").value : "",
                moisture_sources: multi("room-sources"),
                contact_delays: {},
                contact_orientations: {},
                contact_reference_temperatures: {},
                contact_reference_humidities: {},
                contact_covers: {},
            };
            this.shadowRoot.querySelectorAll(".settings-contact-row").forEach(row => {
                const contact = row.dataset.contact;
                const orient = row.querySelector(".room-contact-orientation");
                const delay = row.querySelector(".room-contact-delay");
                const refTemp = row.querySelector(".room-contact-ref-temp");
                const refHum = row.querySelector(".room-contact-ref-humidity");
                const covers = row.querySelector(".room-contact-covers");
                if (contact) {
                    room.contact_orientations[contact] = orient ? orient.value : "unknown";
                    room.contact_delays[contact] = delay ? Number(delay.value || 0) : 0;
                    if (refTemp && refTemp.value) room.contact_reference_temperatures[contact] = refTemp.value;
                    if (refHum && refHum.value) room.contact_reference_humidities[contact] = refHum.value;
                    const selectedCovers = covers ? Array.from(covers.selectedOptions || []).map(x => x.value) : [];
                    if (selectedCovers.length) room.contact_covers[contact] = selectedCovers;
                }
            });
            const ok = await this._settingsPost({ action: "upsert_room", room });
            if (ok) {
                this._subdialogScrollTop = 0;
                this._info = "settings:rooms";
                this._infoStack = ["settings"];
                this._render();
            }
        });
        const deleteRoom = this.shadowRoot.getElementById("settings-delete-room");
        if (deleteRoom) deleteRoom.addEventListener("click", async e => {
            e.stopPropagation();
            const root = this.shadowRoot.querySelector(".room-form");
            const key = root && root.dataset.roomKey;
            if (!key || !window.confirm("Diesen Raum wirklich aus FreshAirIQ entfernen?")) return;
            const ok = await this._settingsPost({ action: "delete_room", room_key: key });
            if (ok) {
                this._subdialogScrollTop = 0;
                this._info = "settings:rooms";
                this._infoStack = ["settings"];
                this._render();
            }
        });
        this.shadowRoot.querySelectorAll("[data-settings-action]").forEach(el => el.addEventListener("click", async e => {
            e.stopPropagation();
            const action = el.dataset.settingsAction;
            const text = action === "reset_learning" ? "Alle gelernten FreshAirIQ-Daten wirklich löschen?" : "Alle FreshAirIQ-Optionen wirklich auf Standardwerte zurücksetzen? Räume und Sensoren bleiben erhalten.";
            if (!window.confirm(text)) return;
            await this._settingsPost({ action });
        }));
        (_s = this.shadowRoot.getElementById("info-close")) === null || _s === void 0 ? void 0 : _s.addEventListener("click", e => { e.stopPropagation(); this._info = null; this._resetInfoNavigation(); this._render(); this._restoreOverlayViewport(); });
        (_t = this.shadowRoot.getElementById("info-back")) === null || _t === void 0 ? void 0 : _t.addEventListener("click", e => { e.stopPropagation(); clearTimeout(this._deferredRender); this._deferredRender = null; this._rememberInfoViewport(this._info); const stackTop = this._infoScrollStack.length ? this._infoScrollStack.pop() : 0; const parent = this._infoStack.length ? this._infoStack.pop() : null; const restoreTop = parent ? ((this._infoScrollByView && this._infoScrollByView.get(parent)) ?? stackTop) : 0; this._info = parent; this._pendingSubdialogScrollTop = restoreTop; this._render(); });
        const thresholdMode = this.shadowRoot.getElementById("threshold-mode-direct");
        if (thresholdMode) thresholdMode.addEventListener("change", async e => {
            e.stopPropagation();
            const selected = thresholdMode.value || "adaptive_home_size";
            this._thresholdModeOverride = selected;
            if (selected === "adaptive_home_size") {
                const ok = await this._settingsPost({action:"set_option", key:"threshold_mode", value:selected}, true);
                if (ok) this._thresholdModeOverride = null;
            }
            this._render();
        });
        const thresholdApply = this.shadowRoot.getElementById("threshold-apply");
        if (thresholdApply) thresholdApply.addEventListener("click", async e => {
            e.stopPropagation();
            const mode = this._thresholdModeOverride || (this.shadowRoot.getElementById("threshold-mode-direct") || {}).value || "adaptive_home_size";
            let ok = true;
            if (mode === "percent_total_water") {
                const percent = this.shadowRoot.getElementById("threshold-percent-direct");
                ok = await this._settingsPost({action:"set_option", key:"min_potential_percent_total_water", value:percent ? Number(percent.value||10) : 10}, true);
            } else if (mode === "fixed_ml") {
                const fixed = this.shadowRoot.getElementById("threshold-ml-direct");
                ok = await this._settingsPost({action:"set_option", key:"min_potential_total_ml", value:fixed ? Number(fixed.value||500) : 500}, true);
            }
            if (ok) ok = await this._settingsPost({action:"set_option", key:"threshold_mode", value:mode}, true);
            if (ok) this._thresholdModeOverride = null;
            this._render();
        });
        this.shadowRoot.querySelectorAll("[data-info]").forEach(el => el.addEventListener("click", async e => { e.stopPropagation(); const next = el.dataset.info; if (!next || next === this._info) return; if (this._info) this._pushInfoViewport(); else this._resetInfoNavigation(); this._pendingSubdialogScrollTop = 0; this._info = next; this._render(); if (next === "threshold" && !this._settingsData) await this._loadSettings(true); }));
        this.shadowRoot.querySelectorAll("[data-room]").forEach(el => el.addEventListener("click", e => { e.stopPropagation(); clearTimeout(this._deferredRender); this._deferredRender = null; const next = `room:${el.dataset.room}`; if (this._info && this._info !== next) this._pushInfoViewport(); else if (!this._info) this._resetInfoNavigation(); this._pendingSubdialogScrollTop = 0; this._info = next; this._render(); }));
        (_u = this.shadowRoot.getElementById("submodal")) === null || _u === void 0 ? void 0 : _u.addEventListener("click", e => { if (e.target.id === "submodal") {
            this._info = null;
            this._resetInfoNavigation();
            this._render();
        } });
        this.shadowRoot.querySelectorAll("[data-profile]").forEach(el => el.addEventListener("click", async (e) => { e.stopPropagation(); const option = el.dataset.profile; const ent = this._profileEntity(); if (ent) {
            this._profileOverride = option;
            this._info = null;
            this._render();
            try { await this._hass.callService("select", "select_option", { entity_id: ent.entity_id, option }); setTimeout(() => { if (this._profileOverride === option) { this._profileOverride = null; this._render(); } }, 3000); } catch (err) { this._profileOverride = null; this._render(); throw err; }
        } }));
        const setForecast = async (value) => { const v = Math.max(1, Math.min(120, Math.round(Number(value) || 5))); const ent = this._forecastEntity(); if (ent) {
            this._forecastOverride = v;
            this._render();
            try { await this._hass.callService("number", "set_value", { entity_id: ent.entity_id, value: v }); setTimeout(() => { if (this._forecastOverride === v) { this._forecastOverride = null; this._render(); } }, 3000); } catch (err) { this._forecastOverride = null; this._render(); throw err; }
        } };
        this.shadowRoot.querySelectorAll("[data-forecast]").forEach(el => el.addEventListener("click", async (e) => { e.stopPropagation(); await setForecast(el.dataset.forecast); }));
        (_v = this.shadowRoot.getElementById("forecast-apply")) === null || _v === void 0 ? void 0 : _v.addEventListener("click", async (e) => { var _a; e.stopPropagation(); await setForecast((_a = this.shadowRoot.getElementById("forecast-custom")) === null || _a === void 0 ? void 0 : _a.value); });
        const setGuest = async (kind, value) => { const ent = this._guestEntity(kind); if (ent) {
            await this._hass.callService("number", "set_value", { entity_id: ent.entity_id, value: Math.max(0, Math.min(20, Math.round(Number(value) || 0))) });
        } };
        this.shadowRoot.querySelectorAll("[data-guest-kind]").forEach(el => el.addEventListener("click", async (e) => { e.stopPropagation(); const kind = el.dataset.guestKind, delta = Number(el.dataset.guestDelta || 0); this._guestOverride=this._guestOverride||{}; const backend=kind === "adult" ? Number(st.guest_adults || 0) : Number(st.guest_children || 0); const current=Number(this._guestOverride[kind] ?? backend); const next=Math.max(0,Math.min(20,current+delta)); this._guestOverride[kind]=next; this._render(); try { await setGuest(kind,next); setTimeout(()=>{ if(this._guestOverride&&this._guestOverride[kind]===next){ delete this._guestOverride[kind]; this._render(); } },1800); } catch(err){ delete this._guestOverride[kind]; this._render(); throw err; } }));
        (_w = this.shadowRoot.querySelector(".modal")) === null || _w === void 0 ? void 0 : _w.addEventListener("click", e => { if (e.target.classList.contains("modal")) {
            this._dialogOpen = false;
            this._info = null;
            this._render();
        } });
        const newDialog = this.shadowRoot.querySelector(".dialog-scroll");
        if (newDialog) {
            // Restore exactly once. Repeated delayed scrollTop writes fight native
            // momentum scrolling on iOS and were the main source of the "jumping"
            // feeling in older FreshAirIQ builds.
            newDialog.scrollTop = oldScroll;
            this._dialogScrollTop = newDialog.scrollTop;
            this._installAndroidTouchScroll(newDialog);
            newDialog.addEventListener("scroll", () => {
                this._dialogScrollTop = newDialog.scrollTop;
                this._lastScrollAt = Date.now();
            }, { passive: true });
            // Desktop/browser hotfix: Home Assistant may consume wheel events at
            // the dashboard/page level before the shadow-DOM dialog scrollport
            // gets native scrolling. Drive the wheel explicitly inside the main
            // detail scrollport and stop propagation only when it can scroll.
            newDialog.addEventListener("wheel", e => {
                if (!e.deltaY || newDialog.scrollHeight <= newDialog.clientHeight) return;
                const before = newDialog.scrollTop;
                newDialog.scrollTop += e.deltaY;
                if (newDialog.scrollTop !== before) {
                    e.preventDefault();
                    e.stopPropagation();
                    this._dialogScrollTop = newDialog.scrollTop;
                }
            }, { passive: false });
        }
        const newSubdialog = this.shadowRoot.querySelector(".subdialog");
        if (newSubdialog) {
            // Hotfix 0.9.4.3: keep the room-detail viewport stable on iOS/WebView.
            // In addition to preserving scrollTop, stop scroll chaining/rubber-band
            // gestures at the top/bottom edge from being handed to Home Assistant's
            // page scroller. That was the remaining sporadic jump-to-top path.
            newSubdialog.scrollTop = oldSubScroll;
            this._subdialogScrollTop = newSubdialog.scrollTop;
            // Native pan scrolling is intentionally left untouched. Android
            // WebView can stop scrolling when a nested touchmove handler calls
            // preventDefault at container boundaries. CSS overscroll containment
            // prevents scroll chaining without cancelling the gesture.
            this._installAndroidTouchScroll(newSubdialog);
            newSubdialog.addEventListener("scroll", () => {
                this._subdialogScrollTop = newSubdialog.scrollTop;
                if (this._info) { if (!this._infoScrollByView) this._infoScrollByView = new Map(); this._infoScrollByView.set(this._info, newSubdialog.scrollTop); }
                this._lastScrollAt = Date.now();
            }, { passive: true });
            // Desktop HA can hand wheel events through the shadow-DOM overlay to
            // the page behind it. Keep wheel movement inside the detail scrollport.
            newSubdialog.addEventListener("wheel", e => {
                if (!e.deltaY || newSubdialog.scrollHeight <= newSubdialog.clientHeight) return;
                const before = newSubdialog.scrollTop;
                newSubdialog.scrollTop += e.deltaY;
                if (newSubdialog.scrollTop !== before) {
                    e.preventDefault();
                    e.stopPropagation();
                    this._subdialogScrollTop = newSubdialog.scrollTop;
                }
            }, { passive: false });
        }
    }
}
class FreshAirIQCardEditor extends HTMLElement {
    constructor() {
        super();
        this.attachShadow({ mode: "open" });
        this._config = normalizeDashboardConfig({});
        this._globalSensorOptions = null;
        this._globalSensorEntryId = null;
        this._globalSensorLoading = false;
        this._globalSensorError = null;
    }
    setConfig(c) { this._config = normalizeDashboardConfig(c); this._render(); }
    set hass(h) {
        this._hass = h;
        this._render();
        void this._loadGlobalSensorOptions();
    }
    _settingsEntryId() {
        if (!this._hass || !this._hass.states) return null;
        const states = Object.values(this._hass.states);
        const preferred = states.filter(s => {
            const a = (s && s.attributes) || {};
            return a.freshairiq_transport === "status_v2" && !!a.freshairiq_entry_id;
        });
        const status = preferred.find(s => s.entity_id === "sensor.freshairiq_status") || preferred[0];
        return status && status.attributes ? status.attributes.freshairiq_entry_id : null;
    }
    async _loadGlobalSensorOptions(force = false) {
        const entryId = this._settingsEntryId();
        if (!entryId || this._globalSensorLoading) return;
        if (!force && this._globalSensorEntryId === entryId && this._globalSensorOptions) return;
        this._globalSensorLoading = true;
        this._globalSensorError = null;
        try {
            const result = await this._hass.callApi("GET", `freshairiq/settings/${entryId}`);
            this._globalSensorEntryId = entryId;
            this._globalSensorOptions = Object.assign({}, (result && result.options) || {});
        } catch (err) {
            this._globalSensorError = (err && err.message) ? err.message : "Globale Sensoreinstellungen konnten nicht geladen werden.";
        } finally {
            this._globalSensorLoading = false;
            this._render();
        }
    }
    async _setGlobalSensorOption(key, value) {
        const entryId = this._settingsEntryId();
        if (!entryId || !this._hass) return;
        const previous = Object.assign({}, this._globalSensorOptions || {});
        this._globalSensorOptions = Object.assign({}, previous, {[key]: !!value});
        this._globalSensorError = null;
        this._render();
        try {
            const result = await this._hass.callApi("POST", `freshairiq/settings/${entryId}`, {action:"set_option", key, value:!!value});
            if (result && result.error) throw new Error(result.error);
            this._globalSensorOptions = Object.assign({}, (result && result.options) || this._globalSensorOptions);
            this._globalSensorEntryId = entryId;
        } catch (err) {
            this._globalSensorOptions = previous;
            this._globalSensorError = (err && err.message) ? err.message : "Globale Sensoreinstellung konnte nicht gespeichert werden.";
        }
        this._render();
    }
    _render() {
        if (!this.shadowRoot) return;
        const infoFields = [
            ["info_moisture", "Feuchte & Wasserbilanz", "Aktuelle Feuchte, entfernbares Potenzial und Live-Bilanz."],
            ["info_temperature", "Temperaturänderungen", "Temperaturverlust oder -gewinn während und nach dem Lüften."],
            ["info_time", "Lüftungszeit", "Empfohlene Dauer und verbleibende IQ-Zeit."],
            ["info_forecast", "Kurzzeitprognose", "Vorhersage für den gewählten Prognosezeitraum."],
            ["info_night", "Nachtprognose & Nachtstrategie", "Nächtliche Entwicklung und empfohlene Fensterstrategie."],
            ["info_mould", "Schimmelrisiko", "Oberflächen-RH und auffällige Räume."],
            ["info_energy", "Energie & Kosten", "Wiederaufheizenergie und geschätzte Heizkosten."],
            ["info_pollen", "Pollen & Außenluft-Veto", "Polleninformationen als ergänzende Analyse; kritische Warnungen bleiben sicherheitsbedingt möglich."],
            ["info_voc", "VOC / TVOC", "Zeigt konfigurierte VOC-/TVOC-Zusatzwerte in Raumdetails. Die globale Berücksichtigung wird im FreshAirIQ-Zahnrad unter „Optionale Sensoren & Außenluft“ gesteuert."],
            ["info_pm25", "PM2.5 / Feinstaub", "Zeigt konfigurierte PM2.5-Zusatzwerte in Raumdetails. Die globale Berücksichtigung wird im FreshAirIQ-Zahnrad gesteuert."],
            ["info_illuminance", "Helligkeit", "Zeigt konfigurierte Helligkeitswerte in Raumdetails. Die globale Berücksichtigung wird im FreshAirIQ-Zahnrad gesteuert."],
            ["info_cross_ventilation", "Querlüftung", "Zeigt Querlüftung als ergänzende Analyseinformation, wenn sie erkannt wird."],
        ];
        const layoutFields = [
            ["show_branding", "Logo & FreshAirIQ-Schriftzug", "Ausblenden macht die Karte kompakter."],
            ["show_profile_badge", "Betriebsmodus oben", "Zeigt den aktuellen Modus als kompakte Kachel oben rechts."],
            ["show_iq_process", "IQ-Aktiv / Analyseleiste", "Zeigt, was FreshAirIQ gerade analysiert und wie sicher die Prognose ist."],
            ["show_details_button", "Details-Schaltfläche", "Blendet den direkten Details-Button ein oder aus."],
            ["show_guests_button", "Gäste-Schaltfläche", "Blendet die Schnellsteuerung für Gäste ein oder aus."],
            ["show_rooms_button", "Räume-Schaltfläche", "Blendet den direkten Zugriff auf die Raumübersicht ein oder aus."],
        ];
        const row = ([key, label, description]) => `<div class="row"><div><label>${label}</label><span>${description}</span></div><ha-switch data-key="${key}" ${this._config[key] !== false ? "checked" : ""}></ha-switch></div>`;
        const globalSensorFields = [
            ["voc_sensor_enabled", "VOC / TVOC berücksichtigen", "Global für FreshAirIQ. Aus = nicht einlesen, nicht anzeigen und nicht für Zusatzempfehlungen berücksichtigen; die Raumzuordnung bleibt gespeichert."],
            ["pm25_sensor_enabled", "PM2.5 berücksichtigen", "Global für FreshAirIQ. Aus = nicht einlesen, nicht anzeigen und nicht für Zusatzempfehlungen berücksichtigen; die Raumzuordnung bleibt gespeichert."],
            ["illuminance_sensor_enabled", "Helligkeit berücksichtigen", "Global für FreshAirIQ. Aus = nicht einlesen, nicht anzeigen und nicht für Verschattungs-Zusatzempfehlungen berücksichtigen; die Raumzuordnung bleibt gespeichert."],
        ];
        const globalSensorRow = ([key, label, description]) => {
            const enabled = this._globalSensorOptions ? this._globalSensorOptions[key] !== false : true;
            return `<div class="row"><div><label>${label}</label><span>${description}</span></div><ha-switch data-global-sensor-key="${key}" ${enabled ? "checked" : ""} ${!this._globalSensorOptions ? "disabled" : ""}></ha-switch></div>`;
        };
        const globalStatus = this._globalSensorLoading
            ? `<div class="editor-note">Globale Sensoreinstellungen werden geladen …</div>`
            : this._globalSensorError
                ? `<div class="editor-error">${esc(this._globalSensorError)}</div>`
                : !this._globalSensorOptions
                    ? `<div class="editor-note">Die globale FreshAirIQ-Konfiguration ist noch nicht verfügbar. Die gleichen Schalter findest du jederzeit im Dashboard-Zahnrad unter „Optionale Sensoren & Außenluft“.</div>`
                    : "";
        this.shadowRoot.innerHTML = `<style>
          :host{display:block;padding:8px 0}.box{display:grid;gap:14px}.intro{padding:2px 2px 4px}.intro b{display:block;font-size:16px}.intro span{display:block;margin-top:4px;font-size:12px;line-height:1.45;color:var(--secondary-text-color)}.section{border:1px solid var(--divider-color);border-radius:12px;overflow:hidden}.section-head{padding:10px 12px;background:color-mix(in srgb,var(--primary-text-color) 4%,transparent)}.section-head b{font-size:11px;letter-spacing:.6px}.section-head span{display:block;font-size:11px;line-height:1.35;color:var(--secondary-text-color);margin-top:3px}.row{display:flex;align-items:center;justify-content:space-between;gap:14px;padding:11px 12px;border-top:1px solid var(--divider-color)}.row>div{min-width:0}.row label{display:block;font-weight:650;font-size:13px}.row span{display:block;margin-top:2px;font-size:11px;line-height:1.35;color:var(--secondary-text-color)}ha-switch{flex:0 0 auto}.editor-note,.editor-error{padding:9px 12px;border-top:1px solid var(--divider-color);font-size:11px;line-height:1.4;color:var(--secondary-text-color)}.editor-error{color:var(--error-color)}</style>
          <div class="box">
            <div class="intro"><b>FreshAirIQ Dashboard</b><span>Standardmäßig bleibt das vollständige Dashboard sichtbar. Hier kannst du Zusatzbereiche einzeln ausblenden. Wenn du alle Informationen und festen Bedienelemente deaktivierst, bleibt eine kompakte Ansicht mit der zentralen FreshAirIQ-Empfehlung.</span></div>
            <section class="section"><div class="section-head"><b>OPTIONALE ZUSATZSENSOREN · GLOBAL</b><span>Diese drei Schalter ändern dieselben FreshAirIQ-Einstellungen wie das Dashboard-Zahnrad und Geräte & Dienste. Aus bedeutet: Der Sensortyp wird weder eingelesen noch angezeigt oder für Zusatzempfehlungen berücksichtigt. Die kanonische Lüftungsphysik bleibt unverändert.</span></div>${globalSensorFields.map(globalSensorRow).join("")}${globalStatus}</section>
            <section class="section"><div class="section-head"><b>INFORMATIONEN DIESER KARTE</b><span>Diese Schalter ändern nur die Darstellung dieser einzelnen Dashboard-Karte. Die globale Sensornutzung wird direkt im Abschnitt darüber gesteuert.</span></div>${infoFields.map(row).join("")}</section>
            <section class="section"><div class="section-head"><b>DARSTELLUNG & KOMPAKTHEIT</b><span>Blende feste Bereiche und Schnellzugriffe aus, bis nur noch die Empfehlung übrig bleibt.</span></div>${layoutFields.map(row).join("")}</section>
          </div>`;
        this.shadowRoot.querySelectorAll("ha-switch[data-key]").forEach(x => x.addEventListener("change", () => {
            const key = x.dataset.key;
            const nextConfig = Object.assign({}, this._config); nextConfig[key] = x.checked; this._config = normalizeDashboardConfig(nextConfig);
            this.dispatchEvent(new CustomEvent("config-changed", { detail: { config: this._config }, bubbles: true, composed: true }));
        }));
        this.shadowRoot.querySelectorAll("ha-switch[data-global-sensor-key]").forEach(x => x.addEventListener("change", async () => {
            const key = x.dataset.globalSensorKey;
            if (key) await this._setGlobalSensorOption(key, x.checked);
        }));
    }
}
if (!customElements.get("freshairiq-card-editor"))
    customElements.define("freshairiq-card-editor", FreshAirIQCardEditor);
FreshAirIQCard.getConfigElement = () => document.createElement("freshairiq-card-editor");
if (!customElements.get(FAIQ_CARD))
    customElements.define(FAIQ_CARD, FreshAirIQCard);
window.customCards = window.customCards || [];
if (!window.customCards.some(c => c.type === FAIQ_CARD))
    window.customCards.push({ type: FAIQ_CARD, name: "FreshAirIQ", description: "Intelligente Lüftungs-, Feuchte-, Energie- und Lernübersicht.", preview: true, documentationURL: "https://github.com/rupascha/freshairiq" });
class FreshAirIQDashboardStrategy extends HTMLElement {
    static getCreateSuggestions() { return { title: "FreshAirIQ", icon: "mdi:home-air-filter" }; }
    static async generate(config = {}) { return { title: config.title || "FreshAirIQ", views: [{ title: "FreshAirIQ", path: "freshairiq", icon: "mdi:home-air-filter", cards: [{ type: "custom:freshairiq-card" }] }] }; }
}
if (!customElements.get("ll-strategy-dashboard-freshairiq"))
    customElements.define("ll-strategy-dashboard-freshairiq", FreshAirIQDashboardStrategy);
window.customStrategies = window.customStrategies || [];
if (!window.customStrategies.some(s => s.type === FAIQ_STRATEGY && s.strategyType === "dashboard"))
    window.customStrategies.push({ type: FAIQ_STRATEGY, strategyType: "dashboard", name: "FreshAirIQ Dashboard", description: "Automatisch erzeugtes Live-Dashboard mit Detail-Popup, Räumen, Nachtprognose, Lernen und Energie." });
console.info(`FreshAirIQ frontend ${FAIQ_VERSION} loaded`);
