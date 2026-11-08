# PB Studio - Project-Brain-Historie (aus CLAUDE.md ausgelagert 2026-10-17)

Nicht automatisch laden. Aktueller Stand: CHANGELOG.md, specs/, Obsidian-Vault.

## 3. 🧠 PROJECT BRAIN & CURRENT STATUS
- **T002 CPU-Probe 2026-10-13:** 9/9 ausgewählte Regressionstestmedien bestanden begrenzte PB-Pfad-/Metadaten-/Frame-/Audiochunk-Funktionen; vollständige Original-SHA-256 nachher identisch. A03 M4A über Librosa/audioread-Fallback mit Deprecation-Warnung. Kein vollständiger App-Import, keine Native-Qualitätsbaseline, kein unabhängiger Holdout, keine GPU/Generierung. Beleg: specs/00037-comfyui-control-center/t002-cpu-check-2026-10-13/cpu-check-report.md. T002 bleibt offen.
- **Latest Wave B 2026-10-13 (Codex):** T005/T006 library contracts and scoped T045 delivered: 109 tests +47 subtests, 163 files compiled; evidence specs/00037-comfyui-control-center/wave-b/qc-report.md. No live ComfyUI/GPU/generation/migration/install/app startup. No qualified profile or automatic product registry. Next: T002 authorized references/measurements; T007 requires separately bounded pilot authorization. Earlier Wave-A-only next-step text is historical.
- **Latest 2026-10-13 (Codex):** Spec00037 Wave A T001/T003/T004 delivered; scoped T045 passed (53 tests +20 subtests, one GET system_stats). Disabled read-only discovery library; no WPF/startup/GPU/generation/migration/install integration. Evidence: specs/00037-comfyui-control-center/wave-a/qc-report.md. Remaining master packages open; user permits external ComfyUI ROCm, PB DirectML unchanged.
- **Next for Spec00037:** T002 media authorization/measurement preparation and separately authorized T005 onward; no automatic continuation beyond Wave A.
- **Latest 2026-10-03 (Codex):** Spec 00036 adds manual checklist and live diagnostic recorder (`LOG-AUFZEICHNUNG.bat`, `logs/sessions/manual_*.log`); received SSE events logged before UI throttling, quoted JSON secret redaction fixed. Python focus 16 passed, native 86 passed; deployed WPF Release 0/0. No new live GUI acceptance; user stopped automation and will test manually. Spec 00035 remains `.completed` without `.qc-passed`.
- **Next Task (current):** Before manual restart, inspect real recovery state: after user closed app, no WPF/listener remained but `%LOCALAPPDATA%\PB_Studio\recovery-control\v1\RUNTIME_DIRTY` persisted; cause unverified, no reset/restart attempted. Approved populated project is nested `C:\Users\david\Documents\PBStudio\t013_psy_20260930\t013_psy_20260930` (1 audio, 61 videos, 2889 cuts); some original E: source paths are missing after drive reorganization. Recorder/checklist delivered; manual runtime capture and Spec 00035 GUI gates remain open.
- **Date:** 2026-10-01 (Claude/Cowork später: WPF-Reste committet, T003-Grenzen per optimaler Zerlegung; davor Claude: Recovery-Lock, Ein-Modell-Betrieb, Caption-Fixes; davor 2026-09-30 Spec 00035: T013 + Befund #2 geschlossen, Launcher-Start-Timeout 90→300 s, weights.db geprüft ok; offen T003 Referenzmarken + T014 menschliche Caption-Bewertung, daher kein `.completed`)
- **Current Status (2026-09-29, latest isolated run):** T016 echter 337.176-s AMF-Export: -1.58 dBTP, 10,115/10,115 Frames, vollständiger Decode. T017 atomisches, redigiertes Segmentmanifest mit Hashbindung, konsistenten Mikrosekunden-Grenzen und SHA-256 der exakten Concat-Eingabeliste im Run-Beleg. Aktuelle isolierte Python-Vollsuite: 1,958 passed/13 skipped/0 failed/35 warnings in 1,766.58 s; JUnit: `%TEMP%\pb00035-health-full-16ad412326064e45bfb5982c31abf239\pytest-results.xml`. Finding-54 Dispositionsregression separat 1/1. Separate echte AMF-Integration 899/899 Frames, −11.72 dBTP, unabhängiger Full-Decode; physische RX 7800 XT/DirectML/LHM-Probe 1/1. C# 80/80; WPF Release-Build 0 Warnungen/Fehler. Dies belegt keine interaktive GUI-/Projekt-Wiederöffnung.
- **T003-Fixes (2026-09-30, später):** gegen rekordbox + 3 konstruierte Mixe gemessen und behoben — Tonart 25→32/40 (`MINOR_PRIOR` 0,075), Beat-Phase-Median 0,37→1,00 (Sub-Bass-Halbschlag + 1-Hop-Anker), Mix-Grenzen F1 0,375→0,842 / 0,364→1,000 / Holdout 0,186→0,556. Grenzerkennung langer Mixe jetzt Chroma-Rekurrenz + genaue Tempostufe, ~4–5× langsamer. Beleg `specs/00035-full-audit-remediation/evidence/t003-fixes-20260930.md`. T003 bleibt offen (beatgematchte Mixe < 0,65).
- **Claude-Session 2026-09-30/10-01 (HEAD `eaa90aa`, gepusht):**
  - **Recovery-Rollbacks aufgeklärt + behoben (`a380a13`):** `ensure_recovery_ready` lief beim Import von `backend.main` ohne Prozess-Sperre. Ein zweites Backend (zweites Fenster, Driver, pytest gegen das echte Verzeichnis) hielt das `RUNTIME_DIRTY` des laufenden für einen Absturz, begann einen Restore und hinterließ ein APPLYING-Journal; der nächste Start rollte zurück. So am 2026-09-30 00:54 **DB auf 2026-09-24 zurückgesetzt**: verloren `gui_qc_20260925` (572 Media) und `test` vom 09-28 (396 Media). Noch vorhanden in Generation `20260929T224820…` und `data/backups/t013_pre_20260930/` — **2026-10-01 entschieden: nicht zurückspielen (Altlasten); Sicherungen bleiben, manuelles Löschen später optional.** Jetzt: exklusiver Lock `…\recovery-control\v1.backend.lock`, live belegt (zweites Backend abgewiesen, Journal unverändert); `Tests/conftest.py` setzt `LOCALAPPDATA` auf Temp.
  - **Ein-Modell-Betrieb (`8a91eed`, `a558db2`):** alle LLM-Aufgaben auf LM Studio `qwen3.5-9b` (Vulkan). `LMStudioClient` sendet `reasoning_effort="none"` (sonst 400–600 Denk-Tokens, leere Tags; `enable_thinking` wirkt in LM Studio nicht). LM-Studio-`capabilities:["tool_use"]` wurde nie gelesen → Chat fiel auf Ollama bonsai-27b; live jetzt qwen3.5-9b mit Tool-Calls, ~3 s. `qwen2.5-vl` kann keine Tool-Calls. MODELLE-Tab filtert ungeeignete Modelle (live 9 sichtbar/19 ausgeblendet, Schalter „Alle anzeigen").
  - **Caption-Tags (`dd3ee87`, `a558db2`, `eaa90aa`):** nur Frame 1 zählte (first-come + `[:10]`); Prompt ohne Figuren; Parser zerhackte Kommalisten mit einem langen Eintrag; Dubletten; `/video/clips` zeigte Tags erst nach Reopen. Alles behoben, live belegt. Bekannt offen: Wortreihenfolge-Dubletten („arme ausgestreckt"/„ausgestreckte arme"). **T014-Kontaktbögen stammen vom alten Prompt/Modell.**
  - **Weitere Fixes:** Clips ohne Tonspur nicht mehr „TEILANALYSE" (`fc25f21`); neutrales Struktur-Label `section` nicht mehr als `transition` ins Hirn (`bf596c3`). Zurückgezogen: „Hirn-Achsen nur Kick" (Trigger-Achsen gelten pro Cut-Trigger).
  - Beleg: `specs/00035-full-audit-remediation/evidence/t013-api-workflow-20260930.md`. Verifiziert: gezielte Python-Bündel (448/82/173/33 passed), C# 83/83, WPF Release 0/0. **Keine Vollsuite nach diesen Commits.**
- **Cowork-Session 2026-10-01 (Branch `codex/full-audit-remediation`):**
  - WPF-Reste committet: Projektübernahme vom Backend per SSE `project_changed` (`99dd5eb`), INGEST-Tab entfernt (`bf99e6a`), Launcher wartet bis 180 s auf den Recovery-Snapshot (`6204940`). Release 0/0, C# 85/85. GUI nicht sichtbar geprüft.
  - **T003 Mix-Grenzen neu:** `SubtrackDetector._optimal_partition` (Kernel-k-means-Zerlegung der Chroma-Ähnlichkeit, Preis 18, Abschnitte 2–15 min) + Tempostufe. Beatgematchte Referenzmixe F1-Mittel 0,538 → 0,783; Holdouts 0,889 / 0,556 (56-s-Blenden). `estimate_beat_grid` bitgleich, 3,9× schneller; Grenzerkennung ~2,4× schneller (≈0,8 min/h unter Last). Tonart/BPM/Beatgrid an 40 rekordbox-Titeln feldgleich. Beleg `evidence/t003-boundaries-20261001.md`, Lab `scripts/dev/t003_boundary_lab.py`.
  - **Nachmittags:** Quality-Gate entsperrt (Skip-Ausnahmen waren am 09-30 abgelaufen, `1e28098`), toter Code + Ollama-Shim weg (`2fc7029`), Altberichte nach `docs/archive/` (`49d1a24`), Caption-Wortreihenfolge-Dubletten (`58b8bca`), T003-melodic-Analyse (`ab6e6f3`, offen). Vollsuite 1.979/9/0, C# 85/85. Offen-Liste: `evidence/offene-punkte-20261001.md`.
  - **Abends:** T014 abgenommen (Davids „Ja“ zu 6/12 Bögen, `ee94f6f`), Tag-Merge-Fix (`2a1071b`), T003 abgenommen per Blendenfenster-Regel (Davids Entscheid; F1 7 Mixe Mittel 0,901/Min 0,737), T012 `.completed` gesetzt. **Spec 00035 Implementierung abgeschlossen; kein `.qc-passed`.** Offen bleiben GUI-/Live-Abnahmen laut Traceability.
  - Hintergrundjobs aus Cowork: `Start-Process` wird beim Ende der Shell mitbeendet (pytest hing an gebrochener Pipe) — `Invoke-CimMethod Win32_Process Create` verwenden.
- **Next Task (2026-09-30):** David bewertet 12 Caption-Kontaktbögen (`evidence/t014-caption-review-20260930/`) → T014; für T003 optional echte Trackwechsel-Zeiten eines DJ-Mitschnitts (Vorlage `evidence/t003-referenz-vorlage.boundaries.txt`) oder Entscheid, ob 0,556 im beatgematchten Fall akzeptabel ist. Danach T012 `.completed`.
- **Next Task (älter):** T003/#34 bleibt ohne unabhängige Zeitcodes/Labels für Mix-Grenzen und Tonart offen. Aktuelle Provider-APIs antworten, aber Ollama und LM Studio melden jeweils 0 geladene Modelle; Ollama-Runtime hatte ROCm ausgewählt und ist damit nicht für DirectML-only-Inferenz freigegeben. T013 GUI/Projekt-Wiederöffnen wartet auf PB Studio-Handover; T014 braucht policy-konforme Inferenz plus menschlich geprüfte Labels. #2 historische Evidenz bleibt nicht wiederherstellbar. Kein `.completed`/`.qc-passed`; kein Release-Claim.
- **Historischer Stand 2026-08-31 — Remote-SHA `d499b58`, gepusht.**
  Audit des Beat-/Tempo-Pfads: **11 von 12 Befunden behoben**, jeder mit
  Regressionstest und ausgeführter Gegenprobe (Fix zurückgerollt, Test fällt).
  - **C-1** Energy-Trigger lagen bei exakt doppelter Zeit — die gecachte
    Energiekurve entsteht bei `analysis_sr` (Default 44100), die Engine rechnete
    mit `sr=22050` zurück. An echter Datei: Dauer 544,2 s, wahre Peak-Zeit
    327,98 s, gemeldet 655,96 s, also jenseits des Dateiendes.
  - **H-3 war größer als gemeldet: VIER divergierende Parametersätze**, nicht
    drei. `_extract_drum_triggers_from_stem` lief ohne `n_mels`, also mit dem
    librosa-Default von 128 Filtern auf ~14 Bins im Kick-Band. Dabei zwei
    weitere Divergenzen: Router und Streaming rechneten für 20–150 Hz,
    übergaben aber nur `fmax` ohne `fmin`; das HiHat-Band hing an der
    Abtastrate (Router 5000–22050 Hz, Engine 5000–11025 Hz). Alle vier Pfade
    beziehen die Parameter jetzt aus `src/pb_studio/audio/band_params.py`.
  - **Außerhalb der Auditliste:** die Streaming-Dedup verglich gegen das letzte
    statt erste Gruppenelement — aus einer durchgehenden 16tel-HiHat wurde
    **genau ein** Zeitpunkt, bei jedem Tempo.
  - **M-3 bewusst nicht verdrahtet**, sondern dokumentiert: `_tempo_at_time`
    hat keinen produktiven Aufrufer, und eine Verdrahtung im `generate()`-Pfad
    wäre eine Verschlechterung. Produktentscheidung, nicht still erfunden.
- **Beatgrid ist verdrahtet** (`src/pb_studio/audio/beat_grid.py`): Schema →
  Router → Merge-Whitelist → AppState → `_load_index` → OpenAPI → C#-Record →
  ViewModel → XAML-Binding, Wächter in `Tests/test_beat_grid_wiring.py`.
  Der erste Live-Lauf lieferte `beat_grid: {}`, obwohl das Log das Ergebnis
  zeigte — `_AUDIO_STAGE_RESULT_FIELDS["beats"]` filterte es nach der
  Berechnung wieder heraus. **Der erste Wächter bemerkte das nicht, weil er nur
  prüfte, ob der Feldname vorkommt. Vorkommen ist nicht Durchleitung.**
  Es **ersetzt bewusst nichts** — `beats` und `bpm` bleiben unverändert; bei
  48,8 % Tempo-Trefferquote gegen 37,0 % wäre alles andere unverantwortlich.
- **DJ-Mixe bekommen mehrere Grid-Abschnitte** (`beat_grid_segments.py`):
  Kontrast an sechs echten Mixen **1,12–1,75 → 2,15–2,85**. Der Router benutzt
  `segment_beat_grids_from_file`, die fensterweise liest — die Array-Variante
  hätte bei einem 188-Minuten-Mix 995 MB angefordert, also genau H-5.
- **Drei eigene Behauptungen an Messungen widerlegt:**
  1. Die **0,75-Kick-Schwelle** meldete 125 von 127 Fenstern als `suspect`,
     darunter 96 % der korrekt erkannten. Ursache: systematischer Versatz von
     genau einer Hop-Länge (+23,2 ms), nur 4 % der Kicks liegen innerhalb
     ±23 ms eines Beats. Die Gegenprobe entscheidet nicht mehr über den Status.
  2. Die **33-%-Tempostreuung in Mixen** ist ein Vielfachfehler des Schätzers,
     keine echte Tempoänderung: 97,2 % liegen auf einfachen Vielfachen des
     Datei-Medians, nach Faltung bleiben 0,1 %. Die Mixe sind tempostabil.
  3. **`tempogram_ratio`** als Vielfachkorrektur repariert 0 Fälle und macht
     4 kaputt (48,8 % → 45,7 %). Verworfen, nicht eingebaut.
- **Die BPM-Attraktoren sind erklärt:** die drei häufigsten Werte des alten
  Pfads (143,55 / 136,00 / 92,29) sind exakt die Tempogramm-Frequenzen
  `60·sr/hop / k` für k = 18, 19, 28. Im EDM-Bereich ist dieses Gitter
  6,8–7,6 BPM grob; ein 126-BPM-Track ist damit **prinzipiell** nicht treffbar.
- **Prozesslehre dieser Sitzung:** die erwartete Richtung *vor* der Messung
  aufschreiben. Sie hat drei eigene Fehler gefangen, darunter einen Kommentar,
  der etwas behauptete, das die nächste Zeile nicht einlöste. Und einmal wurde
  gegen eine **erfundene** Zahl gemessen („50 Abschnitte sind zu viele", aus
  geschätzten 15–25 Tracks pro Mix) — es gibt keine Annotation dieser Mixe.
- **Messbelege:** `docs/measurements/2026-08-30-beatgrid-machbarkeit.md`,
  `2026-08-31-kick-gegenprobe-befund.md`, `2026-08-31-mix-segmentierung.md`.
  Musiktheorie-Grundlagen: `docs/musiktheorie/GRUNDLAGEN.md`.
- **⚠️ DIE BPM IN DEN BEATPORT-DATEINAMEN IST BEI 40 % DER TRACKS FALSCH.**
  Belegt über einen unabhängigen Schiedsrichter (Fourier-Tempogramm ohne Prior
  und ohne k-quantisiertes Kandidatengitter, teilt sich mit keinem der
  Verfahren etwas), 35 Tracks:
  **Beat This! 34/35 = 97,1 % · Dateiname-BPM 21/35 = 60,0 %.**
  Beispiele: Label 122 → real 137,8; Label 100 → real 140,3; Label 92 → real
  137,2. Zwei Dateien desselben Stücks tragen 140 und 103.
  **Konsequenz: alle Trefferquoten dieser Sitzung (35 % / 48,8 % / 55 %) sind
  gegen eine Referenz gemessen, die selbst nur zu 60 % stimmt.** Sie messen
  überwiegend die Labels, nicht den Algorithmus. Künftige Tempo-Messungen
  brauchen entweder GiantSteps oder den Fourier-Schiedsrichter als Referenz.
  Rohdaten: `docs/measurements/beat_this_onnx_arbiter.json`.
- **Beat This! (ISMIR 2024) läuft auf dieser Maschine — VERIFIZIERT.**
  ONNX, MIT-Lizenz (`musetric/beat-this-onnx`, alle drei SHA-256 gegen das
  Manifest geprüft), **keine neue Abhängigkeit**. Node-Placement per
  ORT-Profiling belegt: 2568 Knoten auf `DmlExecutionProvider` gegen 940 auf
  CPU — 96 % der Rechenzeit wirklich auf der GPU, kein stiller Fallback.
  0,41 s je 120-s-Fenster gegen 4,75 s auf CPU. Modell in `models/beat_this/`
  (83,4 MB, gitignoriert). **Downbeats:** 29/35 Tracks mit Median-Taktlänge
  exakt 4,00 Beats, mittlere Abweichung von ganzzahligem Beat-Abstand 0,024 —
  eine andere Größenordnung als die verworfene Ableitung (9 von 520).
  Noch nicht verdrahtet; braucht Bar-Grid-Regularisierung (nur 6/35 haben
  ≥ 90 % der Downbeat-Abstände als Vielfaches von 4).
  Werkzeug: `scripts/dev/measure_neural_beat_tracker.py`.
- **`TEMPO_RANGE` ist genrespezifisch und war zu weit.** Nutzerangabe „meine
  Mixe sind nie schneller als 145 BPM", gemessen an 20 Tracks: 50–220 BPM
  → 35,0 %, 70–145 → 50,0 %, **100–150 → 55,0 %**. Ein weiter Suchraum liefert
  mehr Kandidaten, und der Kontrast bevorzugt darunter systematisch das
  langsamere Raster. Default jetzt (100, 150); `estimate_beat_grid` nimmt
  `tempo_range` als Parameter — für DnB (~174) oder langsamen HipHop (~85)
  muss er gesetzt werden.
- **Zwei WPF-Defekte an der laufenden App gefunden und behoben:**
  1. **Absturz beim Analysieren.** `CaptureOperationContext()` wirft bei
     instabilem Projektkontext; elf Aufrufstellen fingen das ab, **vier
     nicht** — ausgerechnet die, die lange Arbeit starten (beide
     Analysepfade, Stem-Separation, Cut-Liste). Unbehandelte UI-Exception,
     Fenster weg. Wächter: `Tests/test_wpf_operation_context_guarded.py`.
  2. **Backend-Start-Timeout 30 s, Bedarf 60 s.** Das Backend kontaktiert beim
     Start Ollama und LM Studio und läuft in deren Timeouts, wenn sie nicht
     laufen. Die App gab auf und räumte ein funktionierendes Backend ab.
     Jetzt 120 s.
- **Die Beatgrid-Anzeige ist im laufenden GUI belegt** (UIA-Auslesung,
  Screenshot, Gegenprobe vorher leer): `docs/evidence/beatgrid-gui-final/`.
  Sie heißt „Zweitschätzung", ist optisch untergeordnet und nennt Abweichungen
  vom angezeigten Tempo samt Verdacht auf Oktavfehler — zwei gleichrangige
  Tempi ohne Erklärung waren schlechter als eines.
  Prüfwerkzeug: `scripts/dev/verify_beatgrid_in_gui.py` (prüft auf **Änderung**
  des Textes, nicht nur auf Anwesenheit — die erste Fassung hätte einen
  stehengebliebenen alten Wert als Erfolg gemeldet).
- **⚠️ `Stop-Process -Force` gilt auch für die WPF, nicht nur fürs Backend.**
  In dieser Sitzung selbst ausgelöst: die App hart beendet → ihr
  Backend-Kindprozess starb mit → `RUNTIME_DIRTY` blieb stehen → der nächste
  Start stellte die Recovery-Generation von 02:58 wieder her. Analysewerte
  zurückgesetzt, DB-Zählstände unbeschädigt. App immer über
  `CloseMainWindow()`, Backend über `POST /shutdown` und dann auf das
  **Verschwinden von `RUNTIME_DIRTY`** warten (gemessen 36 s).
- **Historischer Stand:** 2026-08-29 (Funktionsaudit + Reparaturplan 01)
- **Audit 2026-08-29:** ~243 Befunde (18 CRITICAL, 61 HIGH, 74 MEDIUM).
  Bericht: `docs/archive/FUNKTIONSAUDIT_2026-08-29.md`. Kernbefund: die Ketten brechen an den
  Übergabestellen zwischen Domänen, nicht innerhalb — und die Tests sind
  durchgehend domänenintern.
  Der uncommittete Stand (892 Z., maschinell via `patch.py` erzeugt) ist NICHT
  committfähig und liegt weiterhin unangetastet im Arbeitsbaum (28 Einträge).
  **Korrektur zur ersten Fassung:** die gemeldeten „10 failed / 2 errors" waren
  ein Messartefakt aus sieben parallel laufenden Agenten mit geteiltem
  `basetemp`. Sequenziell: 7 failed / 1497 passed / 0 errors, alle 7 zuordenbar,
  5 davon aus dem `patch.py`-Stand. `--basetemp` wird NICHT vom Produktionscode
  gelöscht und darf NICHT aus `pytest.ini` entfernt werden — ohne die Option legt
  pytest einen `pytest-current`-Symlink an, der auf dieser Maschine jeden Lauf mit
  `PermissionError: [WinError 5]` bricht. Bestehen bleibt: der DirectML-Adapter
  ist testseitig gefakt, die Owner-Capability global gepatcht — „grün" beweist
  keine Funktion auf der Hardware.
- **Reparaturplan 01 (Datenverlust) — abgeschlossen, 8 lokale Commits:**
  `Tests/`-Wächter gegen doppelte Dict-Schlüssel; drei verschluckte
  Persistenzfehler laut gemacht (fail-closed Unbind über neues
  `BrainService.force_unbind_project_state`, zwei atexit-Save-Handler melden und
  hinterlassen einen in `_load_index` gelesenen Dirty-Marker); Timeline wird vor
  Close und Projektwechsel persistiert (`persist_timeline_for_context`); Save-Pfad
  auf eindeutige versteckte Stage-Namen gehärtet.
  Vollsuite danach: **7 failed / 1522 passed / 13 skipped / 0 errors** (31:12) —
  dieselben 7 Fehler wie vorher, keine neuen; +25 vollständig zugeordnet.
  **Prozesslehre dieser Session:** von vier geplanten Tasks war genau einer
  fachlich korrekt. Zwei hätten still nichts bewirkt, einer behob gar keinen
  erreichbaren Bug. Zwei Fixes hätten neue Defekte erzeugt (Verbindungsleck,
  Reopen-Datenverlust). Ein eigener Commit (`d1724f6`) hat eine fremde
  Arbeitsbaum-Änderung mitgenommen und dabei einen Fix behauptet, der keiner war
  — revertiert in `1d9a8d4`, Message bewusst nicht umgeschrieben.
- **Reparaturplan 03 + `patch.py`-Stand — abgeschlossen und gepusht.**
  Remote-SHA `0a7768c9db3d8131fed8ecb7db4e26b89cd1691b`, neun Commits.
  Vollsuite danach: **2 failed / 1548 passed / 13 skipped / 0 errors** (26:46) —
  von sieben Fehlern auf zwei. Die fünf verschwundenen sind exakt die, die der
  Audit dem `patch.py`-Stand zuschrieb; damit ist jene Zuordnung bestätigt.
  **Die zwei verbleibenden Fehler sind beide Infrastruktur, kein Produktdefekt:**
  `test_audit_sdd_gate` prüft, ob `.qc-passed` für HEAD aktuell ist — der Marker
  pinnt `commit_sha 20792e75`, also ist der Test nach *jedem* Commit rot und
  trägt im Arbeitsalltag kein Signal. `test_t357::test_lhm_backup_restore_copy…`
  löst über eine Evidence-Datei den Ordner
  `tools/LibreHardwareMonitor.backup-20260730T0515+0200` auf; der fällt unter
  `.gitignore:62 /tools/*`, war nie getrackt und existiert nicht mehr — der Test
  kann in **keinem** Clone je grün werden.
- **Der `patch.py`-Arbeitsstand war keine einheitliche Arbeit.** Zwei Schichten,
  am Kommentarstil trennbar: eine handgeschriebene (verdrahtet, begründet,
  getestet) und die maschinelle. **Beide roten Guard-Tests stammten aus der
  maschinellen.** Übernommen: SDK-Pin (HEAD war mit `9.0.316` +
  `rollForward: disable` auf dieser Maschine **gar nicht baubar**),
  Tonart-Score-Vorzeichenfix, `audio_key`-Semantik, FR-362-Degrade,
  Struktur-Labels. Verworfen mit Beleg: drei `*_receipt`-Feldergruppen ohne
  Produzent *und* Konsument, `rejected_clips` samt einer C#-Reflection auf
  nicht existierende Properties, ein Validator ohne Aufrufer, drei
  `cap.grab()`-Schleifen (eine davon ~142.000 Aufrufe statt drei Seeks je Clip),
  ein Teil-Revert des bewussten Fixes `c6b8cd0`.
- **Live verifiziert am laufenden Backend** (`launch.ps1 -BackendOnly`,
  `/health` → `gpu_available: true`): Projekt `12345` zweimal geöffnet, beide
  Male HTTP 200, `/project/info` vorher und nachher byteidentisch, Logzeile
  `Projekt ist bereits geoeffnet, Reopen bleibt folgenlos` (`project_router.py:701`).
  **Grenze dieses Belegs, ausdrücklich:** er zeigt, dass der Reopen folgenlos
  bleibt — er zeigt **nicht**, dass eine ungespeicherte Timeline erhalten
  bliebe, denn das Projekt hat keine (`has_timeline: false`). Dafür wäre ein
  echter Pacing-Lauf nötig. DB vor und nach allem: 6 Projekte, 711 Medien,
  `integrity_check: ok`.
- **Zwei Korrekturen an diesem Dokument selbst:**
  - Die C-01-Beschreibung („`audio_router.py:2255` ruft `get_downbeats()` ohne
    Pflichtargument") beschrieb den **Arbeitsbaum**, nicht HEAD. In HEAD gibt es
    **überhaupt keinen** `get_downbeats`-Aufruf; `downbeat_provenance` ist
    ausnahmslos `"unavailable"`. Der Defekt ist real, aber ein anderer: Downbeats
    werden nie versucht. Und der naheliegende Fix ist falsch —
    `get_downbeats(audio_path)` fährt einen **zweiten vollständigen
    BeatNet-Lauf**; richtig ist `BeatDetector.scan()`, das beides in einem
    Durchlauf liefert.
  - Die LUID-Angaben unten (`0x0001185b`) sind keine Geräteidentität.
    **DXGI-LUIDs werden pro Boot vergeben.** Heute live gemessen:
    `0x00000000_0x314b3078`. Im Repo stehen vier verschiedene Werte für dieselbe
    Karte; alle waren zum Zeitpunkt ihrer Aufnahme richtig. Kein
    Produktionscode gated auf eine hartkodierte LUID (geprüft) — die Vergleiche
    in `system_monitor.py`, `vram_arbiter.py` und `vram_budget_manager.py`
    halten zwei zur Laufzeit gelesene Werte gegeneinander.
- **Historischer Stand:** 2026-08-11 (OBJ-76 Runtime-Wahrheit; 18/20 Tasks belegt)
- **Current Status:** Launcher/LHM/Capture, Shutdown-Persistenz, SigLIP-Gate,
  Scene-Ground-Truth und Recovery-Dry-Run sind fokussiert und live belegt.
  Der direkte LM-Studio-Load/SSE-Transport ist für qwen3.6 und qwen2.5-VL grün;
  der reale PB-Studio-Pfad lieferte unter paralleler 14,27-GB-Fremdmodell-
  Belegung noch keinen nutzbaren Tag-Commit. Der 64-Token-Diagnose-Request ist
  nicht mit dem unbegrenzten Produktaufruf gleichzusetzen. Deshalb
  bleiben T003 und der datenwirksame 10-Clip-Canary T019 offen. Bulk ist NO-GO;
  465 taglose Videos wurden nur read-only inventarisiert. Der isolierte
  Wiederholungslauf benötigt eine eigene Freigabe zum kurzen Pausieren des
  externen Hermes-Research-Watchdogs, der sein 14,27-GB-Modell automatisch lädt.
- **Historischer Stand:** 2026-08-08 (OBJ-73 Remote PASS; geschützter
  Default-Branch `main`)
- **Status (2026-08-08 — autoritativ):**
  - PR #22 mit allen Required Checks gemerged; `main` ist Default-Branch und
    gegen ungeprüfte Änderungen, Force-Pushes und Löschungen geschützt.
  - Acht High-Runtimebefunde behoben: Live-Beat-Cache, SSE-Abschlussjournal,
    RAFT-VRAM-Transaktion, Preview-GPU-Lock/Fehlersignal, Stem-Strukturpfad,
    Anchor-Races, doppeltes Brain-Feedback und Cut-synchrone Wiedergabe.
  - Drei vollständige Quality-Gate-Läufe: jeweils **1291 passed / 13 governed
    skips / 0 failed**; native UI **49/49**, WPF Release **0 Warnungen/0 Fehler**.
  - SDD: OBJ-72 T370–T415 und OBJ-73 T001–T009 vollständig; Release-SHA
    `947ff3885f402ec72c0659edafa20c78107fbf08` remote verifiziert.
- **Historischer Stand:** 2026-08-07 (Vision-Tagging + VRAM-Sensor)
- **Status (2026-08-07 — autoritativ):**
  - Auslöser: „DIE ANALYSE STIMMT NICHT DAS GEHT VIEL ZU LANGE / VIDEO ANALYSE".
    **Bestätigt.** `/video/analyze` brauchte **150,69 s pro Clip** und lieferte
    **`0 tags (none)`**.
  - Ursache: das 15,0-s-Timeout um den LM-Studio-Chat-Call war **kürzer als
    LM Studios JIT-Ladezeit** (gemessen 15,8 s). Jeder erste Call lief in den
    Timeout, der Failover verbrannte 3 Kandidaten × 15 s **pro Frame**. Kein
    Modell wurde je warm, weil jeder Ladeversuch vorher abgebrochen wurde.
  - **Neues Modell:** `qwen2.5-vl-7b-instruct` (Non-Reasoning-VLM, Apache-2.0,
    6,04 GB) installiert und als Override für `video_captioning`/`image_captioning`
    gesetzt. Die vorherigen Kandidaten sind Reasoning-Modelle und verbrennen
    mehrere hundert Denk-Token vor der Tag-Zeile.
  - **Failover-Ketten gekürzt** — jeder Schritt zwingt LM Studio zum
    Modellwechsel, live gemessen **72–120 s pro Wechsel**. Die Kette war selbst
    der Schaden. Alle Preference-Listen gegen das Live-Inventar neu gesetzt
    (6 nicht mehr installierte IDs raus, fehlender `chat`-Block ergänzt).
  - **Moondream:** `onnx_models_available()` ließ den Encoder allein genügen →
    pro Clip 1800 MB + GPU-Lock für einen Load, der garantiert nichts liefert.
    Decoder ist jetzt Pflicht.
  - **Live verifiziert am laufenden Backend:** `POST /video/analyze` → **15,2 s**,
    `captions: completed`, `tag_source: qwen2.5-vl-7b-instruct`, 10 deutsche Tags,
    persistiert in `media.id 205`. Keine Moondream-Reservierung mehr im Log.
    pytest **1281 passed / 13 skipped / 0 failed**.
  - **Vier Review-Agents** haben **6 Defekte in der ersten Fassung meines
    eigenen Fixes** gefunden, alle behoben: fehlende TTL auf `_WARM_MODELS`,
    Ladebudget von Nicht-Ladefehlern verbrannt, Worst Case 3 × 165 s pro Frame,
    Dict-Iteration ohne Snapshot, Cooldown zu lang, ein Test der nichts prüfte.
  - **Zweite Runde, Commit `db9f3eb` (gepusht):** die Review-Restliste ist
    abgearbeitet. pytest **1288 passed / 13 skipped / 0 failed**.
    - **VRAM-Sensor verdrahtet.** `VRAMBudgetManager.monitor` wurde von genau
      einem Aufrufer gesetzt — `VRAMArbiter`, im eigenen Docstring
      „DEPRECATED" und ohne Produktions-Aufrufer. In Produktion war der Monitor
      **immer `None`**; die Eigenbuchhaltung konnte nie gegen die Realität
      geprüft werden. Jetzt im Lifespan verbunden, live belegt:
      `Buchhaltung=15277MB, Sensor=8686MB (Differenz=6591MB)` — das ist
      LM Studio auf derselben Karte. **Meldet, sperrt nicht:** DirectML kann
      auf Shared Memory ausweichen, ein Gate würde „langsam" zu
      „fehlgeschlagen" machen. `Tests/test_vram_sensor_wiring.py` prüft den
      Produzenten; Gegenprobe gemacht, bei entfernter Verdrahtung fällt er.
    - **Merke:** die erste Fassung dieses Checks war selbst toter Code — die
      Unit-Tests injizieren ihren Monitor und blieben grün. Producer-ohne-
      Consumer, diesmal selbst produziert. Nur der fehlende Logeintrag verriet es.
    - `user_task_override` als eigene Receipt-Quelle (Override und
      Präferenzliste teilten sich einen Wert).
    - **6 tote Config-Schlüssel entfernt** (`ai.vision_model` + die fünf
      T4.6-Reste), gegen Python und C# auf Leser geprüft.
    - **50 Clips** mit leeren Tags zurückgesetzt; Szenen/Motion/Embedding
      erhalten, Backup in `data/backups/`.
    - `_VISION_NAME_TOKENS`: `qwen/qwen3.5-`/`qwen/qwen3.6-` **bleiben**. Sie
      decken die präfigierte Namensform ab; Verkürzen fängt je ein reines
      Textmodell mit ein (live gegengeprüft).
- **Historischer Stand:** 2026-08-06 (Datenfluss-Audit + 38 Fixes, `7a604de`)
- **Status (2026-08-06 — autoritativ):**
  - Auslöser: User-Meldung „viele daten werden nicht weiter geleitet" —
    **messbar bestätigt**. Kernmuster 5× unabhängig: Feature implementiert und
    getestet, aber Producer fehlt. Tests befüllten ihren eigenen Store.
  - Dokumente: `docs/LOG_AUDIT_2026-08-05.md`, `docs/REPARATURSTRATEGIE_2026-08-05.md`
  - **38 Fixes** in `7a604de` (52 Dateien, 3548 Zeilen), gepusht auf
    `origin/00013-system-wide-bug-hunting-audit`, Remote-SHA verifiziert.
  - Verifiziert: pytest **1267 passed / 13 skipped / 0 failed**, C# **42/42**,
    WPF Release **0/0**. **Live in der laufenden App** bestätigt: 8 neue
    Director-Regler im UIA-Baum, Kontextfenster `1'048'576 Tokens` gerendert,
    Architekturen `qwen35`/`granitehybrid` statt `llm`/`vlm`, GPU-Telemetrie aktiv.
  - **DB auf Wunsch komplett zurückgesetzt:** 24 Projekte → 0, 2354 Media-Rows → 0,
    FAISS und Brain-Cache geleert, 38 Projektordner entfernt, 31,2 GB frei.
    Backup `data\backups\full_reset_20260805_054257\`. Renders endgültig gelöscht.
  - **Neue Guards:** `Tests/test_trigger_settings_full_wiring.py` (Kette Schema →
    C#-Record → Konstruktoraufruf → XAML-Binding → Engine-Leser),
    `Tests/test_viewmodel_binding_wiring.py` (jede ObservableProperty gebunden
    oder mit Begründung dokumentiert).
  - **Log trägt jetzt ein Datum** — vorher nur `%H:%M:%S` über Wochen angehängt,
    wodurch zwei längst gefixte Fehler zunächst als offen fehlbewertet wurden.
  - **5 von 6 Entscheidungen umgesetzt** (Commit `39aaa3b`, gepusht):
    - **madmom läuft** — die Annahme „auf 3.11 nicht installierbar" ist
      **widerlegt**. `BEATNET_AVAILABLE` erstmals `True`, Downbeats existieren.
      Liegt in `requirements-optional-beatnet.txt` (kein Wheel, braucht MSVC).
    - **Brain-Herkunft sichtbar** — `/brain/stats` meldet archivierte
      Beobachtungen, Semantikversion und Migrationsgrund. Die Migration 002 war
      eine Einmal-Migration und fachlich korrekt; falsch war nur die Unsichtbarkeit.
    - **Stem-Timeout** — Ursache war `duration_seconds == 0`, nicht das Budget.
      Dauer wird jetzt nachgemessen. `separator.py` unangetastet (LOCKED).
    - **Anker-Tab fertig** — `GET`/`POST /project/anchors`, `anchors.json`,
      Einspeisung über `PacingService._merge_ui_anchors`.
    - **5 wirkungslose config.json-Schlüssel entfernt**, `conftest.py` synchron.
    - Dazu **T3.5**: `projector_trainer` hat einen Aufrufer (Fit alle 20 Feedbacks).
  - **Offen: nur T4.5 (NSwag-Layer)** — Architekturwahl, kein Defekt: 4450 Zeilen
    generierter Code testgeschützt, während der real genutzte Hand-Record-Pfad
    ungeschützt ist. Beide Auswege ändern die Contract-Pflege im Team.
  - **Unbewiesen:** `semantic_match_weight` und der Projector-Hook brauchen einen
    echten Analyselauf mit Audio **und** Video plus 20 echte Bewertungen.
  - **Lehre für künftige Arbeit:** vor Signatur-, Pfad- oder Dateiänderungen
    repo-weit nach Aufrufern, Test-Fakes und lesenden Tests greppen. In dieser
    Session zweimal versäumt, beide Male von der Suite gefangen.
- **Historischer Stand:** 2026-08-02 (Reparaturplan 00013, OBJ-72 T413)
- **Phase:** 🟠 OBJ-72 bei 44/46 PASS; lokaler Kandidat technisch geprüft,
  aber nicht release-ready. T415 und die abschließende T414-Digestkonvergenz
  fehlen; `.qc-passed` bleibt gesperrt.
- **Status (2026-08-02 — autoritative OBJ-72-Wahrheit):**
  - T370–T413 einschließlich Betriebssicherheit, Gesamt-/Native-/GUI-/Hardware-
    und Supply-Chain-Gates sind PASS.
  - Clean-Kandidat `7fece74db63470084c5179917d57a8060d20c5a3` besitzt
    `release_eligible=true`, 182 SBOM-Komponenten und ein verifiziertes
    WPF-ZIP mit SHA-256
    `c48e5a12046465b808e25e35559e367b5813c9ae5f42a584a19ebb8626ed3f62`.
  - T414/T415 bleiben offen: PR, Required Checks, geschützter Main-/Release-SHA
    und danach QC-/Brain-/Marker-Digests.
- **Status (2026-07-31 — autoritative Release- und Modellwahrheit):**
  - DirectML-Assets sind durch `config/directml-model-assets.json` und
    `config/directml-asset-bundle.json` an Revisionen, Source-/Target-Hashes,
    Archivhash und Lizenztexte gebunden.
  - CLAP Audio/Text stammt aus
    `ConceptualMachines/magda-sample-tagger@f24970352f239768aaad48cc8734fb298441a763`;
    Processor aus
    `laion/clap-htsat-unfused@8fa0f1c6d0433df6e97c127f64b2a1d6c0dcda8a`;
    Lizenzkette `BSD-3-Clause AND Apache-2.0`.
  - Letzter Hardwarebeleg T363: RX 7800 XT Index `1`, LUID
    `0x00000000_0x0001185b`. Aktuelle Releasefreigabe benötigt erneuten
    Fresh-Install-Beleg T411 plus alle übrigen QC-Gates T404–T415.
- **Historischer Status (2026-07-30 — GPU-/Provider-/Analyse-Reparatur T340–T369):**
  - DirectML, VRAM und LHM verwenden RX 7800 XT Index `1`, LUID
    `0x00000000_0x0001185b`; LHM-0.9.6-Trust ist manifest- und hashgebunden.
  - Liveinventar, providergebundene Selection Receipts, begrenztes Failover,
    persistenter Modellwechsel und nullable `SceneInfo.Confidence` sind repariert.
  - Verifiziert: **1090 passed/11 skipped/0 failed**, WPF Release **0/0**,
    Provider-/GUI-E2E PASS; H.264 und HEVC je 190.051 Frames, Full-Decode,
    106/106 Segmente und keine Schwarz-/Freezeintervalle.
  - T363 PASS: RAFT, SigLIP, Moondream Vision, CLAP und Audio MDX liefen
    aktiv auf RX 7800 XT LUID `0x00000000_0x0001185b`; iGPU jeweils 0 %.
  - CLAP Audio/Text ist funktional; ein aktivierter doppelter GPU-Lock wurde
    entfernt. Moondream Caption bleibt ehrlich unavailable, Vision ist ready.
  - Die damaligen `.completed`-/`.qc-passed`-Marker waren nur für jenen
    Quellstand gültig und erteilen dem aktuellen Worktree keine Freigabe.
  - T369: Secret-Scan und D07 PASS; PB und ausschließlich
    PB-Studio-Brainpfade normal gepusht; Remote-SHAs verifiziert.
- **Status (2026-07-28 — Neue vollständige App-Statusaufnahme):**
- **Status (2026-07-28 — Vollständige App-Statusaufnahme):**
  - Sechs disjunkte read-only Fach-Audits über alle Produktzonen; Masterbericht `docs/archive/FULLSTACK_STATUS_AUDIT_PB_STUDIO_2026-07-28.md`.
  - Verifiziert: pytest **853 passed/11 skipped**, Release-Build 0/0, Backend Health 200, 17 SQLite-DBs integer, FAISS/SQLite 0 Orphans, 12 WPF-Tabs gerendert.
  - Live-Lücken: MODELLE-Endpunkte hängen bei offline Ollama; nur Embedding-Modell geladen; Chat/Vision-LLM nicht nutzbar; H.264/HEVC AMF PASS, AV1 AMF FAIL.
  - Befunde: **2 CRITICAL, 26 HIGH, 25 MEDIUM, 7 LOW**. Kernthemen: CPU-CLAP-Iron-Verstoß, unbestätigte Chat-Mutationen, Long-Mix-OOM, Brain-Deep-Hook, Projekt-/Render-Datenrisiken, WPF-Projektwechsel.
  - SDD: 227/227 Tasks markiert, aber `.completed` und `.qc-passed` fehlen bewusst; kontinuierliches Audit offen.
- **Status (2026-07-10, Teil 3 — Onset-Caching-Fix nach Sweep):**
  - **2 Agent-Teams gebaut** (`dev-*`/`analyst-*` x 12 WPF-Tab-Domains = 24 Subagents + 12 Skills), siehe `docs/agent-teams/README.md`.
  - **Voller 24-Agent-Sweep** über alle 12 Domains, Fokus Pacing-Datennutzung. Kernfund: `advanced_pacing_engine.py:1022` importierte totes `core.session_manager`-Modul (existiert nicht im Repo), ImportError von `except Exception: pass` verschluckt → Onset/Kick/Snare/HiHat/Energy-Trigger im normalen (pre-cached) Pacing-Pfad wirkungslos. Volle priorisierte Findings-Liste (14 HIGH + 12 MEDIUM + 4 LOW) in `docs/agent-teams/README.md` Abschnitt "Sweep 2026-07-10".
  - **Selbstkorrektur:** eigener `CrossModalProjector`-Fix von Teil-1 dieser Session (768→1152) war falsch (SigLIP-Modell-Verwechslung `siglip_wrapper.py` vs. echtem Brain-Feeder `video_embedder.py`). Zurückgesetzt auf 768.
  - **Onset-Caching-Fix umgesetzt** (User-Entscheid: größere Lösung statt Workaround): Audio-Pipeline (`audio_router.py`) berechnet jetzt Onset/Kick/Snare/HiHat-Trigger-Kandidaten einmalig beim `/audio/analyze`-Lauf (~~gleiche librosa-Parameter wie der Live-Fallback~~ — **widerlegt im Audit 2026-08-29:** Cache-, Stem- und Fallback-Pfad nutzen drei divergierende Parametersätze; `n_mels` adaptiv/128/64, `n_fft` adaptiv/2048, `preemphasis` ja/nein/ja, `delta` ungesetzt/gesetzt/gesetzt. Dieselbe Datei liefert je nach Codepfad andere Trigger-Zeitpunkte), persistiert über `app_state.py` (JSON-Blob, kein DB-Schema-Migration nötig), injiziert via `pacing_service._inject_cached_into_engine` in die Pacing-Engine. `advanced_pacing_engine.py`: toter SessionManager-Import entfernt, Audio-Load-Gate korrigiert (lädt Audio nur noch, wenn für eine AKTIVE Trigger-Gewichtung wirklich kein Cache existiert — sonst RAM-Optimierung für lange DJ-Mixes erhalten), `_build_triggers_from_cache` um Kick/Snare/HiHat erweitert. Neue Schema-Felder in `AudioAnalysisResult` (`onset_times`/`kick_times`/`snare_times`/`hihat_times`), C#-DTOs regeneriert.
  - **Verifiziert:** pytest **749 passed**/12 skipped (voller Lauf); Release-Build 0 Fehler; Backend-Live-Smoke sauber (kein Import-/Wiring-Fehler); openapi-Snapshot aktualisiert + Drift-Test grün.
  - **Nicht verifiziert (offen):** kein Live-Test mit echter langer DJ-Mix-Datei, ob Onset/Kick/Snare/HiHat-Regler jetzt tatsächlich sichtbar unterschiedliche Cut-Listen erzeugen (nur Unit-Test-Ebene + Code-Pfad-Verifikation).
- **Status (2026-07-10, Teil 2 — KI-Model-Wiring-Audit):**
  - **Chirurgischer KI-Model-Audit (Vision/Audio-Analyse/LLM/Brain)** via `full-stack-auditor`: 6 Findings, alle gefixt und verifiziert.
    1. **config.json lmstudio_base_url war FALSCH** (`12341` statt echtem `1234` — Live-`curl` bestätigt). Gefixt.
    2. **Model-Registry-Preferenzen** (`model_registry.py` DEFAULT_TASK_PREFERENCES + config.json task_preferences) für chat/chat_general/chat_tool_use/brain_explanation zeigten auf nie-installierte Fantasie-Fine-Tunes — live gegen `GET /v1/models` neu abgeglichen, echte IDs eingesetzt (`google/gemma-4-e4b`, `qwen/qwen3-coder-30b`, `qwen/qwen3-4b-thinking-2507`, `distil-home-assistant-functiongemma`, `gemma-4-12b-it-uncensored@q4_k_s`). Wichtig: `qwen/qwen3.5-9b`/`qwen/qwen3.6-27b` waren entgegen erstem Audit-Verdacht ECHT installiert (alter Log war stale). `task_overrides` (zeigte auf nie-installiertes `gemma4:12b`) geleert.
    3. **Moondream-ONNX-Fallback war dead code** (ONNX-Dateien fehlen, nur `.pt`-Checkpoint vorhanden) UND meldete fälschlich "active"/Erfolg per SSE trotz 0 Tags. Fix: `onnx_models_available()`-Cheap-Check vorgeschaltet (`moondream.py`), `video_router.py` published jetzt ehrlich `unavailable`/`failed` statt Fake-Erfolg. Kein CPU-Fallback eingebaut (IRON RULE 1 respektiert).
    4. **CrossModalProjector Dimensions-Bug**: `DEFAULT_VIDEO_DIM=768` vs. real SigLIP-SO400M `1152` — echte Embeddings wurden bei jeder Brain-Projektion stillschweigend um 384 Dims abgeschnitten (`_fit_to_size`). Fix: Default auf 1152 korrigiert (`cross_modal_projector.py`), kein persistiertes Weight-File betroffen (verifiziert: keins vorhanden).
    5. **llm_status-SSE-Coverage** war nur für Video-Frame-Tagging verdrahtet. Publisher-Pattern (analog `lmstudio_vision_wrapper.py`) jetzt auch in `chat_agent.py` (`process_message`) und `brain/llm_narrator.py` (`_async_generate_explanation`) verdrahtet + in `backend/main.py` Startup injiziert.
    6. Zwei Regressions-Tests durch Preferenz-Änderung angepasst (`test_model_registry.py::test_recommendation_reports_fallback_index` testete versehentlich eine der erfundenen IDs; `test_llm_narrator.py` brauchte `google/gemma-4-e4b` weiterhin im Fallback-Pfad).
  - **Verifiziert:** pytest **749 passed**/11 skipped (voller Lauf); Release-Build 0 Fehler/0 Warnungen; `openapi.snapshot.json`-Drift-Test grün nach Build (war reiner mtime-Phantom aus EOL-Renormalisierung, kein Content-Diff).
  - **Nicht verifiziert (offen):** Live-Smoke der WPF-Statusleiste für Chat/Brain-Explain-Pfad (neue `llm_status`-Publishes noch nicht am laufenden Backend beobachtet, nur Code-Pfad + Unit-Tests).
- **Status (2026-07-09):**
  - **LLM-Status-Widget (Antigravity-Arbeit) fertiggestellt:** SSE `llm_status` (thread-safe via `publish_event_threadsafe`) → WPF-Statusleiste. Fertigstellungs-Fix: Event fehlte im `events_router`-Progress-Filter.
  - **4-Experten-Review** über alle Commits 2026-07-08/09: 4 HIGH / 8 MEDIUM / ~13 LOW — **alle gefixt** (Plan: `docs/superpowers/plans/2026-07-09-review-fixes-commits-0708-0709.md`). Kernfixes: Cross-Thread-SSE-Race, AutomationPeer-No-Op (UIA/pywinauto), WeightStore-Close-Lock, Smoke-Script-False-FAIL, anchor_manager-Parallel-Save, Selektions-Erhalt Director/VideoLibrary, echte LM-Studio-Modell-Ids (`qwen/qwen3.5-9b`, `qwen/qwen3.6-27b` — erfundene Antigravity-Ids ersetzt).
  - **Verifiziert:** pytest **750 passed**/11 skipped; Release-Build 0 Fehler; Live-Smoke mit pywinauto (Tab-Content im UIA-Tree, Widget rendert).
  - **`main` gemergt** (fast-forward auf `6c625f1`) + gepusht. EOL-Renormalisierung per `.gitattributes` committed. Audit-Zyklus FULL_AUDIT_2026-06-10 damit abgeschlossen (AUDIT_FIX_VERIFY erledigt durch Build+pytest+Live-Smoke).
  - **Zurückgestellt:** AP3.6 Video-Grid-Virtualisierung (NuGet → User-Entscheid); AP6-Backlog (~45 🟡/🟢); bewusst-offene Review-LOWs (Begründungen im Plan-Header).
- **Next Task (2026-08-30, Sitzungsende) — LIVE-VERIFIKATION.**
  Runbook: `docs/handoff/2026-08-30-live-verifikation-startpunkt.md`.
  Remote-SHA `b9bae5b7a41af3a9bacb09aaf6126b4d3e31b781`, 34 Commits, lokal ==
  remote, Arbeitsbaum sauber. Vollsuite **2 failed / 1585 passed / 13 skipped /
  0 errors**, WPF Release 0/0, DB 6/711/`ok`.
  **Sieben Fixes und zwei Features sind gebaut und getestet, aber keiner davon
  am laufenden Backend mit echten Projektdaten gesehen.** Genau das steht an:
  V-1 Downbeat-Ableitung an echter Musik (wichtigster Punkt, inkl. Härtefall
  Snare auf 2 und 4), V-2 FR-362-Degrade, V-3 `audio_key` unavailable vs.
  failed, V-4 Heilung der Phantom-Stage-Schlüssel, V-5 die WPF gegen das neue
  Backend (nach dem transformers-Major-Sprung nie gestartet), V-6 Entscheidung
  über die zwei Dauerroten.
  **Vier Betriebsregeln, in dieser Sitzung teuer gelernt:** (1) das Backend
  **nie** hart beenden — `Stop-Process -Force` lässt `RUNTIME_DIRTY` stehen und
  der nächste `backend.main`-Import rollt 398 Artefakte zurück, inklusive
  `data/pb_studio.db`; (2) Fertigsignal des Shutdowns ist das Verschwinden von
  `RUNTIME_DIRTY`, **nicht** der geschlossene Port — dazwischen liegen
  gemessene 28 s; (3) jeder pytest-Lauf braucht ein eigenes `--basetemp`;
  (4) DB-Zählstände vor und nach jedem Lauf prüfen.
  Kleinigkeiten, wenn Zeit bleibt: `has_audio_embedding` wird nach der Analyse
  nie aktualisiert; `"peak"` fehlt in `STRUCTURE_INTENSITY_MULTIPLIERS`; der
  Binding-Wächter hat zwei belegte Falschgrün-Klassen. `.venv-pre-lock-20260830`
  und `.venv-lock` sind Wegwerfstände.
- **Next Task (älter, unverändert offen):** Hermes-Research-Watchdog nur mit eigener Freigabe kurz
  pausieren, genau T003 isoliert live wiederholen und den Watchdog danach exakt
  wieder starten. Nur wenn der echte Produktaufruf dann erneut keine Tags
  liefert, die reservierte Videoanalyse-Zone minimal ändern. Erst nach
  erfolgreichem Tag-Commit und separatem Canary-Go T019 ausführen;
  bis dahin keine Bestandsnachanalyse und keine OBJ-76-Abschlussmarker.
- **Bug-History:** siehe `CHANGELOG.md` (BUG-001..046 archiviert 2026-03-09, HIGH-001..006 gefixt 2026-03-11, R12–R20 gefixt 2026-03-16, Brain-Modul Phase 0–6 abgeschlossen 2026-05-06, BUG-200..205 gefixt 2026-05-08/09, **2026-05-11 Pipeline-Lueken-Plan komplett abgearbeitet** L-K1..K5 + L-M1..M8 + L-N2..N8 + L-TI-1..TI-7, **2026-05-21/22 QA-Loop+Hybrid-Audit** 3 Code-Fixes + 4 Hybrid-Bypass-Fixes, **2026-05-30 Epic 00013 Audit & Optimierungen**, **2026-06-09 Stems-Analyse-Bug & htdemucs Crash behoben**, **2026-06-10 Full-Audit + Epic 00015 K1–K11**, **2026-06-12 Audit-Fix Phase 3 AP1–AP5**).


**Kern-Architektur-Entscheidungen:**
- *AppState:* `backend/app_state.py` Singleton + SQLite-Persistenz + `current_project` (ADR-001+003)
- *VRAM Arbiter:* `with_gpu_task(model_id=...)` prüft VRAMBudgetManager.
  **Audit 2026-08-29:** die Klasse `VRAMArbiter` (264 Z.) ist vollständig toter
  Code (0 Produktions-Aufrufer); die dort beschriebene Dual-Verification läuft
  nicht. Von den 3 produktiven `with_gpu_task`-Aufrufen setzen 2 `manage_vram=False`
  und der dritte ist unerreichbar (`moondream_decoder.onnx` fehlt) — der gesamte
  Reservierungscode läuft im heutigen Betrieb nie. Pacing erreicht DirectML ganz
  ohne `with_gpu_task`.
- *Vision LLM:* Moondream ONNX (FP16) via DirectML
- *Motion Analysis:* RAFT ONNX via DirectML (`raft.py → MotionAnalyzer`)
- *Stem Separation:* htdemucs runs on CPU because PyTorch CPU is used in the pinned environment. DirectML acceleration only applies to ONNX-MDX paths in StemSeparator.
- *Vector DB:* FAISS-CPU (1152-dim SigLIP SO400M embeddings) + sqlite-vec (Brain-Modul KNN)
- *Beat Detection:* **librosa ist der reale Beat-Lieferant.** BeatNet/madmom
  ist zur Laufzeit wirkungslos: `madmom/features/downbeats.py:287` ruft
  `np.asarray(results)[:, 1]` auf eine ungleichförmige Ergebnisliste, was seit
  NumPy 1.24 ein `ValueError` ist. Gegengeprüft mit `beats_per_bar=[4]` statt
  `[2,3,4]` — wirft ebenfalls, keine Konfiguration umgeht den Pfad. BeatNet
  wirft damit bei **jeder** Datei; der Wurf wird gefangen und librosa
  übernimmt. Seit dem venv-Neubau ist `madmom` gar nicht mehr installiert.
  **Downbeats werden seit `6187eb2` aus den Anschlagstärken abgeleitet** und
  ausdrücklich als `status="derived"`, `synthetic=True` gekennzeichnet —
  `"measured"` bleibt echten Detektor-Taktpositionen vorbehalten. Die
  Ableitung verweigert die Auskunft, wenn sich keine Taktposition abhebt; das
  hält FR-317 („keine pauschale jeder-vierte-Beat-Behauptung") ein. Der
  T317-Wächter in `AdvancedPacingEngine._identify_downbeats` ist unangetastet.
  *Historisch, jetzt überholt:*
  **die Downbeats erreichen die Pacing-Engine nicht** (Audit 2026-08-29, C-01):
  `audio_router.py:2255` ruft `detector.get_downbeats()` ohne das Pflichtargument
  → `TypeError`, von `except Exception` verschluckt. Zusätzlich schreibt der Router
  `downbeat_provenance="available"`, während `pacing_service.py:389` auf
  `"measured"` prüft, und `beats` wird nach dem Anhängen der Downbeats nie
  sortiert. Drei Brüche in einer Kette — ein Teilfix macht es schlimmer.
  `beat_trigger_mode="downbeat_only"` liefert daher eine leere Cut-Liste.
  librosa als Fallback. **Korrektur
  2026-08-06:** die frühere Angabe „madmom nicht installierbar auf 3.11" war
  falsch — madmom 0.16.1 baut auf 3.11.9, siehe `requirements-optional-beatnet.txt`.
  Ohne madmom liefert `get_downbeats()` hart `[]`, dann existieren keine Downbeats.
- *Key Detection:* `src/pb_studio/audio/key_detector.py` Krumhansl-Kessler via librosa
- *SSE Fan-out:* `publish_event` broadcastet an ALLE registrierten Queues
- *Path-Traversal-Schutz:* `Path.is_relative_to()` in project_router + render_router
- *Brain-Modul:* 17 Bridge-Achsen · Beta-Bernoulli WeightStore · 5-Level Hierarchical Backoff · SigLIP-ONNX (1152-D) und registriertes CLAP-ONNX via ONNX Runtime DirectML, fail-closed ohne Asset · 6 REST-Endpoints `/brain/{suggest,feedback,learning_session,stats,reset,explain}` · WPF HIRN-Tab + Confidence-Balken
- *Pacing Specialist Skill:* `.claude/skills/audio-video-pacing-specialist` (BPM, Beat-Grid, EDM-Groove, 21+ Mood-Profile, Speech-WPM/CPS & Cut-Optimierung; kompatibel mit Claude, Codex & Antigravity)

---