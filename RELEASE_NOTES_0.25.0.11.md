# FreshAirIQ 0.25.0.11 – Pure Logic Coverage Hotfix

Dieser Hotfix verändert **keine Produktionslogik**. Er schließt ausschließlich die verbliebene Test-Coverage-Lücke im definierten Pure-Logic-Scope und stellt das dokumentierte harte 100-%-CI-Gate wieder konsistent her.

## Änderungen

- Drei bislang nicht ausgeführte Invalidierungszweige in `forecast_validation.py` werden jetzt gezielt getestet:
  - zeitlich angeglichene Startprognose mit erkannter interner Feuchtequelle,
  - zeitlich angeglichene Startprognose mit guten Messrahmen, die dennoch andere objektive Validierungskriterien nicht erfüllt,
  - eingefrorene Startkurve, die nicht auf die tatsächliche Messdauer zeitlich angeglichen werden konnte.
- `.github/workflows/quality.yml` verwendet wieder `--cov-fail-under=100` statt 95.
- Pure-Logic-Coverage: **100,00 % = 4.773/4.773 Statements**.
- Lokale Pure-Logic-/Regressionstests: **609/609 bestanden**.

## Nicht geändert

Keine Änderung an Lüftungsphysik, absoluter Feuchte, Forecast-Modellen, Messwert-Sperren, Batteriesensor-Behandlung, Lernraten, Prioritäten, Empfehlungen, UI-Logik oder Home-Assistant-Laufzeitpfaden.
