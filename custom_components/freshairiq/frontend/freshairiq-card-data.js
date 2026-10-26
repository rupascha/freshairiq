// Where the FreshAirIQ card gets its data from (0.26.5.3).
//
// Live channel: the dashboard state is no longer carried by the attributes of
// the status sensor (every attribute change was a recorder row). The card
// subscribes to freshairiq/dashboard/subscribe and merges the pushed payload
// into the status entity it found, so the rest of the card reads it as before.
// Status sensors of older versions still carry the payload as attributes and
// keep working unchanged.
//
// Also: German wording of the status and reason texts of the integration, and the
// ventilation log export (PDF per airing or per day, CSV; user feedback 0.26.5.3).
// Loaded by freshairiq-card.js with the card version (?v=), like the English module.
export const reasonDE = value => {
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
// 0.26.5.4: what sharing diagnostics is good for (admin hint while undecided).
export const consentHint = de => de
    ? { label: "Diagnosen teilen", title: "Diagnosen teilen?", text: "Damit lernen neue Räume schneller und Prognosen werden für alle genauer – aus echten Lüftungen vieler Häuser. Pseudonymisiert, ohne Namen oder Standort; ohne Zustimmung wird nichts gesendet. Festlegen unter Geräte & Dienste → FreshAirIQ → Konfigurieren.", later: "Später", open: "Öffnen" }
    : { label: "Share diagnostics", title: "Share diagnostics?", text: "This lets new rooms learn faster and makes forecasts more accurate for everyone – from real airings of many homes. Pseudonymised, no names or location; nothing is sent without consent. Decide under Devices & services → FreshAirIQ → Configure.", later: "Later", open: "Open" };
export const statusTextDE = value => {
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

const FAIQ_LIVE_SUBSCRIBE = "freshairiq/dashboard/subscribe";
const FAIQ_LIVE_RETRY_MS = 30000;

export const FAIQ_LIVE_METHODS = {
    _statusEntity() {
        const raw = this._statusEntityRaw();
        const attrs = raw && raw.attributes;
        if (!attrs || !attrs.freshairiq_live_api || attrs.rooms != null) return raw;
        const entryId = attrs.freshairiq_entry_id || null;
        this._ensureLive(entryId);
        const live = this._live;
        // 0.26.5.4 (audit S13): without a live channel the status sensor and the room entities still
        // carry the status and the rooms - shown with a notice instead of an empty card
        if (!live || live.entryId !== entryId) return this._liveFailed ? this._liveDegraded(raw) : null; // first payload still on its way
        const merged = this._liveMerged;
        if (merged && merged.raw === raw && merged.payload === live.payload) return merged.state;
        const state = Object.assign({}, raw, { attributes: Object.assign({}, attrs, live.payload) });
        this._liveMerged = { raw, payload: live.payload, state };
        return state;
    },
    _liveDegraded(raw) {
        const cached = this._liveDegradedState;
        if (cached && cached.raw === raw) return cached.state;
        const state = Object.assign({}, raw, { attributes: Object.assign({}, raw.attributes, { freshairiq_live_unavailable: true }) });
        this._liveDegradedState = { raw, state };
        return state;
    },
    _liveNotice() {
        // audit F04: a payload of another (e.g. replaced) FreshAirIQ entry does not count as a working live channel
        const raw = this._statusEntityRaw(), entryId = (raw && raw.attributes && raw.attributes.freshairiq_entry_id) || null;
        if (!this._liveFailed || (this._live && this._live.entryId === entryId)) return "";
        const text = this._uiLanguage() === "de"
            ? "Live-Verbindung zu FreshAirIQ gestört – eingeschränkte Anzeige aus den Sensoren, neuer Versuch läuft"
            : "Live connection to FreshAirIQ disrupted – limited view from the sensors, retrying";
        return `<div class="live-notice" role="status" style="margin:0 0 8px;padding:6px 10px;border-radius:10px;font-size:12px;color:#ffcf8a;background:rgba(255,180,95,.09);border:1px solid rgba(255,180,95,.35)">${text}</div>`;
    },
    _ensureLive(entryId) {
        const connection = this._hass && this._hass.connection;
        if (!connection || typeof connection.subscribeMessage !== "function") { this._liveFailed = true; return; }
        const key = entryId || "";
        if (this._liveSub && this._liveSub.key === key) return;
        if (this._liveRetryAt && Date.now() < this._liveRetryAt) return;
        this._stopLive();
        const sub = { key, unsub: null, closed: false };
        this._liveSub = sub;
        const message = { type: FAIQ_LIVE_SUBSCRIBE };
        if (entryId) message.entry_id = entryId;
        connection.subscribeMessage(payload => this._onLivePayload(sub, payload), message)
            .then(unsub => { if (sub.closed) unsub(); else sub.unsub = unsub; })
            .catch(() => {
                if (this._liveSub !== sub) return;
                this._liveSub = null;
                this._liveFailed = true;
                if (this.isConnected) this._queueRender(); // the limited view at once, not after the retry pause
                this._liveRetryAt = Date.now() + FAIQ_LIVE_RETRY_MS;
                setTimeout(() => { if (this.isConnected) this._queueRender(); }, FAIQ_LIVE_RETRY_MS);
            });
    },
    _stopLive() {
        const sub = this._liveSub;
        this._liveSub = null;
        if (!sub) return;
        sub.closed = true;
        if (sub.unsub) { try { sub.unsub(); } catch (_) { /* connection already gone */ } }
    },
    _onLivePayload(sub, payload) {
        if (this._liveSub !== sub || !payload || typeof payload !== "object") return;
        this._live = { entryId: sub.key || null, payload };
        this._liveFailed = false;
        if (!this.isConnected) return;
        if (this._info || this._dialogOpen) this._queueLiveRefresh();
        else this._queueRender();
    },
};

export const FAIQ_EXPORT_METHODS = {
    // 0.26.5.4 (community): how much of the room air the running airing has
    // replaced and how long it takes to 95 % under the current conditions.
    // Display only - no goal, no influence on any recommendation.
    _airExchangeLine(r) {
        const a = r && r.active && r.air_exchange;
        if (!a) return "";
        const de = this._uiLanguage() === "de";
        const pct = Math.max(0, Math.round(Number(a.exchanged_percent) || 0));
        const rest = a.minutes_to_95;
        const tail = pct >= 95 || rest === 0
            ? (de ? "praktisch vollständig" : "practically complete")
            : rest === null || rest === undefined ? "" : (de ? `bis 95 % noch ca. ${Math.max(1, Math.round(rest))} min` : `about ${Math.max(1, Math.round(rest))} min to 95 %`);
        const estimate = a.estimate ? (de ? " · Schätzung" : " · estimate") : "";
        return `<div class="muted air-exchange">${de ? "Luftaustausch" : "Air exchange"} ${pct} %${tail ? ` · ${tail}` : ""}${estimate}</div>`;
    },
    _ventLogExtras() {
        const de = this._uiLanguage() === "de";
        return `<label style="display:flex;align-items:center;gap:6px;font-size:12px;min-height:32px;order:-1;flex-basis:100%"><input type="checkbox" id="ventlog-daily"${this._ventLogDaily ? " checked" : ""}><span>${de ? "Pro Tag zusammenfassen" : "Summarise per day"}</span></label><button class="quick-forecast" id="ventlog-csv"><ha-icon icon="mdi:file-delimited-outline"></ha-icon><b>${de ? "Als CSV" : "As CSV"}</b><span>${de ? "für Tabellen" : "for spreadsheets"}</span></button>`;
    },
    async _exportVentilationLog(format = "pdf") {
        const csv = format === "csv";
        const button = this.shadowRoot?.getElementById(csv ? "ventlog-csv" : "ventlog-export");
        const original = button?.innerHTML;
        const de = this._uiLanguage() === "de";
        try {
            const entryId = this._settingsEntryId();
            if (!entryId) throw new Error("FreshAirIQ-Konfiguration nicht gefunden");
            const start = this.shadowRoot?.getElementById("ventlog-start")?.value || "";
            const end = this.shadowRoot?.getElementById("ventlog-end")?.value || "";
            const daily = !!this.shadowRoot?.getElementById("ventlog-daily")?.checked;
            this._ventLogDaily = daily;
            if (button) button.innerHTML = csv
                ? `<ha-icon icon="mdi:progress-clock"></ha-icon><b>${de ? "CSV wird erstellt" : "Creating CSV"}</b><span>${de ? "bitte warten" : "please wait"}</span>`
                : this._tx('<ha-icon icon="mdi:progress-clock"></ha-icon><b>PDF wird erstellt</b><span>bitte warten</span>');
            const query = `start=${encodeURIComponent(start)}&end=${encodeURIComponent(end)}${daily ? "&group=day" : ""}${csv ? "&format=csv" : ""}`;
            const payload = await this._hass.callApi("GET", `freshairiq/ventilation-log/${entryId}?${query}`);
            let blob;
            if (csv) {
                blob = new Blob([payload.csv || ""], { type: "text/csv;charset=utf-8" });
            } else {
                const raw = atob(payload.pdf_base64 || "");
                const bytes = new Uint8Array(raw.length);
                for (let i = 0; i < raw.length; i++) bytes[i] = raw.charCodeAt(i);
                blob = new Blob([bytes], { type: "application/pdf" });
            }
            const url = URL.createObjectURL(blob);
            const a = document.createElement("a"); a.href = url; a.download = payload.filename || `FreshAirIQ-Lueftungsprotokoll.${csv ? "csv" : "pdf"}`; a.click();
            setTimeout(() => URL.revokeObjectURL(url), 1000);
        } catch (err) {
            console.error("FreshAirIQ ventilation log export failed", err);
            const info = this._rememberSupportError(err, csv ? "FAIQ-CSV-EXPORT-001" : "FAIQ-PDF-EXPORT-001");
            window.alert(this._supportErrorText(info));
        } finally { if (button && original) button.innerHTML = original; }
    },
};
