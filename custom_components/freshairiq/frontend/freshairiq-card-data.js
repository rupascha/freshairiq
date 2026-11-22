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
    return ({ "Target reached or additional ventilation benefit is too low": "Ziel erreicht oder zusätzlicher Lüftungsnutzen zu gering", "Reference air no longer removes moisture": "Die Referenzluft nimmt keine nennenswerte Feuchtigkeit mehr auf", "Room goals were reached; the close is kept while humidity stays inside the hysteresis band": "Die Ziele dieses Raums wurden in dieser Lüftung erreicht; die Schließempfehlung bleibt innerhalb der Feuchte-Hysterese bestehen", "Room goals reached; the room is set to close once its goals are reached": "Die Ziele dieses Raums sind erreicht; für diesen Raum ist „Schließen, wenn die Ziele erreicht sind“ gewählt", "Room air is already dry; further airing would dry it out too much": "Die Raumluft ist bereits trocken; weiteres Lüften würde sie zu stark austrocknen", "Configured temperature limit for airing reached; close because of the temperature, not because enough moisture was removed": "Temperaturgrenze beim Lüften erreicht – Schließen wegen der Temperatur, nicht weil genug Feuchtigkeit entfernt wurde", "Reference air would add moisture": "Referenzluft würde zusätzliche Feuchtigkeit eintragen", "Potential exists, but ventilation threshold is not reached": "Potenzial vorhanden, Lüftungsschwelle noch nicht erreicht", "No meaningful ventilation demand": "Kein sinnvoller Lüftungsbedarf", "Missing or implausible measurements": "Messwerte fehlen oder sind unplausibel", "Room is visible but excluded from FreshAirIQ calculations": "Raum wird angezeigt, beeinflusst die Berechnungen aber nicht" }[s] || s);
};
// Today minus ``daysBack`` as YYYY-MM-DD in Home Assistant's time zone (the browser's when it is unknown or invalid).
export const ventLogDay = (hass, daysBack = 0) => {
    const zone = hass?.config?.time_zone, options = { year: "numeric", month: "2-digit", day: "2-digit" };
    let parts;
    try { parts = new Intl.DateTimeFormat("en-US", zone ? { ...options, timeZone: zone } : options).formatToParts(new Date()); }
    catch (_) { parts = new Intl.DateTimeFormat("en-US", options).formatToParts(new Date()); }
    const part = type => Number(parts.find(p => p.type === type).value);
    return new Date(Date.UTC(part("year"), part("month") - 1, part("day") - daysBack)).toISOString().slice(0, 10);
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
    // IQ2 (0.26.7.1): what the forecast tile of a running airing says besides its main value (the forecast net change
    // of the room air): what the humidity target still needs and how well the forecast is calibrated. null = an
    // older payload without the IQ2 fields (the earlier wording is kept then).
    _iq2ForecastParts(st) {
        if (st.forecast_net_room_change_ml == null) return null;
        const parts = [], target = st.forecast_to_target_ml, range = st.forecast_interval_ml;
        if (target != null) parts.push(Number(target) >= 1 ? `bis zum Feuchteziel noch ≈ ${Math.round(Number(target))} ml` : "Feuchteziel erreicht");
        if (Array.isArray(range) && range.length === 2) parts.push(`Erwartungsbereich ${Math.round(range[0])} … ${Math.round(range[1])} ml`);
        else if (st.forecast_quality_state === "collecting") parts.push("Prognosegüte wird kalibriert");
        return parts;
    },
    // N2 (0.26.7.1): a season card names observed days, the minimum amount and the missing coverage separately – 60 days
    // alone never complete a season (observations near the season's start AND end are required as well)
    _seasonCardHtml(x, icon) {
        const n = Number(x.observed_days || 0), min = Number(x.min_days || 60);
        const missing = [n < min ? `Mindestmenge ${n}/${min} Tage` : "Mindestmenge erreicht"];
        if (!x.optimized && n > 0 && x.covers_start === false) missing.push("Saisonbeginn nicht beobachtet");
        if (!x.optimized && n > 0 && x.covers_end === false) missing.push("Saisonende noch nicht beobachtet");
        const text = x.optimized ? "Vollständig durchlaufen und ausreichend belegt" : n > 0 ? missing.join(" · ") : "Noch keine Beobachtungstage";
        return `<div class="season-card ${x.optimized ? "done" : ""}"><ha-icon icon="${escFeedback(icon)}"></ha-icon><b>${escFeedback(x.label || x.key)}</b> <strong>${n} Beobachtungstage</strong><i title="Mindestmenge"><em style="width:${Math.min(100, n / min * 100)}%"></em></i><small>${text}</small></div>`;
    },
    // R07 (0.26.7.2): IQ time tile – a countdown only while one is honest; past the target time with air that still
    // helps the airing is reassessed every cycle (no "0 min"), a negative value is the intended overrun at a close
    _iqTime(st) {
        const r = st.remaining_duration_min;
        const remaining = Number(r) || 0;
        // N1 (0.26.7.1): "0 min" is shown only for a real close; a zero or unknown remaining time of a running airing is
        // "being reassessed" – never "target reached" from None → 0 or a clamped value
        // the integration names why no remaining time can be given; the card shows it and computes no time of its own
        const why = st.remaining_duration_state === "reassessing" && st.remaining_duration_reason ? escFeedback(String(st.remaining_duration_reason).replace(/^(Restzeit nicht bestimmbar|Remaining time cannot be determined) – /, "")) : "Lüftung wirkt weiter";
        if (r == null || st.remaining_duration_state === "reassessing" || (remaining === 0 && st.remaining_duration_state !== "close")) return "<b>wird neu bewertet</b><small>" + why + "</small>";
        return `<b>${remaining > 0 ? `${Math.ceil(remaining)} min` : remaining < 0 ? `+${Math.ceil(Math.abs(remaining))} min` : "0 min"}</b><small>${remaining > 0 ? "bis Ziel" : remaining < 0 ? "über Ziel" : "jetzt schließen"}</small>`;
    },
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
    // 0.26.7.2 (support diagnosis 21.11.): the period as calendar dates in Home Assistant's time zone, the one the export
    // endpoint uses (at 00:20 in Berlin "to" is already the new day); a date the user chose stays during live updates,
    // one left untouched follows the current day (only "from" changed before midnight: "to" is the new day after it)
    _ventLogRange() {
        const kept = this._ventLogChosen || {};
        return { start: kept.start || ventLogDay(this._hass, 30), end: kept.end || ventLogDay(this._hass) };
    },
    _keepVentLogRange(field, id) {
        this._ventLogChosen = { ...(this._ventLogChosen || {}), [field]: this.shadowRoot?.getElementById(id)?.value || "" };
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

// 0.26.5.5: house map card and "Darstellung: Hauskarte" (freshairiq-card-house.js). Awaited here so it is
// ready before freshairiq-card.js defines its elements; a failure never blocks the card.
try {
    await import(new URL(`./freshairiq-card-house.js${new URL(import.meta.url).search}`, import.meta.url).href);
} catch (error) {
    console.error("FreshAirIQ house map registration failed", error);
}
// 0.26.5.5: passive test of a new moisture formula, a section in "Wie gut FreshAirIQ aktuell vorhersagt" – now the
// section "Experimentell" with the status of the adopted base formula.
// Hotfix (31.10.): a failed download no longer hides the section silently – it stays visible with the reason.
try {
    await import(new URL(`./freshairiq-card-shadow.js${new URL(import.meta.url).search}`, import.meta.url).href);
} catch (error) {
    console.error("FreshAirIQ section \"Experimentell\" failed", error);
    customElements.whenDefined("freshairiq-card").then(() => shadowLoadFailed(customElements.get("freshairiq-card"), error));
}
export function shadowLoadFailed(cls, error) {
    const proto = cls && cls.prototype;
    if (!proto || proto.__faiqShadow || typeof proto._learningPanel !== "function") return;
    proto.__faiqShadow = "failed";
    const learningPanel = proto._learningPanel;
    proto._learningPanel = function (st) {
        const html = learningPanel.call(this, st);
        const end = this._info === "learning:quality" && typeof html === "string" ? html.lastIndexOf("</section>") : -1;
        if (end < 0) return html;
        const en = typeof this._uiLanguage === "function" && this._uiLanguage() === "en";
        const reason = String((error && error.message) || error || "").replace(/[&<>"']/g, " ").slice(0, 160);
        const text = en
            ? ["Experimental", "The note on the adopted base formula could not be loaded on this device. Please reload the page (in the app: pull down or restart the app).", "Error code FAIQ-UI-SHADOW-001"]
            : ["Experimentell", "Der Hinweis zur übernommenen Grundformel konnte auf diesem Gerät nicht geladen werden. Bitte die Seite neu laden (in der App: nach unten ziehen oder die App neu starten).", "Fehlercode FAIQ-UI-SHADOW-001"];
        return html.slice(0, end) + `<div class="learning-overview-note faiq-shadow-test faiq-shadow-failed" role="alert" style="overflow-wrap:anywhere"><ha-icon icon="mdi:alert-circle-outline"></ha-icon><span><b>${text[0]}</b><br>${text[1]}<br><small>${text[2]}${reason ? ` · ${reason}` : ""}</small></span></div>` + html.slice(end);
    };
}

// U03 (0.26.7.1): unsent feedback drafts, per integration entry and feedback type. Memory only (this browser
// session's page), never written to storage; a draft is deleted only after the Hub confirmed it.
const FAIQ_FEEDBACK_DRAFTS = new Map();
const FAIQ_FEEDBACK_TYPES = ["bug", "improvement", "other"];
const escFeedback = v => String(v ?? "").split("&").join("&amp;").split("<").join("&lt;").split(">").join("&gt;").split('"').join("&quot;").split("'").join("&#039;");
// The feedback form of the dashboard card (mixed into the card like FAIQ_LIVE_METHODS).
export const FAIQ_FEEDBACK_METHODS = {
    async _sendFeedback(feedbackSend) {
        // R03: the send context is fixed before the request – entry, type, exact text and revision of the draft that was
        // sent, and the draft object itself. Only that draft, still unchanged, is cleared on success.
        // B2 (0.26.7.1): receipt, cooldown and button state belong to the entry that was sent; another entry shown when the
        // answer arrives keeps its own state (its own server/entry cooldown stays valid).
        const entryId=this._settingsEntryId(); const box=this.shadowRoot.getElementById("feedback-message"); const type=this.shadowRoot.getElementById("feedback-type")?.value||"bug"; const sentRaw=box?.value||""; const message=sentRaw.trim();
        const resultEl=()=>this.shadowRoot && this.shadowRoot.getElementById("feedback-result"); const sameEntry=()=>String(this._settingsEntryId()||"-")===String(entryId);
        const show=text=>{ const el=sameEntry()?resultEl():null; if(el) el.textContent=text; };
        if (!entryId || message.length < 3) { show(this._tx("Bitte eine Beschreibung mit mindestens 3 Zeichen eingeben.")); return; }
        const draftRef = this._feedbackDraft().entry; const rev = draftRef.rev || 0;
        if (draftRef.sending) return;   // a second click on the same draft while it is on its way (double click, redrawn button)
        draftRef.sending = true;
        feedbackSend.disabled=true; show(this._tx("Wird sicher an den Diagnose-Hub übertragen …"));
        let locked = false;
        try { const response=await this._hass.callApi("POST", `freshairiq/feedback/${entryId}`, {type,message,client_context:this._fieldTestClientContext()}); if(response?.error) throw new Error(response.error); if (response?.cooldown_until) { draftRef.cooldownUntil = response.cooldown_until; locked = true; }
            if (response?.feedback_id) {
                draftRef.receipt = { id: String(response.feedback_id) };
                if ((draftRef.rev || 0) === rev) {   // nothing typed or switched since the send
                    if ((draftRef.texts[type] || "") === sentRaw) { draftRef.texts[type] = ""; draftRef.scroll[type] = 0; }
                    const now=this.shadowRoot && this.shadowRoot.getElementById("feedback-message");
                    if (now && sameEntry() && draftRef.type === type && now.value === sentRaw) now.value = "";
                }
            }
            show(`${this._uiLanguage() === "de" ? "Gesendet" : "Sent"} · Feedback-ID ${response.feedback_id||"–"} · ${this._t("feedback.sent_next")}`); }
        catch(err) {
            let parsed = null; const body = err?.body || err?.message || "";
            try { parsed = typeof body === "string" ? JSON.parse(body) : body; } catch (_) { parsed = null; }
            if (parsed?.reason === "cooldown" || err?.status_code === 429) {
                const mins = Math.max(1, Math.ceil(Number(parsed?.retry_after_seconds || 900) / 60));
                draftRef.cooldownUntil = parsed?.cooldown_until || new Date(Date.now() + mins * 60000).toISOString();
                locked = true;
                show(this._t("feedback.cooldown_next", { mins }));
            } else show(`${this._tx("Senden fehlgeschlagen")}: ${this._formatApiError(err, this._tx("Bitte Verbindung zum Diagnose-Hub prüfen."))}`);
        } finally {
            draftRef.sending = false;
            // only the buttons of the entry now shown, with that entry's own state
            const shownCooldown = sameEntry() ? locked : this._feedbackCooldownMinutes() > 0;
            const shownLocked = shownCooldown || (!sameEntry() && Boolean(this._feedbackDraft().entry.sending));
            const btn = (this.shadowRoot && this.shadowRoot.getElementById("feedback-send")) || feedbackSend;
            for (const b of new Set([feedbackSend, btn])) {
                if (b !== btn && !sameEntry()) continue;   // the old button of the sent entry is no longer shown
                b.disabled = shownLocked;
                if (shownCooldown) { const mins = this._feedbackCooldownMinutes(); b.innerHTML = `<ha-icon icon="mdi:timer-sand"></ha-icon> ${escFeedback(this._t("feedback.cooldown_button", { mins: mins || 15 }))}`; }
            }
        }
    },
    // B2 (0.26.7.1): the feedback cooldown of the entry shown (entry draft store; server value from the status payload)
    _feedbackCooldownMinutes(st = null) {
        const d = this._feedbackDraft().entry;
        const stamps = [d.cooldownUntil, st && st.diagnostics_upload && st.diagnostics_upload.feedback_cooldown_until]
            .map(v => (v ? new Date(v).getTime() : NaN)).filter(Number.isFinite);
        const until = stamps.length ? Math.max(...stamps) : NaN;
        if (Number.isFinite(until)) d.cooldownUntil = new Date(until).toISOString();
        return Number.isFinite(until) && until > Date.now() ? Math.max(1, Math.ceil((until - Date.now()) / 60000)) : 0;
    },
    // U03 (0.26.7.1): the draft of this entry – chosen type, its text, the receipt of the last accepted feedback.
    _feedbackDraft() {
        const key = String(this._settingsEntryId() || "-");
        if (!FAIQ_FEEDBACK_DRAFTS.has(key)) FAIQ_FEEDBACK_DRAFTS.set(key, { type: "bug", texts: {}, scroll: {}, receipt: null, rev: 0, sending: false, cooldownUntil: null });
        const d = FAIQ_FEEDBACK_DRAFTS.get(key);
        return { entry: d, type: d.type, text: d.texts[d.type] || "", receipt: d.receipt };
    },
    _feedbackResultText(draft, mins) {
        const r = draft && draft.receipt;
        if (r && r.id) return `${this._uiLanguage() === "de" ? "Gesendet" : "Sent"} · Feedback-ID ${r.id}${mins ? ` · ${this._t("feedback.cooldown_next", { mins })}` : ""}`;
        return mins ? this._t("feedback.cooldown_next", { mins }) : this._t("feedback.cooldown_hint");
    },
    _bindFeedbackDraft() {
        const box = this.shadowRoot && this.shadowRoot.getElementById("feedback-message");
        const select = this.shadowRoot && this.shadowRoot.getElementById("feedback-type");
        if (!box || !select || box.dataset.draftBound) return;
        box.dataset.draftBound = "1";
        const { entry } = this._feedbackDraft();
        if (box.value !== (entry.texts[entry.type] || "")) box.value = entry.texts[entry.type] || "";
        if (entry.scroll[entry.type]) box.scrollTop = entry.scroll[entry.type];
        box.addEventListener("input", () => { entry.texts[entry.type] = box.value; entry.rev = (entry.rev || 0) + 1; });
        box.addEventListener("scroll", () => { entry.scroll[entry.type] = box.scrollTop; }, { passive: true });
        select.addEventListener("change", () => {
            const next = FAIQ_FEEDBACK_TYPES.includes(select.value) ? select.value : "bug";
            entry.texts[entry.type] = box.value;   // each type keeps its own draft; switching back shows it again
            entry.type = next; entry.rev = (entry.rev || 0) + 1;
            box.value = entry.texts[next] || "";
            box.scrollTop = entry.scroll[next] || 0;
        });
    },
};
