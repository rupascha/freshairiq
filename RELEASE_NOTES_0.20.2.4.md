# FreshAirIQ 0.20.2.4

Hotfix für die Live-Feuchtebilanz: FreshAirIQ erkennt nun konservativ, wenn ein geschlossener Raum während einer laufenden Hauslüftung wahrscheinlich passiv mitgelüftet wird. Voraussetzung ist nicht nur eine mögliche Luftverbindung, sondern eine messbare Änderung der absoluten Raumfeuchte in Richtung der aktuellen Lüftungsreferenz.

Passive Werte sind ausdrücklich Schätzungen (`≈`) und werden nicht zur Haus-Live-Bilanz addiert. Dadurch bleibt die bestehende aktive Lüftungsbilanz unverändert und Feuchte wird nicht doppelt gezählt.
