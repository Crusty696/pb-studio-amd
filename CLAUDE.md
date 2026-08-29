# CLAUDE.md - PB Studio (AMD Premium Edition)
# SYSTEM PROMPT, RULES & PROJECT BRAIN

Read this file ENTIRELY before executing any tasks. Do not look for other .agent files.

---

## 0. ⚡ COMMANDS (copy-paste ready)
```powershell
# Python Backend starten
# WICHTIG (Audit 2026-08-05, H-7): NICHT nur PYTHONPATH setzen. Ohne
# PBSTUDIO_LHM_MANIFEST_SHA256 meldet der SystemMonitor "LibreHardwareMonitor
# deaktiviert" und das GPU-Monitoring ist tot (21x im Log nachgewiesen).
# Ohne PBSTUDIO_OWNER_CAPABILITY kann die WPF das Backend nicht uebernehmen.
# Fuer echte Arbeit daher immer den Launcher nehmen:
.\start.bat            # bzw. .\launch.ps1 — setzt Owner-Token + LHM-Hashes

# Nur fuer reine Backend-Tests ohne GUI und ohne GPU-Monitoring:
$env:PYTHONPATH = (Join-Path (Get-Location) "src")
.\.venv\Scripts\python.exe -m uvicorn backend.main:app --host 127.0.0.1 --port 8765

# Tests ausführen
$env:PYTHONPATH = (Join-Path (Get-Location) "src")
.\.venv\Scripts\python.exe -m pytest Tests/ -x -q

# WPF Build
dotnet build PBStudio.UI\PBStudio.UI.csproj
```

---

## 1. 🚀 BOOT PROTOCOL
1. Read this file completely.
2. Acknowledge the current task.
3. Verify that your proposed solution respects the IRON RULES.
4. Output confirmation: "✅ BOOT OK | Task: [Current Task] | Brain: 2026-08-11"

---

## 2. ⚠️ IRON RULES (NEVER OVERRIDE)
1. **AMD DIRECTML ONLY:** NO CUDA, NO ROCm. Use `onnxruntime-directml`.
2. **DIRECTML PATTERN:** `enable_mem_pattern = False` AND `enable_cpu_mem_arena = False` (BOTH MANDATORY).
3. **PYTHON & NUMPY:** Python 3.11.x | NumPy 1.26.4 (< 2.0 strict — BeatNet).
4. **HARDWARE ENCODING:** NO NVENC. Use `h264_amf`, `hevc_amf`, `av1_amf` via FFmpeg.
5. **GPU MONITORING:** NO `pynvml`. Use `LibreHardwareMonitorLib.dll` via `pythonnet`.
6. **WINDOWS:** `pathlib.Path` oder raw strings. PowerShell für Shell-Befehle.
7. **PYTHONPATH:** Immer `PYTHONPATH=src` setzen (kein editable install).
8. **TESTS:** `testpaths = Tests` (Großbuchstabe! Windows NTFS auf Linux-Mount).
9. **AUTONOMOUS DEPLOYMENT:** Nach JEDER Aufgabe die Code/Scripts/.bat-Files/Configs ändert die einen Deployment-Schritt brauchen um zu greifen → Deployment AUTONOM ausführen, OHNE User-Aufforderung. Niemals "Source geändert, fertig" als Endmeldung.
10. **100% HONESTY (User-Direktive 2026-05-09):** Niemals Erfolg behaupten ohne Live-Verifikation. Build OK ≠ läuft. Code-Edit ≠ deployed. Test-PASS ≠ User-sichtbar funktional. Bei "sollte greifen" / "wahrscheinlich" → STOP, reformuliere als "verifiziert: X" oder "unbekannt: X". Bei Audit: vollständige Liste, keine selektiven Wahrheiten. Concerns vorab benennen. Wenn Bug nach Fix-Versuch noch da → zugeben, nicht relativieren. Wenn ich nicht weiss → "weiss ich nicht", nicht raten. **Hintergrund:** wiederholte Trust-Incidents 2026-05-08/09 (BUG falsch als gefixt gemeldet, App lief mit altem Binary, BPM-Workflow als "OK" bezeichnet trotz hand-adjust).
   - C#-Änderung in `PBStudio.UI/` → IMMER `dotnet build PBStudio.UI\PBStudio.UI.csproj -c Release` (launcher lädt Release-DLL, nicht Debug)
   - Script-Änderung (.bat/.ps1/.cmd) → IMMER mit `script-validator`-Skill bis 3× clean Run validieren
   - Änderung an Setup/Start/Test-Logik → ALLE abhängigen Wrapper synchron aktualisieren (setup.bat ↔ setup_pb_studio.ps1, start.bat ↔ launch.ps1, test.bat ↔ run_full_test.ps1)
   - Backend-Schema-/Route-Änderung → Frontend `ApiClient.cs` + Schema-Records prüfen + ggf. anpassen + Release-Build
   - Setup-Script-Änderung → `requirements.txt`/Dependency-Listen synchron halten
   - End-Report MUSS explizit zeigen: was gebaut, welche Binaries/Scripts aktualisiert, welche validiert.
   - **Hintergrund:** 2026-05-08 Trust-Incident — Bug-Fix in C# war im Source aber Release-Binary nicht gebaut → User testete altes Binary und verlor Vertrauen. Diese Regel verhindert Wiederholung.
11. **OBSIDIAN VAULT FORTLAUFEND (User-Direktive 2026-05-11):** Obsidian-Vault `C:\Users\david\Brain\10_Projects\PB_studio\` MUSS bei JEDER nicht-trivialen Aenderung mitlaufen: INDEX.md `updated`-Frontmatter + Status-Sektion, log.md append entry, neue ADR in decisions/ bei Architektur-Entscheidung. Drift zwischen Code-State und Vault-State = Vertrauensverlust. Tools: `mcp__obsidian__*` (update_frontmatter, append_to_note, replace_in_note). **Hintergrund:** User explizit angemahnt 2026-05-11 dass Vault nicht stale werden darf.
12. **FULL-SYNC EISERN (User-Direktive 2026-05-11):** Bei der Direktive "alles committen / kompletter Status / Vault gleichstand" MUSS folgendes synchron sein — **kein Detail darf ausgelassen oder uebersprungen werden**:
   - Git: alle relevanten Files committed, `git status --short` leer (außer ignorierten Runtime-Artefakten in .gitignore)
   - Obsidian INDEX.md: Frontmatter `updated` aktuell, Status-Sektion spiegelt Repo-HEAD wider (alle Commits seit letztem INDEX-Update reflektiert)
   - Obsidian log.md: append entries fuer ALLE Session-Ereignisse (Commits, Audits, Decisions, Memory-Updates), keine Luecken
   - Memory: jede neue Direktive/Lesson als eigenes feedback_*.md File + MEMORY.md Index-Eintrag
   - CLAUDE.md §3 PROJECT BRAIN: Date + Status + Next Task + Bug-History aktuell
   - Bei Drift erkannt: ZUERST sync, dann melden — nicht "kommt naechste Session". **Hintergrund:** User-Direktive 2026-05-11 "ein alles muss auf dem selben stand sein wie das projekt selber ist nicht das kleinste detail darf ausgelassen oder uebersprungen werden — das ist eine eiserne regel".

12. **AUTONOMIE-LESSONS:** Bei JEDER User-Anweisung wo der User sagt "warum machst du das nicht selbst" oder aequivalent → Eintrag in `COWORK_AUTONOMY_LESSONS.md`. Pattern-Liste in dieser Datei vor jeder Code-Aktion mental durchgehen.

   **2026-05-16 User-Direktive: AUTONOMIE-DEFAULT-ON.** Default ist autonom handeln, nicht zurueckfragen. Ich darf und MUSS ohne Nachfrage: .bat/.ps1 schreiben + selber ausfuehren (Computer-Use ODER Bash), Git add/commit/push/mv/plumbing inkl. Lock/Index-Recovery (siehe COWORK_AUTONOMY_LESSONS.md Pattern #15 Bypass-Toolkit: `mv` statt `rm`, `GIT_INDEX_FILE=/tmp/...`, `commit-tree`, `dd conv=notrunc` auf refs), Builds (dotnet, pytest, ffmpeg-Probes), Sandbox-Workarounds, Computer-Use bei Bash-Fehler, Cleanup von temp-Files. **User-Action only:** Hardware-Steckaktionen, UAC-Prompts, Reboot. Vor jeder „du musst"/„mach selber"/„autonom"-Antwort des Users: COWORK_AUTONOMY_LESSONS.md scrollen + handeln statt zurueckfragen. **Hintergrund:** 2026-05-16 Ollama-Pilot — bei `.git/index.lock` "Hard-Block" gemeldet statt Bypass-Toolkit angewandt; User: „mach das selber du hast alle tools dafür". **2026-05-16 (Korrektur):** Push war fälschlicherweise in der User-Action-Liste — User hat klargestellt dass Push autonom passiert („Dann pushe sie über mein system du hast alle tools dafür warum muss ich dir das jedes mal sagen"). Diese Regel zieht nach, siehe COWORK_AUTONOMY_LESSONS.md Pattern #17.

13. **VERIFY-BEFORE-CHANGE (User-Direktive 2026-05-15):** Vor jeder Code-Änderung muss die vorgeschlagene Lösung erst verifiziert werden, dass sie funktioniert. Skills einsetzen (`pb-master` für Cross-Module-Analyse, `code-auditor` für Static-Analysis, `full-stack-auditor` für End-to-End, `code-review`, etc.). Erst nach erfolgreichem Verifizieren wird der Code angepasst.
   - **Bug-Fix:** erst Reproduktion, dann verify dass Fix die Root-Cause adressiert (nicht nur Symptom), dann anwenden
   - **Neues Feature:** erst Cross-Module-Verdrahtung mit `pb-master` prüfen, dann implementieren
   - **Refactor:** erst Caller/Dependents via `full-stack-auditor` oder Grep prüfen, dann anwenden
   - **Config/Doc-Change:** mindestens current state lesen + auf Konflikte prüfen, dann anwenden
   - **Hintergrund:** heute (2026-05-15) mehrere Edit-Versuche an Files ohne ausreichende Vorverifizierung → mid-edit Truncations und broken Files. Diese Regel verhindert das.
---

## 3. 🧠 PROJECT BRAIN & CURRENT STATUS
- **Date:** 2026-08-29 (Funktionsaudit + Reparaturplan 01 abgearbeitet)
- **Audit 2026-08-29:** ~243 Befunde (18 CRITICAL, 61 HIGH, 74 MEDIUM).
  Bericht: `FUNKTIONSAUDIT_2026-08-29.md`. Kernbefund: die Ketten brechen an den
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
  - Sechs disjunkte read-only Fach-Audits über alle Produktzonen; Masterbericht `FULLSTACK_STATUS_AUDIT_PB_STUDIO_2026-07-28.md`.
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
- **Next Task (2026-08-29):** Auswertung der vier App-weiten
  Zustandsaufnahmen (Backend, `src/pb_studio`, WPF, Infrastruktur/Tests). Danach
  offen und je einen eigenen Vorgang wert: Downbeats über
  `BeatDetector.scan()` statt eines zweiten BeatNet-Laufs; `has_audio_embedding`
  wird nach der Analyse nie aktualisiert; `"peak"` fehlt in
  `STRUCTURE_INTENSITY_MULTIPLIERS`; `test_audit_sdd_gate` und der
  LHM-Backup-Test brauchen eine Entscheidung (Marker nachziehen bzw. Test an ein
  eingechecktes Artefakt binden), sonst bleiben zwei Dauerrote ohne Signal.
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
- *Beat Detection:* BeatNet (madmom) installiert und `BEATNET_AVAILABLE=True`, ABER
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

---

## 4. 🏗️ ARCHITECTURE MAP
```
src/pb_studio/
├── audio/      # BeatNet(CPU), htdemucs(CPU)/ONNX-MDX(DirectML), SpectralAnalyzer, StructureAnalyzer,
│               # WaveformAnalyzer, KeyDetector (alle VOLLSTÄNDIG implementiert)
├── video/      # raft.py→MotionAnalyzer, scene_detect.py→SceneDetector, FrameGrabber
├── core/       # VRAM Arbiter, Task Queue, LibreHardwareMonitor
├── data/       # SQLite (SQLAlchemy), FAISS-CPU
└── services/   # Orchestration
backend/
├── routers/    # audio, video, pacing, render, events, project (alle vorhanden)
├── app_state.py # Singleton + SQLite-Persistenz + current_project
└── dependencies.py # with_gpu_task(model_id=...)
PBStudio.UI/
├── Services/   # ApiClient.cs (VOLLSTÄNDIG), IApiClient.cs, SSEClient.cs,
│               # PythonBridgeService.cs (PBSTUDIO_PYTHON_EXE env var)
├── ViewModels/ # 9 VMs (alle implementiert, MVVM Toolkit)
├── Views/      # 9 XAML Views (alle vorhanden, kein StartupUri)
├── Converters/ # NullToVisibility, InverseBool, InverseNullToVisibility
├── Resources/  # app.ico (3-size, 16/32/48px)
└── Models/     # AudioClipModel (Key+BeatCount), VideoClipModel (Thumbnail)
```

## 5. 🛠️ LOCKED VERSIONS
| Tool | Version | Constraint |
|------|---------|-----------|
| Python | 3.11.x | madmom/BeatNet |
| NumPy | 1.26.4 | < 2.0 strict |
| onnxruntime-directml | >=1.16.0 | GPU engine |
| PyTorch (CPU) | **Lock 2.11.0+cpu, installiert 2.4.1+cpu** | ML tensors. **Audit 2026-08-29: die venv wurde nie aus `requirements.txt` gebaut.** Auch transformers (4.49 statt 5.5.4), hf-hub (0.36.2 statt 1.5.0) und starlette (1.0.0 statt 1.3.1) weichen ab; `torch-directml` ist undokumentiert installiert. Ein Clean-Install erzeugt eine ANDERE Umgebung als die, in der die Suite grün gemeldet wurde. Entscheidung offen: Lock anpassen oder venv neu bauen. |
| BeatNet | 1.1.1 | Beat detection |
| FFmpeg | aktives Manifest: 6.1.1 Gyan.dev; T411-Hardware-QC bestanden | AMF encoders |
| FAISS-CPU | 1.7.4 | cp311-win_amd64 |

## 6. 📝 BRAIN UPDATE PROTOCOL
Nach jedem Major-Task: Current/Next Task + Architecture Decisions aktualisieren.
Bug-Fixes → in `CHANGELOG.md` dokumentieren, nicht hier. Ziel: < 120 Zeilen.
