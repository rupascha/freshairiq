// House map in Home Assistant (0.26.5.5).
//
// Home Assistant loads only freshairiq-card.js as the Lovelace resource; the house map card
// (custom:freshairiq-house-card) was registered by the old loader only and therefore never
// appeared in the card picker. This module registers it, and adds "Hauskarte (Grundriss)" to
// "Darstellung" of the FreshAirIQ card: the card then shows the house map in place of the
// dashboard, its editor shows the house map options. Classic and IQ are unchanged.
// Loaded by freshairiq-card-data.js with the card version (?v=).

const VARIANT = "house";
const HOUSE_CARD = "freshairiq-house-card";
const HOUSE_EDITOR = "freshairiq-house-card-editor";
const VERSION_QUERY = new URL(import.meta.url).search;
// Language of Home Assistant (like the card), else of the browser.
const de = hass => String((hass && ((hass.locale && hass.locale.language) || hass.language)) || navigator.language || "en").toLowerCase().startsWith("de");
const copy = (textDe, textEn, hass) => (de(hass) ? textDe : textEn);
export const isHouseVariant = config => String((config && config.dashboard_variant) || "") === VARIANT;
export const variantChoices = hass => [["classic", copy("Klassisch", "Classic", hass)], ["iq", "FreshAirIQ IQ"], [VARIANT, copy("Hauskarte (Grundriss)", "House map (floor plan)", hass)]];

// --- custom:freshairiq-house-card (the house map module loads only when it is shown) ---
let houseModule = null;
const loadHouse = () => {
  if (!houseModule) {
    houseModule = import(new URL(`./freshairiq-house-card.js${VERSION_QUERY}`, import.meta.url).href).catch(error => {
      houseModule = null;
      console.error("FreshAirIQ house map module failed to load", error);
      throw error;
    });
  }
  return houseModule;
};

// The display style is set on connect: a constructor must not add attributes (document.createElement).
class HouseCardProxy extends HTMLElement {
  constructor() { super(); this._config = null; this._hass = null; this._impl = null; this._loading = false; }
  static getConfigElement() { return document.createElement(HOUSE_EDITOR); }
  static getStubConfig() { return { auto_focus: "hint" }; }
  connectedCallback() { this.style.display = "block"; this._ensure(); }
  setConfig(config) { this._config = config || {}; if (this._impl) this._impl.setConfig(this._config); this._ensure(); }
  set hass(hass) { this._hass = hass; if (this._impl) this._impl.hass = hass; this._ensure(); }
  get hass() { return this._hass; }
  getCardSize() { return this._impl && this._impl.getCardSize ? this._impl.getCardSize() : 8; }
  _tag() { return "freshairiq-house-card-impl"; }
  async _ensure() {
    if (this._impl || this._loading) return;
    this._loading = true;
    try {
      await loadHouse();
      await customElements.whenDefined(this._tag());
      if (this._impl) return;
      const impl = document.createElement(this._tag());
      if (this._config) impl.setConfig(this._config);
      if (this._hass) impl.hass = this._hass;
      this._impl = impl;
      this.replaceChildren(impl);
    } catch (_error) {
      this.textContent = copy("Das Modul der Hauskarte konnte nicht geladen werden. Bitte die Seite neu laden.", "The house map module could not be loaded. Please reload the page.");
    } finally {
      this._loading = false;
    }
  }
}
class HouseEditorProxy extends HouseCardProxy {
  _tag() { return "freshairiq-house-card-editor-impl"; }
}
if (!customElements.get(HOUSE_EDITOR)) customElements.define(HOUSE_EDITOR, HouseEditorProxy);
if (!customElements.get(HOUSE_CARD)) customElements.define(HOUSE_CARD, HouseCardProxy);
window.customCards = window.customCards || [];
if (!window.customCards.some(card => card.type === HOUSE_CARD)) {
  window.customCards.push({ type: HOUSE_CARD, name: copy("FreshAirIQ Hauskarte", "FreshAirIQ house map"),
    description: copy("Grundriss mit Raumzuständen, Wind und vermuteten Luftwegen (optional).", "Floor plan with room states, wind and likely air paths (optional)."), preview: false });
}

// --- "Darstellung: Hauskarte" of the FreshAirIQ card ---
// Hand config and hass to a house element once its module is defined (an element created before
// its definition is upgraded when the definition arrives).
const feed = (element, config, hass) => customElements.whenDefined(element.localName).then(() => {
  if (config) element.setConfig(config);
  if (hass) element.hass = hass;
});
const upgraded = element => typeof element.setConfig === "function";

function patchCard(cls) {
  const proto = cls.prototype;
  if (proto.__faiqHouse || typeof proto._renderImpl !== "function") return;
  proto.__faiqHouse = true;
  const { setConfig, _render: render, getCardSize } = proto;
  const hass = Object.getOwnPropertyDescriptor(proto, "hass");
  proto.setConfig = function (config) {
    if (isHouseVariant(config)) {
      if (typeof this._cancelQueuedRender === "function") this._cancelQueuedRender();
      if (typeof this._stopLive === "function") this._stopLive();
      if (!this._faiqHouse) {
        this._faiqHouse = document.createElement(HOUSE_CARD);
        this.shadowRoot.replaceChildren(this._faiqHouse);
      }
      feed(this._faiqHouse, config, this._hass);
      return;
    }
    if (this._faiqHouse) {
      this._faiqHouse = null;
      this.shadowRoot.replaceChildren();
      this._hasRendered = false;
    }
    setConfig.call(this, config);
  };
  proto._render = function () { if (!this._faiqHouse) render.call(this); };
  proto.getCardSize = function () { return this._faiqHouse ? 8 : getCardSize.call(this); };
  Object.defineProperty(proto, "hass", {
    configurable: true,
    get: hass.get || function () { return this._hass; },
    set(value) {
      if (!this._faiqHouse) { hass.set.call(this, value); return; }
      this._hass = value;
      if (upgraded(this._faiqHouse)) this._faiqHouse.hass = value;
    },
  });
}

function emitVariant(editor, base, variant) {
  const config = Object.assign({}, base || {}, { dashboard_variant: variant });
  editor.dispatchEvent(new CustomEvent("config-changed", { detail: { config }, bubbles: true, composed: true }));
}

function addHouseChoice(editor) {
  const root = editor.shadowRoot;
  const select = root && root.getElementById("dashboard-variant");
  if (!select) return;
  let option = select.querySelector(`option[value="${VARIANT}"]`);
  if (!option) {
    option = document.createElement("option");
    option.value = VARIANT;
    select.appendChild(option);
  }
  option.textContent = variantChoices(editor._hass)[2][1];
  if (editor.__faiqHouseListener) return;
  editor.__faiqHouseListener = true;
  // Capture phase: the classic/IQ handler would turn every value other than "classic" into "iq".
  root.addEventListener("change", event => {
    const target = event.target;
    if (!target || target.id !== "dashboard-variant" || target.value !== VARIANT) return;
    event.stopImmediatePropagation();
    editor._pendingDashboardVariant = null;
    emitVariant(editor, editor._config, VARIANT);
  }, true);
}

function showHouseEditor(editor, config) {
  if (!editor._faiqHouseEditor) {
    const head = document.createElement("div");
    head.style.cssText = "display:grid;gap:6px;padding:8px 0 12px;margin-bottom:8px;border-bottom:1px solid var(--divider-color)";
    const label = document.createElement("label");
    label.htmlFor = "faiq-dashboard-variant";
    label.textContent = copy("Darstellung", "Dashboard style", editor._hass);
    label.style.fontWeight = "650";
    const select = document.createElement("select");
    select.id = "faiq-dashboard-variant";
    for (const [value, text] of variantChoices(editor._hass)) {
      const option = document.createElement("option");
      option.value = value;
      option.textContent = text;
      select.appendChild(option);
    }
    select.addEventListener("change", () => emitVariant(editor, editor._faiqHouseConfig, select.value));
    head.append(label, select);
    editor._faiqHouseEditor = document.createElement(HOUSE_EDITOR);
    editor.shadowRoot.replaceChildren(head, editor._faiqHouseEditor);
  }
  editor.shadowRoot.getElementById("faiq-dashboard-variant").value = VARIANT;
  feed(editor._faiqHouseEditor, config, editor._hass);
}

function patchEditor(cls) {
  const proto = cls.prototype;
  if (proto.__faiqHouse || typeof proto._emitConfigChanged !== "function") return;
  proto.__faiqHouse = true;
  const { setConfig, _render: render } = proto;
  const hass = Object.getOwnPropertyDescriptor(proto, "hass");
  proto.setConfig = function (config) {
    if (isHouseVariant(config)) {
      this._faiqHouseConfig = Object.assign({}, config);
      this._pendingDashboardVariant = null;
      showHouseEditor(this, this._faiqHouseConfig);
      return;
    }
    if (this._faiqHouseConfig) {
      this._faiqHouseConfig = null;
      this._faiqHouseEditor = null;
      this.shadowRoot.replaceChildren();
    }
    setConfig.call(this, config);
    addHouseChoice(this);
  };
  proto._render = function () {
    if (this._faiqHouseConfig) return;
    render.call(this);
    addHouseChoice(this);
  };
  if (hass && hass.set) {
    Object.defineProperty(proto, "hass", {
      configurable: true,
      get: hass.get || function () { return this._hass; },
      set(value) {
        if (!this._faiqHouseConfig) { hass.set.call(this, value); addHouseChoice(this); return; }
        this._hass = value;
        if (this._faiqHouseEditor && upgraded(this._faiqHouseEditor)) this._faiqHouseEditor.hass = value;
      },
    });
  }
}

customElements.whenDefined("freshairiq-card").then(() => patchCard(customElements.get("freshairiq-card")));
customElements.whenDefined("freshairiq-card-editor").then(() => patchEditor(customElements.get("freshairiq-card-editor")));
