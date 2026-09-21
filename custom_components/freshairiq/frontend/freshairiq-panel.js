const FAIQ_VERSION = "0.25.0.43";
const FAIQ_IMPL = "freshairiq-card-impl";

// FreshAirIQ safe panel.
// This is intentionally a Home Assistant custom panel rather than a Lovelace
// custom card. HA therefore does not resolve it through the Lovelace
// custom-element timeout that can intermittently replace valid custom cards
// with the generic "Configuration error" card on mobile/cold starts.
class FreshAirIQPanel extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode: "open" });
    this._hass = null;
    this._panel = null;
    this._narrow = false;
    this._card = null;
    this._loading = null;
    this._renderShell();
  }

  set hass(value) {
    this._hass = value;
    if (this._card) this._card.hass = value;
    this._ensureCard();
  }

  get hass() { return this._hass; }

  set panel(value) {
    this._panel = value;
    this._ensureCard();
  }

  get panel() { return this._panel; }

  set narrow(value) {
    this._narrow = Boolean(value);
    this.toggleAttribute("narrow", this._narrow);
  }

  get narrow() { return this._narrow; }

  connectedCallback() {
    this._ensureCard();
  }

  _renderShell() {
    if (!this.shadowRoot) return;
    this.shadowRoot.innerHTML = `
      <style>
        :host { display:block; min-height:100%; box-sizing:border-box; }
        #host { width:100%; box-sizing:border-box; padding:12px; }
        #loading {
          max-width:1200px; margin:0 auto; padding:18px;
          color:var(--secondary-text-color); font:14px/1.4 sans-serif;
        }
      </style>
      <div id="host"><div id="loading">FreshAirIQ wird geladen …</div></div>`;
  }

  async _ensureCard() {
    if (this._card || this._loading || !this.isConnected) return;
    this._loading = this._loadCard();
    try {
      await this._loading;
    } finally {
      this._loading = null;
    }
  }

  async _loadCard() {
    try {
      const moduleUrl = new URL(`./freshairiq-card.js?v=${FAIQ_VERSION}`, import.meta.url).href;
      await import(moduleUrl);
      await customElements.whenDefined(FAIQ_IMPL);

      if (this._card) return;
      const card = document.createElement(FAIQ_IMPL);
      card.setConfig({});
      if (this._hass) card.hass = this._hass;
      this._card = card;

      const host = this.shadowRoot && this.shadowRoot.getElementById("host");
      if (host) host.replaceChildren(card);
    } catch (error) {
      console.error("FreshAirIQ panel failed to initialize", error);
      const host = this.shadowRoot && this.shadowRoot.getElementById("host");
      if (host) {
        host.innerHTML = `
          <ha-card>
            <div style="padding:16px">
              <b>FreshAirIQ konnte nicht geladen werden</b>
              <div style="margin-top:6px;color:var(--secondary-text-color);font-size:12px">
                Das sichere FreshAirIQ-Panel konnte sein Frontend-Modul nicht initialisieren.
              </div>
            </div>
          </ha-card>`;
      }
    }
  }
}

if (!customElements.get("freshairiq-panel")) {
  customElements.define("freshairiq-panel", FreshAirIQPanel);
}

console.info(`FreshAirIQ safe panel ${FAIQ_VERSION} registered`);
