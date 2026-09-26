# FreshAirIQ v0.18.2.1 — Geräte-Kompatibilitäts-Hotfix

- Frontend-Bundle auf v0.18.2.1 synchronisiert; Home-Assistant Cache-Busting verwendet damit die neue Version.
- Optional Chaining und Nullish Coalescing im ausgelieferten Frontend auf kompatiblere ES2018-Syntax transpiliert.
- `String.replaceAll()` und `Array.at()` aus dem Frontend entfernt, um ältere Safari-/iPadOS- und Android-WebViews zu unterstützen.
- CSS-Fallbacks für ältere Browser ergänzt (`100vh` vor `100dvh`, klassische Positionierung vor `inset`, Breiten-Fallback vor `min()`, Farb-Fallbacks vor `color-mix()`).
- Keine Berechnungs-, Lern-, Diagnose-, Entscheidungs- oder Dashboard-Inhaltslogik geändert.
