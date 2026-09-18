# FreshAirIQ 0.23.0.1

Korrekturrelease auf Basis 0.23.0.0.

- Bewohner-Konfiguration klar getrennt: Haushalts-/Anwesenheitsdaten vs. persönliche IQ-Profile und Endgeräte.
- Pro Fenster/Tür können eigene Referenz-Temperatur- und Referenz-Feuchtesensoren hinterlegt werden; aktive Öffnungen bestimmen konservativ die verwendete Referenzluft.
- Referenzsensoren im Dashboard verständlicher erklärt.
- Neue Etagenlüftungs-Neubewertung, wenn mehrere Räume derselben Etage geöffnet werden.
- Interne Score-Zahlen werden nicht mehr im Dashboard ausgegeben.
- IQ-Aktiv zeigt während einer Lüftung, ob FreshAirIQ gerade Luftaustausch lernt oder auf synchronisierte Messwerte wartet.
- Lernmessungen können den ersten und letzten belastbaren synchronisierten Messrahmen innerhalb einer Lüftung verwenden, statt die gesamte Session wegen eines ungünstigen Kontaktzeitpunkts zu verwerfen.
- Wiederholungsempfehlungen nach einer Lüftung werden durch schwach erkannte Feuchtequellen nicht mehr vorzeitig freigegeben.
- Raumreihenfolge nutzt die zentrale Coordinator-Reihenfolge als kanonische Quelle und bleibt dadurch in allen Ansichten konsistent.
