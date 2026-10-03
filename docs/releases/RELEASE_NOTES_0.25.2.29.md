# FreshAirIQ 0.25.2.29

- Drei-Zustands-Helfer erkennen die deutschen Zustände `Offen`, `Gekippt` und `Geschlossen` vollständig.
- Guardian unterscheidet jetzt einen dokumentierten finalen Präsentations-Override von einem echten unerklärten Empfehlungswiderspruch; echte Widersprüche bleiben geschützt.
- FreshAirIQ IQ respektiert `show_branding: false` wie die klassische Karte.
- Raum- und Entscheidungsbeschriftungen auf den eigenen dunklen Kartenflächen erhalten einen expliziten hellen Kontrast und erben keine schwarze Textfarbe aus einem hellen Home-Assistant-Theme.
- Manueller Support-Diagnoseversand verwendet einen separaten 90-Sekunden-Timeout; datenschutzkonforme Fehlerdetails unterscheiden Timeout und Hub-HTTP-Status ohne Diagnoseinhalte offenzulegen.
- Englische Anzeige für `Dachgeschosswohnung` lautet `Top-floor apartment`; die interne ID `attic_apartment` bleibt für bestehende Konfigurationen unverändert.
