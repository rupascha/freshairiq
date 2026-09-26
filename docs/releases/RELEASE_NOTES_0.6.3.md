# FreshAirIQ 0.6.3

This release implements the nine requested dashboard corrections and additionally hardens the two settings pages that could show **Konfigurationsfehler** after upgrades.

1. Mould risk is visible on the main card.
2. Wetter outside/reference air produces a clear **Nicht lüften** warning with estimated moisture ingress over five minutes.
3. The idle main card is slimmer; temperature, ventilation duration and the extra-five-minute session forecast appear only during active ventilation.
4. Mould risk is colour-coded in each room.
5. Every room shows its latest learning measurement/diagnosis.
6. Details shows the overall V14.2.1 learning status, total room samples and stable-room count.
7. The idle status is fully German ("Fenster geschlossen lassen").
8. Opening room details no longer intentionally resets the Details scroll position; scroll anchoring is disabled and live rerenders restore the current position.
9. Moisture ingress during ventilation is treated as a valid signed physical effect and can no longer break the dashboard card.

Compatibility hardening: legacy/out-of-range defaults in **Modellparameter** and **Pollen & Wind** are clamped to valid selector ranges before Home Assistant renders the forms. Persistent learning/statistics are unchanged and survive the update.
