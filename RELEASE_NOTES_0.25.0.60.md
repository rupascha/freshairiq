# FreshAirIQ 0.25.0.60 — Release Infrastructure Hotfix

Hotfix auf Basis von v0.25.0.59. Keine Änderung an Lüftungs-, Lern-, Empfehlungs- oder Dashboard-Fachlogik.

## Behoben
- Regressionstests auf den aktuellen Release-Stand synchronisiert, damit ein Versionswechsel nicht fälschlich die Qualitätsprüfung rot schaltet.
- Die verpflichtenden GitHub-Workflows `quality.yml`, `validate.yml` und `release.yml` sind wieder Bestandteil des Release-Projekts.
- GitHub/HACS-Gate verlangt nun ausdrücklich alle drei Workflows.
- Release-ZIPs werden weiterhin fail-closed gebaut und vor sowie nach dem Packen geprüft.
- Cache-, Bytecode-, Coverage- und Entwicklungsartefakte bleiben aus dem Release ausgeschlossen.

## Schutz
- Release wird erst nach erfolgreichem wiederverwendbarem Quality-Workflow erzeugt.
- Der finale ZIP-Upload wird nochmals mit `github_release_gate.py` validiert.
- Versionen in Manifest, Python, Frontend, Quality Policy und package.json werden gegeneinander geprüft.
