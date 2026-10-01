# Offene Punkte und Erkenntnisse – Stand 2026-10-01

Branch `codex/full-audit-remediation`, HEAD `729780d` (gepusht). Nur gelesen, nichts geändert.
Quellen: `tasks.md`, `qc-report.md`, `evidence/traceability.md`, alle `specs/*/tasks.md`,
CLAUDE.md §3, Obsidian `10_Projects/PB_studio/log.md`, `_wiki/learnings/*`,
Bestandsaufnahme der Claude-Code-Session vom 01.10. (03:03 UTC), eigene Gegenprüfung per `git grep`.

## A. Offene Tasks (Specs)

Nur Spec 00035 hat offene Tasks (alle anderen `specs/*/tasks.md`: 0 offen).

| Task | Inhalt | Blockiert durch |
|---|---|---|
| T003 | Audio: Mix-Grenzen in beatgematchten Mixen. Ø F1 0,783; Holdout `melodic_bm` 0,556 < 0,65 (5 richtig / 4 falsch / 4 verpasst, 56-s-Blenden) | Kein echter DJ-Mitschnitt mit unabhängigen Zeitmarken; oder Davids Entscheid, ob 0,556 bei langen Blenden akzeptabel ist |
| T014 | Caption-Treffsicherheit an menschlich bewerteten Clips | David bewertet 12 Kontaktbögen (`evidence/t014-caption-review-20260930/`). **Achtung:** Bögen stammen vom alten Prompt/Modell (vor `dd3ee87`/`a558db2`/`eaa90aa`) – sollten vorher neu erzeugt werden |
| T012 | `.completed` setzen | wartet auf T003 + T014 |

## B. Offene Befunde aus `traceability.md` (Code gefixt, nur Live-/GUI-Abnahme fehlt)

#3 Preview im GUI anhören · #6/#16 Caption-Semantik (= T014) · #8 Live-Modell-Retry · #11 Szenen-Anzeige im GUI ·
#17/#20/#21 WPF-Wiedergabe/Scrubbing · #22 Render-Abbruch live per SSE · #28 Validierungsanzeige ·
#32 Beatgrid-„suspect“ im GUI · #35/#36 Motion/BPM an echter Pacing-Abnahme.
Alles braucht einen sichtbaren GUI-Test durch David oder eine freigegebene GUI-Session.

## C. Nur David kann entscheiden

1. **Zwei verlorene Projekte** `gui_qc_20260925` (572 Medien) und `test` vom 28.09. (396 Medien): am 30.09. 00:54 durch Recovery-Rollback verloren. Vorhanden in Recovery-Generation `20260929T224820…` und `data/backups/t013_pre_20260930/`. Zurückspielen ja/nein? (Ursache behoben in `a380a13`.)
2. **T014** Kontaktbögen bewerten (am besten neu erzeugt mit aktuellem Prompt).
3. **T003** echten DJ-Mitschnitt mit Trackwechsel-Zeiten liefern (Vorlage `evidence/t003-referenz-vorlage.boundaries.txt`) oder 0,556 bei 56-s-Blenden akzeptieren.
4. **Sichtbarer GUI-Test** der WPF-Änderungen vom 01.10. (Projektübernahme per SSE, INGEST-Tab weg, Launcher-Wartezeit).
5. **T4.5 NSwag-Layer** behalten oder entfernen (Architekturwahl, seit 08-06 offen).
6. **Beat This!** (ONNX/DirectML, 97 % Tempo-Treffer) in die Pipeline verdrahten? Braucht Bar-Grid-Regularisierung; Produktentscheid.
7. **M-3 `_tempo_at_time`** bewusst unverdrahtet – bleibt so?
8. Alte Punkte: Hermes-Watchdog-Pause / T019-Canary (OBJ-76) – vermutlich durch Ein-Modell-Betrieb überholt, Bestätigung fehlt.

## D. Aufräumen / toter Code (ohne David machbar)

Gegengeprüft per `git grep` am 01.10.:

| Fund | Befund | Aktion |
|---|---|---|
| `src/pb_studio/ai/clap_pytorch.py` (306 Z.) | kein Importer; PyTorch-CLAP widerspricht DirectML-Regel; nur Wächtertest prüft *Abwesenheit* | löschen |
| `src/pb_studio/ai/moondream_pytorch.py` (419 Z.) | kein Importer | löschen |
| `src/pb_studio/audio/stem_runner.py` (56 Z.) | kein Aufrufer (auch nicht als Subprozess-String) | löschen |
| `src/pb_studio/core/compression.py` (20 Z.) | kein Importer (Treffer „compression“ sind andere Wörter) | löschen |
| `src/pb_studio/video/ollama_vision_wrapper.py` | deprecated Shim, nur von einem Test importiert | Shim + Testteil + Allowlist-Eintrag entfernen |
| `storage/embedding_repository.py`, `video/visual_curves.py` | nur Tests/Skripte | prüfen, eher behalten (Tests nutzen sie) |
| `schemas/health_schemas.py` | **wird** von `health_router.py` importiert | kein toter Code (Heuristik-Fehltreffer) |
| 76 `.pytest_tmp_*`-Ordner im Root | ignoriert, Müll | löschen |
| 2 Worktrees `Pb_studio_AMD_apb_audit`, `…-remediation` | Verzeichnisse fehlen („prunable“) | `git worktree prune` |
| `.venv-lock`, `.venv-pre-lock-20260830` | laut CLAUDE.md Wegwerfstände | löschen (nicht getrackt, groß) |
| 29 Berichte/Skripte im Repo-Root | historisch | nach `docs/archive/` verschieben |
| CLAUDE.md §4 „9 VMs / 9 Views“ | real 15/15 + 2 Dialoge | korrigieren |
| Skills `pb-master/module-map.md`, `dev-video.md`, `video-expertise` | nennen gelöschte Module / `moondream_pytorch` | korrigieren |

## E. Bereits erledigt (frühere Offen-Punkte, am 01.10. gegengeprüft)

- `"peak"` in `STRUCTURE_INTENSITY_MULTIPLIERS` – vorhanden (`advanced_pacing_engine.py:40`).
- `has_audio_embedding` wird nach Analyse gesetzt (`audio_router.py:1569`).
- Die zwei „Dauerroten“ (`test_audit_sdd_gate`, `test_t357` LHM-Backup) – Vollsuite am 01.10.: 1.979 passed / 0 failed.
- T013, Befund #2, weights.db, Recovery-Lock, Ein-Modell-Betrieb, Caption-Fixes.

## F. Wichtigste Erkenntnisse (Learnings)

1. **Nie ein zweites Backend / nicht-isoliertes pytest neben der App** – führte zum Rollback der DB (jetzt Prozess-Lock + conftest-Isolation).
2. **Backend/WPF nie hart beenden** – `RUNTIME_DIRTY` bleibt, nächster Start rollt zurück. Shutdown-Fertigsignal = `RUNTIME_DIRTY` weg.
3. **Dateiname-BPM bei Beatport-Tracks zu 40 % falsch** – alte Trefferquoten messen die Labels, nicht den Algorithmus.
4. **„Vorkommen ist nicht Durchleitung“** – Wächtertests müssen den Datenfluss prüfen, nicht nur Feldnamen.
5. **LM Studio**: `reasoning_effort="none"` nötig; `capabilities:["tool_use"]` muss gelesen werden; Vulkan-Runtime, nie ROCm.
6. **Cowork-Hintergrundjobs** mit `Invoke-CimMethod Win32_Process Create`, nicht `Start-Process`.
7. **Grünе Tests ≠ Funktion auf Hardware** – DirectML-Adapter in Tests gefakt.
8. **Erwartete Richtung vor der Messung aufschreiben** – fing drei eigene Fehler.

## G. Doku-/Brain-Drift

- Obsidian `10_Projects/PB_studio/` enthält nur noch `log.md` – `INDEX.md` fehlt (Regel 11 verlangt ihn).
- CLAUDE.md §3 > 120 Zeilen Ziel deutlich überschritten.
