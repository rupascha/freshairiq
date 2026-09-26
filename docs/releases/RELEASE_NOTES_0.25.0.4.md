# FreshAirIQ 0.25.0.5 — Pure Logic Coverage Gate Hotfix

- Pure-Logic-Coverage-Gate wieder auf echte 100,00 % gebracht.
- `repairs.py` aus dem Pure-Logic-Gate ausgeschlossen, da dieses Modul direkt von Home Assistant Runtime-APIs (`homeassistant.core`, Entity Registry, Issue Registry) abhängt und deshalb in die HA-Runtime-Testschicht gehört. Die vorhandenen `ha_tests/test_repairs_and_entities.py` bleiben dafür zuständig.
- Fehlenden Pure-Logic-Zweig in `language_confidence.py` (keine ausgewählten Räume) durch einen Regressionstest abgedeckt.
- `.coveragerc-pure` behält `fail_under = 100`; ein Rückfall unter 100 % lässt den Testlauf fehlschlagen.

Verifikation dieses Pakets: 583 Pure-Logic-Tests bestanden, 4.879/4.879 Statements abgedeckt, 100,00 %. Python-Kompilierung und ZIP-Integrität werden beim Packaging erneut geprüft. Vollständige HA-Runtime-Tests benötigen eine Home-Assistant-Testumgebung.

## Noch offene v1-Gates
- Reale Home-Assistant-Runtime-/Config-Flow-Coverage bleibt in dieser Arbeitsumgebung unverifiziert, weil die vollständigen Home-Assistant-Testabhängigkeiten nicht installiert sind.
- Die vorhandenen HA-Runtime-Tests, einschließlich `ha_tests/test_repairs_and_entities.py`, müssen im vollständigen HA-CI-Gate ausgeführt werden.

Dies ist ausdrücklich **kein** 1.0-Release; die offenen Runtime-Gates bleiben bestehen.
