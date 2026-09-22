# FreshAirIQ Reliability Foundation v1

## Ziel
FreshAirIQ soll mit wachsender Nutzerzahl Änderungen schnell ausliefern können, ohne bereits funktionierendes Verhalten unbeabsichtigt zu verändern.

## Verbindliche Regeln
1. Verhalten wird geschützt, nicht konkrete Quelltextzeilen.
2. Eine Release-ZIP darf nur aus einem grünen Pflicht-Gate entstehen.
3. Ein behobener Produktionsfehler erhält einen Regressionstest.
4. Historische Diagnose-/Upgrade-Testdaten dürfen historische Versionsnummern behalten; Tests auf die aktuelle Release-Version werden zentral geprüft.
5. Sensorlose Räume sind ein unterstützter Zustand: Name + Volumen dürfen gespeichert werden, Berechnungen bleiben bis zur vollständigen Sensorik passiv.
6. Änderungen an stabilen Verträgen benötigen einen bewusst aktualisierten Vertragstest.

## Nächste Ausbaustufen
- Golden Scenario + Replay Engine für reale Lüftungsentscheidungen.
- Upgrade-/Migration-Matrix für ältere FreshAirIQ-Konfigurationen.
- Fehler-Fingerprinting und Gruppierung im Diagnostics Hub.
- Versionsbezogene Regressionserkennung aus anonymisierten Diagnosedaten.
