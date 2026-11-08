const FAIQ_VERSION = "0.26.7.0";
const FAIQ_CARD = "freshairiq-card";
const FAIQ_EDITOR = "freshairiq-card-editor";
const FAIQ_IMPL = "freshairiq-card-impl";
const FAIQ_EDITOR_IMPL = "freshairiq-card-editor-impl";
const FAIQ_STRATEGY = "freshairiq";
const FAIQ_STRATEGY_ELEMENT = "ll-strategy-dashboard-freshairiq";

// Tiny first-stage resource. Home Assistant currently does not await every
// custom Lovelace resource before it starts constructing cards/strategies. Keep
// the elements HA looks for in this tiny module and load the 250 kB UI only
// behind those stable proxies.
const faiqLoaderLanguage = () => String(navigator.language || "en").toLowerCase().startsWith("de") ? "de" : "en";
const faiqLoaderCopy = (de, en) => faiqLoaderLanguage() === "de" ? de : en;

let implementationPromise = null;
function loadImplementation() {
  if (!implementationPromise) {
    const url = new URL(`./freshairiq-card.js?v=${FAIQ_VERSION}`, import.meta.url).href;
    implementationPromise = import(url).catch((error) => {
      console.error("FreshAirIQ UI module failed to load", error);
      throw error;
    });
  }
  return implementationPromise;
}

class FreshAirIQLoaderProxy extends HTMLElement {
  constructor() {
    super();
    this._config = null;
    this._hass = null;
    this._impl = null;
    this._loading = false;
  }
  // The display style is set on connect: a constructor must not add attributes (document.createElement).
  connectedCallback() { this.style.display = "block"; this._ensureImplementation(); }
  setConfig(config) {
    this._config = config || {};
    if (this._impl && this._impl.setConfig) this._impl.setConfig(this._config);
    this._ensureImplementation();
  }
  set hass(hass) {
    this._hass = hass;
    if (this._impl) this._impl.hass = hass;
    this._ensureImplementation();
  }
  get hass() { return this._hass; }
  _implementationTag() { return FAIQ_IMPL; }
  _showLoadError() {
    if (this._impl) return;
    if (!this.shadowRoot) this.attachShadow({mode:"open"});
    this.shadowRoot.innerHTML = `<ha-card><div style="padding:16px"><b>${faiqLoaderCopy("FreshAirIQ wird geladen", "FreshAirIQ is loading")}</b><div style="margin-top:6px;color:var(--secondary-text-color);font-size:12px">${faiqLoaderCopy("Das Kartenmodul konnte auf diesem Gerät noch nicht vollständig geladen werden. Die FreshAirIQ-Konfiguration selbst ist nicht beschädigt.<br><b>Fehlercode: FAIQ-UI-LOADER-001</b><br>Bitte diesen Code oder einen Screenshot im Forum mitsenden.", "The card module could not be fully loaded on this device yet. Your FreshAirIQ configuration is not damaged.<br><b>Error code: FAIQ-UI-LOADER-001</b><br>Please include this code or a screenshot in the forum.")}</div></div></ha-card>`;
  }
  async _ensureImplementation() {
    if (this._impl || this._loading) return;
    this._loading = true;
    try {
      await loadImplementation();
      await customElements.whenDefined(this._implementationTag());
      if (this._impl) return;
      const impl = document.createElement(this._implementationTag());
      this._impl = impl;
      if (this._config && impl.setConfig) impl.setConfig(this._config);
      if (this._hass) impl.hass = this._hass;
      if (this.shadowRoot) this.shadowRoot.innerHTML = "";
      this.replaceChildren(impl);
    } catch (error) {
      this._showLoadError();
    } finally {
      this._loading = false;
    }
  }
}
class FreshAirIQLoaderCard extends FreshAirIQLoaderProxy {
  static getConfigElement() { return document.createElement(FAIQ_EDITOR); }
  static getStubConfig() { return {dashboard_variant:"classic"}; }
  getCardSize() { return this._impl && this._impl.getCardSize ? this._impl.getCardSize() : 5; }
}
class FreshAirIQLoaderEditor extends FreshAirIQLoaderProxy {
  _implementationTag() { return FAIQ_EDITOR_IMPL; }
}
class FreshAirIQLoaderStrategy extends HTMLElement {
  static getCreateSuggestions() { return {title:"FreshAirIQ",icon:"mdi:home-air-filter"}; }
  static async generate(config={}) {
    return {title:config.title||"FreshAirIQ",views:[{title:"FreshAirIQ",path:"freshairiq",icon:"mdi:home-air-filter",cards:[{type:"tile",entity:"sensor.freshairiq_status",name:"FreshAirIQ",icon:"mdi:home-air-filter",tap_action:{action:"navigate",navigation_path:"/freshairiq-safe"},hold_action:{action:"more-info"}}]}]};
  }
}

// Optional house map (custom:freshairiq-house-card): its own module, loaded only when the card is used.
const FAIQ_HOUSE_CARD = "freshairiq-house-card";
const FAIQ_HOUSE_EDITOR = "freshairiq-house-card-editor";
let houseImplementationPromise = null;
function loadHouseImplementation() {
  if (!houseImplementationPromise) {
    const url = new URL(`./freshairiq-house-card.js?v=${FAIQ_VERSION}`, import.meta.url).href;
    houseImplementationPromise = import(url).catch((error) => {
      houseImplementationPromise = null;
      console.error("FreshAirIQ house map module failed to load", error);
      throw error;
    });
  }
  return houseImplementationPromise;
}
// Standalone proxy: Lovelace creates cards with document.createElement, where a constructor
// must not add attributes (Chrome: NotSupportedError) – the display style is set on connect.
class FreshAirIQHouseLoaderCard extends HTMLElement {
  constructor() { super(); this._config = null; this._hass = null; this._impl = null; this._loading = false; }
  static getConfigElement() { return document.createElement(FAIQ_HOUSE_EDITOR); }
  static getStubConfig() { return {auto_focus:"hint"}; }
  connectedCallback() { this.style.display = "block"; this._ensureImplementation(); }
  setConfig(config) {
    this._config = config || {};
    if (this._impl && this._impl.setConfig) this._impl.setConfig(this._config);
    this._ensureImplementation();
  }
  set hass(hass) {
    this._hass = hass;
    if (this._impl) this._impl.hass = hass;
    this._ensureImplementation();
  }
  get hass() { return this._hass; }
  getCardSize() { return this._impl && this._impl.getCardSize ? this._impl.getCardSize() : 8; }
  _implementationTag() { return "freshairiq-house-card-impl"; }
  _showLoadError() {
    if (this._impl) return;
    if (!this.shadowRoot) this.attachShadow({mode:"open"});
    this.shadowRoot.innerHTML = `<ha-card><div style="padding:16px"><b>${faiqLoaderCopy("Hauskarte wird geladen", "House map is loading")}</b><div style="margin-top:6px;color:var(--secondary-text-color);font-size:12px">${faiqLoaderCopy("Das Modul der Hauskarte konnte nicht geladen werden. Die FreshAirIQ-Konfiguration ist nicht beschädigt.<br><b>Fehlercode: FAIQ-UI-HOUSE-001</b>", "The house map module could not be loaded. Your FreshAirIQ configuration is not damaged.<br><b>Error code: FAIQ-UI-HOUSE-001</b>")}</div></div></ha-card>`;
  }
  async _ensureImplementation() {
    if (this._impl || this._loading) return;
    this._loading = true;
    try {
      await loadHouseImplementation();
      await customElements.whenDefined(this._implementationTag());
      if (this._impl) return;
      const impl = document.createElement(this._implementationTag());
      this._impl = impl;
      if (this._config && impl.setConfig) impl.setConfig(this._config);
      if (this._hass) impl.hass = this._hass;
      if (this.shadowRoot) this.shadowRoot.innerHTML = "";
      this.replaceChildren(impl);
    } catch (error) {
      this._showLoadError();
    } finally {
      this._loading = false;
    }
  }
}
class FreshAirIQHouseLoaderEditor extends FreshAirIQHouseLoaderCard {
  _implementationTag() { return "freshairiq-house-card-editor-impl"; }
}

// These registrations intentionally happen before the heavy dynamic import.
if (!customElements.get(FAIQ_EDITOR)) customElements.define(FAIQ_EDITOR, FreshAirIQLoaderEditor);
if (!customElements.get(FAIQ_CARD)) customElements.define(FAIQ_CARD, FreshAirIQLoaderCard);
if (!customElements.get(FAIQ_STRATEGY_ELEMENT)) customElements.define(FAIQ_STRATEGY_ELEMENT, FreshAirIQLoaderStrategy);
if (!customElements.get(FAIQ_HOUSE_EDITOR)) customElements.define(FAIQ_HOUSE_EDITOR, FreshAirIQHouseLoaderEditor);
if (!customElements.get(FAIQ_HOUSE_CARD)) customElements.define(FAIQ_HOUSE_CARD, FreshAirIQHouseLoaderCard);

window.customCards = window.customCards || [];
if (!window.customCards.some(card => card.type === FAIQ_CARD)) {
  window.customCards.push({type:FAIQ_CARD,name:"FreshAirIQ",description:faiqLoaderCopy("Intelligente Lüftungs-, Feuchte-, Energie- und Lernübersicht.", "Intelligent ventilation, humidity, energy and learning overview."),preview:true});
}
if (!window.customCards.some(card => card.type === FAIQ_HOUSE_CARD)) {
  window.customCards.push({type:FAIQ_HOUSE_CARD,name:faiqLoaderCopy("FreshAirIQ Hauskarte", "FreshAirIQ house map"),description:faiqLoaderCopy("Grundriss mit Raumzuständen, Wind und vermuteten Luftwegen (optional).", "Floor plan with room states, wind and presumed air paths (optional)."),preview:false});
}
window.customStrategies = window.customStrategies || [];
if (!window.customStrategies.some(strategy => strategy.type === FAIQ_STRATEGY && strategy.strategyType === "dashboard")) {
  window.customStrategies.push({type:FAIQ_STRATEGY,strategyType:"dashboard",name:"FreshAirIQ Dashboard",description:faiqLoaderCopy("Native FreshAirIQ Einstiegskarte; öffnet das robuste FreshAirIQ Panel.", "Native FreshAirIQ entry card; opens the robust FreshAirIQ panel.")});
}

// Start preloading only after the public registrations above are visible.
loadImplementation().catch(() => {});
console.info(`FreshAirIQ frontend loader ${FAIQ_VERSION} registered`);
