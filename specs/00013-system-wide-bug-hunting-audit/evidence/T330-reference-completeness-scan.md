# T330 Referenz- und Vollständigkeitsscan

Status: CONFIRMED
Zeitfenster: 2026-07-29T08:25:00+02:00 bis 2026-07-29T10:18:00+02:00
Ausführung: statische Referenz-, Syntax-, XML-, JSON-, OpenAPI-, Link- und
Truncation-Prüfung; keine Funktions-, Regression-, Build-, Hardware-, GUI-,
FFmpeg- oder E2E-Tests

## Inventar

| Zone | Geprüfter Umfang |
|---|---:|
| Skripte (`.ps1`, `.bat`, `.py`) | 71 |
| Dokumente und Beispiele unter `docs/` | 41 |
| Architektur-Dokumente unter `docs/architecture/` | 5 |
| Backend-Schema-Dateien | 9 |
| WPF-Modell-Dateien | 18 |
| Aktive JSON-Konfigurationen/Snapshots | 3 |

Zusätzlich wurden `README.md`, `CLAUDE.md`, `LICENSES.md`,
`PBStudio.UI/README.md`, `PBStudio.UI/STRUCTURE.md`, die aktiven Runtime-
Wrapper und das vollständige Working-Tree-Diff-Inventar geprüft.

## Root Cause und Datenfluss

1. Historische One-off-Skripte waren weiterhin ausführbar und konnten
   ungebundene Prozesse beenden, LM-Studio-Runtime/Modelle außerhalb der
   Registry ändern oder Git-Refs, Staging und Remote direkt mutieren.
2. Einige aktuelle Dokumente und UI-Credits nannten noch SigLIP2/768,
   nichtkanonische Importpfade, individuelle Paketinstallation oder
   benutzerspezifische Repositorypfade.
3. Unerreichbarer Download-/Export-Dead-Code blieb trotz früher fail-closed
   Einstiegspunkte als irreführende Referenz und statischer Security-Sink
   erhalten.
4. Einzelne aktuelle Anleitungen verwiesen auf nicht vorhandene Dateien,
   falsche Testpfad-Großschreibung oder nicht existierende pytest-Optionen.

Caller-, Nebenwirkungs- und Architekturprüfung bestätigten:

- Start-/Stress-/SSE-Wrapper laufen über den hashgebundenen Runtime-Vertrag
  und owner-identifizierte Prozesse; Stop betrifft nur PID, Executable und
  Startzeit des eigenen Prozesses.
- `/shutdown` und `/brain/reset` verlangen in OpenAPI und Backend denselben
  Owner-Capability-Header sowie `403`/`503`.
- Der aktive FAISS-/SigLIP-SO400M-Vertrag ist 1152-dimensional.
- `EmbeddingRepository.VIDEO_DIM=768` gehört zu einem isolierten sqlite-vec-
  Legacy-Store ohne Produktions-Caller. Eine Änderung wäre eine nicht
  freigegebene Datenmigration; der Vertrag bleibt deshalb unverändert und
  wird ausdrücklich vom aktiven SigLIP-Store getrennt.
- `config.json` `ai.provider=auto` wählt den LLM-Anbieter und ist kein
  ONNX-Provider-Fallback.

## Reparaturen

- Aktuelle Dokumente, Beispiele, Lizenz-Credits und Settings-UI auf Python
  3.11, NumPy 1.26.4, SigLIP SO400M/1152, ONNX Runtime DirectML, kanonische
  Importe, `Tests/` und die manifestierte FFmpeg-Runtime synchronisiert.
- Fehlenden Pacing-Dokumentlink auf die vorhandene Modul-Dokumentation
  umgebogen; nicht existente `--audio`-pytest-Anweisung entfernt.
- Aktive Modell-Download-/Export- und provenance-lose Standalone-Verifier auf
  minimale fail-closed Einstiegspunkte mit Exitcode `2` reduziert.
- Veraltete Commit-/Push-/Ref-/Runtime-/Vault-One-offs fail-closed gesperrt;
  D07/D08 bleiben die einzigen Veröffentlichungsverträge.
- Diagnose-only-Skripte auf repository-relative Pfade umgestellt.
- `brain_sync.py` nutzt Repository-/Vault-Pfade aus Skriptpfad und
  Benutzerprofil und behauptet keine hardcodierte Testzahl mehr.
- OpenAPI-Snapshot, Backend-Schema und WPF-Caller/Modelle statisch
  gegengeprüft; keine öffentliche Vertragsdrift gefunden.
- Versionszeilen in `requirements.txt` blieben unverändert. Es wurde keine
  Dependency und kein Lockfile geändert.

## Statische Evidenz

| Gate | Ergebnis |
|---|---|
| PowerShell-Parser | CONFIRMED PASS, 60 Dateien |
| Python-`compile()` ohne Artefaktwrites | CONFIRMED PASS, 346 Dateien |
| JSON-Parse | CONFIRMED PASS, 3 Dateien |
| XAML/XML-Parse | CONFIRMED PASS, 19 Dateien |
| Markdown-Fences und lokale Links | CONFIRMED PASS, 35 aktive Dateien / 5 Links |
| Nonempty-/NUL-Truncation-Sweep | CONFIRMED PASS, 394 Dateien |
| `app.openapi()` gegen Snapshot | CONFIRMED PASS |
| Owner-Header-/403-/503-Vertrag | CONFIRMED PASS, 2 Routen |
| Runtime-Manifest, Python- und FFmpeg-/ffprobe-Hashvertrag | CONFIRMED PASS |
| `git diff --check` | CONFIRMED PASS |
| Hart codierte Repo-/Session-Pfade in aktiven Skripten | CONFIRMED abwesend |
| Direkte aktive Push-/Reset-/Rebase-/Image-Kill-Wrapper | CONFIRMED abwesend |

Die OpenAPI-Reflexion importierte Module statisch, startete aber weder Server
noch Lifespan. Die BeatNet-Warnung wegen fehlendem `madmom` war erwarteter
Import-Fallback und kein Testresultat.

## Klassifikation und Gate

- CONFIRMED: Alle T330-Zonen wurden inventarisiert und statisch geprüft.
- CONFIRMED: Keine offene veraltete aktive Runtime-, DTO-, Modell-,
  Dokumentations- oder Konfigurationsbehauptung verbleibt.
- DECIDED: Ausdrücklich als `HISTORISCH`, `SUPERSEDED`, `Entwurf` oder
  Negativbeispiel markierte Texte bleiben Archiv-/Entscheidungsevidenz.
- DECIDED: Keine Dependency-/Lockfile-Änderung und keine Legacy-store-
  Migration ohne neue Freigabe.
- OPEN: Dynamische Wirksamkeit, Build und Regressionen beginnen erst in T332.
- BLOCKED: none.
