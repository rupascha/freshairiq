# FreshAirIQ 0.25.2.22

## Hotfix

- Verhindert widersprüchliche Live-Anweisungen, bei denen derselbe einzelne Kontakt gleichzeitig offen bleiben und geschlossen werden sollte.
- Eine Öffnung, die als nutzbarer Lüftungs-/Kühlpfad klassifiziert ist, wird im selben aktiven Plan nicht mehr zugleich als zu schließender schädlicher Pfad verwendet.
- Ergänzt den Gebäudetyp `Dachgeschosswohnung` / `Attic apartment`; `Wohnung` / `Apartment` war bereits vorhanden und bleibt unverändert.
- Dachgeschosswohnungen verwenden zunächst denselben konservativen Nacht-Hintergrundfaktor wie Wohnungen; die getrennte Kategorie ermöglicht spätere lernbasierte Segmentierung ohne die bestehende Physik zu verändern.
