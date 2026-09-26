# FreshAirIQ 0.20.2.2

Hotfix: Die rollierende Kurzzeitprognose ermittelt bei Horizonten über 5 Minuten zusätzlich den voraussichtlich effizienten Schließzeitpunkt. Dafür werden die bereits simulierten 5-Minuten-Zustände gegen den bestehenden Mindestertrag, Temperaturverlust, Effizienzgrenze, Mindestdauer und Maximaldauer bewertet. Die Echtzeit-Schließlogik bleibt unverändert und weiterhin maßgeblich.
