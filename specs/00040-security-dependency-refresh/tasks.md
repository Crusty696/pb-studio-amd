# Tasks

- [X] T001 [OBJ-1] {(FR-001)} Scan und Erreichbarkeit in `docs/security-review-2026-11-08.md` bewerten.
- [X] T002 [OBJ-1] {(FR-004)} `config/pytest-skip-allowlist.json` und `config/python-sca-exceptions.json` nach Backup aktualisieren; 37 Regressionen bestanden.
- [X] T003 [OBJ-1] {(FR-002)} `requirements-direct.txt` und `requirements.txt` minimal hashgebunden aktualisieren.
- [X] T004 [OBJ-1] {(FR-003)} Isolierte neue Umgebung aus `requirements.txt` installieren und verifizieren.
- [X] T005 [OBJ-1] {(TR-001)} SCA und Regressionen dokumentieren; `specs/00040-security-dependency-refresh/verification.md` erstellen.
- [ ] T006 [OBJ-1] {(OR-001)} Geprueften Stand committen/pushen, GitHub-Pflichtchecks pruefen und PR 34 mergen; `docs/security-review-2026-11-08.md` und Vault synchronisieren.
- [X] T007 [OBJ-1] {TR-001} CI-Ursache des optionalen madmom-Imports beheben, Python-Skip-Guard und Allowlist bis 2026-12-08 nachweisen; finale Checks und Merge fortsetzen.
- [X] T008 [OBJ-1] {TR-001} Recovery-Concurrency-Test an den isolierten LOCALAPPDATA-Control-Root anbinden; gezielter Windows-Test bestanden.
- [X] T009 [OBJ-1] {TR-001} Transiente Windows-Sharing-/Zugriffsfehler bei atomarem Recovery-JSON-Replace dreimal begrenzt wiederholen; Regression und Paralleltest bestanden.
- [X] T010 [OBJ-1] {TR-001} Vollsuite-Skipbericht auswerten und optionale BeatNet-DBN-Adaptertests eng am 	est_beatnet_compat.py-Modul bis 2026-12-08 freigeben; Regression hinzufuegen.
