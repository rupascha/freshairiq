# FreshAirIQ 0.25.0.1 – Field-Test Diagnostics Hotfix

## Zweck

Dieser Hotfix verändert ausschließlich die Diagnose-/Feldtest-Nachweisführung und die dazugehörige Export-Metadaten-Erfassung. Die Lüftungs-, Prognose-, Prioritäts-, Lern- und Empfehlungssysteme bleiben unverändert.

## Neu im Diagnoseexport

- stabile, zufällig erzeugte anonyme Installationskennung (`anonymous_installation_id`) über mehrere Exporte und FreshAirIQ-Versionen hinweg
- pseudonymer Fingerprint des FreshAirIQ-Konfigurationseintrags, ohne die Home-Assistant-Entry-ID offenzulegen
- eindeutige Export-ID und fortlaufende Exportsequenz
- Home-Assistant-Version, Installationstyp, Python-/OS-/Architektur- und Zeitzoneninformationen über Home Assistants `system_info`, soweit verfügbar
- pseudonyme Client-ID je Browser/App-Installation, Plattform, Betriebssystemversion, Geräteklasse, Gerätefamilie und – falls der Browser sie tatsächlich preisgibt – Gerätemodell
- Companion-App-, Browser-/WebView- und FreshAirIQ-Frontend-Versionen
- Bildschirm-/Viewport-Metadaten zur Reproduzierbarkeit von iPhone/iPad/Android/WebView-Problemen
- bekannte Clients mit First-/Last-Seen und Versionshistorien
- vollständiger privacy-sicherer Snapshot aller modell-, Komfort-, Energie-, Benachrichtigungs- und Dashboard-relevanten Optionen; Entitäts-IDs, Personen-/Gerätenamen und Notification-Targets bleiben ausgeschlossen
- erweiterte Raumkonfiguration inklusive Öffnungsanzahl, Orientierung, Verzögerung, Referenzsensor-Abdeckung, optionale Luftqualitätssensoren und Aktor-Fähigkeiten – ohne Entitäts-IDs
- Konfigurations-Fingerprints und Konfigurationshistorie
- FreshAirIQ- und Home-Assistant-Versionshistorie innerhalb des Exportzeitraums
- Feldtest-Kontinuität: Zeitraum, Kalendertage mit Daten, längste Tagesserie, größte Sampling-Lücke und Lücken >30 Minuten
- SHA-256-Fingerprint der exportierten Records zur Erkennung von Beschädigung/Duplikaten; ausdrücklich keine kryptografische Echtheits-Signatur

## Datenschutz

Es werden absichtlich keine Home-Assistant-Entity-IDs, Koordinaten, Zugangsdaten, Presence-Entity-Namen, Notification-Targets, rohen User-Agent-Strings, Gerätenamen oder Seriennummern exportiert. iOS stellt im WebView normalerweise kein exaktes Hardwaremodell bereit; in diesem Fall wird nur die Gerätefamilie (z. B. iPhone/iPad) zusammen mit der stabilen pseudonymen Client-ID gespeichert.

## Kompatibilität

Das bestehende 30-Tage-Rolling-Log, die 24-MiB-Exportgrenze, Legacy-Kompaktierung und der bisherige `test_dossier` bleiben erhalten. Diagnose-Schema: **10**.

## Noch offene v1-Gates

Reale HA-Runtime-Coverage, Browser-/WebView-E2E und die geplanten gestuften Feldtests mit unabhängigen Haushalten bleiben weiterhin Voraussetzung vor 1.0.

## Release-Status

Dieses Hotfix ist ausdrücklich **kein** 1.0-Release. Die bestehenden 1.0-Quality-Gates bleiben unverändert offen.
