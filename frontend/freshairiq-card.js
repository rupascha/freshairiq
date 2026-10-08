const FAIQ_VERSION = "0.26.4.5";
const FAIQ_CARD = "freshairiq-card";
// Legacy source-contract markers only; rendered duplicate controls are intentionally removed: id="room-ref-temp", id="room-ref-humidity", OPTIONALE ZUSATZSENSOREN · GLOBAL.
// Legacy goal-selector contract markers (not executed): room-goal-priority-1 room-goal-priority-2 room-goal-priority-3
// Legacy multi-selector markers (not executed): Array.from(get("room-temp").selectedOptions); Array.from(get("room-humidity").selectedOptions);
const FAIQ_STRATEGY = "freshairiq";
const FAIQ_UI = Object.freeze({
  "shell.subtitle_iq": { de: "DEIN KLIMA · VON FRESHAIRIQ BEWERTET", en: "YOUR CLIMATE · ASSESSED BY FRESHAIRIQ" },
  "shell.details": { de: "Details", en: "Details" },
  "shell.guests": { de: "Gäste", en: "Guests" },
  "shell.rooms": { de: "Räume", en: "Rooms" },
  "shell.support": { de: "Support", en: "Support" },
  "iq.handling": { de: "FreshAirIQ übernimmt", en: "FreshAirIQ is handling it" },
  "iq.all_good": { de: "Alles gut", en: "All good" },
  "iq.no_action": { de: "Aktuell ist kein Eingreifen nötig.", en: "No action is currently needed." },
  "iq.room_tracking": { de: "{count} Raum/Räume werden automatisch verfolgt.", en: "{count} room(s) are being tracked automatically." },
  "iq.priority_one": { de: "{rooms} hat aktuell Priorität.", en: "{rooms} currently has priority." },
  "iq.priority_many": { de: "{rooms} haben aktuell Priorität.", en: "{rooms} currently have priority." },
  "iq.and": { de: " und ", en: " and " },
  "iq.active": { de: "aktiv", en: "active" },
  "iq.remaining": { de: "{count} min übrig", en: "{count} min remaining" },
  "iq.more_rooms_ok": { de: "{count} weitere Räume ohne akuten Handlungsbedarf", en: "{count} more rooms without urgent action needed" },
  "iq.all_rooms_ok": { de: "Alle {count} Räume ohne akuten Handlungsbedarf", en: "All {count} rooms without urgent action needed" },
  "iq.night": { de: "Nacht", en: "Night" },
  "iq.notice": { de: "Hinweis", en: "Notice" },
  "iq.monitored": { de: "im Blick", en: "monitored" },
  "iq.pollen": { de: "Pollen", en: "Pollen" },
  "iq.watch": { de: "beachten", en: "watch" },
  "iq.okay": { de: "okay", en: "okay" },
  "iq.learning": { de: "Lernen", en: "Learning" },
  "iq.learning_active": { de: "aktiv", en: "active" },
  "editor.dashboard_design": { de: "DASHBOARD-DESIGN", en: "DASHBOARD DESIGN" },
  "editor.dashboard_design_help": { de: "Wähle zwischen dem klassischen FreshAirIQ-Dashboard und der neuen kompakten IQ-Ansicht. Beide verwenden dieselben Berechnungen, Lerndaten und Einstellungen.", en: "Choose between the classic FreshAirIQ dashboard and the new compact IQ view. Both use the same calculations, learning data and settings." },
  "editor.dashboard_style": { de: "Darstellung", en: "Dashboard style" },
  "editor.dashboard_style_help": { de: "Klassisch entspricht der informationsreichen Oberfläche aus v0.25.0.75. FreshAirIQ IQ priorisiert die aktuelle Entscheidung und blendet Details bei Bedarf ein.", en: "Classic preserves the information-rich v0.25.0.75 interface. FreshAirIQ IQ prioritizes the current decision and reveals details on demand." },
  "editor.classic": { de: "Klassisch", en: "Classic" },
  "support.cooldown_button": { de: "Noch {mins} Min. gesperrt", en: "Locked for {mins} more min" },
  "support.cooldown_hint": { de: "danach erneut möglich", en: "available again afterwards" },
  "support.prompt": { de: "Beschreibe kurz dein Anliegen oder den beobachteten Fehler (optional). Die detaillierte FreshAirIQ-Diagnose wird nach deiner Bestätigung direkt an den FreshAirIQ-Support übertragen.", en: "Briefly describe your issue or the problem you observed (optional). After your confirmation, the detailed FreshAirIQ diagnostic report will be sent directly to FreshAirIQ Support." },
  "support.message_too_long": { de: "Bitte verwende maximal 4.000 Zeichen.", en: "Please use no more than 4,000 characters." },
  "support.confirm": { de: "Detaillierte Diagnose jetzt direkt an den FreshAirIQ-Support senden? Nach erfolgreichem Versand ist ein erneuter Diagnoseversand für 60 Minuten gesperrt.", en: "Send the detailed diagnostic report directly to FreshAirIQ Support now? After a successful upload, another diagnostic upload will be locked for 60 minutes." },
  "support.sending": { de: "Diagnose wird gesendet", en: "Sending diagnostic report" },
  "support.please_wait": { de: "bitte warten", en: "please wait" },
  "support.sent": { de: "Erfolgreich gesendet", en: "Sent successfully" },
  "support.cooldown_active": { de: "60 Min. Sperre aktiv", en: "60 min lock active" },
  "support.success": { de: "Diagnose erfolgreich an den FreshAirIQ-Support gesendet.{caseLine}\nEin erneuter Versand ist in 60 Minuten möglich.", en: "Diagnostic report successfully sent to FreshAirIQ Support.{caseLine}\nAnother upload will be available in 60 minutes." },
  "support.failed": { de: "Senden fehlgeschlagen", en: "Upload failed" },
  "support.failure_alert": { de: "Die Diagnose konnte nicht an den FreshAirIQ-Support übertragen werden. Es wurde keine 60-Minuten-Sperre gestartet.\n\nAlternativ erreichst du uns unter support@freshairiq.com.", en: "The diagnostic report could not be sent to FreshAirIQ Support. No 60-minute lock was started.\n\nAlternatively, you can reach us at support@freshairiq.com." },
  "settings.confirm_delete_room": { de: "Diesen Raum wirklich aus FreshAirIQ entfernen?", en: "Really remove this room from FreshAirIQ?" },
  "settings.confirm_reset_learning": { de: "Alle gelernten FreshAirIQ-Daten wirklich löschen?", en: "Really delete all learned FreshAirIQ data?" },
  "settings.confirm_reset_options": { de: "Alle FreshAirIQ-Optionen wirklich auf Standardwerte zurücksetzen? Räume und Sensoren bleiben erhalten.", en: "Really reset all FreshAirIQ options to their default values? Rooms and sensors will be kept." },
});
// Frontend locale bridge: the historical dashboard copy is authored in German.
// Keep that rendering path untouched and translate the rendered UI for English
// Home Assistant profiles. English is also the fallback for non-German locales.
const FAIQ_NATIVE_EN = [["Mittelwert (empfohlen): Durchschnitt aller gültigen Werte. Median: mittlerer Wert, robust gegen einzelne Ausreißer – besonders ab drei Sensoren. Minimum: niedrigste gemessene Temperatur. Maximum: höchste gemessene Temperatur.", "Mean (recommended): average of all valid values. Median: middle value, robust against individual outliers – especially with three or more sensors. Minimum: lowest measured temperature. Maximum: highest measured temperature."],["Mittelwert (empfohlen): Durchschnitt aller gültigen Werte. Median: mittlerer Wert, robust gegen einzelne Ausreißer – besonders ab drei Sensoren. Minimum: trockenste Messstelle. Maximum: feuchteste Messstelle.", "Mean (recommended): average of all valid values. Median: middle value, robust against individual outliers – especially with three or more sensors. Minimum: driest measurement point. Maximum: most humid measurement point."],["Mittelwert (empfohlen)", "Mean (recommended)"],["Median (robust)", "Median (robust)"],["Ein Sensor reicht vollständig aus. Bei mehreren Sensoren werden gültige Werte nach der gewählten Auswertung zusammengefasst. Fällt ein zusätzlicher Sensor aus, arbeitet der Raum mit den verbleibenden gültigen Sensoren weiter.", "One sensor is fully sufficient. With multiple sensors, valid values are combined using the selected aggregation. If an additional sensor becomes unavailable, the room continues with the remaining valid sensors."],["Für eine Lüftungsauswertung muss mindestens ein Klimasensor genügend neue Messwerte liefern. Weitere Sensoren mit mindestens einem neuen Messwert dürfen danach mit einfließen.", "For ventilation-session evaluation, at least one climate sensor must provide enough new measurements. Additional sensors with at least one new measurement may then participate."],["Tür wird als Durchgang genutzt und von außen zugezogen","Door is used as a passage and pulled shut from outside"],["Nur aktivieren, wenn ein echter Drei-Zustands-Sensor am Türbeschlag die Griff- bzw. Beschlagstellung erkennt. Nicht für Drei-Zustands-Helfer aktivieren, die aus mehreren einfachen Kontaktsensoren erstellt wurden.","Enable only when using a genuine three-state sensor on the door hardware that detects the handle or hardware position. Do not enable this option for three-state helpers created from multiple standard contact sensors."],["Diese Tür wird regelmäßig als Durchgang genutzt und von außen nur zugezogen","This door is regularly used as a passage and may only be pulled shut from outside"],["Temperatur und Luftfeuchte sind die Basis für berechnete Räume. Öffnungskontakte sind optional und können auch aus einem anderen Raum stammen. Ohne Kontakt bleibt der Raum klimatisch aktiv und FreshAirIQ kann indirekte Lüftungswirkung erkennen und lernen. Änderungen werden in dieselbe Home-Assistant-Konfiguration geschrieben.","Temperature and humidity are the basis for calculated rooms. Opening contacts are optional and may also be located in another room. Without a contact, the room remains climate-active and FreshAirIQ can detect and learn indirect ventilation effects. Changes are written to the same Home Assistant configuration."],["Optional und ohne Einfluss auf die bestehende Feuchte-, Lüftungs- oder ml-Prognoseberechnung: Referenzsensoren beschreiben besondere Zuluftbereiche. VOC/TVOC misst gasförmige Luftschadstoffe, PM2.5 misst sehr feinen Schwebstaub bis 2,5 µm und Helligkeitssensoren messen Beleuchtungsstärke in Lux. Diese Zusatzwerte können ergänzende Empfehlungen liefern und werden – wenn aktiviert – für die 30-Tage-Diagnostik gesammelt, damit spätere FreshAirIQ-Funktionserweiterungen darauf aufbauen können.","Optional and without affecting the existing humidity, ventilation or ml forecast calculations: reference sensors describe special incoming-air zones. VOC/TVOC measures gaseous air pollutants, PM2.5 measures very fine airborne particles up to 2.5 µm, and illuminance sensors measure light level in lux. These additional values can provide supplementary recommendations and, when enabled, are collected for the 30-day diagnostics so future FreshAirIQ features can build on them."],["Wähle, wie FreshAirIQ die Haus-Lüftungsschwelle bestimmt. Automatisch (empfohlen): FreshAirIQ teilt die erwartete tägliche Feuchteproduktion durch vier und begrenzt das Ergebnis auf 6–12 % der aktuell überwachten Wassermenge. Von Mai bis September wird die Schwelle morgens vor 09:00 Uhr bzw. abends ab 19:00 Uhr um 25 % gesenkt, wenn die Außenluft mindestens 2 °C kühler als die mittlere Raumtemperatur ist. Gesundheits-, Schimmel- und kritische CO₂-Regeln haben Vorrang.","Choose how FreshAirIQ determines the house ventilation threshold. Automatic (recommended): expected daily moisture generation is divided by four and constrained to 6–12% of currently monitored water. From May through September the threshold is reduced by 25% before 09:00 and from 19:00 when outside air is at least 2°C cooler than average indoor temperature. Health, mould and critical CO₂ rules take priority."],["Standard: normale Außenluft. Optionaler Ersatz für die Außenluft-Temperatur dieses Raums, z. B. wenn die Lüftungsöffnung in einen Wintergarten führt. Temperatur und Referenzfeuchte müssen denselben Luftbereich messen. Für Räume mit Öffnungen in unterschiedliche Luftbereiche die feinere Zuordnung pro Fenster/Tür verwenden; sie ist sowohl in Geräte & Dienste als auch in den FreshAirIQ-Einstellungen verfügbar.","Default: normal outdoor air. Optional replacement for the outdoor-air temperature used for this room, for example when its ventilation opening leads into a conservatory. Temperature and reference humidity must measure the same air zone. For rooms with openings into different air zones, use the more precise assignment per window/door; it is available both under Devices & services and in the FreshAirIQ settings."],["Optional je Öffnung: Ordne Temperatur-/Feuchtereferenz und bei Bedarf das zugehörige Rollo bzw. die Jalousie direkt diesem Fenster oder dieser Tür zu. Beispiel: Tür zum Wintergarten → beide Wintergarten-Sensoren; normales Außenfenster → Referenz leer lassen. Rollos/Jalousien werden immer kontaktbezogen zugeordnet. Die Zusatzzuordnung verändert die bestehende Feuchte-/Lüftungsphysik nicht eigenmächtig.","Optional: Assign a local temperature and humidity reference to openings that do not lead to normal outdoor air. Example: conservatory door → select both conservatory sensors. Outdoor windows → leave empty. Temperature and humidity must always be selected as a pair from the same air zone."],["Referenzsensoren beschreiben die Luft, die durch diese Lüftungsöffnung einströmt. Standard ist die normale Außenluft. Setze hier nur dann eine andere Temperatur, wenn der gesamte Raum in einen anderen Luftbereich lüftet, z. B. Wintergarten. Temperatur und Feuchte müssen denselben Luftbereich messen. Bei unterschiedlichen Fenstern/Türen erfolgt die genaue Zuordnung pro Kontakt im FreshAirIQ-Dashboard.","Reference sensors describe the air entering through this ventilation opening. The default is normal outdoor air. Set a different temperature here only if the entire room ventilates into another air zone, for example a conservatory. Temperature and humidity must measure the same air zone. If windows/doors lead to different air zones, assign the reference precisely per contact in the FreshAirIQ dashboard."],["Optional. PM2.5-Sensoren messen sehr feinen Schwebstaub mit Partikeln bis 2,5 µm, typischerweise in µg/m³; solche Sensoren stecken z. B. in Luftqualitätsmessgeräten und manchen Luftreinigern. Keine Änderung der Feuchte-/Lüftungsphysik oder ml-Prognose. Kann Zusatzempfehlungen liefern; aktivierte Werte werden für die 30-Tage-Diagnostik und spätere Funktionserweiterungen gesammelt.","Optional. PM2.5 sensors measure very fine airborne particles up to 2.5 µm, typically in µg/m³; such sensors are found, for example, in air-quality monitors and some air purifiers. They do not change the humidity/ventilation physics or the ml forecast. They can provide supplementary recommendations; enabled values are collected for the 30-day diagnostics and future feature extensions."],["Optionaler Ersatz für die Außenluft-Temperatur dieses Raums, z. B. wenn die Lüftungsöffnung in einen Wintergarten führt. Temperatur und Referenzfeuchte müssen denselben Luftbereich messen. Für Räume mit Öffnungen in unterschiedliche Luftbereiche die feinere Zuordnung pro Fenster/Tür verwenden; sie ist sowohl in Geräte & Dienste als auch in den FreshAirIQ-Einstellungen verfügbar.","Optional replacement for the outdoor-air temperature used for this room, for example when its ventilation opening leads into a conservatory. Temperature and reference humidity must measure the same air zone. For rooms with openings into different air zones, use the more precise assignment per window/door; it is available both under Devices & services and in the FreshAirIQ settings."],["FreshAirIQ kann sofort ohne Raumkonfiguration hinzugefügt werden. Außenluftquelle, Räume und alle weiteren Einstellungen sind hier optional und können anschließend über Geräte & Dienste oder das Dashboard-Zahnrad eingerichtet werden. Solange notwendige Klimaquellen fehlen, erstellt FreshAirIQ keine Lüftungsberechnungen – das Dashboard bleibt trotzdem verfügbar.","FreshAirIQ can be added immediately without configuring any rooms. The outdoor-air source, rooms and all other settings are optional here and can be configured later under Devices & services or via the dashboard settings button. Until the required climate sources are available, FreshAirIQ does not perform ventilation calculations, but the dashboard remains available."],["Optional. Ein Helligkeits-/Beleuchtungsstärkesensor misst Licht in Lux (lx), z. B. ein Zigbee-Helligkeitssensor oder der Lux-Sensor eines Präsenzmelders. Keine Änderung der Feuchte-/Lüftungsphysik oder ml-Prognose. Kann Verschattungs-Zusatzempfehlungen liefern; aktivierte Werte werden für die 30-Tage-Diagnostik und spätere Funktionserweiterungen gesammelt.","Optional. An illuminance sensor measures light in lux (lx), for example a Zigbee light sensor or the lux sensor of an occupancy detector. It does not change the humidity/ventilation physics or the ml forecast. It can provide supplementary shading recommendations; enabled values are collected for the 30-day diagnostics and future feature extensions."],["VOC/TVOC, PM2.5 und Helligkeit sind vollständig optional. Sie verändern weder Feuchte-/Lüftungsphysik, ml-Prognose noch das Lernmodell. Bei aktivierter Nutzung können sie Zusatzempfehlungen erzeugen und werden in der lokalen 30-Tage-Diagnostik für spätere Funktionserweiterungen mitgeführt. Pollen und Wind bleiben separate Außenluft-Einflüsse.","VOC/TVOC, PM2.5 and illuminance are fully optional. They do not change humidity/ventilation physics, the ml forecast or the learning model. When enabled, they may produce supplemental recommendations and are included in the local 30-day diagnostics for future feature development. Pollen and wind remain separate outdoor-air influences."],["Schrittweise FreshAirIQ-Konfiguration direkt in Home Assistant. Wie bei einer guten nativen Config-Flow-Einrichtung sind Grunddaten und erweiterte Einstellungen getrennt; jede Seite erklärt Zweck, Standardwert und – wo sinnvoll – ein Beispiel. Gespeicherte Änderungen gelten sofort und werden identisch im Dashboard-Zahnrad verwendet.","Step-by-step FreshAirIQ configuration directly in Home Assistant. As in a well-structured native config flow, basic data and advanced settings are separated; each page explains the purpose, default value and, where useful, an example. Saved changes take effect immediately and are used identically by the dashboard settings."],["Optional. VOC/TVOC-Sensoren messen flüchtige organische Verbindungen (gasförmige Stoffe z. B. aus Reinigern, Möbeln oder Kochdämpfen). Keine Änderung der Feuchte-/Lüftungsphysik oder ml-Prognose. Kann Zusatzempfehlungen liefern; aktivierte Werte werden für die 30-Tage-Diagnostik und spätere Funktionserweiterungen gesammelt.","Optional. VOC/TVOC sensors measure volatile organic compounds (gaseous substances, for example from cleaning products, furniture or cooking fumes). They do not change the humidity/ventilation physics or the ml forecast. They can provide supplementary recommendations; enabled values are collected for the 30-day diagnostics and future feature extensions."],["Außenluftquelle ändern oder bewusst leer lassen. FreshAirIQ kann auch ohne Außenquelle installiert bleiben; Lüftungsberechnungen starten erst, sobald eine gültige Quelle vorhanden ist. Ohne Wetter-Entität müssen Außentemperatur und Außenluftfeuchtigkeit immer gemeinsam gesetzt werden.","Change the outdoor-air source or deliberately leave it empty. FreshAirIQ can remain installed without an outdoor source; ventilation calculations start only when a valid source is available. Without a weather entity, outdoor temperature and outdoor humidity must always be configured together."],["Optional konfigurierbare Außenluft-Referenz. Ohne Quelle bleibt FreshAirIQ installiert und das Dashboard verfügbar, es werden aber keine verlässlichen Lüftungsberechnungen erzeugt. Ohne Wetter-Entität müssen Außen-Temperatur und Außen-Luftfeuchtigkeit gemeinsam gesetzt werden.","Optional outdoor-air reference. Without a source, FreshAirIQ remains installed and the dashboard stays available, but no reliable ventilation calculations are produced. Without a weather entity, outdoor temperature and outdoor humidity must be configured together."],["Referenztemperatur und Referenzfeuchte können bei besonderen Zuluftbereichen in die Berechnung eingehen. CO₂, VOC/TVOC, PM2.5 und Helligkeit werden derzeit nur protokolliert und für spätere Funktionen gesammelt; sie verändern die aktuelle Feuchte-/ml-Lüftungsempfehlung nicht.","Reference temperature and humidity can affect calculations for special supply-air zones. CO₂, VOC/TVOC, PM2.5 and illuminance are currently logged for future features and do not change the current moisture recommendation."],["Lege den Raum mit Sensoren, Größe und Eigenschaften an. Danach folgen Himmelsrichtungen und Kontaktverzögerungen. Standardwerte sind direkt an den Feldern erklärt. Änderungen werden in derselben Konfiguration gespeichert, die auch das Dashboard-Zahnrad verwendet.","Configure the room with its sensors, size and properties. Contact orientations and delays follow. Default values are explained directly at the fields. Changes are stored in the same configuration used by the dashboard settings."],["Wenn mindestens ein maßgeblicher Tracker sicher zuhause ist, können Bewohner ohne Tracker als anwesend angenommen werden. Sind alle maßgeblichen Tracker sicher außer Haus, können sie als abwesend angenommen werden. Unsichere Zustände werden vorsichtig behandelt.","If at least one relevant tracker is definitely home, residents without trackers may be assumed present. If all relevant trackers are definitely away, they may be assumed absent. Uncertain states are handled conservatively."],["Wähle den Bereich, den du ändern möchtest. Jede bestätigte Unterseite wird sofort gespeichert; „Fertig“ schließt nur noch die Raumeinstellungen. Änderungen werden in derselben Konfiguration gespeichert, die auch das Dashboard-Zahnrad verwendet.","Select the section you want to change. Each confirmed subpage is saved immediately; “Done” only closes the room settings. Changes are stored in the same configuration used by the dashboard settings."],["Ordne jedem Fenster-/Türkontakt bei Bedarf ein eigenes Temperatur-/Feuchte-Paar und das zugehörige Rollo bzw. die Jalousie zu. Beide Referenzsensoren müssen denselben Luftbereich messen. Änderungen werden nach Bestätigung sofort gespeichert.","Assign a temperature/humidity pair to individual window/door contacts when needed. Both sensors must measure the same air zone. Confirmed changes are saved immediately."],["Hier steuerst du, wie FreshAirIQ Lüftungen bewertet und Empfehlungen priorisiert. Jede Einstellung zeigt den dokumentierten Standardwert und eine Erklärung; für die meisten Haushalte sind die Standardwerte die richtige Ausgangsbasis.","Here you control how FreshAirIQ evaluates ventilation and prioritizes recommendations. The documented defaults are suitable for most households."],["Mehrfachauswahl möglich: Dusche, Badewanne, Sauna, Kochen, Waschmaschine, Trockner und/oder Bügelstation. Diese Angabe ist nur Kontext für die Erkennung; FreshAirIQ aktiviert eine Feuchtequelle erst, wenn die Messdaten dazu passen.","Multiple selection is possible: shower, bathtub, sauna, cooking, washing machine, dryer and/or ironing station. This is only context for detection; FreshAirIQ activates a moisture source only when the measurements support it."],["Standard: normale Außenluft. Optionaler Ersatz für die Außenluft-Feuchte. Nur zusammen mit der passenden Referenztemperatur desselben Luftbereichs verwenden. FreshAirIQ berechnet daraus die absolute Feuchte der einströmenden Luft.","Default: normal outdoor air. Optional replacement for outdoor-air humidity. Use only together with the matching reference temperature from the same air zone. FreshAirIQ uses both values to calculate the absolute humidity of the incoming air."],["Nur nötig, wenn ein Querlüftungspaar über verschiedene Stockwerke/Bereiche hinweg physisch verbunden ist. Gleiches Format. Beispiel: wohnzimmer+fitnessraum. Paare im gleichen Bereich brauchen hier keinen Eintrag. Beispiel: leer.","Only required when a cross-ventilation pair is physically connected across different floors/areas. Same format. Example: living_room+gym. Pairs within the same area need no entry here."],["Es wurde eine bestehende Ventilation-Assistant-Konfiguration gefunden. FreshAirIQ kann Außenluftquelle, Räume, Lüftungskontakte und Raumparameter übernehmen. Vorhandene Lernwerte werden beim ersten Start ebenfalls übernommen.","An existing Ventilation Assistant configuration was found. FreshAirIQ can import the outdoor reference, rooms, ventilation contacts and room parameters. Existing learning values are also migrated on first start."],["Optional. Die Gerätezuordnung wird derzeit protokolliert und für spätere FreshAirIQ-Funktionen gesammelt. Sie verändert die aktuelle Lüftungs-/ml-Empfehlung nicht und FreshAirIQ schaltet das Gerät nicht automatisch.","Optional. This value or device assignment is currently logged for future FreshAirIQ features. It does not change the current ventilation/moisture recommendation and no device is controlled automatically. Default: not set. Example: fan.air_purifier."],["Ordne jedem Kontakt die tatsächliche Himmelsrichtung zu. Standard: Unbekannt. Beispiel: Fenster zur Morgensonne = Ost; gegenüberliegendes Fenster = West. Diese Information verbessert Wind- und Querlüftungsbewertung.","Assign the actual compass orientation to each contact. Default: Unknown. Example: a window facing the morning sun = East; the opposite window = West. This information improves wind and cross-ventilation assessment."],["Für {entry_title} konfigurierte Pflicht-Entitäten existieren nicht mehr in Home Assistant: {entities}. Öffne die FreshAirIQ-Einstellungen und ersetze die fehlenden Außen-, Raumsensor- oder Fenster-/Tür-Referenzen.","Required entities configured for {entry_title} no longer exist in Home Assistant: {entities}. Open FreshAirIQ settings and replace the missing outdoor, room sensor, or window/door references."],["Definiere nur echte Luftwege, bei denen zwei Räume gleichzeitig geöffnet einen wirksamen Durchzug bilden können. Standard: leer, also kein zusätzlicher Querlüftungsbonus. Verfügbare Raumschlüssel: {room_keys}","Define only real airflow paths where two rooms opened at the same time can create effective cross ventilation. Default: empty, so no additional cross-ventilation bonus. Available room keys: {room_keys}"],["Diese Geräte werden derzeit nur protokolliert. Die Daten werden für spätere FreshAirIQ-Funktionen gesammelt; aktuell verändern sie die Lüftungs-/ml-Empfehlung nicht und werden nicht automatisch geschaltet.","These devices are currently logged for future FreshAirIQ features. They do not change the current ventilation/moisture recommendation and are not controlled automatically."],["Zeit, die ein Kontakt ununterbrochen offen sein muss, bevor FreshAirIQ eine Lüftungssession startet. Standard: 0 s. Beispiel: 120 s ignoriert kurzes Türöffnen und zählt erst nach zwei Minuten als Lüftung.","Time a contact must remain continuously open before FreshAirIQ starts a ventilation session. Default: 0 s. Example: 120 s ignores brief door openings and counts the contact as ventilation only after two minutes."],["Dies ist dieselbe Profilstruktur wie im Dashboard-Zahnrad. Für komfortable Raum- und Endgeräte-Zuordnung ist das Dashboard-Zahnrad empfohlen; hier bleibt die vollständige native Bearbeitbarkeit erhalten.","This is the same profile structure used by the dashboard settings. The dashboard is recommended for convenient room and device assignment; full native editability remains available here."],["Optionaler Ersatz für die Außenluft-Feuchte. Nur zusammen mit der passenden Referenztemperatur desselben Luftbereichs verwenden. FreshAirIQ berechnet daraus die absolute Feuchte der einströmenden Luft.","Optional replacement for outdoor-air humidity. Use only together with the matching reference temperature from the same air zone. FreshAirIQ uses both values to calculate the absolute humidity of the incoming air."],["Technische native Darstellung derselben persönlichen Profile wie im Dashboard. Das Format bleibt lokal; einfacher ist die grafische Bearbeitung über das FreshAirIQ-Zahnrad. Beispiel: Paul → Wohnzimmer.","Native technical representation of the same personal profiles used by the dashboard. The data stays local; graphical editing in the FreshAirIQ dashboard settings is easier."],["Optional: Tür/Fenster zu einem anderen Luftbereich können ein eigenes Sensorpaar erhalten. Beispiel Wintergarten: Temperatur und Feuchte des Wintergartens gemeinsam auswählen. Außenfenster leer lassen.","Optional: Windows/doors into another air zone can use their own sensor pair. For a conservatory, select both its temperature and humidity sensors. Leave outdoor openings empty."],["Diese Angaben helfen bei Feuchteproduktion, Anwesenheit und Nachtprognosen. Standard: Haus, 2 Erwachsene, 0 Kinder, keine Tracker/Präsenzsensoren, keine Haustiere, Nacht 22:00–07:00, Nachtprognose an.","Household, presence and night model. Residents with a phone can be assigned through person/device_tracker entities; residents without phones remain supported."],["Du kannst alle verfügbaren geeigneten binary_sensor-Entitäten auswählen. Sie dienen als weiche Zusatzinformation; ein einzelnes Bewegungsereignis gilt nicht automatisch als sicherer Menschennachweis.","You can select any suitable available binary_sensor entities. They are soft supporting evidence; a single motion event is not automatically treated as confirmed human presence."],["Passt Sprache und Komfortkontext an deinen Haushalt an. Die physikalische Prognose sowie Gesundheits-, Schimmel- und CO₂-Grenzen bleiben unverändert. Standard: aktiv, ausgewogen, Nacht automatisch.","Adapts wording and comfort context to your household. Physical forecasts and health, mould and CO₂ safety limits remain unchanged. Defaults: enabled, balanced, automatic night handling."],["Optional: Für jede Öffnung in einen anderen Luftbereich ein vollständiges Temperatur-/Feuchte-Sensorpaar auswählen. Normale Außenfenster bleiben leer und verwenden die Außen- bzw. Raumreferenz.","Optional: For each opening into another air zone, select a complete temperature/humidity sensor pair. Outdoor windows stay empty and use the normal outdoor or room reference."],["Zentrale Stelle für Bewohner, Anwesenheit, Komfort und Nacht. Dieselben Werte werden auch im Dashboard-Zahnrad verwendet; Namen und Tracker werden nicht noch einmal an anderer Stelle gepflegt.","Central place for residents, presence, comfort and night settings. The same values are used by the dashboard settings; names and trackers are not maintained a second time elsewhere."],["Kommagetrennt in derselben Reihenfolge wie die Kinder-Tracker. Kinder ohne Tracker dürfen ebenfalls benannt werden. Namen werden nicht für direkte Handlungsaufforderungen an Kinder verwendet.","Comma-separated in the same order as child trackers. Children without trackers may also be named. Names are not used for direct action prompts to children."],["Diese Werte werden nur zur Kostenschätzung des durch Lüften verlorenen Wärmeinhalts verwendet. Die Standardwerte sind Näherungen und können an deinen Tarif bzw. deine Anlage angepasst werden.","These values are used only to estimate the cost of reheating the heat lost through ventilation. The default values are approximations and can be adjusted to your tariff or heating system."],["Grunddaten deines Zuhauses. Geräte & Dienste und das Dashboard-Zahnrad bearbeiten dieselbe FreshAirIQ-Konfiguration; eine Änderung an einer Stelle ist an der anderen Stelle ebenfalls aktiv.","Core home data. The structure mirrors the dashboard settings and both interfaces edit the same ConfigEntry values."],["Format: raum_a+raum_b. Mehrere Paare mit Komma trennen. Beispiel: wohnzimmer+schlafzimmer,arbeitszimmer+kinderzimmer. Ein Bonus gilt nur, wenn beide zugehörigen Lüftungskontakte aktiv sind.","Format: room_a+room_b. Separate multiple pairs with commas. Example: living_room+bedroom,office+child_room. A bonus applies only when both associated ventilation contacts are active."],["Kommagetrennt in derselben Reihenfolge wie die Erwachsenen-Tracker. Zusätzliche Namen dürfen Bewohner ohne eigenen Tracker benennen. Wird nur lokal für persönliche Ansprache verwendet.","Comma-separated in the same order as the adult trackers. Additional names may represent residents without their own tracker. Used locally for personal wording only."],["Aus = konfigurierte Helligkeitssensoren werden nicht eingelesen, nicht angezeigt und nicht zur Präzisierung von Verschattungs-Empfehlungen verwendet. Die Zuordnung bleibt gespeichert.","Off = configured illuminance sensors are not read, shown or used to refine shading recommendations. The room assignment remains stored."],["Standard: Benachrichtigungen aus, keine Empfänger, Ebene „Haus“, alle Räume, Lüften/Schließen/Abschluss/Kühlung/Schimmel/Sensorfehler an, Nacht/Lernen aus, Mindestabstand 90 Minuten.","Default: notifications off, no recipients, scope “House”, all rooms, ventilate/close/completion/cooling/mould/sensor-error notifications on, night/learning off, minimum interval 90 minutes."],["Technische Feineinstellungen der Lüftungslogik. Für die meisten Haushalte sollten die Standardwerte unverändert bleiben. Änderungen werden nach dem Speichern sofort übernommen.","Adaptive ventilation logic. By default the threshold scales with dwelling size and moisture generation, targeting roughly 3–5 meaningful ventilation cycles per day."],["Verzögerung je Fenster-/Türkontakt. Standard: 0 s. Beispiel: 120 s = erst nach zwei Minuten offen zählt der Kontakt als Lüftung. Die bestätigte Seite wird sofort gespeichert.","Delay per window/door contact. Default: 0 s. Example: 120 s means the contact counts as ventilation only after it has remained open for two minutes. The confirmed page is saved immediately."],["Eigene Stockwerke/Zonen anlegen, sortieren und verwalten. Standard: keine zusätzliche Vorauswahl; vorhandene Raumzuordnungen werden automatisch übernommen. Aktuell: {levels}","Create, sort and manage custom floors/zones. Default: no additional preset; existing room assignments are adopted automatically. Current: {levels}"],["Erlaubt sind 1–365 Tage. Lüftungs- und Klimaergebnisse werden langfristig als kompakte Tageswerte gespeichert; hochaufgelöste Temperaturpunkte bleiben auf 30 Tage begrenzt.","Allowed range: 1–365 days. Compact daily ventilation and climate aggregates are retained long term; high-resolution temperature points remain limited to 30 days."],["Konfiguriere Raum {room_count}. Nach dem Speichern folgen die Himmelsrichtungen der ausgewählten Fenster/Türen. Standardwerte und optionale Felder sind direkt beschrieben.","Configure room {room_count}. Enter either direct volume in m³ OR length × width × height. Rooms may also be shown while excluded from calculations."],["Aus = konfigurierte VOC-/TVOC-Sensoren werden nicht eingelesen, nicht angezeigt und nicht für Zusatzempfehlungen berücksichtigt. Die Zuordnung im Raum bleibt gespeichert.","Off = configured VOC/TVOC sensors are not read, shown or used for supplemental recommendations. The room assignment remains stored."],["Gib nur den Anteil der aktuell überwachten Gesamtwassermenge an, der als entfernbares Feuchtepotenzial erreicht werden muss, bevor die normale Hauslüftung empfohlen wird.","Set only the share of currently monitored total water that must be removable before normal whole-house ventilation is recommended."],["Aus, nur bei erkannten Problemen, täglich nachts oder wöchentlich. Ein künftiger Nachtversand wird pro Installation deterministisch zwischen 02:00 und 03:59 Uhr verteilt.","Off, only for detected problems, nightly, or weekly. A future nightly upload is deterministically distributed between 02:00 and 03:59 local time."],["Sensoren aus der Auswahl oben, die auch bei Haustieren zuverlässig echte menschliche Präsenz erkennen. Diese Signale dürfen im Haustiermodus stärker gewichtet werden.","Sensors from the selection above that reliably detect real human presence even with pets. These signals may be weighted more strongly in pet mode."],["Aktivieren, wenn Haustiere Bewegungsmelder auslösen können. Klassische Bewegungsmelder werden dann deutlich schwächer gewichtet, damit kein Phantom-Bewohner entsteht.","Enable when pets can trigger motion sensors. Conventional motion sensors are then weighted much less strongly to avoid phantom occupants."],["Aus = konfigurierte PM2.5-Sensoren werden nicht eingelesen, nicht angezeigt und nicht für Zusatzempfehlungen berücksichtigt. Die Zuordnung im Raum bleibt gespeichert.","Off = configured PM2.5 sensors are not read, shown or used for supplemental recommendations. The room assignment remains stored."],["Automatisch verwendet die bewährte Standard-Raumgrenze. Prozent und Festwert überschreiben sie nur für diesen Raum; Gesundheits- und Sicherheitsregeln haben Vorrang.","Automatic uses the established default room threshold. Percentage and fixed modes override it only for this room; health and safety rules take priority."],["Entfeuchten toleriert für wirksamen Feuchteabbau etwas mehr Temperaturverlust. Komfort balanciert Feuchte und Energie. Sommer kühlen verwendet nur die Kühlparameter.","Dehumidify tolerates somewhat more temperature loss for effective moisture removal. Comfort balances moisture and energy. Summer cooling uses cooling-specific parameters only."],["Zeitraum für die intelligente Live-Prognose im Dashboard und in Raumdetails. Standard: 5 Minuten. Größere Werte reagieren träger, zeigen aber längerfristige Effekte.","Choose the time horizon used by the intelligent short-term forecast. The same value is used by the dashboard, detail view and forecast values."],["Optional. Der Messwert wird derzeit protokolliert und für spätere FreshAirIQ-Funktionen gesammelt. Er verändert die aktuelle Feuchte-/ml-Lüftungsempfehlung nicht.","Optional. This sensor value is currently logged for future FreshAirIQ features and does not change the current ventilation/moisture recommendation. Default: not set. Example: sensor.living_room_illuminance."],["Bestimmt die grundsätzliche Priorität der Recommendation Engine. Standard: Komfort. Nach der Auswahl zeigt FreshAirIQ nur die dazu passenden Feineinstellungen.","Choose the priority. FreshAirIQ then shows only the fine-tuning inputs relevant to that profile."],["„Mindestens einer offen“ = ein beliebiger Kontakt startet die Lüftung. „Alle offen“ = erst alle gewählten Kontakte gemeinsam gelten als aktiver Lüftungspfad.","“At least one open” = any selected contact starts ventilation. “All open” = only all selected contacts together count as an active ventilation path."],["Setzt alle globalen FreshAirIQ-Optionen auf die dokumentierten Standardwerte zurück. Räume, Sensorzuordnungen und gespeicherte Statistiken bleiben erhalten.","Restores all FreshAirIQ options to documented defaults. Rooms, sensors and statistics remain unchanged."],["Orientierungswert für das Ende einer erfolgreichen Entfeuchtung. FreshAirIQ berücksichtigt zusätzlich Restpotenzial, Prognose und Mindest-/Maximaldauer.","Guideline value for the end of successful dehumidification. FreshAirIQ also considers remaining potential, forecast and minimum/maximum duration."],["Wie lange muss ein Kontakt ununterbrochen offen sein, bevor FreshAirIQ eine Lüftung erkennt? Standard: 0 s. Beispiel: 120 s ignoriert kurzes Türöffnen.","Optional: time a contact must stay open before FreshAirIQ treats ventilation as active. 0 s reacts immediately."],["Beschreibt ausschließlich das Gebäude. Bewohner und Anwesenheit werden getrennt im Bewohnerprofil gepflegt – dadurch gibt es keine doppelten Angaben.","Describes the building only. Residents and presence are maintained separately in the resident profile so the same values are not entered twice."],["Ab diesem normalen Feuchteniveau wird ein Raum eher zum Lüftungskandidaten. Die absolute Feuchtedifferenz und das Potenzial müssen weiterhin passen.","Above this normal humidity level, a room is more likely to become a ventilation candidate. The absolute-humidity difference and potential must still be suitable."],["Lege den Raum vollständig an. Nach dem Speichern folgen Himmelsrichtungen und Kontaktverzögerungen. Jede bestätigte Seite wird sofort gespeichert.","Configure the room completely. After saving, contact orientations and contact delays follow. Each confirmed page is saved immediately."],["Wähle das Heizsystem für die Schätzung von Wiederaufheizkosten. Standard: Wärmepumpe. Im nächsten Schritt erscheinen nur passende Kostenparameter.","Select the heating system used to estimate reheating costs. Default: heat pump. The next step shows only the applicable cost parameters."],["Veraltetete Kompatibilitätsanzeige; Querlüftung wird vollständig auf der eigenen Seite „Querlüftung“ gepflegt. Beispiel: wohnzimmer+schlafzimmer.","Legacy compatibility display; cross ventilation is fully managed on the dedicated “Cross ventilation” page. Example: living_room+bedroom."],["Automatisch benötigt keinen weiteren Wert. Prozent und fester ml-Wert öffnen im nächsten Schritt ausschließlich das jeweils passende Eingabefeld.","Automatic needs no additional value. Percentage and fixed mL open only the relevant input on the next step."],["Optional. Nur zusammen mit einem Außen-Feuchtesensor verwenden. Dann ersetzt dieses Sensorpaar die Wetter-Entität für die aktuelle Außenluft.","Optional. Use only together with an outdoor humidity sensor. This sensor pair then replaces the weather entity for current outdoor air."],["Entfeuchten = Feuchteabbau hat Vorrang. Komfort = ausgewogene Entscheidung. Sommer kühlen = passive Abkühlung mit vertretbarem Feuchterisiko.","Dehumidify = moisture removal has priority. Comfort = balanced decision. Summer cooling = passive cooling with acceptable moisture risk."],["Räume anlegen, sortieren oder entfernen. Detailänderungen eines vorhandenen Raums sind zusätzlich direkt am jeweiligen Raum-Eintrag möglich.","Manage room structure here. Sensors, windows and other room details are edited directly on each room."],["Ab hier senkt FreshAirIQ die Anforderungen an die notwendige absolute Feuchtedifferenz, damit hohe Raumfeuchte schneller priorisiert wird.","Above this level, FreshAirIQ lowers the required absolute-humidity difference so high indoor humidity is prioritized sooner."],["Ordne jedem Kontakt die tatsächliche Himmelsrichtung zu. Standard: Unbekannt. Beispiel: Morgensonne = Ost, gegenüberliegende Seite = West.","Assign the actual compass orientation to each contact. Default: Unknown. Example: morning sun = East, opposite side = West."],["Wähle mindestens einen Kontakt, der diesen Raum tatsächlich belüftet. Das darf auch ein Fenster oder eine Tür in einem anderen Raum sein.","Select at least one contact that actually ventilates this room. It may also be a window or door located in another room."],["Nach dem Schließen wartet FreshAirIQ diese Zeit, damit sich Sensorwerte und Raumluft stabilisieren, bevor eine neue Empfehlung entsteht.","After closing, FreshAirIQ waits this long for sensor values and room air to stabilize before issuing a new recommendation."],["Pflicht für berechnete Räume. Der Sensor sollte nicht direkt im Spritzwasser, über einem Heizkörper oder unmittelbar am Fenster sitzen.","Required for calculated rooms. Do not place the sensor directly in splash water, above a radiator or immediately next to a window."],["Für eine abweichende Fenster-/Tür-Referenz müssen Temperatur und Luftfeuchtigkeit gemeinsam aus demselben Luftbereich gewählt werden.","A local window/door reference requires both temperature and humidity from the same air zone."],["FreshAirIQ bewertet diese Geräte als zusätzliche Maßnahmen. Ohne explizite Home-Assistant-Aktion wird nichts automatisch geschaltet.","FreshAirIQ evaluates these devices as additional interventions. Nothing is controlled automatically without an explicit Home Assistant action."],["Nur bei aktivierter Helligkeitsnutzung. Präzisiert vorhandene Verschattungs-Empfehlungen; die Lüftungsberechnung bleibt unverändert.","Used only when illuminance input is enabled. It refines existing shading recommendations; ventilation calculations remain unchanged."],["Optional für Kompatibilitätsanalysen. Exakte Gerätenamen, Seriennummern und exakte Gerätemodelle werden nicht an den Hub übertragen.","Optional for compatibility analysis. Exact device names, serial numbers and exact device models are not sent to the Hub."],["Längere Sessions werden nicht als saubere Lernprobe verwendet, weil Wetter-, Heizungs- und Nutzungseinflüsse zunehmend dominieren.","Longer sessions are not used as clean learning samples because weather, heating and occupancy effects increasingly dominate."],["Selten benötigte Wartungsfunktionen. Raumzuordnungen und Sensoren werden nur dort verändert, wo dies ausdrücklich beschrieben ist.","Maintenance functions that are rarely needed. Room assignments and sensors are changed only where this is explicitly stated."],["Einstellungen für die lokale Auswertung. Lernwerte selbst werden automatisch von FreshAirIQ aufgebaut und persistent gespeichert.","Settings for local analysis. Learned values are built automatically by FreshAirIQ and stored persistently."],["Lege die Himmelsrichtung jedes Lüftungskontakts fest. Standard: Unbekannt. Beispiel: Morgensonne = Ost, gegenüberliegend = West.","Set the compass direction for each ventilation contact as part of room setup."],["Näherungsfaktor für kältere Innenoberflächen. Niedrigere Werte bedeuten stärkere angenommene Abkühlung Richtung Außentemperatur.","Approximation factor for colder indoor surfaces. Lower values mean stronger assumed cooling toward outdoor temperature."],["Unterscheidet u. a. freistehendes Haus, Doppelhaushälfte, Reihenmittel-/Reihenendhaus, Wohnung, Maisonette und Mehrfamilienhaus.","Distinguishes detached house, semi-detached house, mid/end-terrace house, apartment, maisonette and multi-family building, among others."],["Oberhalb dieses Index wird bei aktivem Veto eine normale Lüftung verschoben; kritisches Schimmel-/CO₂-Risiko bleibt priorisiert.","Above this index, normal ventilation is postponed when the veto is active; critical mould/CO₂ risk remains prioritized."],["Die Feuchtedifferenzen sind widersprüchlich: Schließ-Differenz ≤ Mindestdifferenz bei hoher Feuchte ≤ normale Mindestdifferenz.","Humidity differences are inconsistent: close difference ≤ high-humidity minimum difference ≤ normal minimum difference."],["Gib ausschließlich das entfernbare Feuchtepotenzial in ml an, ab dem FreshAirIQ eine normale Hauslüftung als sinnvoll bewertet.","Set only the removable moisture potential in mL from which FreshAirIQ considers normal whole-house ventilation worthwhile."],["Übernimmt die vorhandene ältere FreshAirIQ-Konfiguration, damit Räume und Sensorzuordnungen nicht neu angelegt werden müssen.","Default: on. Imports the existing legacy FreshAirIQ configuration so rooms and sensor assignments do not need to be recreated."],["Sendet eine Meldung, wenn weiterer Luftaustausch keinen ausreichenden Nutzen mehr bringt oder Komfortgrenzen erreicht werden.","Sends a notification when further air exchange no longer provides enough benefit or comfort limits are reached. Default: on."],["Ordne den erwachsenen Bewohnern ihre primären person/device_tracker-Entitäten zu. Mehrere Bewohner können ausgewählt werden.","Assign the primary person/device_tracker entities to adult residents. Multiple residents can be selected."],["Die persönlichen Bewohnerprofile enthalten ungültige Daten. Bitte die Zuordnung prüfen oder im Dashboard-Zahnrad bearbeiten.","The resident profile assignments are invalid. Use a JSON object or edit them from the FreshAirIQ dashboard settings."],["Aktivieren setzt nur globale Optionen auf dokumentierte Standardwerte zurück; Räume und Sensorzuordnungen bleiben erhalten.","Default: off. Enabling resets only global options to documented defaults; rooms and sensor assignments remain."],["Stockwerke und Zonen sind frei definierbar. Auch Zwischengeschosse, Anbauten, Wintergärten oder Außenbereiche sind möglich.","Floors and zones are user-defined, including mezzanines, annexes, conservatories or outdoor areas."],["Ordne jedem Kontakt die tatsächliche Himmelsrichtung zu. Standard: Unbekannt. Die bestätigte Seite wird sofort gespeichert.","Assign the actual compass orientation to each contact. Default: Unknown. The confirmed page is saved immediately."],["Ein einzelner problematischer Raum kann ab diesem entfernbaren Potenzial unabhängig von der Haussumme priorisiert werden.","A single problematic room can be prioritized from this removable potential onward, independently of the house total."],["Ändere Raumdaten, Sensoren und Eigenschaften. Sobald du diese Seite speicherst, werden die Änderungen sofort übernommen.","Replace temperature, humidity or CO₂ sensors, change room size/zone or adjust ventilation contacts."],["Löscht gelernte Raum-Luftwechsel, Routinen und Nachtmodell. Raumkonfiguration, Optionen und Statistik bleiben erhalten.","Deletes learned room air-exchange values, routines and the night model. Room configuration, options and statistics remain intact."],["Passt nur Komfortsprache und nicht sicherheitskritische Gewichtungen an. Die physikalische Prognose bleibt unverändert.","Adjusts comfort wording and non-safety-critical weighting only. The physical forecast remains unchanged."],["Vergib Positionsnummern. Standard: aktuelle Reihenfolge. Niedrigere Zahl = weiter oben im Dashboard und in Raumlisten.","Assign position numbers. Default: current order. A lower number places the room higher in the dashboard and room lists."],["Eine erneute Empfehlung innerhalb der Nachlaufphase benötigt mindestens diesen zusätzlichen erwarteten Feuchtenutzen.","A repeated recommendation during the cooldown period requires at least this much additional expected moisture benefit."],["Optional für Kinder mit eigenem Tracker. Kinder ohne Tracker werden weiterhin über die Haushaltslogik berücksichtigt.","Optional for children with their own tracker. Children without a tracker are still handled by household logic."],["Wähle einen unbenutzten Bereich. Bereiche mit noch zugeordneten Räumen müssen zuerst von diesen Räumen gelöst werden.","Select an unused area. Areas that still contain rooms must first be removed from those rooms."],["Ändere Raumdaten, Sensoren, Feuchtequellen und Berechnungsgrundlagen. Jede bestätigte Seite wird sofort gespeichert.","Change room data, sensors, moisture sources and calculation parameters. Each confirmed page is saved immediately."],["Vor diesem Zeitpunkt empfiehlt FreshAirIQ normalerweise nicht allein wegen nachlassendem Zusatznutzen das Schließen.","Before this point, FreshAirIQ normally does not recommend closing solely because additional benefit is declining."],["Optional. Empfohlene Quelle für Außenluft und Wetterprognose. Kann jederzeit nach der Installation ergänzt werden.","Optional. Recommended source for outdoor air and weather forecasts. It can be added at any time after installation."],["„Mindestens einer offen“ reagiert auf jeden gewählten Kontakt; „Alle offen“ erst auf den gemeinsamen Lüftungspfad.","“At least one open” reacts to any selected contact; “All open” only to the shared ventilation path."],["Ist die verbleibende absolute Feuchtedifferenz kleiner, bringt weiteres Lüften meist nur noch wenig Feuchteertrag.","If the remaining absolute-humidity difference is smaller, further ventilation usually provides little additional moisture removal."],["Empfohlen: automatisch nach Haus-/Wohnungsgröße. Prozent- und fester mL-Modus bleiben für Spezialfälle verfügbar.","Recommended: adaptive to dwelling size. FreshAirIQ targets about four meaningful ventilation cycles per day and uses cool morning/evening opportunities earlier on warm days."],["Frei wählbarer Anzeigename, z. B. „Wohnzimmer“. Daraus erzeugt FreshAirIQ einen stabilen internen Raumschlüssel.","Custom display name, for example “Living room”. FreshAirIQ derives a stable internal room key from it."],["Wann genügend entfernbares Wasser für eine Empfehlung vorhanden ist. Standard: automatische Hausgrößen-Schwelle.","Defines when enough removable water is available for a recommendation. Default: automatic home-size threshold."],["Grenze für optionale VOC-/TVOC-basierte Zusatzempfehlungen. Kein Einfluss auf die kanonische Lüftungsberechnung.","Threshold for optional VOC/TVOC-based supplemental recommendations. It does not change canonical ventilation calculations."],["Wähle den Raum. Anschließend bekommt jeder Lüftungskontakt seine eigene Himmelsrichtung, z. B. Süd oder Nordost.","Select the room. Each ventilation contact can then receive its own compass direction, for example South or North-East."],["Optional. FreshAirIQ kann bei Wärme Verschattung empfehlen; keine automatische Steuerung ohne explizite Aktion.","Optional room-climate input or intervention target. FreshAirIQ only recommends device actions by default; actuation requires an explicit Home Assistant action."],["Obergrenze einer normalen Lüftungsempfehlung. Sicherheits-/Gesundheitslogik kann weiterhin gesondert reagieren.","Upper limit for a normal ventilation recommendation. Safety/health logic may still react separately."],["Kritische PM2.5-Grenze für Diagnose und spätere Priorisierung. Kein Einfluss auf die bestehende Lüftungsphysik.","Critical PM2.5 threshold for diagnostics and future prioritisation. It does not change the existing ventilation physics."],["Erlaubt sind 1–120 Minuten. Für spontane Lüftungsentscheidungen sind 5–20 Minuten meist am aussagekräftigsten.","Allowed range: 1–120 minutes. For immediate ventilation decisions, 5–20 minutes is usually the most informative range."],["Nur im Festwertmodus: entfernbares Feuchtepotenzial, ab dem dieser Raum eigenständig priorisiert werden darf.","Fixed mode only: removable moisture potential from which this room may be prioritized individually."],["Kritische VOC-Grenze für Diagnose und spätere Priorisierung. Kein Einfluss auf die bestehende Lüftungsphysik.","Critical VOC threshold for diagnostics and future prioritisation. It does not change the existing ventilation physics."],["Grenze für optionale PM2.5-basierte Zusatzempfehlungen. Kein Einfluss auf die kanonische Lüftungsberechnung.","Threshold for optional PM2.5-based supplemental recommendations. It does not change canonical ventilation calculations."],["Nutzt Haushaltskontext für passendere Empfehlungen; Gesundheits- und Sicherheitsgrenzen bleiben unverändert.","Uses household context for more suitable recommendations; health and safety limits remain unchanged."],["Hilft bei Raumgruppierung und Querlüftung. Eigene Bereiche kannst du unter „Stockwerke & Bereiche“ anlegen.","Helps with room grouping and cross ventilation. You can create custom areas under “Floors & areas”."],["Jeder Bereich erhält eine Positionsnummer. Standard: aktuelle Reihenfolge. Niedrigere Zahl = weiter oben.","Each area receives a position number. Default: current order. A lower number places it higher."],["Außen-Temperatur und Außen-Luftfeuchtigkeit müssen gemeinsam ausgewählt oder beide leer gelassen werden.","Outdoor temperature and outdoor humidity must be selected together or both left empty."],["Weitere fünf Minuten sollen mindestens diese zusätzliche Wassermenge entfernen, sonst sinkt der Nutzen.","Another five minutes should remove at least this additional amount of water; otherwise the benefit is considered too low."],["Anteil der aktuellen Wassermenge in der Hausluft, ab dem eine Lüftungsempfehlung ausgelöst werden kann.","Example: 10% of 6,000 mL currently monitored water gives a 600 mL ventilation threshold."],["Optional. Wird als alternative Kühl-/Heizmaßnahme berücksichtigt, aber nicht selbstständig geschaltet.","Optional room-climate input or intervention target. FreshAirIQ only recommends device actions by default; actuation requires an explicit Home Assistant action."],["Wähle den Raum. Im nächsten Schritt kannst du jedem Lüftungskontakt eine eigene Himmelsrichtung geben.","Choose the room. The next step lets you assign an individual orientation to each ventilation contact."],["Grundprofil für Gebäudehülle und Luftaustausch. Entspricht exakt der Einstellung im Dashboard-Zahnrad.","Base profile for the building envelope and air exchange. This is the same setting used by the dashboard settings."],["Aus = Raum bleibt sichtbar, fließt aber nicht in Empfehlungen, Hausbilanz, Statistik oder Lernen ein.","Off = the room remains visible but is excluded from recommendations, house balance, statistics and learning."],["Verhindert, dass kurz nach einer abgeschlossenen Lüftung sofort dieselbe Empfehlung erneut erscheint.","Prevents the same recommendation from reappearing immediately after completed ventilation."],["Name frei wählen, z. B. „Erdgeschoss“, „Kellergeschoss“, „Wintergarten“ oder „Anbau“. Standard: leer.","Choose any name, for example “Ground floor”, “Basement”, “Conservatory” or “Extension”. Default: empty."],["Die Feuchtewerte müssen logisch aufeinander folgen: Zielwert ≤ Lüftungsstartwert ≤ hohe Luftfeuchte.","Humidity values must be ordered logically: target ≤ ventilation start ≤ high humidity."],["Pflicht für berechnete Räume. Möglichst einen Sensor verwenden, der die tatsächliche Raumluft misst.","Required for calculated rooms. Prefer a sensor that measures the actual room air."],["Besondere Eigenschaften wie Dusche, Badewanne oder Sauna. Standard: keine Feuchtequelle hinterlegt.","Special properties such as shower, bathtub or sauna. Default: no moisture source configured."],["Statistik und technische Modellparameter. Die Standardwerte sind für die meisten Haushalte passend.","Statistics and technical model parameters. Defaults suit most homes."],["Optionaler numerischer Pollenindex. Wird nur genutzt, wenn „Pollen berücksichtigen“ aktiviert ist.","Optional numeric pollen index. Used only when pollen consideration is enabled."],["Aus = Raum bleibt sichtbar, beeinflusst aber Empfehlungen, Hausbilanz, Statistik und Lernen nicht.","Off = the room remains visible but does not affect recommendations, house balance, statistics or learning."],["Warnt, wenn für eine belastbare Empfehlung erforderliche Sensordaten fehlen oder unplausibel sind.","Warns when sensor data required for a reliable recommendation is missing or implausible. Default: on."],["Nur im Prozentmodus: Mindestanteil der aktuell überwachten Wassermenge, der entfernbar sein soll.","Percentage mode only: minimum share of the currently monitored water amount that should be removable."],["Lege fest, welche Meldungen FreshAirIQ senden darf und wie Wiederaufheizkosten geschätzt werden.","Define which notifications FreshAirIQ may send and how reheating costs are estimated."],["Schwächt klassische Bewegungssensoren, damit Haustiere nicht als Bewohner interpretiert werden.","Reduces the weight of conventional motion sensors so pets are not interpreted as residents."],["Mindestunterschied zwischen absoluter Feuchte innen und Referenzluft für normale Entfeuchtung.","Minimum difference between indoor absolute humidity and reference air for normal dehumidification."],["Optional. Alternative/Ergänzung bei Feinstaub, VOC oder pollenbedingt ungünstiger Außenluft.","Optional room-climate input or intervention target. FreshAirIQ only recommends device actions by default; actuation requires an explicit Home Assistant action."],["Löscht nur gelernte Modelle; Räume, Sensorzuordnungen und globale Optionen bleiben erhalten.","Default: off. Deletes only learned models; rooms, sensor assignments and global options remain."],["Zusätzlicher Feuchteabbau, den FreshAirIQ für die nächsten fünf Minuten mindestens erwartet.","Minimum additional moisture removal FreshAirIQ expects over the next five minutes. Example: 25 ml in Comfort mode."],["Vorhandenen Raum mit denselben Sensor- und Eigenschaftenfeldern wie im Dashboard bearbeiten","Edit an existing room with the same sensor and property fields that are available in the dashboard."],["Oberhalb dieser Raumfeuchte wird Kühlung nicht auf Kosten zusätzlicher Feuchte priorisiert.","Above this indoor humidity, cooling is not prioritised at the cost of additional moisture. Default: 70%."],["Frei wählbarer Anzeigename. Daraus erzeugt FreshAirIQ intern einen stabilen Raumschlüssel.","Freely selectable display name. FreshAirIQ derives a stable internal room key from it."],["Grundgrenzen für relative und absolute Feuchte. Standard: 62/68/58 % und 2,5/1,5/0,4 g/m³.","Core limits for relative and absolute humidity. Default: 62/68/58% and 2.5/1.5/0.4 g/m³."],["Wähle den Raum, dessen Sensoren, Größe, Bereich oder optionale Geräte du ändern möchtest.","Select the room whose sensors, size, area or optional devices you want to edit. Example: “Living room”. No preselection."],["Wähle den zu entfernenden Raum. Räume werden erst nach zusätzlicher Bestätigung gelöscht.","Select the room to remove. Rooms are deleted only after an additional confirmation."],["Eher warm, ausgewogen oder eher kühl. Sicherheitsentscheidungen werden nie abgeschwächt.","Warm, balanced or cool. Safety decisions are never weakened."],["Temperatur-/Feuchtereferenz und Rollo/Jalousie separat für jede einzelne Lüftungsöffnung","Temperature and humidity reference for each individual ventilation opening"],["Empfohlen, wenn deine Wetter-Entität zuverlässige Temperatur- und Feuchtewerte liefert.","Recommended when your weather entity provides reliable temperature and humidity values."],["Wähle vorhandene notify.*-Dienste. Ohne Empfänger werden keine Pushmeldungen versendet.","Select existing notify.* services. No push notifications are sent without a recipient."],["Verwendet nur vorhandene lokale Winddaten; ohne Windrichtung bleibt der Faktor neutral.","Uses only available local wind data; without wind direction the factor remains neutral."],["Nur Bereiche ohne zugeordnete Räume können entfernt werden. Standard: keine Vorauswahl.","Only unused zones can be removed."],["Wähle alle Fenster/Türen, über die FreshAirIQ eine Lüftung dieses Raums erkennen soll.","Select all windows/doors through which FreshAirIQ should detect ventilation for this room."],["Optional. Mit CO₂-Sensor kann FreshAirIQ Luftqualität zusätzlich zur Feuchte bewerten.","Optional. With a CO₂ sensor, FreshAirIQ can assess air quality in addition to humidity."],["Leer bedeutet alle Räume. Auswahl begrenzt raumbezogene Meldungen auf bestimmte Räume.","Empty means all rooms. A selection limits room-specific messages to those rooms."],["Fester entfernbarer Feuchtewert, ab dem eine Lüftungsempfehlung ausgelöst werden kann.","Example: 500 mL means combined removable potential must reach at least 500 mL. Health, mould and critical CO₂ rules may intervene earlier."],["Ab diesem CO₂-Wert steigt die Lüftungspriorität, sofern ein CO₂-Sensor vorhanden ist.","Above this CO₂ value, ventilation priority increases when a CO₂ sensor is available."],["Wähle den Raum, dessen Fenster-/Türkontakte eine Öffnungsverzögerung erhalten sollen.","Select the room whose window/door contacts should receive an opening delay. Example: count a basement door as ventilation only after 120 s."],["Maximal tolerierter zusätzlicher Raumtemperaturverlust in den nächsten fünf Minuten.","Maximum tolerated additional room-temperature loss over the next five minutes. Example: 0.6 °C in Comfort mode."],["Standard: keine Vorauswahl. Entweder Volumen direkt oder vollständige Maße angeben.","Enter either the volume directly or length, width and height."],["Ab dieser geschätzten Oberflächenfeuchte meldet FreshAirIQ erhöhtes Schimmelrisiko.","Above this estimated surface humidity, FreshAirIQ reports elevated mould risk."],["Aktiviert das persistente Lernen von Luftwechsel, Routinen und Prognosekorrekturen.","Enables persistent learning of air exchange, routines and forecast corrections. Default: on."],["Haus = zentrale Empfehlungen. Raum = raumbezogene Meldungen. Beides = beide Ebenen.","House = central recommendations. Room = room-specific messages. Both = both levels."],["Entweder das Volumen direkt in m³ eintragen ODER Länge, Breite und Höhe verwenden.","Enter the volume directly in m³ OR use length, width and height."],["Je höher der COP/JAZ, desto weniger Strom muss zum Wiederaufheizen gekauft werden.","The higher the COP/seasonal performance factor, the less electricity is required for reheating."],["Maximal akzeptierter prognostizierter Feuchteeintrag während fünf Minuten Kühlung.","Maximum accepted predicted moisture gain during five minutes of cooling. Default: 60 ml."],["Personen, Tracker, Präsenz, Komfort, Nacht und persönliche Profile an einer Stelle","People, trackers, presence, comfort, night settings and personal profiles in one place"],["Automatisch, prozentual oder als fester ml-Wert – mit eindeutiger Eingabe je Modus","Automatic, percentage or fixed mL with one unambiguous input per mode"],["Zeitgrenzen, Stabilisierung und Schutz vor zu häufigen Wiederholungsempfehlungen.","Time limits, stabilization and protection against overly frequent repeated recommendations."],["Optional. Ohne Wetter-Entität nur gemeinsam mit Außenluftfeuchtigkeit verwenden.","Optional. Use only together with an outdoor humidity sensor."],["Optional. Alternative bei hoher Feuchte, ungünstiger Außenluft oder Pollen-Veto.","Optional room-climate input or intervention target. FreshAirIQ only recommends device actions by default; actuation requires an explicit Home Assistant action."],["Wähle eine lokale Wetter-Entität oder sowohl Temperatur- als auch Feuchtesensor.","Select a local weather entity or both temperature and humidity sensors."],["Die Schimmelwarnschwelle muss niedriger als die kritische Schimmelschwelle sein.","The mould warning threshold must be lower than the critical mould threshold."],["Begrenzt den zusätzlich tolerierten Temperaturverlust der nächsten fünf Minuten.","Limits the additional temperature loss tolerated over the next five minutes."],["Optional. Kann Frischluftbedarf bei CO₂ oder Lüftungsempfehlungen unterstützen.","Optional room-climate input or intervention target. FreshAirIQ only recommends device actions by default; actuation requires an explicit Home Assistant action."],["Nur im Prozentmodus: Anteil der aktuellen Wassermenge in der Luft dieses Raums.","Percentage mode only: share of the current water content in this room air."],["Die Öffnungsverzögerung kann für jeden Kontaktsensor separat festgelegt werden.","Configure opening delay separately for every contact."],["Nutzt Haushaltskontext und gelerntes Verhalten nur für passendere Empfehlungen.","Uses household context and learned behaviour only for more suitable recommendations."],["Gib entweder das Raumvolumen in m³ oder vollständig Länge, Breite und Höhe an.","Enter either room volume or complete length, width and height."],["Einstellungsdialog schließen; bereits bestätigte Seiten sind schon gespeichert","Apply all changes and reload FreshAirIQ"],["Ab dieser geschätzten Oberflächenfeuchte gilt das Schimmelrisiko als kritisch.","Above this estimated surface humidity, mould risk is considered critical."],["Optionale automatische, lokal pseudonymisierte Diagnoseübertragung vorbereiten","Prepare optional automatic, locally pseudonymised diagnostics sharing"],["Optional. Wird später nur bei aktivierter Pollenberücksichtigung ausgewertet.","Optional. Evaluated only when pollen consideration is enabled."],["Gib bei der Berechnung aus Abmessungen Länge, Breite und Höhe vollständig an.","For dimension-based volume, enter complete length, width and height."],["Temperatur, Feuchte und die Kontakte, mit denen FreshAirIQ Lüftungen erkennt.","Sensors and contacts FreshAirIQ uses for this room."],["Entfernt den Raum nach Bestätigung aus FreshAirIQ. Standard: Bestätigung aus.","The room will no longer be evaluated after saving."],["FreshAirIQ speichert lokal bis zu 30 Tage. Standard: 14 Tage Anzeigezeitraum.","FreshAirIQ can show 1–365 days of compact daily ventilation and climate aggregates. High-resolution temperature points remain limited to 30 days for performance."],["Berücksichtigt hausinterne Verteilverluste der Fernwärme. 1,00 = verlustfrei;","Accounts for distribution losses inside the home. 1.00 = no loss; default: 0.98."],["Optional, kommagetrennt. Kinder ohne Tracker dürfen ebenfalls benannt werden.","Optional, comma-separated. Children without trackers may also be named."],["Nur im Modus „Fester mL-Wert“: Mindestpotenzial über alle berechneten Räume.","Fixed mL mode only: minimum potential across all calculated rooms."],["Steuert, ob und wie lange FreshAirIQ gültige Lüftungen als Lernproben nutzt.","Controls whether and for how long FreshAirIQ uses valid ventilation sessions as learning samples."],["Ende des Zeitfensters, für das die Nachtprognose berechnet und gelernt wird.","End of the time window for which the overnight forecast is calculated and learned."],["Sendet eine Meldung, wenn FreshAirIQ einen sinnvollen Lüftungsstart erkennt.","Sends a notification when FreshAirIQ detects a useful time to start ventilation. Default: on."],["Gelernte Raum- und Nachtmodelle löschen; Räume und Optionen bleiben erhalten","Delete learned room and night models; rooms and options remain intact"],["Optional, kommagetrennt und passend zur Reihenfolge der Erwachsenen-Tracker.","Optional, comma-separated and matching the order of the adult trackers."],["Zusätzliche Präsenzsignale und Verhalten von Bewohnern ohne eigenen Tracker.","Additional presence signals and handling of residents without their own tracker."],["Sensoren, die auch bei Haustieren zuverlässig menschliche Präsenz anzeigen.","Sensors that reliably indicate human presence even when pets are present."],["Haushaltsweiter Komfortstandard. Einzelne Profile können ihn überschreiben.","Household comfort default. Individual profiles may override it."],["Optional. Ohne Wetter-Entität nur gemeinsam mit Außentemperatur verwenden.","Optional. Use only together with an outdoor temperature sensor."],["Für diesen Raum bzw. diese Anfrage gibt es keine ausführbare Intervention.","No executable intervention matches this room or request."],["Wird zusammen mit den Lernwerten für Tages- und Nachtprognosen verwendet.","Used together with learned values for daytime and overnight forecasts."],["Kinder erhalten im Startmodell einen eigenen, niedrigeren Feuchtebeitrag.","Children receive their own lower moisture contribution in the initial model."],["Für berechnete Räume ist mindestens ein Fenster-/Türkontakt erforderlich.","Calculated rooms need at least one window/door contact."],["Die ausgewählte Intervention enthält keine gültige Home-Assistant-Aktion.","The selected intervention does not contain a valid Home Assistant action."],["Die CO₂-Warnschwelle muss niedriger als die kritische CO₂-Schwelle sein.","The CO₂ warning threshold must be lower than the critical CO₂ threshold."],["Typischer Heizwert; kann an den verwendeten Brennstoff angepasst werden.","Typical heating value; can be adjusted to the fuel being used."],["Lege fest, wie FreshAirIQ Komfort, Feuchte, Pollen und Wind priorisiert.","Control how FreshAirIQ prioritizes comfort, humidity, pollen and wind."],["Gewichtet nur nicht sicherheitskritische Komfort-/Energieentscheidungen.","Weights only non-safety-critical comfort/energy decisions."],["Gib entweder das Raumvolumen oder Länge, Breite und Höhe vollständig an.","Enter either room volume or complete length, width and height."],["Die konfigurierte Interventions-Entität {entity_id} ist nicht verfügbar.","The configured intervention entity {entity_id} is unavailable."],["Verhindert wiederholte identische Meldungen innerhalb dieses Zeitraums.","Prevents repeated identical notifications within this period."],["Raumklima, ausgewogen oder Energie sparen. Wirkt nur im Komfortbereich.","Indoor climate, balanced or energy saving. Applies only within the comfort layer."],["Raumeinstellungen schließen; bereits bestätigte Seiten sind gespeichert","Close room settings; pages already confirmed are saved"],["Optional. Wird nur bei aktivierter Pollenberücksichtigung ausgewertet.","Optional. Evaluated only when pollen consideration is enabled."],["Optional. Besonders für Dusche, Bad, Küche oder andere Feuchtequellen.","Optional room-climate input or intervention target. FreshAirIQ only recommends device actions by default; actuation requires an explicit Home Assistant action."],["Bewertet, wie viel Feuchte pro 0,1 °C Temperaturverlust entfernt wird.","Evaluates how much moisture is removed per 0.1 °C of temperature loss."],["Optional. Zentrale/dezentrale Lüftung, WRG oder vergleichbares Gerät.","Optional room-climate input or intervention target. FreshAirIQ only recommends device actions by default; actuation requires an explicit Home Assistant action."],["Betriebsprofil, Prognosen, Pollen/Wind, Querlüftung und Modellgrenzen","Operating profile, forecasts, pollen/wind, cross ventilation and model limits"],["Wird nur verwendet, wenn im Raum ein Luftbefeuchter konfiguriert ist.","Only used when a room humidifier is configured."],["Wähle alle Kontakte, über die FreshAirIQ eine Lüftung erkennen soll.","Select all contacts through which FreshAirIQ should detect ventilation."],["Wird nur verwendet, wenn Rollos/Jalousien im Raum konfiguriert sind.","Only used when covers/blinds are configured."],["Querlüftungspaare (Raumschlüssel+Raumschlüssel, …) (Standard: leer)","Cross-ventilation pairs (room_key+room_key,...) (Default: empty)"],["Sommerkühlung wird erst oberhalb dieser Raumtemperatur priorisiert.","Summer cooling is prioritised only above this room temperature. Default: 24 °C."],["Die Home-Assistant-Aktion {service} konnte nicht ausgeführt werden.","The Home Assistant action {service} could not be executed."],["Optional. Nur zusammen mit einem Außen-Temperatursensor verwenden.","Optional. Use only together with an outdoor temperature sensor."],["Sendet nach einer abgeschlossenen Lüftung das ermittelte Ergebnis.","Sends the measured result after a completed ventilation session. Default: on."],["Alle globalen Optionen auf die dokumentierten Standardwerte setzen","Reset all global options to the documented defaults"],["Automatisch, nachts lieber geschlossen oder nachts offen ist okay.","Automatic, prefer closed at night, or open at night is acceptable."],["Schätzt Bewohner ohne Tracker anhand des sicheren Haushaltsstatus.","Estimates residents without trackers from the reliable household presence state."],["Aktiviert = weiteren Raum anlegen; aus = Einrichtung abschließen.","Default: on. Enabled = add another room; disabled = finish setup."],["Minimale Feuchte-/Temperatur-Effizienz (Standard: 8 ml je 0,1 °C)","Minimum efficiency (mL/0.1°C) (Default: 8.0)"],["Der Betriebsmodus {option} wird von FreshAirIQ nicht unterstützt.","The operating profile {option} is not supported by FreshAirIQ."],["Optional. Wird nur bei deutlich zu trockener Raumluft empfohlen.","Optional room-climate input or intervention target. FreshAirIQ only recommends device actions by default; actuation requires an explicit Home Assistant action."],["Nur erforderlich, wenn kein direktes Raumvolumen angegeben wird.","Only required when no direct room volume is entered."],["Ab diesem CO₂-Wert wird die Luftqualität als kritisch behandelt.","Above this CO₂ value, air quality is treated as critical."],["Aus = Pollen werden angezeigt, blockieren aber keine Empfehlung.","Off = pollen is displayed but does not block a recommendation."],["Automatische Diagnoseübertragung (Beta-Standard: Täglich nachts)","Automatic diagnostics sharing (beta default: Nightly)"],["Luftfeuchtesensor des Raums. Für berechnete Räume erforderlich;","Humidity sensor for the room. Required for calculated rooms; default: no preselection."],["Optional. Nur zusammen mit einem Außen-Feuchtesensor verwenden.","Optional. Use only together with an outdoor humidity sensor."],["Grenzen für geschätzte Oberflächenfeuchte und CO₂-Luftqualität.","Limits for estimated surface humidity and CO₂ air quality."],["Bestimmt ausschließlich die Berechnung der Wiederaufheizkosten.","Used only for reheating-cost calculations. Example: for a heat pump, electricity price and COP/SCOP are used. Default: heat pump."],["Fensterausrichtung mit Winddaten berücksichtigen (Standard: an)","Use window orientation with wind data (Default: on)"],["Benachrichtigungen und die Kostenschätzung für dein Heizsystem.","Notifications and heating cost estimation."],["Festlegen, welche Räume gemeinsam einen Luftstrom bilden können","Define which rooms can form a shared airflow path"],["Temperatursensor des Raums. Für berechnete Räume erforderlich;","Temperature sensor for the room. Required for calculated rooms; default: no preselection."],["Abwägung zwischen zusätzlichem Feuchteertrag und Wärmeverlust.","Balances additional moisture removal against heat loss."],["Entweder Volumen direkt in m³ oder vollständige Maße angeben.","Enter either the volume directly in m³ or complete dimensions."],["Die Mindestdauer darf nicht größer als die Maximaldauer sein.","Minimum ventilation duration must not exceed maximum duration."],["Warnt bei relevantem geschätztem Oberflächen-/Schimmelrisiko.","Warns about relevant estimated surface/mould risk. Default: on."],["Quelle für Außen-Temperatur, Außenfeuchte und optional Pollen","Source for outdoor temperature, outdoor humidity and optional pollen"],["Maximal tolerierter Feuchteeintrag in 5 Min (Standard: 60,0)","Maximum tolerated moisture gain in 5 min (Default: 60.0)"],["Verbindungen zwischen Bereichen/Stockwerken (Standard: leer)","Connections between areas/floors (Default: empty)"],["Groben Geräte-/Browser-Kontext mitsenden (Beta-Standard: An)","Include coarse device/browser context (beta default: On)"],["Maximaler Temperaturverlust in 5 Minuten (Standard: 0,6 °C)","Maximum next-5-minute temperature loss (°C) (Default: 0.6)"],["Bewohner ohne Tracker folgen Haushaltsstatus (Standard: an)","Residents without trackers follow household status (Default: on)"],["Die Außenluft muss mindestens um diesen Betrag kühler sein.","Outdoor air must be at least this much cooler. Default: 2 °C."],["Gib entweder das Raumvolumen oder vollständige Raummaße an.","Enter either room volume or complete room dimensions."],["Für eine FreshAirIQ-Intervention ist room_key erforderlich.","A room_key is required to execute a FreshAirIQ intervention."],["Referenzluft & Rollo/Jalousie je Fenster/Tür · {room_name}","Reference air per window/door · {room_name}"],["Name, Stockwerk/Bereich und Teilnahme an den Berechnungen.","Name, level and whether the room participates in calculations."],["Reduzierte Mindestdifferenz bei bereits hoher Raumfeuchte.","Reduced minimum difference when room humidity is already high."],["Schwellen, Zeitgrenzen, Effizienz, Schimmel/CO₂ und Lernen","Thresholds, time limits, efficiency, mould/CO₂ and learning"],["Minimale Differenz bei hoher Feuchte (Standard: 1,5 g/m³)","Minimum difference at high RH (g/m³) (Default: 1.5)"],["Mindestpotenzial einzelner Problemraum (Standard: 100 ml)","Minimum critical-room potential (mL) (Default: 100.0)"],["Maximaler Temperaturverlust nächste 5 Min (Standard: 0,6)","Maximum temperature loss next 5 min (Default: 0.6)"],["Priorität zwischen Entfeuchten, Komfort und Sommerkühlung","Priority between dehumidification, comfort and summer cooling"],["Außenluftfeuchtigkeit (optional – später konfigurierbar)","Outdoor humidity sensor (optional)"],["Klimaanlage/Heizung (optional) (Standard: nicht gesetzt)","Climate/HVAC entity (optional)"],["Lüftungs-/WRG-Gerät (optional) (Standard: nicht gesetzt)","Ventilation/HRV device (optional)"],["Neuen Raum mit Sensoren, Größe und Eigenschaften anlegen","Create a new room with sensors, size and properties"],["Mindestpotenzial Haus bei festem Wert (Standard: 500 ml)","Minimum total potential (mL) (Default: 500.0)"],["Benötigt einen Pollenindex-Sensor unter Außenluftquelle.","Requires a pollen-index sensor under the outdoor-air source."],["Nutzbarer Anteil der im Heizöl enthaltenen Wärmeenergie.","Usable share of the heat energy contained in heating oil. Default: 0.88."],["Mindestverhältnis von Feuchteabbau zu Temperaturverlust.","Minimum ratio of moisture removal to temperature loss. Example: 8 ml per 0.1 °C."],["Verzögerung pro Kontakt, bevor eine Lüftung erkannt wird","Delay per contact before ventilation is detected"],["FreshAirIQ konnte die Statistikdaten nicht zurücksetzen.","FreshAirIQ could not reset the statistics data."],["Reihenfolge im Dashboard und in Auswahllisten festlegen","Set the order in the dashboard and selection lists"],["Minimale absolute Feuchtedifferenz (Standard: 2,5 g/m³)","Minimum humidity difference (g/m³) (Default: 2.5)"],["Mindesthelligkeit für Verschattung (Standard: 10000 lx)","Minimum illuminance for shading (Default: 10000 lx)"],["Angezeigten Zeitraum zwischen 1 und 365 Tagen festlegen","Set the displayed period between 1 and 365 days"],["Helligkeitssensor (optional) (Standard: nicht gesetzt)","Illuminance sensor (optional)"],["Empfohlene Standardquelle für aktuelle Außenluftdaten.","Recommended default source for current outdoor-air data."],["Schwellenart für Hauspotenzial (Standard: automatisch)","Ventilation threshold mode (Default: adaptive_home_size)"],["Mindestnutzen für erneute Empfehlung (Standard: 80 ml)","Minimum benefit for a repeated recommendation (Default: 80 ml)"],["Mindestertrag der nächsten 5 Minuten (Standard: 25 ml)","Minimum next-5-minute return (mL) (Default: 25.0)"],["Minimale Feuchte-/Temperatur-Effizienz (Standard: 8,0)","Minimum moisture/temperature efficiency (Default: 8.0)"],["Person- oder device_tracker-Entitäten der Erwachsenen.","Person or device_tracker entities for adult residents."],["{room_name} · Referenzluft & Rollo/Jalousie je Öffnung","{room_name} · Reference air per opening"],["VOC-/TVOC-Sensor (optional) (Standard: nicht gesetzt)","VOC/TVOC sensor (optional)"],["Rollos/Jalousien (optional) (Standard: nicht gesetzt)","Blinds/covers (optional)"],["Nur nötig, wenn kein direktes Volumen angegeben wird.","Only required when no direct room volume is entered."],["Lokale Wetter-Entität (Standard: weather.* verwenden)","Local weather entity"],["Lerndaten oder Einstellungswerte gezielt zurücksetzen","Reset learning data or defaults"],["Raumname, Bereich, Sensoren, Größe und Feuchtequellen","Room name, area, sensors, size and moisture sources"],["Mindestabstand gleicher Meldungen (Standard: 90 min)","Cooldown minutes (Default: 90)"],["Anzahl, Namen und zugehörige Person-/Geräte-Tracker.","Counts, names and associated person/device trackers."],["Luftbefeuchter (optional) (Standard: nicht gesetzt)","Humidifier (optional)"],["Individuelle Lüftungsgrenze (Standard: Automatisch)","Individual ventilation threshold"],["Vorhandene Konfiguration importieren (Standard: an)","Import existing configuration into FreshAirIQ"],["Bei Überschreitung Lüften verhindern (Standard: an)","Block normal ventilation above limit (Default: on)"],["Außenluft mindestens so viel kühler (Standard: 2,0)","Outdoor air at least this much cooler (Default: 2.0)"],["Maximale Raumfeuchte für Kühlmodus (Standard: 70,0)","Maximum indoor RH for cooling (Default: 70.0)"],["Standard-Temperaturempfinden (Standard: ausgewogen)","Default thermal preference (Default: balanced)"],["FreshAirIQ konnte die Lerndaten nicht zurücksetzen.","FreshAirIQ could not reset the learning data."],["Außentemperatur (optional – später konfigurierbar)","Outdoor temperature sensor (optional)"],["Stockwerk/Bereich für Gruppierung und Querlüftung.","Floor/area used for grouping and cross ventilation. Example: “Ground floor”. Default: not assigned."],["Außenluft, Gebäude, Bewohner, Stockwerke und Räume","Outdoor air, building, occupants, levels and rooms"],["Zu bearbeitender Raum (Standard: keine Vorauswahl)","Room to edit"],["Stabilisierungszeit nach Lüftung (Standard: 4 min)","Stabilization time after ventilation (Default: 4 min)"],["Maximale Dauer einer Lernprobe (Standard: 120 min)","Maximum learning sample duration (Default: 120.0)"],["Aktiviert Nachtprognose und adaptives Nachtmodell.","Enables the overnight forecast and adaptive night model."],["Meldet günstige Fenster für passive Sommerkühlung.","Reports favourable windows for passive summer cooling. Default: on."],["Wetter-Entität (optional – später konfigurierbar)","Local weather entity (recommended)"],["Kontaktlogik (Standard: „Mindestens einer offen“)","Contact logic"],["PM2.5-Sensor (optional) (Standard: nicht gesetzt)","PM2.5 sensor (optional)"],["Luftreiniger (optional) (Standard: nicht gesetzt)","Air purifier (optional)"],["Schimmel kritisch Oberflächen-RH (Standard: 90 %)","Critical mould surface RH (%) (Default: 90.0)"],["Abluftgerät (optional) (Standard: nicht gesetzt)","Exhaust device (optional)"],["Zuluftgerät (optional) (Standard: nicht gesetzt)","Supply-air device (optional)"],["Entfeuchter (optional) (Standard: nicht gesetzt)","Dehumidifier (optional)"],["Optional für zusätzliche Luftqualitätsbewertung.","Optional for additional air-quality assessment."],["Außenluftfeuchtesensor (Standard: nicht gesetzt)","Outdoor humidity sensor (optional)"],["Pause bis erneute Empfehlung (Standard: 120 min)","Delay before a repeated recommendation (Default: 20 min)"],["Haustiersichere Präsenzsensoren (Standard: leer)","Pet-safe presence sensors (Default: empty)"],["Hauptschalter für alle FreshAirIQ-Pushmeldungen.","Master switch for all FreshAirIQ push notifications."],["Verschattung ab Raumtemperatur (Standard: 24 °C)","Consider shading above room temperature (Default: 24 °C)"],["Sommerkühlung ab Raumtemperatur (Standard: 24,0)","Summer cooling from room temperature (Default: 24.0)"],["Heizsystem und Kostenparameter für Wärmeverluste","Heating system and cost parameters for heat losses"],["Außentemperatursensor (Standard: nicht gesetzt)","Outdoor temperature sensor (optional)"],["Lüftungsstart relative Feuchte (Standard: 62 %)","Ventilation start RH (%) (Default: 62.0)"],["Schimmelwarnung Oberflächen-RH (Standard: 80 %)","Mould warning surface RH (%) (Default: 80.0)"],["Lerndaten wirklich zurücksetzen (Standard: aus)","Really reset learning data"],["Der FreshAirIQ-Raum {room_key} existiert nicht.","The FreshAirIQ room {room_key} does not exist."],["Pollenindex (optional – später konfigurierbar)","Pollen index sensor (optional)"],["Stockwerk/Bereich (Standard: nicht zugeordnet)","Floor"],["FreshAirIQ – vorhandene Konfiguration gefunden","FreshAirIQ – existing configuration found"],["Das Raumvolumen muss mindestens 2 m³ betragen.","Room volume must be at least 2 m³."],["FreshAirIQ wurde erfolgreich neu konfiguriert.","FreshAirIQ was reconfigured successfully."],["Komfortable Uhrzeitauswahl statt Stunden-Zahl.","Convenient time selection instead of a numeric hour."],["Anlagenwirkungsgrad Fernwärme (Standard: 0,98)","System efficiency (Default: 0.98)"],["Zeitfenster und Aktivierung der Nachtprognose.","Time window and activation of the overnight forecast."],["Geschätzte Lüftungskosten im Statistikzeitraum","Estimated ventilation cost in statistics period"],["Temperatursensor (Standard: keine Vorauswahl)","Temperature sensor"],["Statistikzeitraum und gespeicherte Auswertung","Statistics period and stored analysis"],["„Lüftung abgeschlossen“ senden (Standard: an)","Completed sessions (Default: on)"],["Name des Stockwerks/Bereichs (Standard: leer)","Floor/zone name"],["Persönliche Präferenz für die Nachtstrategie.","Personal preference for overnight strategy."],["Persönliche Profil-Zuordnungen (Standard: {})","Personal profile assignments (Default: {})"],["Pollenindex-Sensor (Standard: nicht gesetzt)","Pollen index sensor (optional)"],["Mindestertrag nächste 5 Min (Standard: 25,0)","Minimum yield next 5 min (Default: 25.0)"],["Empfänger, Meldungstypen und Mindestabstände","Recipients, notification types and minimum intervals"],["Persönliche Priorität (Standard: ausgewogen)","Personal priority (Default: balanced)"],["Fenster in der Nacht (Standard: automatisch)","Windows at night (Default: automatic)"],["Referenzluft & Rollo/Jalousie je Fenster/Tür","Reference air per window/door"],["Präsenz-/Bewegungssensoren (Standard: leer)","Presence/motion sensors (Default: empty)"],["Informiert über relevante Lernfortschritte.","Reports relevant learning progress. Default: off."],["Energieinhalt Heizöl (Standard: 10,0 kWh/l)","Heating oil energy content (Default: 10.0)"],["Entfernte Feuchtigkeit im Statistikzeitraum","Removed moisture in statistics period"],["Feuchtesensor (Standard: keine Vorauswahl)","Humidity sensor"],["In Berechnungen einbeziehen (Standard: an)","Include in FreshAirIQ calculations"],["Meldungen und Kostenmodell des Heizsystems","Notifications and heating-system cost model"],["Nutzbarer Anteil der gekauften Gasenergie.","Usable share of the purchased gas energy."],["Temperaturempfinden (Standard: ausgewogen)","Thermal preference (Default: balanced)"],["Regelmäßig im Haushalt lebende Erwachsene.","Adults who regularly live in the household."],["Himmelsrichtung jedes Fenster-/Türkontakts","Compass direction of each window/door contact"],["Fenster-Himmelsrichtungen für {room_name}","Window orientations for {room_name}"],["Maximale Lüftungsdauer (Standard: 20 min)","Maximum ventilation duration (min) (Default: 20.0)"],["„Fenster schließen“ senden (Standard: an)","Close recommendations (Default: on)"],["Feuchtequellen im Raum (Standard: keine)","Moisture sources in the room (Default: none)"],["Minimale Lüftungsdauer (Standard: 3 min)","Minimum ventilation duration (min) (Default: 3.0)"],["Benachrichtigungen aktiv (Standard: aus)","Enable notifications (Default: off)"],["„Lüften empfohlen“ senden (Standard: an)","Ventilate recommendations (Default: on)"],["Angezeigter Zeitraum (Standard: 14 Tage)","Days (Default: 14)"],["Wirkungsgrad Gasheizung (Standard: 0,92)","Gas boiler efficiency (Default: 0.92)"],["Arbeitspreis deines Gastarifs. Beispiel/","Your gas energy price. Example/default: €0.11/kWh."],["Arbeitspreis deiner Fernwärme. Beispiel/","Your district-heating energy price. Example/default: €0.15/kWh."],["Eigene Stockwerke und Bereiche verwalten","Manage custom floors and areas"],["Gebäudetyp ohne doppelte Bewohnerangaben","Building type without duplicate resident settings"],["Pollen-Veto und Wind-/Fensterausrichtung","Pollen veto and wind/window orientation"],["Optional für Kinder mit eigenem Tracker.","Optional for children with their own tracker."],["Das berechnete Raumvolumen ist zu klein.","The calculated room volume is too small."],["Weiteren Raum hinzufügen (Standard: an)","Add another room (default: on)"],["Statistik und technische Feinabstimmung","Statistics and technical fine-tuning"],["Raum dauerhaft aus FreshAirIQ entfernen","Permanently remove a room from FreshAirIQ"],["Anteil der Wassermenge (Standard: 10 %)","Share of total water (Default: 10.0)"],["Tracker für Erwachsene (Standard: leer)","Adult phone/person entities (optional)"],["Nur diese Räume (Standard: leer = alle)","Only these rooms"],["PM2.5-Warnschwelle (Standard: 15 µg/m³)","PM2.5 warning threshold (Default: 15 µg/m³)"],["Wirkungsgrad Ölheizung (Standard: 0,88)","Oil boiler efficiency (Default: 0.88)"],["Zurücksetzen bestätigen (Standard: aus)","Reset all settings to defaults"],["Vergib je Bereich eine Positionsnummer.","Assign each area a position number. Example: Ground floor = 1, Upper floor = 2. Lower numbers appear first."],["Räume anlegen, sortieren oder entfernen","Create, sort or remove rooms"],["Persönliche Empfehlungen (Standard: an)","Personal recommendations (Default: on)"],["Wähle mindestens einen Lüftungskontakt.","Select at least one ventilation contact."],["Hohe relative Feuchte (Standard: 68 %)","High RH (%) (Default: 68.0)"],["Ziel relative Feuchte (Standard: 58 %)","Target RH (%) (Default: 58.0)"],["Schließ-Differenz (Standard: 0,4 g/m³)","Close difference (g/m³) (Default: 0.4)"],["Pollen berücksichtigen (Standard: aus)","Consider pollen (Default: off)"],["COP/JAZ der Wärmepumpe (Standard: 3,5)","COP / seasonal performance (Default: 3.5)"],["Regelmäßig im Haushalt lebende Kinder.","Children who regularly live in the household."],["Temperaturänderung seit Lüftungsbeginn","Temperature change since ventilation start"],["Raumname (Standard: keine Vorauswahl)","Room name"],["Fenster-/Türkontakte (Standard: leer)","Ventilation contacts"],["Raumgrenze in Prozent (Standard: 5 %)","Room threshold percentage (Default: 5%)"],["{room_count} Raum/Räume konfiguriert.","{room_count} room(s) configured."],["Optionale Zusatzsensoren & Referenzen","Optional additional sensors & references"],["CO₂-Warnschwelle (Standard: 1000 ppm)","CO₂ warning threshold (ppm) (Default: 1000.0)"],["Haustiere im Haushalt (Standard: aus)","Pets in household (Default: off)"],["Maximaler Pollenindex (Standard: 4,0)","Maximum pollen index (Default: 4.0)"],["Fernwärmepreis (Standard: 0,15 €/kWh)","District heat price (Default: 0.15)"],["Aktion (Standard: Bereich hinzufügen)","Action"],["Weiche Zusatzsignale für Anwesenheit.","Soft supporting signals for presence."],["Höchste geschätzte Oberflächenfeuchte","Highest estimated surface humidity"],["CO₂-Sensor (Standard: nicht gesetzt)","CO₂ sensor (optional)"],["Außenluft-Referenz neu konfigurieren","Reconfigure outdoor-air reference"],["Automatisch nach Hausgröße & Nutzung","Automatic by dwelling size & usage"],["Entfernen bestätigen (Standard: aus)","Confirm removal"],["Schimmelrisiko melden (Standard: an)","Mould risk (Default: on)"],["Nachtprognose senden (Standard: aus)","Night forecast (Default: off)"],["Lernmeldungen senden (Standard: aus)","Learning messages (Default: off)"],["Vergib je Raum eine Positionsnummer.","Assign each room a position number. Example: Living room = 1, Kitchen = 2. Lower numbers appear first."],["Befeuchten unter (Standard: 35 % rF)","Recommend humidification below (Default: 35% RH)"],["Bereich (Standard: keine Vorauswahl)","Zone"],["Zur Hauptübersicht der Einstellungen","Back to the main settings overview"],["Temperaturänderung seit Sessionstart","Temperature change since session start"],["Geschätzte Feuchteproduktion pro Tag","Estimated daily moisture generation"],["Raumvolumen direkt (Standard: leer)","Room volume"],["Feste Raumgrenze (Standard: 100 ml)","Fixed room threshold (Default: 100 mL)"],["Aus Länge × Breite × Höhe berechnen","Calculate from length × width × height"],["Tracker für Kinder (Standard: leer)","Child phone/person entities (optional)"],["Sommerkühlung melden (Standard: an)","Summer cooling (Default: on)"],["Sendet Hinweise zur Nachtstrategie.","Sends night-strategy hints. Default: off, so FreshAirIQ does not notify unexpectedly at night."],["Öffnungsverzögerungen · {room_name}","Opening delays · {room_name}"],["PM2.5 kritisch (Standard: 35 µg/m³)","Critical PM2.5 threshold (Default: 35 µg/m³)"],["VOC / TVOC verwenden (Standard: an)","Use VOC / TVOC (Default: on)"],["Helligkeit verwenden (Standard: an)","Use illuminance (Default: on)"],["Tracker Erwachsene (Standard: leer)","Adult trackers (Default: empty)"],["Geschätzte Kosten nächste 5 Minuten","Estimated cost next 5 minutes"],["Prognostizierte Wiederaufheizkosten","Forecast reheating cost"],["Auswertung & Experteneinstellungen","Insights & expert settings"],["Oberflächenfaktor (Standard: 0,25)","Estimated surface factor (Default: 0.25)"],["Betriebsprofil (Standard: Komfort)","Operating profile (Default: comfort)"],["Nachtprognose aktiv (Standard: an)","Overnight forecast enabled (Default: on)"],["Sensorfehler melden (Standard: an)","Sensor faults (Default: on)"],["Raum für Kontaktverzögerung wählen","Choose room"],["Prognosezeitraum (Standard: 5 min)","Forecast horizon"],["Querlüftungspaare (Standard: leer)","Cross-ventilation pairs (Default: empty)"],["Komfort & persönliche Empfehlungen","Comfort & personal recommendations"],["Persönliche IQ-Profile & Endgeräte","Personal IQ profiles & devices"],["Prognostizierte Temperaturänderung","Forecast temperature change"],["{room_name} · Kontaktverzögerungen","{room_name} · Contact delays"],["FreshAirIQ benötigt Aufmerksamkeit","FreshAirIQ needs attention"],["Benachrichtigungen und Heizkosten","Notifications and heating costs"],["Zur vorherigen Einstellungsgruppe","Back to the previous settings group"],["Raum (Standard: keine Vorauswahl)","Room"],["CO₂ kritisch (Standard: 1400 ppm)","Critical CO₂ threshold (ppm) (Default: 1400.0)"],["Namen Erwachsene (Standard: leer)","Adult names (Default: empty)"],["Heizsystem (Standard: Wärmepumpe)","Heating system (Default: heat_pump)"],["Strompreis (Standard: 0,30 €/kWh)","Electricity price (Default: 0.3)"],["Einstellungen auf Standard setzen","Restore default settings"],["Lüftungsschwelle · Fester ml-Wert","Ventilation threshold · Fixed mL"],["Wasserdampf in überwachten Räumen","Water vapor in monitored rooms"],["Prozent der gesamten Wassermenge","Percent of total water"],["Optionale Geräte – Datensammlung","Optional devices – data collection"],["VOC-Warnschwelle (Standard: 600)","VOC warning threshold (Default: 600)"],["Heizölpreis (Standard: 1,00 €/l)","Heating oil price (Default: 1.0)"],["Arbeitspreis deines Stromtarifs.","Your electricity energy price. Example: €0.30/kWh. Used for heat pumps and electric heating."],["Preis je Liter Heizöl. Beispiel/","Heating-oil price per litre. Example/default: €1.00/l."],["Feuchtewirkung nächste 5 Minuten","Moisture effect next 5 minutes"],["Betriebsprofil, Pollen und Wind","Operating profile, pollen and wind"],["Lernmodell aktiv (Standard: an)","Learning model enabled (Default: on)"],["Gaspreis (Standard: 0,11 €/kWh)","Gas price (Default: 0.11)"],["Tracker Kinder (Standard: leer)","Child trackers (Default: empty)"],["Nacht beginnt (Standard: 22:00)","Night starts (Default: 22:00)"],["{room_name} · Himmelsrichtungen","{room_name} · Orientations"],["Öffnungsverzögerung je Kontakt","Opening delay per contact"],["Meldungsebene (Standard: Haus)","Scope (Default: house)"],["Optionale Sensoren & Außenluft","Optional sensors & outdoor air"],["PM2.5 verwenden (Standard: an)","Use PM2.5 (Default: on)"],["Himmelsrichtung je Fenster/Tür","Orientation per window/door"],["Standardwerte wiederherstellen","Restore defaults"],["Zeitraum für die Live-Prognose","Time horizon for the live forecast"],["Fester Wert (Standard: 500 ml)","Fixed value (Default: 500 mL)"],["Geschätzte Feuchtebilanz heute","Estimated moisture balance today"],["Prognostizierte Feuchtewirkung","Forecast moisture effect"],["Raum, Sensoren & Eigenschaften","Room, sensors & size"],["Alle gewählten Kontakte offen","All selected contacts open"],["Fensterausrichtung je Kontakt","Window orientation per contact"],["Nachtbeginn (Standard: 22:00)","Night start (Default: 22:00)"],["Namen Kinder (Standard: leer)","Child names (Default: empty)"],["VOC kritisch (Standard: 1200)","Critical VOC threshold (Default: 1200)"],["Heizkosten · {heating_system}","Heating costs · {heating_system}"],["Nacht endet (Standard: 07:00)","Night ends (Default: 07:00)"],["Intelligente Lüftungsschwelle","Intelligent ventilation threshold"],["Modus (Standard: Automatisch)","Mode (Default: Automatic)"],["Geschätzte Oberflächenfeuchte","Estimated surface humidity"],["Übernachtungsgäste Erwachsene","Adult overnight guests"],["Bitte gib einen Raumnamen an.","Please enter a room name."],["FreshAirIQ ist nicht geladen.","FreshAirIQ is not loaded."],["Mindestens ein Kontakt offen","Any selected contact open"],["Prozent der Raum-Wassermenge","Percentage of room water content"],["Benachrichtigungen & Energie","Notifications & energy"],["Lüftungsdauer & Wiederholung","Ventilation duration & repetition"],["Bewohnerprofil & Anwesenheit","Resident profile & presence"],["Aktiviert die Nachtprognose.","Enables the overnight forecast."],["Prozentwert (Standard: 10 %)","Percentage (Default: 10%)"],["Temperatur nächste 5 Minuten","Temperature next 5 minutes"],["Raumbreite (Standard: leer)","Room width"],["← Zurück zu Zuhause & Räume","← Back to home & rooms"],["Gebäudetyp (Standard: Haus)","Building type (Default: house)"],["Nachtende (Standard: 07:00)","Night end (Default: 07:00)"],["Fenster/Türen · {room_name}","Windows/doors · {room_name}"],["Frei wählbarer Anzeigename.","Custom display name. Example: “Ground floor”, “Basement”, “Conservatory” or “Extension”. Default: empty."],["Raumlänge (Standard: leer)","Room length"],["FreshAirIQ – Einstellungen","Settings"],["Optionale Raumklima-Geräte","Optional room-climate devices"],["Erweiterte Modellparameter","Advanced model parameters"],["Nutzen & Temperaturverlust","Benefit & temperature loss"],["Empfänger (Standard: leer)","Recipients"],["Betriebsprofil · {profile}","Operating profile · {profile}"],["Auswertung & Expertenmodus","Insights & expert settings"],["Nur Lerndaten zurücksetzen","Reset learning data only"],["Beginn der Nachtbewertung.","Start of the overnight evaluation period."],["Lüftungsschwelle · Prozent","Ventilation threshold · Percentage"],["Nachtprognose Feuchtigkeit","Overnight moisture forecast"],["Gelernte Nacht-Feuchterate","Learned night moisture rate"],["Erwartete Personen zuhause","Expected people at home"],["Raumhöhe (Standard: leer)","Room height"],["Nachts lieber geschlossen","Prefer closed at night"],["← Zurück zu Einstellungen","← Back to settings"],["Verbleibende Lüftungszeit","Ventilation time remaining"],["Feuchtebilanz der Lüftung","Ventilation moisture balance"],["Übernachtungsgäste Kinder","Child overnight guests"],["Erwachsene (Standard: 2)","Adults (Default: 2)"],["Persönliche Empfehlungen","Personal recommendations"],["Ende der Nachtbewertung.","End of the overnight evaluation period."],["Entfernbare Feuchtigkeit","Removable moisture"],["Empfohlene Lüftungsdauer","Recommended ventilation duration"],["Gib einen Raumnamen an.","Enter a room name."],["Automatisch entscheiden","Automatic"],["Automatisch (empfohlen)","Automatic (recommended)"],["Heizung & Energiekosten","Heating & energy costs"],["Bisherige Lüftungsdauer","Ventilation session elapsed"],["Vertrauen Nachtprognose","Overnight forecast confidence"],["{room_name} · Raumdaten","{room_name} · Room details"],["Raum wurde gespeichert.","Room saved."],["Lüftung & Empfehlungen","Ventilation & recommendations"],["Wartung & Zurücksetzen","Maintenance & reset"],["Komfort & Luftqualität","Comfort & air quality"],["{room_name} bearbeiten","Edit {room_name}"],["Lerndaten zurücksetzen","Reset learning"],["Statistik zurücksetzen","Reset statistics"],["FreshAirIQ hinzufügen","Add FreshAirIQ"],["Nachts offen ist okay","Open at night is okay"],["Stockwerke & Bereiche","Levels & areas"],["Öffnungsverzögerungen","Opening delays"],["Volumen direkt in m³","Enter volume directly in m³"],["Empfehlungsschwellen","Recommendation thresholds"],["Kinder (Standard: 0)","Children (Default: 0)"],["Sicherheitsabfrage.","Safety confirmation. Default: off. Enable only when the selected room really should be removed."],["Statistik & Verlauf","Statistics & history"],["Meldungen & Energie","Notifications & energy"],["Letzte Lerndiagnose","Last learning diagnosis"],["Schließen empfohlen","Close recommended"],["Fenster-Ausrichtung","Window orientation"],["Freistehendes Haus","Detached house"],["Außenluft & Wetter","Outdoor air & weather"],["Sensoren & Fenster","Sensors & windows"],["Gebäude & Bewohner","Property & occupants"],["Benachrichtigungen","Notifications"],["Bereich hinzufügen","Add zone"],["Bereiche sortieren","Sort zones"],["Live-Feuchtebilanz","Live moisture balance"],["Für Kühlung lüften","Ventilate for cooling"],["Prognosesicherheit","Forecast confidence"],["Raum konfigurieren","Configure room"],["Raumeigenschaften","Room properties"],["Bereich entfernen","Remove zone"],["Diagnose-Freigabe","Diagnostics sharing"],["Nächste 5 Minuten","Next 5 minutes"],["Raum gespeichert","Room saved"],["Haus (allgemein)","House (general)"],["Doppelhaushälfte","Semi-detached house"],["Reihenmittelhaus","Mid-terrace house"],["Mehrfamilienhaus","Multi-family building"],["Raum & Zuordnung","Room"],["Feuchteschwellen","Humidity thresholds"],["Prognosezeitraum","Forecast horizon"],["Lüftungsschwelle","Ventilation threshold"],["Absolute Feuchte","Absolute humidity"],["Feuchtedifferenz","Humidity difference"],["Feuchtepotenzial","Moisture potential"],["Raum hinzufügen","Add room"],["Nicht angegeben","Not specified"],["Zuhause & Räume","Home & rooms"],["Räume verwalten","Manage rooms"],["Räume sortieren","Sort rooms"],["Raum bearbeiten","Edit room"],["Raumreihenfolge","Room order"],["Kellergeschoss","Basement"],["Fester mL-Wert","Fixed mL value"],["Energie sparen","Save energy"],["Fester ml-Wert","Fixed mL value"],["Daten & Lernen","Data & learning"],["Raum entfernen","Remove room"],["Raum auswählen","Select room"],["Schimmel & CO₂","Mould & CO₂"],["Betriebsprofil","Operating profile"],["Schimmelrisiko","Mould risk"],["Grundschätzung","Base estimate"],["Reihenendhaus","End-terrace house"],["Sommer kühlen","Summer cooling"],["Waschmaschine","Washing machine"],["Pollen & Wind","Pollen & wind"],["Lernvertrauen","Learning confidence"],["Sensor prüfen","Check sensor"],["Leicht erhöht","Slightly elevated"],["Betriebsmodus","Operating mode"],["Obergeschoss","Upper floor"],["Dachgeschoss","Attic"],["Haus/Wohnung","Whole home"],["Bügelstation","Ironing station"],["Weiterlüften","Continue ventilating"],["Nicht lüften","Do not ventilate"],["Nur anzeigen","Monitor only"],["Lerndiagnose","Learning diagnosis"],["Erdgeschoss","Ground floor"],["Entfeuchten","Dehumidify"],["Raumbezogen","Per room"],["Reihenfolge","Order"],["Querlüftung","Cross ventilation"],["Anwesenheit","Presence"],["Sehr stabil","Very stable"],["Nach unten","Move down"],["Wärmepumpe","Heat pump"],["Ausgewogen","Balanced"],["Lernmodell","Learning model"],["Heizsystem","Heating system"],["Alles okay","Okay"],["Lernstatus","Learning status"],["Lernproben","Learning samples"],["Sonstiges","Other"],["Nach oben","Move up"],["Fernwärme","District heating"],["Badewanne","Bath"],["Eher warm","Warm"],["Eher kühl","Cool"],["Raumklima","Indoor climate"],["Raumgröße","Room size"],["Schließen","Close"],["Unbekannt","Unknown"],["Sehr hoch","Very high"],["Brauchbar","Usable"],["Sonstige","Other"],["Nordwest","North-west"],["Trockner","Dryer"],["Bewohner","Residents"],["Nordost","North-east"],["Südwest","South-west"],["Wohnung","Apartment"],["Komfort","Comfort"],["Elektro","Electric"],["Gebäude","Building"],["Niedrig","Low"],["Südost","South-east"],["Beides","Both"],["Dusche","Shower"],["Kochen","Cooking"],["Fertig","Save changes"],["Zurück","Back"],["Aktion","Action"],["Lüften","Ventilate"],["Warten","Wait"],["Erhöht","Elevated"],["Stabil","Stable"],["Nacht","Night"],["Lernt","Learning"],["Nord","North"],["Haus","House"],["Hoch","High"],["Ost","East"],["Süd","South"],["Öl","Oil"]];
const FAIQ_UI_EN = [
  ["ROLLLÄDEN & JALOUSIEN", "BLINDS & SHUTTERS"],
  ["FreshAirIQ normalisiert die Geräteposition auf einen eindeutigen geschlossenen Anteil. Ist die Beschattung stärker geschlossen als die Lern-Grenze, läuft die Lüftungsbilanz weiter, die Session wird aber nicht zum Lernen verwendet.", "FreshAirIQ normalizes device position to an unambiguous closed percentage. If shading is closed beyond the learning threshold, ventilation balancing continues but the session is excluded from learning."],
  ["Positionslogik", "Position interpretation"],
  ["Wähle, ob 0 % bei deinen Rollläden vollständig geschlossen oder vollständig geöffnet bedeutet.", "Choose whether 0% means your blinds/shutters are fully closed or fully open."],
  ["0 % = vollständig geschlossen / 100 % = vollständig geöffnet", "0% = fully closed / 100% = fully open"],
  ["0 % = vollständig geöffnet / 100 % = vollständig geschlossen", "0% = fully open / 100% = fully closed"],
  ["Lern-Grenze geschlossen", "Closed threshold for learning"],
  ["Nur bis einschließlich dieses geschlossenen Anteils wird eine Lüftung als unverfälschte Lernprobe verwendet. Standard: 20 %. Bei >20 % wird weiter bilanziert, aber nicht gelernt.", "A ventilation session is used as an unbiased learning sample only up to and including this closed percentage. Default: 20%. Above 20%, balancing continues but the session is excluded from learning."],
  ["noch keine Messung", "no measurement yet"], ["Noch keine Messung", "No measurement yet"],
  ["Lüften", "Ventilate"], ["Weiterlüften", "Continue ventilating"], ["Schließen", "Close"],
  ["Nicht lüften", "Do not ventilate"], ["Warten", "Wait"], ["Alles okay", "Everything is okay"],
  ["Sensor prüfen", "Check sensor"], ["Zum Kühlen lüften", "Ventilate for cooling"], ["Nur anzeigen", "Monitor only"],
  ["Sehr hoch", "Very high"], ["Hoch", "High"], ["Erhöht", "Elevated"], ["Leicht erhöht", "Slightly elevated"],
  ["Niedrig", "Low"], ["Unbekannt", "Unknown"], ["Sehr stabil", "Very stable"], ["Stabil", "Stable"],
  ["Brauchbar", "Usable"], ["Lernt", "Learning"], ["Grundschätzung", "Base estimate"],
  ["Entfeuchten", "Dehumidify"], ["Komfort", "Comfort"], ["Sommer kühlen", "Summer cooling"],
  ["Kellergeschoss", "Basement"], ["Erdgeschoss", "Ground floor"], ["Obergeschoss", "Upper floor"], ["Dachgeschoss", "Attic"],
  ["Unzugeordnet", "Unassigned"], ["Freistehendes Haus", "Detached house"], ["Doppelhaushälfte", "Semi-detached house"],
  ["Reihenmittelhaus", "Mid-terrace house"], ["Reihenendhaus", "End-terrace house"], ["Wohnung", "Apartment"], ["Dachgeschosswohnung", "Top-floor apartment"],
  ["Mehrfamilienhaus", "Multi-family house"], ["Sonstiges", "Other"], ["Haus", "House"],
  ["Wärmepumpe", "Heat pump"], ["Fernwärme", "District heating"], ["Elektro", "Electric"], ["Öl", "Oil"],
  ["Nordost", "Northeast"], ["Nordwest", "Northwest"], ["Südost", "Southeast"], ["Südwest", "Southwest"],
  ["Nord", "North"], ["Süd", "South"], ["Ost", "East"], ["West", "West"],
  ["Pollenbelastung liegt über dem eingestellten Grenzwert", "Pollen load is above the configured threshold"],
  ["Ziel erreicht oder zusätzlicher Lüftungsnutzen zu gering", "Target reached or additional ventilation benefit is too low"],
  ["Referenzluft würde zusätzliche Feuchtigkeit eintragen", "Reference air would add moisture"],
  ["Potenzial vorhanden, Lüftungsschwelle noch nicht erreicht", "Potential exists, but the ventilation threshold has not been reached"],
  ["Kein sinnvoller Lüftungsbedarf", "No meaningful ventilation demand"], ["Messwerte fehlen oder sind unplausibel", "Measurements are missing or implausible"],
  ["Raum wird angezeigt, beeinflusst die Berechnungen aber nicht", "Room is displayed but excluded from FreshAirIQ calculations"],
  ["Fenster geschlossen lassen", "Keep windows closed"], ["Fenster jetzt schließen", "Close windows now"], ["Raumsensoren prüfen", "Check room sensors"],
  ["Pollenbelastung zu hoch · Lüften verschoben", "Pollen load too high · ventilation postponed"], ["Sommerkühlung sinnvoll", "Summer cooling is beneficial"],
  ["Noch keine Lernmessung", "No learning measurement yet"], ["Noch keine Lernsession ausgewertet", "No learning session evaluated yet"],
  ["Außenluft, Gebäude, Betriebsprofil und Prognose", "Outdoor air, building, operating profile and forecast"],
  ["Bewohner", "Residents"], ["Anwesenheit, Namen, Räume, Komfort und persönliche Endgeräte", "Presence, names, rooms, comfort and personal devices"],
  ["Räume & Stockwerke", "Rooms & floors"], ["Hausstruktur, Raumgrößen, Sensoren, Kontakte und Luftwege", "Building structure, room sizes, sensors, contacts and airflow paths"],
  ["Lüftungslogik", "Ventilation logic"], ["Feuchte, Schimmel, Wind, Querlüftung und Lernmodell", "Humidity, mould, wind, cross-ventilation and learning model"],
  ["Allgemeine Ziele, Ereignisse und Cooldown", "General targets, events and cooldown"], ["Energie & Daten", "Energy & data"],
  ["Heizkosten, Statistik und Auswertung", "Heating costs, statistics and analysis"],
  ["Bug beschreiben oder Verbesserungsvorschlag direkt an den Diagnose-Hub senden", "Describe a bug or send an improvement suggestion directly to the diagnostics hub"],
  ["Lerndaten oder Einstellungen zurücksetzen", "Reset learning data or settings"], ["Außenluft & Wetter", "Outdoor air & weather"],
  ["Gebäude", "Building"], ["Prognose", "Forecast"], ["Räume & Sensoren", "Rooms & sensors"], ["Luftwege & Querlüftung", "Airflow paths & cross-ventilation"],
  ["Optionale Sensoren & Außenluft", "Optional sensors & outdoor air"], ["Lüftungsmodell", "Ventilation model"], ["Daten & Statistik", "Data & statistics"],
  ["Personen, Anwesenheit, Räume, Komfort und Endgeräte an einer Stelle", "People, presence, rooms, comfort and devices in one place"],
  ["Öffnen und direkt bearbeiten", "Open and edit directly"], ["Kühlung ab Innentemperatur", "Cooling from indoor temperature"],
  ["Sommerkühlung wird erst oberhalb dieses Werts erwogen.", "Summer cooling is considered only above this value."],
  ["Mindest-Temperaturvorteil außen", "Minimum outdoor temperature advantage"], ["Außenluft muss mindestens so viel kühler sein.", "Outdoor air must be at least this much cooler."],
  ["Maximale Innenfeuchte für Kühlung", "Maximum indoor humidity for cooling"], ["Verhindert Kühlung durch zu feuchte Luft.", "Prevents cooling with air that is too humid."],
  ["Zulässiger Feuchteeintrag im Prognosefenster.", "Allowed moisture gain during the forecast window."], ["Preis für die Wiederaufheizenergie.", "Price of reheating energy."],
  ["Wärmepumpen-COP", "Heat-pump COP"], ["Verhältnis von Wärmeleistung zu Stromaufnahme.", "Ratio of heat output to electrical input."],
  ["Ölpreis", "Oil price"], ["Preis je Liter Heizöl.", "Price per litre of heating oil."], ["Energiegehalt Heizöl", "Heating-oil energy content"],
  ["Wirkungsgrad Ölheizung", "Oil-heating efficiency"], ["Fernwärmepreis", "District-heating price"], ["Arbeitspreis der gelieferten Wärme.", "Energy price of delivered heat."],
  ["Berücksichtigt Verteilverluste im Haus.", "Accounts for distribution losses in the building."],
  ["Sensorwerte verfügbar", "Sensor values available"], ["Sensoren aktuell nicht verfügbar", "Sensors currently unavailable"], ["Keine Klimasensoren konfiguriert", "No climate sensors configured"],
  ["FreshAirIQ zeigt die echten Sensorwerte dieses Raums an. Der Raum ist bewusst von Empfehlungen, Prognosen, Hausbilanz und Lernen ausgeschlossen.", "FreshAirIQ shows the real sensor values for this room. The room is intentionally excluded from recommendations, forecasts, whole-home balance and learning."],
  ["Der Raum ist auf „Nur anzeigen“ gestellt, aber mindestens ein zugeordneter Klimasensor liefert aktuell keinen gültigen Wert.", "The room is set to ‘Monitor only’, but at least one assigned climate sensor currently has no valid value."],
  ["Dieser Strukturraum bleibt im Gebäudemodell erhalten. Es werden keine Klimawerte geschätzt oder erfunden.", "This structural room remains in the building model. No climate values are estimated or invented."],
  ["keine Richtung hinterlegt", "no direction configured"], ["Daueröffnung überwachen", "Monitor long-term opening"],
  ["MECHANISCHE LÜFTUNG AKTIV", "MECHANICAL VENTILATION ACTIVE"], ["LÜFTUNG AKTIV", "VENTILATION ACTIVE"], ["PASSIV MITGELÜFTET", "PASSIVELY VENTILATED"], ["GESCHLOSSEN", "CLOSED"],
  ["würde Feuchtigkeit eintragen", "would add moisture"], ["Automatisch nach Hausgröße & Nutzung", "Automatic based on home size & usage"],
  ["Intelligente Lüftungsschwelle", "Smart ventilation threshold"], ["Temperaturänderung", "Temperature change"], ["Lüftungszeit", "Ventilation time"],
  ["Keine weiteren Details verfügbar.", "No further details available."], ["Feuchteabbau hat Vorrang; FreshAirIQ toleriert dafür etwas mehr Wärmeverlust.", "Moisture reduction has priority; FreshAirIQ accepts slightly more heat loss for it."],
  ["Ausgewogene Entscheidung aus Feuchte, Temperatur, Luftqualität und Energie.", "Balanced decision based on humidity, temperature, air quality and energy."],
  ["Kühle Außenluft wird gezielt zum Absenken der Raumtemperatur genutzt, solange der Feuchteeintrag vertretbar bleibt.", "Cool outdoor air is used specifically to lower room temperature as long as moisture gain remains acceptable."],
  ["Prognosen & Lernen", "Forecasts & learning"], ["Prognosemodell, Feedback, Shadow-Lernen & Validierung", "Forecast model, feedback, shadow learning & validation"],
  ["Tagesroutinen, Nutzerstrategie & persönlicher Kontext", "Daily routines, user strategy & personal context"], ["Lernt noch", "Still learning"],
  ["Wird sicher an den Diagnose-Hub übertragen …", "Being securely transmitted to the diagnostics hub …"],
  ["Diesen Raum wirklich aus FreshAirIQ entfernen?", "Really remove this room from FreshAirIQ?"], ["Alle gelernten FreshAirIQ-Daten wirklich löschen?", "Really delete all learned FreshAirIQ data?"],
  ["Alle FreshAirIQ-Optionen wirklich auf Standardwerte zurücksetzen? Räume und Sensoren bleiben erhalten.", "Really reset all FreshAirIQ options to defaults? Rooms and sensors will be kept."],
  ["Feuchte & Wasserbilanz", "Humidity & water balance"], ["Aktuelle Feuchte, entfernbares Potenzial und Live-Bilanz.", "Current humidity, removable potential and live balance."],
  ["Temperaturänderungen", "Temperature changes"], ["Temperaturverlust oder -gewinn während und nach dem Lüften.", "Temperature loss or gain during and after ventilation."],
  ["Empfohlene Dauer und verbleibende IQ-Zeit.", "Recommended duration and remaining IQ time."], ["Vorhersage für den gewählten Prognosezeitraum.", "Forecast for the selected forecast period."],
  ["Nächtliche Entwicklung und empfohlene Fensterstrategie.", "Overnight development and recommended window strategy."], ["Oberflächen-RH und auffällige Räume.", "Surface RH and notable rooms."],
  ["Wiederaufheizenergie und geschätzte Heizkosten.", "Reheating energy and estimated heating costs."], ["Pollen & Außenluft-Veto", "Pollen & outdoor-air veto"],
  ["Querlüftung", "Cross-ventilation"], ["IQ-Aktiv / Analyseleiste", "IQ active / analysis bar"], ["Details-Schaltfläche", "Details button"],
  ["Gäste-Schaltfläche", "Guests button"], ["Räume-Schaltfläche", "Rooms button"], ["VOC / TVOC berücksichtigen", "Consider VOC / TVOC"],
  ["PM2.5 berücksichtigen", "Consider PM2.5"], ["Helligkeit berücksichtigen", "Consider illuminance"],
  ["Intelligente Lüftungs-, Feuchte-, Energie- und Lernübersicht.", "Smart ventilation, humidity, energy and learning overview."],
  ["Automatisch erzeugtes Live-Dashboard mit Detail-Popup, Räumen, Nachtprognose, Lernen und Energie.", "Automatically generated live dashboard with detail popup, rooms, night forecast, learning and energy."],
  ["Details", "Details"], ["Gäste", "Guests"], ["Räume", "Rooms"], ["Raum", "Room"], ["Zurück", "Back"], ["Speichern", "Save"], ["Abbrechen", "Cancel"],
  ["Einstellungen", "Settings"], ["Empfehlung", "Recommendation"], ["Empfehlungen", "Recommendations"], ["Warum diese Entscheidung?", "Why this decision?"],
  ["WARUM DIESE ENTSCHEIDUNG?", "WHY THIS DECISION?"], ["HAUSLÜFTUNG", "WHOLE-HOME VENTILATION"], ["Hauslüftung", "Whole-home ventilation"],
  ["FEUCHTE", "HUMIDITY"], ["TEMPERATUR", "TEMPERATURE"], ["SCHIMMEL", "MOULD"], ["NACHT", "NIGHT"], ["LERNEN", "LEARNING"],
  ["Aktuell lernt FreshAirIQ", "FreshAirIQ is currently learning"], ["Lernfortschritt nach Bereichen", "Learning progress by area"],
  ["Tippe auf einen Bereich, um Details zu sehen.", "Tap an area to see details."], ["Erfahrungsreife", "Experience maturity"], ["Prognosequalität", "Forecast quality"],
  ["FreshAirIQ übernimmt", "FreshAirIQ is handling it"], ["Aktuell ist kein Eingreifen nötig.", "No action is currently needed."],
  ["Fenster ist gekippt; vollständig öffnen erhöht den Luftwechsel für die aktuelle Empfehlung", "Window is tilted; opening it fully increases airflow for the current recommendation"],
  ["Drei-Zustands-Sensor meldet Kipplüftung; FreshAirIQ empfiehlt für den aktuellen Bedarf vollständiges Öffnen", "Three-state sensor reports a tilted window; FreshAirIQ recommends opening it fully for the current ventilation demand"],
  ["Drei-Zustands-Sensor meldet Kipplüftung; die gewählte Lüftungsart wird mit dem separaten Kippmodell bewertet", "Three-state sensor reports tilted ventilation; the selected ventilation mode is evaluated with the separate tilt model"],
  ["Drei-Zustands-Sensor meldet Kipplüftung; der reduzierte Luftwechsel wird separat gelernt", "Three-state sensor reports a tilted window; the reduced airflow is learned separately"],
  ["Vollständig öffnen", "Open fully"],
  ["Nacht", "Night"], ["Hinweis", "Notice"], ["im Blick", "monitored"], ["Pollen", "Pollen"], ["beachten", "watch"], ["okay", "okay"], ["Lernen", "Learning"], ["aktiv", "active"],
  ["Alles gut", "All good"], ["Raum/Räume werden automatisch verfolgt.", "room(s) are being tracked automatically."],
  ["weitere Räume ohne akuten Handlungsbedarf", "more rooms without urgent action needed"], ["Räume ohne akuten Handlungsbedarf", "rooms without urgent action needed"],
];
FAIQ_NATIVE_EN.push(
  ["RÄUME & SENSOREN", "ROOMS & SENSORS"],
  ["Räume direkt im Dashboard verwalten", "Manage rooms directly in the dashboard"],
  ["Noch keine Räume eingerichtet.", "No rooms configured yet."],
  ["Raum hinzufügen", "Add room"],
  ["Schlüssel", "Key"],
  ["Kontakt(e)", "contact(s)"],
  ["Noch kein Fenster-/Türkontakt ausgewählt.", "No window/door contact selected yet."],
  ["Ausrichtung", "Orientation"],
  ["Unbekannt", "Unknown"],
  ["Öffnungsverzögerung", "Opening delay"],
  ["Referenztemperatur dieser Öffnung", "Reference temperature for this opening"],
  ["Referenzfeuchte dieser Öffnung", "Reference humidity for this opening"],
  ["Rollo / Jalousie dieser Öffnung", "Blind / shutter for this opening"],
  ["Tür wird als Durchgang genutzt und von außen zugezogen", "Door is used as a passage and pulled shut from outside"],
  ["Kontakte im Detail", "Opening details"],
  ["Abweichende Referenz nur paarweise (Temperatur + Feuchte) setzen.", "Set an alternative reference only as a pair (temperature + humidity)."],
  ["Lüftungsziele priorisieren", "Prioritize ventilation goals"],
  ["Entfeuchtung", "Dehumidification"],
  ["CO₂ / Luftqualität", "CO₂ / air quality"],
  ["Temperaturkomfort", "Temperature comfort"],
  ["Für diesen Raum ist aktuell kein priorisierbares Lüftungsziel konfiguriert. Optionale Ziele erscheinen automatisch, sobald die benötigten Sensoren bzw. ein Komfortziel hinterlegt sind.", "No prioritizable ventilation goal is currently configured for this room. Optional goals appear automatically once the required sensors or a comfort target are configured."],
  ["Es werden nur Ziele angezeigt, für die dieser Raum die nötigen Daten besitzt. CO₂ erscheint nur mit CO₂-Sensor; Temperaturkomfort nur mit Thermostat oder manuellem/Fallback-Ziel.", "Only goals for which this room has the required data are shown. CO₂ appears only with a CO₂ sensor; temperature comfort only with a thermostat or manual/fallback target."],
  ["Priorität", "Priority"],
  ["CO₂-Sensor", "CO₂ sensor"],
  ["Ablüfter / mechanische Lüftung", "Exhaust fan / mechanical ventilation"],
  ["Komfort-Zieltemperatur", "Comfort target temperature"],
  ["Manuelle Zieltemperatur", "Manual target temperature"],
  ["Fallback-Zieltemperatur", "Fallback target temperature"],
  ["VOC-/TVOC-Sensor", "VOC/TVOC sensor"],
  ["PM2.5-Sensor", "PM2.5 sensor"],
  ["Helligkeitssensor", "Illuminance sensor"],
  ["Thermostat / Klimagerät", "Thermostat / climate device"],
  ["Zuluftgerät", "Supply-air device"],
  ["Lüftungs-/WRG-Gerät", "Ventilation/HRV device"],
  ["Entfeuchter", "Dehumidifier"],
  ["Luftbefeuchter", "Humidifier"],
  ["Luftreiniger", "Air purifier"],
  ["Feuchtequellen", "Moisture sources"],
  ["Dusche", "Shower"],
  ["Badewanne", "Bathtub"],
  ["Kochen", "Cooking"],
  ["Wäsche trocknen", "Drying laundry"],
  ["Raum speichern", "Save room"],
  ["Raum löschen", "Delete room"],
  ["Optional. Mit einem CO₂-Sensor wird Luftqualität zu einem regulären Lüftungsziel. Ohne Sensor entstehen weder CO₂-Priorität noch CO₂-Empfehlung, ETA oder Zielanzeige.", "Optional. With a CO₂ sensor, air quality becomes a regular ventilation goal. Without a sensor there is no CO₂ priority, CO₂ recommendation, ETA or goal display."],
  ["Optional. EIN startet mechanische Lüftung, AUS beendet sie. FreshAirIQ bewertet und lernt diese Lüftungsart getrennt von Fenster-/Kipplüftung; das Gerät wird nicht automatisch geschaltet.", "Optional. ON starts mechanical ventilation and OFF ends it. FreshAirIQ evaluates and learns this ventilation type separately from window/tilt ventilation; the device is not switched automatically."],
  ["Freiwillige Eingabe. Ohne Thermostat/Klimagerät kann der Raum gespeichert und weiter genutzt werden. Ist ein Gerät ausgewählt, verwendet FreshAirIQ im Automatikmodus dessen letzten plausiblen Sollwert als Temperatur-Komfortziel; Frostschutz/Aus nach Lüftungsbeginn ersetzt dieses Ziel nicht.", "Optional. Evaluated as an alternative cooling measure; FreshAirIQ does not invent a target temperature."],
  ["Optional. Kann Frischluftbedarf bei erhöhtem CO₂ unterstützen.", "Optional. Can support fresh-air demand when CO₂ is elevated."],
  ["Optional. Zentrale oder dezentrale mechanische Lüftung.", "Optional. Central or decentralized mechanical ventilation."],
  ["Optional. Alternative bei hoher Feuchte oder ungünstiger Außenluft.", "Optional. Alternative when humidity is high or outdoor air is unsuitable."],
  ["Optional. Wird nur bei deutlich trockener Raumluft empfohlen.", "Optional. Recommended only when room air is clearly too dry."],
  ["Optional. Ergänzung bei Feinstaub, VOC oder Pollen-Veto.", "Optional. Additional measure for particulate matter, VOC or pollen veto."],
  ["Markiere typische Feuchte- und Wärmequellen, die FreshAirIQ bei der Quellenanalyse berücksichtigen darf.", "Mark typical moisture and heat sources that FreshAirIQ may consider in source analysis."],
  ["Außenluft / Raum-Referenz verwenden", "Use outdoor / room reference"],
  ["Entitäten durchsuchen …", "Search entities …"],
  ["Nicht gesetzt", "Not set"]
);
// 0.26.4.5: English for every remaining German UI text found by tools/i18n_audit (card + editor).
FAIQ_NATIVE_EN.push(
  ["WASSER IN DER LUFT", "WATER IN THE AIR"],
  ["NACHTPROGNOSE", "NIGHT FORECAST"],
  ["Nachtprognose", "Night forecast"],
  ["ANWESENHEIT", "PRESENCE"],
  ["Lernt dein Zuhause kennen", "Getting to know your home"],
  ["Raumphysik · Prognosemodell", "Room physics · forecast model"],
  ["Dein Zuhause", "Your home"],
  ["Raum braucht Aufmerksamkeit", "room needs attention"],
  ["Räume brauchen Aufmerksamkeit", "rooms need attention"],
  ["in Ordnung", "fine"],
  ["Nachricht an den Support (optional)", "Message to support (optional)"],
  ["Beschreibung", "Description"],
  ["Meldung senden", "Send report"],
  ["Aktuell: ", "Current: "],
  ["Pollenbewertung", "Pollen assessment"],
  ["Betragsgenauigkeit", "Magnitude accuracy"],
  ["Richtung", "Direction"],
  ["Lernwirkung vs. Grundmodell", "Learning effect vs. basic model"],
  ["Aktuell vs. vorherige Generation", "Current vs. previous generation"],
  ["Welche Räume den Wert verursachen", "Which rooms cause the value"],
  ["RAUM-INTELLIGENZ", "ROOM INTELLIGENCE"],
  ["Daten plausibel", "Data plausible"],
  ["Messwerte plausibel", "Readings plausible"],
  ["Messwerte unplausibel", "Readings implausible"],
  ["LETZTE LERNMESSUNG", "LAST LEARNING MEASUREMENT"],
  ["RAUMLUFTFEUCHTE", "ROOM HUMIDITY"],
  ["FRESHAIRIQ ENTSCHEIDUNG", "FRESHAIRIQ DECISION"],
  ["LIVE-OPTIMIERUNG", "LIVE OPTIMISATION"],
  ["JETZT ENTFERNBAR", "REMOVABLE NOW"],
  ["berechnete Räume", "calculated rooms"],
  ["bis Nachtende", "until end of night"],
  ["Mehr zur Entscheidung", "More about the decision"],
  ["Sicherheit", "confidence"],
  ["Nachtprognose & Nachtstrategie", "Night forecast & night strategy"],
  ["Helligkeit", "Brightness"],
  ["Zeigt den aktuellen Modus als kompakte Kachel oben rechts.", "Shows the current mode as a compact tile at the top right."],
  ["Wasser in der Hausluft", "Water in the indoor air"],
  ["Letzte Messung", "Last measurement"],
  ["Grenze", "Limit"],
  ["Grundmodell", "Basic model"],
  ["Deine Gewohnheiten", "Your habits"],
  ["Langzeitlernen", "Long-term learning"],
  ["Lokaler PDF-Nachweis", "Local PDF record"],
  ["lokal", "local"],
  ["VON", "FROM"],
  ["BIS", "TO"],
  ["PDF erstellen", "Create PDF"],
  ["Aktuelle Raumwerte auf einen Blick", "Current room values at a glance"],
  ["RAUMKLIMA", "INDOOR CLIMATE"],
  ["g/m³ absolut", "g/m³ absolute"],
  ["LERNSTATUS", "LEARNING STATUS"],
  ["Proben", "samples"],
  ["Fensternavigation", "Window navigation"],
  ["Hilfe, Diagnose & Feedback", "Help, diagnostics & feedback"],
  ["DIAGNOSE", "DIAGNOSTICS"],
  ["Diagnosedaten", "Diagnostic data"],
  ["exportieren", "export"],
  ["an Support senden", "send to support"],
  ["Fehler / Bug", "Error / bug"],
  ["Verbesserungsvorschlag", "Suggestion"],
  ["Support per E-Mail", "Support by email"],
  ["Optional: Was ist passiert?", "Optional: What happened?"],
  ["Paarvergleiche", "Pair comparisons"],
  ["Generationenvergleiche", "Generation comparisons"],
  ["Gelerntes Modell MAE", "Learned model MAE"],
  ["Aktuelle Generation MAE", "Current generation MAE"],
  ["Vorherige Generation MAE", "Previous generation MAE"],
  ["95-%-Intervall Lerngewinn", "95 % interval learning gain"],
  ["Sammelt Vergleichsdaten", "Collecting comparison data"],
  ["Wo FreshAirIQ genauer hinschaut", "Where FreshAirIQ takes a closer look"],
  ["FRESHAIRIQ EMPFIEHLT", "FRESHAIRIQ RECOMMENDS"],
  ["Wasserdampf", "water vapour"],
  ["RAUMMODELL", "ROOM MODEL"],
  ["Systemcheck", "System check"],
  ["IQ AKTIV", "IQ ACTIVE"],
  ["BISHER", "SO FAR"],
  ["IQ-ZEIT", "IQ TIME"],
  ["bis Ziel", "to target"],
  ["Ziel erreicht", "Target reached"],
  ["Prognosegenauigkeit", "Forecast accuracy"],
  ["Raumempfehlung(en) befolgt", "room recommendation(s) followed"],
  ["Lernmessung(en) verwertbar", "learning measurement(s) usable"],
  ["Feuchtigkeit erfolgreich reduziert", "Humidity successfully reduced"],
  ["Vergleichsmessung", "Comparison measurement"],
  ["Gesamtergebnis", "Overall result"],
  ["IQ-AUSWERTUNG", "IQ EVALUATION"],
  ["Abweichung", "Deviation"],
  ["ABSCHLUSSMESSUNG", "FINAL MEASUREMENT"],
  ["Abschlussauswertung", "Final evaluation"],
  ["modellierte Wirkung", "modelled effect"],
  ["Wird berechnet …", "Calculating …"],
  ["MIT EMPFEHLUNG", "WITH RECOMMENDATION"],
  ["ENTSCHEIDUNGSWIRKUNG", "DECISION IMPACT"],
  ["NACHTSTRATEGIE", "NIGHT STRATEGY"],
  ["Nachtstrategie", "Night strategy"],
  ["JETZT", "NOW"],
  ["LERNT JETZT: IQ lernt gerade den realen Luftaustausch", "LEARNING NOW: IQ is learning the real air exchange"],
  ["Keine Klimasensoren erforderlich", "No climate sensors required"],
  ["Letzte echte Sensormessung", "Last real sensor reading"],
  ["RAUM-MONITORING", "ROOM MONITORING"],
  ["AKTIVE FEUCHTEQUELLE", "ACTIVE MOISTURE SOURCE"],
  ["SICHERHEIT", "CONFIDENCE"],
  ["LIVE-FEUCHTEBILANZ · GANZES HAUS", "LIVE MOISTURE BALANCE · WHOLE HOUSE"],
  ["IQ-ENTSCHEIDUNG", "IQ DECISION"],
  ["Aktuelle Entscheidung", "Current decision"],
  ["PROGNOSEZEITRAUM", "FORECAST HORIZON"],
  ["Nachtmodell", "Night model"],
  ["adaptiv · Ziel ca. 3–5×/Tag", "adaptive · target approx. 3–5×/day"],
  ["Hauptempfehlung", "Main recommendation"],
  ["Personen", "people"],
  ["Schwelle", "Threshold"],
  ["Kurzfristiger Schließcheck (5 min): voraussichtlich", "Short-term close check (5 min): expected"],
  ["ml Feuchteabbau", "ml moisture reduction"],
  ["ml Feuchtigkeit können entfernt werden", "ml of moisture can be removed"],
  ["Jetzt lüften · etwa", "Ventilate now · about"],
  ["Lüftung läuft ·", "Ventilation running ·"],
  ["Freshy ist zufrieden", "Freshy is happy"],
  ["Freshy möchte, dass du lüftest", "Freshy wants you to air the rooms"],
  ["Freshy lüftet mit", "Freshy is airing with you"],
  ["Freshy schläft", "Freshy is asleep"],
  ["Freshy hält ein Blatt als Schirm", "Freshy holds a leaf as an umbrella"],
  ["Freshy fächelt sich Luft zu", "Freshy fans itself"],
  ["Freshy ist besorgt", "Freshy is worried"],
  ["Einzelergebnis aus älterem Datenformat nicht verfügbar", "Single result not available from the older data format"],
  ["Messwert nicht belastbar", "Reading not reliable"],
  ["LETZTE LÜFTUNG", "LAST VENTILATION"],
  ["Noch keine abgeschlossene Lüftung", "No completed ventilation yet"],
  ["Sobald eine Lüftung abgeschlossen ist, bleibt ihr Ergebnis hier abrufbar.", "Once a ventilation is completed, its result stays available here."],
  ["Feuchte nicht belastbar", "Humidity not reliable"],
  ["· vollständiges Ergebnis öffnen", "· open full result"],
  ["nicht belastbar", "not reliable"],
  ["Für diese Lüftung konnte beim Start keine belastbar auswertbare Prognose eingefroren werden", "No reliable forecast could be frozen at the start of this ventilation"],
  ["% · Startprognose gegen Ergebnis bei gleicher Messdauer", "% · start forecast vs. result over the same measuring time"],
  ["Feuchteergebnis nicht in Lernen oder Feuchtestatistik übernommen · Sensorzeitstempel während der Lüftung nicht vollständig", "Humidity result not used for learning or humidity statistics · sensor timestamps during ventilation incomplete"],
  ["Raum/Räume mit aktiver Feuchtequelle", "room(s) with an active moisture source"],
  ["Raum/Räume mit zeitgleichem Startvergleich", "room(s) with a simultaneous start comparison"],
  ["Raum/Räumen für Genauigkeitswertung verwertbar", "room(s) usable for accuracy scoring"],
  ["Raum/Räume wegen nicht ausreichend synchroner Messdaten ausgeschlossen", "room(s) excluded because readings were not synchronous enough"],
  ["Keine Genauigkeitswertung · Messdaten nicht streng genug synchronisiert", "No accuracy score · readings not synchronised closely enough"],
  ["Raum/Räume für Genauigkeitswertung verwertbar", "room(s) usable for accuracy scoring"],
  ["Ergebnis noch", "Result for"],
  ["Lüftung beendet · Feuchteergebnis nicht belastbar", "Ventilation finished · humidity result not reliable"],
  ["Feuchtigkeit ist angestiegen", "Humidity has increased"],
  ["Lüftung ausgewertet", "Ventilation evaluated"],
  ["nicht als Messwert gespeichert", "not stored as a reading"],
  ["FreshAirIQ wartet bei zeitversetzt meldenden Sensoren auf einen belastbaren Messvergleich. Die Lern-Auswertung kann deshalb verzögert erscheinen. Dieser Vergleich wird wegen nicht ausreichend synchroner Messdaten nicht als Prognosegenauigkeit gewertet.", "FreshAirIQ waits for a reliable comparison when sensors report with a delay, so the learning evaluation may appear later. This comparison is not counted as forecast accuracy because the readings were not synchronous enough."],
  ["Die Genauigkeit wird ausschließlich aus den streng vergleichbaren Raummessungen berechnet. Asynchrone Räume bleiben sichtbar, beeinflussen diese Wertung aber nicht.", "Accuracy is calculated only from strictly comparable room readings. Asynchronous rooms stay visible but do not affect this score."],
  ["Feuchtevergleich nicht belastbar", "Humidity comparison not reliable"],
  ["Vom Öffnen des ersten bis zum Schließen des letzten Lüftungsfensters zusammengefasst.", "Summarised from opening the first to closing the last window."],
  ["LÜFTUNG ABGESCHLOSSEN", "VENTILATION COMPLETED"],
  ["Ergebnis öffnen ›", "Open result ›"],
  ["Vollständige Auswertung", "Full evaluation"],
  ["Daueröffnung wird überwacht", "Long opening is being monitored"],
  ["Fenster kann vorerst offen/gekippt bleiben", "Window can stay open/tilted for now"],
  ["Sensoren prüfen", "Check sensors"],
  ["Raum/Räume mit ungültigen Messwerten", "room(s) with invalid readings"],
  ["Jetzt schließen", "Close now"],
  ["Lüftung läuft", "Ventilation running"],
  ["Kühlere Außenluft kann genutzt werden", "Cooler outdoor air can be used"],
  ["Jetzt lüften", "Ventilate now"],
  ["Hausweit", "Whole home"],
  ["möglich", "possible"],
  ["Raumweise lüften", "Ventilate room by room"],
  ["Feuchteproblem · noch nicht lüften", "Humidity issue · do not ventilate yet"],
  ["Feuchteproblem · abwarten", "Humidity issue · wait"],
  ["Außenluft würde in", "Outdoor air would in"],
  ["FreshAirIQ bewertet fortlaufend Raum-, Außen- und Prognosedaten.", "FreshAirIQ continuously evaluates room, outdoor and forecast data."],
  ["Rückmeldung wird geprüft", "Checking feedback"],
  ["Warte kurz auf die Klimasensoren", "Waiting briefly for the climate sensors"],
  ["Fenster geschlossen ·", "Window closed ·"],
  ["FreshAirIQ hat die Lüftung beendet und fordert jetzt noch einmal die bereits konfigurierten Temperatur- und Feuchtesensoren an. Erst danach wird das Ergebnis angezeigt.", "FreshAirIQ has finished the ventilation and is requesting the configured temperature and humidity sensors once more. The result is shown afterwards."],
  ["frische Abschlusswerte werden eingesammelt", "collecting fresh final readings"],
  ["Kein Stillstand: FreshAirIQ wartet bewusst kurz auf eine aktuelle Sensor-Rückmeldung. Antwortet ein Batteriesensor nicht, endet die Gnadenfrist automatisch und die Messqualität wird aus den tatsächlich während der Lüftung beobachteten Meldungen bewertet.", "Not stuck: FreshAirIQ deliberately waits briefly for a current sensor update. If a battery sensor does not respond, the grace period ends automatically and measurement quality is rated from the updates actually observed during ventilation."],
  ["FreshAirIQ überwacht", "FreshAirIQ is monitoring"],
  ["DAUER-/KIPPLÜFTUNG", "LONG/TILTED VENTILATION"],
  ["Live-Messverlauf berücksichtigt", "live readings considered"],
  ["am Feuchteziel begrenzt", "limited at the humidity target"],
  ["optimal noch ca.", "optimal for about"],
  ["seit Lüftungsbeginn", "since ventilation started"],
  ["FreshAirIQ aktualisiert Feuchte, Temperatur und Kosten für den neuen Zeitraum.", "FreshAirIQ updates humidity, temperature and costs for the new period."],
  ["seit Start", "since start"],
  ["DAUERÖFFNUNG", "LONG OPENING"],
  ["wird überwacht", "is being monitored"],
  ["Temperatur & Feuchte werden laufend geprüft", "temperature & humidity are checked continuously"],
  ["über Ziel", "above target"],
  ["kontrolliert über Nacht lüften", "ventilate in a controlled way overnight"],
  ["vor dem Schlafengehen kurz lüften, dann schließen", "air briefly before bed, then close"],
  ["Mit der Empfehlung erwartet FreshAirIQ morgen rund", "With the recommendation FreshAirIQ expects tomorrow about"],
  ["ml weniger Feuchte.", "ml less moisture."],
  ["Die Empfehlung bringt voraussichtlich nur einen kleinen Vorteil von rund", "The recommendation probably brings only a small benefit of about"],
  ["Für diese Nacht ist kein messbarer Feuchtevorteil durch zusätzliches Lüften zu erwarten.", "No measurable humidity benefit from extra ventilation is expected tonight."],
  ["WAS BRINGT LÜFTEN VOR DEM SCHLAFEN?", "WHAT DOES AIRING BEFORE BED BRING?"],
  ["OHNE ZUSÄTZLICHES LÜFTEN", "WITHOUT EXTRA VENTILATION"],
  ["bis morgen früh", "until tomorrow morning"],
  ["% Oberflächen-RH", "% surface RH"],
  ["auffällig", "elevated"],
  ["unauffällig", "unremarkable"],
  ["geschlossen", "closed"],
  ["teilweise offen", "partly open"],
  ["kurz vorlüften", "air briefly beforehand"],
  ["vorher lüften", "air beforehand"],
  ["g/m³ außen", "g/m³ outdoors"],
  ["Wetter wird bewertet", "weather is being evaluated"],
  ["SPÄTER", "LATER"],
  ["Feuchte & Temperatur", "Humidity & temperature"],
  ["Feuchte", "Humidity"],
  ["DAUER-/KIPPLÜFTUNG WIRD ÜBERWACHT: FreshAirIQ prüft Temperatur, Feuchtebilanz und Außenbedingungen fortlaufend und empfiehlt das Schließen, sobald die Daueröffnung ungünstig wird.", "LONG/TILTED VENTILATION MONITORED: FreshAirIQ continuously checks temperature, moisture balance and outdoor conditions and recommends closing as soon as the long opening becomes unfavourable."],
  ["· Feuchtewirkung · Temperaturreaktion · optimale Schließzeit ·", "· moisture effect · temperature response · optimal closing time ·"],
  ["Raum/Räume warten noch auf passende Sensordaten", "room(s) still waiting for matching sensor data"],
  ["LÜFTUNG WIRD BEOBACHTET: FreshAirIQ sammelt aktuelle Temperatur- und Feuchtemeldungen · für eine Modellanpassung fehlen noch zeitlich passende Sensordaten", "VENTILATION OBSERVED: FreshAirIQ is collecting current temperature and humidity updates · matching sensor data is still missing for a model adjustment"],
  ["Datenquelle(n) prüfen · verbleibende Daten werden weiter bewertet", "data source(s) to check · remaining data is still evaluated"],
  ["FreshAirIQ erwartet mit der empfohlenen Nachtstrategie morgen früh etwa", "With the recommended night strategy FreshAirIQ expects tomorrow morning about"],
  ["ml weniger Feuchte. Wetter, Außenluft und deine gelernten Raumverläufe fließen in diesen Vergleich ein.", "ml less moisture. Weather, outdoor air and your learned room behaviour are part of this comparison."],
  ["FreshAirIQ vergleicht die erwartete Nachtentwicklung mit und ohne Eingriff. Aktuell ergibt sich kein belastbarer zusätzlicher Feuchtegewinn durch eine andere Strategie.", "FreshAirIQ compares the expected night development with and without intervention. Currently no reliable additional humidity gain results from a different strategy."],
  ["Begründung & IQ-Analyse", "Reasoning & IQ analysis"],
  ["Keine raumspezifische Maßnahme nötig", "No room-specific action needed"],
  ["FreshAirIQ überwacht die Räume weiter. Die Hausschwelle entscheidet separat über eine allgemeine Lüftungsempfehlung.", "FreshAirIQ keeps monitoring the rooms. The house threshold separately decides on a general ventilation recommendation."],
  ["wärmer", "warmer"],
  ["kühler", "cooler"],
  ["nahezu unverändert", "almost unchanged"],
  ["Wird für Gebäude, Etage, Volumen und Bewohnerzuordnung geführt – ohne erfundene Klimawerte.", "Kept for building, floor, volume and resident assignment – without invented climate values."],
  ["m³ · Fenster", "m³ · window"],
  ["· nur Struktur", "· structure only"],
  ["FreshAirIQ konnte die Aktion nicht abschließen.", "FreshAirIQ could not complete the action."],
  ["Nur bei erkannten Problemen", "Only when problems are detected"],
  ["Täglich nachts", "Daily at night"],
  ["Wöchentlich", "Weekly"],
  ["Alle Support-Funktionen sind hier zentral gebündelt.", "All support functions in one place."],
  ["Diagnosedaten lokal exportieren oder direkt an den FreshAirIQ-Support senden.", "Export diagnostics locally or send them directly to FreshAirIQ support."],
  ["Die Diagnose wird verschlüsselt über Home Assistant direkt an den FreshAirIQ-Diagnose-Server übertragen – nicht an die hier angezeigte lokale Home-Assistant-Adresse. Zugangsdaten und Tokens werden nicht übertragen.", "Diagnostics are sent encrypted through Home Assistant directly to the FreshAirIQ diagnostics server – not to the local Home Assistant address shown here. Credentials and tokens are not transmitted."],
  ["Fehler und Verbesserungsvorschläge direkt melden.", "Report bugs and suggestions directly."],
  ["Art der Meldung", "Type of report"],
  ["Bitte keine Passwörter, Tokens oder persönlichen Geheimnisse eintragen.", "Please do not enter passwords, tokens or personal secrets."],
  ["Automatische Diagnoseübertragung", "Automatic diagnostics upload"],
  [". Ändern unter Geräte & Dienste → FreshAirIQ → Konfigurieren → Daten & Lernen → Diagnose-Freigabe.", ". Change under Devices & services → FreshAirIQ → Configure → Data & learning → Diagnostics sharing."],
  ["Sensor aktuell nicht verfügbar", "Sensor currently unavailable"],
  ["OPTIONALE ZUSATZSENSOREN · KEIN EINFLUSS AUF DIE LÜFTUNGSPHYSIK", "OPTIONAL EXTRA SENSORS · NO EFFECT ON VENTILATION PHYSICS"],
  ["Bitte Verfügbarkeit und Zuordnung der Temperatur-/Feuchtesensoren prüfen.", "Please check availability and assignment of the temperature/humidity sensors."],
  ["Bei Bedarf können unter Räume & Sensoren Temperatur- und Feuchtesensoren hinterlegt werden.", "If needed, temperature and humidity sensors can be added under Devices & services → FreshAirIQ → Configure."],
  ["Fenster-/Türkontakt", "Window/door contact"],
  ["FreshAirIQ behandelt die lange, stabile Öffnung als wahrscheinliche Dauer- oder Kipplüftung und überwacht sie weiter.", "FreshAirIQ treats the long, stable opening as likely long or tilted ventilation and keeps monitoring it."],
  ["FreshAirIQ begleitet die laufende Lüftung in diesem Raum.", "FreshAirIQ is following the running ventilation in this room."],
  ["FreshAirIQ bewertet diesen Raum fortlaufend aus Klima, Außenluft, Lernmodell und Gebäudeeigenschaften.", "FreshAirIQ continuously evaluates this room from climate, outdoor air, learned model and building properties."],
  ["Oberflächen-RH ·", "surface RH ·"],
  ["Lüftungen ·", "ventilations ·"],
  ["geschätztes Wiederaufheizen", "estimated reheating"],
  ["Fenster/Türen:", "Windows/doors:"],
  ["Daten prüfen", "Check data"],
  ["Bilanz seit Sessionstart", "Balance since session start"],
  ["aktuell entfernbares Potenzial", "currently removable potential"],
  ["Prognose ↔ Realität · Treffer", "Forecast ↔ reality · hits"],
  ["% · Feuchtefaktor", "% · humidity factor"],
  ["· Übernahmen", "· adoptions"],
  ["Vergleicht Produktionsmodell mit Alternativen", "Compares the production model with alternatives"],
  ["· aktuell erwartet", "· currently expected"],
  ["Feuchtequelle", "Moisture source"],
  ["· Schätzung", "· estimate"],
  ["Räumen werden gelüftet", "rooms are being ventilated"],
  ["Live-Bilanz für das ganze Haus", "Live balance for the whole home"],
  ["LIVE-FEUCHTEBILANZ NACH RÄUMEN", "LIVE MOISTURE BALANCE BY ROOM"],
  ["Hausweite Lüftung läuft", "Whole-home ventilation running"],
  ["Wo Feuchtigkeit entweicht oder hinzukommt", "Where moisture escapes or is added"],
  ["Bei einer großen Hauslüftung bewertet FreshAirIQ primär die gemeinsame Hauswirkung. Passiv mitgelüftete Räume werden aus ihrem eigenen Sensorverlauf erkannt und mit ≈ als Schätzung markiert; sie werden nicht doppelt zur Hausbilanz addiert.", "During a large whole-home ventilation FreshAirIQ mainly evaluates the combined effect on the home. Passively ventilated rooms are detected from their own sensor history and marked with ≈ as an estimate; they are not added to the home balance twice."],
  ["Aktive Lüftungen sind deutlich hervorgehoben. Passiv mitgelüftete Räume werden aus ihrem Sensorverlauf erkannt und als Schätzung markiert. Minus = entfernt, Plus = hinzugekommen.", "Active ventilations are highlighted. Passively ventilated rooms are detected from their sensor history and marked as an estimate. Minus = removed, plus = added."],
  ["aktuell entfernbar", "currently removable"],
  ["kein relevantes Potenzial", "no relevant potential"],
  ["FEUCHTEPOTENZIAL NACH RÄUMEN", "MOISTURE POTENTIAL BY ROOM"],
  ["Ohne laufende Lüftung zeigt FreshAirIQ hier raumweise, wo aktuell Feuchtigkeit entfernt werden könnte oder wo Lüften Feuchtigkeit eintragen würde. Minus = entfernbar, Plus = möglicher Eintrag.", "Without a running ventilation FreshAirIQ shows per room where moisture could currently be removed or where ventilating would add moisture. Minus = removable, plus = possible gain."],
  ["Keine gültigen Raumdaten vorhanden.", "No valid room data available."],
  ["LÜFTUNGSERGEBNIS · DAUERHAFT GESPEICHERT", "VENTILATION RESULT · STORED PERMANENTLY"],
  ["Letzte Lüftung im Detail", "Last ventilation in detail"],
  ["Hier bleibt die zuletzt vollständig abgeschlossene Hauslüftung erhalten – auch nachdem die 5-Minuten-Ergebnisanzeige auf dem Hauptdashboard beendet ist.", "The last fully completed whole-home ventilation is kept here – even after the 5-minute result display on the main dashboard has ended."],
  ["SCHIMMEL-IQ · RISIKO NACH RÄUMEN", "MOULD IQ · RISK BY ROOM"],
  ["Die Räume sind nach Risiko sortiert.", "Rooms are sorted by risk."],
  ["Wichtig: Das ist nur eine grobe Einschätzung.", "Important: this is only a rough estimate."],
  ["FreshAirIQ leitet die Oberflächenfeuchte aus dem Raumklima ab. Ohne gemessene Oberflächentemperatur bzw. Taupunkt an der konkreten Bauteiloberfläche lässt sich ein tatsächliches Schimmelrisiko nicht sicher bestimmen. Tippe einen Raum an, um Ursache, Empfehlung und Lernwerte zu sehen.", "FreshAirIQ derives the surface humidity from the room climate. Without a measured surface temperature or dew point on the actual building surface, a real mould risk cannot be determined reliably. Tap a room to see cause, recommendation and learned values."],
  ["Der Statussensor liefert aktuell keine Raumdaten. Bitte Home Assistant nach dem Update einmal neu starten; vorhandene Raumkonfigurationen werden dabei nicht gelöscht.", "The status sensor currently delivers no room data. Please restart Home Assistant once after the update; existing room configurations are not deleted."],
  ["ml in der Luft", "ml in the air"],
  ["RÄUME", "ROOMS"],
  ["Raumübersicht", "Room overview"],
  ["ANWESENHEIT & GÄSTEMODUS", "PRESENCE & GUEST MODE"],
  ["Wer ist heute Nacht im Haus?", "Who is home tonight?"],
  ["FreshAirIQ berücksichtigt aktuell", "FreshAirIQ currently considers"],
  [". Davon sind", ". Of these,"],
  ["über Home Assistant als zuhause erkannt,", "are detected as home via Home Assistant,"],
  ["als abwesend und", "as away and"],
  ["Übernachtungsgäste:", "Overnight guests:"],
  ["Kinder. Jede Änderung kalkuliert Kurzzeit- und Nachtprognose sofort neu. Anwesenheits-IQ", "children. Every change immediately recalculates the short-term and night forecast. Presence IQ"],
  ["ml über", "ml across"],
  ["FreshAirIQ berechnet die Wasserdampfmenge je Raum aus absoluter Feuchte × Raumvolumen. So wird aus Prozent Luftfeuchte ein physikalisch vergleichbarer Wert.", "FreshAirIQ calculates the amount of water vapour per room from absolute humidity × room volume. This turns percent humidity into a physically comparable value."],
  ["Die Entscheidung wird aus Gesundheit/Schimmel, Komfort, Feuchtewirkung, Temperatur und Energie priorisiert. Gelernte Gewohnheiten dürfen Sicherheitsentscheidungen nicht überstimmen.", "The decision is prioritised by health/mould, comfort, moisture effect, temperature and energy. Learned habits must not override safety decisions."],
  ["FreshAirIQ kombiniert Raumdaten, Außenluft, Prognosen und Lernwerte.", "FreshAirIQ combines room data, outdoor air, forecasts and learned values."],
  ["Die Lüftungsschwelle legt fest, ab welchem gesamten Feuchtepotenzial FreshAirIQ eine Hauslüftung als sinnvoll bewertet. Aktuell liegt sie bei", "The ventilation threshold defines from which total moisture potential FreshAirIQ rates a whole-home ventilation as worthwhile. It is currently"],
  [". Die Raumempfehlungen können zusätzlich eigene Gesundheits- oder Schimmelgründe haben. Ändern kannst du die Schwelle unter Einstellungen → Geräte & Dienste → FreshAirIQ → Konfigurieren.", ". Room recommendations can additionally have their own health or mould reasons. You can change the threshold under Settings → Devices & services → FreshAirIQ → Configure."],
  ["FreshAirIQ berücksichtigt die konfigurierte Pollenbelastung als möglichen Lüftungs-Veto-Faktor.", "FreshAirIQ considers the configured pollen load as a possible veto against ventilating."],
  ["Lüftung aktuell eingeschränkt", "Ventilation currently restricted"],
  ["kein Pollen-Veto", "no pollen veto"],
  ["Feuchtebilanz / entfernbar", "Moisture balance / removable"],
  ["Während einer Lüftung zeigt der Wert die seit Beginn berechnete Feuchteänderung. Ohne aktive Lüftung zeigt er das aktuell entfernbar geschätzte Potenzial. Die aktuelle Empfehlungsschwelle liegt bei", "During a ventilation the value shows the moisture change calculated since the start. Without an active ventilation it shows the currently estimated removable potential. The current recommendation threshold is"],
  ["· Minus = Feuchte entfernt, Plus = Feuchte eingetragen.", "· Minus = moisture removed, plus = moisture added."],
  ["Volumengewichtete Temperaturänderung der aktuell gelüfteten Räume seit dem jeweiligen Sessionstart.", "Volume-weighted temperature change of the currently ventilated rooms since their session start."],
  ["Nach einem Neustart werden nur plausible, echte Sensorwerte als Startbasis akzeptiert.", "After a restart, only plausible, real sensor values are accepted as a starting point."],
  ["Empfohlene Dauer aus Außentemperatur, Feuchtedifferenz und den eingestellten Mindest-/Maximalzeiten.", "Recommended duration from outdoor temperature, humidity difference and the configured minimum/maximum times."],
  ["Bei aktiver Lüftung wird die verbleibende bzw. überschrittene Zeit live berechnet.", "During an active ventilation the remaining or exceeded time is calculated live."],
  ["Minuten", "minutes"],
  ["Rollierende Hybrid-Prognose aus gelerntem Luftwechsel, absoluter Feuchte innen/außen, zukünftiger Wetterentwicklung (falls verfügbar), aktuellem Feuchte- und Temperaturtrend, interner Feuchteproduktion, Wind/Fensterausrichtung und Querlüftung. Heizsystem und Energiepreis beeinflussen nicht die physikalische Feuchteprognose, sondern nur die separate Wärmeverlust- und Kostenschätzung.", "Rolling hybrid forecast from learned air exchange, absolute humidity indoors/outdoors, future weather development (if available), current humidity and temperature trend, internal moisture production, wind/window orientation and cross-ventilation. Heating system and energy price do not affect the physical humidity forecast, only the separate heat-loss and cost estimate."],
  ["Bei Horizonten über 5 Minuten simuliert FreshAirIQ den Zustand in 5-Minuten-Schritten und schätzt zusätzlich den effizienten Endpunkt innerhalb des Prognosefensters. Minus = voraussichtlich Feuchte entfernt, Plus = Feuchte kommt hinzu. Modellvertrauen aktuell", "For horizons over 5 minutes FreshAirIQ simulates the state in 5-minute steps and additionally estimates the efficient end point within the forecast window. Minus = moisture expected to be removed, plus = moisture added. Current model confidence"],
  ["Aktive Plausibilitäts- und Vollständigkeitsprüfung der konfigurierten Datenquellen.", "Active plausibility and completeness check of the configured data sources."],
  ["Räume gültig ·", "rooms valid ·"],
  ["auffällig · Wetter", "flagged · weather"],
  ["Räumen ·", "rooms ·"],
  ["verfügbar", "available"],
  ["Intelligente Feuchteprognose bis zum relevanten Nachtende (", "Intelligent humidity forecast until the relevant end of night ("],
  ["Sie kombiniert aktuell erwartete Bewohner (", "It combines the currently expected residents ("],
  ["), Gäste, gelernte Nachtproben, aktuellen Feuchtetrend, absolute Außenfeuchte, offene Fenster, Wind, Fensterausrichtung und gelernten Luftwechsel. Wettereffekt", "), guests, learned night samples, current humidity trend, absolute outdoor humidity, open windows, wind, window orientation and learned air exchange. Weather effect"],
  ["Entfeuchten priorisiert Feuchteabbau. Komfort balanciert Feuchte, Temperatur und Energie. Sommer kühlen nutzt kühle Außenluft, solange der Feuchteeintrag vertretbar bleibt.", "Dehumidify prioritises moisture removal. Comfort balances humidity, temperature and energy. Summer cooling uses cool outdoor air as long as the added moisture stays acceptable."],
  ["ERKLÄRUNG", "EXPLANATION"],
  ["oder", "or"],
  ["Übernehmen", "Apply"],
  ["Schnellwahl wird sofort übernommen. Für einen beliebigen Wert von 1 bis 120 Minuten Zahl eingeben und „Übernehmen“ wählen.", "Quick choices apply immediately. For any value from 1 to 120 minutes enter a number and choose “Apply”."],
  ["ÜBERNACHTUNGSGÄSTE", "OVERNIGHT GUESTS"],
  ["Die Anzeige reagiert sofort; FreshAirIQ berechnet die Nachtprognose anschließend mit der neuen Belegung neu.", "The display reacts immediately; FreshAirIQ then recalculates the night forecast with the new occupancy."],
  ["Ich kenne inzwischen dein Zuhause und bestätigte Nutzungs- und Komfortmuster. Persönliche Optimierung ist aktiv.", "I now know your home and confirmed usage and comfort patterns. Personal optimisation is active."],
  ["Ich arbeite zunächst mit Gebäudephysik und aktuellen Messwerten. Persönliches Lernen beginnt erst mit belastbaren Beobachtungen.", "For now I work with building physics and current readings. Personal learning only starts with reliable observations."],
  ["FreshAirIQ sammelt unabhängige Erfahrungen und bestätigt erkannte Muster Schritt für Schritt an realen Ergebnissen.", "FreshAirIQ collects independent experience and confirms detected patterns step by step against real results."],
  ["Lernlüftungen", "learning ventilations"],
  ["unabhängige Lüftungen · Lernwirkung", "independent ventilations · learning effect"],
  ["Tage ·", "days ·"],
  ["Lüftungen", "ventilations"],
  ["/120 Nächte", "/120 nights"],
  ["Reife zeigt unabhängige Erfahrung. Prognosequalität zeigt getrennt davon, wie gut Vorhersagen bisher zur Realität passen.", "Maturity shows independent experience. Forecast quality shows separately how well predictions have matched reality so far."],
  ["Raumphysik, Feuchtepuffer & Hausstrategie", "Room physics, moisture buffer & home strategy"],
  ["MODELLQUALITÄT & DIAGNOSE", "MODEL QUALITY & DIAGNOSTICS"],
  ["Wie gut FreshAirIQ aktuell vorhersagt", "How well FreshAirIQ currently predicts"],
  ["Lernreife und Prognosequalität sind getrennt. Zusätzlich vergleicht FreshAirIQ jede neue geeignete Lüftung paarweise mit einem eingefrorenen, ungelernten Grundmodell. Sobald für denselben Raum eine ältere, abweichende Forecast-Generation existiert, wird außerdem die aktuelle Generation gegen diesen unmittelbaren beobachteten Vorgänger unter derselben Startlage und Messdauer replayt.", "Learning maturity and forecast quality are separate. In addition, FreshAirIQ compares every new suitable ventilation pairwise with a frozen, untrained base model. If an older, different forecast generation exists for the same room, the current generation is also replayed against this directly observed predecessor with the same starting situation and measuring time."],
  ["Prognosegüte", "Forecast quality"],
  ["Unabhängige Lüftungen", "Independent ventilations"],
  ["Unterschiedliche Tage", "Different days"],
  ["· Belegt wird eine Verbesserung erst nach mindestens", "· An improvement is only confirmed after at least"],
  ["unabhängigen Lüftungen an", "independent ventilations on"],
  ["unterschiedlichen Tagen und einem vollständig positiven, nach Lüftungen geclusterten Fehlerintervall. Der Generationenvergleich verwendet dieselben konservativen Evidenzregeln.", "different days and a fully positive error interval clustered by ventilation. The generation comparison uses the same conservative evidence rules."],
  ["/ 60 Tage", "/ 60 days"],
  ["Vollständig durchlaufen und ausreichend belegt", "Fully covered and sufficiently backed by data"],
  ["Noch nicht vollständig beobachtet", "Not fully observed yet"],
  ["Jahreszeiten werden mit den nächsten Beobachtungstagen aufgebaut.", "Seasons are built up over the next observation days."],
  ["Saisonalität & Nachtmodell", "Seasonality & night model"],
  ["Hier zählt Zeit als echte Erfahrung: jede Nacht höchstens einmal und jede Jahreszeit erst, wenn sie vollständig durchlaufen und ausreichend mit brauchbaren Messwerten belegt wurde.", "Time counts here as real experience: each night at most once, and each season only when it has been fully covered and sufficiently backed by usable readings."],
  ["Tage Kalenderabdeckung", "days of calendar coverage"],
  ["Saisonalität", "Seasonality"],
  ["Gesamtmodell Saisonalität", "Overall seasonality model"],
  ["/ 365 Tage", "/ 365 days"],
  ["Nächte gelernt", "nights learned"],
  ["Hohe Pollingraten beschleunigen die Reife nicht. Entscheidend sind unterschiedliche Nächte, Tage und vollständig beobachtete Jahreszeiten.", "High polling rates do not speed up maturity. What counts are different nights, days and fully observed seasons."],
  ["Unterschiedliche Nächte bestimmen die Reife.", "Different nights determine maturity."],
  ["Noch keine Lerndaten verfügbar.", "No learning data available yet."],
  ["Hausklima & Lüftungsintelligenz", "Home climate & ventilation intelligence"],
  ["über berechnete Räume", "across calculated rooms"],
  ["LÜFTUNGSSCHWELLE", "VENTILATION THRESHOLD"],
  ["Wasser in der Hausluft · Tagesmittel", "Water in the indoor air · daily average"],
  ["Absolute Feuchte × Raumvolumen, über alle überwachten Räume aggregiert. Tageswert = Mittel aller gültigen Messungen; Trend:", "Absolute humidity × room volume, aggregated over all monitored rooms. Daily value = average of all valid readings; trend:"],
  ["aktuell zuhause/erwartet ·", "currently home/expected ·"],
  ["FreshAirIQ nutzt die Anwesenheit für Nachtprognose und Belegungsmodell.", "FreshAirIQ uses presence for the night forecast and occupancy model."],
  ["% der Wassermenge", "% of the water amount"],
  ["nicht berücksichtigt", "not considered"],
  ["noch unsicher", "still uncertain"],
  ["Haustiermodus ist aktiv; reine Bewegung wird vorsichtiger bewertet.", "Pet mode is active; motion alone is rated more cautiously."],
  ["LÜFTUNGSPROTOKOLL", "VENTILATION LOG"],
  ["FreshAirIQ protokolliert abgeschlossene Lüftungen lokal in Home Assistant. Wähle einen Zeitraum und erstelle eine übersichtliche PDF mit Raum, Zeit, Dauer und – soweit durch die Sensoren belastbar erfasst – Klima- und Feuchtewirkung. Die PDF ist eine Sensordokumentation und keine rechtliche Bewertung.", "FreshAirIQ logs completed ventilations locally in Home Assistant. Choose a period and create a clear PDF with room, time, duration and – where reliably captured by the sensors – climate and moisture effect. The PDF is sensor documentation, not a legal assessment."],
  ["Lüftungsprotokoll", "Ventilation log"],
  ["FreshAirIQ-Konfiguration nicht gefunden", "FreshAirIQ configuration not found"],
  ["PDF wird erstellt", "Creating PDF"],
  ["bitte warten", "please wait"],
  ["Export wird erstellt", "Creating export"],
  ["Datei ist bereit", "File is ready"],
  ["FreshAirIQ wartet auf die Status-Entität.", "FreshAirIQ is waiting for the status entity."],
  ["min übrig", "min remaining"],
  ["min drüber", "min over"],
  ["Bitte eine Beschreibung mit mindestens 3 Zeichen eingeben.", "Please enter a description with at least 3 characters."],
  ["Bitte Verbindung zum Diagnose-Hub prüfen.", "Please check the connection to the diagnostics hub."],
  ["Polleninformationen als ergänzende Analyse; kritische Warnungen bleiben sicherheitsbedingt möglich.", "Pollen information as additional analysis; critical warnings remain possible for safety reasons."],
  ["Zeigt konfigurierte VOC-/TVOC-Zusatzwerte in Raumdetails. Die globale Berücksichtigung wird unter Geräte & Dienste → FreshAirIQ → Konfigurieren gesteuert.", "Shows configured VOC/TVOC values in room details. Whether they are considered globally is set under Devices & services → FreshAirIQ → Configure."],
  ["Zeigt konfigurierte PM2.5-Zusatzwerte in Raumdetails. Die globale Berücksichtigung wird unter Geräte & Dienste → FreshAirIQ → Konfigurieren gesteuert.", "Shows configured PM2.5 values in room details. Whether they are considered globally is set under Devices & services → FreshAirIQ → Configure."],
  ["Zeigt konfigurierte Helligkeitswerte in Raumdetails. Die globale Berücksichtigung wird unter Geräte & Dienste → FreshAirIQ → Konfigurieren gesteuert.", "Shows configured illuminance values in room details. Whether they are considered globally is set under Devices & services → FreshAirIQ → Configure."],
  ["Zeigt Querlüftung als ergänzende Analyseinformation, wenn sie erkannt wird.", "Shows cross-ventilation as additional analysis information when it is detected."],
  ["Zeigt Empfehlungen zum Starten oder Fortsetzen einer Lüftung.", "Shows recommendations to start or continue ventilating."],
  ["Zeigt Empfehlungen zum Beenden einer Lüftung.", "Shows recommendations to stop ventilating."],
  ["Zeigt raumspezifische Hinweise, wenn Lüften aktuell nicht sinnvoll ist.", "Shows room-specific notes when ventilating is currently not useful."],
  ["Sommerkühlung", "Summer cooling"],
  ["Zeigt Empfehlungen zum Lüften für Kühlung.", "Shows recommendations to ventilate for cooling."],
  ["Zeigt Empfehlungen bei fehlenden oder unplausiblen Messwerten.", "Shows recommendations for missing or implausible readings."],
  ["Ausblenden macht die Karte kompakter.", "Hiding makes the card more compact."],
  ["Zeigt, was FreshAirIQ gerade analysiert und wie sicher die Prognose ist.", "Shows what FreshAirIQ is analysing right now and how certain the forecast is."],
  ["Blendet den direkten Details-Button ein oder aus.", "Shows or hides the direct Details button."],
  ["Blendet die Schnellsteuerung für Gäste ein oder aus.", "Shows or hides the quick controls for guests."],
  ["Blendet den direkten Zugriff auf die Raumübersicht ein oder aus.", "Shows or hides direct access to the room overview."],
  ["Support-Schaltfläche", "Support button"],
  ["Blendet den zentralen Zugriff auf Diagnose, Feedback und Support ein oder aus.", "Shows or hides central access to diagnostics, feedback and support."],
  ["Überschrift, Aktion und Zusammenfassung der aktuellen Empfehlung.", "Heading, action and summary of the current recommendation."],
  ["Feuchte-, Temperatur- und CO₂-Ziele sowie deren Wirkung und Zeit.", "Humidity, temperature and CO₂ goals with their effect and time."],
  ["Raumnamen, Raumstatus und raumbezogene Hinweise.", "Room names, room status and room notes."],
  ["Werte in Kennzahlen- und Informationskacheln.", "Values in key-figure and information tiles."],
  ["Begründungen & Details", "Reasons & details"],
  ["Begründungen, Alternativen und ausführliche Entscheidungstexte.", "Reasons, alternatives and detailed decision texts."],
  ["Labels, Hinweise und andere kleine Metatexte.", "Labels, notes and other small meta texts."],
  ["Standardmäßig bleibt das vollständige Dashboard sichtbar. Hier kannst du Zusatzbereiche einzeln ausblenden. Wenn du alle Informationen und festen Bedienelemente deaktivierst, bleibt eine kompakte Ansicht mit der zentralen FreshAirIQ-Empfehlung.", "By default the full dashboard stays visible. Here you can hide additional areas individually. If you turn off all information and fixed controls, a compact view with the central FreshAirIQ recommendation remains."],
  ["Wähle, welche Arten von raumspezifischen Empfehlungen diese Karte wiedergibt.", "Choose which kinds of room-specific recommendations this card shows."],
  ["Diese Schalter ändern nur die Darstellung dieser einzelnen Dashboard-Karte. Globale FreshAirIQ-Einstellungen werden ausschließlich unter Geräte & Dienste → FreshAirIQ → Konfigurieren verwaltet.", "These switches only change how this single dashboard card looks. Global FreshAirIQ settings are managed exclusively under Devices & services → FreshAirIQ → Configure."],
  ["Blende feste Bereiche und Schnellzugriffe aus, bis nur noch die Empfehlung übrig bleibt.", "Hide fixed areas and shortcuts until only the recommendation is left."],
  ["INFORMATIONEN DIESER KARTE", "INFORMATION ON THIS CARD"],
  ["DARSTELLUNG & KOMPAKTHEIT", "LAYOUT & COMPACTNESS"],
  ["EMPFEHLUNGEN", "RECOMMENDATIONS"],
  ["WASSER IN DER HAUSLUFT", "WATER IN THE INDOOR AIR"],
  ["FEUCHTEPOTENZIAL", "MOISTURE POTENTIAL"],
  ["Oberflächen-RH", "surface RH"],
  ["Personen aktuell zuhause/erwartet", "people currently home/expected"],
  ["Person aktuell zuhause/erwartet", "person currently home/expected"],
  ["Erwachsene", "adults"],
  ["Kinder", "children"],
  ["Gäste", "Guests"],
  ["Wetter fehlt", "weather missing"],
  ["Fenster", "Window"],
  ["Lernmodell", "learned model"],
  ["sicher erkannt", "reliably detected"],
  ["wahrscheinlich", "likely"],
  ["unauffällig", "unremarkable"],
  ["Hausweite", "Whole-home"]
);
// 0.26.4.5: longest phrases first; single words only as whole words. Plain substring
// replacement turned "Hausklima" into "Houseklima" and "Raumübersicht" into "Roomübersicht".
const FAIQ_EN_RULES = [...FAIQ_NATIVE_EN, ...FAIQ_UI_EN]
  .filter(([de]) => de)
  .sort((a, b) => b[0].length - a[0].length)
  .map(([de, en]) => /^[\p{L}\p{N}₂.\-]+$/u.test(de)
    ? [new RegExp(`(?<![\\p{L}\\p{N}])${de.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")}(?![\\p{L}\\p{N}])`, "gu"), en]
    : [de, en]);
const faiqEnglishText = value => {
  let out = String(value == null ? "" : value);
  // Sentence patterns with numbers first, before word/phrase rules split them up.
  out = out
    .replace(/(\d+) von (\d+) Räumen werden gelüftet/g, "$1 of $2 rooms are being ventilated")
    .replace(/(\d+) von (\d+) Raum\/Räumen für Genauigkeitswertung verwertbar/g, "$1 of $2 room(s) usable for accuracy scoring")
    .replace(/Ergebnis noch (\d+) min im Dashboard/g, "Result shown for $1 more min on the dashboard")
    .replace(/Außenluft würde in (\d+) min ca\. \+(\d+) ml Feuchtigkeit eintragen/g, "Outdoor air would add about +$2 ml of moisture within $1 min")
    .replace(/optimal noch ca\. (\d+) min/g, "optimal for about $1 more min")
    .replace(/Hausweit (.+?) möglich/g, "Whole home: $1 possible")
    .replace(/(\d+)\/4 Jahreszeiten/g, "$1/4 seasons")
    .replace(/(\d+) geeigneten Raumvergleichen aus/g, "$1 suitable room comparisons from")
    .replace(/(\d+) Tage · (\d+) Lüftungen/g, "$1 days · $2 ventilations")
    .replace(/CO₂ in (\d+) Räumen/g, "CO₂ in $1 rooms")
    .replace(/Kurzfristiger Schließcheck \(5 min\): voraussichtlich (\d+) ml Feuchteabbau/g, "Short-term close check (5 min): expected $1 ml moisture reduction")
    .replace(/Etwa (\d+) ml Feuchtigkeit können entfernt werden/g, "About $1 ml of moisture can be removed")
    .replace(/Jetzt lüften · etwa (\d+) ml entfernbar/g, "Ventilate now · about $1 ml removable")
    .replace(/Lüftung läuft · (\d+) ml Feuchtigkeit eingetragen/g, "Ventilation running · $1 ml moisture added")
    .replace(/Lüftung läuft · (\d+) ml Feuchtigkeit entfernt/g, "Ventilation running · $1 ml moisture removed")
    .replace(/(\d+) Raum\/Räume werden automatisch verfolgt\./g, "$1 room(s) are being tracked automatically.")
    .replace(/(\d+) weitere Räume ohne akuten Handlungsbedarf/g, "$1 more rooms without urgent action needed")
    .replace(/Alle (\d+) Räume ohne akuten Handlungsbedarf/g, "All $1 rooms without urgent action needed")
    .replace(/(\d+) min übrig/g, "$1 min remaining")
    .replace(/LETZTE (\d+) TAGE/g, "LAST $1 DAYS")
    .replace(/WEITERE (\d+) MIN/g, "NEXT $1 MIN")
    .replace(/weitere (\d+) min/g, "next $1 min")
    .replace(/Bilanz in (\d+) Tagen/g, "Balance over $1 days")
    .replace(/Noch maximal (\d+) s/g, "At most $1 s left")
    .replace(/Noch (\d+) Min\. gesperrt/g, "Locked for $1 more min")
    .replace(/(\d+) TAGE\b/g, "$1 DAYS")
    .replace(/(\d+) Raum braucht Aufmerksamkeit/g, "$1 room needs attention")
    .replace(/(\d+) Räume brauchen Aufmerksamkeit/g, "$1 rooms need attention");
  for (const [de, en] of FAIQ_EN_RULES) out = typeof de === "string" ? out.split(de).join(en) : out.replace(de, () => en);

  return out;
};
const faiqLocalizeTree = root => {
  if (!root) return;
  const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT);
  const nodes = [];
  while (walker.nextNode()) nodes.push(walker.currentNode);
  for (const node of nodes) {
    const parent = node.parentElement;
    if (parent && ["STYLE", "SCRIPT"].includes(parent.tagName)) continue;
    const translated = faiqEnglishText(node.nodeValue);
    if (translated !== node.nodeValue) node.nodeValue = translated;
  }
  root.querySelectorAll?.("[title],[placeholder],[aria-label]").forEach(el => {
    for (const attr of ["title", "placeholder", "aria-label"]) {
      if (!el.hasAttribute(attr)) continue;
      const before = el.getAttribute(attr) || "";
      const after = faiqEnglishText(before);
      if (after !== before) el.setAttribute(attr, after);
    }
  });
};
const esc = v => String(v !== null && v !== void 0 ? v : "").split("&").join("&amp;").split("<").join("&lt;").split(">").join("&gt;").split('"').join("&quot;").split("'").join("&#039;");
const lastItem = arr => (arr && arr.length ? arr[arr.length - 1] : undefined);
// 0.26.4.5: number/date format follows the dashboard language (set at the start of _render).
let FAIQ_NUMBER_LOCALE = "de";
const fmt = (v, d = 1) => { const n = Number(v); if (!Number.isFinite(n)) return "–"; const s = n.toFixed(d); return FAIQ_NUMBER_LOCALE === "de" ? s.replace(".", ",") : s; };
// 0.26.4.1: head counts read "4 Personen", not "4,0"; a weighted share (e.g. 2,5) keeps one decimal.
const fmtPeople = v => { const n = Number(v); if (!Number.isFinite(n)) return "–"; const r = Math.round(n * 10) / 10; return Number.isInteger(r) ? String(r) : fmt(r, 1); };
const whenDE = v => { if (!v)
    return FAIQ_NUMBER_LOCALE === "de" ? "noch keine Messung" : "no measurement yet"; const d = new Date(v); return Number.isNaN(d.getTime()) ? "–" : d.toLocaleString(FAIQ_NUMBER_LOCALE === "de" ? "de-DE" : "en-GB", { day: "2-digit", month: "2-digit", hour: "2-digit", minute: "2-digit" }); };
const signed = (v, unit = "") => { const n = Number(v || 0); if (Math.abs(n) < .05)
    return `±${fmt(0, 1)}${unit ? " " + unit : ""}`; return `${n > 0 ? "+" : "−"}${fmt(Math.abs(n), 1)}${unit ? " " + unit : ""}`; };
const moisture = (physicalRemovedMl, zero = "0 ml") => {
    const n = Number(physicalRemovedMl || 0);
    if (Math.abs(n) < .5)
        return { text: zero, color: "#9aa7b3", kind: "neutral" };
    return n > 0
        ? { text: `−${Math.abs(Math.round(n))} ml`, color: "#67df92", kind: "removed" }
        : { text: `+${Math.abs(Math.round(n))} ml`, color: "#ff7770", kind: "added" };
};
const actionDE = v => ({ "Ventilate": "Lüften", "Continue ventilating": "Weiterlüften", "Close": "Schließen", "Do not ventilate": "Nicht lüften", "Wait": "Warten", "Okay": "Alles okay", "Check sensor": "Sensor prüfen", "Ventilate for cooling": "Zum Kühlen lüften", "Monitor only": "Nur anzeigen", "Open fully": "Vollständig öffnen" }[v] || v || "–");
const mouldDE = v => ({ "Very high": "Sehr hoch", "High": "Hoch", "Elevated": "Erhöht", "Slightly elevated": "Leicht erhöht", "Low": "Niedrig", "Unknown": "Unbekannt" }[v] || v || "Unbekannt");
const learnDE = v => ({ "Very stable": "Sehr stabil", "Stable": "Stabil", "Usable": "Brauchbar", "Learning": "Lernt", "Base estimate": "Grundschätzung" }[v] || v || "–");
const profileDE = v => ({ dehumidify: "Entfeuchten", comfort: "Komfort", summer_cooling: "Sommer kühlen" }[v] || v || "Komfort");
const floorDE = v => ({ basement: "Kellergeschoss", base_floor: "Kellergeschoss", "base floor": "Kellergeschoss", Basement: "Kellergeschoss", ground_floor: "Erdgeschoss", "ground floor": "Erdgeschoss", "Ground Floor": "Erdgeschoss", upper_floor: "Obergeschoss", "upper floor": "Obergeschoss", "Upper Floor": "Obergeschoss", attic: "Dachgeschoss", Attic: "Dachgeschoss", other: "Sonstige", Other: "Sonstige" }[String(v || "")] || v || "Unzugeordnet");
const propertyDE = v => ({ house: "Haus", detached: "Freistehendes Haus", semi_detached: "Doppelhaushälfte", row_mid: "Reihenmittelhaus", row_end: "Reihenendhaus", apartment: "Wohnung", attic_apartment: "Dachgeschosswohnung", maisonette: "Maisonette", multi_family: "Mehrfamilienhaus", other: "Sonstiges" }[v] || v || "–");
const heatingDE = v => ({ heat_pump: "Wärmepumpe", gas: "Gas", district_heating: "Fernwärme", electric: "Elektro", oil: "Öl" }[v] || v || "–");
const orientationDE = v => ({ unknown: "–", n: "Nord", ne: "Nordost", e: "Ost", se: "Südost", s: "Süd", sw: "Südwest", w: "West", nw: "Nordwest" }[String(v || "unknown").toLowerCase()] || "–");
const roomVisual = r => {
    const customIcon = String((r && r.icon) || "").trim();
    if (customIcon.startsWith("mdi:")) return [customIcon, "#5bd4ff", "rgba(91,212,255,.11)"];
    const name = String((r === null || r === void 0 ? void 0 : r.name) || (r === null || r === void 0 ? void 0 : r.key) || "").toLowerCase();
    // 0.26.4.2 (community): "Wohnzimmer" showed the kitchen pot. Only kitchens get it.
    if (name.includes("küche") || name.includes("kueche") || name.includes("kitchen"))
        return ["mdi:pot-steam-outline", "#f2c45d", "rgba(242,196,93,.13)"];
    if (name.includes("wohn") || name.includes("living"))
        return ["mdi:sofa-outline", "#f2c45d", "rgba(242,196,93,.13)"];
    if (name.includes("gäste wc") || name.includes("gaeste wc") || name.includes("gästewc") || name.includes("gaestewc") || name.includes("toilet"))
        return ["mdi:toilet", "#42a5ff", "rgba(66,165,255,.13)"];
    if (name.includes("flur") || name.includes("diele") || name.includes("treppe") || name.includes("hall") || name.includes("corridor") || name.includes("stair") || name.includes("landing"))
        return ["mdi:stairs", "#b47cff", "rgba(180,124,255,.13)"];
    if (name.includes("schlaf") || name.includes("bedroom"))
        return ["mdi:bed-king-outline", "#39d6d0", "rgba(57,214,208,.13)"];
    if (name.includes("kinder") || name.includes("kid") || name.includes("child") || name.includes("nursery"))
        return ["mdi:teddy-bear", "#ff8eb4", "rgba(255,142,180,.13)"];
    if (name.includes("bad") || name.includes("bade") || name.includes("bath") || name.includes("shower"))
        return ["mdi:bathtub-outline", "#61b6ff", "rgba(97,182,255,.13)"];
    if (name.includes("arbeits") || name.includes("büro") || name.includes("buero") || name.includes("office") || name.includes("study"))
        return ["mdi:desk", "#69d19b", "rgba(105,209,155,.13)"];
    if (name.includes("fitness") || name.includes("gym"))
        return ["mdi:dumbbell", "#f28d64", "rgba(242,141,100,.13)"];
    if (name.includes("wellness") || name.includes("sauna"))
        return ["mdi:spa-outline", "#c98cff", "rgba(201,140,255,.13)"];
    if (name.includes("lager") || name.includes("abstell") || name.includes("storage") || name.includes("utility") || name.includes("laundry"))
        return ["mdi:archive-outline", "#a6b4bf", "rgba(166,180,191,.11)"];
    if (name.includes("gast") || name.includes("gäste") || name.includes("gaeste") || name.includes("guest"))
        return ["mdi:bed-outline", "#61b6ff", "rgba(97,182,255,.13)"];
    return ["mdi:home-outline", "#5bd4ff", "rgba(91,212,255,.11)"];
};
const reasonDE = value => {
    var _a, _b;
    const s = String(value || "");
    if (s.startsWith("Short-term 5-minute close check expects")) {
        const n = ((_a = s.match(/(\d+)\s*ml/)) === null || _a === void 0 ? void 0 : _a[1]) || "–";
        return `Kurzfristiger Schließcheck (5 min): voraussichtlich ${n} ml Feuchteabbau`;
    }
    if (s.startsWith("About") && s.includes("moisture can be removed")) {
        const n = ((_b = s.match(/About\s+(\d+)\s+ml/)) === null || _b === void 0 ? void 0 : _b[1]) || "–";
        return `Etwa ${n} ml Feuchtigkeit können entfernt werden`;
    }
    if (s.startsWith("Pollen load")) {
        return "Pollenbelastung liegt über dem eingestellten Grenzwert";
    }
    return ({ "Target reached or additional ventilation benefit is too low": "Ziel erreicht oder zusätzlicher Lüftungsnutzen zu gering", "Reference air would add moisture": "Referenzluft würde zusätzliche Feuchtigkeit eintragen", "Potential exists, but ventilation threshold is not reached": "Potenzial vorhanden, Lüftungsschwelle noch nicht erreicht", "No meaningful ventilation demand": "Kein sinnvoller Lüftungsbedarf", "Missing or implausible measurements": "Messwerte fehlen oder sind unplausibel", "Room is visible but excluded from FreshAirIQ calculations": "Raum wird angezeigt, beeinflusst die Berechnungen aber nicht" }[s] || s);
};
const statusTextDE = value => {
    var _a, _b;
    const s = String(value || "");
    if (s === "Keep windows closed")
        return "Fenster geschlossen lassen";
    if (s.startsWith("Ventilate now")) {
        const n = ((_a = s.match(/(\d+)\s*ml/)) === null || _a === void 0 ? void 0 : _a[1]) || "–";
        return `Jetzt lüften · etwa ${n} ml entfernbar`;
    }
    if (s.startsWith("Ventilation running")) {
        const n = ((_b = s.match(/(\d+)\s*ml/)) === null || _b === void 0 ? void 0 : _b[1]) || "–";
        return s.includes("added") ? `Lüftung läuft · ${n} ml Feuchtigkeit eingetragen` : `Lüftung läuft · ${n} ml Feuchtigkeit entfernt`;
    }
    if (s.startsWith("Close "))
        return "Fenster jetzt schließen";
    if (s.startsWith("Check "))
        return "Raumsensoren prüfen";
    if (s.startsWith("Pollen load"))
        return "Pollenbelastung zu hoch · Lüften verschoben";
    if (s.startsWith("Summer cooling"))
        return "Sommerkühlung sinnvoll";
    return s;
};
const mouldStyle = v => ({ "Very high": ["#ff6868", "rgba(255,80,80,.12)"], "High": ["#ffb45f", "rgba(255,180,95,.10)"], "Elevated": ["#e2bd69", "rgba(226,189,105,.08)"], "Slightly elevated": ["#d7c982", "rgba(215,201,130,.06)"], "Low": ["#67df92", "rgba(103,223,146,.05)"], "Unknown": ["#9aa7b3", "rgba(255,255,255,.025)"] }[v] || ["#9aa7b3", "rgba(255,255,255,.025)"]);
const diagnosisDE = value => String(value || "Noch keine Lernmessung").replace(/^Learned:/, "Gelernt:").replace(/^Rejected:/, "Verworfen:").replace(/^Paused:/, "Pausiert:").replace("No learning session evaluated yet", "Noch keine Lernsession ausgewertet").replace("learning disabled", "Lernmodus deaktiviert").replace("duration", "Dauer").replace("start delta", "Startdifferenz").replace("humidity reduction", "Feuchteabbau").replace("learning rate", "Lernrate").replace("sample", "Probe").replace("reduction", "Abbau").replace("rate", "Rate");
const styleFor = a => ({
    "Close": ["#ffb45f", "rgba(255,180,95,.08)", "mdi:window-closed-variant"],
    "Continue ventilating": ["#5bcaff", "rgba(70,190,235,.07)", "mdi:weather-windy"],
    "Ventilate": ["#62e889", "rgba(80,210,125,.07)", "mdi:weather-windy"],
    "Ventilate for cooling": ["#63d2f7", "rgba(70,190,235,.07)", "mdi:snowflake"],
    "Do not ventilate": ["#ff7770", "rgba(220,90,80,.07)", "mdi:water-plus"],
    "Wait": ["#e2bd69", "rgba(210,175,95,.06)", "mdi:progress-clock"],
    "Check sensor": ["#ff7770", "rgba(220,90,80,.07)", "mdi:alert-circle-outline"],
    "Monitor only": ["#9aa7b3", "rgba(255,255,255,.025)", "mdi:eye-outline"]
}[a] || ["#9aa7b3", "rgba(255,255,255,.025)", "mdi:check-circle-outline"]);
const FAIQ_FONT_SCALE_STEPS = Object.freeze([0.8,0.9,1,1.1,1.2,1.3,1.4,1.5]);
const normalizeFontScale = value => { const n=Number(value); if(!Number.isFinite(n)) return 1; return FAIQ_FONT_SCALE_STEPS.reduce((best,step)=>Math.abs(step-n)<Math.abs(best-n)?step:best,1); };
const normalizeDashboardConfig = input => {
    const raw = input || {};
    const inherited = (key, legacyKey, fallback = true) => raw[key] !== undefined ? raw[key] : (legacyKey && raw[legacyKey] !== undefined ? raw[legacyKey] : fallback);
    const out = Object.assign({}, raw, {
        info_moisture: inherited("info_moisture", "show_moisture", true),
        info_temperature: inherited("info_temperature", "show_temperature", true),
        info_time: inherited("info_time", "show_time", true),
        info_forecast: inherited("info_forecast", "show_next5", true),
        info_night: inherited("info_night", "show_night", true),
        info_mould: inherited("info_mould", "show_mould", true),
        info_energy: inherited("info_energy", "show_energy", true),
        info_pollen: inherited("info_pollen", "show_pollen", true),
        info_voc: inherited("info_voc", null, true),
        info_pm25: inherited("info_pm25", null, true),
        info_illuminance: inherited("info_illuminance", null, true),
        info_cross_ventilation: inherited("info_cross_ventilation", "show_cross_ventilation", true),
        show_branding: inherited("show_branding", null, true),
        show_profile_badge: inherited("show_profile_badge", null, true),
        show_iq_process: inherited("show_iq_process", null, true),
        show_details_button: inherited("show_details_button", null, true),
        show_guests_button: inherited("show_guests_button", null, true),
        show_rooms_button: inherited("show_rooms_button", null, true),
        show_support_button: inherited("show_support_button", null, true),
        show_rec_ventilate: inherited("show_rec_ventilate", null, true),
        show_rec_close: inherited("show_rec_close", null, true),
        show_rec_wait: inherited("show_rec_wait", null, true),
        show_rec_cooling: inherited("show_rec_cooling", null, true),
        show_rec_sensor: inherited("show_rec_sensor", null, true),
        dashboard_variant: ["classic", "iq"].includes(String(raw.dashboard_variant || "classic")) ? String(raw.dashboard_variant || "classic") : "classic",
        font_scale_recommendation: normalizeFontScale(raw.font_scale_recommendation),
        font_scale_goals: normalizeFontScale(raw.font_scale_goals),
        font_scale_rooms: normalizeFontScale(raw.font_scale_rooms),
        font_scale_metrics: normalizeFontScale(raw.font_scale_metrics),
        font_scale_details: normalizeFontScale(raw.font_scale_details),
        font_scale_meta: normalizeFontScale(raw.font_scale_meta),
    });
    ["show_moisture", "show_temperature", "show_time", "show_next5", "show_night", "show_mould", "show_energy", "show_pollen", "show_cross_ventilation"].forEach(key => delete out[key]);
    return out;
};
const FAIQ_CARD_CSS = `
      :host{display:block;color-scheme:dark;-webkit-text-size-adjust:100%;text-size-adjust:100%}*{box-sizing:border-box}ha-card{overflow:visible;border-radius:22px;border:1px solid rgba(80,205,245,.13);background:radial-gradient(circle at 92% 0%,rgba(60,205,255,.10),transparent 34%),linear-gradient(135deg,rgba(22,29,38,.99),rgba(17,23,30,.99));color:#e9f0f4;--primary-text-color:#e9f0f4;--secondary-text-color:#84939e;box-shadow:0 10px 30px rgba(0,0,0,.20)}.card{padding:13px;font-family:inherit}.top{display:grid;grid-template-columns:48px minmax(0,1fr) auto;gap:11px;align-items:center}.logo{width:48px;height:48px;border-radius:14px;object-fit:cover}.brand{font-size:20px;font-weight:950}.iq{color:#56d5ff}.hero{font-size:10px;font-weight:800;color:var(--faiq-hero-color);margin-top:3px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.pill{padding:6px 9px;border-radius:999px;font-size:9px;font-weight:850;color:var(--faiq-hero-color);background:var(--faiq-hero-bg);border:1px solid var(--faiq-hero-border)}.recommendations{margin-top:11px;padding:10px;border-radius:14px;background:rgba(255,255,255,.022);border:1px solid rgba(255,255,255,.065)}.recommendations-title{display:flex;align-items:end;justify-content:space-between;gap:10px;margin-bottom:7px}.recommendations-title b{font-size:12px}.recommendations-title span{font-size:8px;color:#82929e;text-align:right}.recommendation-row{display:grid;grid-template-columns:34px minmax(0,1fr);gap:9px;padding:9px 8px;border-radius:11px;border:1px solid rgba(255,255,255,.10);border:1px solid color-mix(in srgb,var(--rec) 25%,transparent);background:rgba(255,255,255,.025);background:color-mix(in srgb,var(--rec) 5%,transparent)}.recommendation-row+.recommendation-row{margin-top:6px}.rec-icon{width:34px;height:34px;border-radius:10px;display:flex;align-items:center;justify-content:center;color:var(--rec);background:rgba(255,255,255,.045);background:color-mix(in srgb,var(--rec) 10%,transparent)}.rec-icon ha-icon{--mdc-icon-size:20px}.rec-head{display:flex;justify-content:space-between;gap:8px;align-items:baseline}.rec-head b{font-size:11px}.rec-head strong{font-size:9px;color:var(--rec);white-space:nowrap}.rec-reasons{display:grid;gap:2px;margin-top:4px}.rec-reasons span{font-size:9px;line-height:12px;color:#b4c0c8}.rec-reasons span:before{content:"• ";color:var(--rec)}.recommendation-empty{display:grid;grid-template-columns:28px minmax(0,1fr);gap:8px;align-items:center;color:#67df92}.recommendation-empty ha-icon{--mdc-icon-size:22px}.recommendation-empty b,.recommendation-empty span{display:block}.recommendation-empty b{font-size:10px}.recommendation-empty span{font-size:8px;line-height:11px;color:#84939e;margin-top:2px}.decision-card{margin-top:12px;padding:15px;border-radius:18px;background:rgba(255,255,255,.025);background:linear-gradient(145deg,color-mix(in srgb,var(--decision) 9%,transparent),rgba(255,255,255,.018));border:1px solid rgba(255,255,255,.10);border:1px solid color-mix(in srgb,var(--decision) 34%,transparent);box-shadow:inset 0 1px 0 rgba(255,255,255,.025)}.decision-kicker{display:flex;align-items:center;gap:7px;font-size:8px;font-weight:950;letter-spacing:.9px;color:var(--decision)}.decision-dot{width:7px;height:7px;border-radius:50%;background:var(--decision);box-shadow:0 0 12px rgba(91,212,255,.35);box-shadow:0 0 12px color-mix(in srgb,var(--decision) 75%,transparent)}.decision-main{display:grid;grid-template-columns:44px minmax(0,1fr);gap:11px;align-items:center;margin-top:10px}.decision-icon{width:44px;height:44px;border-radius:13px;display:flex;align-items:center;justify-content:center;color:var(--decision);background:rgba(255,255,255,.045);background:color-mix(in srgb,var(--decision) 12%,transparent);border:1px solid rgba(255,255,255,.10);border:1px solid color-mix(in srgb,var(--decision) 22%,transparent)}.decision-icon ha-icon{--mdc-icon-size:26px}.decision-main h2{font-size:18px;line-height:22px;margin:0;color:#f2f7fa}.decision-action{font-size:11px;line-height:15px;font-weight:900;color:var(--decision);margin-top:3px}.decision-rooms{display:flex;gap:5px;flex-wrap:wrap;margin-top:9px}.decision-rooms span{font-size:8.5px;font-weight:850;padding:4px 7px;border-radius:999px;background:rgba(255,255,255,.045);border:1px solid rgba(255,255,255,.075)}.decision-summary{font-size:10px;line-height:14px;color:#b7c3ca;margin:10px 0 0}.decision-impacts{display:grid;grid-template-columns:repeat(auto-fit,minmax(115px,1fr));gap:6px;margin-top:11px}.decision-impact{padding:8px;border-radius:11px;background:rgba(255,255,255,.028);border:1px solid rgba(255,255,255,.065);min-width:0}.decision-impact span{display:block;font-size:6.8px;font-weight:900;letter-spacing:.5px;color:#82929e}.decision-impact b{display:block;font-size:11px;line-height:14px;margin-top:3px;white-space:normal;overflow-wrap:anywhere;color:#e9f0f4}.night-context b{font-size:10.5px}.night-comparison{grid-column:1/-1}.night-comparison-grid{display:grid;grid-template-columns:minmax(0,1fr) auto minmax(0,1fr);gap:8px;align-items:center;margin-top:7px}.night-comparison-side{min-width:0;padding:7px;border-radius:9px;background:rgba(255,255,255,.025)}.night-comparison-side span{font-size:7px}.night-comparison-side b{font-size:12px;line-height:15px}.night-comparison-arrow{font-size:16px;color:var(--decision);font-weight:900}.night-comparison-benefit{margin-top:7px;font-size:9px;line-height:12px;font-weight:850;color:var(--decision)}.decision-compare{display:grid;grid-template-columns:1fr 24px 1fr;gap:6px;align-items:center;margin-top:10px;padding:9px;border-radius:12px;background:rgba(255,255,255,.025);border:1px solid rgba(255,255,255,.06);text-align:center}.decision-compare ha-icon{--mdc-icon-size:18px;color:#82929e}.decision-compare span,.decision-compare b{display:block}.decision-compare span{font-size:7px;color:#82929e;font-weight:900}.decision-compare b{font-size:11px;margin-top:2px}.decision-section-title{font-size:7px!important;font-weight:950!important;letter-spacing:.65px;color:#82929e!important;margin-bottom:4px}.decision-why{display:grid;gap:4px;margin-top:10px;padding-top:9px;border-top:1px solid rgba(255,255,255,.06)}.decision-why>div:not(.decision-section-title){display:grid;grid-template-columns:16px minmax(0,1fr);gap:5px;align-items:start}.decision-why ha-icon{--mdc-icon-size:14px;color:var(--decision);margin-top:1px}.decision-why span{font-size:9px;line-height:12px;color:#c2ccd2}.decision-alternative{font-size:8.5px;line-height:12px;color:#8797a2;margin-top:9px;padding:7px 8px;border-radius:9px;background:rgba(255,255,255,.022)}.decision-footer{display:flex;justify-content:space-between;gap:8px;margin-top:9px;font-size:7px;color:#647580}.decision-footer span:last-child{text-align:right}.metrics{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:7px;margin-top:11px}.active-metrics{grid-template-columns:repeat(6,minmax(0,1fr))}.metric,.mini,.summary,.history,.learn-panel{background:rgba(255,255,255,.026);border:1px solid rgba(255,255,255,.065)}.metric{padding:9px;border-radius:12px;min-width:0}.tiny{font-size:8px;line-height:10px;font-weight:900;letter-spacing:.7px;color:#82929e}.value{font-size:16px;font-weight:950;margin-top:3px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.muted{font-size:8.5px;line-height:11px;color:#84939e;font-weight:650;margin-top:2px}.actions{margin-top:9px;display:flex;gap:7px;flex-wrap:wrap}.details-btn,.close{appearance:none;border:1px solid rgba(255,255,255,.10);background:rgba(255,255,255,.04);color:inherit;border-radius:10px;padding:8px 11px;font:inherit;font-size:9px;font-weight:850;cursor:pointer}.modal{position:fixed;top:0;right:0;bottom:0;left:0;inset:0;z-index:9999;background:rgba(4,8,12,.72);-webkit-backdrop-filter:blur(8px);backdrop-filter:blur(8px);display:flex;align-items:flex-start;justify-content:center;padding:calc(env(safe-area-inset-top,0px) + 58px) 16px 16px;overflow:hidden}.dialog{width:calc(100vw - 28px);width:min(1240px,calc(100vw - 28px));margin:0 auto;height:calc(100vh - env(safe-area-inset-top,0px) - 74px);height:calc(100dvh - env(safe-area-inset-top,0px) - 74px);max-height:calc(100vh - env(safe-area-inset-top,0px) - 74px);max-height:calc(100dvh - env(safe-area-inset-top,0px) - 74px);display:flex;flex-direction:column;overflow:hidden;border-radius:22px;background:linear-gradient(145deg,#171f28,#10171e);border:1px solid rgba(91,212,255,.18);box-shadow:0 30px 80px rgba(0,0,0,.55)}.dialog-head{display:grid;grid-template-columns:42px minmax(0,1fr) 42px;align-items:center;gap:8px;position:relative;flex:0 0 auto;padding:12px 16px;min-height:62px;background:#151d25;border-bottom:1px solid rgba(255,255,255,.07);border-radius:22px 22px 0 0;z-index:30}.dialog-scroll{min-height:0;flex:1 1 0;overflow-y:auto;overflow-x:hidden;touch-action:pan-y pinch-zoom;-webkit-overflow-scrolling:touch;overscroll-behavior:contain;overscroll-behavior-y:contain;overflow-anchor:none;scroll-behavior:auto;padding:10px 16px 16px;background:linear-gradient(145deg,#171f28,#10171e)}.dialog-scroll{touch-action:pan-y pinch-zoom}.dialog-head-copy{min-width:0}.dialog-title{font-size:20px;font-weight:950}.dialog-back{appearance:none;width:42px;height:42px;display:flex;align-items:center;justify-content:center;border:1px solid rgba(255,255,255,.08);border-radius:11px;background:rgba(10,18,24,.78);color:#d9e2e8;cursor:pointer;justify-self:start}.dialog-back ha-icon{--mdc-icon-size:20px}.settings-gear{appearance:none;width:42px;height:42px;display:flex;align-items:center;justify-content:center;border:1px solid rgba(91,212,255,.16);border-radius:11px;background:rgba(91,212,255,.055);color:#86defb;cursor:pointer}.settings-gear ha-icon{--mdc-icon-size:20px}.close{font-size:18px;width:42px;height:42px;padding:0;display:flex;align-items:center;justify-content:center}.overview{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:8px}.summary{padding:11px;border-radius:13px}.summary strong{display:block;font-size:19px;margin-top:3px}.summary span{font-size:8px;color:#84939e}.history-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:8px;margin-top:8px}.history{padding:11px;border-radius:14px}.history-head{display:flex;justify-content:space-between;gap:10px}.history-head strong{color:#67df92}#ventlog-export{margin-left:auto}.support-contact{padding-left:16px;padding-right:16px}.support-contact .support-email{font-size:12px;line-height:1.45;color:var(--primary-text-color)}.chart{height:110px;margin:8px 0}.chart svg{width:100%;height:100%}.last-vent{display:grid;grid-template-columns:minmax(0,1fr) auto auto;gap:12px;align-items:center;margin-top:8px;padding:11px;border-radius:14px;background:rgba(255,255,255,.026);border:1px solid rgba(255,255,255,.065)}.last-vent b,.last-vent span{display:block}.last-vent span{font-size:8.5px;color:#84939e}.learn-panel{display:grid;grid-template-columns:1fr 2fr;gap:12px;padding:11px;border-radius:14px;margin-top:8px}.learn-status{display:grid;grid-template-columns:52px 1fr;gap:12px;align-items:center;text-align:center;padding:14px;border-radius:14px;margin-top:8px;background:rgba(255,255,255,.026);border:1px solid rgba(255,255,255,.065)}.learn-status ha-icon{--mdc-icon-size:34px;color:#67df92;justify-self:center}.learn-status strong{display:block;font-size:20px;color:#67df92;margin:2px 0}.learn-status span{display:block;font-size:10px;color:#a7b1b8;font-weight:700}.last-learning{display:grid;grid-template-columns:24px 1fr;gap:7px;align-items:center;margin-top:7px;padding:7px;border-radius:9px;border:1px solid rgba(255,255,255,.10);border:1px solid color-mix(in srgb,var(--learn) 35%,transparent);background:rgba(255,255,255,.025);background:color-mix(in srgb,var(--learn) 7%,transparent);color:var(--learn)}.last-learning ha-icon{--mdc-icon-size:17px}.last-learning b{font-size:8.5px;line-height:11px;display:block;margin-top:2px}.floor-title{display:none}.rooms-overview{padding:15px}.rooms-overview h3{font-size:18px;margin:4px 34px 2px 0}.rooms-subtitle{margin:0 0 12px!important;font-size:11px!important;color:#9aabb8!important}.rooms{display:grid;grid-template-columns:1fr;gap:10px}.room{padding:11px 12px;border-radius:15px;background:#172029;border:1px solid rgba(255,255,255,.10);color:#e9f0f4}.room-head{display:grid;grid-template-columns:44px minmax(0,1fr) auto 18px;gap:9px;align-items:center}.room-ident{min-width:0}.room-icon{width:44px;height:44px;border-radius:12px;display:flex;align-items:center;justify-content:center;color:var(--accent);background:var(--icon-bg)}.room-icon ha-icon{--mdc-icon-size:26px}.room-title{font-size:15px;font-weight:950;line-height:19px;color:#ffffff!important;text-shadow:0 1px 1px rgba(0,0,0,.35)}.room-head .muted{font-size:9.5px;line-height:12px;margin-top:2px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.room-water{display:flex;align-items:center;justify-content:flex-end;gap:6px;white-space:nowrap}.room-water ha-icon{--mdc-icon-size:23px;color:#379dff}.room-water strong{font-size:14px;font-weight:950}.room-chevron{--mdc-icon-size:20px;color:#8da2b2}.room-summary-grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:7px;margin-top:9px}.room-stat{display:grid;grid-template-columns:28px minmax(0,1fr);gap:7px;align-items:center;padding:8px 8px;border-radius:11px;min-width:0;background:rgba(255,255,255,.025);border:1px solid rgba(255,255,255,.07)}.room-stat .stat-icon{--mdc-icon-size:21px;color:#e9eff3}.room-stat .tiny{font-size:7.2px;line-height:9px;white-space:nowrap;letter-spacing:.45px}.room-stat .room-value{font-size:11.5px;font-weight:900;margin-top:2px;white-space:nowrap}.room-stat .muted{font-size:8px;line-height:10px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.learning-bars{color:#f0f3f5!important}.room-action{font-size:9px;font-weight:850;color:var(--accent)}.room-climate{margin-top:9px;padding:8px;border-radius:10px;background:rgba(255,255,255,.022);border:1px solid rgba(255,255,255,.055)}.room-main{display:grid;grid-template-columns:1fr auto;gap:8px;margin-top:8px}.right{text-align:right}.room-value{font-size:12px;font-weight:850;margin-top:2px}.room-big{font-size:17px;font-weight:950}.mini-grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:5px;margin-top:7px}.mini{padding:6px;border-radius:9px;min-width:0}.mini-value{font-size:11px;font-weight:900;margin-top:2px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.reason{display:grid;gap:2px;font-size:8.5px;line-height:11px;color:#95a2ab;margin-top:7px;min-height:22px}.reason span:before{content:"• ";color:var(--accent)}.clickable,.metric{cursor:pointer}.clickable:hover,.metric:hover{border-color:rgba(91,212,255,.25)}.info-panel{position:relative;margin:0 0 10px;padding:13px;border-radius:14px;background:rgba(72,188,230,.07);border:1px solid rgba(91,212,255,.18)}.info-panel h3{margin:4px 0 7px;font-size:16px}.info-panel p{margin:6px 0;font-size:10px;line-height:14px;color:#b4c0c8}.info-nav{position:sticky;top:0;z-index:30;display:grid;grid-template-columns:42px minmax(0,1fr) 42px;align-items:center;gap:10px;min-height:62px;padding:10px 12px;background:rgba(16,24,30,.96);-webkit-backdrop-filter:blur(12px);backdrop-filter:blur(12px);border-bottom:1px solid rgba(255,255,255,.07);border-radius:20px 20px 0 0}.info-nav-label{text-align:center;font-size:10px;font-weight:900;letter-spacing:1.1px;color:#8fa4b2;text-transform:uppercase;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.info-close{position:static;width:42px;height:42px;display:flex;align-items:center;justify-content:center;border:1px solid rgba(255,255,255,.08);border-radius:11px;background:rgba(10,18,24,.78);color:#d9e2e8;font-size:23px;line-height:1;cursor:pointer;z-index:3;-webkit-backdrop-filter:blur(8px);backdrop-filter:blur(8px);justify-self:end}.info-back{position:static;width:42px;height:42px;display:flex;align-items:center;justify-content:center;border:1px solid rgba(255,255,255,.08);border-radius:11px;background:rgba(10,18,24,.78);color:#d9e2e8;cursor:pointer;justify-self:start}.info-back ha-icon{--mdc-icon-size:20px}.info-kicker{padding-right:0}.room-iq-hero{display:grid;grid-template-columns:44px minmax(0,1fr) auto;gap:10px;align-items:center;margin:12px 0;padding:12px;border-radius:14px;border:1px solid color-mix(in srgb,var(--room-iq) 30%,transparent);background:color-mix(in srgb,var(--room-iq) 7%,transparent)}.room-iq-icon{width:44px;height:44px;border-radius:12px;display:flex;align-items:center;justify-content:center;background:color-mix(in srgb,var(--room-iq) 12%,transparent);color:var(--room-iq)}.room-iq-icon ha-icon{--mdc-icon-size:25px}.room-iq-hero strong,.room-iq-hero span{display:block}.room-iq-hero strong{font-size:15px;color:var(--room-iq)}.room-iq-hero span{font-size:9px;color:#aebbc4;margin-top:3px;line-height:13px}.room-iq-quality{padding:6px 8px;border-radius:999px;font-size:8px;font-weight:850;white-space:nowrap}.room-iq-quality.ok{color:#67df92;background:rgba(103,223,146,.08)}.room-iq-quality.warn{color:#ff9b7a;background:rgba(255,155,122,.08)}.room-iq-why{display:grid;gap:5px;margin:9px 0;padding:10px;border-radius:12px;background:rgba(255,255,255,.025)}.room-iq-why>div:not(.tiny){display:grid;grid-template-columns:18px 1fr;gap:6px;align-items:start;font-size:9px;line-height:13px;color:#bac5cc}.room-iq-why ha-icon{--mdc-icon-size:15px;color:#63d2f7}.room-iq-context{margin-top:10px;padding:10px;border-radius:12px;background:rgba(255,255,255,.025)}.room-iq-context span{display:block;margin-top:4px;font-size:9px;line-height:13px;color:#98a8b3}.info-grid{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:6px}.info-grid>div{padding:7px 8px;border-radius:10px;background:rgba(255,255,255,.025);min-height:0}.info-grid b,.info-grid span{display:block}.info-grid b{font-size:12px;line-height:15px}.info-grid span{font-size:7.5px;line-height:10px;color:#84939e;margin-top:2px}.dialog-scroll,.dialog-scroll *{touch-action:pan-y pinch-zoom}.measurement{font-size:7.5px;margin-top:6px;padding:4px 6px;border-radius:7px;border:1px solid transparent}.measure-ok{color:#7ea98c;background:rgba(75,150,95,.045);border-color:rgba(90,170,110,.10)}.measure-bad{color:#b77f7f;background:rgba(170,70,70,.045);border-color:rgba(190,80,80,.10)}.floor-room-group{margin-top:12px}.floor-room-group:first-child{margin-top:4px}.floor-room-heading{display:flex;align-items:center;gap:6px;padding:4px 3px 6px;color:#8fa4b2;font-size:9px;font-weight:900;letter-spacing:.7px;text-transform:uppercase}.floor-room-heading ha-icon{--mdc-icon-size:15px}.floor-room-content{display:grid;gap:5px}.rooms-overview .floor-room-content{gap:8px}.breakdown{display:grid;gap:5px;margin-top:9px}.breakdown-row{display:grid;grid-template-columns:minmax(0,1fr) auto 70px;gap:8px;align-items:center;padding:8px;border-radius:9px;background:rgba(255,255,255,.025)}.breakdown-row span{font-size:8px;color:#84939e}.breakdown-row strong{text-align:right}.room-detail{scroll-margin-top:70px}.dialog{min-height:min-content}.submodal{position:fixed;top:0;right:0;bottom:0;left:0;inset:0;z-index:10010;background:rgba(4,9,13,.74);display:flex;align-items:flex-start;justify-content:center;padding:calc(env(safe-area-inset-top,0px) + 58px) 16px 16px;box-sizing:border-box;overflow:hidden}.subdialog{color:#e9f0f4;--primary-text-color:#e9f0f4;--secondary-text-color:#84939e;width:100%;width:min(920px,100%);min-height:0;height:calc(100vh - env(safe-area-inset-top,0px) - 76px);height:calc(100dvh - env(safe-area-inset-top,0px) - 76px);max-height:calc(100vh - env(safe-area-inset-top,0px) - 76px);max-height:calc(100dvh - env(safe-area-inset-top,0px) - 76px);overflow-y:auto;overflow-x:hidden;touch-action:pan-y pinch-zoom;-webkit-overflow-scrolling:touch;overscroll-behavior:contain;overscroll-behavior-y:contain;overflow-anchor:none;scroll-behavior:auto;scrollbar-gutter:stable;border-radius:20px;background:linear-gradient(145deg,#171f28,#10171e);border:1px solid rgba(91,212,255,.18);box-shadow:0 20px 80px rgba(0,0,0,.55)}.subdialog .info-panel{margin:0;border:0}.profile-options{display:grid;gap:9px;padding:0 14px 16px}.profile-option{text-align:left;border:1px solid rgba(255,255,255,.12);border-radius:14px;background:rgba(255,255,255,.04);padding:12px;color:inherit}.profile-option.selected{border-color:#67df92}.profile-option span{display:block;margin-top:4px;color:var(--secondary-text-color)}

      .brand-subtitle{font-size:9px;letter-spacing:1.6px;font-weight:800;color:#7e919f;margin-top:1px}.ai-top{padding-bottom:2px}.top.profile-only{display:flex;justify-content:flex-end;min-height:0}.top.profile-only .pill{justify-self:auto}.ai-card{position:relative;overflow:hidden;background:linear-gradient(145deg,rgba(19,32,40,.98),rgba(8,16,22,.98))}.ai-card:before{content:"";position:absolute;top:0;right:0;bottom:0;left:0;inset:0;pointer-events:none;background:radial-gradient(circle at 85% 0%,rgba(91,212,255,.08),transparent 36%);background:radial-gradient(circle at 85% 0%,color-mix(in srgb,var(--decision) 14%,transparent),transparent 36%)}.context-impacts{position:relative}.decision-impact small{display:block;margin-top:3px;font-size:9px;color:var(--secondary-text-color);font-weight:500;line-height:1.25}.decision-impact.clickable{cursor:pointer;border-color:rgba(91,212,255,.20)}.decision-impact.clickable:after{content:"›";position:absolute;right:7px;top:6px;color:#6f8797;font-size:13px}.decision-impact{position:relative}.decision-impact.forecast{cursor:pointer;border-color:rgba(91,212,255,.22);border-color:color-mix(in srgb,var(--decision) 45%,rgba(255,255,255,.10))}.iq-process{margin-top:12px;padding:10px 11px;border:1px solid rgba(106,215,255,.14);border-radius:13px;background:rgba(68,178,219,.045)}.iq-process-head{display:grid;grid-template-columns:auto auto 1fr;gap:7px;align-items:center;font-size:9px;letter-spacing:.7px;color:#85dfff}.iq-process-head>span:last-child{text-align:right;color:var(--secondary-text-color);letter-spacing:0}.iq-pulse{width:7px;height:7px;border-radius:50%;background:#67df92;box-shadow:0 0 0 0 rgba(103,223,146,.5);animation:iqpulse 2s infinite}.iq-process-text{font-size:10px;color:var(--secondary-text-color);margin-top:5px;line-height:1.4}@keyframes iqpulse{0%{box-shadow:0 0 0 0 rgba(103,223,146,.45)}70%{box-shadow:0 0 0 7px rgba(103,223,146,0)}100%{box-shadow:0 0 0 0 rgba(103,223,146,0)}}.compact-actions{margin-top:7px;padding-top:7px;border-top:1px solid rgba(255,255,255,.055);justify-content:flex-start}.compact-actions .details-btn{min-height:30px;padding:6px 12px;font-size:10px;opacity:.82}.iq-variant .brand,.iq-variant .details-btn,.iq-variant .decision-room-disclosure>summary,.iq-variant .decision-room-disclosure>summary span{color:#e9f1f5}.detail-quick{display:flex;align-items:center;justify-content:space-between;gap:12px;padding:12px 14px;margin:4px 0 12px;border:1px solid rgba(99,210,247,.14);border-radius:15px;background:rgba(99,210,247,.045)}.detail-quick b,.detail-quick span{display:block}.detail-quick span{font-size:10px;color:var(--secondary-text-color);margin-top:2px}.quick-forecast{display:grid;grid-template-columns:auto auto;gap:2px 6px;align-items:center;border:1px solid rgba(99,210,247,.22);border-radius:12px;background:rgba(99,210,247,.08);color:inherit;padding:8px 10px;cursor:pointer}.quick-forecast ha-icon{grid-row:1/3;--mdc-icon-size:19px;color:#63d2f7}.quick-forecast b{font-size:13px}.quick-forecast span{font-size:8px;margin:0;text-align:left}.last-vent-tile{--result:#63d2f7;display:grid;grid-template-columns:42px minmax(0,1fr) 22px;gap:10px;align-items:center;margin-top:12px;padding:12px 13px;border-radius:15px;border:1px solid color-mix(in srgb,var(--result) 22%,rgba(255,255,255,.08));background:color-mix(in srgb,var(--result) 5%,rgba(255,255,255,.018));cursor:pointer}.last-vent-tile-icon{width:42px;height:42px;border-radius:12px;display:flex;align-items:center;justify-content:center;color:var(--result);background:color-mix(in srgb,var(--result) 10%,transparent);border:1px solid color-mix(in srgb,var(--result) 18%,transparent)}.last-vent-tile-icon ha-icon{--mdc-icon-size:23px}.last-vent-tile b,.last-vent-tile span{display:block}.last-vent-tile b{font-size:11px;margin-top:2px}.last-vent-tile span{font-size:8px;line-height:11px;color:#82929e;margin-top:2px}.last-vent-tile-chevron{--mdc-icon-size:20px;color:var(--result);justify-self:end}.vent-result{margin-top:12px;padding:14px;border-radius:18px;border:1px solid color-mix(in srgb,var(--result) 32%,rgba(255,255,255,.10));background:linear-gradient(145deg,color-mix(in srgb,var(--result) 8%,rgba(255,255,255,.018)),rgba(255,255,255,.015))}.vent-result-hero{box-shadow:0 0 0 1px color-mix(in srgb,var(--result) 8%,transparent),0 12px 35px rgba(0,0,0,.16)}.result-head{display:grid;grid-template-columns:42px minmax(0,1fr) auto;gap:10px;align-items:center}.result-icon{width:42px;height:42px;border-radius:13px;display:flex;align-items:center;justify-content:center;color:var(--result);background:color-mix(in srgb,var(--result) 12%,transparent);border:1px solid color-mix(in srgb,var(--result) 22%,transparent)}.result-icon ha-icon{--mdc-icon-size:25px}.result-head h3{font-size:15px;line-height:19px;margin:2px 0 0}.result-head span{font-size:8.5px;color:var(--secondary-text-color)}.result-countdown{justify-self:end;padding:5px 8px;border-radius:999px;border:1px solid color-mix(in srgb,var(--result) 25%,transparent);background:color-mix(in srgb,var(--result) 8%,transparent);color:var(--result)!important;font-weight:850;white-space:nowrap}.result-metrics{display:grid;grid-template-columns:repeat(auto-fit,minmax(105px,1fr));gap:6px;margin-top:11px}.result-metrics>div{padding:9px;border-radius:11px;background:rgba(255,255,255,.028);border:1px solid rgba(255,255,255,.07)}.result-metrics span,.result-metrics b,.result-metrics small{display:block}.result-metrics span{font-size:7px;letter-spacing:.5px;color:#82929e}.result-metrics b{font-size:12px;margin-top:2px}.result-metrics small{font-size:7.5px;color:#82929e;margin-top:1px}.result-iq{display:grid;grid-template-columns:27px minmax(0,1fr);gap:8px;margin-top:9px;padding:9px;border-radius:11px;background:rgba(91,212,255,.04);border:1px solid rgba(91,212,255,.12)}.result-iq ha-icon{--mdc-icon-size:20px;color:#63d2f7}.result-iq b,.result-iq span{display:block}.result-iq b{font-size:9.5px}.result-iq span{font-size:8px;line-height:11px;color:#8fa0ac;margin-top:2px}.result-rooms{display:grid;gap:5px;margin-top:9px}.result-room{display:grid;grid-template-columns:minmax(0,1fr) auto;gap:9px;align-items:center;padding:8px 9px;border-radius:10px;background:rgba(255,255,255,.025);border:1px solid rgba(255,255,255,.055)}.result-room b,.result-room span{display:block}.result-room b{font-size:9.5px}.result-room span{font-size:7.5px;line-height:10px;color:#84939e;margin-top:2px}.result-room strong{font-size:10px;white-space:nowrap}.result-footer{display:flex;justify-content:space-between;gap:10px;align-items:center;margin-top:8px;font-size:7.5px;color:#82929e}.result-footer b{font-size:8.5px;color:var(--result);white-space:nowrap}.result-complete{font-size:7.5px;color:#718490;white-space:nowrap}.metrics{display:none!important}
      @media(max-width:900px){.metrics{grid-template-columns:repeat(3,minmax(0,1fr))}.rooms{grid-template-columns:1fr}.overview{grid-template-columns:repeat(2,minmax(0,1fr))}}@media(max-width:650px){.decision-impacts{grid-template-columns:repeat(auto-fit,minmax(120px,1fr))}.decision-footer{display:grid;gap:3px}.decision-footer span:last-child{text-align:left}.metrics{grid-template-columns:repeat(2,minmax(0,1fr))}.history-grid,.learn-panel{grid-template-columns:1fr}.info-grid{grid-template-columns:repeat(2,minmax(0,1fr));gap:5px}.info-grid>div{padding:7px}.info-grid b{font-size:11px;line-height:14px}.info-grid span{font-size:7.2px;line-height:9.5px}.result-head{grid-template-columns:38px minmax(0,1fr)}.result-countdown{grid-column:2;justify-self:start}.result-metrics{grid-template-columns:repeat(auto-fit,minmax(105px,1fr))}.rooms-overview{padding:13px}.rooms-overview h3{font-size:17px}.rooms-subtitle{font-size:10px!important;margin-bottom:10px!important}.room{padding:10px}.room-head{grid-template-columns:42px minmax(0,1fr) auto 16px;gap:7px}.room-icon{width:42px;height:42px}.room-title{font-size:14px}.room-head .muted{font-size:8.5px}.room-water{gap:4px}.room-water strong{font-size:12.5px}.room-water ha-icon{--mdc-icon-size:20px}.room-chevron{--mdc-icon-size:18px}.room-summary-grid{grid-template-columns:repeat(3,minmax(0,1fr));gap:5px;margin-top:8px}.room-stat{grid-template-columns:22px minmax(0,1fr);gap:5px;padding:7px 5px}.room-stat .stat-icon{--mdc-icon-size:18px}.room-stat .tiny{font-size:6.5px;letter-spacing:.3px}.room-stat .room-value{font-size:10px}.room-stat .muted{font-size:7px}.top{grid-template-columns:44px minmax(0,1fr) auto}.pill{justify-self:end}.room-iq-hero{grid-template-columns:38px minmax(0,1fr)}.room-iq-quality{grid-column:2;justify-self:start}.info-close{width:42px;height:42px}.info-back{width:42px;height:42px}.modal{padding:calc(env(safe-area-inset-top,0px) + 58px) 7px 12px}.dialog{--dialog-pad:12px;width:100%;max-height:calc(100vh - env(safe-area-inset-top,0px) - 70px);max-height:calc(100dvh - env(safe-area-inset-top,0px) - 70px)}}
    .breakdown-row.vent-active{background:rgba(80,220,150,.10)!important;border:1px solid rgba(80,220,150,.26)!important;box-shadow:inset 3px 0 0 rgba(80,220,150,.75)}.vent-passive{background:rgba(91,212,255,.07)!important;border:1px solid rgba(91,212,255,.20)!important;box-shadow:inset 3px 0 0 rgba(91,212,255,.65)}.breakdown-row.vent-passive b,.breakdown-row.vent-passive span{color:#dff6ff}.breakdown-row.vent-inactive{opacity:.58}.breakdown-row b{display:flex;align-items:center;gap:8px}.breakdown-row b ha-icon{--mdc-icon-size:19px}.breakdown-row.vent-active b,.breakdown-row.vent-active span{color:#dff8e8}.house-live{display:grid;grid-template-columns:minmax(0,1fr) auto;gap:6px 12px;align-items:center;margin:12px 0;padding:12px;border-radius:14px;background:rgba(91,212,255,.07);border:1px solid rgba(91,212,255,.18)}.house-live b,.house-live span{display:block}.monitor-only-detail .room-iq-hero{grid-template-columns:54px minmax(0,1fr) auto}.monitor-only-grid{grid-template-columns:repeat(2,minmax(0,1fr))}.monitor-only-empty{display:grid;grid-template-columns:28px minmax(0,1fr);gap:9px;align-items:center;margin-top:10px;padding:11px;border-radius:12px;background:rgba(255,255,255,.025);border:1px solid rgba(255,255,255,.06)}.monitor-only-empty>ha-icon{--mdc-icon-size:22px;color:#82929e}.monitor-only-empty b,.monitor-only-empty span{display:block}.monitor-only-empty b{font-size:10px}.monitor-only-empty span{font-size:8px;line-height:11px;color:#8fa1ad;margin-top:2px}.house-live>span{grid-column:1/-1;color:#8fa4b1;font-size:8.5px}.settings-panel{padding:14px!important;background:linear-gradient(145deg,rgba(35,57,72,.50),rgba(16,24,30,.98))!important}.settings-hero{display:grid;grid-template-columns:48px minmax(0,1fr);gap:12px;align-items:start;margin-bottom:13px}.settings-hero-icon{width:48px;height:48px;border-radius:14px;display:flex;align-items:center;justify-content:center;background:rgba(91,212,255,.10);color:#63d2f7;border:1px solid rgba(91,212,255,.18)}.settings-hero-icon ha-icon{--mdc-icon-size:27px}.settings-hero h3{margin:2px 0 3px}.settings-category-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:8px}.settings-category{appearance:none;display:grid;grid-template-columns:38px minmax(0,1fr) 20px;gap:10px;align-items:center;text-align:left;padding:11px;border-radius:13px;border:1px solid rgba(255,255,255,.08);background:rgba(255,255,255,.026);color:inherit;cursor:pointer}.settings-category>ha-icon:first-child{--mdc-icon-size:23px;color:#63d2f7}.settings-category b,.settings-category span{display:block}.settings-category b{font-size:11px}.settings-category span{font-size:8.5px;line-height:12px;color:#8fa1ad;margin-top:2px}.settings-category.resident-feature{border-color:rgba(91,212,255,.20);background:linear-gradient(135deg,rgba(91,212,255,.075),rgba(138,107,255,.035));box-shadow:inset 0 1px 0 rgba(255,255,255,.035)}.resident-feature-badge{display:block;width:max-content;margin-bottom:3px;color:#76dbff;font-size:6px;line-height:8px;font-weight:950;letter-spacing:.55px}.resident-profile-spotlight{appearance:none;width:100%;display:grid;grid-template-columns:56px minmax(0,1fr);gap:12px;align-items:center;text-align:left;margin:10px 0 12px;padding:14px;border-radius:17px;border:1px solid rgba(91,212,255,.24);background:radial-gradient(circle at 8% 20%,rgba(91,212,255,.18),transparent 38%),linear-gradient(135deg,rgba(91,212,255,.08),rgba(138,107,255,.07));color:inherit;box-shadow:inset 0 1px 0 rgba(255,255,255,.05),0 8px 26px rgba(0,0,0,.12);cursor:pointer}.resident-profile-spotlight-icon{position:relative;width:54px;height:54px;border-radius:17px;display:flex;align-items:center;justify-content:center;background:rgba(91,212,255,.11);border:1px solid rgba(91,212,255,.23);color:#73dcff}.resident-profile-spotlight-icon>ha-icon:first-child{--mdc-icon-size:29px}.resident-profile-spotlight-brain{position:absolute;right:-4px;bottom:-4px;--mdc-icon-size:18px;padding:4px;border-radius:9px;background:#17242d;color:#8b7cff;border:1px solid rgba(138,107,255,.28)}.resident-profile-spotlight h4{margin:2px 0 4px;font-size:14px}.resident-profile-spotlight p{margin:0;color:#9eafb9;font-size:8.5px;line-height:12px}.resident-profile-spotlight-link{display:flex!important;align-items:center;gap:4px;margin-top:8px!important;color:#74dcff!important;font-size:8px!important;font-weight:900}.resident-profile-spotlight-link ha-icon{--mdc-icon-size:14px}.settings-chevron{--mdc-icon-size:18px;color:#718490}.settings-group{margin-top:10px;border:1px solid rgba(255,255,255,.075);border-radius:14px;overflow:hidden;background:rgba(255,255,255,.016)}.settings-group-head{padding:10px 11px;background:rgba(91,212,255,.035);border-bottom:1px solid rgba(255,255,255,.055)}.settings-group-head span{display:block;font-size:8.5px;line-height:12px;color:#91a2ad;margin-top:3px}.settings-field{display:grid;grid-template-columns:minmax(0,1fr) minmax(190px,42%);gap:14px;align-items:center;padding:11px;border-top:1px solid rgba(255,255,255,.052)}.settings-group .settings-field:first-of-type{border-top:0}.settings-field-copy b,.settings-field-copy span,.settings-field-copy small{display:block}.settings-field-copy b{font-size:10.5px}.settings-field-copy span{font-size:8.5px;line-height:12px;color:#a6b4bd;margin-top:3px}.settings-field-copy small{font-size:7.5px;line-height:11px;color:#6f828f;margin-top:4px}.settings-control{min-width:0}.settings-input-wrap{display:flex;align-items:center;gap:7px}.settings-input-wrap>span{font-size:8px;color:#81939f;white-space:nowrap}.settings-input{width:100%;min-height:38px;padding:8px 9px;border-radius:10px;border:1px solid rgba(255,255,255,.12);background:#0f181f;color:#eaf1f5;font:inherit;font-size:9px;outline:none}.settings-input:focus{border-color:rgba(91,212,255,.55);box-shadow:0 0 0 2px rgba(91,212,255,.08)}.settings-textarea{resize:vertical;line-height:14px}.settings-multi{min-height:92px}.settings-checklist{display:grid;gap:5px;max-height:190px;overflow:auto;padding:7px;border-radius:10px;border:1px solid rgba(255,255,255,.12);background:#0f181f}.settings-check-option{display:flex;align-items:center;gap:8px;min-height:28px;padding:4px 6px;border-radius:7px;background:rgba(255,255,255,.025);font-size:8.5px}.settings-check-option input{width:16px;height:16px;flex:0 0 auto;accent-color:#63d2f7}.settings-check-option span{min-width:0;overflow-wrap:anywhere}.settings-switch{position:relative;display:inline-flex;justify-self:end;width:44px;height:24px}.settings-switch input{opacity:0;width:0;height:0}.settings-switch span{position:absolute;inset:0;border-radius:999px;background:#35424b;border:1px solid rgba(255,255,255,.10);transition:.18s}.settings-switch span:after{content:"";position:absolute;width:18px;height:18px;left:2px;top:2px;border-radius:50%;background:#dbe4e9;transition:.18s}.settings-switch input:checked+span{background:rgba(91,212,255,.28);border-color:rgba(91,212,255,.45)}.settings-switch input:checked+span:after{transform:translateX(20px);background:#70dafa}.settings-field-stack{grid-template-columns:1fr;align-items:stretch}.resident-profile-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:8px;padding:10px}.resident-profile-card{position:relative;overflow:hidden;padding:12px;border-radius:16px;border:1px solid rgba(91,212,255,.20);background:linear-gradient(145deg,rgba(91,212,255,.075),rgba(138,107,255,.035) 48%,rgba(255,255,255,.018));box-shadow:inset 0 1px 0 rgba(255,255,255,.045),0 8px 24px rgba(0,0,0,.12)}.resident-profile-glow{position:absolute;right:-34px;top:-42px;width:120px;height:120px;border-radius:50%;background:radial-gradient(circle,rgba(91,212,255,.13),transparent 68%);pointer-events:none}.resident-profile-badge{position:relative;display:flex;align-items:center;gap:5px;width:max-content;padding:4px 7px;border-radius:999px;background:rgba(91,212,255,.075);border:1px solid rgba(91,212,255,.15);color:#78dcff;font-size:6.7px;font-weight:950;letter-spacing:.55px;margin-bottom:9px}.resident-profile-badge ha-icon{--mdc-icon-size:12px}.resident-profile-head{position:relative;display:grid;grid-template-columns:38px minmax(0,1fr) 26px;gap:9px;align-items:center;margin-bottom:10px}.resident-avatar{width:38px;height:38px;border-radius:12px;display:flex;align-items:center;justify-content:center;background:linear-gradient(145deg,rgba(91,212,255,.16),rgba(138,107,255,.09));color:#74ddff;border:1px solid rgba(91,212,255,.24);box-shadow:inset 0 1px 0 rgba(255,255,255,.05)}.resident-profile-spark{--mdc-icon-size:18px;color:#70d9fb;opacity:.72;justify-self:end}.resident-avatar ha-icon{--mdc-icon-size:19px}.resident-profile-head b,.resident-profile-head span{display:block}.resident-profile-head b{font-size:10px}.resident-profile-head span{font-size:7.5px;color:#8395a0;margin-top:2px;overflow:hidden;text-overflow:ellipsis}.resident-profile-card label{display:block;margin-top:8px}.resident-profile-card label>span{display:block;font-size:7.5px;color:#8fa1ad;margin-bottom:4px}.settings-save,.settings-delete,.settings-danger button,.settings-error button{appearance:none;border:1px solid rgba(91,212,255,.22);border-radius:11px;background:rgba(91,212,255,.08);color:#dff6ff;padding:9px 11px;font:inherit;font-size:9px;font-weight:850;cursor:pointer;display:flex;align-items:center;justify-content:center;gap:6px}.settings-save ha-icon,.settings-delete ha-icon{--mdc-icon-size:17px}.settings-delete,.settings-danger button{border-color:rgba(255,119,112,.23);background:rgba(255,119,112,.07);color:#ffaaa5}.settings-toast{position:sticky;top:63px;z-index:35;width:max-content;max-width:calc(100% - 24px);margin:8px auto -2px;padding:6px 10px;border-radius:999px;background:#19382d;color:#78e8a1;border:1px solid rgba(103,223,146,.23);font-size:8.5px;font-weight:850}.settings-inline-error{display:flex;align-items:center;gap:7px;margin:9px 12px;padding:8px 10px;border-radius:10px;background:rgba(255,119,112,.09);color:#ffaaa5;border:1px solid rgba(255,119,112,.20);font-size:8.5px}.settings-inline-error ha-icon{--mdc-icon-size:17px}.settings-loading{display:flex;align-items:center;justify-content:center;gap:9px;min-height:140px;color:#9fb0ba}.settings-error{display:grid;grid-template-columns:30px minmax(0,1fr);gap:9px;align-items:center;padding:12px}.settings-error>ha-icon{color:#ff7770}.settings-error b,.settings-error span{display:block}.settings-error span{font-size:8.5px;color:#a6b4bd;margin-top:3px}.settings-error button{grid-column:2;justify-self:start}.settings-room-list{display:grid;gap:7px;margin-top:12px}.settings-room-row{display:grid;grid-template-columns:minmax(0,1fr) auto;gap:7px}.settings-room-main{appearance:none;display:grid;grid-template-columns:30px minmax(0,1fr) 18px;gap:9px;align-items:center;text-align:left;padding:10px;border-radius:12px;border:1px solid rgba(255,255,255,.08);background:rgba(255,255,255,.026);color:inherit;cursor:pointer}.settings-room-main b,.settings-room-main span{display:block}.settings-room-main b{font-size:10.5px}.settings-room-main span{font-size:8px;color:#8799a5;margin-top:2px}.settings-room-index{width:28px;height:28px;border-radius:9px;display:flex!important;align-items:center;justify-content:center;background:rgba(91,212,255,.08);color:#63d2f7!important;font-weight:900}.settings-room-order{display:grid;grid-template-columns:34px 34px;gap:4px}.settings-room-order button{appearance:none;border:1px solid rgba(255,255,255,.08);border-radius:9px;background:rgba(255,255,255,.03);color:#b9c6cd}.settings-room-order button:disabled{opacity:.25}.settings-room-order ha-icon{--mdc-icon-size:17px}.settings-add-room{margin-top:10px;width:100%}.settings-empty{padding:14px;text-align:center;font-size:9px;color:#82929e}.settings-dim-grid{display:grid;grid-template-columns:repeat(3,1fr);gap:7px;padding:11px;border-top:1px solid rgba(255,255,255,.052)}.settings-dim-grid label{font-size:8px;color:#81939f}.settings-dim-grid input{margin-top:4px}.settings-contact-box{padding:11px;border-top:1px solid rgba(255,255,255,.052)}.settings-contact-row{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:8px;align-items:end;margin-top:10px;padding:10px;border-radius:12px;background:rgba(255,255,255,.022);border:1px solid rgba(255,255,255,.055)}.settings-contact-title{grid-column:1/-1}.settings-contact-row label>span{display:block;margin:0 0 4px;font-size:7.5px;color:#81939f}.settings-contact-help{grid-column:1/-1;font-size:7.2px;line-height:10px;color:#718490}.settings-contact-row b,.settings-contact-row span{display:block}.settings-contact-row b{font-size:9px}.settings-contact-row span{font-size:7.5px;color:#718490;margin-top:2px;overflow:hidden;text-overflow:ellipsis}.settings-room-actions{display:flex;gap:8px;padding:11px;border-top:1px solid rgba(255,255,255,.052)}.settings-danger-grid{display:grid;gap:9px;margin-top:12px}.settings-danger{display:grid;grid-template-columns:36px minmax(0,1fr) auto;gap:10px;align-items:center;padding:11px;border-radius:12px;border:1px solid rgba(255,255,255,.08);background:rgba(255,255,255,.025)}.settings-danger>ha-icon{color:#e7b86a}.settings-danger b,.settings-danger span{display:block}.settings-danger b{font-size:10px}.settings-danger span{font-size:8px;line-height:11px;color:#8fa1ad;margin-top:2px}@media(max-width:700px){.resident-profile-grid{grid-template-columns:1fr}.settings-category-grid{grid-template-columns:1fr}.settings-field{grid-template-columns:1fr;gap:8px}.settings-switch{justify-self:start}.settings-contact-row{grid-template-columns:1fr}.settings-danger{grid-template-columns:30px minmax(0,1fr)}.settings-danger button{grid-column:1/-1}.settings-room-row{grid-template-columns:1fr}.settings-room-order{grid-template-columns:1fr 1fr}.settings-dim-grid{grid-template-columns:1fr}.dialog-head{grid-template-columns:42px minmax(0,1fr) 42px}.dialog-title{font-size:16px}}.learning-overview-card{margin-top:8px;padding:13px;border-radius:18px;background:linear-gradient(145deg,rgba(91,212,255,.065),rgba(255,255,255,.018));border:1px solid rgba(91,212,255,.18);box-shadow:inset 0 1px 0 rgba(255,255,255,.035)}.learning-overview-hero{display:grid;grid-template-columns:66px minmax(0,1fr);gap:13px;align-items:center}.learning-overview-copy h2{margin:3px 0 4px;font-size:17px}.learning-overview-copy p{margin:0;color:#9fb1bc;font-size:8.5px;line-height:12px}.learning-overview-title{display:flex;align-items:center;justify-content:space-between;gap:8px}.learning-overview-title span{font-size:7px;font-weight:900;color:#67df92;border:1px solid rgba(103,223,146,.3);background:rgba(103,223,146,.08);border-radius:999px;padding:4px 7px;white-space:nowrap}.learning-kpis{display:grid;grid-template-columns:1fr 1fr;gap:8px;margin-top:12px}.learning-kpis>div{padding:10px;border-radius:13px;background:rgba(255,255,255,.025);border:1px solid rgba(91,212,255,.12)}.learning-kpis span,.learning-kpis b{display:flex;align-items:center;gap:5px}.learning-kpis span{font-size:8px;font-weight:800;color:#a7b7c1}.learning-kpis span ha-icon{--mdc-icon-size:14px;color:#63d2f7}.learning-kpis b{font-size:18px;margin:5px 0}.learning-kpis i,.learning-area-score i,.learning-detail-progress i,.season-card i,.season-total i,.night-grid i{display:block;height:5px;border-radius:999px;background:rgba(255,255,255,.07);overflow:hidden}.learning-kpis em,.learning-area-score em,.learning-detail-progress em,.season-card em,.season-total em,.night-grid em{display:block;height:100%;border-radius:inherit;background:#63d2f7}.learning-now{width:100%;display:grid;grid-template-columns:28px minmax(0,1fr) 18px;gap:8px;align-items:center;text-align:left;margin-top:10px;padding:10px;border-radius:12px;border:1px solid rgba(91,212,255,.2);background:rgba(91,212,255,.045);color:inherit}.learning-now>ha-icon:first-child{color:#e8d765}.learning-now b,.learning-now small{display:block}.learning-now b{font-size:9px}.learning-now small{font-size:7.5px;color:#63d2f7;margin-top:2px}.learning-area-head{margin:13px 2px 7px}.learning-area-head b,.learning-area-head span{display:block}.learning-area-head b{font-size:12px}.learning-area-head span{font-size:7.5px;color:#8296a2;margin-top:2px}.learning-area-list{display:grid;gap:7px}.learning-area{appearance:none;width:100%;display:grid;grid-template-columns:38px minmax(0,1fr) 72px 16px;gap:9px;align-items:center;text-align:left;padding:9px;border-radius:13px;background:rgba(255,255,255,.024);border:1px solid rgba(255,255,255,.065);color:inherit}.learning-area-icon{width:36px;height:36px;border-radius:11px;display:flex;align-items:center;justify-content:center;background:rgba(91,212,255,.08);border:1px solid rgba(91,212,255,.15);color:#63d2f7}.learning-area-icon ha-icon{--mdc-icon-size:20px}.learning-area-copy b,.learning-area-copy small{display:block}.learning-area-copy b{font-size:9.5px}.learning-area-copy small{font-size:7px;color:#8296a2;margin-top:3px}.learning-area-score b{display:block;text-align:right;font-size:9px;margin-bottom:5px}.learning-area-chevron{--mdc-icon-size:17px;color:#63d2f7}.learning-overview-note{display:grid;grid-template-columns:18px minmax(0,1fr);gap:7px;align-items:start;margin-top:10px;padding:9px;border-radius:11px;background:rgba(91,212,255,.035);border:1px solid rgba(91,212,255,.1);color:#8296a2}.learning-overview-note ha-icon{--mdc-icon-size:16px;color:#63d2f7}.learning-overview-note span{font-size:7.3px;line-height:10px}.learning-detail-panel{padding-bottom:16px}.learning-group-hero,.longterm-hero{display:grid;grid-template-columns:48px minmax(0,1fr) auto;gap:10px;align-items:center;margin:10px 0 12px;padding:12px;border-radius:15px;background:rgba(91,212,255,.045);border:1px solid rgba(91,212,255,.14)}.learning-group-hero>ha-icon,.longterm-hero>ha-icon{--mdc-icon-size:28px;color:#63d2f7}.learning-group-hero h3{margin:0}.learning-group-hero p,.longterm-hero span{margin:2px 0 0;font-size:7.5px;color:#8ea1ad}.learning-group-hero strong{font-size:16px}.learning-detail-list{display:grid;gap:8px}.learning-detail-card{display:grid;grid-template-columns:38px minmax(0,1fr);gap:9px;padding:10px;border-radius:13px;background:rgba(255,255,255,.024);border:1px solid rgba(255,255,255,.06)}.learning-detail-icon{width:36px;height:36px;border-radius:11px;display:flex;align-items:center;justify-content:center;background:rgba(91,212,255,.08);color:#63d2f7}.learning-detail-icon ha-icon{--mdc-icon-size:20px}.learning-detail-head{display:flex;justify-content:space-between;gap:8px}.learning-detail-head b{font-size:9.5px}.learning-detail-head strong{font-size:7px;color:#67df92}.learning-detail-card p{font-size:7.3px;line-height:10px;color:#8fa1ad;margin:3px 0 7px}.learning-detail-card small{display:block;font-size:6.8px;color:#788c98;margin-top:4px}.learning-detail-progress{display:grid;grid-template-columns:minmax(0,1fr) auto;gap:8px;align-items:center}.learning-detail-progress b{font-size:7px}.learning-quality-grid{display:grid;grid-template-columns:1fr 1fr;gap:7px;margin:10px 0}.learning-quality-grid>div{padding:10px;border-radius:12px;background:rgba(255,255,255,.025);border:1px solid rgba(255,255,255,.06)}.learning-quality-grid span,.learning-quality-grid b{display:block}.learning-quality-grid span{font-size:7px;color:#8296a2}.learning-quality-grid b{font-size:16px;margin-top:3px}.learning-section-title{display:flex;justify-content:space-between;gap:8px;align-items:center;margin:13px 2px 7px}.learning-section-title b{font-size:11px}.learning-section-title span{font-size:7px;color:#63d2f7}.season-grid{display:grid;grid-template-columns:1fr 1fr;gap:7px}.season-card{display:grid;gap:5px;padding:10px;border-radius:13px;background:rgba(255,255,255,.024);border:1px solid rgba(255,255,255,.06)}.season-card>ha-icon{--mdc-icon-size:20px;color:#e7bd58}.season-card b{font-size:9px}.season-card strong{font-size:8px}.season-card small{font-size:6.8px;color:#8296a2}.season-card.done{border-color:rgba(103,223,146,.22)}.season-card.done>ha-icon{color:#67df92}.season-total{padding:10px;margin-top:8px;border-radius:13px;background:rgba(91,212,255,.035);border:1px solid rgba(91,212,255,.13)}.season-total span,.season-total b{display:block}.season-total span{font-size:7px;color:#8296a2}.season-total b{font-size:9px;margin:3px 0 7px}.night-grid{display:grid;grid-template-columns:1fr 1fr;gap:7px}.night-grid>div{padding:11px;border-radius:13px;background:rgba(255,255,255,.024);border:1px solid rgba(255,255,255,.06)}.night-grid strong,.night-grid b,.night-grid small{display:block}.night-grid strong{font-size:18px}.night-grid b{font-size:8px;margin:3px 0 7px}.night-grid small{font-size:6.8px;line-height:9px;color:#8296a2}.learning-empty{padding:12px;color:#8296a2;font-size:8px}@media(max-width:650px){.learning-overview-title{align-items:flex-start;flex-direction:column}.learning-area{grid-template-columns:36px minmax(0,1fr) 62px 14px}.season-grid,.night-grid{grid-template-columns:1fr 1fr}}.intelligence-hero{display:grid;grid-template-columns:66px minmax(0,1fr);gap:14px;align-items:center;padding:16px;margin-bottom:12px;border-radius:18px;background:radial-gradient(circle at 8% 20%,rgba(91,212,255,.16),transparent 34%),linear-gradient(135deg,rgba(91,212,255,.09),rgba(138,107,255,.07));border:1px solid rgba(91,212,255,.22);box-shadow:inset 0 1px 0 rgba(255,255,255,.05)}.intelligence-orbit{width:62px;height:62px;border-radius:20px;display:flex;align-items:center;justify-content:center;background:rgba(91,212,255,.10);border:1px solid rgba(91,212,255,.28);box-shadow:0 0 28px rgba(91,212,255,.10)}.intelligence-orbit ha-icon{--mdc-icon-size:34px;color:#6bdcff}.intelligence-copy h2{margin:3px 0 5px;font-size:18px;line-height:22px}.intelligence-copy p{margin:0;color:#a9bac4;font-size:9px;line-height:13px}.intelligence-meta{display:flex;flex-wrap:wrap;gap:6px;margin-top:9px}.intelligence-meta span{padding:5px 7px;border-radius:999px;background:rgba(255,255,255,.035);border:1px solid rgba(255,255,255,.07);font-size:7.5px;color:#8fa3af}.intelligence-meta b{color:#e9f8ff}.intelligence-v2.personal-ready .intelligence-hero{background:radial-gradient(circle at 8% 20%,rgba(91,212,255,.22),transparent 34%),linear-gradient(135deg,rgba(91,212,255,.13),rgba(138,107,255,.12));border-color:rgba(117,220,255,.38);box-shadow:inset 0 1px 0 rgba(255,255,255,.07),0 0 30px rgba(91,212,255,.07)}.learning-components-card{margin-top:8px;padding:13px;border-radius:16px;background:linear-gradient(145deg,rgba(91,212,255,.055),rgba(255,255,255,.018));border:1px solid rgba(91,212,255,.14);box-shadow:inset 0 1px 0 rgba(255,255,255,.025)}.learning-components-head{display:grid;grid-template-columns:minmax(0,1fr) auto;gap:12px;align-items:start}.learning-components-title{display:grid;grid-template-columns:40px minmax(0,1fr);gap:10px;align-items:center}.learning-components-icon{width:40px;height:40px;border-radius:12px;display:flex;align-items:center;justify-content:center;background:rgba(91,212,255,.10);border:1px solid rgba(91,212,255,.18);color:#63d2f7}.learning-components-icon ha-icon{--mdc-icon-size:23px}.learning-components-title h3{margin:2px 0 2px;font-size:14px}.learning-components-title span{display:block;font-size:8px;line-height:11px;color:#8fa1ad}.learning-overall{text-align:right;padding:7px 9px;border-radius:11px;background:rgba(91,212,255,.06);border:1px solid rgba(91,212,255,.12);min-width:74px}.learning-overall span,.learning-overall b{display:block}.learning-overall span{font-size:6.5px;font-weight:900;letter-spacing:.45px;color:#7f929e}.learning-overall b{font-size:17px;color:#dff7ff;margin-top:2px}.learn-quality-strip{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:6px;margin-top:10px}.learn-quality-strip>div{padding:7px 8px;border-radius:10px;background:rgba(255,255,255,.025);border:1px solid rgba(255,255,255,.055)}.learn-quality-strip span,.learn-quality-strip b{display:block}.learn-quality-strip span{font-size:6.2px;font-weight:900;letter-spacing:.4px;color:#788c99}.learn-quality-strip b{font-size:9px;line-height:12px;margin-top:2px;color:#dbe8ee}.learning-components-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:7px;margin-top:10px}.learn-component{display:grid;grid-template-columns:34px minmax(0,1fr);gap:8px;padding:9px;border-radius:12px;background:rgba(255,255,255,.024);border:1px solid rgba(255,255,255,.06);--learn-accent:#82929e}.learn-component.very{--learn-accent:#67df92}.learn-component.stable{--learn-accent:#7bd7b0}.learn-component.learning{--learn-accent:#63d2f7}.learn-component.early{--learn-accent:#d7b56c}.learn-component-icon{width:34px;height:34px;border-radius:10px;display:flex;align-items:center;justify-content:center;color:var(--learn-accent);background:color-mix(in srgb,var(--learn-accent) 10%,transparent);border:1px solid color-mix(in srgb,var(--learn-accent) 18%,transparent)}.learn-component-icon ha-icon{--mdc-icon-size:19px}.learn-component-head{display:grid;grid-template-columns:minmax(0,1fr) auto;gap:7px;align-items:start}.learn-component-head b,.learn-component-head span{display:block}.learn-component-head b{font-size:9.5px}.learn-component-head span{font-size:7px;line-height:9.5px;color:#7f929e;margin-top:2px}.learn-component-head strong{font-size:7.5px;color:var(--learn-accent);white-space:nowrap;padding:3px 5px;border-radius:999px;background:color-mix(in srgb,var(--learn-accent) 8%,transparent);border:1px solid color-mix(in srgb,var(--learn-accent) 16%,transparent)}.learn-progress{height:4px;border-radius:999px;background:rgba(255,255,255,.055);overflow:hidden;margin-top:7px}.learn-progress i{display:block;height:100%;border-radius:inherit;background:var(--learn-accent)}.learn-component-foot{display:flex;align-items:center;justify-content:space-between;gap:6px;margin-top:5px;font-size:6.8px;color:#768995}.learn-component-detail{font-size:7px;line-height:9.5px;color:#9cabb4;margin-top:5px}.learning-components-note{display:grid;grid-template-columns:16px minmax(0,1fr);gap:6px;align-items:start;margin-top:9px;padding-top:8px;border-top:1px solid rgba(255,255,255,.055);color:#7d909c}.learning-components-note ha-icon{--mdc-icon-size:14px}.learning-components-note span{font-size:7px;line-height:10px}.learn-components-empty{grid-column:1/-1;display:flex;gap:8px;align-items:center;padding:12px;color:#8395a0;font-size:8px}@media(max-width:650px){.learning-components-head{grid-template-columns:1fr}.learning-overall{justify-self:start;text-align:left}.learn-quality-strip{grid-template-columns:repeat(2,minmax(0,1fr))}.learning-components-grid{grid-template-columns:1fr}.learn-component-head{grid-template-columns:minmax(0,1fr) auto}}.learning-detail-card{padding:10px!important;gap:9px!important}.learning-detail-card p{margin:3px 0 5px!important}.learning-detail-progress{margin-top:5px!important}.longterm-hero{grid-template-columns:48px minmax(0,1fr)!important;gap:12px!important;align-items:center!important}.longterm-hero-copy{min-width:0;display:flex;flex-direction:column;gap:4px}.longterm-hero-copy b,.longterm-hero-copy span{display:block!important;position:static!important;white-space:normal!important}.longterm-hero-copy b{font-size:15px;line-height:19px}.longterm-hero-copy span{font-size:8px;line-height:11px;color:#8fa1ad}`;

/* v0.25.1.8 Compact AI-first dashboard. The full analysis remains behind the
 * existing detail views; the landing surface deliberately exposes only the
 * decision, rooms needing attention and three contextual intelligence doors. */
const FAIQ_AI_COMPACT_CSS = `
.ai-compact{margin-top:10px;display:grid;gap:9px}.ai-assistant{display:grid;grid-template-columns:62px minmax(0,1fr) 28px;gap:11px;align-items:center;padding:12px;border-radius:17px;background:radial-gradient(circle at 9% 50%,color-mix(in srgb,var(--ai) 14%,transparent),transparent 31%),rgba(255,255,255,.025);border:1px solid color-mix(in srgb,var(--ai) 25%,rgba(255,255,255,.06));cursor:pointer}.ai-mascot{position:relative;width:58px;height:58px;border-radius:50%;background:radial-gradient(circle at 42% 36%,#17364a 0 15%,#07131d 55%,#03080d 100%);border:2px solid #57d9ff;box-shadow:0 0 20px rgba(70,211,255,.22),inset 0 0 14px rgba(64,215,255,.16);animation:faiqFloat 3.6s ease-in-out infinite}.ai-mascot:before,.ai-mascot:after{content:"";position:absolute;top:23px;width:6px;height:11px;border-radius:999px;background:#c8f8ff;box-shadow:0 0 9px #57d9ff;animation:faiqBlink 5.2s infinite}.ai-mascot:before{left:16px}.ai-mascot:after{right:16px}.ai-smile{position:absolute;left:50%;top:36px;width:15px;height:7px;transform:translateX(-50%);border-bottom:2px solid #9af0ff;border-radius:0 0 14px 14px}.ai-leaf{position:absolute;right:-6px;bottom:2px;width:19px;height:11px;border-radius:100% 0 100% 0;background:#4ce6a2;transform:rotate(-26deg);box-shadow:0 0 12px rgba(76,230,162,.35)}.ai-compact.live .ai-leaf{animation:faiqLeafWind .7s ease-in-out infinite}.ai-compact.recommend .ai-mascot{border-color:#62e889;animation:faiqInvite 1.8s ease-in-out infinite}.ai-compact.close .ai-mascot{border-color:#ffb45f;animation:faiqAttention 1.25s ease-in-out infinite}.ai-compact.sensor .ai-mascot{border-color:#ff7770;animation:faiqSensor 1.8s ease-in-out infinite}.ai-compact.wait .ai-mascot{border-color:#e2bd69;animation:faiqWait 2.8s ease-in-out infinite}.ai-compact.pollen .ai-mascot{border-color:#e2bd69;animation:faiqPollen 2.6s ease-in-out infinite}.ai-compact.pollen .ai-leaf{animation:faiqLeafPollen 1.2s ease-in-out infinite}.ai-compact.cooling .ai-mascot{border-color:#63d2f7;animation:faiqCool 2.1s ease-in-out infinite}.ai-compact.good .ai-mascot{border-color:#62e889;animation:faiqContent 4s ease-in-out infinite}.ai-compact.success .ai-mascot{border-color:#62e889;animation:faiqCelebrateSmooth 3.4s ease-in-out infinite}@keyframes faiqFloat{0%,100%{transform:translateY(0)}50%{transform:translateY(-3px)}}@keyframes faiqContent{0%,100%{transform:translateY(0)}50%{transform:translateY(-2px)}}@keyframes faiqInvite{0%,100%{transform:translateY(0) scale(1)}50%{transform:translateY(-4px) scale(1.04)}}@keyframes faiqAttention{0%,100%{transform:rotate(0)}35%{transform:rotate(-4deg)}70%{transform:rotate(4deg)}}@keyframes faiqSensor{0%,100%{transform:translateX(0)}25%{transform:translateX(-2px)}50%{transform:translateX(2px)}75%{transform:translateX(-1px)}}@keyframes faiqWait{0%,100%{transform:translateY(0) rotate(0)}50%{transform:translateY(-1px) rotate(-2deg)}}@keyframes faiqPollen{0%,100%{transform:rotate(0)}45%{transform:rotate(-3deg)}55%{transform:rotate(3deg)}}@keyframes faiqCool{0%,100%{transform:translateY(0) scale(1)}50%{transform:translateY(-3px) scale(.98)}}@keyframes faiqBlink{0%,46%,50%,100%{transform:scaleY(1)}48%{transform:scaleY(.12)}}@keyframes faiqBreeze{0%,100%{filter:none}50%{filter:drop-shadow(8px 0 5px rgba(91,212,255,.35))}}@keyframes faiqLeafWind{0%,100%{transform:rotate(-35deg)}50%{transform:rotate(-8deg)}}@keyframes faiqLeafPollen{0%,100%{transform:rotate(-26deg)}50%{transform:rotate(-10deg) translateY(-2px)}}.ai-wind,.ai-sleepcap,.ai-zzz{display:none;position:absolute;pointer-events:none}.ai-compact.live .ai-wind{display:none}.ai-compact.live .ai-mascot{transform-origin:50% 60%;box-shadow:0 0 22px rgba(70,211,255,.28),inset 0 0 16px rgba(64,215,255,.2)}.ai-compact.pre-night .ai-sleepcap,.ai-compact.night .ai-sleepcap{display:block;z-index:8;left:5px;top:-13px;width:51px;height:31px;transform:rotate(-8deg);filter:drop-shadow(0 3px 4px rgba(0,0,0,.34));background:transparent}.ai-compact.pre-night .ai-sleepcap:before,.ai-compact.night .ai-sleepcap:before{content:"";position:absolute;left:5px;top:13px;width:37px;height:16px;border-radius:70% 30% 58% 24%;background:linear-gradient(145deg,#8f9cff 0%,#5969d9 58%,#35459e 100%);clip-path:polygon(0 100%,18% 25%,58% 0,100% 58%,82% 100%);box-shadow:inset 0 1px 0 rgba(255,255,255,.28)}.ai-compact.pre-night .ai-sleepcap:after,.ai-compact.night .ai-sleepcap:after{content:"";position:absolute;right:1px;top:14px;width:11px;height:11px;border-radius:50%;background:#e7ebff;box-shadow:0 0 7px rgba(191,200,255,.5)}.ai-compact.pre-night .ai-sleepcap,.ai-compact.night .ai-sleepcap{border-bottom:4px solid #dbe1ff;border-radius:0 0 45% 45%}.ai-compact.pre-night .ai-mascot{animation:faiqBedtime 3s ease-in-out infinite}.ai-compact.night .ai-mascot{animation:faiqSleep 4.2s ease-in-out infinite;border-color:#7789e8}.ai-compact.night .ai-mascot:before,.ai-compact.night .ai-mascot:after{height:2px;top:27px;animation:none;border-radius:99px;box-shadow:0 0 5px #57d9ff}.ai-compact.night .ai-smile{top:35px;width:10px;height:4px;opacity:.7}.ai-compact.night .ai-zzz{display:block;right:-20px;top:-10px;color:#9fb0ff;font-weight:950;font-size:11px;letter-spacing:1px;animation:faiqZzzSmooth 3.8s ease-in-out infinite}@keyframes faiqBedtime{0%,100%{transform:translateY(0) rotate(0)}50%{transform:translateY(2px) rotate(-4deg)}}@keyframes faiqSleep{0%,100%{transform:translateY(1px) rotate(-2deg) scale(1)}50%{transform:translateY(3px) rotate(-2deg) scale(.97)}}@media(prefers-reduced-motion:reduce){.ai-mascot,.ai-mascot:before,.ai-mascot:after,.ai-leaf,.ai-wind,.ai-zzz{animation:none!important}}.ai-mascot-wrap{position:relative;width:58px;height:58px}.ai-mascot-wrap .ai-mascot{position:absolute;inset:0;background:radial-gradient(circle at 40% 32%,#17384d 0 10%,#07151f 48%,#02070c 100%);box-shadow:0 0 9px #3ed7ff,0 0 22px rgba(70,211,255,.34),inset 0 0 15px rgba(64,215,255,.18);z-index:3}.ai-mascot-wrap .ai-leaf{left:-7px;right:auto;top:5px;bottom:auto;width:20px;height:12px;background:linear-gradient(135deg,#25efb0,#42d997)}.ai-airflow,.ai-air-leaf{display:none;position:absolute;pointer-events:none}.ai-airflow{left:-16px;width:86px;height:17px;border-top:2px solid rgba(83,210,255,.7);border-radius:50%;filter:drop-shadow(0 0 5px rgba(83,210,255,.55));z-index:1}.ai-airflow.a{top:8px}.ai-airflow.b{top:27px;left:-20px;width:92px}.ai-airflow.c{top:44px;left:-10px;width:78px}.ai-air-leaf{width:10px;height:6px;border-radius:100% 0 100% 0;background:#38e8a7;box-shadow:0 0 7px rgba(56,232,167,.55);z-index:2}.ai-compact.live .ai-airflow,.ai-compact.live .ai-air-leaf{display:block}.ai-compact.live .ai-mascot{animation:faiqSailSmooth 2.8s ease-in-out infinite}.ai-compact.live .ai-airflow.a{animation:faiqFlowA 2.8s ease-in-out infinite}.ai-compact.live .ai-airflow.b{animation:faiqFlowB 2.8s ease-in-out infinite}.ai-compact.live .ai-airflow.c{animation:faiqFlowC 2.8s ease-in-out infinite}.ai-compact.live .ai-air-leaf.one{left:2px;top:44px;animation:faiqAirLeafA 2.8s ease-in-out infinite}.ai-compact.live .ai-air-leaf.two{left:48px;top:7px;animation:faiqAirLeafB 2.8s ease-in-out infinite}.ai-compact.continuous .ai-airflow.a,.ai-compact.continuous .ai-airflow.c{display:block;border-top-width:1px;opacity:.25;animation:faiqGentleFlow 5.6s ease-in-out infinite}.ai-compact.continuous .ai-airflow.c{animation-direction:reverse}.ai-compact.continuous .ai-mascot{animation:faiqGentleVent 5.6s ease-in-out infinite}.ai-compact.continuous .ai-leaf{animation:faiqGentleLeaf 5.6s ease-in-out infinite}.ai-compact.cooling .ai-airflow.b{display:block;opacity:.4;animation:faiqCoolFlow 4.2s ease-in-out infinite}.ai-compact.success .ai-mascot{animation:faiqCelebrateSmooth 3.4s ease-in-out infinite}.ai-compact.night .ai-zzz{animation:faiqZzzSmooth 3.8s ease-in-out infinite}@keyframes faiqSailSmooth{0%,100%{transform:translate(0,0) rotate(-3deg)}25%{transform:translate(3px,-3px) rotate(1deg)}50%{transform:translate(5px,-1px) rotate(4deg)}75%{transform:translate(2px,2px) rotate(0deg)}}@keyframes faiqFlowA{0%,100%{transform:translateX(0) scaleX(.9);opacity:.35}50%{transform:translateX(8px) scaleX(1.08);opacity:.85}}@keyframes faiqFlowB{0%,100%{transform:translateX(5px);opacity:.3}50%{transform:translateX(-5px);opacity:.7}}@keyframes faiqFlowC{0%,100%{transform:translateX(-2px);opacity:.2}50%{transform:translateX(9px);opacity:.55}}@keyframes faiqAirLeafA{0%,100%{transform:translate(0,0) rotate(-35deg);opacity:.15}50%{transform:translate(40px,-22px) rotate(45deg);opacity:.9}}@keyframes faiqAirLeafB{0%,100%{transform:translate(0,0) rotate(20deg);opacity:.15}50%{transform:translate(-38px,28px) rotate(-60deg);opacity:.8}}@keyframes faiqGentleVent{0%,100%{transform:translateY(0) rotate(-1deg)}50%{transform:translateY(-1px) rotate(1deg)}}@keyframes faiqGentleFlow{0%,100%{transform:translateX(0);opacity:.15}50%{transform:translateX(5px);opacity:.3}}@keyframes faiqGentleLeaf{0%,100%{transform:rotate(-34deg)}50%{transform:rotate(-27deg)}}@keyframes faiqCoolFlow{0%,100%{transform:translateX(0);opacity:.2}50%{transform:translateX(7px);opacity:.48}}@keyframes faiqCelebrateSmooth{0%,100%{transform:translateY(0) rotate(0) scale(1)}25%{transform:translateY(-5px) rotate(-4deg) scale(1.03)}50%{transform:translateY(-2px) scale(1.05)}75%{transform:translateY(-5px) rotate(4deg) scale(1.03)}}@keyframes faiqZzzSmooth{0%,100%{transform:translate(0,8px) scale(.8);opacity:0}50%{transform:translate(5px,-2px) scale(1);opacity:1}}
/* v0.25.1.19 Freshy 3D + bounded semantic animation hotfix */
.ai-mascot-wrap{position:relative;width:62px;height:62px;overflow:hidden;border-radius:22px;contain:paint}
.ai-mascot-wrap .ai-mascot{inset:3px;width:52px;height:52px;border:0;background:radial-gradient(circle at 34% 25%,rgba(185,247,255,.28) 0 3%,rgba(56,176,220,.15) 8%,transparent 22%),radial-gradient(circle at 38% 34%,#12384c 0 9%,#082333 25%,#03131d 58%,#01070c 82%,#000306 100%);box-shadow:inset -10px -12px 16px rgba(0,0,0,.72),inset 7px 6px 14px rgba(77,221,255,.13),inset 0 0 0 2px rgba(95,224,255,.92),0 0 5px #45dcff,0 0 13px rgba(54,211,255,.68),0 0 22px rgba(31,157,214,.28);z-index:3}
.ai-mascot-wrap .ai-mascot:before,.ai-mascot-wrap .ai-mascot:after{top:20px;width:6px;height:10px;background:linear-gradient(180deg,#e9fdff,#94efff);box-shadow:0 0 5px #8eeeff,0 0 10px rgba(73,220,255,.85)}
.ai-mascot-wrap .ai-mascot:before{left:14px}.ai-mascot-wrap .ai-mascot:after{right:14px}.ai-mascot-wrap .ai-smile{top:33px;width:14px;height:7px;border-bottom-color:#aaf5ff;filter:drop-shadow(0 0 3px rgba(86,224,255,.8))}
/* The green leaf is Freshy's permanent wing, not a transient airflow particle. */
.ai-mascot-wrap .ai-leaf{display:block!important;left:2px;right:auto;top:7px;bottom:auto;width:21px;height:14px;border-radius:100% 8% 100% 8%;transform-origin:90% 75%;transform:rotate(-32deg);background:radial-gradient(circle at 28% 25%,#9affd3 0 5%,transparent 18%),linear-gradient(145deg,#38f2aa 0%,#19c982 55%,#087f58 100%);box-shadow:inset -3px -3px 5px rgba(0,70,48,.28),0 0 7px rgba(48,239,169,.55);z-index:5}
.ai-mascot-wrap .ai-leaf:before{content:"";position:absolute;left:3px;top:7px;width:15px;height:1px;background:rgba(221,255,239,.72);transform:rotate(18deg);transform-origin:left center;border-radius:99px}
.ai-airflow{left:3px;width:54px;height:14px;box-sizing:border-box;overflow:hidden}.ai-airflow.a{top:8px}.ai-airflow.b{top:27px;left:2px;width:57px}.ai-airflow.c{top:45px;left:5px;width:51px}.ai-air-leaf{width:8px;height:5px}.ai-compact.live .ai-air-leaf.one{left:7px;top:45px}.ai-compact.live .ai-air-leaf.two{left:46px;top:8px}
@keyframes faiqSailSmooth{0%,100%{transform:translate(0,0) rotate(-3deg)}25%{transform:translate(2px,-2px) rotate(1deg)}50%{transform:translate(3px,-1px) rotate(3deg)}75%{transform:translate(1px,2px) rotate(0deg)}}
@keyframes faiqFlowA{0%,100%{transform:translateX(0) scaleX(.9);opacity:.35}50%{transform:translateX(3px) scaleX(1.02);opacity:.82}}
@keyframes faiqFlowB{0%,100%{transform:translateX(2px);opacity:.3}50%{transform:translateX(-2px);opacity:.68}}
@keyframes faiqFlowC{0%,100%{transform:translateX(-1px);opacity:.2}50%{transform:translateX(3px);opacity:.52}}
@keyframes faiqAirLeafA{0%,100%{transform:translate(0,0) rotate(-35deg);opacity:.12}50%{transform:translate(31px,-19px) rotate(45deg);opacity:.85}}
@keyframes faiqAirLeafB{0%,100%{transform:translate(0,0) rotate(20deg);opacity:.12}50%{transform:translate(-30px,25px) rotate(-60deg);opacity:.76}}
@keyframes faiqGentleFlow{0%,100%{transform:translateX(0);opacity:.13}50%{transform:translateX(3px);opacity:.28}}
@keyframes faiqCoolFlow{0%,100%{transform:translateX(0);opacity:.2}50%{transform:translateX(3px);opacity:.46}}
@keyframes faiqLeafWind{0%,100%{transform:rotate(-32deg)}50%{transform:rotate(-19deg)}}
@keyframes faiqLeafPollen{0%,100%{transform:rotate(-32deg)}50%{transform:rotate(-24deg) translateY(-1px)}}
@keyframes faiqGentleLeaf{0%,100%{transform:rotate(-32deg)}50%{transform:rotate(-28deg)}}
@media(max-width:520px){.ai-mascot-wrap{width:52px;height:52px;border-radius:18px}.ai-mascot-wrap .ai-mascot{inset:3px;width:44px;height:44px}.ai-mascot-wrap .ai-mascot:before,.ai-mascot-wrap .ai-mascot:after{top:17px;height:8px}.ai-mascot-wrap .ai-mascot:before{left:12px}.ai-mascot-wrap .ai-mascot:after{right:12px}.ai-mascot-wrap .ai-smile{top:28px;width:12px}.ai-mascot-wrap .ai-leaf{left:1px;top:6px;width:18px;height:12px}.ai-airflow{max-width:47px}.ai-airflow.b{width:48px}.ai-airflow.c{width:44px}}
/* v0.25.1.19: Freshy reference-view hotfix. The angle layer stays static so state animations
   can move Freshy without ever losing the three-quarter presentation. */
.ai-mascot-wrap{perspective:180px}
.ai-freshy-angle{position:absolute;inset:3px 4px 4px 2px;z-index:3;transform:rotateY(-17deg) rotateZ(-4deg);transform-origin:50% 56%;transform-style:preserve-3d;filter:drop-shadow(5px 5px 7px rgba(0,0,0,.34))}
.ai-mascot-wrap .ai-freshy-angle .ai-mascot{inset:0;width:52px;height:52px;overflow:visible;background:radial-gradient(ellipse at 27% 18%,rgba(222,253,255,.42) 0 2%,rgba(83,216,255,.18) 7%,transparent 20%),radial-gradient(ellipse at 32% 31%,#17445a 0 8%,#092635 25%,#03141d 56%,#01070b 80%,#000204 100%);box-shadow:inset -13px -10px 17px rgba(0,0,0,.82),inset 6px 5px 12px rgba(93,226,255,.14),inset 0 0 0 2px rgba(101,229,255,.96),-2px -1px 5px rgba(119,236,255,.55),0 0 8px #45dcff,0 0 18px rgba(54,211,255,.62),0 0 27px rgba(31,157,214,.24)}
.ai-mascot-wrap .ai-freshy-angle .ai-mascot:before{left:20px;top:19px;width:7px;height:10px}
.ai-mascot-wrap .ai-freshy-angle .ai-mascot:after{right:8px;top:20px;width:5px;height:8px;transform:scaleY(.72);opacity:.92}
.ai-mascot-wrap .ai-freshy-angle .ai-smile{left:61%;top:33px;width:13px;height:6px;transform:translateX(-50%) rotate(-3deg)}
/* Freshy's green leaf wing sits behind the body, as in the visual reference. */
.ai-mascot-wrap .ai-freshy-angle .ai-leaf{left:-8px;top:8px;width:23px;height:16px;z-index:-1;transform-origin:92% 70%;transform:rotate(-27deg) skewX(-8deg);background:radial-gradient(circle at 28% 22%,#b7ffdc 0 4%,transparent 17%),linear-gradient(145deg,#52f6b6 0%,#1bd28a 56%,#087a54 100%);box-shadow:inset -4px -3px 6px rgba(0,65,44,.30),0 0 8px rgba(48,239,169,.62)}
.ai-mascot-wrap .ai-freshy-angle .ai-leaf:before{left:4px;top:8px;width:16px}
.ai-compact.live .ai-freshy-angle .ai-leaf{animation:faiqWingFlight 2.8s ease-in-out infinite}
.ai-compact.continuous .ai-freshy-angle .ai-leaf{animation:faiqWingGentle 5.6s ease-in-out infinite}
@keyframes faiqWingFlight{0%,100%{transform:rotate(-27deg) skewX(-8deg)}50%{transform:rotate(-14deg) skewX(-5deg)}}
@keyframes faiqWingGentle{0%,100%{transform:rotate(-27deg) skewX(-8deg)}50%{transform:rotate(-23deg) skewX(-7deg)}}
@media(max-width:520px){.ai-freshy-angle{inset:3px 4px 4px 2px}.ai-mascot-wrap .ai-freshy-angle .ai-mascot{width:44px;height:44px}.ai-mascot-wrap .ai-freshy-angle .ai-mascot:before{left:17px;top:16px;width:6px;height:8px}.ai-mascot-wrap .ai-freshy-angle .ai-mascot:after{right:7px;top:17px;width:4px;height:7px}.ai-mascot-wrap .ai-freshy-angle .ai-smile{left:61%;top:28px;width:11px;height:5px}.ai-mascot-wrap .ai-freshy-angle .ai-leaf{left:-7px;top:7px;width:20px;height:14px}}
/* v0.25.1.19: approved Freshy visual-state hotfix. Keep the mascot large and expressive;
   clipping is a safety boundary, never a reason to shrink the character. */
.ai-assistant{grid-template-columns:94px minmax(0,1fr) 28px;min-height:112px;overflow:hidden;isolation:isolate}
.ai-mascot-wrap{width:88px;height:88px;border-radius:0;overflow:hidden;contain:paint;perspective:260px;background:radial-gradient(circle at 48% 54%,rgba(42,203,255,.10),transparent 62%)}
.ai-freshy-angle{inset:8px 10px 8px 12px;transform:rotateY(-15deg) rotateZ(-3deg);filter:drop-shadow(6px 7px 8px rgba(0,0,0,.38))}
.ai-mascot-wrap .ai-freshy-angle .ai-mascot{width:66px;height:66px;inset:0;overflow:visible;background:radial-gradient(ellipse at 25% 16%,rgba(231,254,255,.58) 0 2%,rgba(84,221,255,.20) 7%,transparent 20%),radial-gradient(ellipse at 31% 30%,#17495f 0 7%,#082331 24%,#021019 56%,#000509 82%,#000102 100%);box-shadow:inset -16px -13px 21px rgba(0,0,0,.88),inset 7px 6px 15px rgba(96,228,255,.15),inset 0 0 0 2px rgba(116,237,255,.98),-3px -2px 7px rgba(135,241,255,.62),0 0 10px #43ddff,0 0 25px rgba(50,211,255,.62),0 0 40px rgba(27,154,215,.24)}
.ai-mascot-wrap .ai-freshy-angle .ai-mascot:before{left:25px;top:24px;width:8px;height:12px}.ai-mascot-wrap .ai-freshy-angle .ai-mascot:after{right:10px;top:25px;width:6px;height:10px;transform:scaleY(.76)}
.ai-mascot-wrap .ai-freshy-angle .ai-smile{left:61%;top:42px;width:16px;height:7px}
/* Two compact, nearly horizontal leaf wings: bird-wing silhouette, never ear-like. */
.ai-mascot-wrap .ai-freshy-angle .ai-leaf,.ai-mascot-wrap .ai-freshy-angle .ai-leaf-right{display:block!important;position:absolute;top:22px;width:25px;height:13px;z-index:-1;pointer-events:none;transform-origin:92% 54%;border-radius:78% 18% 72% 24%;background:radial-gradient(ellipse at 28% 24%,#c1ffe1 0 4%,transparent 18%),linear-gradient(160deg,#62f7b8 0%,#1ed58e 57%,#087d55 100%);box-shadow:inset -4px -3px 6px rgba(0,65,44,.30),0 0 8px rgba(48,239,169,.56)}
.ai-mascot-wrap .ai-freshy-angle .ai-leaf{left:-16px;transform:rotate(-5deg) skewX(-10deg)}
.ai-mascot-wrap .ai-freshy-angle .ai-leaf-right{right:-14px;transform:scaleX(-1) rotate(-4deg) skewX(-9deg);opacity:.82}
.ai-mascot-wrap .ai-freshy-angle .ai-leaf:before,.ai-mascot-wrap .ai-freshy-angle .ai-leaf-right:before{content:"";position:absolute;left:4px;top:7px;width:18px;height:1px;background:rgba(225,255,241,.70);transform:rotate(4deg);transform-origin:left center;border-radius:99px}
/* Airflow lives behind Freshy and has enough room without escaping the hero. */
.ai-airflow{left:2px;width:82px;height:18px;z-index:1}.ai-airflow.a{top:16px}.ai-airflow.b{top:39px;left:0;width:86px}.ai-airflow.c{top:62px;left:5px;width:77px}.ai-air-leaf{z-index:2}
.ai-compact.live .ai-air-leaf.one{left:8px;top:64px}.ai-compact.live .ai-air-leaf.two{left:68px;top:13px}
.ai-compact.live .ai-freshy-angle .ai-leaf{animation:faiqWingFlight18 2.8s ease-in-out infinite}.ai-compact.live .ai-freshy-angle .ai-leaf-right{animation:faiqWingFlightRight18 2.8s ease-in-out infinite}
@keyframes faiqWingFlight18{0%,100%{transform:rotate(-5deg) skewX(-10deg)}50%{transform:rotate(-13deg) translateY(-2px) skewX(-8deg)}}
@keyframes faiqWingFlightRight18{0%,100%{transform:scaleX(-1) rotate(-4deg) skewX(-9deg)}50%{transform:scaleX(-1) rotate(-11deg) translateY(-2px) skewX(-7deg)}}
/* Continuous ventilation is intentionally calm: one faint stream, no flying particles. */
.ai-compact.continuous .ai-airflow,.ai-compact.continuous .ai-air-leaf{display:none!important}.ai-compact.continuous .ai-airflow.b{display:block!important;opacity:.16;border-top-width:1px;animation:faiqGentleFlow18 7.2s ease-in-out infinite}
.ai-compact.continuous .ai-freshy-angle .ai-leaf{animation:faiqWingGentle18 7.2s ease-in-out infinite}.ai-compact.continuous .ai-freshy-angle .ai-leaf-right{animation:faiqWingGentleRight18 7.2s ease-in-out infinite}
@keyframes faiqGentleFlow18{0%,100%{transform:translateX(0) scaleX(.92);opacity:.10}50%{transform:translateX(2px) scaleX(.96);opacity:.19}}
@keyframes faiqWingGentle18{0%,100%{transform:rotate(-5deg) skewX(-10deg)}50%{transform:rotate(-7deg) translateY(-1px) skewX(-9deg)}}
@keyframes faiqWingGentleRight18{0%,100%{transform:scaleX(-1) rotate(-4deg) skewX(-9deg)}50%{transform:scaleX(-1) rotate(-6deg) translateY(-1px) skewX(-8deg)}}
/* Waiting is genuinely still: no airflow or particles. */
.ai-compact.wait .ai-airflow,.ai-compact.wait .ai-air-leaf,.ai-compact.good .ai-airflow,.ai-compact.good .ai-air-leaf{display:none!important}
/* Pre-night: cap on, clearly tired but still awake. */
.ai-compact.pre-night .ai-mascot:before,.ai-compact.pre-night .ai-mascot:after{height:5px;top:29px;border-radius:50% 50% 70% 70%;animation:none;transform:rotate(8deg) scaleY(.55);opacity:.92}
.ai-compact.pre-night .ai-mascot:after{transform:rotate(-8deg) scaleY(.55)}.ai-compact.pre-night .ai-smile{top:44px;width:12px;opacity:.78}
.ai-compact.pre-night .ai-zzz,.ai-compact.pre-night .ai-moon{display:none!important}
/* Night: purple ambience + crescent moon; Freshy is asleep. */
.ai-moon{display:none;position:absolute;right:2px;top:3px;width:18px;height:18px;border-radius:50%;background:#b08cff;box-shadow:0 0 13px rgba(150,105,255,.75);z-index:6}.ai-moon:after{content:"";position:absolute;width:16px;height:16px;left:6px;top:-2px;border-radius:50%;background:#09101a}
.ai-compact.night .ai-moon{display:block}.ai-compact.night .ai-mascot-wrap{background:radial-gradient(circle at 50% 52%,rgba(115,72,255,.22),transparent 65%)}.ai-compact.night .ai-freshy-angle{filter:drop-shadow(6px 7px 8px rgba(0,0,0,.38)) drop-shadow(0 0 10px rgba(123,82,255,.35))}.ai-compact.night .ai-airflow,.ai-compact.night .ai-air-leaf{display:none!important}
/* Success stays celebratory but restrained. */
.ai-compact.success .ai-airflow{display:none!important}.ai-compact.success .ai-air-leaf{display:block;opacity:.65}
@media(max-width:520px){.ai-assistant{grid-template-columns:84px minmax(0,1fr) 22px;min-height:102px}.ai-mascot-wrap{width:78px;height:78px}.ai-freshy-angle{inset:8px 9px 7px 11px}.ai-mascot-wrap .ai-freshy-angle .ai-mascot{width:58px;height:58px}.ai-mascot-wrap .ai-freshy-angle .ai-mascot:before{left:22px;top:21px;width:7px;height:10px}.ai-mascot-wrap .ai-freshy-angle .ai-mascot:after{right:9px;top:22px;width:5px;height:9px}.ai-mascot-wrap .ai-freshy-angle .ai-smile{top:37px;width:14px}.ai-mascot-wrap .ai-freshy-angle .ai-leaf,.ai-mascot-wrap .ai-freshy-angle .ai-leaf-right{top:19px;width:22px;height:12px}.ai-mascot-wrap .ai-freshy-angle .ai-leaf{left:-14px}.ai-mascot-wrap .ai-freshy-angle .ai-leaf-right{right:-12px}.ai-airflow{width:72px}.ai-airflow.b{width:76px}.ai-airflow.c{width:68px}.ai-compact.pre-night .ai-mascot:before,.ai-compact.pre-night .ai-mascot:after{top:26px}}
.ai-copy{min-width:0}.ai-kicker{font-size:7px;font-weight:950;letter-spacing:.75px;color:var(--ai);text-transform:uppercase}.ai-copy h2{margin:2px 0 2px;font-size:20px;line-height:23px}.ai-copy p{margin:0;color:#aab8c1;font-size:9.5px;line-height:13px;display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden}.ai-chevron{--mdc-icon-size:21px;color:#738793}.ai-facts{display:flex;gap:6px;flex-wrap:wrap;margin-top:7px}.ai-facts span{display:inline-flex;align-items:center;gap:4px;font-size:8px;font-weight:850;color:#c9d5db}.ai-facts ha-icon{--mdc-icon-size:14px;color:var(--ai)}.ai-attention{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:6px}.ai-room{display:grid;grid-template-columns:30px minmax(0,1fr) 16px;gap:7px;align-items:center;padding:8px 9px;border-radius:12px;background:color-mix(in srgb,var(--room) 6%,rgba(255,255,255,.02));border:1px solid color-mix(in srgb,var(--room) 26%,transparent);cursor:pointer}.ai-room>ha-icon:first-child{--mdc-icon-size:20px;color:var(--room)}.ai-room b,.ai-room small{display:block;min-width:0;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.ai-room b{font-size:9.5px}.ai-room small{font-size:7.5px;color:var(--room);margin-top:2px}.ai-room>ha-icon:last-child{--mdc-icon-size:15px;color:#70828d}.ai-all-good{display:flex;align-items:center;gap:6px;padding:7px 9px;border-radius:11px;background:rgba(98,232,137,.035);border:1px solid rgba(98,232,137,.12);font-size:8px;color:#9fb0b9;cursor:pointer}.ai-all-good ha-icon{--mdc-icon-size:16px;color:#62e889}.ai-context{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:6px}.ai-context button{appearance:none;min-width:0;border:1px solid rgba(255,255,255,.065);background:rgba(255,255,255,.022);color:inherit;border-radius:11px;padding:7px 8px;display:grid;grid-template-columns:17px minmax(0,1fr);gap:5px;text-align:left;cursor:pointer}.ai-context ha-icon{--mdc-icon-size:15px;color:var(--ctx,#63d2f7)}.ai-context b,.ai-context small{display:block;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.ai-context b{font-size:8px}.ai-context small{font-size:6.7px;color:#7f929e;margin-top:1px}.compact-actions{justify-content:flex-end;margin-top:7px}.compact-actions .details-btn{padding:6px 9px;font-size:8px}@media(max-width:520px){.ai-assistant{grid-template-columns:84px minmax(0,1fr) 22px;padding:10px}.ai-mascot{width:48px;height:48px}.ai-mascot:before,.ai-mascot:after{top:19px;height:9px}.ai-mascot:before{left:13px}.ai-mascot:after{right:13px}.ai-smile{top:30px}.ai-copy h2{font-size:17px;line-height:20px}.ai-attention{grid-template-columns:1fr}.ai-context button{padding:7px 6px}.ai-context small{display:none}}

/* v0.25.1.19: Freshy seamless-hero hotfix.
   Remove the visible mascot tile and avoid hard clipping. Air effects fade before the
   top/left/bottom hero boundaries while remaining free to extend softly toward the copy. */
.ai-assistant{position:relative}
.ai-mascot-wrap{overflow:visible;contain:none;border-radius:0;background:none;isolation:isolate}
.ai-mascot-wrap::before{content:none!important}
.ai-airflow{-webkit-mask-image:linear-gradient(90deg,transparent 0%,#000 14%,#000 82%,transparent 100%);mask-image:linear-gradient(90deg,transparent 0%,#000 14%,#000 82%,transparent 100%)}
.ai-air-leaf{filter:drop-shadow(0 0 4px rgba(56,232,167,.38))}
.ai-copy{position:relative;z-index:4}.ai-chevron{position:relative;z-index:5}
@media(max-width:520px){.ai-mascot-wrap{overflow:visible;contain:none;background:none}}

`;

/* v0.25.1.40 compact readability + progressive disclosure */
const FAIQ_COMPACT_DISCLOSURE_CSS = `
.ai-copy h2{font-size:21px;line-height:24px}.ai-copy p{font-size:11px;line-height:15px;-webkit-line-clamp:2}.ai-kicker{font-size:8px}.ai-facts span{font-size:9.5px}.ai-attention{grid-template-columns:1fr}.ai-room-wrap{min-width:0}.ai-room{grid-template-columns:32px minmax(0,1fr) 20px;padding:9px 10px}.ai-room b{font-size:11.5px}.ai-room small{font-size:9.5px;line-height:13px}.ai-all-good{font-size:9.5px}.ai-context b{font-size:9.5px}.ai-context small{font-size:8px}.compact-actions .details-btn{font-size:9.5px}.ai-inline-detail{margin-top:-3px;padding:10px 11px;border-radius:0 0 12px 12px;background:color-mix(in srgb,var(--detail) 5%,rgba(255,255,255,.018));border:1px solid color-mix(in srgb,var(--detail) 22%,transparent);border-top:0;display:grid;gap:6px;min-width:0}.ai-inline-detail>div:not(.ai-inline-title):not(.ai-inline-values){display:grid;grid-template-columns:17px minmax(0,1fr);gap:6px;align-items:start}.ai-inline-detail>div>ha-icon{--mdc-icon-size:15px;color:var(--detail)}.ai-inline-detail>div>span{font-size:11px;line-height:15px;color:#c7d1d7;overflow-wrap:anywhere}.ai-inline-title{font-size:8.5px;font-weight:950;letter-spacing:.65px;color:var(--detail)}.ai-inline-values{display:flex!important;grid-template-columns:none!important;gap:6px!important;flex-wrap:wrap;margin-top:2px}.ai-inline-values span{font-size:9.5px!important;font-weight:800;padding:4px 7px;border-radius:999px;background:rgba(255,255,255,.04);color:#b9c7ce!important}.ai-more{appearance:none;border:0;background:transparent;color:var(--detail);padding:5px 0 1px;font:inherit;font-size:10px;font-weight:900;display:flex;align-items:center;justify-content:flex-end;gap:3px;cursor:pointer}.ai-more ha-icon{--mdc-icon-size:15px}.ai-expand-chevron{transition:transform .15s ease}.decision-inline-detail{margin-top:-12px;padding-top:17px}.ai-assistant,.ai-room{min-width:0;overflow:hidden}.ai-copy,.ai-room>div{min-width:0}@media(max-width:520px){.ai-copy h2{font-size:19px;line-height:22px}.ai-copy p{font-size:10.5px;line-height:14px}.ai-context small{display:block;font-size:7.5px}.ai-context button{grid-template-columns:16px minmax(0,1fr);padding:7px 5px}.ai-context b{font-size:9px}.ai-inline-detail>div>span{font-size:10.5px;line-height:14px}}

/* v0.25.1.40 classic dashboard progressive disclosure */
.decision-card{padding:14px}.decision-kicker{font-size:9.5px;line-height:13px}.decision-main h2{font-size:20px;line-height:24px}.decision-action{font-size:13px;line-height:17px}.decision-impact span{font-size:8.5px;line-height:11px}.decision-impact b{font-size:13px;line-height:17px}.decision-impact small{font-size:10.5px;line-height:14px}.decision-room-disclosures{display:grid;gap:7px;margin-top:10px}.decision-room-disclosure,.decision-more{border:1px solid rgba(255,255,255,.075);border-radius:12px;background:rgba(255,255,255,.025);overflow:hidden}.decision-room-disclosure{border-color:color-mix(in srgb,var(--room-detail) 28%,rgba(255,255,255,.075));background:color-mix(in srgb,var(--room-detail) 5%,rgba(255,255,255,.025))}.decision-room-disclosure>summary,.decision-more>summary{list-style:none;display:grid;align-items:center;cursor:pointer;min-width:0}.decision-room-disclosure>summary::-webkit-details-marker,.decision-more>summary::-webkit-details-marker{display:none}.decision-room-disclosure>summary{grid-template-columns:minmax(0,1fr) auto 20px;gap:8px;padding:10px 11px;color:var(--primary-text-color,#fff)}.decision-room-disclosure>summary span{font-size:12.5px;font-weight:900;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;color:var(--primary-text-color,#fff)}.decision-room-disclosure>summary strong{font-size:10.5px;color:var(--room-detail);white-space:nowrap}.decision-room-disclosure>summary ha-icon,.decision-more>summary ha-icon{--mdc-icon-size:18px;transition:transform .16s ease}.decision-room-disclosure[open]>summary ha-icon,.decision-more[open]>summary ha-icon{transform:rotate(180deg)}.decision-room-detail{padding:0 11px 11px;border-top:1px solid rgba(255,255,255,.055)}.decision-room-detail .decision-section-title{font-size:8.5px!important;margin-top:10px}.decision-room-reason{display:grid;grid-template-columns:18px minmax(0,1fr);gap:7px;align-items:start;margin-top:7px}.decision-room-reason ha-icon{--mdc-icon-size:16px;color:var(--room-detail)}.decision-room-reason span{font-size:11.5px;line-height:16px;color:#c7d1d7;overflow-wrap:anywhere}.decision-room-values{display:flex;gap:6px;flex-wrap:wrap;margin-top:9px}.decision-room-values span{font-size:10px;font-weight:800;padding:4px 7px;border-radius:999px;background:rgba(255,255,255,.045)}.decision-room-open{appearance:none;border:0;background:transparent;color:var(--room-detail);padding:9px 0 0;font:inherit;font-size:10.5px;font-weight:900;cursor:pointer}.decision-more{margin-top:11px}.decision-more>summary{grid-template-columns:minmax(0,1fr) auto 20px;gap:8px;padding:10px 11px}.decision-more>summary>span:first-child{font-size:12px;font-weight:900}.decision-more-hint{font-size:9.5px;color:#8798a3;white-space:nowrap}.decision-more-content{padding:0 11px 11px;border-top:1px solid rgba(255,255,255,.055)}.decision-more-content .decision-summary{font-size:11.5px;line-height:16px;margin-top:10px}.decision-more-content .decision-section-title{font-size:8.5px!important}.decision-more-content .decision-why span{font-size:11.5px;line-height:16px}.decision-more-content .decision-alternative{font-size:10.5px;line-height:15px}.decision-more-content .iq-process-head{font-size:10.5px}.decision-more-content .iq-process-text{font-size:11.5px;line-height:16px}@media(max-width:520px){.decision-main h2{font-size:19px;line-height:23px}.decision-action{font-size:12.5px;line-height:17px}.decision-impact span{font-size:8px}.decision-impact b{font-size:12.5px}.decision-impact small{font-size:10px}.decision-more-hint{display:none}.decision-more>summary{grid-template-columns:minmax(0,1fr) 20px}.decision-room-disclosure>summary span{font-size:12px}.decision-room-reason span,.decision-more-content .decision-summary,.decision-more-content .decision-why span,.decision-more-content .iq-process-text{font-size:11px;line-height:15px}}
/* v0.25.1.40: materially larger Classic typography; responsive grids stay intact. */
.hero{font-size:12px;line-height:16px}.pill{font-size:11px}.decision-kicker{font-size:11px;line-height:15px}.decision-main h2{font-size:22px;line-height:27px}.decision-action{font-size:15px;line-height:20px}.decision-rooms span{font-size:11px}.decision-summary{font-size:13px;line-height:18px}.decision-impact span{font-size:10px;line-height:13px}.decision-impact b,.night-context b{font-size:14px;line-height:19px}.decision-impact small{font-size:12px;line-height:16px}.decision-room-disclosure>summary span{font-size:14px}.decision-room-disclosure>summary strong{font-size:12px}.decision-room-reason span{font-size:13px;line-height:18px}.decision-room-values span{font-size:11.5px}.decision-room-open{font-size:12px}.decision-more>summary>span:first-child{font-size:14px}.decision-more-hint{font-size:11px}.decision-more-content .decision-summary,.decision-more-content .decision-why span,.decision-more-content .iq-process-text{font-size:13px;line-height:18px}.decision-more-content .decision-section-title,.decision-room-detail .decision-section-title{font-size:10px!important;line-height:13px}.decision-more-content .decision-alternative,.decision-more-content .iq-process-head{font-size:12px;line-height:16px}.tiny{font-size:10px;line-height:13px}.muted{font-size:11px;line-height:15px}.details-btn{font-size:11px}
@media(max-width:520px){.decision-main h2{font-size:21px;line-height:26px}.decision-action{font-size:14px;line-height:19px}.decision-impact span{font-size:9.5px}.decision-impact b{font-size:13.5px;line-height:18px}.decision-impact small{font-size:11.5px;line-height:16px}.decision-room-disclosure>summary span{font-size:13.5px}.decision-room-reason span,.decision-more-content .decision-summary,.decision-more-content .decision-why span,.decision-more-content .iq-process-text{font-size:12.5px;line-height:17px}}


.settings-goal-order-list{display:grid;gap:7px;margin-top:8px}.settings-goal-order-row{display:grid;grid-template-columns:28px minmax(0,1fr) auto;gap:9px;align-items:center;padding:9px 10px;border:1px solid var(--divider-color,#ffffff18);border-radius:11px}.settings-goal-order-index{font-size:11px;font-weight:900;color:var(--secondary-text-color,#9aa7b3);text-align:center}.settings-goal-order-row b{font-size:12px}.settings-goal-order-buttons{display:flex;gap:4px}.settings-goal-order-buttons button{width:31px;height:31px;border-radius:8px;border:1px solid var(--divider-color,#ffffff20);background:transparent;color:var(--primary-text-color,#fff);display:grid;place-items:center}.settings-goal-order-buttons button:disabled{opacity:.28}.goal-impact{display:flex;gap:4px;white-space:nowrap;font-size:10px;font-weight:900}.goal-impact.removed,.goal-impact.cooler,.goal-impact.lower{color:#67df92}.goal-impact.added,.goal-impact.warmer{color:#ff7770}.goal-impact.neutral{color:#9aa7b3}.goal-impact-time{color:#aebbc4;font-weight:750}.goal-impact-note{font-size:8.5px;color:#8fa1ad;font-weight:700}.decision-goal-overview{margin:14px 0 10px;padding:12px;border:1px solid #ffffff18;border-radius:14px;background:#ffffff08}.decision-goal-room+.decision-goal-room{margin-top:10px;padding-top:10px;border-top:1px solid #ffffff12}.decision-goal-head{display:flex;gap:8px;align-items:center;justify-content:space-between;margin-bottom:8px}.decision-goal-head>span{font-weight:700;color:#e9f0f4}.decision-goal-head>strong{font-size:11px;color:#9fd9ff}.decision-goals{display:flex;gap:7px;flex-wrap:wrap}.decision-goal{display:flex;align-items:center;gap:5px;padding:6px 8px;border-radius:10px;background:#111a20;border:1px solid #ffffff12}.decision-goal ha-icon{--mdc-icon-size:16px}.decision-goal b{font-size:11px}.decision-goal small{font-size:10px;color:#aebbc4}.decision-goal.reached{border-color:#62e88955}.decision-goal.open{border-color:#63d2f755}.decision-goal.blocked{border-color:#e2bd6955}.decision-goal-protection{display:flex;align-items:center;gap:6px;margin-top:8px;color:#f0c56e;font-size:11px}.decision-scope{display:inline-flex;align-items:center;margin:0 0 8px;padding:3px 7px;border-radius:999px;border:1px solid color-mix(in srgb,var(--decision) 30%,transparent);background:color-mix(in srgb,var(--decision) 7%,transparent);font-size:9px;font-weight:950;letter-spacing:.55px;color:var(--decision);text-transform:uppercase}.decision-goal-overview.compact{padding:8px 9px;margin:10px 0 8px}.decision-house-goals{display:flex;gap:7px;flex-wrap:wrap}.house-goal{display:inline-flex;align-items:center;gap:5px;min-height:27px;padding:4px 7px;border:1px solid color-mix(in srgb,var(--goal) 34%,transparent);border-radius:10px;background:color-mix(in srgb,var(--goal) 6%,#111a20)}.house-goal-icon{--mdc-icon-size:18px;color:var(--goal)}.house-goal-status,.house-goal-eta,.house-goal-blocked{display:inline-flex;align-items:center;gap:3px;font-size:10.5px;font-weight:850;white-space:nowrap}.house-goal-status.reached{color:#73df99}.house-goal-status ha-icon,.house-goal-eta ha-icon,.house-goal-blocked ha-icon{--mdc-icon-size:14px}.house-goal-eta{color:#c8d6de}.house-goal-blocked{color:#ff7b7b}.decision-goal-rooms{margin-top:7px;border-top:1px solid #ffffff12;padding-top:6px}.decision-goal-rooms>summary,.decision-goal-room>summary{list-style:none;cursor:pointer}.decision-goal-rooms>summary::-webkit-details-marker,.decision-goal-room>summary::-webkit-details-marker{display:none}.decision-goal-rooms>summary{display:flex;align-items:center;justify-content:space-between;padding:4px 2px;font-size:10.5px;font-weight:900;color:#c9d5dc}.decision-goal-rooms>summary ha-icon,.decision-goal-chevron{--mdc-icon-size:17px;transition:transform .16s ease}.decision-goal-rooms[open]>summary>ha-icon,.decision-goal-room[open]>summary>.decision-goal-chevron{transform:rotate(180deg)}.decision-goal-room-list{margin-top:7px;padding-top:2px;overflow:visible}.decision-goal-room{border-top:1px solid #ffffff0e}.decision-goal-room:first-child{border-top:0}.decision-goal-room>summary{display:grid;grid-template-columns:minmax(85px,1fr) auto auto 17px;gap:7px;align-items:center;padding:7px 2px}.decision-goal-room-name{font-size:11.5px;font-weight:850;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.decision-goal-room>summary>strong{display:inline-flex;align-items:center;gap:3px;font-size:9.5px;color:#9fd9ff;white-space:nowrap}.decision-goal-room>summary>strong ha-icon{--mdc-icon-size:15px}.decision-goals{display:flex;gap:5px;flex-wrap:nowrap}.decision-goal-icon{display:inline-flex;align-items:center;gap:2px;white-space:nowrap}.decision-goal-icon .goal-kind{--mdc-icon-size:16px;color:#c8d6de}.decision-goal-icon .goal-state{--mdc-icon-size:13px}.decision-goal-icon.reached .goal-state{color:#73df99}.decision-goal-icon.open .goal-state{color:#63d2f7}.decision-goal-icon.blocked .goal-state{color:#ff7b7b}.decision-goal-icon small{font-size:9px;color:#b9c6ce}.decision-goal-room-detail{padding:0 2px 8px 2px}.decision-goal-action{margin-top:5px;font-size:10px;color:#aebbc4}.decision-goal-explain{display:flex;gap:5px;align-items:flex-start;margin-top:6px;color:#ff9a9a;font-size:10.5px;line-height:14px}.decision-goal-explain ha-icon{--mdc-icon-size:15px}.decision-goal-protection{font-size:10.5px;line-height:14px}.decision-goal-room-detail .decision-room-reason{margin-top:5px}.decision-goal-room-detail .decision-room-reason span{font-size:10.5px;line-height:14px}@media(max-width:520px){.decision-goal-room>summary{grid-template-columns:minmax(78px,1fr) auto minmax(0,auto) 15px;gap:5px}.decision-goal-room-name{font-size:11px}.decision-goal-room>summary>strong{font-size:9px}.decision-goal-icon .goal-kind{--mdc-icon-size:15px}.decision-goal-icon small{font-size:8.5px}.house-goal{padding:4px 6px}.house-goal-status,.house-goal-eta,.house-goal-blocked{font-size:10px}}.ai-scope{display:inline-flex;margin-bottom:3px;font-size:7px;font-weight:950;letter-spacing:.65px;color:var(--ai);text-transform:uppercase}.ai-goal-line{display:flex;gap:5px;flex-wrap:wrap;margin-top:6px}.ai-goal-chip{font-size:7.5px;font-weight:850;padding:3px 6px;border-radius:999px;border:1px solid color-mix(in srgb,var(--goal) 34%,transparent);background:color-mix(in srgb,var(--goal) 7%,transparent);color:#dbe7ed}.ai-goal-chip.driver{color:var(--goal);border-color:color-mix(in srgb,var(--goal) 60%,transparent)}.decision-kicker{font-size:calc(11px * var(--faiq-font-recommendation,1));line-height:calc(15px * var(--faiq-font-recommendation,1))}.decision-main h2{font-size:calc(22px * var(--faiq-font-recommendation,1));line-height:calc(27px * var(--faiq-font-recommendation,1))}.decision-action{font-size:calc(15px * var(--faiq-font-recommendation,1));line-height:calc(20px * var(--faiq-font-recommendation,1))}.decision-card>.decision-summary{font-size:calc(13px * var(--faiq-font-recommendation,1));line-height:calc(18px * var(--faiq-font-recommendation,1))}.decision-rooms span{font-size:calc(11px * var(--faiq-font-recommendation,1))}
.decision-goal-overview .house-goal-status,.decision-goal-overview .house-goal-eta,.decision-goal-overview .house-goal-blocked{font-size:calc(10.5px * var(--faiq-font-goals,1))}.goal-tracker .goal-pill small{font-size:calc(10px * var(--faiq-font-goals,1))}.goal-tracker .goal-impact,.goal-tracker .goal-impact-time{font-size:calc(10px * var(--faiq-font-goals,1))}.goal-tracker .goal-impact-note{font-size:calc(8.5px * var(--faiq-font-goals,1))}.decision-goal-overview .decision-goal-room-name{font-size:calc(11.5px * var(--faiq-font-goals,1))}.decision-goal-overview .decision-goal-action,.decision-goal-overview .decision-goal-explain,.decision-goal-overview .decision-goal-protection{font-size:calc(10.5px * var(--faiq-font-goals,1))}
.room-card .room-title,.room-list .room-title,.ai-attention .ai-room b{font-size:calc(15px * var(--faiq-font-rooms,1));line-height:calc(19px * var(--faiq-font-rooms,1))}.room-card .room-sub,.room-list .room-sub,.ai-attention .ai-room small{font-size:calc(9.5px * var(--faiq-font-rooms,1));line-height:calc(13px * var(--faiq-font-rooms,1))}.decision-room-disclosure>summary span{font-size:calc(14px * var(--faiq-font-rooms,1))}.decision-room-disclosure>summary strong{font-size:calc(12px * var(--faiq-font-rooms,1))}.decision-room-open{font-size:calc(12px * var(--faiq-font-rooms,1))}
.metrics .metric .tiny,.metrics .summary .tiny,.metrics .mini .tiny,.active-metrics .metric .tiny{font-size:calc(10px * var(--faiq-font-metrics,1));line-height:calc(13px * var(--faiq-font-metrics,1))}.metrics .metric .value,.metrics .summary .value,.metrics .mini .value,.active-metrics .metric .value{font-size:calc(16px * var(--faiq-font-metrics,1))}.metrics .metric .muted,.metrics .summary .muted,.metrics .mini .muted,.active-metrics .metric .muted{font-size:calc(11px * var(--faiq-font-metrics,1));line-height:calc(15px * var(--faiq-font-metrics,1))}
.decision-more-content .decision-summary,.decision-more-content .decision-why span,.decision-more-content .iq-process-text,.decision-room-detail .decision-room-reason span{font-size:calc(13px * var(--faiq-font-details,1));line-height:calc(18px * var(--faiq-font-details,1))}.decision-more-content .decision-alternative,.decision-more-content .iq-process-head{font-size:calc(12px * var(--faiq-font-details,1));line-height:calc(16px * var(--faiq-font-details,1))}.decision-more-content .decision-section-title,.decision-room-detail .decision-section-title{font-size:calc(10px * var(--faiq-font-details,1))!important;line-height:calc(13px * var(--faiq-font-details,1))}
.top .hero{font-size:calc(12px * var(--faiq-font-meta,1));line-height:calc(16px * var(--faiq-font-meta,1))}.top .pill{font-size:calc(11px * var(--faiq-font-meta,1))}.decision-scope{font-size:calc(11px * var(--faiq-font-meta,1));line-height:calc(14px * var(--faiq-font-meta,1))}.ai-scope{font-size:calc(10px * var(--faiq-font-meta,1));line-height:calc(13px * var(--faiq-font-meta,1))}.ai-goal-chip{font-size:calc(10px * var(--faiq-font-meta,1));line-height:calc(13px * var(--faiq-font-meta,1))}.decision-more-hint{font-size:calc(11px * var(--faiq-font-meta,1))}
@media(max-width:520px){.decision-main h2{font-size:calc(21px * var(--faiq-font-recommendation,1));line-height:calc(26px * var(--faiq-font-recommendation,1))}.decision-action{font-size:calc(14px * var(--faiq-font-recommendation,1));line-height:calc(19px * var(--faiq-font-recommendation,1))}.decision-room-disclosure>summary span{font-size:calc(13.5px * var(--faiq-font-rooms,1))}.decision-room-detail .decision-room-reason span,.decision-more-content .decision-summary,.decision-more-content .decision-why span,.decision-more-content .iq-process-text{font-size:calc(12.5px * var(--faiq-font-details,1));line-height:calc(17px * var(--faiq-font-details,1))}.decision-scope{font-size:calc(10.5px * var(--faiq-font-meta,1))}.ai-scope,.ai-goal-chip{font-size:calc(9.5px * var(--faiq-font-meta,1));line-height:calc(12px * var(--faiq-font-meta,1))}}

/* v0.25.4: readable hierarchical scope/goal typography without growing the card. */
.decision-scope{font-size:11px;line-height:14px}.decision-goal-overview.compact .decision-goal small{font-size:10.5px}.ai-scope{font-size:10px;line-height:13px}.ai-goal-chip{font-size:10px;line-height:13px;padding:3px 7px}
/* v0.26.3.2: complete per-card goal typography coverage.
   Keep 100% identical to the established desktop/mobile baselines while every
   visible text element inside the goal projection follows the Goals scale. */
.decision-goal-overview .decision-goal-head>span{font-size:calc(14px * var(--faiq-font-goals,1))}
.decision-goal-overview .decision-goal-head>strong{font-size:calc(11px * var(--faiq-font-goals,1))}
.decision-goal-overview .decision-goal b{font-size:calc(11px * var(--faiq-font-goals,1))}
.decision-goal-overview .decision-goal small,.decision-goal-overview.compact .decision-goal small{font-size:calc(10.5px * var(--faiq-font-goals,1))}
.decision-goal-overview .decision-goal-rooms>summary{font-size:calc(10.5px * var(--faiq-font-goals,1))}
.decision-goal-overview .decision-goal-room>summary>strong{font-size:calc(9.5px * var(--faiq-font-goals,1))}
.decision-goal-overview .decision-goal-icon small{font-size:calc(9px * var(--faiq-font-goals,1))}
.decision-goal-overview .decision-goal-room-detail .decision-room-reason span{font-size:calc(10.5px * var(--faiq-font-goals,1));line-height:calc(14px * var(--faiq-font-goals,1))}
@media(max-width:520px){.decision-goal-overview .decision-goal-room-name{font-size:calc(11px * var(--faiq-font-goals,1))}.decision-goal-overview .decision-goal-room>summary>strong{font-size:calc(9px * var(--faiq-font-goals,1))}.decision-goal-overview .decision-goal-icon small{font-size:calc(8.5px * var(--faiq-font-goals,1))}.decision-goal-overview .house-goal-status,.decision-goal-overview .house-goal-eta,.decision-goal-overview .house-goal-blocked{font-size:calc(10px * var(--faiq-font-goals,1))}}

.decision-goal-overview .decision-goal-room.decision-room-disclosure{margin-top:6px;padding-top:0}
.decision-goal-overview .decision-goal-room.decision-room-disclosure:first-child{margin-top:0}

/* Sustained ventilation is deliberately calmer and visually smaller than active airing. */
.ai-compact.continuous .ai-freshy-angle .ai-leaf,.ai-compact.continuous .ai-freshy-angle .ai-leaf-right{width:19px;height:10px;top:23px;opacity:.72}
.ai-compact.continuous .ai-freshy-angle .ai-leaf{left:-11px}.ai-compact.continuous .ai-freshy-angle .ai-leaf-right{right:-9px}
@media(max-width:520px){.decision-scope{font-size:10.5px}.ai-scope,.ai-goal-chip{font-size:9.5px;line-height:12px}.ai-compact.continuous .ai-freshy-angle .ai-leaf,.ai-compact.continuous .ai-freshy-angle .ai-leaf-right{width:17px;height:9px;top:20px}}

/* v0.25.2.36: dark-surface foreground contract. FreshAirIQ owns these dark surfaces,
   so inherited controls and detail/Intelligence content stay readable in light HA themes. */
.dialog{color:#e9f0f4;--primary-text-color:#e9f0f4;--secondary-text-color:#84939e}

/* v0.25.2.29: dashboard text contrast contract. The card uses its own dark surfaces,
   therefore room labels must not inherit a light HA theme's dark primary text. */
.room-title,.room-water strong,.room-value,.room-big,.breakdown-row b,.breakdown-row strong,.ai-room b,.decision-room-disclosure>summary span,.decision-more>summary>span:first-child{color:#e9f0f4}

`;
const FAIQ_DESIGN_CSS = `
/* FreshAirIQ design layer (0.26.3.2): touch targets, tiles, legibility. Appended last on purpose. */
button,summary,.clickable,[data-info],[data-room]{touch-action:manipulation;-webkit-tap-highlight-color:transparent}
.clickable{transition:transform .12s ease,border-color .15s ease,background-color .15s ease}
.clickable:active,.compact-actions .details-btn:active{transform:scale(.985)}
@media (hover:hover){.clickable:hover{border-color:rgba(91,212,255,.4)}}
.details-btn:focus-visible,.close:focus-visible,.info-back:focus-visible,.clickable:focus-visible,[role="button"]:focus-visible,summary:focus-visible,.faiq-render-retry:focus-visible{outline:2px solid #5bd4ff;outline-offset:2px}
@media (prefers-reduced-motion:reduce){.clickable,.details-btn{transition:none}.clickable:active,.compact-actions .details-btn:active{transform:none}}
.close,.info-back{min-width:44px;min-height:44px}
.compact-actions{display:grid;grid-template-columns:repeat(auto-fit,minmax(78px,1fr));gap:8px;justify-content:stretch;margin-top:12px;padding-top:12px}
.compact-actions .details-btn{display:flex;flex-direction:column;align-items:center;justify-content:center;gap:5px;min-height:58px;padding:8px 6px;border-radius:14px;font-size:calc(12px * var(--faiq-font-meta,1));font-weight:800;line-height:1.15;opacity:1;background:rgba(255,255,255,.055);border:1px solid rgba(255,255,255,.12)}
.compact-actions .details-btn ha-icon{--mdc-icon-size:21px;color:#5bd4ff;pointer-events:none}
.compact-actions .details-btn span{pointer-events:none;text-align:center}
.rooms-summary{display:flex;flex-wrap:wrap;gap:8px;margin:0 0 14px}
.rooms-chip{display:inline-flex;align-items:center;gap:6px;min-height:30px;padding:5px 11px;border-radius:999px;font-size:calc(12px * var(--faiq-font-meta,1));font-weight:800;color:#d5e0e7;background:rgba(255,255,255,.05);border:1px solid rgba(255,255,255,.10)}
.rooms-chip ha-icon{--mdc-icon-size:16px}
.rooms-chip.attention{color:#ffcf8a;background:rgba(255,180,95,.09);border-color:rgba(255,180,95,.35)}
.rooms-chip.ok{color:#7fe3a2;background:rgba(98,232,137,.08);border-color:rgba(98,232,137,.30)}
.rooms-chip.water{color:#8fd2ff;background:rgba(91,212,255,.08);border-color:rgba(91,212,255,.28)}
.floor-room-heading{padding:6px 3px 8px;font-size:calc(11px * var(--faiq-font-rooms,1));letter-spacing:.8px;color:#9db2c0}
.rooms-overview .floor-room-content{grid-template-columns:repeat(auto-fill,minmax(min(100%,330px),1fr));gap:10px}
.room{position:relative;padding:13px 14px;border-radius:16px;background:linear-gradient(160deg,#1a252f,#151d25);box-shadow:inset 3px 0 0 var(--status,transparent)}
.room-head{grid-template-columns:46px minmax(0,1fr) auto 18px;gap:11px}
.room-head .muted{font-size:calc(11.5px * var(--faiq-font-rooms,1));line-height:15px}
.room-status{display:inline-flex;align-items:center;margin-top:5px;padding:2px 9px;border-radius:999px;font-size:calc(11px * var(--faiq-font-rooms,1));font-weight:850;line-height:16px;color:var(--status,#9aa7b3);background:rgba(255,255,255,.06);background:color-mix(in srgb,var(--status,#9aa7b3) 13%,transparent);border:1px solid rgba(255,255,255,.14);border:1px solid color-mix(in srgb,var(--status,#9aa7b3) 34%,transparent)}
.room-water strong{font-size:calc(15px * var(--faiq-font-rooms,1))}
.room-stat{padding:9px 10px;border-radius:12px}
.room-stat>div{min-width:0}
.room-stat .tiny{font-size:9.5px;line-height:12px;letter-spacing:.5px}
.room-stat .muted{font-size:10.5px;line-height:13px}
.room-stat .room-value{white-space:normal;overflow-wrap:anywhere;line-height:1.25}
@media(max-width:520px){.room-summary-grid{gap:6px}.room-stat{grid-template-columns:minmax(0,1fr);padding:9px 8px}.room-stat .stat-icon{display:none}.room-stat .tiny{font-size:9px;letter-spacing:.2px;overflow:hidden;text-overflow:ellipsis}.room-stat .muted{white-space:normal;display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden}.goal-pill small.goal-impact{flex-wrap:wrap;row-gap:0}.goal-tracker .goal-sep{display:none}.goal-pill{padding:7px 7px;gap:5px}.room-stat{align-items:start}.goal-pill .goal-impact-note{white-space:normal;display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical}}
.goal-sep{font-style:normal}
.goal-tracker{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:6px;margin:10px 0 0}
.goal-pill{display:flex;align-items:center;gap:6px;min-width:0;padding:7px 8px;border-radius:11px;background:rgba(255,255,255,.04);border:1px solid rgba(255,255,255,.10)}
.goal-pill.reached{background:rgba(98,232,137,.07);border-color:rgba(98,232,137,.28)}
.goal-pill.open{border-style:dashed}
.goal-pill ha-icon{--mdc-icon-size:18px;flex:0 0 18px;color:#aebbc4}
.goal-pill.reached ha-icon{color:#73df99}
.goal-pill>span{display:flex;flex-direction:column;min-width:0;overflow:hidden}
.goal-pill b{display:none}
.goal-pill small{white-space:nowrap}
.goal-impact-note{overflow:hidden;text-overflow:ellipsis;white-space:nowrap;font-size:calc(10px * var(--faiq-font-goals,1))}
.goal-tracker .goal-impact-time{font-size:calc(10px * var(--faiq-font-goals,1))}
.goal-tracker.compact{margin:5px 0}.goal-tracker.compact .goal-pill{padding:4px 6px}
.top .pill[data-info]{position:relative;display:inline-flex;align-items:center;min-height:36px;padding:0 14px;cursor:pointer}
.top .pill[data-info]::after{content:"";position:absolute;inset:-6px -4px}
.ai-scope.clickable{position:relative;align-items:center;gap:2px;padding:4px 10px;margin-bottom:7px;border-radius:999px;cursor:pointer;background:rgba(255,255,255,.04);border:1px solid rgba(255,255,255,.18);border:1px solid color-mix(in srgb,var(--ai,#62e889) 45%,transparent)}
.ai-scope.clickable::after{content:"›";margin-left:4px;font-size:1.25em;line-height:1}
.ai-scope.clickable::before{content:"";position:absolute;inset:-10px -8px}
.ai-all-good{min-height:44px;font-size:calc(11px * var(--faiq-font-meta,1))}
.ai-context button{min-height:48px;align-items:center}
.ai-context b{font-size:calc(11px * var(--faiq-font-meta,1))}
.ai-context small{font-size:calc(9.5px * var(--faiq-font-meta,1))}
.decision-more>summary{min-height:48px}
.decision-goal-overview.compact{padding:6px 12px 4px}
.goal-lines{display:grid;gap:0}
.goal-line{display:flex;align-items:center;gap:8px;min-height:32px;min-width:0}
.goal-line ha-icon{--mdc-icon-size:17px;flex:0 0 17px;color:var(--goal)}
.goal-line b{font-size:calc(13px * var(--faiq-font-goals,1));font-weight:800;color:#e9f0f4;white-space:nowrap}
.goal-line-state{margin-left:auto;min-width:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;text-align:right;font-size:calc(12px * var(--faiq-font-goals,1));font-weight:650;color:#a9b8c2}
.goal-line.reached ha-icon,.goal-line.reached .goal-line-state{color:#73df99}
.goal-line.blocked ha-icon,.goal-line.blocked .goal-line-state{color:#e2bd69}
.decision-goal-overview .decision-goal-rooms{margin-top:4px;padding-top:2px;border-top:1px solid rgba(255,255,255,.07)}
.decision-goal-overview .decision-goal-rooms>summary{min-height:36px;padding:2px 0;font-size:calc(12px * var(--faiq-font-goals,1));font-weight:800;color:#9fb1bc}
.decision-goal-overview .decision-goal-room-list{margin-top:0;padding-top:0}
.decision-goal-overview .decision-goal-room,.decision-goal-overview .decision-goal-room.decision-room-disclosure{--room-detail:#63d2f7;margin:0;border:0;border-top:1px solid rgba(255,255,255,.06);border-radius:0;background:none}
.decision-goal-overview .decision-goal-room>summary{display:grid;grid-template-columns:minmax(0,1fr) auto 16px;column-gap:8px;row-gap:0;align-items:center;min-height:40px;padding:6px 0 8px}
.decision-goal-overview .decision-goal-room>summary .decision-goal-room-name{font-size:calc(13px * var(--faiq-font-goals,1));font-weight:750;color:#e9f0f4}
.decision-goal-overview .decision-goal-room>summary .goal-room-status{font-size:calc(12px * var(--faiq-font-goals,1));font-weight:650;color:#8fc9ec;white-space:nowrap}
.decision-goal-overview .decision-goal-room>summary .goal-room-status.reached{color:#73df99}
.decision-goal-overview .decision-goal-room>summary .goal-room-status.blocked{color:#e2bd69}
.decision-goal-overview .decision-goal-room>summary .goal-room-note{grid-column:1/-1;margin-top:1px;font-size:calc(11px * var(--faiq-font-goals,1));font-weight:600;color:#cfae62;white-space:normal}
.decision-goal-overview .decision-goal-room>summary .decision-goal-chevron{--mdc-icon-size:16px;color:#7f929e}
.decision-goal-room-detail{padding:0 0 10px}
.decision-goal-room-detail .decision-section-title{margin-top:12px}
.goal-room-goals{display:grid;gap:2px;margin:6px 0}
.goal-room-goal{display:grid;grid-template-columns:20px minmax(0,1fr);gap:8px;align-items:center;padding:4px 0}
.goal-room-goal ha-icon{--mdc-icon-size:16px;color:#c8d6de}
.goal-room-goal>span{display:grid;gap:1px;min-width:0}
.goal-room-goal b{font-size:calc(12.5px * var(--faiq-font-goals,1));color:#eef4f7}
.goal-room-goal small{font-size:calc(11.5px * var(--faiq-font-goals,1));color:#b2c0c9}
.goal-room-goal.reached small{color:#73df99}
.goal-room-goal.blocked small{color:#ecca7f}
.goal-room-priority{margin:2px 0 8px;font-size:calc(11.5px * var(--faiq-font-goals,1));color:#9fb1bc}
.decision-goal-overview .decision-goal-explain{color:#ecca7f;font-size:calc(11.5px * var(--faiq-font-goals,1));line-height:1.4}
.faiq-consent{display:flex;align-items:center;gap:10px;margin:0 0 10px;padding:8px 10px 8px 12px;border-radius:12px;background:rgba(91,212,255,.06);border:1px solid rgba(91,212,255,.22)}
.faiq-consent>ha-icon{--mdc-icon-size:18px;flex:0 0 18px;color:#5bd4ff}
.faiq-consent-text{flex:1 1 auto;min-width:0;font-size:calc(12px * var(--faiq-font-meta,1));line-height:1.35;color:#b8c6cf}
.faiq-consent-text b{color:#e9f0f4}
.faiq-consent-link{appearance:none;border:0;background:none;padding:0;margin:0;color:#8fd2ff;font:inherit;font-weight:700;text-decoration:underline;cursor:pointer}
.faiq-consent-actions{display:flex;gap:6px;flex:0 0 auto}
.faiq-consent-actions button{appearance:none;min-height:36px;min-width:52px;padding:0 12px;border-radius:10px;border:1px solid rgba(255,255,255,.16);background:rgba(255,255,255,.05);color:#e9f0f4;font:inherit;font-size:calc(12px * var(--faiq-font-meta,1));font-weight:800;cursor:pointer}
.faiq-consent-actions button.primary{background:#5bd4ff;border-color:#5bd4ff;color:#06222e}
.faiq-consent-actions button:disabled{opacity:.55;cursor:default}
@media(max-width:430px){.faiq-consent{flex-wrap:wrap}.faiq-consent-actions{width:100%;justify-content:flex-end}}
.faiq-render-notice{display:flex;gap:12px;align-items:center;justify-content:space-between;margin:0 0 12px;padding:12px 14px;border-radius:14px;background:rgba(255,119,112,.10);border:1px solid rgba(255,119,112,.40);color:#ffd9d6}
.faiq-render-notice>div{display:grid;gap:3px;min-width:0}
.faiq-render-notice b{font-size:14px;line-height:18px}
.faiq-render-notice span{font-size:11.5px;line-height:15px;color:#f0bdb9;word-break:break-word}
.faiq-render-retry{flex:0 0 auto;min-height:44px;padding:0 14px;border-radius:12px;border:1px solid rgba(255,255,255,.20);background:rgba(255,255,255,.08);color:inherit;font:inherit;font-weight:800;cursor:pointer}
/* 0.26.4.1: diagnostics buttons. Icon on the left, two clean text lines, equal width –
   the bold and plain parts no longer wrap into each other. */
.settings-room-actions #diagnostics-export,.settings-room-actions #diagnostics-send{flex:1 1 0;min-width:0;min-height:58px;display:grid;grid-template-columns:auto minmax(0,1fr);grid-template-rows:auto auto;column-gap:10px;row-gap:2px;align-items:center;justify-items:start;justify-content:stretch;text-align:left;padding:10px 14px;line-height:1.2}
.settings-room-actions #diagnostics-export ha-icon,.settings-room-actions #diagnostics-send ha-icon{grid-row:1 / 3;align-self:center;--mdc-icon-size:20px}
.settings-room-actions #diagnostics-export b,.settings-room-actions #diagnostics-send b{font-size:13px;font-weight:800;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;max-width:100%}
.settings-room-actions #diagnostics-export span,.settings-room-actions #diagnostics-send span{font-size:12px;font-weight:600;opacity:.78;white-space:normal;max-width:100%}
@media(max-width:380px){.settings-room-actions:has(#diagnostics-send){flex-direction:column}}
`;
const FAIQ_FRESHY_CSS = `
/* ---- Freshy character (0.26.4) ---- */
.fr{display:block;overflow:visible}
.fr .fr-face,.fr .frx,.fr .fr-halo-run{display:none}
.fr .fr-whole{transform-box:view-box;transform-origin:96px 70px}
.fr .fr-body{transform-box:view-box;transform-origin:96px 70px;animation:frBreathe 4.2s ease-in-out infinite}
.fr .fr-leaves{transform-box:view-box;transform-origin:54px 72px;animation:frSway 3.4s ease-in-out infinite alternate}
.fr .fr-eye{transform-box:fill-box;transform-origin:center;animation:frBlink 5.5s infinite}
.fr .fr-halo{stroke:#7FE3FF}
.fr text{font-family:inherit}
@keyframes frBreathe{0%,100%{transform:scale(1)}50%{transform:scale(1.035)}}
@keyframes frSway{0%{transform:rotate(-5deg)}100%{transform:rotate(5deg)}}
@keyframes frFlutter{0%{transform:rotate(-12deg)}100%{transform:rotate(10deg)}}
@keyframes frFan{0%{transform:rotate(-24deg)}100%{transform:rotate(14deg)}}
@keyframes frBlink{0%,93%,100%{transform:scaleY(1)}96%{transform:scaleY(.12)}}
@keyframes frPulse{0%,100%{stroke-opacity:1;stroke-width:3.4}50%{stroke-opacity:.45;stroke-width:5.5}}
@keyframes frWind{0%{transform:translateX(16px);opacity:0}30%{opacity:.9}100%{transform:translateX(-26px);opacity:0}}
@keyframes frOut{0%{transform:translate(0,0) scale(.6);opacity:0}25%{opacity:1}100%{transform:translate(26px,-30px) scale(1);opacity:0}}
@keyframes frNod{0%,60%,100%{transform:translateY(0)}70%{transform:translateY(5px)}80%{transform:translateY(0)}88%{transform:translateY(3px)}}
@keyframes frDraw{0%,20%{stroke-dashoffset:40}60%,100%{stroke-dashoffset:0}}
@keyframes frZ{0%{transform:translate(0,6px);opacity:0}30%{opacity:1}100%{transform:translate(8px,-18px);opacity:0}}
@keyframes frRain{0%{transform:translateY(-30px);opacity:0}15%{opacity:.9}100%{transform:translateY(120px);opacity:0}}
@keyframes frSweat{0%,30%{transform:translateY(0);opacity:0}45%{opacity:1}100%{transform:translateY(18px);opacity:0}}
@keyframes frWobble{0%,100%{transform:rotate(0)}25%{transform:rotate(-3deg)}75%{transform:rotate(3deg)}}
@keyframes frFlicker{0%,100%{stroke-opacity:.9}40%{stroke-opacity:.25}45%{stroke-opacity:.8}60%{stroke-opacity:.3}}
@keyframes frBob{0%,100%{transform:translateY(0)}50%{transform:translateY(-5px)}}
@keyframes frSneeze{0%,70%,100%{transform:translate(0,0) scale(1)}76%{transform:translate(-3px,2px) scale(1.04,.96)}82%{transform:translate(5px,-2px) scale(.97,1.03)}90%{transform:translate(0,0)}}
@keyframes frFloat{0%{transform:translate(0,0);opacity:0}30%{opacity:1}100%{transform:translate(-14px,-22px);opacity:0}}
@keyframes frThink{0%,10%{opacity:0;transform:scale(.4)}25%,85%{opacity:1;transform:scale(1)}100%{opacity:0;transform:scale(1)}}
.fr-ok .fr-face-happy,.fr-done .fr-face-happy,.fr-rain .fr-face-happy,.fr-cool .fr-face-happy,.fr-learn .fr-face-happy{display:inline}
.fr-act .fr-face-awake,.fr-run .fr-face-awake{display:inline}
.fr-night .fr-face-sleep{display:inline}
.fr-mould .fr-face-worry,.fr-sensor .fr-face-worry{display:inline}
.fr-pollen .fr-face-squint{display:inline}
.fr-act .fr-halo{stroke:#F0B357;animation:frPulse 1.6s ease-in-out infinite}
.fr-act .fr-leaves{animation:frFlutter .7s ease-in-out infinite alternate}
.fr-act .frx-wind,.fr-run .frx-wind{display:inline}
.fr-run .fr-halo{display:none}
.fr-run .fr-halo-run{display:inline}
.fr-run .fr-leaves{animation:frFlutter .9s ease-in-out infinite alternate}
.fr-run .frx-out{display:inline}
.fr-done .fr-halo{stroke:#8FD8A6}
.fr-done .fr-whole{animation:frNod 2.6s ease-in-out infinite}
.fr-done .frx-check{display:inline}
.fr-night .fr-body{animation-duration:6.5s}
.fr-night .fr-halo{stroke:#4C79A8;stroke-opacity:.8}
.fr-night .fr-leaves{animation-duration:6s}
.fr-night .frx-z{display:inline}
.fr-rain .fr-leaf-big{display:none}
.fr-rain .frx-rain,.fr-rain .frx-umbrella{display:inline}
.fr-cool .fr-leaves{animation:frFan .45s ease-in-out infinite alternate}
.fr-cool .frx-sweat{display:inline}
.fr-mould .fr-halo{stroke:#F0B357}
.fr-mould .fr-whole{animation:frWobble 1.8s ease-in-out infinite}
.fr-sensor .fr-halo{stroke:#9AA9B5;animation:frFlicker 2.4s linear infinite}
.fr-sensor .frx-q{display:inline}
.fr-pollen .fr-whole{animation:frSneeze 3.2s ease-in-out infinite}
.fr-pollen .frx-pollen{display:inline}
.fr-learn .frx-think{display:inline}
.fr .frx-wind path{animation:frWind 1.6s linear infinite}
.fr .frx-wind path:nth-child(2){animation-delay:.5s}
.fr .frx-wind path:nth-child(3){animation-delay:1s}
.fr .frx-out path{transform-box:fill-box;animation:frOut 2.2s ease-out infinite}
.fr .frx-out path:nth-child(2){animation-delay:.7s}
.fr .frx-out path:nth-child(3){animation-delay:1.4s}
.fr .frx-check path{stroke-dasharray:40;animation:frDraw 2.6s ease-out infinite}
.fr .frx-z text{animation:frZ 3s ease-out infinite}
.fr .frx-z text:nth-child(2){animation-delay:1.5s}
.fr .frx-rain path{animation:frRain 1.1s linear infinite}
.fr .frx-rain path:nth-child(2){animation-delay:.3s}
.fr .frx-rain path:nth-child(3){animation-delay:.65s}
.fr .frx-rain path:nth-child(4){animation-delay:.85s}
.fr .frx-rain path:nth-child(5){animation-delay:.15s}
.fr .frx-sweat path{animation:frSweat 2.4s ease-in infinite}
.fr .frx-q text{animation:frBob 1.6s ease-in-out infinite}
.fr .frx-pollen circle{animation:frFloat 3s ease-out infinite}
.fr .frx-pollen circle:nth-child(2){animation-delay:1s}
.fr .frx-pollen circle:nth-child(3){animation-delay:2s}
.fr .frx-think circle{transform-box:fill-box;transform-origin:center;animation:frThink 3s ease-out infinite}
.fr .frx-think circle:nth-child(2){animation-delay:.4s}
.fr .frx-think circle:nth-child(3){animation-delay:.8s}
@media (prefers-reduced-motion: reduce){.fr *{animation:none!important}}

/* 0.26.4.1: the animated Freshy lives in the IQ hero, sized so it never becomes tiny. */
.ai-assistant{grid-template-columns:112px minmax(0,1fr) 28px}
.ai-mascot-wrap.fr-wrap{width:112px;height:98px;display:flex;align-items:center;justify-content:center;overflow:visible;contain:none;perspective:none;background:none}
.ai-mascot-wrap.fr-wrap .fr{width:112px;height:98px}
@media(max-width:520px){.ai-assistant{grid-template-columns:96px minmax(0,1fr) 22px}.ai-mascot-wrap.fr-wrap,.ai-mascot-wrap.fr-wrap .fr{width:96px;height:84px}}
`;
// ---------------------------------------------------------------------------
// Freshy (0.26.4): the FreshAirIQ mascot as an animated vector character.
// One drawing, eleven moods. The mood only switches CSS classes; every motion
// lives in FAIQ_FRESHY_CSS and stops under prefers-reduced-motion.
// ---------------------------------------------------------------------------
const FRESHY_MOODS = ["ok", "act", "run", "done", "night", "rain", "cool", "mould", "sensor", "pollen", "learn"];
const FRESHY_LABELS = {
    de: { ok: "Freshy ist zufrieden", act: "Freshy möchte, dass du lüftest", run: "Freshy lüftet mit", done: "Freshy nickt: Ziel erreicht", night: "Freshy schläft", rain: "Freshy hält ein Blatt als Schirm", cool: "Freshy fächelt sich Luft zu", mould: "Freshy ist besorgt", sensor: "Freshy vermisst einen Sensor", pollen: "Freshy niest", learn: "Freshy denkt nach" },
    en: { ok: "Freshy is happy", act: "Freshy wants you to air the rooms", run: "Freshy is airing with you", done: "Freshy nods: goal reached", night: "Freshy is asleep", rain: "Freshy holds a leaf as an umbrella", cool: "Freshy fans itself", mould: "Freshy is worried", sensor: "Freshy misses a sensor", pollen: "Freshy sneezes", learn: "Freshy is thinking" },
};
function freshySvg(mood, size = 150, lang = "de", progress = null) {
    const m = FRESHY_MOODS.includes(mood) ? mood : "ok";
    const w = Math.round(size), h = Math.round(size * 140 / 160);
    const label = (FRESHY_LABELS[lang] || FRESHY_LABELS.de)[m];
    // Progress ring (mood "run"): circumference of r=49 is ~308.
    const p = Math.max(0, Math.min(1, Number.isFinite(Number(progress)) ? Number(progress) : 0.6));
    const dash = `${Math.round(308 * p)} 308`;
    return `<svg class="fr fr-${m}" width="${w}" height="${h}" viewBox="0 0 160 140" role="img" aria-label="${esc(label)}">
<defs>
<radialGradient id="frBody" cx="38%" cy="32%" r="75%"><stop offset="0%" stop-color="#123447"></stop><stop offset="45%" stop-color="#06141E"></stop><stop offset="100%" stop-color="#020609"></stop></radialGradient>
<filter id="frGlow" x="-40%" y="-40%" width="180%" height="180%"><feGaussianBlur stdDeviation="4.2" result="b"></feGaussianBlur><feMerge><feMergeNode in="b"></feMergeNode><feMergeNode in="SourceGraphic"></feMergeNode></feMerge></filter>
<filter id="frSoft" x="-40%" y="-40%" width="180%" height="180%"><feGaussianBlur stdDeviation="1.4" result="b"></feGaussianBlur><feMerge><feMergeNode in="b"></feMergeNode><feMergeNode in="SourceGraphic"></feMergeNode></feMerge></filter>
</defs>
<g class="frx frx-rain" stroke="#7DD3E8" stroke-width="2" stroke-linecap="round" opacity=".85"><path d="M18 10v9"></path><path d="M38 0v9"></path><path d="M148 6v9"></path><path d="M134 0v9"></path><path d="M8 30v9"></path></g>
<g class="fr-whole">
<g class="fr-leaves">
<path d="M55 76 C 46 82, 38 92, 29 104" fill="none" stroke="#6EE7B7" stroke-width="3" stroke-linecap="round"></path>
<g class="fr-leaf-big"><path d="M53 69 C 28 66, 9 45, 13 15 C 41 19, 58 41, 53 69 Z" fill="#6EE7B7"></path><path d="M51 65 C 40 52, 27 36, 16 19" fill="none" stroke="#A8F5D6" stroke-width="1.6" stroke-linecap="round"></path></g>
<path d="M31 101 C 17 97, 8 106, 10 120 C 25 122, 34 113, 31 101 Z" fill="#6EE7B7"></path>
<path d="M29 104 C 23 109, 17 113, 12 118" fill="none" stroke="#A8F5D6" stroke-width="1.3" stroke-linecap="round"></path>
</g>
<g class="fr-body">
<circle class="fr-halo" cx="96" cy="70" r="49.5" fill="none" stroke-width="5" stroke-opacity=".35" filter="url(#frGlow)"></circle>
<circle class="fr-halo" cx="96" cy="70" r="49" fill="none" stroke-width="3.4" filter="url(#frGlow)"></circle>
<g class="fr-halo-run"><circle cx="96" cy="70" r="49" fill="none" stroke="#1E3A4C" stroke-width="5"></circle><circle cx="96" cy="70" r="49" fill="none" stroke="#7DD3E8" stroke-width="5" stroke-linecap="round" stroke-dasharray="${dash}" transform="rotate(-90 96 70)" filter="url(#frGlow)"></circle></g>
<circle cx="96" cy="70" r="45" fill="url(#frBody)"></circle>
<circle cx="96" cy="70" r="44" fill="none" stroke="#7FE3FF" stroke-opacity=".22" stroke-width="1.5"></circle>
<path d="M66 44 C 74 34, 88 29, 100 29" fill="none" stroke="#BFF3FF" stroke-opacity=".18" stroke-width="3" stroke-linecap="round"></path>
<g class="fr-face fr-face-happy" filter="url(#frSoft)"><path class="fr-eye" d="M77 72 C 77 58, 99 58, 99 72 C 92 68.5, 84 68.5, 77 72 Z" fill="#D6FAFF"></path><path class="fr-eye" d="M106 68 C 108 59, 121 59, 123 68" fill="none" stroke="#A6F1FF" stroke-width="3.2" stroke-linecap="round"></path><path d="M100 82 C 104 87, 110 87, 114 82" fill="none" stroke="#9FEFFF" stroke-width="2.4" stroke-linecap="round"></path></g>
<g class="fr-face fr-face-awake" filter="url(#frSoft)"><ellipse class="fr-eye" cx="91" cy="66" rx="5.5" ry="7.5" fill="#CFF8FF"></ellipse><ellipse class="fr-eye" cx="113" cy="64" rx="5" ry="7" fill="#CFF8FF"></ellipse><circle cx="93" cy="63" r="1.6" fill="#06141E"></circle><circle cx="115" cy="61" r="1.5" fill="#06141E"></circle><path d="M100 82 C 104 87, 110 87, 114 82" fill="none" stroke="#9FEFFF" stroke-width="2.4" stroke-linecap="round"></path></g>
<g class="fr-face fr-face-sleep" filter="url(#frSoft)"><path d="M81 67 C 85 72, 92 72, 96 67" fill="none" stroke="#9FEFFF" stroke-width="2.6" stroke-linecap="round"></path><path d="M106 65 C 110 70, 116 70, 120 65" fill="none" stroke="#9FEFFF" stroke-width="2.6" stroke-linecap="round"></path><circle cx="106" cy="83" r="2.6" fill="none" stroke="#9FEFFF" stroke-width="2"></circle></g>
<g class="fr-face fr-face-worry" filter="url(#frSoft)"><path d="M81 58 L 94 54" stroke="#9FEFFF" stroke-width="2.2" stroke-linecap="round"></path><path d="M106 54 L 119 58" stroke="#9FEFFF" stroke-width="2.2" stroke-linecap="round"></path><ellipse class="fr-eye" cx="89" cy="67" rx="4.5" ry="5.5" fill="#CFF8FF"></ellipse><ellipse class="fr-eye" cx="113" cy="67" rx="4.5" ry="5.5" fill="#CFF8FF"></ellipse><path d="M98 85 C 101 82, 104 82, 107 85 C 110 88, 113 88, 116 85" fill="none" stroke="#9FEFFF" stroke-width="2.2" stroke-linecap="round"></path></g>
<g class="fr-face fr-face-squint" filter="url(#frSoft)"><path d="M82 61 L 94 66 L 82 71" fill="none" stroke="#9FEFFF" stroke-width="2.6" stroke-linecap="round" stroke-linejoin="round"></path><path d="M121 59 L 109 64 L 121 69" fill="none" stroke="#9FEFFF" stroke-width="2.6" stroke-linecap="round" stroke-linejoin="round"></path><ellipse cx="106" cy="84" rx="4" ry="3.4" fill="#9FEFFF"></ellipse></g>
</g>
<g class="frx frx-umbrella"><path d="M96 22 L 96 12" stroke="#6EE7B7" stroke-width="2.6" stroke-linecap="round"></path><path d="M58 22 C 72 0, 120 0, 134 22 C 118 16, 74 16, 58 22 Z" fill="#6EE7B7"></path><path d="M62 20 C 80 10, 112 10, 130 20" fill="none" stroke="#A8F5D6" stroke-width="1.4" stroke-linecap="round"></path></g>
</g>
<g class="frx frx-wind" fill="none" stroke="#B9EEFA" stroke-width="2.2" stroke-linecap="round"><path d="M158 40 C 150 36, 144 44, 136 40"></path><path d="M160 70 C 152 66, 146 74, 140 70"></path><path d="M156 100 C 148 96, 142 104, 134 100"></path></g>
<g class="frx frx-out" fill="#7DD3E8"><path d="M128 46 C 128 46, 123 52, 123 55 a5 5 0 0 0 10 0 C 133 52, 128 46, 128 46 Z"></path><path d="M134 64 C 134 64, 130 69, 130 71 a4 4 0 0 0 8 0 C 138 69, 134 64, 134 64 Z"></path><path d="M124 30 C 124 30, 120 35, 120 37 a4 4 0 0 0 8 0 C 128 35, 124 30, 124 30 Z"></path></g>
<g class="frx frx-check"><circle cx="140" cy="28" r="13" fill="#173A2A" stroke="#8FD8A6" stroke-width="2"></circle><path d="M134 28 L 139 33 L 147 23" fill="none" stroke="#8FD8A6" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"></path></g>
<g class="frx frx-z" fill="#9FC3E6" font-weight="800"><text x="132" y="34" font-size="15">z</text><text x="142" y="22" font-size="11">z</text></g>
<g class="frx frx-sweat"><path d="M140 46 C 140 46, 136 51, 136 54 a4 4 0 0 0 8 0 C 144 51, 140 46, 140 46 Z" fill="#7DD3E8"></path></g>
<g class="frx frx-q" fill="#C9D6DE" font-weight="800"><text x="134" y="34" font-size="24">?</text></g>
<g class="frx frx-pollen" fill="#F0D36B"><circle cx="146" cy="78" r="3"></circle><circle cx="138" cy="94" r="2.4"></circle><circle cx="150" cy="56" r="2.2"></circle></g>
<g class="frx frx-think" fill="#BFF3FF"><circle cx="132" cy="36" r="3"></circle><circle cx="141" cy="25" r="4"></circle><circle cx="152" cy="12" r="5"></circle></g>
</svg>`;
}

class FreshAirIQCard extends HTMLElement {
    static getStubConfig() { return { dashboard_variant: "classic" }; }
    constructor() { super(); this.attachShadow({ mode: "open" }); this._config = {}; this._pageScrollSnapshot = null; this._viewportRestoreToken = 0; this._hass = null; this._dialogOpen = false; this._info = null; this._infoStack = []; this._infoScrollStack = []; this._dialogScrollTop = 0; this._subdialogScrollTop = 0; this._pendingSubdialogScrollTop = null; this._forceDialogTop = false; this._postResultTimer = null; this._settingsData = null; this._settingsLoading = false; this._settingsSaving = false; this._settingsError = null; this._settingsNotice = null; this._lastSupportError = null; this._renderFrame = null; this._renderFrameIsRaf = false; this._liveRefreshFrame = null; this._liveRefreshFrameIsRaf = false; this._statusEntityId = null; this._statusRescanNeeded = false; this._relevantStateIds = null; this._roomEntityIds = null; this._roomConfigSignature = null; this._entityCache = {}; this._profileOverride = null; this._forecastOverride = null; this._fieldTestRegistrationPromise = null; this._fieldTestSessionClientId = null; this._liveViewSnapshot = null; this._liveHtmlCache = {}; this._chartCache = { bars: new WeakMap(), line: new WeakMap() }; this._learningCardCache = null; this._compactExpanded = null; this._classicDisclosureOpen = new Set(); }
    _uiLanguage() {
        const raw = String((this._hass && (this._hass.language || this._hass.locale?.language)) || navigator.language || "en").toLowerCase();
        return raw.startsWith("de") ? "de" : "en";
    }
    _t(key, vars = {}) {
        const entry = FAIQ_UI[key];
        if (!entry) return key;
        let out = String(entry[this._uiLanguage()] ?? entry.en ?? entry.de ?? key);
        for (const [name, value] of Object.entries(vars)) out = out.split(`{${name}}`).join(String(value));
        return out;
    }
    _localizeLegacyFragment(root) {
        if (!root || this._uiLanguage() === "de") return;
        const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT);
        const nodes = [];
        while (walker.nextNode()) nodes.push(walker.currentNode);
        for (const node of nodes) {
            const parent = node.parentElement;
            if (parent && ["STYLE", "SCRIPT"].includes(parent.tagName)) continue;
            const translated = faiqEnglishText(node.nodeValue);
            if (translated !== node.nodeValue) node.nodeValue = translated;
        }
        root.querySelectorAll?.("[title],[placeholder],[aria-label]").forEach(el => {
            for (const attr of ["title", "placeholder", "aria-label"]) {
                if (!el.hasAttribute(attr)) continue;
                const before = el.getAttribute(attr) || "";
                const after = faiqEnglishText(before);
                if (after !== before) el.setAttribute(attr, after);
            }
        });
    }
    _captureOverlayViewport() {
        const nodes = [];
        const seen = new Set();
        const remember = node => {
            if (!node || seen.has(node)) return;
            try {
                const cs = getComputedStyle(node);
                if (/(auto|scroll)/.test(`${cs.overflowY} ${cs.overflow}`) && node.scrollHeight > node.clientHeight) {
                    seen.add(node); nodes.push([node, node.scrollTop, node.scrollLeft]);
                }
            } catch (_) {}
        };
        // Follow the composed tree, not only light-DOM parents. Home Assistant
        // dashboards place the card below several nested shadow-root scrollers.
        let node = this;
        while (node) {
            const root = node.getRootNode?.();
            const parent = node.parentElement || (root && root.host) || null;
            if (!parent) break;
            remember(parent);
            const parentRoot = parent.getRootNode?.();
            if (parentRoot && parentRoot.querySelectorAll) parentRoot.querySelectorAll('*').forEach(remember);
            node = parent;
        }
        remember(document.scrollingElement); remember(document.documentElement); remember(document.body);
        this._viewportRestoreToken += 1;
        this._pageScrollSnapshot = { x: window.scrollX, y: window.scrollY, nodes, token: this._viewportRestoreToken };
    }
    _restoreOverlayViewport() {
        const snap = this._pageScrollSnapshot; if (!snap) return;
        const token = snap.token;
        const restore = () => {
            if (!this._pageScrollSnapshot || this._pageScrollSnapshot.token !== token) return;
            for (const [node, top, left] of snap.nodes || []) if (node?.isConnected) { node.scrollTop = top; node.scrollLeft = left; }
            window.scrollTo(snap.x || 0, snap.y || 0);
        };
        // HA/WebView can perform layout/focus scrolling after the overlay has been
        // removed. Keep the immutable snapshot alive through that complete phase.
        restore();
        requestAnimationFrame(() => { restore(); requestAnimationFrame(restore); });
        [50, 150, 350].forEach(ms => setTimeout(restore, ms));
        setTimeout(() => { if (this._pageScrollSnapshot?.token === token) this._pageScrollSnapshot = null; }, 450);
    }
    _rememberInfoViewport(view = this._info) {
        if (!this._infoScrollByView) this._infoScrollByView = new Map();
        if (!view) return 0;
        const current = this.shadowRoot?.querySelector(".subdialog");
        const top = current ? current.scrollTop : (this._infoScrollByView.get(view) ?? this._subdialogScrollTop ?? 0);
        this._infoScrollByView.set(view, top);
        return top;
    }
    _pushInfoViewport() {
        if (this._info) {
            this._infoStack.push(this._info);
            this._infoScrollStack.push(this._rememberInfoViewport(this._info));
        }
    }
    _resetInfoNavigation() { this._infoStack = []; this._infoScrollStack = []; if (this._infoScrollByView) this._infoScrollByView.clear(); this._subdialogScrollTop = 0; this._pendingSubdialogScrollTop = null; }
    _installAndroidTouchScroll(scroller) {
        if (!scroller || !/Android/i.test(navigator.userAgent || "")) return;
        let startY = 0, startTop = 0, dragging = false;
        scroller.addEventListener("touchstart", e => {
            if (!e.touches || e.touches.length !== 1) return;
            startY = e.touches[0].clientY; startTop = scroller.scrollTop; dragging = false;
        }, { passive: true });
        scroller.addEventListener("touchmove", e => {
            if (!e.touches || e.touches.length !== 1 || scroller.scrollHeight <= scroller.clientHeight) return;
            const delta = startY - e.touches[0].clientY;
            if (!dragging && Math.abs(delta) < 4) return;
            dragging = true;
            const max = Math.max(0, scroller.scrollHeight - scroller.clientHeight);
            const next = Math.max(0, Math.min(max, startTop + delta));
            if (next !== scroller.scrollTop) scroller.scrollTop = next;
            if (e.cancelable) e.preventDefault();
            e.stopPropagation();
        }, { passive: false });
    }
    _closeOverlayToCard() {
        this._dialogOpen = false; this._info = null; this._resetInfoNavigation();
        this._render(); this._restoreOverlayViewport();
    }
    _feedbackClientContext() {
        // Keep feedback and diagnostic uploads on one platform/access contract.
        // A browser is an access mode, not an operating-system platform.
        const context = this._fieldTestClientContext();
        return {
            client_id: context.client_id,
            platform_family: context.platform_family,
            device_class: context.device_class,
            companion_app: context.companion_app,
            browser_family: context.browser_family,
            viewport_css_px: context.viewport_css_px,
            device_pixel_ratio: context.device_pixel_ratio,
        };
    }
    _ensureStaticStyle() {
        if (!this.shadowRoot) return null;
        let style = this.shadowRoot.getElementById("faiq-static-style");
        if (!style) {
            style = document.createElement("style");
            style.id = "faiq-static-style";
            style.textContent = FAIQ_CARD_CSS + FAIQ_AI_COMPACT_CSS + FAIQ_COMPACT_DISCLOSURE_CSS + FAIQ_DESIGN_CSS + FAIQ_FRESHY_CSS;
            this.shadowRoot.prepend(style);
        }
        return style;
    }
    _replaceRenderedContent(html) {
        const style = this._ensureStaticStyle();
        if (!style || !this.shadowRoot) return;
        let node = style.nextSibling;
        while (node) {
            const next = node.nextSibling;
            this.shadowRoot.removeChild(node);
            node = next;
        }
        const template = document.createElement("template");
        template.innerHTML = html;
        this._localizeLegacyFragment(template.content);
        this.shadowRoot.appendChild(template.content);
    }
    disconnectedCallback() { if (this._postResultTimer) clearTimeout(this._postResultTimer); this._postResultTimer = null; this._cancelQueuedRender(); this._cancelQueuedLiveRefresh(); }
    _fieldTestClientId() {
        const storageKey = "freshairiq.field_test.client_id";
        try {
            let value = window.localStorage.getItem(storageKey);
            if (!value || !value.startsWith("faiq-client-")) {
                const token = (window.crypto && typeof window.crypto.randomUUID === "function")
                    ? window.crypto.randomUUID().replaceAll("-", "")
                    : `${Date.now().toString(36)}${Math.random().toString(36).slice(2, 18)}`;
                value = `faiq-client-${token}`;
                window.localStorage.setItem(storageKey, value);
            }
            return { id: value, persistence: "localStorage" };
        }
        catch (_) {
            if (!this._fieldTestSessionClientId) {
                const token = (window.crypto && typeof window.crypto.randomUUID === "function")
                    ? window.crypto.randomUUID().replaceAll("-", "")
                    : `${Date.now().toString(36)}${Math.random().toString(36).slice(2, 18)}`;
                this._fieldTestSessionClientId = `faiq-client-session-${token}`;
            }
            return { id: this._fieldTestSessionClientId, persistence: "session" };
        }
    }
    _formatApiError(err, fallback = "Unbekannter Fehler") {
        const candidates = [err?.body, err?.message, err?.error, err];
        for (const value of candidates) {
            if (typeof value === "string" && value.trim() && value.trim() !== "[object Object]") return value.trim();
            if (value && typeof value === "object") {
                const code = value.error_code || value.code; const msg = value.error || value.message || value.detail;
                if (typeof msg === "string" && msg.trim()) return `${msg.trim()}${code ? ` (${code})` : ""}`;
            }
        }
        return fallback;
    }

    _fieldTestClientContext() {
        const nav = window.navigator || {};
        const ua = String(nav.userAgent || "");
        const rawPlatform = String((nav.userAgentData && nav.userAgentData.platform) || nav.platform || "");
        const touchPoints = Number(nav.maxTouchPoints || 0);
        const isIPad = /iPad/i.test(ua) || (/MacIntel/i.test(rawPlatform) && touchPoints > 1);
        const isIPhone = /iPhone|iPod/i.test(ua);
        const isAndroid = /Android/i.test(ua);
        let platformFamily = "Other", deviceClass = "other", deviceFamily = null, deviceModel = null, osVersion = null;
        if (isIPad) {
            platformFamily = "iPadOS"; deviceClass = "tablet"; deviceFamily = "iPad"; deviceModel = "iPad";
        } else if (isIPhone) {
            platformFamily = "iOS"; deviceClass = "phone"; deviceFamily = "iPhone"; deviceModel = "iPhone";
        } else if (isAndroid) {
            platformFamily = "Android";
            deviceClass = /Mobile/i.test(ua) ? "phone" : "tablet";
            deviceFamily = deviceClass === "phone" ? "Android phone" : "Android tablet";
            const androidDetails = ua.match(/\(Linux;\s*Android\s+[^;\)]+;\s*([^\)]+)\)/i);
            if (androidDetails && androidDetails[1]) {
                const segments = androidDetails[1].split(";").map(part => part.trim()).filter(Boolean);
                const candidate = segments.find(part =>
                    !/^wv$/i.test(part) &&
                    !/^[a-z]{2}[-_][A-Z]{2}$/i.test(part) &&
                    !/^Build\//i.test(part)
                );
                if (candidate && candidate !== "K") deviceModel = candidate.replace(/\s+Build\/.*$/i, "").trim() || null;
            }
        } else if (/Windows/i.test(ua) || /Win/i.test(rawPlatform)) {
            platformFamily = "Windows"; deviceClass = "desktop"; deviceFamily = "PC";
        } else if (/Macintosh|Mac OS X/i.test(ua) || /Mac/i.test(rawPlatform)) {
            platformFamily = "macOS"; deviceClass = "desktop"; deviceFamily = "Mac";
        } else if (/Linux/i.test(ua) || /Linux/i.test(rawPlatform)) {
            platformFamily = "Linux"; deviceClass = "desktop"; deviceFamily = "Linux PC";
        }
        if (platformFamily === "iOS" || platformFamily === "iPadOS") {
            const match = ua.match(/(?:CPU(?: iPhone)? OS|iPhone OS)\s+([0-9_]+)/i);
            if (match) osVersion = match[1].replaceAll("_", ".");
        } else if (platformFamily === "Android") {
            const match = ua.match(/Android\s+([0-9.]+)/i);
            if (match) osVersion = match[1];
        } else if (platformFamily === "Windows") {
            const match = ua.match(/Windows NT\s+([0-9.]+)/i);
            if (match) osVersion = match[1];
        } else if (platformFamily === "macOS") {
            const match = ua.match(/Mac OS X\s+([0-9_]+)/i);
            if (match) osVersion = match[1].replaceAll("_", ".");
        }
        const companionMatch = ua.match(/Home Assistant\/([^\s;(]+)/i);
        const companionApp = !!companionMatch;
        let browserFamily = companionApp ? "Home Assistant WebView" : "Other";
        let browserVersion = null;
        const browserPatterns = [
            ["Edge", /(?:Edg|EdgiOS|EdgA)\/([0-9.]+)/],
            ["Chrome", /(?:Chrome|CriOS)\/([0-9.]+)/],
            ["Firefox", /(?:Firefox|FxiOS)\/([0-9.]+)/],
            ["Safari", /Version\/([0-9.]+).*Safari\//],
        ];
        for (const [name, pattern] of browserPatterns) {
            const match = ua.match(pattern);
            if (match) { if (!companionApp) browserFamily = name; browserVersion = match[1]; break; }
        }
        const webkit = ua.match(/AppleWebKit\/([0-9.]+)/i);
        const chromium = ua.match(/(?:Chrome|CriOS)\/([0-9.]+)/i);
        const client = this._fieldTestClientId();
        return {
            client_id: client.id,
            client_id_persistence: client.persistence,
            platform_family: platformFamily,
            os_version: osVersion,
            device_class: deviceClass,
            device_family: deviceFamily,
            device_model: deviceModel,
            companion_app: companionApp,
            companion_app_version: companionMatch ? companionMatch[1] : null,
            browser_family: browserFamily,
            browser_version: browserVersion,
            webview_engine_version: chromium ? chromium[1] : (webkit ? webkit[1] : null),
            home_assistant_version_reported_by_frontend: this._hass && this._hass.config ? this._hass.config.version : null,
            freshairiq_frontend_version: FAIQ_VERSION,
            viewport_css_px: { width: Math.round(window.innerWidth || 0), height: Math.round(window.innerHeight || 0) },
            screen_css_px: { width: Math.round((window.screen && window.screen.width) || 0), height: Math.round((window.screen && window.screen.height) || 0) },
            device_pixel_ratio: Number(window.devicePixelRatio || 1),
            touch_points: touchPoints,
            standalone_display_mode: !!(window.matchMedia && window.matchMedia("(display-mode: standalone)").matches),
        };
    }
    async _registerFieldTestClient(force = false) {
        if (!this._hass || typeof this._hass.callApi !== "function") return null;
        if (this._fieldTestRegistrationPromise) return this._fieldTestRegistrationPromise;
        const lastKey = "freshairiq.field_test.client_last_sync";
        if (!force) {
            try {
                const last = Number(window.localStorage.getItem(lastKey) || 0);
                if (Number.isFinite(last) && Date.now() - last < 24 * 60 * 60 * 1000) return null;
            } catch (_) { /* session-only registration remains possible */ }
        }
        const context = this._fieldTestClientContext();
        this._fieldTestRegistrationPromise = this._hass.callApi("POST", "freshairiq/diagnostics", context)
            .then(result => {
                if (result && result.registered) {
                    try { window.localStorage.setItem(lastKey, String(Date.now())); } catch (_) { /* privacy/storage mode */ }
                }
                return result;
            })
            .catch(err => { console.debug("FreshAirIQ field-test client registration skipped", err); return null; })
            .finally(() => { this._fieldTestRegistrationPromise = null; });
        return this._fieldTestRegistrationPromise;
    }
    _cancelQueuedRender() {
        if (this._renderFrame == null) return;
        if (this._renderFrameIsRaf && typeof cancelAnimationFrame === "function") cancelAnimationFrame(this._renderFrame);
        else clearTimeout(this._renderFrame);
        this._renderFrame = null;
        this._renderFrameIsRaf = false;
    }
    _queueRender() {
        if (this._renderFrame != null) return;
        const run = () => { this._renderFrame = null; this._renderFrameIsRaf = false; this._render(); };
        if (typeof requestAnimationFrame === "function") {
            this._renderFrameIsRaf = true;
            this._renderFrame = requestAnimationFrame(run);
        } else {
            this._renderFrameIsRaf = false;
            this._renderFrame = setTimeout(run, 0);
        }
    }
    _cancelQueuedLiveRefresh() {
        if (this._liveRefreshFrame == null) return;
        if (this._liveRefreshFrameIsRaf && typeof cancelAnimationFrame === "function") cancelAnimationFrame(this._liveRefreshFrame);
        else clearTimeout(this._liveRefreshFrame);
        this._liveRefreshFrame = null;
        this._liveRefreshFrameIsRaf = false;
    }
    _queueLiveRefresh() {
        if (this._liveRefreshFrame != null) return;
        const run = () => {
            this._liveRefreshFrame = null;
            this._liveRefreshFrameIsRaf = false;
            this._refreshOpenViewsLive();
        };
        if (typeof requestAnimationFrame === "function") {
            this._liveRefreshFrameIsRaf = true;
            this._liveRefreshFrame = requestAnimationFrame(run);
        } else {
            this._liveRefreshFrameIsRaf = false;
            this._liveRefreshFrame = setTimeout(run, 0);
        }
    }
    _collectLiveViewData() {
        const entity = this._statusEntity();
        if (!entity) return null;
        this._ensureRelevantStateIds(entity);
        const st = Object.assign({}, entity.attributes || {});
        let rooms = Object.values(st.rooms || {}).filter(r => r && typeof r === "object");
        const byKey = new Map(rooms.map(r => [String(r.key || ""), r]));
        const activeEntryId = st.freshairiq_entry_id || null;
        const roomStateIds = this._roomEntityIds && this._roomEntityIds.size ? this._roomEntityIds : null;
        const roomStates = roomStateIds
            ? Array.from(roomStateIds, id => this._hass.states[id]).filter(Boolean)
            : Object.values((this._hass && this._hass.states) || {});
        for (const state of roomStates) {
            const attrs = (state && state.attributes) || {};
            const room = attrs.freshairiq_room_payload;
            if (!room || !["room_v1", "room_v2"].includes(attrs.freshairiq_transport)) continue;
            if (activeEntryId && (attrs.freshairiq_transport !== "room_v2" || attrs.freshairiq_entry_id !== activeEntryId)) continue;
            const key = String(room.key || attrs.freshairiq_room_key || "");
            if (!key) continue;
            byKey.set(key, Object.assign({}, byKey.get(key) || {}, room));
        }
        rooms = Array.from(byKey.values()).filter(r => r && r.key);
        if (rooms.length && !Number(st.total_water_ml)) {
            st.total_water_ml = rooms
                .filter(r => r.calculation_enabled !== false && r.data_quality === "ok")
                .reduce((sum, r) => sum + Number(r.water_in_air_ml || 0), 0);
        }
        rooms = this._orderedRooms(rooms);
        return { st, rooms };
    }
    _liveNodesCompatible(current, fresh) {
        if (!current || !fresh || current.nodeType !== fresh.nodeType) return false;
        if (current.nodeType !== 1) return true;
        return current.tagName === fresh.tagName;
    }
    _patchLiveNode(current, fresh) {
        if (!this._liveNodesCompatible(current, fresh)) return;
        if (current.nodeType === 1) {
            const tag = String(current.tagName || "").toUpperCase();
            const isUnsavedRoomControl = ["INPUT", "SELECT", "TEXTAREA"].includes(tag) &&
                current.closest && current.closest(".room-form");
            // A room editor is a draft until the user presses “Raum speichern”.
            // Live HA state refreshes must never restore another select to the
            // last persisted value while the user is configuring its pair.
            if (isUnsavedRoomControl) return;
        }
        if (current.nodeType === 3) {
            if (current.nodeValue !== fresh.nodeValue) current.nodeValue = fresh.nodeValue;
            return;
        }
        if (current.nodeType !== 1) return;
        const active = current.getRootNode && current.getRootNode().activeElement === current;
        // Native <details> open/closed state belongs to the user's interaction, not
        // to freshly rendered HA data. Preserve it while patching live contents.
        const preserveDetailsOpen = String(current.tagName || "").toUpperCase() === "DETAILS";
        const detailsWasOpen = preserveDetailsOpen ? current.open : false;
        for (const attr of Array.prototype.slice.call(current.attributes || [])) {
            if (preserveDetailsOpen && attr.name === "open") continue;
            if (!fresh.hasAttribute(attr.name)) current.removeAttribute(attr.name);
        }
        for (const attr of Array.prototype.slice.call(fresh.attributes || [])) {
            if (preserveDetailsOpen && attr.name === "open") continue;
            if (current.getAttribute(attr.name) !== attr.value) current.setAttribute(attr.name, attr.value);
        }
        if (preserveDetailsOpen) current.open = detailsWasOpen;
        if (!active) {
            const tag = String(current.tagName || "").toUpperCase();
            if (tag === "INPUT") {
                if (current.type === "checkbox" || current.type === "radio") current.checked = fresh.checked;
                else if (current.value !== fresh.value) current.value = fresh.value;
            } else if (tag === "TEXTAREA" || tag === "SELECT") {
                if (current.value !== fresh.value) current.value = fresh.value;
            }
        }
        const currentChildren = Array.prototype.slice.call(current.childNodes || []);
        const freshChildren = Array.prototype.slice.call(fresh.childNodes || []);
        const sameShape = currentChildren.length === freshChildren.length && currentChildren.every((child, index) => this._liveNodesCompatible(child, freshChildren[index]));
        if (sameShape) {
            currentChildren.forEach((child, index) => this._patchLiveNode(child, freshChildren[index]));
            return;
        }
        const interactiveSelector = 'button,a,input,select,textarea,[data-info],[data-room],[data-profile],[data-forecast],[data-guest-kind]';
        const containsInteraction = current.matches(interactiveSelector) || !!current.querySelector(interactiveSelector);
        if (!containsInteraction) {
            current.innerHTML = fresh.innerHTML;
            return;
        }
        const count = Math.min(currentChildren.length, freshChildren.length);
        for (let i = 0; i < count; i++) {
            if (this._liveNodesCompatible(currentChildren[i], freshChildren[i])) this._patchLiveNode(currentChildren[i], freshChildren[i]);
        }
    }
    _liveViewStateSnapshot(key) {
        const ids = Array.from(this._relevantStateIds || []).sort();
        const refs = ids.map(id => (this._hass && this._hass.states ? this._hass.states[id] || null : null));
        const previous = this._liveViewSnapshot;
        const unchanged = !!previous && previous.key === key && previous.ids.length === ids.length &&
            ids.every((id, index) => id === previous.ids[index] && refs[index] === previous.refs[index]);
        this._liveViewSnapshot = { key, ids, refs };
        return unchanged;
    }
    _freshLiveNode(cacheKey, html, selector) {
        if (this._liveHtmlCache[cacheKey] === html) return null;
        this._liveHtmlCache[cacheKey] = html;
        const template = document.createElement("template");
        template.innerHTML = html;
        return template.content.querySelector(selector);
    }
    _refreshOpenViewsLive() {
        try {
            this._refreshOpenViewsLiveImpl();
        } catch (error) {
            this._handleRenderFailure(error, "live refresh");
        }
    }
    _refreshOpenViewsLiveImpl() {
        if (!this.shadowRoot || (!this._dialogOpen && !this._info)) return;
        const data = this._collectLiveViewData();
        if (!data) return;
        const viewKey = `${this._dialogOpen ? "dialog" : ""}|${this._info || ""}`;
        if (this._liveViewStateSnapshot(viewKey)) {
            this._roomViewUpdatePending = false;
            return;
        }
        const { st, rooms } = data;
        if (this._dialogOpen) {
            const current = this.shadowRoot.querySelector(".modal");
            const html = this._details(st, rooms);
            const fresh = current ? this._freshLiveNode("dialog", html, ".modal") : null;
            if (fresh) this._patchLiveNode(current, fresh);
        }
        if (this._info) {
            const current = this.shadowRoot.querySelector(".subdialog");
            const html = `<div class="subdialog">${this._infoNav()}${this._infoPanel(st, rooms)}${this._info === "profile" ? this._profileControls(st) : ""}${this._info === "next5" ? this._forecastControls(st) : ""}${this._info === "guests" ? this._guestControls(st) : ""}</div>`;
            const fresh = current ? this._freshLiveNode(`info:${this._info}`, html, ".subdialog") : null;
            if (fresh) this._patchLiveNode(current, fresh);
        }
        this._roomViewUpdatePending = false;
    }
    _relevantStateChanged(previous, next) {
        if (!previous || !next || !previous.states || !next.states) return true;
        if (!this._relevantStateIds || !this._relevantStateIds.size) return true;
        for (const id of this._relevantStateIds) {
            if (previous.states[id] !== next.states[id]) {
                const state = next.states[id];
                const a = (state && state.attributes) || {};
                if (id !== this._statusEntityId && (a.freshairiq_transport === "status_v2" || a.freshairiq_entity_key === "status"))
                    this._statusRescanNeeded = true;
                return true;
            }
        }
        return false;
    }
    _invalidateEntityCaches() { this._statusEntityId = null; this._statusRescanNeeded = false; this._relevantStateIds = null; this._roomEntityIds = null; this._roomConfigSignature = null; this._entityCache = {}; this._liveViewSnapshot = null; this._liveHtmlCache = {}; this._learningCardCache = null; }
    _ensureRelevantStateIds(status = null) {
        if (!this._hass) return;
        const current = status || this._statusEntity();
        const attrs = (current && current.attributes) || {};
        const rawRooms = attrs.rooms || {};
        const keys = (Array.isArray(rawRooms) ? rawRooms.map(r => String((r && r.key) || "")) : Object.keys(rawRooms)).filter(Boolean).sort();
        const signature = `${attrs.freshairiq_entry_id || ""}|${keys.join("|")}`;
        if (this._relevantStateIds && this._roomConfigSignature === signature) return;
        const entryId = attrs.freshairiq_entry_id || null;
        const ids = new Set();
        const roomIds = new Set();
        if (current && current.entity_id) ids.add(current.entity_id);
        if (this._config.entity) ids.add(this._config.entity);
        for (const state of Object.values(this._hass.states || {})) {
            if (!state || !state.entity_id) continue;
            const a = state.attributes || {};
            const sameEntry = !entryId || a.freshairiq_entry_id === entryId;
            const roomTransport = sameEntry && ["room_v1", "room_v2"].includes(a.freshairiq_transport);
            const taggedControl = sameEntry && !!a.freshairiq_entity_key;
            const legacyFresh = !entryId && String(state.entity_id).includes("freshairiq");
            if (roomTransport) roomIds.add(state.entity_id);
            if (roomTransport || taggedControl || legacyFresh) ids.add(state.entity_id);
        }
        this._relevantStateIds = ids;
        this._roomEntityIds = roomIds;
        this._roomConfigSignature = signature;
    }
    _freshAirIQStates(status = null) {
        if (!this._hass) return [];
        const current = status || this._statusEntity();
        this._ensureRelevantStateIds(current);
        if (!this._relevantStateIds || !this._relevantStateIds.size) return [];
        return Array.from(this._relevantStateIds, id => this._hass.states[id]).filter(Boolean);
    }
    setConfig(c) { this._config = normalizeDashboardConfig(c); this._invalidateEntityCaches(); this._render(); }
    set hass(h) {
        const previous = this._hass;
        this._hass = h;
        void this._registerFieldTestClient(false);
        const relevantChanged = this._relevantStateChanged(previous, h);
        // Home Assistant replaces the hass object for every state event. Most of
        // those events are unrelated to FreshAirIQ. Ignore them entirely instead
        // of rebuilding a large Shadow DOM. Relevant FreshAirIQ entities are
        // tracked by object identity, so genuine dashboard changes remain live.
        if (!relevantChanged) return;
        // Hotfix 0.20.1.2: every open FreshAirIQ window keeps its existing
        // scroll container and receives live value patches inside that DOM. This
        // keeps numbers/text/statuses current without recreating .modal/.subdialog
        // and therefore without resetting native iOS/Android WebView scrolling.
        if (this._info || this._dialogOpen) {
            this._queueLiveRefresh();
            return;
        }
        this._queueRender();
    }
    getCardSize() { return 5; }
    _statusEntity() {
        if (!this._hass)
            return null;
        const cached = this._statusEntityId ? this._hass.states[this._statusEntityId] : null;
        if (!this._statusRescanNeeded && cached && cached.attributes && cached.attributes.freshairiq_transport === "status_v2")
            return cached;
        const remember = state => { if (state && state.entity_id) this._statusEntityId = state.entity_id; this._statusRescanNeeded = false; return state; };
        const states = Object.values(this._hass.states);
        const isFreshAirIQ = s => {
            var _a;
            if (!((_a = s === null || s === void 0 ? void 0 : s.entity_id) === null || _a === void 0 ? void 0 : _a.startsWith("sensor.")))
                return false;
            const a = s.attributes || {};
            // Do not rely on the generated entity_id/friendly_name here. Home Assistant
            // can retain/rename registry entities after an update. The status sensor is
            // uniquely identifiable by FreshAirIQ's dashboard payload itself.
            const payloadSignature = (a.rooms != null &&
                (a.intelligent_recommendation != null || a.cross_ventilation != null ||
                    a.overnight_forecast_ml != null || a.ventilation_threshold_ml != null));
            return payloadSignature || s.entity_id.includes("freshairiq") ||
                String(a.friendly_name || "").toLowerCase().includes("freshairiq");
        };
        const roomCount = s => {
            var _a;
            const rooms = (_a = s === null || s === void 0 ? void 0 : s.attributes) === null || _a === void 0 ? void 0 : _a.rooms;
            return Array.isArray(rooms) ? rooms.length : (rooms && typeof rooms === "object" ? Object.keys(rooms).length : 0);
        };
        const hasDashboardPayload = s => {
            const a = (s === null || s === void 0 ? void 0 : s.attributes) || {};
            return roomCount(s) > 0 || a.total_water_ml != null || a.intelligent_recommendation != null || a.history_summary != null;
        };
        const usefulScore = s => {
            const a = s.attributes || {};
            let score = 0;
            // Current transport/version identity outranks payload size. This prevents
            // a stale registry entity with more historic rooms from winning.
            if (a.freshairiq_transport === "status_v2")
                score += 1000000;
            if (String(a.freshairiq_version || a.version || "") === FAIQ_VERSION)
                score += 500000;
            if (a.freshairiq_entry_id)
                score += 100000;
            if (a.total_water_ml != null)
                score += 5000;
            if (a.intelligent_recommendation != null)
                score += 2500;
            if (a.history_summary != null)
                score += 1000;
            if (a.status != null)
                score += 500;
            score += Math.min(roomCount(s), 100);
            if (s.entity_id === "sensor.freshairiq_status")
                score += 1;
            return score;
        };
        // A Home Assistant entity registry can retain an older sensor.freshairiq_status
        // while the current integration receives a suffixed entity id. Always select
        // the FreshAirIQ status sensor that actually carries the room/dashboard payload.
        const configured = this._config.entity && this._hass.states[this._config.entity];
        // If the card explicitly points at a current FreshAirIQ status_v2 entity,
        // that config-entry choice is authoritative. This also keeps multiple
        // FreshAirIQ instances separated.
        if (configured && configured.attributes &&
            configured.attributes.freshairiq_transport === "status_v2" &&
            hasDashboardPayload(configured))
            return remember(configured);
        const payloadCandidates = states.filter(s => isFreshAirIQ(s) && hasDashboardPayload(s));
        if (configured && hasDashboardPayload(configured))
            payloadCandidates.push(configured);
        if (payloadCandidates.length) {
            return remember([...new Set(payloadCandidates)].sort((a, b) => usefulScore(b) - usefulScore(a))[0]);
        }
        // During startup the current status sensor may exist before its attributes
        // arrive. Prefer the configured/canonical status entity only as a fallback.
        if (configured)
            return remember(configured);
        const canonical = this._hass.states["sensor.freshairiq_status"];
        if (canonical)
            return remember(canonical);
        return remember(states.find(s => {
            var _a;
            return isFreshAirIQ(s) &&
                (/(^|_)status(_\d+)?$/.test(s.entity_id.split(".")[1] || "") || /\bstatus\b/i.test(String(((_a = s.attributes) === null || _a === void 0 ? void 0 : _a.friendly_name) || "")));
        }) || null);
    }
    _num(id, f = 0) { var _a, _b, _c; const n = Number((_c = (_b = (_a = this._hass) === null || _a === void 0 ? void 0 : _a.states) === null || _b === void 0 ? void 0 : _b[id]) === null || _c === void 0 ? void 0 : _c.state); return Number.isFinite(n) ? n : f; }
    _profileEntity() {
        var _a;
        const cached = this._entityCache.profile && this._hass && this._hass.states[this._entityCache.profile];
        if (cached) return cached;
        const wanted = ["dehumidify", "comfort", "summer_cooling"];
        const status = this._statusEntity();
        const indexedStates = this._freshAirIQStates(status);
        const entryId = status && status.attributes ? status.attributes.freshairiq_entry_id : null;
        const tagged = indexedStates.find(s => {
            var _a;
            const a = (s === null || s === void 0 ? void 0 : s.attributes) || {};
            return ((_a = s === null || s === void 0 ? void 0 : s.entity_id) === null || _a === void 0 ? void 0 : _a.startsWith("select.")) &&
                a.freshairiq_entity_key === "operating_profile" &&
                (!entryId || a.freshairiq_entry_id === entryId);
        });
        if (tagged) { this._entityCache.profile = tagged.entity_id; return tagged; }
        // Backward-compatible fallback for installations that have not yet exposed
        // the identity attributes. Restrict it to FreshAirIQ-named entities.
        const legacyStates = Object.values((this._hass && this._hass.states) || {});
        const fallback = legacyStates.find(s => {
            var _a, _b;
            if (!((_a = s === null || s === void 0 ? void 0 : s.entity_id) === null || _a === void 0 ? void 0 : _a.startsWith("select.")))
                return false;
            const a = s.attributes || {};
            const opts = Array.isArray((_b = s.attributes) === null || _b === void 0 ? void 0 : _b.options) ? s.attributes.options : [];
            const name = `${s.entity_id} ${String(a.friendly_name || "")}`.toLowerCase();
            return name.includes("freshairiq") && wanted.every(v => opts.includes(v));
        }) || null;
        if (fallback) this._entityCache.profile = fallback.entity_id;
        return fallback;
    }
    _forecastEntity() {
        var _a;
        const cached = this._entityCache.forecast && this._hass && this._hass.states[this._entityCache.forecast];
        if (cached) return cached;
        const status = this._statusEntity();
        const indexedStates = this._freshAirIQStates(status);
        const entryId = status && status.attributes ? status.attributes.freshairiq_entry_id : null;
        const tagged = indexedStates.find(s => {
            var _a;
            const a = (s === null || s === void 0 ? void 0 : s.attributes) || {};
            return ((_a = s === null || s === void 0 ? void 0 : s.entity_id) === null || _a === void 0 ? void 0 : _a.startsWith("number.")) &&
                a.freshairiq_entity_key === "forecast_horizon_min" &&
                (!entryId || a.freshairiq_entry_id === entryId);
        });
        if (tagged) { this._entityCache.forecast = tagged.entity_id; return tagged; }
        // Backward-compatible fallback: never bind a generic 1..120 minute helper.
        const legacyStates = Object.values((this._hass && this._hass.states) || {});
        const fallback = legacyStates.find(s => {
            var _a;
            if (!((_a = s === null || s === void 0 ? void 0 : s.entity_id) === null || _a === void 0 ? void 0 : _a.startsWith("number.")))
                return false;
            const a = s.attributes || {};
            const name = `${s.entity_id} ${String(a.friendly_name || "")}`.toLowerCase();
            return name.includes("freshairiq") && (name.includes("prognosezeitraum") || name.includes("forecast_horizon"));
        }) || null;
        if (fallback) this._entityCache.forecast = fallback.entity_id;
        return fallback;
    }
    _guestEntity(kind) {
        const key = kind === "child" ? "guest_children" : "guest_adults";
        const cacheKey = `guest:${key}`;
        const cachedId = this._entityCache[cacheKey];
        const cached = cachedId && this._hass && this._hass.states[cachedId];
        if (cached) return cached;
        const status = this._statusEntity();
        const indexedStates = this._freshAirIQStates(status);
        const entryId = status && status.attributes ? status.attributes.freshairiq_entry_id : null;
        const tagged = indexedStates.find(state => {
            const a = (state && state.attributes) || {};
            return state && String(state.entity_id || "").startsWith("number.") &&
                a.freshairiq_entity_key === key &&
                (!entryId || a.freshairiq_entry_id === entryId);
        });
        if (tagged) { this._entityCache[cacheKey] = tagged.entity_id; return tagged; }
        // Legacy fallback only. New versions use the stable entity metadata above,
        // so renaming an entity in Home Assistant cannot break guest controls.
        const needle = kind === "child" ? "übernachtungsgäste kinder" : "übernachtungsgäste erwachsene";
        const legacyStates = Object.values((this._hass && this._hass.states) || {});
        const fallback = legacyStates.find(state => {
            const a = (state && state.attributes) || {};
            const name = `${state && state.entity_id || ""} ${String(a.friendly_name || "")}`.toLowerCase();
            return String(state && state.entity_id || "").startsWith("number.") &&
                name.includes("freshairiq") && name.includes(needle);
        }) || null;
        if (fallback) this._entityCache[cacheKey] = fallback.entity_id;
        return fallback;
    }
    _profileValue(st) { var _a; const actual = String(((_a = this._profileEntity()) === null || _a === void 0 ? void 0 : _a.state) || st.operating_profile || "comfort"); if (this._profileOverride != null) { if (actual === this._profileOverride) this._profileOverride = null; else return this._profileOverride; } return actual; }
    _forecastValue(st) { var _a; const n = Number((_a = this._forecastEntity()) === null || _a === void 0 ? void 0 : _a.state); const actual = Number.isFinite(n) ? n : Number(st.forecast_horizon_min || 5); if (this._forecastOverride != null) { if (Math.round(actual) === Math.round(this._forecastOverride)) this._forecastOverride = null; else return this._forecastOverride; } return actual; }
    _svgBars(history) {
        const rows = Array.isArray(history) ? history : [];
        if (!rows.length) return "";
        const cache = this._chartCache && this._chartCache.bars;
        if (cache && cache.has(rows)) return cache.get(rows);
        const signedValues = rows.map(r => Number((r.water_ml ?? r.removed_ml) ?? 0));
        const vals = signedValues.map(v => Math.abs(v));
        const max = Math.max(...vals, 1), w = 560, h = 112, g = 3, b = (w - g * (vals.length - 1)) / vals.length;
        const html = `<svg viewBox="0 0 ${w} ${h}" preserveAspectRatio="none">${vals.map((v, i) => { const bh = Math.max(2, (v / max) * 86), x = i * (b + g), y = 98 - bh, fill = signedValues[i] < 0 ? "#ff7770" : "#67df92"; return `<rect x="${x.toFixed(1)}" y="${y.toFixed(1)}" width="${b.toFixed(1)}" height="${bh.toFixed(1)}" rx="3" fill="${fill}" opacity="${v ? 0.9 : .18}"/>`; }).join("")}</svg>`;
        if (cache) cache.set(rows, html);
        return html;
    }
    _svgLine(points, field = "temperature_c") {
        const rows = Array.isArray(points) ? points : [];
        if (!rows.length) return "";
        const vals = rows.map(r => Number(r[field])).filter(Number.isFinite);
        if (vals.length < 2) return "";
        const rawMin = Math.min(...vals), rawMax = Math.max(...vals);
        const unit = field === "humidity_percent" ? "%" : "°C";
        const step = field === "humidity_percent" ? 5 : 1;
        let axisMin = Math.floor(rawMin / step) * step, axisMax = Math.ceil(rawMax / step) * step;
        if (axisMax <= axisMin) axisMax = axisMin + step;
        const span = axisMax - axisMin, w = 560, h = 112, left = 42, right = 8, top = 8, bottom = 8;
        const y = v => h - bottom - (v - axisMin) / span * (h - top - bottom);
        const path = vals.map((v, i) => `${i ? "L" : "M"}${(left + i / Math.max(vals.length - 1, 1) * (w - left - right)).toFixed(1)},${y(v).toFixed(1)}`).join(" ");
        const ticks = [axisMax, axisMin + span / 2, axisMin];
        const grid = ticks.map(v => `<line x1="${left}" x2="${w-right}" y1="${y(v).toFixed(1)}" y2="${y(v).toFixed(1)}" stroke="rgba(160,185,200,.18)" stroke-width="1"/><text x="${left-6}" y="${(y(v)+3).toFixed(1)}" text-anchor="end" fill="#9fb0ba" font-size="10">${fmt(v, field === "humidity_percent" ? 0 : 1)}${unit}</text>`).join("");
        return `<svg viewBox="0 0 ${w} ${h}" preserveAspectRatio="none">${grid}<path d="${path}" fill="none" stroke="#61d6ff" stroke-width="3" stroke-linecap="round"/></svg>`;
    }
    _recentVentilation(st) {
        const last = st && st.last_ventilation ? st.last_ventilation : null;
        if (!last || !last.ended_at) return null;
        const ended = Date.parse(last.ended_at);
        if (!Number.isFinite(ended)) return null;
        const explicitUntil = Date.parse(last.display_until || "");
        const until = Number.isFinite(explicitUntil) ? explicitUntil : ended + 5 * 60 * 1000;
        const remainingMs = until - Date.now();
        return remainingMs > 0 ? Object.assign({}, last, { _remainingMs: remainingMs }) : null;
    }
    _ventilationResultRows(last, respectPreferences = false) {
        const rows = Array.isArray(last && last.room_results) ? last.room_results : [];
        if (!rows.length) {
            const names = Array.isArray(last && last.rooms) ? last.rooms : [];
            return names.map(name => `<div class="result-room"><div><b>${esc(name)}</b><span>Einzelergebnis aus älterem Datenformat nicht verfügbar</span></div></div>`).join("");
        }
        const prefs = respectPreferences ? this._config : {};
        const showMoisture = !respectPreferences || prefs.info_moisture !== false;
        const showTemperature = !respectPreferences || prefs.info_temperature !== false;
        const showTime = !respectPreferences || prefs.info_time !== false;
        const showForecast = !respectPreferences || prefs.info_forecast !== false;
        const showEnergy = !respectPreferences || prefs.info_energy !== false;
        return rows.map(r => {
            const moistureValid = r.moisture_result_complete !== false && r.removed_ml != null;
            const m = moistureValid ? moisture(r.removed_ml, "±0 ml") : { text: "Messwert nicht belastbar", color: "#9aa7b3", kind: "unknown" };
            const meta = [];
            if (showTime) meta.push(`${fmt(r.duration_min || 0, 1)} min`);
            if (showTemperature) meta.push(r.temp_delta_c == null ? "Temperatur –" : signed(r.temp_delta_c, "°C"));
            if (showEnergy) meta.push(`${fmt(r.cost || 0, 2)} €`);
            const roomPrediction = r.aligned_predicted_removed_ml != null ? r.aligned_predicted_removed_ml : r.predicted_removed_ml;
            if (showForecast && roomPrediction != null) meta.push(`Startprognose ${moisture(roomPrediction, "±0 ml").text}`);
            const attrs = r.key ? ` class="result-room clickable" data-room="${esc(r.key)}"` : ` class="result-room"`;
            return `<div${attrs}><div><b>${esc(r.name || r.key || "Raum")}</b>${meta.length ? `<span>${meta.join(" · ")}</span>` : ""}</div>${showMoisture ? `<strong style="color:${m.color}">${m.text}</strong>` : ""}</div>`;
        }).join("");
    }
    _lastVentilationTile(last) {
        if (!last)
            return `<section class="last-vent-tile clickable" data-info="lastvent"><div class="last-vent-tile-icon"><ha-icon icon="mdi:history"></ha-icon></div><div><div class="tiny">LETZTE LÜFTUNG</div><b>Noch keine abgeschlossene Lüftung</b><span>Sobald eine Lüftung abgeschlossen ist, bleibt ihr Ergebnis hier abrufbar.</span></div><ha-icon class="last-vent-tile-chevron" icon="mdi:chevron-right"></ha-icon></section>`;
        const moistureValid = last.moisture_result_complete !== false && last.removed_ml != null;
        const m = moistureValid ? moisture(last.removed_ml, "±0 ml") : { text: "Feuchte nicht belastbar", color: "#9aa7b3", kind: "unknown" };
        return `<section class="last-vent-tile clickable" data-info="lastvent" style="--result:${m.color}"><div class="last-vent-tile-icon"><ha-icon icon="mdi:history"></ha-icon></div><div><div class="tiny">LETZTE LÜFTUNG</div><b>${m.text} · ${fmt(last.duration_min || 0, 1)} min</b><span>${esc(whenDE(last.ended_at))} · vollständiges Ergebnis öffnen</span></div><ha-icon class="last-vent-tile-chevron" icon="mdi:chevron-right"></ha-icon></section>`;
    }
    _ventilationResultCard(last, variant = "detail") {
        if (!last) return `<div class="last-vent"><div><div class="tiny">LETZTE LÜFTUNG</div><b>Noch keine abgeschlossene Lüftung</b></div></div>`;
        const moistureValid = last.moisture_result_complete !== false && last.removed_ml != null;
        const m = moistureValid ? moisture(last.removed_ml, "±0 ml") : { text: "nicht belastbar", color: "#9aa7b3", kind: "unknown" };
        const hero = variant === "hero";
        const respectPreferences = hero;
        const showMoisture = !respectPreferences || this._config.info_moisture !== false;
        const showTemperature = !respectPreferences || this._config.info_temperature !== false;
        const showTime = !respectPreferences || this._config.info_time !== false;
        const showForecast = !respectPreferences || this._config.info_forecast !== false;
        const showEnergy = !respectPreferences || this._config.info_energy !== false;
        const showCrossVentilation = !respectPreferences || this._config.info_cross_ventilation !== false;
        const alignmentQuality = String(last.prediction_alignment_quality || "");
        const scoreValidated = alignmentQuality
            ? ["validated", "partial_validated", "legacy_validated"].includes(alignmentQuality)
            : last.prediction_accuracy_percent != null;
        const displayAccuracy = scoreValidated ? last.prediction_accuracy_percent : null;
        const displayPredicted = scoreValidated ? last.predicted_removed_ml : null;
        const displayMeasured = scoreValidated ? last.prediction_actual_removed_ml : null;
        const displayError = scoreValidated ? last.prediction_error_ml : null;
        const accuracy = displayAccuracy == null
            ? (last.prediction_status_text || "Für diese Lüftung konnte beim Start keine belastbar auswertbare Prognose eingefroren werden")
            : `Prognosegenauigkeit ${Math.round(Number(displayAccuracy))} % · Startprognose gegen Ergebnis bei gleicher Messdauer`;
        const predicted = displayPredicted == null ? "" : ` · beim Start vorhergesagt ${moisture(displayPredicted, "±0 ml").text}`;
        const predictionMeasured = displayMeasured == null ? null : moisture(displayMeasured, "±0 ml");
        const qualityBits = [];
        if (!moistureValid) qualityBits.push("Feuchteergebnis nicht in Lernen oder Feuchtestatistik übernommen · Sensorzeitstempel während der Lüftung nicht vollständig");
        if (showCrossVentilation && last.cross_ventilation) qualityBits.push("Querlüftung erkannt");
        if (Number(last.recommendation_followed_count || 0) > 0) qualityBits.push(`${Number(last.recommendation_followed_count)} Raumempfehlung(en) befolgt`);
        if (Number(last.learning_valid_count || 0) > 0) qualityBits.push(`${Number(last.learning_valid_count)} Lernmessung(en) verwertbar`);
        if (Number(last.moisture_source_contaminated_rooms || 0) > 0) qualityBits.push(`${Number(last.moisture_source_contaminated_rooms)} Raum/Räume mit aktiver Feuchtequelle`);
        if (Number(last.prediction_time_aligned_rooms || 0) > 0) qualityBits.push(`${Number(last.prediction_time_aligned_rooms)} Raum/Räume mit zeitgleichem Startvergleich`);
        if (alignmentQuality === "partial_validated") {
            qualityBits.push(`${Number(last.prediction_comparable_rooms || 0)} von ${Number(last.prediction_time_aligned_rooms || 0)} Raum/Räumen für Genauigkeitswertung verwertbar`);
            if (Number(last.prediction_excluded_rooms || 0) > 0) qualityBits.push(`${Number(last.prediction_excluded_rooms)} Raum/Räume wegen nicht ausreichend synchroner Messdaten ausgeschlossen`);
        } else if (Number(last.prediction_time_aligned_sessions || 0) > Number(last.prediction_comparable_sessions || 0)) qualityBits.push("Keine Genauigkeitswertung · Messdaten nicht streng genug synchronisiert");
        else if (Number(last.prediction_comparable_rooms || 0) > 0) qualityBits.push(`${Number(last.prediction_comparable_rooms)} Raum/Räume für Genauigkeitswertung verwertbar`);
        const remaining = hero && Number(last._remainingMs) > 0 ? `<span class="result-countdown">Ergebnis noch ${Math.max(1, Math.ceil(Number(last._remainingMs) / 60000))} min im Dashboard</span>` : "";
        const resultHeadline = showMoisture ? (!moistureValid ? "Lüftung beendet · Feuchteergebnis nicht belastbar" : m.kind === "removed" ? "Feuchtigkeit erfolgreich reduziert" : m.kind === "added" ? "Feuchtigkeit ist angestiegen" : "Lüftung ausgewertet") : "Lüftung ausgewertet";
        const metrics = [];
        if (showMoisture) metrics.push(`<div><span>FEUCHTE</span><b style="color:${m.color}">${m.text}</b>${!moistureValid ? `<small>nicht als Messwert gespeichert</small>` : ""}</div>`);
        if (showTime) metrics.push(`<div><span>DAUER</span><b>${fmt(last.duration_min || 0, 1)} min</b></div>`);
        if (showTemperature) metrics.push(`<div><span>TEMPERATUR</span><b>${last.temp_delta_c == null ? "–" : signed(last.temp_delta_c, "°C")}</b></div>`);
        if (showEnergy) metrics.push(`<div><span>WIEDERAUFHEIZEN</span><b>${fmt(last.cost || 0, 2)} €</b><small>${fmt(last.energy_kwh || 0, 2)} kWh</small></div>`);
        const learningFeedback = alignmentQuality === "informational"
            ? `<span class="result-learning-feedback">FreshAirIQ wartet bei zeitversetzt meldenden Sensoren auf einen belastbaren Messvergleich. Die Lern-Auswertung kann deshalb verzögert erscheinen. Dieser Vergleich wird wegen nicht ausreichend synchroner Messdaten nicht als Prognosegenauigkeit gewertet.${last.learning_feedback_text ? ` ${esc(last.learning_feedback_text)}` : ""}</span>`
            : alignmentQuality === "partial_validated"
                ? `<span class="result-learning-feedback">Die Genauigkeit wird ausschließlich aus den streng vergleichbaren Raummessungen berechnet. Asynchrone Räume bleiben sichtbar, beeinflussen diese Wertung aber nicht.${last.learning_feedback_text ? ` ${esc(last.learning_feedback_text)}` : ""}</span>`
                : (last.learning_feedback_text ? `<span class="result-learning-feedback">${esc(last.learning_feedback_text)}</span>` : "");
        const iqMoistureSummary = !moistureValid ? "Feuchtevergleich nicht belastbar" : (predictionMeasured ? `Vergleichsmessung ${predictionMeasured.text}` : `Gesamtergebnis ${m.text}`);
        const iqEvaluation = showForecast ? `<div class="result-iq"><ha-icon icon="mdi:brain"></ha-icon><div><div class="tiny">IQ-AUSWERTUNG</div><b>${esc(accuracy)}</b><span>${showMoisture ? iqMoistureSummary : "Ergebnis gemessen"}${predicted}${displayError == null ? "" : ` · Abweichung ${signed(displayError, "ml")}`}</span>${learningFeedback}${qualityBits.length ? `<span>${qualityBits.map(esc).join(" · ")}</span>` : ""}</div></div>` : "";
        const openAttr = hero ? ` data-info="lastvent"` : "";
        return `<section class="vent-result ${hero ? "vent-result-hero clickable" : "vent-result-panel"}"${openAttr} style="--result:${m.color}"><div class="result-head"><div class="result-icon"><ha-icon icon="mdi:check-circle-outline"></ha-icon></div><div><div class="tiny">${hero ? "LÜFTUNG ABGESCHLOSSEN" : "LETZTE LÜFTUNG"}</div><h3>${resultHeadline}</h3><span>${esc(whenDE(last.ended_at))} · ${Number(last.room_count || (last.rooms || []).length || 0)} Raum/Räume</span></div>${remaining}</div>${metrics.length ? `<div class="result-metrics">${metrics.join("")}</div>` : ""}${iqEvaluation}<div class="result-rooms">${this._ventilationResultRows(last, respectPreferences)}</div><div class="result-footer"><span>Vom Öffnen des ersten bis zum Schließen des letzten Lüftungsfensters zusammengefasst.</span>${hero ? `<b>Ergebnis öffnen ›</b>` : `<span class="result-complete">Vollständige Auswertung</span>`}</div></section>`;
    }
    _hero(st, rooms, live, potential) {
        const iq = st.intelligent_recommendation || {};
        const passiveOpenMonitor = String(iq.status || st.status || "") === "passive_open_monitor";
        const iqColor = passiveOpenMonitor ? "#63d2f7" : iq.severity === "good" ? "#62e889" : iq.severity === "warning" ? "#e2bd69" : iq.severity === "danger" ? "#ff7770" : "#8fa0ac";
        if (iq.title)
            return { color: iqColor, title: iq.title, sub: iq.instruction || iq.summary || "" };
        if (passiveOpenMonitor)
            return { color: "#63d2f7", title: "Daueröffnung wird überwacht", sub: "Fenster kann vorerst offen/gekippt bleiben" };
        const active = rooms.filter(r => r.active && r.calculation_enabled !== false), close = rooms.filter(r => r.action === "Close"), vent = rooms.filter(r => r.action === "Ventilate"), bad = rooms.filter(r => r.data_quality !== "ok" && r.calculation_enabled !== false);
        if (bad.length)
            return { color: "#ff7770", title: "Sensoren prüfen", sub: `${bad.length} Raum/Räume mit ungültigen Messwerten` };
        if (close.length)
            return { color: "#ffb45f", title: "Jetzt schließen", sub: close.map(r => r.name).join(", ") };
        if (active.length) {
            const m = moisture(live);
            return { color: m.color, title: "Lüftung läuft", sub: `${active.length} Raum/Räume aktiv · ${m.text}` };
        }
        if (st.status === "pollen_warning")
            return { color: "#ffb45f", title: "Pollen beachten", sub: `Index ${fmt(st.pollen_index, 1)} · Grenzwert ${fmt(st.pollen_limit, 1)}` };
        if (st.status === "cooling_recommended")
            return { color: "#63d2f7", title: "Sommerkühlung sinnvoll", sub: "Kühlere Außenluft kann genutzt werden" };
        if (st.status === "ventilate")
            return { color: "#62e889", title: "Jetzt lüften", sub: `Hausweit ${moisture(potential).text} möglich` };
        if (vent.length)
            return { color: "#62e889", title: "Raumweise lüften", sub: vent.map(r => r.name).join(", ") };
        const roomProblem = rooms.find(r => ["Do not ventilate", "Wait"].includes(r.action) && (r.recommendation_reasons || []).some(x => /Raumluftfeuchte|Oberflächenfeuchte|Room humidity|Surface humidity|CO₂/.test(String(x))));
        if (roomProblem)
            return { color: roomProblem.action === "Do not ventilate" ? "#ff7770" : "#e2bd69", title: roomProblem.action === "Do not ventilate" ? "Feuchteproblem · noch nicht lüften" : "Feuchteproblem · abwarten", sub: roomProblem.name };
        const fallbackH = Math.max(1, Math.round(this._forecastValue(st) || 5));
        const incoming = Math.max(0, -Number(st.forecast_moisture_effect_ml || 0));
        if (incoming >= 1)
            return { color: "#ff7770", title: "Nicht lüften", sub: `Außenluft würde in ${fallbackH} min ca. +${Math.round(incoming)} ml Feuchtigkeit eintragen` };
        return { color: "#8fa0ac", title: "Alles okay", sub: statusTextDE(st.status_text) || "Fenster geschlossen lassen" };
    }
    _freshyClockMinutes(value, fallback) {
        const match = String(value || "").match(/^(\d{1,2}):(\d{2})/);
        if (!match) return fallback;
        const hour = Number(match[1]), minute = Number(match[2]);
        if (!Number.isInteger(hour) || !Number.isInteger(minute) || hour < 0 || hour > 23 || minute < 0 || minute > 59) return fallback;
        return hour * 60 + minute;
    }
    _freshyTimeKind(st, now = new Date()) {
        const start = this._freshyClockMinutes(st && st.night_start_hour, 22 * 60);
        const end = this._freshyClockMinutes(st && st.night_end_hour, 6 * 60);
        const current = now.getHours() * 60 + now.getMinutes();
        const inNight = start === end ? true : (start < end ? current >= start && current < end : current >= start || current < end);
        if (inNight) return "night";
        const preStart = (start - 60 + 1440) % 1440;
        const inPreNight = preStart < start
            ? current >= preStart && current < start
            : current >= preStart || current < start;
        return inPreNight ? "pre-night" : "good";
    }
    _compactAIPanel(st, rooms = []) {
        const calc = rooms.filter(r => r.calculation_enabled !== false);
        const active = calc.filter(r => r.active && !r.session_finalization_pending);
        const hero = this._hero(st, rooms, Number(st.live_balance_ml || 0), Number(st.potential_total_ml || 0));
        const heroTitle = String(hero.title || "").toLowerCase();
        const status = String(st.status || "").toLowerCase();
        const passiveOpenMonitor = status === "passive_open_monitor" || heroTitle.includes("daueröffnung") || heroTitle.includes("long opening");
        const monitoredRoomKeys = new Set((st.intelligent_recommendation?.room_keys || []).map(String));
        const isCanonicalMonitorRoom = r => passiveOpenMonitor && r.active && monitoredRoomKeys.has(String(r.key));
        const close = calc.filter(r => r.action === "Close" && !isCanonicalMonitorRoom(r));
        const vent = calc.filter(r => ["Ventilate", "Ventilate for cooling"].includes(r.action));
        const bad = calc.filter(r => r.data_quality !== "ok");
        const priority = passiveOpenMonitor && active.length ? active : (close.length ? close : (active.length ? active : (vent.length ? vent : bad)));

        const duration = active.length ? Number(st.remaining_duration_min || 0) : Number(st.recommended_duration_min || 0);
        const amount = active.length ? Math.abs(Number(st.live_balance_ml || 0)) : Math.max(0, Number(st.potential_total_ml || 0));
        const freshyTimeKind = this._freshyTimeKind(st);
        const isNight = freshyTimeKind === "night";
        const isPreNight = freshyTimeKind === "pre-night";
        // Semantic Freshy state: a primary night recommendation must stay visually "night" even
        // when its selected rooms also carry the normal Ventilate action. Active ventilation
        // still wins so an already running session keeps the live sailing animation.
        const nightStrategy = st.night_strategy || {};
        const nightRecommendation = !active.length && (
            Boolean(nightStrategy.primary || st.night_strategy_primary) ||
            heroTitle.includes("nacht") || heroTitle.includes("night")
        );
        const kind = active.length && passiveOpenMonitor ? "continuous"
            : active.length ? "live"
            : bad.length && status !== "sensor_recovering" ? "sensor"
            : close.length ? "close"
            : status === "pollen_warning" || Boolean(st.pollen_blocked) ? "pollen"
            : status === "cooling_recommended" || vent.some(r => r.action === "Ventilate for cooling") ? "cooling"
            : heroTitle.includes("abwarten") || heroTitle.includes("nicht lüften") || heroTitle.includes("wait for") || heroTitle.includes("do not ventilate") ? "wait"
            : ["completed", "complete", "success", "ventilation_completed"].includes(status) ? "success"
            : nightRecommendation ? "night"
            : vent.length || status === "ventilate" ? "recommend"
            : isNight ? "night"
            : isPreNight ? "pre-night"
            : "good";
        // 0.26.4.1: Freshy's mood (11 animated states) follows the same situation logic.
        const freshyMouldSerious = calc.some(r => ["High", "Very high"].includes(r.mould_level));
        const freshyRainClose = nightStrategy.action === "close" && Boolean(nightStrategy.rain_expected);
        const freshyNightAction = ["pre_ventilate", "open_selected"].includes(String(nightStrategy.action || ""));
        const freshyMood = kind === "live" && close.some(r => r.active) ? "done"
            : kind === "continuous" || kind === "live" ? "run"
            : kind === "sensor" ? "sensor"
            : kind === "close" || kind === "success" ? "done"
            : kind === "pollen" ? "pollen"
            : kind === "cooling" ? "cool"
            : kind === "recommend" ? "act"
            : kind === "night" ? (nightRecommendation && freshyNightAction ? "act" : freshyRainClose ? "rain" : "night")
            : kind === "wait" ? (freshyRainClose || nightStrategy.rain_expected ? "rain" : isNight ? "night" : "ok")
            : freshyMouldSerious ? "mould"
            : isNight ? "night"
            : "ok";
        const freshyProgress = active.length && Number(st.recommended_duration_min || 0) > 0 ? 1 - Math.max(0, Number(st.remaining_duration_min || 0)) / Number(st.recommended_duration_min) : null;
        const color = kind === "sensor" ? "#ff7770" : ["close", "wait", "pollen"].includes(kind) ? "#ffb45f" : ["good", "success", "recommend"].includes(kind) ? "#62e889" : ["live", "continuous", "cooling"].includes(kind) ? "#63d2f7" : ["night", "pre-night"].includes(kind) ? "#8796ff" : (hero.color || "#63d2f7");
        const roomNames = priority.slice(0, 2).map(r => r.name).filter(Boolean);
        const summary = active.length ? this._t("iq.room_tracking", { count: active.length }) : roomNames.length ? this._t(roomNames.length > 1 ? "iq.priority_many" : "iq.priority_one", { rooms: roomNames.join(this._t("iq.and")) }) : (hero.sub || this._t("iq.no_action"));
        const factTime = Number.isFinite(duration) && Math.abs(duration) >= .5 ? `<span><ha-icon icon="mdi:clock-outline"></ha-icon>${active.length && duration >= 0 ? this._t("iq.remaining", { count: Math.ceil(duration) }) : `${Math.max(1, Math.round(Math.abs(duration)))} min`}</span>` : "";
        const factMoisture = amount >= 1 ? `<span><ha-icon icon="mdi:water-outline"></ha-icon>≈ ${Math.round(amount)} ml</span>` : "";
        const roomCards = priority.slice(0, 2).map(r => {
            const canonicalMonitor = isCanonicalMonitorRoom(r);
            const [accent,,icon] = canonicalMonitor ? ["#63d2f7", "", "mdi:window-open"] : styleFor(r.action);
            const label = canonicalMonitor ? (this._uiLanguage() === "de" ? "Daueröffnung überwachen" : "Monitor long-term opening") : (r.active ? this._t("iq.active") : (this._uiLanguage() === "de" ? actionDE(r.action) : faiqEnglishText(actionDE(r.action))));
            const mins = Number(r.recommended_duration_min || r.remaining_duration_min || 0);
            const expanded = this._compactExpanded === `room:${r.key}`;
            const rawReasons = (r.recommendation_reasons || []).filter(Boolean);
            const reasons = rawReasons.length ? rawReasons : [reasonDE(r.reason)].filter(Boolean);
            const reasonHtml = reasons.slice(0, 4).map(x => `<div><ha-icon icon="mdi:check-circle-outline"></ha-icon><span>${esc(this._uiLanguage() === "de" ? x : faiqEnglishText(x))}</span></div>`).join("");
            const details = expanded ? `<div class="ai-inline-detail room-inline-detail" style="--detail:${accent}"><div class="ai-inline-title">${this._uiLanguage() === "de" ? "WARUM DIESER RAUM?" : "WHY THIS ROOM?"}</div>${reasonHtml || `<div><ha-icon icon="mdi:information-outline"></ha-icon><span>${esc(this._uiLanguage() === "de" ? "Die aktuelle FreshAirIQ-Entscheidung basiert auf den verfügbaren Raum- und Außendaten." : "The current FreshAirIQ decision is based on the available room and outdoor data.")}</span></div>`}${this._goalTracker(r,false)}<div class="ai-inline-values"><span>${fmt(r.temperature, 1)} °C · ${Math.round(Number(r.humidity || 0))} %</span><span>${fmt(r.absolute_humidity, 1)} g/m³</span>${Number(r.potential_ml || 0) > 0 ? `<span>≈ ${Math.round(Number(r.potential_ml))} ml</span>` : ""}</div><button class="ai-more" data-room="${esc(r.key)}">${this._uiLanguage() === "de" ? "Alle Raumdetails" : "All room details"}<ha-icon icon="mdi:chevron-right"></ha-icon></button></div>` : "";
            return `<div class="ai-room-wrap"><div class="ai-room" role="button" tabindex="0" data-compact-toggle="room:${esc(r.key)}" aria-expanded="${expanded ? "true" : "false"}" style="--room:${accent}"><ha-icon icon="${icon}"></ha-icon><div><b>${esc(r.name || r.key)}</b><small>${esc(label)}${mins > 0 ? ` · ${Math.round(mins)} min` : ""}</small></div><ha-icon class="ai-expand-chevron" icon="${expanded ? "mdi:chevron-up" : "mdi:chevron-down"}"></ha-icon></div>${details}</div>`;
        }).join("");
        const healthyCount = Math.max(0, calc.length - priority.length);
        const nightImportant = Boolean((st.night_strategy || {}).primary || st.night_strategy_primary || Number(st.overnight_forecast_ml || 0) > 0);
        const pollenBlocked = Boolean(st.pollen_blocked);
        const learningText = String(st.learning_status || st.learning_stage || this._t("iq.learning_active")).replaceAll("_", " ");
        const decisionExpanded = this._compactExpanded === "decision";
        const decisionReasons = (st.intelligent_recommendation?.reasons || st.intelligent_recommendation?.why || []).filter(Boolean).slice(0, 4);
        const freshyBrain = st.intelligent_recommendation || {};
        const freshySelected = (freshyBrain.selected_rooms || []).filter(Boolean);
        const freshySelectedRooms = freshySelected.length ? calc.filter(r => freshySelected.includes(r.name) || freshySelected.includes(r.key)) : priority;
        const freshyScope = this._presentationScope(freshyBrain, freshySelectedRooms);
        const freshyGoalChips = this._compactGoalChips(freshySelectedRooms);
        const decisionDetail = decisionExpanded ? `<div class="ai-inline-detail decision-inline-detail" style="--detail:${color}"><div class="ai-inline-title">${this._uiLanguage() === "de" ? "WARUM DIESE EMPFEHLUNG?" : "WHY THIS RECOMMENDATION?"}</div>${decisionReasons.map(x => `<div><ha-icon icon="mdi:check-circle-outline"></ha-icon><span>${esc(this._uiLanguage() === "de" ? x : faiqEnglishText(x))}</span></div>`).join("") || `<div><ha-icon icon="mdi:information-outline"></ha-icon><span>${esc(this._uiLanguage() === "de" ? (hero.sub || "FreshAirIQ bewertet fortlaufend Raum-, Außen- und Prognosedaten.") : faiqEnglishText(hero.sub || "FreshAirIQ continuously evaluates room, outdoor and forecast data."))}</span></div>`}<button class="ai-more" data-info="decision">${this._uiLanguage() === "de" ? "Vollständige Entscheidung" : "Full decision"}<ha-icon icon="mdi:chevron-right"></ha-icon></button></div>` : "";
        return `<section class="ai-compact ${kind}" style="--ai:${color}">
          <div class="ai-assistant" role="button" tabindex="0" data-compact-toggle="decision" aria-expanded="${decisionExpanded ? "true" : "false"}">
            <div class="ai-mascot-wrap fr-wrap">${freshySvg(freshyMood, 112, this._uiLanguage(), freshyProgress)}</div>
            <div class="ai-copy"><div class="ai-scope${["RÄUME","ROOMS"].includes(freshyScope) ? " clickable" : ""}"${["RÄUME","ROOMS"].includes(freshyScope) ? ' data-info="rooms" role="button" tabindex="0" aria-label="' + esc(this._t("shell.rooms")) + '"' : ""}>${esc(freshyScope)}</div><div class="ai-kicker">${esc(this._t("iq.handling"))}</div><h2>${esc(this._uiLanguage() === "de" ? (hero.title || this._t("iq.all_good")) : faiqEnglishText(hero.title || this._t("iq.all_good")))}</h2><p>${esc(summary)}</p>${freshyGoalChips}<div class="ai-facts">${factTime}${factMoisture}</div></div>
            <ha-icon class="ai-chevron" icon="${decisionExpanded ? "mdi:chevron-up" : "mdi:chevron-down"}"></ha-icon>
          </div>
          ${decisionDetail}
          ${roomCards ? `<div class="ai-attention">${roomCards}</div>` : ""}
          <div class="ai-all-good clickable" data-info="rooms"><ha-icon icon="mdi:check-circle-outline"></ha-icon><span>${priority.length ? this._t("iq.more_rooms_ok", { count: healthyCount }) : this._t("iq.all_rooms_ok", { count: calc.length })}</span><ha-icon icon="mdi:chevron-right"></ha-icon></div>
          <div class="ai-context">
            <button data-info="night" style="--ctx:${nightImportant ? "#e2bd69" : "#7ec8ff"}"><ha-icon icon="mdi:weather-night"></ha-icon><span><b>${esc(this._t("iq.night"))}</b><small>${esc(this._t(nightImportant ? "iq.notice" : "iq.monitored"))}</small></span></button>
            <button data-info="pollen" style="--ctx:${pollenBlocked ? "#e2bd69" : "#62e889"}"><ha-icon icon="mdi:leaf"></ha-icon><span><b>${esc(this._t("iq.pollen"))}</b><small>${esc(this._t(pollenBlocked ? "iq.watch" : "iq.okay"))}</small></span></button>
            <button data-info="learning:quality" style="--ctx:#b68cff"><ha-icon icon="mdi:brain"></ha-icon><span><b>${esc(this._t("iq.learning"))}</b><small>${esc(this._uiLanguage() === "de" ? learningText : faiqEnglishText(learningText))}</small></span></button>
          </div>
        </section>`;
    }
    _intelligentPanel(st, rooms = []) {
        let iq = st.intelligent_recommendation || {};
        const brain = iq.decision_brain || {};
        const state = st.iq_state || {};
        if (!brain.headline && !iq.title && rooms.length) {
            const calc = rooms.filter(r => r.calculation_enabled !== false);
            const active = calc.filter(r => r.active);
            const close = calc.filter(r => r.action === "Close");
            const vent = calc.filter(r => r.action === "Ventilate" || r.action === "Ventilate for cooling");
            if (close.length)
                iq = { kind: "close", severity: "warning", title: "Jetzt schließen", instruction: close.map(r => r.name).join(", ") };
            else if (active.length)
                iq = { kind: "continue", severity: "good", title: "Lüftung läuft", instruction: active.map(r => r.name).join(", ") };
            else if (vent.length)
                iq = { kind: "ventilate", severity: "good", title: "Jetzt lüften", instruction: vent.map(r => r.name).join(", ") };
        }
        const calcRooms = rooms.filter(r => r.calculation_enabled !== false);
        const active = calcRooms.filter(r => r.active);
        const finalizing = st.finalizing_measurements || {};
        const activelyVentilating = active.filter(r => !r.session_finalization_pending);
        if (finalizing.active && !activelyVentilating.length) {
            const roomNames = Array.isArray(finalizing.room_names) ? finalizing.room_names.filter(Boolean) : [];
            const remaining = Math.max(0, Math.ceil(Number(finalizing.wait_remaining_s || 0)));
            const roomText = roomNames.length ? roomNames.slice(0, 3).join(" + ") : `${Number(finalizing.room_count || 1)} Raum/Räume`;
            const waitText = remaining > 0 ? `Noch maximal ${remaining} s` : "Rückmeldung wird geprüft";
            return `<section class="decision-card ai-card" style="--decision:#63d2f7">
      <div class="decision-kicker"><span class="decision-dot"></span>ABSCHLUSSMESSUNG</div>
      <div class="decision-main">
        <div class="decision-icon"><ha-icon icon="mdi:progress-clock"></ha-icon></div>
        <div><h2>Warte kurz auf die Klimasensoren</h2><div class="decision-action">Fenster geschlossen · ${esc(roomText)}</div></div>
      </div>
      <p class="decision-summary">FreshAirIQ hat die Lüftung beendet und fordert jetzt noch einmal die bereits konfigurierten Temperatur- und Feuchtesensoren an. Erst danach wird das Ergebnis angezeigt.</p>
      <div class="decision-impacts context-impacts"><div class="decision-impact forecast"><span>STATUS</span><b>${esc(waitText)}</b><small>frische Abschlusswerte werden eingesammelt</small></div></div>
      <div class="iq-process"><div class="iq-process-head"><span class="iq-pulse"></span><b>IQ AKTIV</b><span>Abschlussauswertung</span></div><div class="iq-process-text">Kein Stillstand: FreshAirIQ wartet bewusst kurz auf eine aktuelle Sensor-Rückmeldung. Antwortet ein Batteriesensor nicht, endet die Gnadenfrist automatisch und die Messqualität wird aus den tatsächlich während der Lüftung beobachteten Meldungen bewertet.</div></div>
    </section>`;
        }
        const recentVentilation = active.length ? null : this._recentVentilation(st);
        if (recentVentilation) return this._ventilationResultCard(recentVentilation, "hero");
        const bad = calcRooms.filter(r => r.data_quality !== "ok");
        const mouldRooms = calcRooms.filter(r => ["Elevated", "High", "Very high"].includes(r.mould_level));
        const kind = String(iq.kind || "okay");
        const passiveOpenMonitor = String(iq.status || st.status || "") === "passive_open_monitor";
        const nightStrategy = st.night_strategy || brain.night_strategy || {};
        const nightPrimary = Boolean(iq.night_strategy_primary || brain.night_strategy_primary);
        const color = nightPrimary ? "#7ec8ff" : iq.severity === "danger" ? "#ff7770" : iq.severity === "warning" ? "#e2bd69" :
            ["ventilate", "continue"].includes(kind) ? "#62e889" : passiveOpenMonitor || kind === "prepare" ? "#63d2f7" : "#8fa0ac";
        const icon = nightPrimary ? (nightStrategy.action === "close" ? "mdi:weather-night-partly-cloudy" : "mdi:weather-night") :
            kind === "ventilate" ? "mdi:weather-windy" : kind === "continue" ? "mdi:weather-windy-variant" :
                kind === "close" ? "mdi:window-closed-variant" : kind === "sensor" ? "mdi:alert-circle-outline" :
                    kind === "wait" || kind === "pollen_wait" ? "mdi:clock-outline" : passiveOpenMonitor ? "mdi:window-open" : kind === "prepare" ? "mdi:weather-sunset-up" : "mdi:brain";
        const headline = brain.headline || iq.title || state.headline || "FreshAirIQ überwacht";
        const action = brain.action_line || iq.instruction || state.summary || "";
        const label = brain.decision_label || (passiveOpenMonitor ? "DAUER-/KIPPLÜFTUNG" : (["continue", "close"].includes(kind) ? "LIVE-OPTIMIERUNG" : "FRESHAIRIQ ENTSCHEIDUNG"));
        const summary = brain.summary || iq.summary || state.summary || "";
        const why = (brain.why || iq.reasons || state.explanation || []).filter(Boolean).slice(0, 4);
        const impact = brain.impact || {};
        const comparison = brain.comparison || {};
        const selected = (brain.selected_rooms || []).filter(Boolean);
        const forecastH = Math.max(1, Math.round(this._forecastValue(st) || 5));
        const forecastDataH = Math.max(1, Math.round(Number(st.forecast_horizon_min || 5)));
        const forecastPending = forecastH !== forecastDataH;
        const selectedRoomObjs = selected.length ? calcRooms.filter(r => selected.includes(r.name) || selected.includes(r.key)) : [];
        const idleForecastRooms = selectedRoomObjs.length ? selectedRoomObjs : calcRooms.filter(r => r.data_quality === "ok" && r.ventilation_candidate);
        const forecastRooms = active.length ? active : idleForecastRooms;
        const houseShortEffect = st.house_ventilation_mode && iq.house_next_5_min_moisture_effect_ml != null ? Number(iq.house_next_5_min_moisture_effect_ml) : null;
        const forecastEffect = active.length ? (forecastH === 5 && houseShortEffect != null ? houseShortEffect : Number(st.forecast_moisture_effect_ml || 0)) : forecastRooms.reduce((a, r) => a + Number(r.forecast_moisture_effect_ml || 0), 0);
        const forecastUncappedEffect = active.length ? Number(st.forecast_uncapped_moisture_effect_ml != null ? st.forecast_uncapped_moisture_effect_ml : forecastEffect) : forecastRooms.reduce((a, r) => a + Number(r.forecast_uncapped_moisture_effect_ml != null ? r.forecast_uncapped_moisture_effect_ml : r.forecast_moisture_effect_ml || 0), 0);
        const forecastTargetLimited = active.length ? Boolean(st.forecast_target_limited) : forecastRooms.some(r => Boolean(r.forecast_target_limited));
        const forecastLiveAdapted = active.length ? Boolean(st.forecast_live_adapted) : forecastRooms.some(r => Boolean(r.forecast_live_adapted));
        const forecastCost = active.length ? Number(st.forecast_cost || 0) : forecastRooms.reduce((a, r) => a + Number(r.forecast_cost || 0), 0);
        const forecastVolume = forecastRooms.reduce((a, r) => a + Number(r.volume_m3 || 0), 0);
        const forecastTemp = active.length ? Number(st.forecast_temperature_change_c || 0) : (forecastVolume > 0 ? forecastRooms.reduce((a, r) => a + Number(r.forecast_temperature_change_c || 0) * Number(r.volume_m3 || 0), 0) / forecastVolume : 0);
        const forecastConfidence = active.length ? Number(st.forecast_confidence || 0) : (forecastVolume > 0 ? forecastRooms.reduce((a, r) => a + Number(r.forecast_confidence || 0) * Number(r.volume_m3 || 0), 0) / forecastVolume : 0);
        const liveBalance = Number(st.live_balance_ml || 0);
        const potential = Number(st.potential_total_ml || 0);
        const night = Number(st.overnight_forecast_ml || 0);
        const remaining = Number(st.remaining_duration_min || 0);
        const currentTemp = Number(st.temperature_change_live_c || 0);
        const showMoisture = this._config.info_moisture !== false;
        const showTemperature = this._config.info_temperature !== false;
        const showTime = this._config.info_time !== false;
        const showForecast = this._config.info_forecast !== false;
        const showNight = this._config.info_night !== false;
        const showMould = this._config.info_mould !== false;
        const showEnergy = this._config.info_energy !== false;
        const showPollen = this._config.info_pollen !== false;
        const showCrossVentilation = this._config.info_cross_ventilation !== false;
        const contextCards = [];
        const forecastMeta = (includeConfidence = false) => {
            const parts = [];
            if (active.length && forecastLiveAdapted) parts.push("Live-Messverlauf berücksichtigt");
            if (active.length && forecastTargetLimited && Math.abs(forecastUncappedEffect - forecastEffect) >= 1) parts.push("am Feuchteziel begrenzt");
            if (showTemperature) parts.push(signed(forecastTemp, "°C"));
            if (showEnergy) parts.push(`${fmt(forecastCost, 2)} €`);
            if (active.length && forecastH > 5) {
                const optimum = Number(st.forecast_optimal_close_in_min);
                if (Number.isFinite(optimum) && optimum > 0 && optimum <= forecastH) parts.push(`optimal noch ca. ${Math.round(optimum)} min`);
                else if (st.forecast_optimal_close_in_min == null) parts.push(`Endpunkt > ${forecastH} min`);
            }
            if (includeConfidence) parts.push(`IQ ${Math.round(forecastConfidence)} %`);
            return parts.join(" · ") || "modellierte Wirkung";
        };
        if (active.length) {
            const m = moisture(liveBalance);
            if (showMoisture)
                contextCards.push(`<div class="decision-impact live clickable" data-info="moisture"><span>BISHER</span><b style="color:${m.color}">${m.text}</b><small>seit Lüftungsbeginn</small></div>`);
            if (showForecast) {
                if (forecastPending) {
                    contextCards.push(`<div class="decision-impact forecast clickable" data-info="next5"><span>WEITERE ${forecastH} MIN</span><b>Wird berechnet …</b><small>FreshAirIQ aktualisiert Feuchte, Temperatur und Kosten für den neuen Zeitraum.</small></div>`);
                } else {
                    const forecastDisplayEffect = forecastEffect;
                    const f = moisture(forecastDisplayEffect);
                    contextCards.push(`<div class="decision-impact forecast clickable" data-info="next5"><span>WEITERE ${forecastH} MIN</span><b style="color:${f.color}">${f.text}</b><small>${forecastMeta(false)}</small></div>`);
                }
            }
            if (showTemperature && Math.abs(currentTemp) >= .01)
                contextCards.push(`<div class="decision-impact clickable" data-info="temperature"><span>TEMPERATUR LIVE</span><b>${signed(currentTemp, "°C")}</b><small>seit Start</small></div>`);
            if (showTime && Number.isFinite(remaining)) {
                if (passiveOpenMonitor)
                    contextCards.push(`<div class="decision-impact clickable" data-info="time"><span>DAUERÖFFNUNG</span><b>wird überwacht</b><small>Temperatur & Feuchte werden laufend geprüft</small></div>`);
                else
                    contextCards.push(`<div class="decision-impact clickable" data-info="time"><span>IQ-ZEIT</span><b>${remaining > 0 ? `${Math.ceil(remaining)} min` : remaining < 0 ? `+${Math.ceil(Math.abs(remaining))} min` : "0 min"}</b><small>${remaining > 0 ? "bis Ziel" : remaining < 0 ? "über Ziel" : "Ziel erreicht"}</small></div>`);
            }
        }
        else {
            const p = moisture(potential);
            if (showMoisture)
                contextCards.push(`<div class="decision-impact clickable" data-info="moisture"><span>JETZT ENTFERNBAR</span><b style="color:${p.color}">${p.text}</b><small>Schwelle ${Math.round(Number(st.ventilation_threshold_ml || 0))} ml</small></div>`);
            // v0.20.4.2: Vor Lüftungsbeginn keine zeitgebundene Lüftungsprognose anzeigen.
            // Die Prognose bleibt intern vollständig berechnet und erscheint erst bei aktiver Lüftung
            // als "WEITERE <Horizont> MIN". So bleibt die Vorher-Ansicht eine reine Entscheidungshilfe.
            if (showMoisture)
                contextCards.push(`<div class="decision-impact clickable" data-info="water"><span>WASSER IN DER LUFT</span><b>${Math.round(Number(st.total_water_ml || 0))} ml</b><small>${calcRooms.length} berechnete Räume</small></div>`);
            const nightWithoutRaw = nightStrategy.forecast_without_action_ml;
            const nightWithRaw = nightStrategy.forecast_with_strategy_ml;
            const nightWithout = Number(nightWithoutRaw);
            const nightWith = Number(nightWithRaw);
            const hasNightComparison = nightWithoutRaw !== null && nightWithoutRaw !== undefined && nightWithRaw !== null && nightWithRaw !== undefined && Number.isFinite(nightWithout) && Number.isFinite(nightWith);
            if (showNight && nightStrategy.active && hasNightComparison && Math.abs(nightWith - nightWithout) >= 1) {
                const nightBenefit = Math.round(nightWithout - nightWith);
                const strategyText = nightStrategy.action === "open_selected" ? "kontrolliert über Nacht lüften" : nightStrategy.action === "pre_ventilate" ? "vor dem Schlafengehen kurz lüften, dann schließen" : "empfohlenen Fensterzustand nutzen";
                const benefitText = nightBenefit >= 10 ? `Mit der Empfehlung erwartet FreshAirIQ morgen rund ${nightBenefit} ml weniger Feuchte.` : nightBenefit > 0 ? `Die Empfehlung bringt voraussichtlich nur einen kleinen Vorteil von rund ${nightBenefit} ml.` : `Für diese Nacht ist kein messbarer Feuchtevorteil durch zusätzliches Lüften zu erwarten.`;
                contextCards.push(`<div class="decision-impact night-context night-comparison clickable" data-info="night"><span>WAS BRINGT LÜFTEN VOR DEM SCHLAFEN?</span><div class="night-comparison-grid"><div class="night-comparison-side"><span>OHNE ZUSÄTZLICHES LÜFTEN</span><b>${nightWithout >= 0 ? "+" : ""}${Math.round(nightWithout)} ml</b><small>bis morgen früh</small></div><div class="night-comparison-arrow">→</div><div class="night-comparison-side"><span>MIT EMPFEHLUNG</span><b>${nightWith >= 0 ? "+" : ""}${Math.round(nightWith)} ml</b><small>${esc(strategyText)}</small></div></div><div class="night-comparison-benefit">${esc(benefitText)}</div></div>`);
            }
            else if (showNight && Number.isFinite(night)) {
                contextCards.push(`<div class="decision-impact clickable" data-info="night"><span>NACHTPROGNOSE</span><b>${night >= 0 ? "+" : ""}${Math.round(night)} ml</b><small>bis Nachtende · IQ ${Math.round(Number(st.overnight_confidence || 0))} %</small></div>`);
            }
            if (showMould)
                contextCards.push(`<div class="decision-impact clickable" data-info="mould"><span>SCHIMMEL</span><b>${mouldRooms.length ? `${mouldRooms.length} auffällig` : "unauffällig"}</b><small>max. ${Math.round(Number(st.max_surface_rh || 0))} % Oberflächen-RH</small></div>`);
        }
        if (showMoisture && !active.length && Number(impact.moisture_ml || 0) > 0 && Math.abs(Number(impact.moisture_ml) - Math.abs(forecastEffect)) > 1)
            contextCards.push(`<div class="decision-impact clickable" data-info="decision"><span>ENTSCHEIDUNGSWIRKUNG</span><b>−${Math.round(Number(impact.moisture_ml))} ml</b><small>${Number(impact.duration_min || 0) > 0 ? `${fmt(Number(impact.duration_min), 0)} min` : "bewertete Option"}</small></div>`);
        if (showNight && nightStrategy.active && !nightPrimary) {
            const delta = Number(nightStrategy.outside_minus_inside_ah_g_m3);
            const nightRooms = Array.isArray(nightStrategy.selected_rooms) ? nightStrategy.selected_rooms.filter(Boolean) : [];
            const nightAction = nightStrategy.action === "close" ? "geschlossen" : nightStrategy.action === "open_selected" ? (nightRooms.length ? `${nightRooms.join(" + ")} teilweise offen` : "teilweise offen") : nightStrategy.action === "pre_ventilate" ? (nightRooms.length ? `${nightRooms.join(" + ")} kurz vorlüften` : "vorher lüften") : "beobachten";
            contextCards.push(`<div class="decision-impact night-context clickable" data-info="night"><span>NACHTSTRATEGIE</span><b>${esc(nightAction)}</b><small>${Number.isFinite(delta) ? `${delta >= 0 ? "+" : ""}${fmt(delta, 1)} g/m³ außen` : "Wetter wird bewertet"} · IQ ${Math.round(Number(nightStrategy.confidence || 0))} %</small></div>`);
        }
        let compareHtml = "";
        if (showForecast && (Number(comparison.future_ml || 0) > 0 || Number(comparison.now_ml || 0) > 0)) {
            compareHtml = `<div class="decision-compare"><div><span>JETZT</span><b>${Math.round(Number(comparison.now_ml || 0))} ml</b></div><ha-icon icon="mdi:arrow-right"></ha-icon><div><span>${esc(comparison.alternative_label || "SPÄTER")}</span><b>${Math.round(Number(comparison.future_ml || 0))} ml</b></div></div>`;
        }

        const analysisBits = [];
        analysisBits.push(`${calcRooms.length} Räume`);
        if (showForecast && st.future_weather_available)
            analysisBits.push("Wetterprognose");
        if (showNight && nightStrategy.active)
            analysisBits.push("Nachtstrategie");
        if (showMoisture && showTemperature) analysisBits.push("Feuchte & Temperatur");
        else if (showMoisture) analysisBits.push("Feuchte");
        else if (showTemperature) analysisBits.push("Temperatur");
        if (showCrossVentilation && st.cross_ventilation)
            analysisBits.push("Querlüftung");
        if (showPollen && st.pollen_enabled)
            analysisBits.push("Pollen");
        if (Number(st.house_strategy_samples || 0) > 0)
            analysisBits.push("Lernmodell");
        const optionCount = Number(brain.short_term_options || 0) + Number(brain.long_term_options || 0);
        const learningActive = active.filter(r => r.session_measurement_quality?.timestamp_gate_passed === true);
        const learningWaiting = active.filter(r => r.session_measurement_quality?.timestamp_gate_passed !== true);
        const learningNames = learningActive.slice(0,2).map(r => r.name).join(" + ");
        const processText = passiveOpenMonitor
            ? `DAUER-/KIPPLÜFTUNG WIRD ÜBERWACHT: FreshAirIQ prüft Temperatur, Feuchtebilanz und Außenbedingungen fortlaufend und empfiehlt das Schließen, sobald die Daueröffnung ungünstig wird.`
            : active.length
            ? learningActive.length
                ? `LERNT JETZT: IQ lernt gerade den realen Luftaustausch${learningNames ? ` in ${learningNames}` : ""} · Feuchtewirkung · Temperaturreaktion · optimale Schließzeit · ${learningActive.length} verwertbare Messrahmen${learningWaiting.length ? ` · ${learningWaiting.length} Raum/Räume warten noch auf passende Sensordaten` : ""}`
                : `LÜFTUNG WIRD BEOBACHTET: FreshAirIQ sammelt aktuelle Temperatur- und Feuchtemeldungen · für eine Modellanpassung fehlen noch zeitlich passende Sensordaten`
            : bad.length
                ? `${bad.length} Datenquelle(n) prüfen · verbleibende Daten werden weiter bewertet`
                : showNight && nightStrategy.active
                    ? (() => {
                        const n0 = Number(nightStrategy.forecast_without_action_ml);
                        const n1 = Number(nightStrategy.forecast_with_strategy_ml);
                        const gain = Number.isFinite(n0) && Number.isFinite(n1) ? Math.round(n0 - n1) : 0;
                        if (gain > 0) return `FreshAirIQ erwartet mit der empfohlenen Nachtstrategie morgen früh etwa ${gain} ml weniger Feuchte. Wetter, Außenluft und deine gelernten Raumverläufe fließen in diesen Vergleich ein.`;
                        return `FreshAirIQ vergleicht die erwartete Nachtentwicklung mit und ohne Eingriff. Aktuell ergibt sich kein belastbarer zusätzlicher Feuchtegewinn durch eine andere Strategie.`;
                    })()
                    : `${analysisBits.join(" · ")} analysiert${optionCount ? ` · ${optionCount} Optionen bewertet` : ""}`;
        return `<section class="decision-card ai-card" style="--decision:${color}">
      <div class="decision-scope">${esc(this._presentationScope(brain, selectedRoomObjs))}</div>
      <div class="decision-kicker"><span class="decision-dot"></span>${esc(label)}</div>
      <div class="decision-main">
        <div class="decision-icon"><ha-icon icon="${icon}"></ha-icon></div>
        <div><h2>${esc(headline)}</h2><div class="decision-action">${esc(action)}</div></div>
      </div>
      ${this._decisionGoalOverview(selectedRoomObjs, passiveOpenMonitor)}
      ${!selectedRoomObjs.length && selected.length ? `<div class="decision-rooms">${selected.map(x => `<span>${esc(x)}</span>`).join("")}</div>` : ""}
      ${contextCards.length ? `<div class="decision-impacts context-impacts">${contextCards.join("")}</div>` : ""}
      ${compareHtml}
      ${(summary || why.length || brain.alternative || this._config.show_iq_process !== false) ? `<details class="decision-more"><summary data-classic-disclosure="decision"><span>Mehr zur Entscheidung</span><span class="decision-more-hint">Begründung & IQ-Analyse</span><ha-icon icon="mdi:chevron-down"></ha-icon></summary><div class="decision-more-content">${summary ? `<p class="decision-summary">${esc(summary)}</p>` : ""}${why.length ? `<div class="decision-why"><div class="decision-section-title">WARUM DIESE ENTSCHEIDUNG?</div>${why.map(x => `<div><ha-icon icon="mdi:check-circle-outline"></ha-icon><span>${esc(x)}</span></div>`).join("")}</div>` : ""}${brain.alternative ? `<div class="decision-alternative"><b>Alternative:</b> ${esc(brain.alternative)}</div>` : ""}${this._config.show_iq_process === false ? "" : `<div class="iq-process"><div class="iq-process-head"><span class="iq-pulse"></span><b>IQ AKTIV</b><span>${active.length && showForecast ? `Prognose ${forecastH} min · ` : ""}${Math.round(forecastConfidence || Number(impact.confidence || 0))} % Sicherheit</span></div><div class="iq-process-text">${esc(processText)}</div></div>`}</div></details>` : ""}
    </section>`;
    }
    _presentationScope(brain, rooms) {
        const de = this._uiLanguage() === "de";
        const scope = String((brain && brain.presentation_scope) || "rooms");
        if (scope === "house") return de ? "HAUS" : "WHOLE HOME";
        if (scope === "floor") return String((brain && brain.presentation_floor) || (de ? "ETAGE" : "FLOOR")).toUpperCase();
        if ((rooms || []).length === 1) return String((rooms[0] && (rooms[0].name || rooms[0].key)) || (de ? "RAUM" : "ROOM")).toUpperCase();
        return de ? "RÄUME" : "ROOMS";
    }
    _compactGoalChips(rooms) {
        const selected = (rooms || []).filter(r => r && r.goal_state && Array.isArray(r.goal_state.goals));
        if (!selected.length) return "";
        const de = this._uiLanguage() === "de";
        const labels = {humidity:de?"Feuchte":"Humidity",co2:"CO₂",temperature:de?"Temperatur":"Temperature"};
        const colors = {humidity:"#62e889",co2:"#b68cff",temperature:"#63d2f7"};
        const agg = new Map();
        for (const r of selected) {
            const gs=r.goal_state||{}; const priority=Array.isArray(gs.priorities)?gs.priorities:[];
            for (const g of (gs.goals||[]).filter(x=>x&&x.active)) {
                const a=agg.get(g.id)||{id:g.id,total:0,reached:0,open:0,blocked:0,eta:[],driver:false};
                a.total++; if(g.reached)a.reached++; else if(g.achievable_now){a.open++; if(g.eta_min!=null)a.eta.push(Number(g.eta_min));} else a.blocked++;
                if(g.id===gs.driving_goal || (!gs.driving_goal && !g.reached && priority[0]===g.id)) a.driver=true; agg.set(g.id,a);
            }
        }
        const order=["humidity","co2","temperature"];
        const chips=order.filter(id=>agg.has(id)).map(id=>{const a=agg.get(id); const eta=a.eta.length?Math.max(...a.eta):null; const status=a.reached===a.total?"✓":eta!=null?`~${Math.max(1,Math.round(eta))} min`:a.open?(de?"offen":"open"):(de?"blockiert":"blocked"); return `<span class="ai-goal-chip ${a.driver?"driver":""}" style="--goal:${colors[id]}">${esc(labels[id])} ${esc(status)}</span>`;}).join("");
        return chips?`<div class="ai-goal-line">${chips}</div>`:"";
    }
    _decisionGoalOverview(rooms, passiveOpenMonitor=false) {
        const selected = (rooms || []).filter(r => r && r.goal_state && Array.isArray(r.goal_state.goals));
        if (!selected.length) return "";
        const de = this._uiLanguage() === "de";
        const goalIcons = {humidity:"mdi:water-outline",temperature:"mdi:thermometer",co2:"mdi:molecule-co2"};
        const goalNames = {humidity:de?"Entfeuchtung":"Humidity",temperature:de?"Temperatur":"Temperature",co2:"CO₂"};
        const goalColors = {humidity:"#63d2f7",temperature:"#f0b56b",co2:"#a9d57a"};
        const goalOrder = ["humidity","temperature","co2"];
        const aggregate = new Map();
        for (const r of selected) {
            for (const g of (r.goal_state.goals || []).filter(x => x && x.active)) {
                const a = aggregate.get(g.id) || {total:0,reached:0,eta:[],blocked:0,blockedRooms:[],goals:[]};
                a.total += 1;
                a.goals.push(g);
                if (g.reached) a.reached += 1;
                else if (g.achievable_now && g.eta_min != null && Number.isFinite(Number(g.eta_min))) a.eta.push(Number(g.eta_min));
                else if (!g.achievable_now) { a.blocked += 1; a.blockedRooms.push(String(r.name || r.key)); }
                aggregate.set(g.id,a);
            }
        }
        const fallbackGoalEta = id => {
            const values = selected.flatMap(r => {
                const goal = (r.goal_state?.goals || []).find(g => g && g.id === id && g.active && !g.reached && g.achievable_now);
                if (!goal) return [];
                const raw = r.session_recommended_duration_min ?? r.recommended_duration_min;
                const value = Number(raw);
                return Number.isFinite(value) && value > 0 ? [value] : [];
            });
            return values.length ? Math.max(...values) : null;
        };
        // 0.26.3.2: plain-language goal lines. "0/2" and a red cross were not
        // understandable; a blocked goal is a normal trade-off, not an error.
        const goalLabels = {humidity:de?"Entfeuchten":"Dehumidify",temperature:de?"Abkühlen":"Cool down",co2:de?"Frischluft (CO₂)":"Fresh air (CO₂)"};
        const goalValue = (id, v) => { const n = Number(v); if (v == null || !Number.isFinite(n)) return ""; return id === "temperature" ? `${fmt(n, 1)} °C` : id === "co2" ? `${Math.round(n)} ppm` : `${Math.round(n)} %`; };
        const goalValues = g => { const now = goalValue(g.id, g.value), target = goalValue(g.id, g.target); return now && target ? (de ? `jetzt ${now} · Ziel ${target}` : `now ${now} · target ${target}`) : ""; };
        const etaText = m => `${de ? "ca." : "approx."} ${Math.max(1, Math.round(m))} min`;
        const houseGoals = goalOrder.filter(id => aggregate.has(id)).map(id => {
            const a = aggregate.get(id);
            const maxEta = a.eta.length ? Math.max(...a.eta) : fallbackGoalEta(id);
            const open = a.total - a.reached - a.blocked;
            const state = a.reached === a.total ? "reached" : open > 0 ? "open" : "blocked";
            const parts = [];
            if (state === "reached") parts.push(de ? "erreicht" : "reached");
            else if (state === "blocked") parts.push(de ? "gerade nicht möglich" : "not possible right now");
            else {
                if (a.total > 1) parts.push(de ? `${a.reached} von ${a.total} Räumen` : `${a.reached} of ${a.total} rooms`);
                if (maxEta != null) parts.push(etaText(maxEta));
                if (a.blocked) parts.push(de ? `${a.blocked} nicht möglich` : `${a.blocked} not possible`);
                if (!parts.length) parts.push(de ? "läuft" : "in progress");
            }
            const text = parts.join(" · ");
            return `<div class="goal-line ${state}" style="--goal:${goalColors[id]}" role="group" aria-label="${esc(`${goalLabels[id]}: ${text}`)}"><ha-icon icon="${state === "reached" ? "mdi:check" : goalIcons[id]}"></ha-icon><b>${esc(goalLabels[id])}</b><span class="goal-line-state">${esc(text)}</span></div>`;
        }).join("");
        const roomRows = selected.map(r => {
            const gs = r.goal_state || {};
            const active = (gs.goals || []).filter(g => g && g.active);
            if (!active.length) return "";
            const priority = Array.isArray(gs.priorities) ? gs.priorities : [];
            const driver = active.find(g => g.id === gs.driving_goal && !g.reached) || active.find(g => !g.reached && g.achievable_now && priority.includes(g.id)) || active.find(g => !g.reached && g.achievable_now) || active.find(g => !g.reached) || active[0];
            const roomEta = g => { const raw = g.eta_min != null ? g.eta_min : (r.session_recommended_duration_min ?? r.recommended_duration_min); const n = Number(raw); return Number.isFinite(n) && n > 0 ? n : null; };
            let statusText, statusClass;
            if (active.every(g => g.reached)) { statusText = de ? "Ziele erreicht" : "Goals reached"; statusClass = "reached"; }
            else if (driver.achievable_now && !driver.reached) { const m = roomEta(driver); statusText = `${goalLabels[driver.id] || driver.id}${m != null ? ` · ${etaText(m)}` : ""}`; statusClass = "open"; }
            else { statusText = `${goalLabels[driver.id] || driver.id}: ${de ? "gerade nicht möglich" : "not possible now"}`; statusClass = "blocked"; }
            const otherBlocked = active.filter(g => g !== driver && !g.reached && !g.achievable_now);
            const note = otherBlocked.length ? `<span class="goal-room-note">${esc(`${otherBlocked.map(g => goalLabels[g.id] || g.id).join(", ")}: ${de ? "gerade nicht möglich" : "not possible right now"}`)}</span>` : "";
            const goalList = active.map(g => {
                const title = goalLabels[g.id] || g.id;
                const state = g.reached ? (de ? "erreicht" : "reached") : g.achievable_now ? (roomEta(g) != null ? etaText(roomEta(g)) : (de ? "läuft" : "in progress")) : (de ? "gerade nicht möglich" : "not possible right now");
                const stateClass = g.reached ? "reached" : g.achievable_now ? "open" : "blocked";
                const values = g.reached ? "" : goalValues(g);
                return `<div class="goal-room-goal ${stateClass}" aria-label="${esc(title)}"><ha-icon class="goal-kind" icon="${goalIcons[g.id] || "mdi:target"}"></ha-icon><span><b>${esc(title)}</b><small>${esc(state)}${values ? ` · ${esc(values)}` : ""}</small></span></div>`;
            }).join("");
            const order = priority.filter(id => active.some(g => g.id === id));
            const priorityLine = order.length > 1 ? `<div class="goal-room-priority">${de ? "Priorität" : "Priority"}: ${order.map((id, i) => `${i + 1}. ${esc(goalLabels[id] || id)}`).join(" · ")}</div>` : "";
            const openBlocked = active.find(g => !g.reached && !g.achievable_now);
            const openGoal = active.find(g => !g.reached);
            const roomReasons = (r.recommendation_reasons || []).filter(Boolean);
            const fallbackReason = reasonDE(r.reason);
            let protection = "";
            if (gs.hard_close && openGoal) {
                const blockedName = goalLabels[(openBlocked || openGoal).id] || (openBlocked || openGoal).id;
                const reason = roomReasons[0] || fallbackReason || (de?"Eine Schutzgrenze ist erreicht.":"A protection limit has been reached.");
                protection = `<div class="decision-goal-protection"><ha-icon icon="mdi:shield-alert-outline"></ha-icon><span><b>${esc(blockedName)}:</b> ${esc(reason)}</span></div>`;
            }
            const details = roomReasons.length ? roomReasons : [fallbackReason].filter(Boolean);
            const canonicalMonitor = passiveOpenMonitor && r.active;
            const displayAction = canonicalMonitor ? "Daueröffnung überwachen" : actionDE(r.action);
            return `<details class="decision-goal-room decision-room-disclosure"><summary data-classic-disclosure="room:${esc(r.key)}"><span class="decision-goal-room-name">${esc(r.name||r.key)}</span><span class="goal-room-status ${statusClass}">${esc(statusText)}</span><ha-icon class="decision-goal-chevron" icon="mdi:chevron-down"></ha-icon>${note}</summary><div class="decision-goal-room-detail"><div class="decision-goal-action"><strong>${esc(displayAction)}</strong></div><div class="goal-room-goals">${goalList}</div>${priorityLine}${protection}${openBlocked?`<div class="decision-goal-explain"><ha-icon icon="mdi:information-outline"></ha-icon><span>${de?`${goalLabels[openBlocked.id]||openBlocked.id} ist gerade nicht durch Lüften erreichbar – FreshAirIQ verfolgt zuerst die anderen Ziele.`:`${goalLabels[openBlocked.id]||openBlocked.id} cannot be reached by ventilating right now – FreshAirIQ pursues the other goals first.`}</span></div>`:""}<div class="decision-section-title">${de?"WARUM DIESER RAUM?":"WHY THIS ROOM?"}</div>${details.map(x=>`<div class="decision-room-reason"><ha-icon icon="mdi:check-circle-outline"></ha-icon><span>${esc(x)}</span></div>`).join("")}<button class="decision-room-open" type="button" data-room="${esc(r.key)}">${de?"Raumdetails öffnen ›":"Open room details ›"}</button></div></details>`;
        }).filter(Boolean).join("");
        if (!houseGoals && !roomRows) return "";
        return `<div class="decision-goal-overview compact"><div class="decision-house-goals goal-lines">${houseGoals}</div>${roomRows?`<details class="decision-goal-rooms"><summary data-classic-disclosure="goal-rooms"><span>${de?"Räume & Ziele anzeigen":"Show rooms & goals"} (${selected.length})</span><ha-icon icon="mdi:chevron-down"></ha-icon></summary><div class="decision-goal-room-list">${roomRows}</div></details>`:""}</div>`;
    }
    _recommendationRows(rooms) {
        const visibleAction = action => {
            if (["Ventilate","Continue ventilating"].includes(action)) return this._config.show_rec_ventilate !== false;
            if (action === "Close") return this._config.show_rec_close !== false;
            if (["Do not ventilate","Wait"].includes(action)) return this._config.show_rec_wait !== false;
            if (action === "Ventilate for cooling") return this._config.show_rec_cooling !== false;
            if (action === "Check sensor") return this._config.show_rec_sensor !== false;
            return true;
        };
        const important = rooms.filter(r => {
            if (!visibleAction(r.action)) return false;
            if (r.calculation_enabled === false || r.data_quality !== "ok")
                return false;
            if (["Ventilate", "Continue ventilating", "Close", "Ventilate for cooling", "Check sensor"].includes(r.action))
                return true;
            if (["Do not ventilate", "Wait"].includes(r.action))
                return (r.recommendation_reasons || []).some(x => /Raumluftfeuchte|Oberflächenfeuchte|Room humidity|Surface humidity|CO₂|Pollen/.test(String(x)));
            return false;
        });
        if (!important.length)
            return `<div class="recommendation-empty"><ha-icon icon="mdi:check-circle-outline"></ha-icon><div><b>Keine raumspezifische Maßnahme nötig</b><span>FreshAirIQ überwacht die Räume weiter. Die Hausschwelle entscheidet separat über eine allgemeine Lüftungsempfehlung.</span></div></div>`;
        return important.map(r => { const [accent, , icon] = styleFor(r.action); const reasons = (r.recommendation_reasons || []).filter(Boolean); return `<article class="recommendation-row clickable" data-room="${esc(r.key)}" style="--rec:${accent}"><div class="rec-icon"><ha-icon icon="${icon}"></ha-icon></div><div class="rec-body"><div class="rec-head"><b>${esc(r.name)}</b><strong>${esc(actionDE(r.action))}</strong></div><div class="rec-reasons">${reasons.map(x => `<span>${esc(x)}</span>`).join("") || `<span>${esc(reasonDE(r.reason))}</span>`}</div></div></article>`; }).join("");
    }
    _goalTracker(r, compact=false) {
        const goals=((r.goal_state||{}).goals||[]).filter(g=>g.active);if(!goals.length)return "";const de=this._uiLanguage()!=="en",names={humidity:de?"Feuchte":"Humidity",co2:"CO₂",temperature:de?"Temperatur":"Temperature"},icons={humidity:"mdi:water-outline",co2:"mdi:molecule-co2",temperature:"mdi:thermometer"};const horizon=Math.max(1,Number(r.forecast_horizon_min||5)),effect=Number(r.forecast_physical_moisture_effect_ml??r.forecast_moisture_effect_ml??0),tempEffect=Number(r.forecast_temperature_change_c??r.forecast_5_min_temperature_change_c??0);
        const impact=g=>{if(g.id==="humidity"){const potential=Number(r.realistic_potential_ml??r.potential_ml??0);if(potential>.5&&effect>.5){const rate=effect/horizon,mins=rate>.01?Math.max(1,Math.ceil(potential/rate)):horizon;return{text:`−${Math.round(potential)} ml`,cls:"removed",time:`${mins} min`,note:de?"entfernbar":"removable"}}if(effect<-.5)return{text:`+${Math.abs(Math.round(effect))} ml`,cls:"added",time:`${Math.round(horizon)} min`,note:de?"würde hinzukommen":"would be added"};return{text:"±0 ml",cls:"neutral",time:`${Math.round(horizon)} min`,note:de?"kein relevanter Effekt":"no relevant effect"}}if(g.id==="temperature"){const sign=tempEffect>0?"+":tempEffect<0?"−":"±";return{text:`${sign}${fmt(Math.abs(tempEffect),1)} °C`,cls:tempEffect>0?"warmer":tempEffect<0?"cooler":"neutral",time:`${Math.round(horizon)} min`,note:de?(tempEffect>0?"wärmer":tempEffect<0?"kühler":"nahezu unverändert"):(tempEffect>0?"warmer":tempEffect<0?"cooler":"nearly unchanged")}}if(g.id==="co2"){const value=Number(g.value),target=Number(g.target),delta=Number.isFinite(value)&&Number.isFinite(target)?value-target:NaN;if(delta>0)return{text:`−${Math.round(delta)} ppm`,cls:"lower",time:g.eta_min!=null&&Number(g.eta_min)>0?`${Math.max(1,Math.round(Number(g.eta_min)))} min`:"–",note:de?(g.eta_min!=null?"bis Ziel":"bis Ziel · Zeit lernt"):(g.eta_min!=null?"to target":"to target · time learning")};return{text:"±0 ppm",cls:"neutral",time:"–",note:de?"Ziel bereits erreicht":"target already reached"}}return{text:"–",cls:"neutral",time:"–",note:""}};return `<div class="goal-tracker ${compact?"compact":""}">${goals.map(g=>{const x=impact(g);return `<div class="goal-pill ${g.reached?"reached":"open"}"><ha-icon icon="${icons[g.id]||"mdi:target"}"></ha-icon><span><b>${names[g.id]||g.id}</b>${compact?"":`<small class="goal-impact ${x.cls}">${x.text}<span class="goal-impact-time"><i class="goal-sep">· </i>${x.time}</span></small><small class="goal-impact-note">${x.note}</small>`}</span></div>`}).join("")}</div>`;
    }
    _roomCard(r) {
        try {
            return this._roomCardImpl(r);
        } catch (error) {
            try { console.error("FreshAirIQ room tile failed", r && r.key, error); } catch (_) { /* ignore */ }
            const name = esc((r && (r.name || r.key)) || "?");
            return `<article class="room clickable room-render-error" data-room="${esc(r && r.key)}"><div class="room-head"><div class="room-ident"><div class="room-title">${name}</div><div class="muted">Anzeige dieses Raums fehlgeschlagen · FAIQ-UI-ROOM-001</div></div><ha-icon class="room-chevron" icon="mdi:chevron-right"></ha-icon></div></article>`;
        }
    }
    _roomCardImpl(r) {
        const [icon, accent, iconBg] = roomVisual(r);
        const [mouldColor, mouldBg] = mouldStyle(r.mould_level);
        const waterMl = Math.max(0, Number(r.water_in_air_ml || 0));
        const contactDirs = Object.values(r.contact_orientations || {}).map(orientationDE).filter(x => x !== "–");
        const dirText = contactDirs.length ? [...new Set(contactDirs)].join(" / ") : orientationDE(r.window_orientation);
        const samples = Number(r.learning_samples || 0);
        const structureOnly = r.calculation_enabled === false;
        const summary = structureOnly
            ? `<div class="room-summary-grid"><div class="room-stat" style="grid-column:1/-1"><ha-icon class="stat-icon" icon="mdi:home-floor-0"></ha-icon><div><div class="tiny">STRUKTURRAUM</div><div class="room-value">Keine Klimasensoren erforderlich</div><div class="muted">Wird für Gebäude, Etage, Volumen und Bewohnerzuordnung geführt – ohne erfundene Klimawerte.</div></div></div></div>`
            : `<div class="room-summary-grid"><div class="room-stat"><ha-icon class="stat-icon" icon="mdi:thermometer"></ha-icon><div><div class="tiny">RAUMKLIMA</div><div class="room-value">${fmt(r.temperature, 1)} °C · ${Math.round(Number(r.humidity || 0))} %</div><div class="muted">${fmt(r.absolute_humidity, 1)} g/m³ absolut</div></div></div><div class="room-stat mould-mini" style="border-color:${mouldColor}55;background:${mouldBg}"><ha-icon class="stat-icon" icon="mdi:shield-outline" style="color:${mouldColor}"></ha-icon><div><div class="tiny">SCHIMMEL</div><div class="room-value" style="color:${mouldColor}">${Math.round(Number(r.surface_rh || 0))} %</div><div class="muted" style="color:${mouldColor}">${esc(mouldDE(r.mould_level))}</div></div></div><div class="room-stat"><ha-icon class="stat-icon learning-bars" icon="mdi:chart-bar"></ha-icon><div><div class="tiny">LERNSTATUS</div><div class="room-value">${esc(learnDE(r.learning_status))}</div><div class="muted">${samples} ${samples === 1 ? "Probe" : "Proben"} · ${fmt(Number(r.learned_exchange_rate_per_min || 0) * 100, 1)} %/min</div></div></div></div>`;
        const statusColor = structureOnly ? "#9aa7b3" : (r.action === "Okay" ? "#67df92" : styleFor(r.action)[0]);
        const statusChip = structureOnly ? "" : `<span class="room-status">${esc(actionDE(r.action))}</span>`;
        return `<article class="room clickable" role="button" tabindex="0" data-room="${esc(r.key)}" style="--accent:${accent};--icon-bg:${iconBg};--status:${statusColor}"><div class="room-head"><div class="room-icon"><ha-icon icon="${icon}"></ha-icon></div><div class="room-ident"><div class="room-title">${esc(r.name || r.key)}</div><div class="muted">${esc(floorDE(r.floor))} · ${fmt(r.volume_m3, 1)} m³ · Fenster ${esc(dirText)}${structureOnly ? " · nur Struktur" : ""}</div>${statusChip}</div>${structureOnly ? "" : `<div class="room-water"><ha-icon icon="mdi:water"></ha-icon><strong>${Math.round(waterMl)} ml</strong></div>`}<ha-icon class="room-chevron" icon="mdi:chevron-right"></ha-icon></div>${summary}</article>`;
    }
    _infoBackButton() {
        return `<button class="info-back" id="info-back" aria-label="Zurück"><ha-icon icon="mdi:arrow-left"></ha-icon></button>`;
    }
    _infoNav() {
        const label = this._info && this._info.startsWith("settings") ? "FreshAirIQ Einstellungen" : "FreshAirIQ";
        return `<div class="info-nav" role="toolbar" aria-label="Fensternavigation">${this._infoBackButton()}<div class="info-nav-label">${esc(label)}</div><button class="info-close" id="info-close" aria-label="Schließen">×</button></div>`;
    }
    _errorPayload(err, fallbackCode = "FAIQ-UI-UNKNOWN-001") {
        const body = err?.body || err?.message || "";
        let parsed = null;
        try { parsed = typeof body === "string" ? JSON.parse(body) : body; } catch (_) { parsed = null; }
        return {
            code: parsed?.error_code || err?.error_code || fallbackCode,
            message: parsed?.error || parsed?.message || (typeof body === "string" && !body.trim().startsWith("{") ? body : "FreshAirIQ konnte die Aktion nicht abschließen."),
            detail: parsed?.detail || parsed?.error_type || "",
        };
    }
    _rememberSupportError(err, fallbackCode) {
        const info = this._errorPayload(err, fallbackCode);
        this._lastSupportError = {...info, at:new Date().toISOString()};
        return info;
    }
    _supportErrorText(info) {
        return `${info.message}\n\nFehlercode: ${info.code}${info.detail ? `\nTechnik: ${info.detail}` : ""}`;
    }

    async _sendDiagnosticsToDeveloper() {
        const button = this.shadowRoot?.getElementById("diagnostics-send");
        const original = button?.innerHTML;
        const knownUntil = this._supportCooldownUntil ? new Date(this._supportCooldownUntil) : null;
        if (knownUntil && knownUntil.getTime() > Date.now()) {
            const mins = Math.max(1, Math.ceil((knownUntil.getTime() - Date.now()) / 60000));
            if (button) button.innerHTML = `<ha-icon icon="mdi:timer-sand"></ha-icon><b>${esc(this._t("support.cooldown_button", { mins }))}</b><span>${esc(this._t("support.cooldown_hint"))}</span>`;
            setTimeout(() => { if (button && original) button.innerHTML = original; }, 2500);
            return;
        }
        const message = String(this.shadowRoot?.getElementById("diagnostics-message")?.value || "").trim();
        if (message.length > 4000) { window.alert(this._t("support.message_too_long")); return; }
        try {
            if (button) { button.disabled = true; button.innerHTML = `<ha-icon icon="mdi:progress-clock"></ha-icon><b>${esc(this._t("support.sending"))}</b><span>${esc(this._t("support.please_wait"))}</span>`; }
            await this._registerFieldTestClient(true);
            const result = await this._hass.callApi("POST", "freshairiq/support-diagnostics", { message });
            if (result?.accepted) {
                this._supportCooldownUntil = result.cooldown_until;
                const caseId = result.support_case_id || "";
                if (button) button.innerHTML = `<ha-icon icon="mdi:check-circle-outline"></ha-icon><b>${esc(this._t("support.sent"))}</b><span>${caseId ? `Support-ID ${esc(caseId)}` : esc(this._t("support.cooldown_active"))}</span>`;
                window.alert(this._t("support.success", { caseLine: caseId ? `\nSupport-ID: ${caseId}` : "" }));
            }
        } catch (err) {
            const body = err?.body || err?.message || "";
            let parsed = null;
            try { parsed = typeof body === "string" ? JSON.parse(body) : body; } catch (_) { parsed = null; }
            if (parsed?.reason === "cooldown" || err?.status_code === 429) {
                const seconds = Number(parsed?.retry_after_seconds || 3600);
                const mins = Math.max(1, Math.ceil(seconds / 60));
                if (parsed?.cooldown_until) this._supportCooldownUntil = parsed.cooldown_until;
                if (button) button.innerHTML = `<ha-icon icon="mdi:timer-sand"></ha-icon><b>${esc(this._t("support.cooldown_button", { mins }))}</b><span>${esc(this._t("support.cooldown_hint"))}</span>`;
            } else {
                console.error("FreshAirIQ support diagnostics upload failed", err);
                const info = this._rememberSupportError(err, "FAIQ-SUPPORT-UPLOAD-001");
                if (button) button.innerHTML = `<ha-icon icon="mdi:alert-circle-outline"></ha-icon><b>${esc(this._t("support.failed"))}</b><span>${esc(info.code)}</span>`;
                window.alert(`${this._t("support.failure_alert")}\n\nFehlercode: ${info.code}${info.detail ? `\nTechnik: ${info.detail}` : ""}`);
            }
        } finally {
            setTimeout(() => { if (button && original) { button.disabled = false; button.innerHTML = original; } }, 3500);
        }
    }
    _settingsEntryId() {
        const s = this._statusEntity();
        return s && s.attributes ? s.attributes.freshairiq_entry_id : null;
    }
    _consentSnoozed() {
        // "Später" hides the hint for seven days in this browser.
        try { const at = Number(window.localStorage.getItem("freshairiq-consent-later") || 0); return at > 0 && Date.now() - at < 7 * 86400000; } catch (_) { return false; }
    }
    _orderedRooms(rawRooms) {
        const source = Array.isArray(rawRooms) ? rawRooms : Object.values(rawRooms || {});
        return source.filter(r => r && typeof r === "object").map((room, index) => ({ room, index })).sort((a, b) => {
            const av = Number(a.room.sort_order);
            const bv = Number(b.room.sort_order);
            const ao = Number.isFinite(av) ? av : 9999;
            const bo = Number.isFinite(bv) ? bv : 9999;
            return ao - bo || a.index - b.index || String(a.room.name || a.room.key || "").localeCompare(String(b.room.name || b.room.key || ""), "de");
        }).map(x => x.room);
    }
    _groupRoomsByFloor(rawRooms, renderRoom) {
        const ordered = this._orderedRooms(rawRooms);
        const groups = [];
        const byFloor = new Map();
        ordered.forEach(room => {
            const key = String(room.floor || "");
            if (!byFloor.has(key)) { const group = { key, rooms: [] }; byFloor.set(key, group); groups.push(group); }
            byFloor.get(key).rooms.push(room);
        });
        return groups.map(group => `<section class="floor-room-group"><div class="floor-room-heading"><ha-icon icon="mdi:layers-outline"></ha-icon><span>${esc(floorDE(group.key))}</span></div><div class="floor-room-content">${group.rooms.map(renderRoom).join("")}</div></section>`).join("");
    }
    _infoPanel(st, rooms) {
        var _a, _b, _c;
        if (!this._info)
            return "";
        if (this._info === "support") {
            const mode = String(((st && st.diagnostics_upload) || {}).configured_reporting_mode || "daily");
            const modeLabel = {off:"Aus",errors:"Nur bei erkannten Problemen",daily:"Täglich nachts",weekly:"Wöchentlich"}[mode] || mode;
            return `<section class="info-panel settings-panel"><div class="tiny info-kicker">FRESHAIRIQ SUPPORT</div><h3>Hilfe, Diagnose & Feedback</h3><p>Alle Support-Funktionen sind hier zentral gebündelt.</p><section class="settings-group"><div class="settings-group-head"><div><div class="tiny">DIAGNOSE</div><span>Diagnosedaten lokal exportieren oder direkt an den FreshAirIQ-Support senden.</span></div></div><div class="settings-field settings-field-stack"><div class="settings-field-copy"><b>Nachricht an den Support (optional)</b><span>Die Diagnose wird verschlüsselt über Home Assistant direkt an den FreshAirIQ-Diagnose-Server übertragen – nicht an die hier angezeigte lokale Home-Assistant-Adresse. Zugangsdaten und Tokens werden nicht übertragen.</span></div><textarea id="diagnostics-message" class="settings-input settings-textarea" rows="4" maxlength="4000" placeholder="Optional: Was ist passiert?"></textarea></div><div class="settings-room-actions"><button class="settings-save" id="diagnostics-export"><ha-icon icon="mdi:download"></ha-icon><b>Diagnosedaten</b><span>exportieren</span></button><button class="settings-save" id="diagnostics-send"><ha-icon icon="mdi:shield-lock-outline"></ha-icon><b>Diagnosedaten</b><span>an Support senden</span></button></div></section><section class="settings-group"><div class="settings-group-head"><div><div class="tiny">FEEDBACK</div><span>Fehler und Verbesserungsvorschläge direkt melden.</span></div></div><div class="settings-field settings-field-stack"><div class="settings-field-copy"><b>Art der Meldung</b></div><select id="feedback-type" class="settings-input"><option value="bug">Fehler / Bug</option><option value="improvement">Verbesserungsvorschlag</option><option value="other">Sonstiges</option></select></div><div class="settings-field settings-field-stack"><div class="settings-field-copy"><b>Beschreibung</b><span>Bitte keine Passwörter, Tokens oder persönlichen Geheimnisse eintragen.</span></div><textarea id="feedback-message" class="settings-input settings-textarea" rows="6" maxlength="10000"></textarea></div><div class="settings-room-actions"><button class="settings-save" id="feedback-send"><ha-icon icon="mdi:send-outline"></ha-icon> Meldung senden</button></div><div id="feedback-result" class="muted"></div></section><section class="settings-group support-contact"><div class="settings-field-copy"><b>Support per E-Mail</b><span class="support-email">support@freshairiq.com</span></div><div class="settings-field"><div class="settings-field-copy"><b>Automatische Diagnoseübertragung</b><span>Aktuell: ${esc(modeLabel)}. Ändern unter Geräte & Dienste → FreshAirIQ → Konfigurieren → Daten & Lernen → Diagnose-Freigabe.</span></div></div></section></section>`;
        }
        const r = this._info.startsWith("room:") ? rooms.find(x => x.key === this._info.slice(5)) : null;
        if (r) {
            const optionalSensorRows = [];
            if (this._config.info_voc !== false && r.voc_enabled !== false && r.voc_configured)
                optionalSensorRows.push(`<div><b><ha-icon icon="mdi:molecule"></ha-icon> ${r.voc_available ? fmt(r.voc, 0) : "–"}</b><span>VOC / TVOC · ${r.voc_available ? "Zusatzdaten aktiv" : "Sensor aktuell nicht verfügbar"}</span></div>`);
            if (this._config.info_pm25 !== false && r.pm25_enabled !== false && r.pm25_configured)
                optionalSensorRows.push(`<div><b><ha-icon icon="mdi:blur"></ha-icon> ${r.pm25_available ? `${fmt(r.pm25, 1)} µg/m³` : "–"}</b><span>PM2.5 · ${r.pm25_available ? "Zusatzdaten aktiv" : "Sensor aktuell nicht verfügbar"}</span></div>`);
            if (this._config.info_illuminance !== false && r.illuminance_enabled !== false && r.illuminance_configured)
                optionalSensorRows.push(`<div><b><ha-icon icon="mdi:white-balance-sunny"></ha-icon> ${r.illuminance_available ? `${fmt(r.illuminance, 0)} lx` : "–"}</b><span>Helligkeit · ${r.illuminance_available ? "Zusatzdaten aktiv" : "Sensor aktuell nicht verfügbar"}</span></div>`);
            const optionalSensorHtml = optionalSensorRows.length ? `<div class="room-optional-sensors"><div class="tiny">OPTIONALE ZUSATZSENSOREN · KEIN EINFLUSS AUF DIE LÜFTUNGSPHYSIK</div><div class="info-grid">${optionalSensorRows.join("")}</div></div>` : "";
            if (r.calculation_enabled === false) {
                const hasSensors = r.sensor_data_configured === true;
                const hasLiveData = r.sensor_data_available === true && Number.isFinite(Number(r.temperature)) && Number.isFinite(Number(r.humidity));
                const monitorState = hasLiveData ? "Sensorwerte verfügbar" : (hasSensors ? "Sensoren aktuell nicht verfügbar" : "Keine Klimasensoren konfiguriert");
                const monitorClass = hasLiveData ? "ok" : "warn";
                const monitorText = hasLiveData
                    ? "FreshAirIQ zeigt die echten Sensorwerte dieses Raums an. Der Raum ist bewusst von Empfehlungen, Prognosen, Hausbilanz und Lernen ausgeschlossen."
                    : hasSensors
                        ? "Der Raum ist auf „Nur anzeigen“ gestellt, aber mindestens ein zugeordneter Klimasensor liefert aktuell keinen gültigen Wert."
                        : "Dieser Strukturraum bleibt im Gebäudemodell erhalten. Es werden keine Klimawerte geschätzt oder erfunden.";
                const valueBlock = hasLiveData
                    ? `<div class="info-grid monitor-only-grid"><div><b>${fmt(r.temperature, 1)} °C / ${Math.round(Number(r.humidity))} %</b><span>${fmt(r.absolute_humidity, 2)} g/m³ absolut · ${Math.round(Number(r.water_in_air_ml || 0))} ml Wasserdampf</span></div><div><b>${esc(whenDE(r.last_measurement_at))}</b><span>Letzte echte Sensormessung</span></div></div>`
                    : `<div class="monitor-only-empty"><ha-icon icon="mdi:information-outline"></ha-icon><div><b>${esc(monitorState)}</b><span>${hasSensors ? "Bitte Verfügbarkeit und Zuordnung der Temperatur-/Feuchtesensoren prüfen." : "Bei Bedarf können unter Räume & Sensoren Temperatur- und Feuchtesensoren hinterlegt werden."}</span></div></div>`;
                const contactCount = Number(r.contact_count || 0);
                return `<section class="info-panel room-detail monitor-only-detail"><div class="tiny room-detail-label">RAUM-MONITORING</div><h3>${esc(r.name)}</h3><div class="room-iq-hero monitor-only-hero" style="--room-iq:#82929e"><div class="room-iq-icon"><ha-icon icon="mdi:eye-outline"></ha-icon></div><div><div class="tiny">FRESHAIRIQ MODUS</div><strong>Nur anzeigen</strong><span>${esc(monitorText)}</span></div><div class="room-iq-quality ${monitorClass}">${esc(monitorState)}</div></div>${valueBlock}${optionalSensorHtml}<div class="room-iq-context"><div class="tiny">RAUMMODELL</div><span>${esc(floorDE(r.floor))} · ${fmt(r.volume_m3, 1)} m³ · ${contactCount} Fenster-/Türkontakt${contactCount === 1 ? "" : "e"}</span></div></section>`;
            }
            const bal = moisture(r.result_ml), pot = moisture((_a = r.realistic_potential_ml) !== null && _a !== void 0 ? _a : r.potential_ml), eff = moisture((_b = r.forecast_moisture_effect_ml) !== null && _b !== void 0 ? _b : r.moisture_effect_next_5_min_ml);
            const dirs = Object.entries(r.contact_orientations || {}).map(([k, v]) => `${k}: ${orientationDE(v)}`).join(" · ") || "keine Richtung hinterlegt";
            const days = Number(st.statistics_days || 14), hist = r.history_14d || [], sum = hist.reduce((a, x) => ({ removed: a.removed + Number(x.removed_ml || 0), sessions: a.sessions + Number(x.sessions || 0), mins: a.mins + Number(x.ventilation_minutes || 0), cost: a.cost + Number(x.cost || 0) }), { removed: 0, sessions: 0, mins: 0, cost: 0 });
            const monitoredRoomKeys = new Set((st.intelligent_recommendation?.room_keys || []).map(String));
            const passiveOpenRoom = String(st.intelligent_recommendation?.status || st.status || "") === "passive_open_monitor" && r.active && monitoredRoomKeys.has(String(r.key));
            const actionStyle = passiveOpenRoom ? ["#63d2f7", "rgba(99,210,247,.08)", "mdi:window-open"] : styleFor(r.action), roomReasons = (r.recommendation_reasons || []).filter(Boolean);
            const qualityOk = r.data_quality === "ok" && r.last_measurement_valid !== false;
            const roomLead = passiveOpenRoom
                ? `FreshAirIQ behandelt die lange, stabile Öffnung als wahrscheinliche Dauer- oder Kipplüftung und überwacht sie weiter.`
                : r.active ? `FreshAirIQ begleitet die laufende Lüftung in diesem Raum.` : `FreshAirIQ bewertet diesen Raum fortlaufend aus Klima, Außenluft, Lernmodell und Gebäudeeigenschaften.`;
            const roomAction = passiveOpenRoom ? "Daueröffnung überwachen" : actionDE(r.action);
            return `<section class="info-panel room-detail"><div class="tiny room-detail-label">RAUM-INTELLIGENZ · ${days} TAGE</div><h3>${esc(r.name)}</h3><div class="room-iq-hero" style="--room-iq:${actionStyle[0]}"><div class="room-iq-icon"><ha-icon icon="${actionStyle[2]}"></ha-icon></div><div><div class="tiny">FRESHAIRIQ EMPFIEHLT</div><strong>${esc(roomAction)}</strong><span>${esc(roomLead)}</span></div><div class="room-iq-quality ${qualityOk ? "ok" : "warn"}">${qualityOk ? "Daten plausibel" : "Daten prüfen"}</div></div>${roomReasons.length ? `<div class="room-iq-why"><div class="tiny">WARUM?</div>${roomReasons.slice(0,4).map(x => `<div><ha-icon icon="mdi:check-circle-outline"></ha-icon><span>${esc(x)}</span></div>`).join("")}</div>` : ""}<div class="info-grid"><div><b>${fmt(r.temperature, 1)} °C / ${Math.round(Number(r.humidity || 0))} %</b><span>${fmt(r.absolute_humidity, 2)} g/m³ absolut · ${Math.round(Number(r.water_in_air_ml || 0))} ml Wasserdampf</span></div><div><b>${esc(whenDE(r.last_measurement_at))}</b><span>Letzte Messung · ${r.last_measurement_valid === false ? "Messwerte unplausibel" : "Messwerte plausibel"}</span></div><div><b style="color:${r.active ? bal.color : pot.color}">${r.active ? bal.text : pot.text}</b><span>${r.active ? "Bilanz seit Sessionstart" : "aktuell entfernbares Potenzial"}</span></div><div><b>${eff.text}</b><span>weitere ${Number(r.forecast_horizon_min || st.forecast_horizon_min || 5)} min · ${signed((_c = r.forecast_temperature_change_c) !== null && _c !== void 0 ? _c : r.temp_next_5_min_c, "°C")} · ${fmt(r.forecast_cost || 0, 2)} €</span></div><div><b>${Math.round(Number(r.surface_rh || 0))} %</b><span>Oberflächen-RH · ${esc(mouldDE(r.mould_level))}</span></div><div><b style="color:${moisture(sum.removed).color}">${sum.removed > 0 ? "−" : sum.removed < 0 ? "+" : "±"}${fmt(Math.abs(sum.removed) / 1000, 2)} l</b><span>Bilanz in ${days} Tagen</span></div><div><b>${sum.sessions}</b><span>Lüftungen · ${fmt(sum.mins, 0)} min</span></div><div><b>${fmt(sum.cost, 2)} €</b><span>geschätztes Wiederaufheizen</span></div><div><b>${Number(r.learning_samples || 0)} Proben</b><span>${esc(learnDE(r.learning_status))} · ${fmt(Number(r.learned_exchange_rate_per_min || 0) * 100, 1)} %/min</span></div>${Number(r.outcome_feedback_samples || 0) > 0 ? `<div><b>${Number(r.outcome_feedback_samples || 0)} Feedback-Proben</b><span>Prognose ↔ Realität · Treffer ${fmt(r.outcome_success_rate || 0, 0)} % · Feuchtefaktor ${fmt(r.outcome_removed_factor || 1, 2)}</span></div>` : ""}${Number(r.outcome_feedback_samples || 0) > 0 ? `<div><b>Learning 3.0 · ${r.shadow_rollback_active ? "Rollback-Schutz" : "Shadow-Modelle"}</b><span>${esc(r.shadow_learning_status || "Vergleicht Produktionsmodell mit Alternativen")} · Übernahmen ${Number(r.shadow_learning_promotions || 0)} · Rollbacks ${Number(r.shadow_learning_rollbacks || 0)}</span></div>` : ""}${Number(r.routine_source_samples || 0) > 0 ? `<div><b>Routine-IQ ${fmt(r.routine_maturity || 0, 0)} %</b><span>${Number(r.routine_source_samples || 0)} Zeitmuster-Proben${r.routine_expected_source_ml_min != null ? ` · aktuell erwartet ${signed(Number(r.routine_expected_source_ml_min || 0) * 60, " ml/h")}` : ""}</span></div>` : ""}${Number(r.strategy_samples || 0) > 0 ? `<div><b>Strategie-IQ ${fmt(r.strategy_maturity || 0, 0)} %</b><span>${Number(r.strategy_samples || 0)} Empfehlungen ausgewertet · ${Number(r.strategy_outcome_samples || 0)} Ergebnisproben</span></div>` : ""}</div>${optionalSensorHtml}<div class="last-learning" style="--learn:${r.last_learning_valid === false ? "#c97878" : r.last_learning_valid === true ? "#6fbd88" : "#82929e"}"><ha-icon icon="${r.last_learning_valid === false ? "mdi:alert-circle-outline" : r.last_learning_valid === true ? "mdi:check-circle-outline" : "mdi:brain"}"></ha-icon><div><div class="tiny">LETZTE LERNMESSUNG · ${esc(whenDE(r.last_learning_at))}</div><b>${esc(diagnosisDE(r.learning_diagnosis))}</b></div></div><div class="history-grid"><div class="history"><div class="tiny">RAUMLUFTFEUCHTE · ${Math.min(days, 30)} TAGE · %</div><div class="chart">${this._svgLine(r.humidity_history_14d || [], "humidity_percent")}</div></div><div class="history"><div class="tiny">TEMPERATUR · ${Math.min(days, 30)} TAGE · °C</div><div class="chart">${this._svgLine(r.temperature_history_14d || [])}</div></div></div>${r.moisture_source_active ? `<div class="last-learning" style="--learn:#e6be62"><ha-icon icon="mdi:water-plus-outline"></ha-icon><div><div class="tiny">AKTIVE FEUCHTEQUELLE · ${Math.round(Number(r.moisture_source_confidence || 0))} % SICHERHEIT</div><b>${esc(r.moisture_source_message || `${r.moisture_source_label || "Feuchtequelle"} erkannt.`)} · ca. +${Math.round(Number(r.moisture_source_rate_ml_min || 0) * 60)} ml/h</b></div></div>` : ""}<div class="room-iq-context"><div class="tiny">RAUMMODELL</div><span>Fenster/Türen: ${esc(dirs)} · Luftstromfaktor ${fmt(r.airflow_factor, 2)} · ${esc(floorDE(r.floor))} · ${fmt(r.volume_m3, 1)} m³</span></div></section>`;
        }
        if (this._info === "moisture" && rooms.some(x => x.active)) {
            const activeRooms = rooms.filter(r => r.active);
            const houseMode = Boolean(st.house_ventilation_mode);
            const houseBalance = moisture(Number(st.live_balance_ml || 0));
            const rows = this._groupRoomsByFloor(rooms, r => {
                const passive = !r.active && Boolean(r.passive_ventilation_active);
                const value = r.active ? Number(r.result_ml || 0) : (passive ? Number(r.passive_ventilation_estimated_ml || 0) : 0);
                const m = moisture(value);
                const mechanicalActive = r.active && Boolean(r.configured_actuators?.mechanical_exhaust_active);
                const state = mechanicalActive ? "MECHANISCHE LÜFTUNG AKTIV" : (r.active ? "LÜFTUNG AKTIV" : (passive ? "PASSIV MITGELÜFTET" : "GESCHLOSSEN"));
                const icon = mechanicalActive ? "mdi:fan" : (r.active ? "mdi:window-open-variant" : (passive ? "mdi:swap-horizontal" : "mdi:window-closed-variant"));
                const cls = r.active ? "vent-active" : (passive ? "vent-passive" : "vent-inactive");
                const displayValue = passive ? `≈ ${m.text}` : m.text;
                const confidence = passive ? ` · Schätzung ${Math.round(Number(r.passive_ventilation_confidence || 0))} %` : "";
                return `<div class="breakdown-row clickable ${cls}" data-room="${esc(r.key)}"><b><ha-icon icon="${icon}"></ha-icon>${esc(r.name)}</b><span>${state}${confidence}</span><strong style="color:${m.color}">${displayValue}</strong></div>`;
            });
            const houseHero = houseMode ? `<div class="house-live"><div><div class="tiny">HAUSLÜFTUNG AKTIV</div><b>${activeRooms.length} von ${rooms.filter(r=>r.calculation_enabled!==false).length} Räumen werden gelüftet</b></div><strong style="color:${houseBalance.color}">${houseBalance.text}</strong><span>Live-Bilanz für das ganze Haus</span></div>` : "";
            return `<section class="info-panel"><div class="tiny info-kicker">${houseMode ? "LIVE-FEUCHTEBILANZ · GANZES HAUS" : "LIVE-FEUCHTEBILANZ NACH RÄUMEN"}</div><h3>${houseMode ? "Hausweite Lüftung läuft" : "Wo Feuchtigkeit entweicht oder hinzukommt"}</h3><p>${houseMode ? "Bei einer großen Hauslüftung bewertet FreshAirIQ primär die gemeinsame Hauswirkung. Passiv mitgelüftete Räume werden aus ihrem eigenen Sensorverlauf erkannt und mit ≈ als Schätzung markiert; sie werden nicht doppelt zur Hausbilanz addiert." : "Aktive Lüftungen sind deutlich hervorgehoben. Passiv mitgelüftete Räume werden aus ihrem Sensorverlauf erkannt und als Schätzung markiert. Minus = entfernt, Plus = hinzugekommen."}</p>${houseHero}<div class="breakdown">${rows}</div></section>`;
        }
        if (this._info === "moisture") {
            const calc = this._orderedRooms(rooms.filter(r => r.calculation_enabled !== false && r.data_quality === "ok"));
            const rows = this._groupRoomsByFloor(calc, r => {
                var _a, _b, _c, _d;
                const potential = Number((_b = (_a = r.realistic_potential_ml) !== null && _a !== void 0 ? _a : r.potential_ml) !== null && _b !== void 0 ? _b : 0);
                const shortEffect = Number((_d = (_c = r.forecast_moisture_effect_ml) !== null && _c !== void 0 ? _c : r.moisture_effect_next_5_min_ml) !== null && _d !== void 0 ? _d : 0);
                const value = potential > .5 ? potential : (shortEffect < -.5 ? shortEffect : 0);
                const m = moisture(value);
                const label = potential > .5 ? "aktuell entfernbar" : shortEffect < -.5 ? "würde Feuchtigkeit eintragen" : "kein relevantes Potenzial";
                return `<div class="breakdown-row clickable" data-room="${esc(r.key)}"><b>${esc(r.name)}</b><span>${label}</span><strong style="color:${m.color}">${m.text}</strong></div>`;
            });
            return `<section class="info-panel"><div class="tiny info-kicker">FEUCHTEPOTENZIAL NACH RÄUMEN</div><h3>Welche Räume den Wert verursachen</h3><p>Ohne laufende Lüftung zeigt FreshAirIQ hier raumweise, wo aktuell Feuchtigkeit entfernt werden könnte oder wo Lüften Feuchtigkeit eintragen würde. Minus = entfernbar, Plus = möglicher Eintrag.</p><div class="breakdown">${rows || "<p>Keine gültigen Raumdaten vorhanden.</p>"}</div></section>`;
        }
        if (this._info === "lastvent") {
            const last = st.last_ventilation || null;
            return `<section class="info-panel"><div class="tiny info-kicker">LÜFTUNGSERGEBNIS · DAUERHAFT GESPEICHERT</div><h3>Letzte Lüftung im Detail</h3><p>Hier bleibt die zuletzt vollständig abgeschlossene Hauslüftung erhalten – auch nachdem die 5-Minuten-Ergebnisanzeige auf dem Hauptdashboard beendet ist.</p>${this._ventilationResultCard(last, "panel")}</section>`;
        }
        if (this._info === "mould") {
            const order = { "Very high": 5, "High": 4, "Elevated": 3, "Slightly elevated": 2, "Low": 1, "Unknown": 0 };
            const canonical = this._orderedRooms(rooms);
            const canonicalIndex = new Map(canonical.map((r, i) => [String(r.key || ""), i]));
            const mouldOrdered = [...canonical].sort((a, b) => (order[b.mould_level] || 0) - (order[a.mould_level] || 0) || Number(b.surface_rh || 0) - Number(a.surface_rh || 0) || (canonicalIndex.get(String(a.key || "")) || 0) - (canonicalIndex.get(String(b.key || "")) || 0));
            const rows = mouldOrdered.map(r => { const [c] = mouldStyle(r.mould_level); return `<div class="breakdown-row clickable" data-room="${esc(r.key)}"><b>${esc(r.name)}</b><span>${Math.round(Number(r.surface_rh || 0))} % Oberflächen-RH</span><strong style="color:${c}">${esc(mouldDE(r.mould_level))}</strong></div>`; }).join("");
            return `<section class="info-panel"><div class="tiny info-kicker">SCHIMMEL-IQ · RISIKO NACH RÄUMEN</div><h3>Wo FreshAirIQ genauer hinschaut</h3><p>Die Räume sind nach Risiko sortiert. <b>Wichtig: Das ist nur eine grobe Einschätzung.</b> FreshAirIQ leitet die Oberflächenfeuchte aus dem Raumklima ab. Ohne gemessene Oberflächentemperatur bzw. Taupunkt an der konkreten Bauteiloberfläche lässt sich ein tatsächliches Schimmelrisiko nicht sicher bestimmen. Tippe einen Raum an, um Ursache, Empfehlung und Lernwerte zu sehen.</p><div class="breakdown">${rows}</div></section>`;
        }
        if (this._info === "rooms") {
            const ordered = this._orderedRooms(rooms);
            const cards = this._groupRoomsByFloor(ordered, r => this._roomCard(r));
            const empty = rooms.length ? "" : `<p>Der Statussensor liefert aktuell keine Raumdaten. Bitte Home Assistant nach dem Update einmal neu starten; vorhandene Raumkonfigurationen werden dabei nicht gelöscht.</p>`;
            const calcRooms = rooms.filter(r => r.calculation_enabled !== false);
            const needsAttention = calcRooms.filter(r => r.data_quality !== "ok" || ["Ventilate", "Continue ventilating", "Close", "Check sensor", "Do not ventilate"].includes(r.action) || ["Elevated", "High", "Very high"].includes(r.mould_level)).length;
            const roomsOk = Math.max(0, calcRooms.length - needsAttention);
            const waterTotal = Math.round(calcRooms.filter(r => r.data_quality === "ok").reduce((a, r) => a + Number(r.water_in_air_ml || 0), 0));
            const summary = calcRooms.length ? `<div class="rooms-summary">${needsAttention ? `<span class="rooms-chip attention"><ha-icon icon="mdi:alert-circle-outline"></ha-icon>${needsAttention} ${needsAttention === 1 ? "Raum braucht Aufmerksamkeit" : "Räume brauchen Aufmerksamkeit"}</span>` : ""}<span class="rooms-chip ok"><ha-icon icon="mdi:check-circle-outline"></ha-icon>${roomsOk} in Ordnung</span><span class="rooms-chip water"><ha-icon icon="mdi:water-outline"></ha-icon>${waterTotal} ml in der Luft</span></div>` : "";
            return `<section class="info-panel rooms-overview"><div class="tiny info-kicker">RÄUME</div><h3>Raumübersicht</h3><p class="rooms-subtitle">Aktuelle Raumwerte auf einen Blick</p>${summary}${empty}<div class="rooms">${cards}</div></section>`;
        }
        if (this._info === "guests") {
            const ga = Number(st.guest_adults || 0), gc = Number(st.guest_children || 0);
            return `<section class="info-panel"><div class="tiny info-kicker">ANWESENHEIT & GÄSTEMODUS</div><h3>Wer ist heute Nacht im Haus?</h3><p>FreshAirIQ berücksichtigt aktuell <b>${fmtPeople(st.effective_occupants || 0)} Personen</b>. Davon sind ${Number(st.home_tracked_occupants || 0)} über Home Assistant als zuhause erkannt, ${Number(st.away_tracked_occupants || 0)} als abwesend und ${Number(st.untracked_adults || 0) + Number(st.untracked_children || 0)} ohne eigenes Tracking.</p><p class="muted">Übernachtungsgäste: ${ga} Erwachsene · ${gc} Kinder. Jede Änderung kalkuliert Kurzzeit- und Nachtprognose sofort neu. Anwesenheits-IQ ${Math.round(Number(st.presence_confidence || 0))} %.</p></section>`;
        }
        if (this._info === "water") {
            const calc = rooms.filter(r => r.calculation_enabled !== false && r.data_quality === "ok");
            const total = calc.reduce((a, r) => a + Number(r.water_in_air_ml || 0), 0);
            const rows = this._orderedRooms(calc).map(r => `<div class="breakdown-row clickable" data-room="${esc(r.key)}"><b>${esc(r.name)}</b><span>${fmt(r.absolute_humidity, 1)} g/m³ · ${fmt(r.volume_m3, 1)} m³</span><strong>${Math.round(Number(r.water_in_air_ml || 0))} ml</strong></div>`).join("");
            return `<section class="info-panel"><div class="tiny info-kicker">WASSER IN DER HAUSLUFT</div><h3>${Math.round(total)} ml über ${calc.length} Räume</h3><p>FreshAirIQ berechnet die Wasserdampfmenge je Raum aus absoluter Feuchte × Raumvolumen. So wird aus Prozent Luftfeuchte ein physikalisch vergleichbarer Wert.</p><div class="breakdown">${rows || "<p>Keine gültigen Raumdaten vorhanden.</p>"}</div></section>`;
        }
        if (this._info === "decision") {
            const brain = ((st.intelligent_recommendation || {}).decision_brain || {}), why = (brain.why || (st.intelligent_recommendation || {}).reasons || []).filter(Boolean);
            return `<section class="info-panel"><div class="tiny info-kicker">IQ-ENTSCHEIDUNG</div><h3>${esc(brain.headline || (st.intelligent_recommendation || {}).title || "Aktuelle Entscheidung")}</h3><p>${esc(brain.summary || (st.intelligent_recommendation || {}).summary || "FreshAirIQ kombiniert Raumdaten, Außenluft, Prognosen und Lernwerte.")}</p>${why.length ? `<div class="room-iq-why">${why.slice(0,6).map(x => `<div><ha-icon icon="mdi:check-circle-outline"></ha-icon><span>${esc(x)}</span></div>`).join("")}</div>` : ""}<p class="muted">Die Entscheidung wird aus Gesundheit/Schimmel, Komfort, Feuchtewirkung, Temperatur und Energie priorisiert. Gelernte Gewohnheiten dürfen Sicherheitsentscheidungen nicht überstimmen.</p></section>`;
        }
        if (String(this._info || "").startsWith("learning:")) {
            const learningPanel = this._learningPanel(st);
            if (learningPanel) return learningPanel;
        }
        const map = {
            threshold: ["Intelligente Lüftungsschwelle", `Die Lüftungsschwelle legt fest, ab welchem gesamten Feuchtepotenzial FreshAirIQ eine Hauslüftung als sinnvoll bewertet. Aktuell liegt sie bei ${Math.round(Number(st.ventilation_threshold_ml || 0))} ml.`, `Modus: ${st.ventilation_threshold_mode || "–"}. Die Raumempfehlungen können zusätzlich eigene Gesundheits- oder Schimmelgründe haben. Ändern kannst du die Schwelle unter Einstellungen → Geräte & Dienste → FreshAirIQ → Konfigurieren.`],
            pollen: ["Pollenbewertung", `FreshAirIQ berücksichtigt die konfigurierte Pollenbelastung als möglichen Lüftungs-Veto-Faktor.`, `Aktueller Index ${fmt(st.pollen_index, 1)} · Grenze ${fmt(st.pollen_limit, 1)} · ${st.pollen_blocked ? "Lüftung aktuell eingeschränkt" : "kein Pollen-Veto"}.`],
            moisture: ["Feuchtebilanz / entfernbar", `Während einer Lüftung zeigt der Wert die seit Beginn berechnete Feuchteänderung. Ohne aktive Lüftung zeigt er das aktuell entfernbar geschätzte Potenzial. Die aktuelle Empfehlungsschwelle liegt bei ${Math.round(Number(st.ventilation_threshold_ml || 0))} ml.`, `Schwellenmodus: ${st.ventilation_threshold_mode || "–"} · Minus = Feuchte entfernt, Plus = Feuchte eingetragen.`],
            temperature: ["Temperaturänderung", `Volumengewichtete Temperaturänderung der aktuell gelüfteten Räume seit dem jeweiligen Sessionstart.`, `Nach einem Neustart werden nur plausible, echte Sensorwerte als Startbasis akzeptiert.`],
            time: ["Lüftungszeit", `Empfohlene Dauer aus Außentemperatur, Feuchtedifferenz und den eingestellten Mindest-/Maximalzeiten.`, `Bei aktiver Lüftung wird die verbleibende bzw. überschrittene Zeit live berechnet.`],
            next5: [`Prognose weitere ${Number(st.forecast_horizon_min || 5)} Minuten`, `Rollierende Hybrid-Prognose aus gelerntem Luftwechsel, absoluter Feuchte innen/außen, zukünftiger Wetterentwicklung (falls verfügbar), aktuellem Feuchte- und Temperaturtrend, interner Feuchteproduktion, Wind/Fensterausrichtung und Querlüftung. Heizsystem und Energiepreis beeinflussen nicht die physikalische Feuchteprognose, sondern nur die separate Wärmeverlust- und Kostenschätzung.`, `Bei Horizonten über 5 Minuten simuliert FreshAirIQ den Zustand in 5-Minuten-Schritten und schätzt zusätzlich den effizienten Endpunkt innerhalb des Prognosefensters. Minus = voraussichtlich Feuchte entfernt, Plus = Feuchte kommt hinzu. Modellvertrauen aktuell ${Math.round(Number(st.forecast_confidence || 0))} %.`],
            systemcheck: ["FreshAirIQ Systemcheck", `Aktive Plausibilitäts- und Vollständigkeitsprüfung der konfigurierten Datenquellen.`, `${Number(st.system_check?.valid_rooms || 0)}/${Number(st.system_check?.configured_rooms || 0)} Räume gültig · ${Number(st.system_check?.stale_or_invalid_rooms || 0)} auffällig · Wetter ${st.system_check?.weather_available ? "verfügbar" : "fehlt"} · CO₂ in ${Number(st.system_check?.co2_rooms || 0)} Räumen · ${st.system_check?.overall || "–"}.`],
            night: ["Nachtprognose", `Intelligente Feuchteprognose bis zum relevanten Nachtende (${fmt(st.overnight_hours_remaining || 0, 1)} h).`, `Sie kombiniert aktuell erwartete Bewohner (${fmtPeople(st.effective_occupants || 0)}), Gäste, gelernte Nachtproben, aktuellen Feuchtetrend, absolute Außenfeuchte, offene Fenster, Wind, Fensterausrichtung und gelernten Luftwechsel. Wettereffekt ${Number(st.overnight_weather_effect_ml || 0) >= 0 ? "+" : ""}${Math.round(Number(st.overnight_weather_effect_ml || 0))} ml · Trendkorrektur ${Number(st.overnight_trend_effect_ml || 0) >= 0 ? "+" : ""}${Math.round(Number(st.overnight_trend_effect_ml || 0))} ml · IQ ${Math.round(Number(st.overnight_confidence || 0))} %.`], profile: ["Betriebsmodus", `Aktuell: ${profileDE(st.operating_profile)}`, `Entfeuchten priorisiert Feuchteabbau. Komfort balanciert Feuchte, Temperatur und Energie. Sommer kühlen nutzt kühle Außenluft, solange der Feuchteeintrag vertretbar bleibt.`]
        };
        const x = map[this._info] || ["FreshAirIQ Detail", "Keine weiteren Details verfügbar.", ""];
        return `<section class="info-panel"><div class="tiny info-kicker">ERKLÄRUNG</div><h3>${esc(x[0])}</h3><p>${esc(x[1])}</p><p class="muted">${esc(x[2])}</p></section>`;
    }
    _profileControls(st) { const current = this._profileValue(st); const opts = [["dehumidify", "Entfeuchten", "Feuchteabbau hat Vorrang; FreshAirIQ toleriert dafür etwas mehr Wärmeverlust."], ["comfort", "Komfort", "Ausgewogene Entscheidung aus Feuchte, Temperatur, Luftqualität und Energie."], ["summer_cooling", "Sommer kühlen", "Kühle Außenluft wird gezielt zum Absenken der Raumtemperatur genutzt, solange der Feuchteeintrag vertretbar bleibt."]]; return `<div class="profile-options">${opts.map(([v, n, d]) => `<button class="profile-option ${current === v ? "selected" : ""}" data-profile="${v}"><b>${n}</b><span>${d}</span></button>`).join("")}</div>`; }
    _forecastControls(st) { const h = this._forecastValue(st); const presets = [5, 10, 15, 30, 60]; return `<div class="profile-options"><div class="tiny">PROGNOSEZEITRAUM</div><div style="display:flex;flex-wrap:nowrap;gap:7px">${presets.map(v => `<button class="profile-option ${h === v ? "selected" : ""}" style="width:auto;flex:1 1 0;min-width:0;padding:9px 6px" data-forecast="${v}"><b>${v} min</b></button>`).join("")}</div><div style="display:flex;align-items:center;gap:10px;margin:2px 0"><span style="height:1px;flex:1;background:rgba(255,255,255,.08)"></span><span class="muted" style="font-weight:800">oder</span><span style="height:1px;flex:1;background:rgba(255,255,255,.08)"></span></div><div style="display:flex;gap:8px;align-items:center"><input id="forecast-custom" type="number" min="1" max="120" step="1" value="${h}" style="width:110px;padding:10px;border-radius:10px;border:1px solid rgba(255,255,255,.14);background:rgba(255,255,255,.04);color:inherit"><button class="profile-option" id="forecast-apply" style="width:auto"><b>Übernehmen</b></button></div><span class="muted">Schnellwahl wird sofort übernommen. Für einen beliebigen Wert von 1 bis 120 Minuten Zahl eingeben und „Übernehmen“ wählen.</span></div>`; }
    _guestControls(st) { const ov=this._guestOverride||{}; const row = (kind, label, value) => `<div style="display:grid;grid-template-columns:1fr auto auto auto;gap:8px;align-items:center"><b>${label}</b><button class="profile-option" style="width:46px;text-align:center" data-guest-kind="${kind}" data-guest-delta="-1"><b>−</b></button><strong style="min-width:28px;text-align:center;font-size:20px">${Number(ov[kind] ?? value ?? 0)}</strong><button class="profile-option" style="width:46px;text-align:center" data-guest-kind="${kind}" data-guest-delta="1"><b>+</b></button></div>`; return `<div class="profile-options"><div class="tiny">ÜBERNACHTUNGSGÄSTE</div>${row("adult", "Erwachsene", st.guest_adults)}${row("child", "Kinder", st.guest_children)}<span class="muted">Die Anzeige reagiert sofort; FreshAirIQ berechnet die Nachtprognose anschließend mit der neuen Belegung neu.</span></div>`; }
    _learningComponentsCard(st, rooms) {
        const model = st.learning_components || {};
        const backtest = st.forecast_backtest || {};
        const effectiveness = st.learning_effectiveness || {};
        const cached = this._learningCardCache;
        if (cached && cached.model === model && cached.backtest === backtest && cached.effectiveness === effectiveness) return cached.html;
        const reliability = backtest.reliability || {};
        const components = Array.isArray(model.components) ? model.components : [];
        const byKey = Object.fromEntries(components.map(c => [String(c.key || ""), c]));
        const overall = Math.max(0, Math.min(100, Number(model.overall_maturity_percent || 0)));
        const reliabilityScore = reliability.score_percent == null ? null : Math.max(0, Math.min(100, Number(reliability.score_percent)));
        const stage = model.stage_label || "Grundmodell";
        const stageCopy = model.personal_optimization_ready === true
            ? "Ich kenne inzwischen dein Zuhause und bestätigte Nutzungs- und Komfortmuster. Persönliche Optimierung ist aktiv."
            : overall < 12
                ? "Ich arbeite zunächst mit Gebäudephysik und aktuellen Messwerten. Persönliches Lernen beginnt erst mit belastbaren Beobachtungen."
                : "FreshAirIQ sammelt unabhängige Erfahrungen und bestätigt erkannte Muster Schritt für Schritt an realen Ergebnissen.";
        const pct = v => Math.max(0, Math.min(100, Number(v || 0)));
        const avg = keys => {
            const vals = keys.map(k => byKey[k]).filter(Boolean).map(c => pct(c.maturity_percent));
            return vals.length ? vals.reduce((a,b)=>a+b,0) / vals.length : 0;
        };
        const evidence = key => byKey[key] || {};
        const room = evidence("room_physics"), feedback = evidence("forecast_feedback"), routines = evidence("routines");
        const season = evidence("seasonality"), night = evidence("night_model"), house = evidence("house_strategy");
        const personal = evidence("personal_context"), strategy = evidence("user_strategy"), validation = evidence("forecast_validation");
        const roomDays = (String(room.evidence_text || "").match(/(\d+) unterschiedliche Tage/) || [])[1];
        const routineDays = Number(routines.samples || 0);
        const nightCount = Number(night.samples || 0);
        const seasonDone = Number(season.samples || 0);
        const categories = [
            ["learning:home", "mdi:home-outline", "Dein Zuhause", ["room_physics","post_close","house_strategy"], `${roomDays || 0} unterschiedliche Lerntage · ${Number(room.samples || 0)} Lernlüftungen`],
            ["learning:forecast", "mdi:chart-line", "Prognosen & Lernen", ["live_forecast","forecast_feedback","shadow_learning","forecast_validation"], `${Number(validation.samples || 0)} Realvergleiche · ${Number(effectiveness.independent_sessions || 0)} unabhängige Lüftungen · Lernwirkung ${effectiveness.improvement_percent == null ? "–" : (Number(effectiveness.improvement_percent) >= 0 ? "+" : "") + fmt(effectiveness.improvement_percent, 0) + "%"}`],
            ["learning:habits", "mdi:account-outline", "Deine Gewohnheiten", ["routines","user_strategy","personal_context"], `${routineDays} Tage · ${Number(personal.samples || 0)} Lüftungen`],
            ["learning:longterm", "mdi:leaf", "Langzeitlernen", ["seasonality","night_model"], `${seasonDone}/4 Jahreszeiten · ${nightCount}/120 Nächte`],
        ];
        const categoryHtml = categories.map(([info, icon, label, keys, detail]) => {
            const maturity = avg(keys);
            return `<button class="learning-area clickable" data-info="${info}"><span class="learning-area-icon"><ha-icon icon="${icon}"></ha-icon></span><span class="learning-area-copy"><b>${label}</b><small>${esc(detail)}</small></span><span class="learning-area-score"><b>${Math.round(maturity)} %</b><i><em style="width:${maturity}%"></em></i></span><ha-icon class="learning-area-chevron" icon="mdi:chevron-right"></ha-icon></button>`;
        }).join("");
        const activeLearning = [room, routines, night].filter(c => c && c.label).map(c => c.label).slice(0,3).join(" · ") || "Raumphysik · Prognosemodell";
        const html = `<section class="learning-overview-card"><div class="learning-overview-hero"><div class="intelligence-orbit"><ha-icon icon="mdi:brain"></ha-icon></div><div class="learning-overview-copy"><div class="tiny">FRESHAIRIQ INTELLIGENCE 2.0</div><div class="learning-overview-title"><h2>Lernt dein Zuhause kennen</h2><span>${esc(stage)}</span></div><p>${esc(stageCopy)}</p></div></div><div class="learning-kpis"><div><span><ha-icon icon="mdi:sprout-outline"></ha-icon> Erfahrungsreife</span><b>${Math.round(overall)} %</b><i><em style="width:${overall}%"></em></i></div><div><span><ha-icon icon="mdi:star-outline"></ha-icon> Prognosequalität</span><b>${reliabilityScore == null ? "–" : Math.round(reliabilityScore)+" %"}</b><i><em style="width:${reliabilityScore == null ? 0 : reliabilityScore}%"></em></i></div></div><button class="learning-now clickable" data-info="learning:quality"><ha-icon icon="mdi:lightbulb-outline"></ha-icon><span><b>Aktuell lernt FreshAirIQ</b><small>${esc(activeLearning)}</small></span><ha-icon icon="mdi:chevron-right"></ha-icon></button><div class="learning-area-head"><b>Lernfortschritt nach Bereichen</b><span>Tippe auf einen Bereich, um Details zu sehen.</span></div><div class="learning-area-list">${categoryHtml}</div><div class="learning-overview-note"><ha-icon icon="mdi:information-outline"></ha-icon><span>Reife zeigt unabhängige Erfahrung. Prognosequalität zeigt getrennt davon, wie gut Vorhersagen bisher zur Realität passen.</span></div></section>`;
        this._learningCardCache = { model, backtest, effectiveness, html };
        return html;
    }
    _learningPanel(st) {
        const model = st.learning_components || {};
        const backtest = st.forecast_backtest || {};
        const effectiveness = st.learning_effectiveness || {};
        const reliability = backtest.reliability || {};
        const components = Array.isArray(model.components) ? model.components : [];
        const byKey = Object.fromEntries(components.map(c => [String(c.key || ""), c]));
        const groups = {
            "learning:home": ["Dein Zuhause", "Raumphysik, Feuchtepuffer & Hausstrategie", "mdi:home-outline", ["room_physics","post_close","house_strategy"]],
            "learning:forecast": ["Prognosen & Lernen", "Prognosemodell, Feedback, Shadow-Lernen & Validierung", "mdi:chart-line", ["live_forecast","forecast_feedback","shadow_learning","forecast_validation"]],
            "learning:habits": ["Deine Gewohnheiten", "Tagesroutinen, Nutzerstrategie & persönlicher Kontext", "mdi:account-outline", ["routines","user_strategy","personal_context"]],
        };
        const iconMap = {room_physics:"mdi:home-analytics",post_close:"mdi:water-sync",house_strategy:"mdi:home-lightning-bolt-outline",live_forecast:"mdi:chart-bell-curve-cumulative",forecast_feedback:"mdi:chart-timeline-variant-shimmer",shadow_learning:"mdi:shield-sync-outline",forecast_validation:"mdi:target",routines:"mdi:clock-outline",user_strategy:"mdi:account-check-outline",personal_context:"mdi:account-heart-outline"};
        const componentCard = c => {
            const m = Math.max(0,Math.min(100,Number(c.maturity_percent||0)));
            return `<div class="learning-detail-card"><div class="learning-detail-icon"><ha-icon icon="${iconMap[c.key] || "mdi:brain"}"></ha-icon></div><div><div class="learning-detail-head"><b>${esc(c.label || c.key)}</b><strong>${esc(c.status || "–")}</strong></div><p>${esc(c.description || "")}</p><div class="learning-detail-progress"><i><em style="width:${m}%"></em></i><b>${Math.round(m)} % Reife</b></div><small>${esc(c.evidence_text || `${Number(c.samples||0)} ${c.evidence_label || "Proben"}`)}</small>${c.detail ? `<small>${esc(c.detail)}</small>` : ""}</div></div>`;
        };
        if (this._info === "learning:quality") {
            const score = reliability.score_percent == null ? null : Number(reliability.score_percent);
            const effect = effectiveness.improvement_percent == null ? null : Number(effectiveness.improvement_percent);
            const effectLabel = effectiveness.status_label || "Sammelt Vergleichsdaten";
            const generation = effectiveness.generation_effectiveness || {};
            const generationEffect = generation.improvement_percent == null ? null : Number(generation.improvement_percent);
            return `<section class="info-panel learning-detail-panel"><div class="tiny info-kicker">MODELLQUALITÄT & DIAGNOSE</div><h3>Wie gut FreshAirIQ aktuell vorhersagt</h3><p>Lernreife und Prognosequalität sind getrennt. Zusätzlich vergleicht FreshAirIQ jede neue geeignete Lüftung paarweise mit einem eingefrorenen, ungelernten Grundmodell. Sobald für denselben Raum eine ältere, abweichende Forecast-Generation existiert, wird außerdem die aktuelle Generation gegen diesen unmittelbaren beobachteten Vorgänger unter derselben Startlage und Messdauer replayt.</p><div class="learning-quality-grid"><div><span>Prognosegüte</span><b>${score == null ? "–" : Math.round(score)+" %"}</b></div><div><span>Betragsgenauigkeit</span><b>${reliability.magnitude_accuracy_percent == null ? "–" : fmt(reliability.magnitude_accuracy_percent,0)+" %"}</b></div><div><span>Richtung</span><b>${reliability.direction_accuracy_percent == null ? "–" : fmt(reliability.direction_accuracy_percent,0)+" %"}</b></div><div><span>MAE</span><b>${(backtest.overall||{}).moisture_mae_ml == null ? "–" : fmt((backtest.overall||{}).moisture_mae_ml,0)+" ml"}</b></div><div><span>Lernwirkung vs. Grundmodell</span><b>${effect == null ? "–" : (effect >= 0 ? "+" : "") + fmt(effect,1)+" %"}</b></div><div><span>Aktuell vs. vorherige Generation</span><b>${generationEffect == null ? "–" : (generationEffect >= 0 ? "+" : "") + fmt(generationEffect,1)+" %"}</b></div><div><span>Paarvergleiche</span><b>${Number(effectiveness.samples || 0)}</b></div><div><span>Unabhängige Lüftungen</span><b>${Number(effectiveness.independent_sessions || 0)}</b></div><div><span>Generationenvergleiche</span><b>${Number(generation.independent_sessions || 0)}</b></div><div><span>Unterschiedliche Tage</span><b>${Number(effectiveness.distinct_days || 0)}</b></div><div><span>Gelerntes Modell MAE</span><b>${effectiveness.production_mae_ml == null ? "–" : fmt(effectiveness.production_mae_ml,0)+" ml"}</b></div><div><span>Grundmodell MAE</span><b>${effectiveness.baseline_mae_ml == null ? "–" : fmt(effectiveness.baseline_mae_ml,0)+" ml"}</b></div><div><span>Aktuelle Generation MAE</span><b>${generation.current_model_mae_ml == null ? "–" : fmt(generation.current_model_mae_ml,0)+" ml"}</b></div><div><span>Vorherige Generation MAE</span><b>${generation.previous_model_mae_ml == null ? "–" : fmt(generation.previous_model_mae_ml,0)+" ml"}</b></div><div><span>95-%-Intervall Lerngewinn</span><b>${effectiveness.paired_gain_ci95_low_ml == null || effectiveness.paired_gain_ci95_high_ml == null ? "–" : signed(effectiveness.paired_gain_ci95_low_ml," ml")+" bis "+signed(effectiveness.paired_gain_ci95_high_ml," ml")}</b></div></div><div class="learning-overview-note"><ha-icon icon="mdi:compare-horizontal"></ha-icon><span><b>${esc(effectLabel)}</b> · Belegt wird eine Verbesserung erst nach mindestens ${Number((effectiveness.evidence_rules||{}).minimum_samples || 12)} geeigneten Raumvergleichen aus ${Number((effectiveness.evidence_rules||{}).minimum_independent_sessions || 8)} unabhängigen Lüftungen an ${Number((effectiveness.evidence_rules||{}).minimum_distinct_days || 4)} unterschiedlichen Tagen und einem vollständig positiven, nach Lüftungen geclusterten Fehlerintervall. Der Generationenvergleich verwendet dieselben konservativen Evidenzregeln.</span></div>${byKey.forecast_validation ? componentCard(byKey.forecast_validation) : ""}</section>`;
        }
        if (this._info === "learning:longterm") {
            const season = byKey.seasonality || {}, night = byKey.night_model || {};
            const breakdown = Array.isArray(season.season_breakdown) ? season.season_breakdown : [];
            const seasonIcon = {spring:"mdi:sprout",summer:"mdi:white-balance-sunny",autumn:"mdi:leaf-maple",winter:"mdi:snowflake"};
            const seasonCards = breakdown.length ? breakdown.map(x => `<div class="season-card ${x.optimized ? "done" : ""}"><ha-icon icon="${seasonIcon[x.key] || "mdi:leaf"}"></ha-icon><b>${esc(x.label || x.key)}</b><strong>${Number(x.observed_days||0)} / 60 Tage</strong><i><em style="width:${Math.min(100,Number(x.observed_days||0)/60*100)}%"></em></i><small>${x.optimized ? "Vollständig durchlaufen und ausreichend belegt" : Number(x.observed_days||0)>0 ? "Lernt noch" : "Noch nicht vollständig beobachtet"}</small></div>`).join("") : `<div class="learning-empty">Jahreszeiten werden mit den nächsten Beobachtungstagen aufgebaut.</div>`;
            const seasonM = Math.max(0,Math.min(100,Number(season.maturity_percent||0))), nightM = Math.max(0,Math.min(100,Number(night.maturity_percent||0)));
            return `<section class="info-panel learning-detail-panel"><div class="tiny info-kicker">LANGZEITLERNEN</div><h3>Saisonalität & Nachtmodell</h3><p>Hier zählt Zeit als echte Erfahrung: jede Nacht höchstens einmal und jede Jahreszeit erst, wenn sie vollständig durchlaufen und ausreichend mit brauchbaren Messwerten belegt wurde.</p><div class="longterm-hero"><ha-icon icon="mdi:leaf"></ha-icon><div class="longterm-hero-copy"><b>Langzeitlernen</b><span>${Math.round((seasonM+nightM)/2)} % Reife · ${Number(season.calendar_span_days||0)} Tage Kalenderabdeckung</span></div></div><div class="learning-section-title"><b>Saisonalität</b><span>${Number(season.samples||0)}/4 Jahreszeiten optimiert</span></div><div class="season-grid">${seasonCards}</div><div class="season-total"><span>Gesamtmodell Saisonalität</span><b>${Number(season.samples||0)} / 4 Jahreszeiten · ${Number(season.calendar_span_days||0)} / 365 Tage</b><i><em style="width:${seasonM}%"></em></i></div><div class="learning-section-title"><b>Nachtmodell</b><span>${esc(night.status || "Lernt noch")}</span></div><div class="night-grid"><div><strong>${Number(night.samples||0)} / 120</strong><b>Nächte gelernt</b><i><em style="width:${nightM}%"></em></i></div><div><strong>${Number(night.raw_samples||0)}</strong><b>Messupdates</b><small>${esc(night.detail || "Unterschiedliche Nächte bestimmen die Reife.")}</small></div></div><div class="learning-overview-note"><ha-icon icon="mdi:lightbulb-outline"></ha-icon><span>Hohe Pollingraten beschleunigen die Reife nicht. Entscheidend sind unterschiedliche Nächte, Tage und vollständig beobachtete Jahreszeiten.</span></div></section>`;
        }
        const group = groups[this._info];
        if (!group) return null;
        const [title, subtitle, icon, keys] = group;
        const selected = keys.map(k => byKey[k]).filter(Boolean);
        const maturity = selected.length ? selected.reduce((a,c)=>a+Number(c.maturity_percent||0),0)/selected.length : 0;
        return `<section class="info-panel learning-detail-panel"><div class="tiny info-kicker">FRESHAIRIQ INTELLIGENCE 2.0</div><div class="learning-group-hero"><ha-icon icon="${icon}"></ha-icon><div><h3>${esc(title)}</h3><p>${esc(subtitle)}</p></div><strong>${Math.round(maturity)} %</strong></div><div class="learning-detail-list">${selected.map(componentCard).join("") || `<div class="learning-empty">Noch keine Lerndaten verfügbar.</div>`}</div></section>`;
    }
    _details(st, rooms) {
        var _a, _b, _c, _d, _e, _f, _g;
        const days = Number(st.statistics_days || 14), history = st.history_14d || [], summary = st.history_summary || {};
        const configuredLevels = Array.isArray(st.levels) ? st.levels : [];
        const present = [...new Set(rooms.map(r => r.floor || "Unzugeordnet"))];
        const floors = [...configuredLevels.filter(x => present.includes(x)), ...present.filter(x => !configuredLevels.includes(x))];
        const learningRooms = rooms.filter(r => r.calculation_enabled !== false && r.data_quality === "ok");
        const learningSamples = learningRooms.reduce((a, r) => a + Number(r.learning_samples || 0), 0);
        const stableRooms = learningRooms.filter(r => Number(r.learning_samples || 0) >= 25).length;
        const veryStableRooms = learningRooms.filter(r => Number(r.learning_samples || 0) >= 50).length;
        const learningTitle = learningRooms.length && veryStableRooms === learningRooms.length ? "Sehr stabil" : learningRooms.length && stableRooms === learningRooms.length ? "Stabil" : learningSamples > 0 ? "Lernt noch" : "Grundschätzung";
        const last = st.last_ventilation || null;
        const lastCard = this._lastVentilationTile(last);
        const supportUntilRaw = this._supportCooldownUntil || st.diagnostics_upload?.support_cooldown_until || null;
        if (supportUntilRaw) this._supportCooldownUntil = supportUntilRaw;
        const supportUntil = supportUntilRaw ? new Date(supportUntilRaw) : null;
        const supportRemainingMinutes = supportUntil && supportUntil.getTime() > Date.now() ? Math.max(1, Math.ceil((supportUntil.getTime() - Date.now()) / 60000)) : 0;
        const supportSendLabel = supportRemainingMinutes ? `<b>Noch ${supportRemainingMinutes} Min. gesperrt</b><span>danach erneut senden</span>` : '<b>Diagnosedaten</b><span>an Support senden</span>';
        return `<div class="modal" role="dialog" aria-modal="true"><div class="dialog"><div class="dialog-head"><button id="details-back" class="dialog-back" aria-label="Zurück"><ha-icon icon="mdi:arrow-left"></ha-icon></button><div class="dialog-head-copy"><div class="tiny">FRESHAIRIQ DETAILS</div><div class="dialog-title">Hausklima & Lüftungsintelligenz</div></div><button id="close" class="close" aria-label="Schließen">✕</button></div><div class="dialog-scroll"><div class="overview"><div class="summary clickable" data-info="water"><div class="tiny">WASSER IN DER LUFT</div><strong>${Math.round(Number(st.total_water_ml || 0))} ml</strong><span>über berechnete Räume</span></div><div class="summary clickable" data-info="threshold"><div class="tiny">LÜFTUNGSSCHWELLE</div><strong>${Math.round(Number(st.ventilation_threshold_ml || 0))} ml</strong><span>${st.ventilation_threshold_mode === "adaptive_home_size" ? "adaptiv · Ziel ca. 3–5×/Tag" : `${fmt(st.ventilation_threshold_percent || 10, 1)} % der Wassermenge`}</span></div><div class="summary clickable" data-info="night"><div class="tiny">NACHTPROGNOSE</div><strong style="color:#ff9b7a">+${Math.round(Number(st.overnight_forecast_ml || 0))} ml</strong><span>${Number(st.night_model_samples || 0)} Lernproben</span></div><div class="summary clickable" data-info="pollen"><div class="tiny">POLLEN</div><strong style="color:${st.pollen_blocked ? "#ff7770" : "#67df92"}">${st.pollen_enabled ? fmt(st.pollen_index, 1) : "aus"}</strong><span>${st.pollen_enabled ? `Grenze ${fmt(st.pollen_limit, 1)}` : "nicht berücksichtigt"}</span></div></div><div class="history-grid"><div class="history"><div class="history-head"><div><div class="tiny">LETZTE ${days} TAGE</div><b>Wasser in der Hausluft · Tagesmittel</b></div><strong>${fmt(Number(((_a = lastItem((st.water_history_14d || []).filter(x => x.samples > 0))) === null || _a === void 0 ? void 0 : _a.water_ml) || 0) / 1000, 2)} l</strong></div><div class="chart">${this._svgBars(st.water_history_14d || [])}</div><div class="muted">Absolute Feuchte × Raumvolumen, über alle überwachten Räume aggregiert. Tageswert = Mittel aller gültigen Messungen; Trend: ${esc(((_b = lastItem((st.water_history_14d || []).filter(x => x.samples > 0))) === null || _b === void 0 ? void 0 : _b.trend) || "stabil")}.</div></div><div class="history"><div class="history-head"><div><div class="tiny">ANWESENHEIT</div><b>Anwesenheit & Bewohner</b></div><strong>${Number(st.presence_confidence || 0) >= 80 ? "sicher erkannt" : Number(st.presence_confidence || 0) >= 55 ? "wahrscheinlich" : "noch unsicher"}</strong></div><div class="muted">${fmtPeople(st.effective_occupants || 0)} ${Number(st.effective_occupants) === 1 ? "Person" : "Personen"} aktuell zuhause/erwartet · ${Number(st.adult_occupants || 0)} Erwachsene · ${Number(st.child_occupants || 0)} Kinder · Gäste ${Number(st.guest_adults || 0)}+${Number(st.guest_children || 0)}</div><div class="muted">FreshAirIQ nutzt die Anwesenheit für Nachtprognose und Belegungsmodell.${st.pets_in_household ? " Haustiermodus ist aktiv; reine Bewegung wird vorsichtiger bewertet." : ""}</div></div></div>${this._learningComponentsCard(st, rooms)}${lastCard}${this._ventilationLogCard()}</div></div></div></div>`;
    }
    _ventilationLogCard() {
        const end = new Date();
        const start = new Date(end.getTime() - 30 * 86400000);
        const iso = d => d.toISOString().slice(0,10);
        return `<div class="history" style="margin-top:8px"><div class="history-head"><div><div class="tiny">LÜFTUNGSPROTOKOLL</div><b>Lokaler PDF-Nachweis</b></div><strong>lokal</strong></div><div class="muted">FreshAirIQ protokolliert abgeschlossene Lüftungen lokal in Home Assistant. Wähle einen Zeitraum und erstelle eine übersichtliche PDF mit Raum, Zeit, Dauer und – soweit durch die Sensoren belastbar erfasst – Klima- und Feuchtewirkung. Die PDF ist eine Sensordokumentation und keine rechtliche Bewertung.</div><div style="display:flex;gap:8px;align-items:end;flex-wrap:wrap;margin-top:10px"><label><span class="tiny">VON</span><input class="settings-input" id="ventlog-start" type="date" value="${iso(start)}"></label><label><span class="tiny">BIS</span><input class="settings-input" id="ventlog-end" type="date" value="${iso(end)}"></label><button class="quick-forecast" id="ventlog-export"><ha-icon icon="mdi:file-pdf-box"></ha-icon><b>PDF erstellen</b><span>Lüftungsprotokoll</span></button></div></div>`;
    }
    async _exportVentilationLog() {
        const button = this.shadowRoot?.getElementById("ventlog-export");
        const original = button?.innerHTML;
        try {
            const entryId = this._settingsEntryId();
            if (!entryId) throw new Error("FreshAirIQ-Konfiguration nicht gefunden");
            const start = this.shadowRoot?.getElementById("ventlog-start")?.value || "";
            const end = this.shadowRoot?.getElementById("ventlog-end")?.value || "";
            if (button) button.innerHTML = '<ha-icon icon="mdi:progress-clock"></ha-icon><b>PDF wird erstellt</b><span>bitte warten</span>';
            const payload = await this._hass.callApi("GET", `freshairiq/ventilation-log/${entryId}?start=${encodeURIComponent(start)}&end=${encodeURIComponent(end)}`);
            const raw = atob(payload.pdf_base64 || "");
            const bytes = new Uint8Array(raw.length);
            for (let i=0;i<raw.length;i++) bytes[i] = raw.charCodeAt(i);
            const url = URL.createObjectURL(new Blob([bytes], {type:"application/pdf"}));
            const a = document.createElement("a"); a.href=url; a.download=payload.filename || "FreshAirIQ-Lueftungsprotokoll.pdf"; a.click();
            setTimeout(() => URL.revokeObjectURL(url), 1000);
        } catch (err) {
            console.error("FreshAirIQ ventilation log export failed", err);
            const info = this._rememberSupportError(err, "FAIQ-PDF-EXPORT-001");
            window.alert(this._supportErrorText(info));
        } finally { if (button && original) button.innerHTML = original; }
    }
    async _exportDiagnostics() {
        var _a;
        const button = (_a = this.shadowRoot) === null || _a === void 0 ? void 0 : _a.getElementById("diagnostics-export");
        const original = button === null || button === void 0 ? void 0 : button.innerHTML;
        try {
            if (button)
                button.innerHTML = '<ha-icon icon="mdi:progress-clock"></ha-icon><b>Export wird erstellt</b><span>bitte warten</span>';
            await this._registerFieldTestClient(true);
            const payload = await this._hass.callApi("GET", "freshairiq/diagnostics");
            const stamp = new Date().toISOString().split(":").join("-").replace(/\.\d{3}Z$/, "Z");
            const blob = new Blob([JSON.stringify(payload, null, 2)], { type: "application/json;charset=utf-8" });
            const url = URL.createObjectURL(blob);
            const a = document.createElement("a");
            a.href = url;
            a.download = `FreshAirIQ-diagnostics-${stamp}.json`;
            a.style.display = "none";
            document.body.appendChild(a);
            a.click();
            a.remove();
            setTimeout(() => URL.revokeObjectURL(url), 30000);
            if (button)
                button.innerHTML = '<ha-icon icon="mdi:check-circle-outline"></ha-icon><b>Export erstellt</b><span>Datei ist bereit</span>';
            setTimeout(() => { if (button && original)
                button.innerHTML = original; }, 1800);
        }
        catch (err) {
            console.error("FreshAirIQ diagnostics export failed", err);
            const info = this._rememberSupportError(err, "FAIQ-DIAG-EXPORT-001");
            if (button)
                button.innerHTML = `<ha-icon icon="mdi:alert-circle-outline"></ha-icon><b>Export fehlgeschlagen</b><span>${esc(info.code)}</span>`;
            window.alert(this._supportErrorText(info));
            setTimeout(() => { if (button && original)
                button.innerHTML = original; }, 2500);
        }
    }

    _render() {
        FAIQ_NUMBER_LOCALE = this._uiLanguage();
        // Error boundary (0.26.3.2): a render exception must never leave the
        // person on an unresponsive card. Tapping Rooms/Details/etc. only changes
        // state and re-renders, so an exception here used to look like "nothing
        // happens". Now the card recovers to the dashboard and shows a readable
        // error code instead.
        try {
            this._renderImpl();
        } catch (error) {
            this._handleRenderFailure(error, "render");
        }
    }
    _handleRenderFailure(error, phase = "render") {
        const view = this._info || (this._dialogOpen ? "details" : "dashboard");
        try { console.error(`FreshAirIQ ${phase} failed in view "${view}"`, error); } catch (_) { /* ignore */ }
        const wasOverlay = !!(this._info || this._dialogOpen);
        this._cancelQueuedRender();
        this._cancelQueuedLiveRefresh();
        if (wasOverlay) {
            this._info = null; this._dialogOpen = false; this._infoStack = [];
            try { this._resetInfoNavigation(); } catch (_) { /* ignore */ }
            try {
                this._renderImpl();
                this._showRenderNotice(error, view, false);
                return;
            } catch (_) { /* fall through to the stand-alone fallback */ }
        }
        this._showRenderNotice(error, view, true);
    }
    _showRenderNotice(error, view, standalone) {
        if (!this.shadowRoot) return;
        const de = this._uiLanguage() === "de";
        const detail = esc(`${(error && error.name) || "Error"}: ${String((error && error.message) || error || "").slice(0, 160)}`);
        const title = de ? `Die Ansicht „${esc(view)}“ konnte nicht angezeigt werden.` : `The “${esc(view)}” view could not be displayed.`;
        const hint = de ? "Bitte diesen Code oder einen Screenshot an den Support senden." : "Please send this code or a screenshot to support.";
        const retry = de ? "Erneut versuchen" : "Try again";
        const body = `<div class="faiq-render-notice" role="alert"><div><b>${title}</b><span>${de ? "Fehlercode" : "Error code"}: FAIQ-UI-RENDER-001 · ${detail}</span><span>${hint}</span></div><button type="button" class="faiq-render-retry">${retry}</button></div>`;
        if (standalone) {
            this._replaceRenderedContent(`<ha-card><div class="card">${body}</div></ha-card>`);
        } else {
            const host = this.shadowRoot.querySelector(".card");
            if (!host) return;
            const holder = document.createElement("template");
            holder.innerHTML = body;
            host.prepend(holder.content);
        }
        const button = this.shadowRoot.querySelector(".faiq-render-retry");
        if (button) button.addEventListener("click", e => { e.stopPropagation(); this._render(); });
    }
    _renderImpl() {
        this._cancelQueuedRender();
        this._cancelQueuedLiveRefresh();
        this._liveViewSnapshot = null;
        this._liveHtmlCache = {};
        var _a, _b, _c, _d, _e, _f, _g, _h, _j, _k, _l, _m, _o, _p, _q, _r, _s, _t, _u, _v, _w;
        if (!this.shadowRoot)
            return;
        const oldDialog = this.shadowRoot.querySelector(".dialog-scroll");
        if (oldDialog)
            this._dialogScrollTop = oldDialog.scrollTop;
        const oldSubdialog = this.shadowRoot.querySelector(".subdialog");
        if (oldSubdialog) {
            // The DOM still represents the view that was rendered before a navigation
            // event changed this._info. Navigation handlers persist that old view
            // explicitly before changing this._info. Never write oldSubdialog.scrollTop
            // into the *new* logical view here, otherwise Back overwrites the parent's
            // saved position with the child's scroll position (usually 0).
            this._subdialogScrollTop = oldSubdialog.scrollTop;
        }
        const oldScroll = this._forceDialogTop ? 0 : this._dialogScrollTop;
        const oldSubScroll = this._pendingSubdialogScrollTop !== null
            ? this._pendingSubdialogScrollTop
            : (this._info ? ((this._infoScrollByView && this._infoScrollByView.get(this._info)) ?? this._subdialogScrollTop) : this._subdialogScrollTop);
        this._pendingSubdialogScrollTop = null;
        this._forceDialogTop = false;
        const entity = this._statusEntity();
        if (!entity) {
            this._replaceRenderedContent(`<ha-card><div style="padding:16px">FreshAirIQ wartet auf die Status-Entität.</div></ha-card>`);
            return;
        }
        this._ensureRelevantStateIds(entity);
        const st = Object.assign({}, entity.attributes || {});
        if (this._postResultTimer) { clearTimeout(this._postResultTimer); this._postResultTimer = null; }
        if (!this._info && !this._dialogOpen) {
            const recent = this._recentVentilation(st);
            if (recent && Number(recent._remainingMs) > 0) {
                this._postResultTimer = setTimeout(() => { this._postResultTimer = null; if (!this._info && !this._dialogOpen) this._render(); }, Number(recent._remainingMs) + 80);
            }
        }
        let rooms = Object.values(st.rooms || {}).filter(r => r && typeof r === "object");
        // The coordinator publishes an explicit canonical key order. Never infer
        // presentation order from object insertion order or transient per-room
        // entity updates; that was the reason rooms such as Wintergarten could
        // jump to a different position on mobile clients.
        const configuredOrder = Array.isArray(st.room_sort_order) ? st.room_sort_order.map(String) : [];
        const canonicalOrder = new Map(configuredOrder.map((key, index) => [key, index]));
        if (!canonicalOrder.size) this._orderedRooms(rooms).forEach((room, index) => canonicalOrder.set(String(room.key || ""), index));
        const byKey = new Map(rooms.map(r => [String(r.key || ""), r]));
        const activeEntryId = st.freshairiq_entry_id || null;
        const roomStateIds = this._roomEntityIds && this._roomEntityIds.size ? this._roomEntityIds : null;
        const roomStates = roomStateIds ? Array.from(roomStateIds, id => this._hass.states[id]).filter(Boolean) : Object.values(((_a = this._hass) === null || _a === void 0 ? void 0 : _a.states) || {});
        for (const s of roomStates) {
            const a = (s === null || s === void 0 ? void 0 : s.attributes) || {}, r = a.freshairiq_room_payload;
            if (!r || !["room_v1", "room_v2"].includes(a.freshairiq_transport))
                continue;
            if (activeEntryId) {
                if (a.freshairiq_transport !== "room_v2" || a.freshairiq_entry_id !== activeEntryId)
                    continue;
            }
            const key = String(r.key || a.freshairiq_room_key || "");
            if (!key)
                continue;
            const base = byKey.get(key) || {};
            byKey.set(key, Object.assign({}, base, r));
        }
        rooms = Array.from(byKey.values()).filter(r => r && r.key);
        if (rooms.length && !Number(st.total_water_ml)) {
            st.total_water_ml = rooms.filter(r => r.calculation_enabled !== false && r.data_quality === "ok").reduce((a, r) => a + Number(r.water_in_air_ml || 0), 0);
        }
        rooms.sort((a, b) => {
            const ai = canonicalOrder.has(String(a.key || "")) ? canonicalOrder.get(String(a.key || "")) : Number(a.sort_order ?? 9999);
            const bi = canonicalOrder.has(String(b.key || "")) ? canonicalOrder.get(String(b.key || "")) : Number(b.sort_order ?? 9999);
            return ai - bi || String(a.name || a.key || "").localeCompare(String(b.name || b.key || ""), "de");
        });
        const potential = Number((_b = st.potential_total_ml) !== null && _b !== void 0 ? _b : this._num("sensor.freshairiq_removable_moisture")), live = Number((_c = st.live_balance_ml) !== null && _c !== void 0 ? _c : this._num("sensor.freshairiq_live_moisture_balance")), next5Effect = Number((_e = (_d = st.forecast_moisture_effect_ml) !== null && _d !== void 0 ? _d : st.next_5_min_effect_ml) !== null && _e !== void 0 ? _e : this._num("sensor.freshairiq_next_5_minutes")), duration = Number((_f = st.recommended_duration_min) !== null && _f !== void 0 ? _f : this._num("sensor.freshairiq_recommended_ventilation_duration")), remaining = Number((_g = st.remaining_duration_min) !== null && _g !== void 0 ? _g : this._num("sensor.freshairiq_ventilation_time_remaining")), tempChange = Number((_h = st.temperature_change_live_c) !== null && _h !== void 0 ? _h : this._num("sensor.freshairiq_temperature_change_since_ventilation_start")), overnight = Number((_j = st.overnight_forecast_ml) !== null && _j !== void 0 ? _j : this._num("sensor.freshairiq_overnight_moisture_forecast"));
        const active = rooms.filter(r => r.active && r.calculation_enabled !== false), hero = this._hero(st, rooms, live, potential), balance = moisture(live), pot = moisture(potential), next = moisture(next5Effect), night = { text: `+${Math.abs(Math.round(overnight))} ml`, color: "#ff9b7a" };
        const mouldRooms = rooms.filter(r => r.calculation_enabled !== false && ["Elevated", "High", "Very high"].includes(r.mould_level));
        const mouldWorst = rooms.reduce((a, r) => Number(r.surface_rh || 0) > Number(a.surface_rh || 0) ? r : a, { surface_rh: 0, mould_level: "Low" });
        const [mouldColor] = mouldStyle(mouldWorst.mould_level);
        const profile = this._profileValue(st), forecastH = this._forecastValue(st), activeCosts = Number((_k = st.forecast_cost) !== null && _k !== void 0 ? _k : active.reduce((a, r) => { var _a, _b; return a + Number((_b = (_a = r.forecast_cost) !== null && _a !== void 0 ? _a : r.next_5_min_cost) !== null && _b !== void 0 ? _b : 0); }, 0)), activeTemp = Number((_l = st.forecast_temperature_change_c) !== null && _l !== void 0 ? _l : (active.length ? active.reduce((a, r) => { var _a, _b; return a + Number((_b = (_a = r.forecast_temperature_change_c) !== null && _a !== void 0 ? _a : r.temp_next_5_min_c) !== null && _b !== void 0 ? _b : 0) * Number(r.volume_m3 || 0); }, 0) / Math.max(active.reduce((a, r) => a + Number(r.volume_m3 || 0), 0), 1) : 0));
        const timeText = active.length ? (remaining >= 0 ? `${Math.ceil(remaining)} min übrig` : `${Math.abs(Math.round(remaining))} min drüber`) : `${Math.round(duration)} min`;
        const moistureMain = active.length ? balance : pot;
        const rec = st.intelligent_recommendation || {};
        const dashboardVariant = this._config.dashboard_variant === "classic" ? "classic" : "iq";
        // The classic branch intentionally preserves the v0.25.0.75 landing surface.
        // Both variants share the same backend state, details, rooms and settings.
        const intelligentPanel = dashboardVariant === "classic" ? this._intelligentPanel(st, rooms) : this._compactAIPanel(st, rooms);
        const showBranding = this._config.show_branding !== false;
        const showProfileBadge = this._config.show_profile_badge !== false;
        const classicTopBar = showBranding || showProfileBadge ? `<div class="top ai-top${showBranding ? "" : " profile-only"}">${showBranding ? `<img class="logo" src="/freshairiq/frontend/freshairiq-icon.png" alt="FreshAirIQ"><div><div class="brand">FreshAir<span class="iq">IQ</span></div><div class="brand-subtitle">INTELLIGENT HOME CLIMATE</div></div>` : ""}${showProfileBadge ? `<div class="pill" data-info="profile">${esc(profileDE(profile))}</div>` : ""}</div>` : "";
        const iqTopBar = showBranding || showProfileBadge ? `<div class="top ai-top${showBranding ? "" : " profile-only"}">${showBranding ? `<img class="logo" src="/freshairiq/frontend/freshairiq-icon.png" alt="FreshAirIQ"><div><div class="brand">FreshAir<span class="iq">IQ</span></div><div class="brand-subtitle">${esc(this._t("shell.subtitle_iq"))}</div></div>` : ""}${showProfileBadge ? `<div class="pill" data-info="profile">${esc(profileDE(profile))}</div>` : ""}</div>` : "";
        const topBar = dashboardVariant === "classic" ? classicTopBar : iqTopBar;
        const consentState = (st.diagnostics_upload && st.diagnostics_upload.consent) || null;
        const isAdmin = !!(this._hass && this._hass.user && this._hass.user.is_admin);
        // 0.26.4.3: settings live only under Devices & services. The card no longer
        // writes the consent itself; it points admins to the one place to decide.
        const consentPrompt = consentState === "unset" && isAdmin && !this._consentDecided && !this._consentSnoozed() ? (() => {
            const de = this._uiLanguage() === "de";
            return `<div class="faiq-consent" role="region" aria-label="${de ? "Diagnosen teilen" : "Share diagnostics"}"><ha-icon icon="mdi:shield-check-outline"></ha-icon><span class="faiq-consent-text"><b>${de ? "Diagnosen teilen?" : "Share diagnostics?"}</b> ${de ? "Pseudonymisiert, ohne Namen oder Standort. Ohne Zustimmung wird nichts gesendet. Festlegen unter Geräte & Dienste → FreshAirIQ → Konfigurieren." : "Pseudonymised, no names or location. Nothing is sent without consent. Decide under Devices & services → FreshAirIQ → Configure."}</span><span class="faiq-consent-actions"><button type="button" data-consent-later>${de ? "Später" : "Later"}</button><button type="button" class="primary" data-consent-open>${de ? "Öffnen" : "Open"}</button></span></div>`;
        })() : "";
        this.style.setProperty("--faiq-hero-color", hero.color);
        this.style.setProperty("--faiq-hero-bg", `${hero.color}12`);
        this.style.setProperty("--faiq-hero-border", `${hero.color}2a`);
        this.style.setProperty("--faiq-font-recommendation", String(this._config.font_scale_recommendation));
        this.style.setProperty("--faiq-font-goals", String(this._config.font_scale_goals));
        this.style.setProperty("--faiq-font-rooms", String(this._config.font_scale_rooms));
        this.style.setProperty("--faiq-font-metrics", String(this._config.font_scale_metrics));
        this.style.setProperty("--faiq-font-details", String(this._config.font_scale_details));
        this.style.setProperty("--faiq-font-meta", String(this._config.font_scale_meta));
        this._replaceRenderedContent(`<ha-card><div class="card ${dashboardVariant === "iq" ? "iq-variant" : "classic-variant"}">${topBar}${consentPrompt}${intelligentPanel}${(this._config.show_details_button !== false || this._config.show_guests_button !== false || this._config.show_rooms_button !== false || this._config.show_support_button !== false) ? `<div class="actions compact-actions">${this._config.show_details_button === false ? "" : `<button class="details-btn" id="details"><ha-icon icon="mdi:chart-box-outline"></ha-icon><span>${esc(this._t("shell.details"))}</span></button>`}${this._config.show_guests_button === false ? "" : `<button class="details-btn" id="guests"><ha-icon icon="mdi:account-group-outline"></ha-icon><span>${esc(this._t("shell.guests"))}</span></button>`}${this._config.show_rooms_button === false ? "" : `<button class="details-btn" id="rooms"><ha-icon icon="mdi:floor-plan"></ha-icon><span>${esc(this._t("shell.rooms"))}</span></button>`}${this._config.show_support_button === false ? "" : `<button class="details-btn" id="support"><ha-icon icon="mdi:lifebuoy"></ha-icon><span>${esc(this._t("shell.support"))}</span></button>`}</div>` : ""}</div>${this._dialogOpen ? this._details(st, rooms) : ""}${this._info ? `<div class="submodal" id="submodal"><div class="subdialog">${this._infoNav()}${this._infoPanel(st, rooms)}${this._info === "profile" ? this._profileControls(st) : ""}${this._info === "next5" ? this._forecastControls(st) : ""}${this._info === "guests" ? this._guestControls(st) : ""}</div></div>` : ""}</ha-card>`);
        this.shadowRoot.querySelector("[data-consent-open]")?.addEventListener("click", e => {
            e.stopPropagation();
            try { window.history.pushState(null, "", "/config/integrations/integration/freshairiq"); window.dispatchEvent(new CustomEvent("location-changed", { detail: { replace: false } })); } catch (_) { /* ignore */ }
        });
        this.shadowRoot.querySelector("[data-consent-later]")?.addEventListener("click", e => {
            e.stopPropagation();
            try { window.localStorage.setItem("freshairiq-consent-later", String(Date.now())); } catch (_) { /* storage unavailable */ }
            this._consentDecided = true; this._render();
        });
        (_m = this.shadowRoot.getElementById("details")) === null || _m === void 0 ? void 0 : _m.addEventListener("click", e => { e.stopPropagation(); this._captureOverlayViewport(); this._dialogOpen = true; this._info = null; this._render(); });
        (_o = this.shadowRoot.getElementById("rooms")) === null || _o === void 0 ? void 0 : _o.addEventListener("click", e => { e.stopPropagation(); this._captureOverlayViewport(); clearTimeout(this._deferredRender); this._deferredRender = null; this._resetInfoNavigation(); this._info = "rooms"; this._render(); });
        (_p = this.shadowRoot.getElementById("guests")) === null || _p === void 0 ? void 0 : _p.addEventListener("click", e => { e.stopPropagation(); this._captureOverlayViewport(); this._resetInfoNavigation(); this._info = "guests"; this._render(); });
        this.shadowRoot.getElementById("support")?.addEventListener("click", async e => { e.stopPropagation(); this._captureOverlayViewport(); this._resetInfoNavigation(); this._info = "support"; this._render(); });
        (_q = this.shadowRoot.getElementById("close")) === null || _q === void 0 ? void 0 : _q.addEventListener("click", e => { e.stopPropagation(); this._dialogOpen = false; this._info = null; this._infoStack = []; this._render(); this._restoreOverlayViewport(); });
        const detailsBack = this.shadowRoot.getElementById("details-back");
        if (detailsBack) detailsBack.addEventListener("click", e => { e.stopPropagation(); this._dialogOpen = false; this._info = null; this._infoStack = []; this._render(); this._restoreOverlayViewport(); });
        (_r = this.shadowRoot.getElementById("diagnostics-export")) === null || _r === void 0 ? void 0 : _r.addEventListener("click", async (e) => { e.stopPropagation(); await this._exportDiagnostics(); });
        this.shadowRoot.getElementById("diagnostics-send")?.addEventListener("click", async (e) => { e.stopPropagation(); await this._sendDiagnosticsToDeveloper(); });
        this.shadowRoot.getElementById("ventlog-export")?.addEventListener("click", async (e) => { e.stopPropagation(); await this._exportVentilationLog(); });
        const feedbackSend = this.shadowRoot.getElementById("feedback-send");
        if (feedbackSend) feedbackSend.addEventListener("click", async (e) => {
            e.stopPropagation(); const entryId=this._settingsEntryId(); const type=this.shadowRoot.getElementById("feedback-type")?.value||"bug"; const message=(this.shadowRoot.getElementById("feedback-message")?.value||"").trim(); const result=this.shadowRoot.getElementById("feedback-result");
            if (!entryId || message.length < 3) { if(result) result.textContent="Bitte eine Beschreibung mit mindestens 3 Zeichen eingeben."; return; }
            feedbackSend.disabled=true; if(result) result.textContent="Wird sicher an den Diagnose-Hub übertragen …";
            try { const response=await this._hass.callApi("POST", `freshairiq/feedback/${entryId}`, {type,message,client_context:this._fieldTestClientContext()}); if(response?.error) throw new Error(response.error); if(result) result.textContent=`Gesendet · Feedback-ID ${response.feedback_id||"erstellt"}`; const box=this.shadowRoot.getElementById("feedback-message"); if(box) box.value=""; } catch(err) { if(result) result.textContent=`Senden fehlgeschlagen: ${this._formatApiError(err, "Bitte Verbindung zum Diagnose-Hub prüfen.")}`; } finally { feedbackSend.disabled=false; }
        });
        this.shadowRoot.querySelectorAll("summary[data-classic-disclosure]").forEach(summary => {
            const el = summary.parentElement;
            const key = summary.dataset.classicDisclosure;
            if (!el || !key) return;
            el.open = this._classicDisclosureOpen.has(key);
            el.addEventListener("toggle", () => {
                if (el.open) this._classicDisclosureOpen.add(key);
                else this._classicDisclosureOpen.delete(key);
            });
        });
        this.shadowRoot.querySelectorAll("[data-compact-toggle]").forEach(el => {
            const toggle = e => { e.stopPropagation(); const key = el.dataset.compactToggle; if (!key) return; this._compactExpanded = this._compactExpanded === key ? null : key; this._render(); };
            el.addEventListener("click", toggle);
            el.addEventListener("keydown", e => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); toggle(e); } });
        });
        (_s = this.shadowRoot.getElementById("info-close")) === null || _s === void 0 ? void 0 : _s.addEventListener("click", e => { e.stopPropagation(); this._info = null; this._resetInfoNavigation(); this._render(); if (!this._dialogOpen) this._restoreOverlayViewport(); });
        (_t = this.shadowRoot.getElementById("info-back")) === null || _t === void 0 ? void 0 : _t.addEventListener("click", e => { e.stopPropagation(); clearTimeout(this._deferredRender); this._deferredRender = null; this._rememberInfoViewport(this._info); const stackTop = this._infoScrollStack.length ? this._infoScrollStack.pop() : 0; const parent = this._infoStack.length ? this._infoStack.pop() : null; const restoreTop = parent ? ((this._infoScrollByView && this._infoScrollByView.get(parent)) ?? stackTop) : 0; this._info = parent; this._pendingSubdialogScrollTop = restoreTop; this._render(); });
        this.shadowRoot.querySelectorAll("[data-info]").forEach(el => el.addEventListener("click", async e => { e.stopPropagation(); const next = el.dataset.info; if (!next || next === this._info) return; if (this._info) this._pushInfoViewport(); else { if (!this._dialogOpen) this._captureOverlayViewport(); this._resetInfoNavigation(); } this._pendingSubdialogScrollTop = 0; this._info = next; this._render(); }));
        this.shadowRoot.querySelectorAll('[data-info][role="button"]').forEach(el => el.addEventListener("keydown", e => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); el.click(); } }));
        this.shadowRoot.querySelectorAll('[data-room][role="button"]').forEach(el => el.addEventListener("keydown", e => { if (e.target === el && (e.key === "Enter" || e.key === " ")) { e.preventDefault(); el.click(); } }));
        this.shadowRoot.querySelectorAll("[data-room]").forEach(el => el.addEventListener("click", e => { e.stopPropagation(); clearTimeout(this._deferredRender); this._deferredRender = null; const next = `room:${el.dataset.room}`; if (this._info && this._info !== next) this._pushInfoViewport(); else if (!this._info) { if (!this._dialogOpen) this._captureOverlayViewport(); this._resetInfoNavigation(); } this._pendingSubdialogScrollTop = 0; this._info = next; this._render(); }));
        (_u = this.shadowRoot.getElementById("submodal")) === null || _u === void 0 ? void 0 : _u.addEventListener("click", e => { if (e.target.id === "submodal") {
            this._info = null;
            this._resetInfoNavigation();
            this._render();
        } });
        this.shadowRoot.querySelectorAll("[data-profile]").forEach(el => el.addEventListener("click", async (e) => { e.stopPropagation(); const option = el.dataset.profile; const ent = this._profileEntity(); if (ent) {
            this._profileOverride = option;
            this._info = null;
            this._render();
            try { await this._hass.callService("select", "select_option", { entity_id: ent.entity_id, option }); setTimeout(() => { if (this._profileOverride === option) { this._profileOverride = null; this._render(); } }, 3000); } catch (err) { this._profileOverride = null; this._render(); throw err; }
        } }));
        const setForecast = async (value) => { const v = Math.max(1, Math.min(120, Math.round(Number(value) || 5))); const ent = this._forecastEntity(); if (ent) {
            this._forecastOverride = v;
            this._render();
            try { await this._hass.callService("number", "set_value", { entity_id: ent.entity_id, value: v }); setTimeout(() => { if (this._forecastOverride === v) { this._forecastOverride = null; this._render(); } }, 3000); } catch (err) { this._forecastOverride = null; this._render(); throw err; }
        } };
        this.shadowRoot.querySelectorAll("[data-forecast]").forEach(el => el.addEventListener("click", async (e) => { e.stopPropagation(); await setForecast(el.dataset.forecast); }));
        (_v = this.shadowRoot.getElementById("forecast-apply")) === null || _v === void 0 ? void 0 : _v.addEventListener("click", async (e) => { var _a; e.stopPropagation(); await setForecast((_a = this.shadowRoot.getElementById("forecast-custom")) === null || _a === void 0 ? void 0 : _a.value); });
        const setGuest = async (kind, value) => { const ent = this._guestEntity(kind); if (ent) {
            await this._hass.callService("number", "set_value", { entity_id: ent.entity_id, value: Math.max(0, Math.min(20, Math.round(Number(value) || 0))) });
        } };
        this.shadowRoot.querySelectorAll("[data-guest-kind]").forEach(el => el.addEventListener("click", async (e) => { e.stopPropagation(); const kind = el.dataset.guestKind, delta = Number(el.dataset.guestDelta || 0); this._guestOverride=this._guestOverride||{}; const backend=kind === "adult" ? Number(st.guest_adults || 0) : Number(st.guest_children || 0); const current=Number(this._guestOverride[kind] ?? backend); const next=Math.max(0,Math.min(20,current+delta)); this._guestOverride[kind]=next; this._render(); try { await setGuest(kind,next); setTimeout(()=>{ if(this._guestOverride&&this._guestOverride[kind]===next){ delete this._guestOverride[kind]; this._render(); } },1800); } catch(err){ delete this._guestOverride[kind]; this._render(); throw err; } }));
        (_w = this.shadowRoot.querySelector(".modal")) === null || _w === void 0 ? void 0 : _w.addEventListener("click", e => { if (e.target.classList.contains("modal")) {
            this._dialogOpen = false;
            this._info = null;
            this._render();
        } });
        const newDialog = this.shadowRoot.querySelector(".dialog-scroll");
        if (newDialog) {
            // Restore exactly once. Repeated delayed scrollTop writes fight native
            // momentum scrolling on iOS and were the main source of the "jumping"
            // feeling in older FreshAirIQ builds.
            newDialog.scrollTop = oldScroll;
            this._dialogScrollTop = newDialog.scrollTop;
            this._installAndroidTouchScroll(newDialog);
            newDialog.addEventListener("scroll", () => {
                this._dialogScrollTop = newDialog.scrollTop;
                this._lastScrollAt = Date.now();
            }, { passive: true });
            // Desktop/browser hotfix: Home Assistant may consume wheel events at
            // the dashboard/page level before the shadow-DOM dialog scrollport
            // gets native scrolling. Drive the wheel explicitly inside the main
            // detail scrollport and stop propagation only when it can scroll.
            newDialog.addEventListener("wheel", e => {
                if (!e.deltaY || newDialog.scrollHeight <= newDialog.clientHeight) return;
                const before = newDialog.scrollTop;
                newDialog.scrollTop += e.deltaY;
                if (newDialog.scrollTop !== before) {
                    e.preventDefault();
                    e.stopPropagation();
                    this._dialogScrollTop = newDialog.scrollTop;
                }
            }, { passive: false });
        }
        const newSubdialog = this.shadowRoot.querySelector(".subdialog");
        if (newSubdialog) {
            // Hotfix 0.9.4.3: keep the room-detail viewport stable on iOS/WebView.
            // In addition to preserving scrollTop, stop scroll chaining/rubber-band
            // gestures at the top/bottom edge from being handed to Home Assistant's
            // page scroller. That was the remaining sporadic jump-to-top path.
            newSubdialog.scrollTop = oldSubScroll;
            this._subdialogScrollTop = newSubdialog.scrollTop;
            // Native pan scrolling is intentionally left untouched. Android
            // WebView can stop scrolling when a nested touchmove handler calls
            // preventDefault at container boundaries. CSS overscroll containment
            // prevents scroll chaining without cancelling the gesture.
            this._installAndroidTouchScroll(newSubdialog);
            newSubdialog.addEventListener("scroll", () => {
                this._subdialogScrollTop = newSubdialog.scrollTop;
                if (this._info) { if (!this._infoScrollByView) this._infoScrollByView = new Map(); this._infoScrollByView.set(this._info, newSubdialog.scrollTop); }
                this._lastScrollAt = Date.now();
            }, { passive: true });
            // Desktop HA can hand wheel events through the shadow-DOM overlay to
            // the page behind it. Keep wheel movement inside the detail scrollport.
            newSubdialog.addEventListener("wheel", e => {
                if (!e.deltaY || newSubdialog.scrollHeight <= newSubdialog.clientHeight) return;
                const before = newSubdialog.scrollTop;
                newSubdialog.scrollTop += e.deltaY;
                if (newSubdialog.scrollTop !== before) {
                    e.preventDefault();
                    e.stopPropagation();
                    this._subdialogScrollTop = newSubdialog.scrollTop;
                }
            }, { passive: false });
        }
    }
}
class FreshAirIQCardEditor extends HTMLElement {
    constructor() {
        super();
        this.attachShadow({ mode: "open" });
        this._config = normalizeDashboardConfig({});
        this._pendingDashboardVariant = null;
        this._editorRenderContext = null;
    }
    setConfig(c) {
        const incoming = normalizeDashboardConfig(c);
        if (this._pendingDashboardVariant && incoming.dashboard_variant !== this._pendingDashboardVariant) {
            this._config = normalizeDashboardConfig(Object.assign({}, incoming, {dashboard_variant: this._pendingDashboardVariant}));
            queueMicrotask(() => this._emitConfigChanged(this._config));
        } else {
            this._config = incoming;
            if (this._pendingDashboardVariant === incoming.dashboard_variant) this._pendingDashboardVariant = null;
        }
        this._render();
    }
    _emitConfigChanged(config) {
        const event = new CustomEvent("config-changed", {detail: {config: normalizeDashboardConfig(config)}, bubbles: true, composed: true});
        this.dispatchEvent(event);
    }
    _editorDE() {
        return this._uiLanguage() === "de";
    }
    _uiLanguage() {
        const raw = String((this._hass && (this._hass.language || this._hass.locale?.language)) || navigator.language || "en").toLowerCase();
        return raw.startsWith("de") ? "de" : "en";
    }
    _t(key, vars = {}) {
        const entry = FAIQ_UI[key];
        if (!entry) return key;
        let out = String(entry[this._uiLanguage()] ?? entry.en ?? entry.de ?? key);
        for (const [name, value] of Object.entries(vars)) out = out.split(`{${name}}`).join(String(value));
        return out;
    }
    set hass(h) {
        this._hass = h;
        // Home Assistant replaces the hass object frequently. Rebuilding the
        // editor Shadow DOM for every state update closes an open native
        // <select> immediately (most visible on iOS/Android). Only rerender
        // when editor-relevant context actually changes; API option loads
        // trigger their own render when data arrives.
        const language = String((h && (h.language || h.locale?.language)) || navigator.language || "en").toLowerCase();
        const renderContext = `${language}|${this._settingsEntryId() || ""}`;
        if (this._editorRenderContext !== renderContext) {
            this._editorRenderContext = renderContext;
            this._render();
        }
    }
    _settingsEntryId() {
        if (!this._hass || !this._hass.states) return null;
        const states = Object.values(this._hass.states);
        const preferred = states.filter(s => {
            const a = (s && s.attributes) || {};
            return a.freshairiq_transport === "status_v2" && !!a.freshairiq_entry_id;
        });
        const status = preferred.find(s => s.entity_id === "sensor.freshairiq_status") || preferred[0];
        return status && status.attributes ? status.attributes.freshairiq_entry_id : null;
    }
    _render() {
        if (!this.shadowRoot) return;
        const infoFields = [
            ["info_moisture", "Feuchte & Wasserbilanz", "Aktuelle Feuchte, entfernbares Potenzial und Live-Bilanz."],
            ["info_temperature", "Temperaturänderungen", "Temperaturverlust oder -gewinn während und nach dem Lüften."],
            ["info_time", "Lüftungszeit", "Empfohlene Dauer und verbleibende IQ-Zeit."],
            ["info_forecast", "Kurzzeitprognose", "Vorhersage für den gewählten Prognosezeitraum."],
            ["info_night", "Nachtprognose & Nachtstrategie", "Nächtliche Entwicklung und empfohlene Fensterstrategie."],
            ["info_mould", "Schimmelrisiko", "Oberflächen-RH und auffällige Räume."],
            ["info_energy", "Energie & Kosten", "Wiederaufheizenergie und geschätzte Heizkosten."],
            ["info_pollen", "Pollen & Außenluft-Veto", "Polleninformationen als ergänzende Analyse; kritische Warnungen bleiben sicherheitsbedingt möglich."],
            ["info_voc", "VOC / TVOC", "Zeigt konfigurierte VOC-/TVOC-Zusatzwerte in Raumdetails. Die globale Berücksichtigung wird unter Geräte & Dienste → FreshAirIQ → Konfigurieren gesteuert."],
            ["info_pm25", "PM2.5 / Feinstaub", "Zeigt konfigurierte PM2.5-Zusatzwerte in Raumdetails. Die globale Berücksichtigung wird unter Geräte & Dienste → FreshAirIQ → Konfigurieren gesteuert."],
            ["info_illuminance", "Helligkeit", "Zeigt konfigurierte Helligkeitswerte in Raumdetails. Die globale Berücksichtigung wird unter Geräte & Dienste → FreshAirIQ → Konfigurieren gesteuert."],
            ["info_cross_ventilation", "Querlüftung", "Zeigt Querlüftung als ergänzende Analyseinformation, wenn sie erkannt wird."],
        ];
        const recommendationFields = [
            ["show_rec_ventilate", "Lüften / Weiterlüften", "Zeigt Empfehlungen zum Starten oder Fortsetzen einer Lüftung."],
            ["show_rec_close", "Schließen", "Zeigt Empfehlungen zum Beenden einer Lüftung."],
            ["show_rec_wait", "Warten / Nicht lüften", "Zeigt raumspezifische Hinweise, wenn Lüften aktuell nicht sinnvoll ist."],
            ["show_rec_cooling", "Sommerkühlung", "Zeigt Empfehlungen zum Lüften für Kühlung."],
            ["show_rec_sensor", "Sensor prüfen", "Zeigt Empfehlungen bei fehlenden oder unplausiblen Messwerten."],
        ];
        const layoutFields = [
            ["show_branding", "Logo & FreshAirIQ-Schriftzug", "Ausblenden macht die Karte kompakter."],
            ["show_profile_badge", "Betriebsmodus oben", "Zeigt den aktuellen Modus als kompakte Kachel oben rechts."],
            ["show_iq_process", "IQ-Aktiv / Analyseleiste", "Zeigt, was FreshAirIQ gerade analysiert und wie sicher die Prognose ist."],
            ["show_details_button", "Details-Schaltfläche", "Blendet den direkten Details-Button ein oder aus."],
            ["show_guests_button", "Gäste-Schaltfläche", "Blendet die Schnellsteuerung für Gäste ein oder aus."],
            ["show_rooms_button", "Räume-Schaltfläche", "Blendet den direkten Zugriff auf die Raumübersicht ein oder aus."],
            ["show_support_button", "Support-Schaltfläche", "Blendet den zentralen Zugriff auf Diagnose, Feedback und Support ein oder aus."],
        ];
        const row = ([key, label, description]) => `<div class="row"><div><label>${label}</label><span>${description}</span></div><ha-switch data-key="${key}" ${this._config[key] !== false ? "checked" : ""}></ha-switch></div>`;
        const scaleFields = this._editorDE() ? [
            ["font_scale_recommendation","Hauptempfehlung","Überschrift, Aktion und Zusammenfassung der aktuellen Empfehlung."],
            ["font_scale_goals","Ziele","Feuchte-, Temperatur- und CO₂-Ziele sowie deren Wirkung und Zeit."],
            ["font_scale_rooms","Räume","Raumnamen, Raumstatus und raumbezogene Hinweise."],
            ["font_scale_metrics","Kennzahlen","Werte in Kennzahlen- und Informationskacheln."],
            ["font_scale_details","Begründungen & Details","Begründungen, Alternativen und ausführliche Entscheidungstexte."],
            ["font_scale_meta","Kleine Zusatztexte","Labels, Hinweise und andere kleine Metatexte."],
        ] : [
            ["font_scale_recommendation","Main recommendation","Heading, action and summary of the current recommendation."],
            ["font_scale_goals","Goals","Humidity, temperature and CO₂ goals including impact and time."],
            ["font_scale_rooms","Rooms","Room names, room status and room-specific hints."],
            ["font_scale_metrics","Metrics","Values in metric and information tiles."],
            ["font_scale_details","Reasons & details","Reasons, alternatives and detailed decision text."],
            ["font_scale_meta","Small supporting text","Labels, hints and other small metadata text."],
        ];
        const scaleRow = ([key,label,description]) => { const options=FAIQ_FONT_SCALE_STEPS.map(step => `<option value="${step}" ${this._config[key] === step ? "selected" : ""}>${Math.round(step*100)} %</option>`).join(""); return `<div class="row scale-row"><div><label>${label}</label><span>${description}</span></div><select class="scale-select" data-scale-key="${key}">${options}</select></div>`; };
        this.shadowRoot.innerHTML = `<style>
          :host{display:block;padding:8px 0}.box{display:grid;gap:14px}.intro{padding:2px 2px 4px}.intro b{display:block;font-size:16px}.intro span{display:block;margin-top:4px;font-size:12px;line-height:1.45;color:var(--secondary-text-color)}.section{border:1px solid var(--divider-color);border-radius:12px;overflow:hidden}.section-head{padding:10px 12px;background:color-mix(in srgb,var(--primary-text-color) 4%,transparent)}.section-head b{font-size:11px;letter-spacing:.6px}.section-head span{display:block;font-size:11px;line-height:1.35;color:var(--secondary-text-color);margin-top:3px}.row{display:flex;align-items:center;justify-content:space-between;gap:14px;padding:11px 12px;border-top:1px solid var(--divider-color)}.row>div{min-width:0}.row label{display:block;font-weight:650;font-size:13px}.row span{display:block;margin-top:2px;font-size:11px;line-height:1.35;color:var(--secondary-text-color)}ha-switch{flex:0 0 auto}.variant-select{min-width:150px;padding:8px 10px;border-radius:9px;border:1px solid var(--divider-color);background:var(--card-background-color);color:var(--primary-text-color);font:inherit}.editor-note,.editor-error{padding:9px 12px;border-top:1px solid var(--divider-color);font-size:11px;line-height:1.4;color:var(--secondary-text-color)}.editor-error{color:var(--error-color)}.scale-select{min-width:96px;padding:8px 10px;border-radius:9px;border:1px solid var(--divider-color);background:var(--card-background-color);color:var(--primary-text-color);font:inherit;font-weight:750}.goal-tracker{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:6px;margin:10px 0 0}.goal-pill{display:flex;align-items:center;gap:5px;min-width:0;padding:7px 6px;border-radius:10px;background:rgba(127,127,127,.10);border:1px solid rgba(127,127,127,.18)}.goal-pill.reached{opacity:.82}.goal-pill.open{border-style:dashed}.goal-pill ha-icon{width:18px}.goal-pill span{display:flex;flex-direction:column;min-width:0}.goal-pill b{display:none}.goal-pill small{opacity:.86;font-size:10px;white-space:nowrap}.goal-pill .goal-impact-time{font-size:9px}.goal-impact-note{overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.goal-tracker.compact{margin:5px 0}.goal-tracker.compact .goal-pill{padding:4px 6px}
</style>
          <div class="box">
            <div class="intro"><b>FreshAirIQ Dashboard</b><span>Standardmäßig bleibt das vollständige Dashboard sichtbar. Hier kannst du Zusatzbereiche einzeln ausblenden. Wenn du alle Informationen und festen Bedienelemente deaktivierst, bleibt eine kompakte Ansicht mit der zentralen FreshAirIQ-Empfehlung.</span></div>
            <section class="section"><div class="section-head"><b>${this._t("editor.dashboard_design")}</b><span>${this._t("editor.dashboard_design_help")}</span></div><div class="row"><div><label>${this._t("editor.dashboard_style")}</label><span>${this._t("editor.dashboard_style_help")}</span></div><select id="dashboard-variant" class="variant-select"><option value="classic" ${this._config.dashboard_variant === "classic" ? "selected" : ""}>${this._t("editor.classic")}</option><option value="iq" ${this._config.dashboard_variant !== "classic" ? "selected" : ""}>FreshAirIQ IQ</option></select></div></section>
<section class="section"><div class="section-head"><b>EMPFEHLUNGEN</b><span>Wähle, welche Arten von raumspezifischen Empfehlungen diese Karte wiedergibt.</span></div>${recommendationFields.map(row).join("")}</section>
            <section class="section"><div class="section-head"><b>INFORMATIONEN DIESER KARTE</b><span>Diese Schalter ändern nur die Darstellung dieser einzelnen Dashboard-Karte. Globale FreshAirIQ-Einstellungen werden ausschließlich unter Geräte & Dienste → FreshAirIQ → Konfigurieren verwaltet.</span></div>${infoFields.map(row).join("")}</section>
            <section class="section"><div class="section-head"><b>DARSTELLUNG & KOMPAKTHEIT</b><span>Blende feste Bereiche und Schnellzugriffe aus, bis nur noch die Empfehlung übrig bleibt.</span></div>${layoutFields.map(row).join("")}</section>
            <section class="section"><div class="section-head"><b>${this._editorDE() ? "SCHRIFTGRÖSSEN DIESER KARTE" : "TEXT SIZES FOR THIS CARD"}</b><span>${this._editorDE() ? "Jeder Bereich lässt sich unabhängig in festen 10-%-Stufen von 80 bis 150 % einstellen. Die Einstellung gilt nur für diese Dashboard-Karte; 100 % entspricht exakt der bisherigen Größe." : "Set each area independently in fixed 10% steps from 80 to 150%. These settings apply only to this dashboard card; 100% exactly matches the previous size."}</span></div>${scaleFields.map(scaleRow).join("")}</section>
          </div>`;
        // 0.26.4.5: the editor had German-only sections; translate its text in English.
        if (!this._editorDE()) faiqLocalizeTree(this.shadowRoot);
        this.shadowRoot.getElementById("dashboard-variant")?.addEventListener("change", e => {
            const nextConfig = Object.assign({}, this._config, {dashboard_variant: e.target.value === "classic" ? "classic" : "iq"});
            this._pendingDashboardVariant = nextConfig.dashboard_variant;
            this._config = normalizeDashboardConfig(nextConfig);
            this._emitConfigChanged(this._config);
        });
        this.shadowRoot.querySelectorAll("ha-switch[data-key]").forEach(x => x.addEventListener("change", () => {
            const key = x.dataset.key;
            const nextConfig = Object.assign({}, this._config); nextConfig[key] = x.checked; this._config = normalizeDashboardConfig(nextConfig);
            this.dispatchEvent(new CustomEvent("config-changed", { detail: { config: this._config }, bubbles: true, composed: true }));
        }));
        this.shadowRoot.querySelectorAll("select[data-scale-key]").forEach(x => x.addEventListener("change", () => {
            const key=x.dataset.scaleKey; const nextConfig=Object.assign({},this._config); nextConfig[key]=Number(x.value); this._config=normalizeDashboardConfig(nextConfig); this._emitConfigChanged(this._config);
        }));
    }
}
if (!customElements.get("freshairiq-card-editor"))
    customElements.define("freshairiq-card-editor", FreshAirIQCardEditor);
FreshAirIQCard.getConfigElement = () => document.createElement("freshairiq-card-editor");
if (!customElements.get(FAIQ_CARD))
    customElements.define(FAIQ_CARD, FreshAirIQCard);
window.customCards = window.customCards || [];
if (!window.customCards.some(c => c.type === FAIQ_CARD))
    window.customCards.push({ type: FAIQ_CARD, name: "FreshAirIQ", description: "Intelligente Lüftungs-, Feuchte-, Energie- und Lernübersicht.", preview: true, documentationURL: "https://github.com/rupascha/freshairiq" });
class FreshAirIQDashboardStrategy extends HTMLElement {
    static getCreateSuggestions() { return { title: "FreshAirIQ", icon: "mdi:home-air-filter" }; }
    static async generate(config = {}) { return { title: config.title || "FreshAirIQ", views: [{ title: "FreshAirIQ", path: "freshairiq", icon: "mdi:home-air-filter", cards: [{ type: "custom:freshairiq-card" }] }] }; }
}
if (!customElements.get("ll-strategy-dashboard-freshairiq"))
    customElements.define("ll-strategy-dashboard-freshairiq", FreshAirIQDashboardStrategy);
window.customStrategies = window.customStrategies || [];
if (!window.customStrategies.some(s => s.type === FAIQ_STRATEGY && s.strategyType === "dashboard"))
    window.customStrategies.push({ type: FAIQ_STRATEGY, strategyType: "dashboard", name: "FreshAirIQ Dashboard", description: "Automatisch erzeugtes Live-Dashboard mit Detail-Popup, Räumen, Nachtprognose, Lernen und Energie." });
console.info(`FreshAirIQ frontend ${FAIQ_VERSION} loaded`);
