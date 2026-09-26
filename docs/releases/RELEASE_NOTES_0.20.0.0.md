# FreshAirIQ 0.20.0.0

- Neues integriertes Einstellungszentrum direkt im Dashboard: Zahnrad im Details-Kopf öffnet die vollständige FreshAirIQ-Konfiguration.
- Dashboard und „Geräte & Dienste“ bearbeiten dieselben Home-Assistant-Config-Entry-Daten und Optionen; es gibt keinen zweiten Konfigurationsspeicher.
- Einstellungen neu und übersichtlich nach Außenluft, Gebäude/Anwesenheit, Bereichen, Räumen/Sensoren, Betriebsprofil, Prognose, Pollen/Wind, Querlüftung, Modell, Energie/Kosten, Benachrichtigungen, Statistik und Wartung gegliedert.
- Alle Dashboard-Einstellungen sind deutsch erklärt, zeigen dokumentierte Standardwerte und enthalten bei komplexen Eingaben konkrete Beispiele, insbesondere für Querlüftung.
- Räume, Sensorzuordnungen, mehrere Kontakte, Kontaktmodus, Ausrichtungen, Öffnungsverzögerungen, Maße/Volumen, CO₂ und Feuchtequellen können direkt im Dashboard verwaltet werden.
- Vier bisher im Backend vorhandene, aber nicht an das Dashboard exportierte Statuswerte werden jetzt übertragen: Lüftungsschwellenmodus, Anwesenheitserklärung, Haustiermodus und hausweite Strategie-Lernproben.
- Deutsche Übersetzungsschlüssel vervollständigt; die deutschen Übersetzungen entsprechen wieder vollständig dem vorhandenen Sprachschlüsselumfang.
- Schreibzugriffe auf das neue Einstellungs-API sind authentifiziert und auf Home-Assistant-Administratoren begrenzt.
- Keine Änderung an Klima-, Prognose-, Lern- oder Empfehlungsalgorithmen außer dem korrigierten Datentransport zum Dashboard.
