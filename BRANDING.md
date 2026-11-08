# FreshAirIQ Branding

**Project:** FreshAirIQ  
**Developer:** rupascha  
**Tagline:** Intelligent lüften. Gesund wohnen. Energie sparen.

**Tagline (English):** Ventilate smarter. Live healthier. Save energy.

## Assets
- `docs/freshairiq-branding-official.png` — full approved branding artwork, German (README_DE.md)
- `docs/freshairiq-branding-official-en.png` — the same artwork in English (README.md / README_EN.md); identical pixel for pixel except the tagline and the four labels
- `docs/freshairiq-logo.png` — language-neutral logo card (the artwork without tagline and labels)
- `docs/freshairiq-social-preview.png` — language-neutral GitHub social preview, 1280 × 640 (upload under **Settings → General → Social preview** of the public repository)
- `docs/freshairiq-icon-512.png` — reduced symbol for small UI contexts
- `docs/freshairiq-icon-256.png`
- `docs/freshairiq-icon-128.png`

The reduced mark uses the house, airflow and leaf motif so it remains recognizable at small sizes.

> Note: Home Assistant's integration logo shown in Settings is supplied through the Home Assistant brands infrastructure for published integrations. Keeping these assets in the repository prepares that submission; merely bundling a PNG inside a custom integration does not replace the Settings integration icon.

## Languages
Only the branding artwork carries text. German pages use the German artwork, English pages the English one; the
brand mark, symbols, colours and layout stay identical. Logos, icons and the social preview contain no text and
serve both languages. Screenshots exist per language (`docs/screenshots/` English, `docs/screenshots/de/` German).

## Home Assistant and the Marketplace
Home Assistant (core `brands` integration) and the Marketplace take the integration icon and logo from
`custom_components/freshairiq/brand/`: `icon.png` / `logo.png` 256 × 256, `@2x` 512 × 512, with `dark_` variants
for dark themes. The brand images have no language variants, so these files are language-neutral (no text).
