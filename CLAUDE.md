# CLAUDE.md - PB Studio (AMD Premium Edition)
# SYSTEM PROMPT, RULES & PROJECT BRAIN

Read this file ENTIRELY before executing any tasks. Do not look for other .agent files.

---

## 0. ⚡ COMMANDS (copy-paste ready)
```powershell
# Python Backend starten
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
4. Output confirmation: "✅ BOOT OK | Task: [Current Task] | Brain: 2026-05-11"

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
- **Date:** 2026-07-30 (Reparaturplan 00013, OBJ-71 T368)
- **Phase:** 🔴 End-QC BLOCKED; nicht release-ready.
- **Status (2026-07-30 — GPU-/Provider-/Analyse-Reparatur T340–T368):**
  - DirectML, VRAM und LHM verwenden RX 7800 XT Index `1`, LUID
    `0x00000000_0x0001185b`; LHM-0.9.6-Trust ist manifest- und hashgebunden.
  - Liveinventar, providergebundene Selection Receipts, begrenztes Failover,
    persistenter Modellwechsel und nullable `SceneInfo.Confidence` sind repariert.
  - Verifiziert: **1086 passed/12 skipped/0 failed**, WPF Release **0/0**,
    Provider-/GUI-E2E PASS; H.264 und HEVC je 190.051 Frames, Full-Decode,
    106/106 Segmente und keine Schwarz-/Freezeintervalle.
  - **Blocker T363:** Audio läuft auf der RX 7800 XT; RAFT/SigLIP benötigen
    mit den vorhandenen ONNX-Exports verbotene CPU-Knoten. Freigegebene
    Moondream-/CLAP-ONNX-Assets fehlen.
  - `.completed` ist nach post-fix T360 gültig; `.qc-passed` ist abwesend.
  - T369: Secret-Scan und D07 PASS; sieben PB-Zonencommits und ausschließlich
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
  - **Onset-Caching-Fix umgesetzt** (User-Entscheid: größere Lösung statt Workaround): Audio-Pipeline (`audio_router.py`) berechnet jetzt Onset/Kick/Snare/HiHat-Trigger-Kandidaten einmalig beim `/audio/analyze`-Lauf (gleiche librosa-Parameter wie der Live-Fallback), persistiert über `app_state.py` (JSON-Blob, kein DB-Schema-Migration nötig), injiziert via `pacing_service._inject_cached_into_engine` in die Pacing-Engine. `advanced_pacing_engine.py`: toter SessionManager-Import entfernt, Audio-Load-Gate korrigiert (lädt Audio nur noch, wenn für eine AKTIVE Trigger-Gewichtung wirklich kein Cache existiert — sonst RAM-Optimierung für lange DJ-Mixes erhalten), `_build_triggers_from_cache` um Kick/Snare/HiHat erweitert. Neue Schema-Felder in `AudioAnalysisResult` (`onset_times`/`kick_times`/`snare_times`/`hihat_times`), C#-DTOs regeneriert.
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
- **Next Task:** DirectML-only-kompatible RAFT-/SigLIP-Exports und freigegebene,
  gehashte Moondream-/CLAP-ONNX-Assets bereitstellen; danach T363 und T368
  erneut ausführen.
- **Bug-History:** siehe `CHANGELOG.md` (BUG-001..046 archiviert 2026-03-09, HIGH-001..006 gefixt 2026-03-11, R12–R20 gefixt 2026-03-16, Brain-Modul Phase 0–6 abgeschlossen 2026-05-06, BUG-200..205 gefixt 2026-05-08/09, **2026-05-11 Pipeline-Lueken-Plan komplett abgearbeitet** L-K1..K5 + L-M1..M8 + L-N2..N8 + L-TI-1..TI-7, **2026-05-21/22 QA-Loop+Hybrid-Audit** 3 Code-Fixes + 4 Hybrid-Bypass-Fixes, **2026-05-30 Epic 00013 Audit & Optimierungen**, **2026-06-09 Stems-Analyse-Bug & htdemucs Crash behoben**, **2026-06-10 Full-Audit + Epic 00015 K1–K11**, **2026-06-12 Audit-Fix Phase 3 AP1–AP5**).


**Kern-Architektur-Entscheidungen:**
- *AppState:* `backend/app_state.py` Singleton + SQLite-Persistenz + `current_project` (ADR-001+003)
- *VRAM Arbiter:* `with_gpu_task(model_id=...)` prüft VRAMBudgetManager
- *Vision LLM:* Moondream ONNX (FP16) via DirectML
- *Motion Analysis:* RAFT ONNX via DirectML (`raft.py → MotionAnalyzer`)
- *Stem Separation:* htdemucs runs on CPU because PyTorch CPU is used in the pinned environment. DirectML acceleration only applies to ONNX-MDX paths in StemSeparator.
- *Vector DB:* FAISS-CPU (1152-dim SigLIP SO400M embeddings) + sqlite-vec (Brain-Modul KNN)
- *Beat Detection:* BeatDetector mit librosa-Fallback (madmom nicht installierbar auf 3.11)
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
| PyTorch (CPU) | 2.4.1+cpu | ML tensors |
| BeatNet | 1.1.1 | Beat detection |
| FFmpeg | aktives Manifest: 8.0.1 Gyan.dev; 6.1.1 erst nach T332-Hardware-QC | AMF encoders |
| FAISS-CPU | 1.7.4 | cp311-win_amd64 |

## 6. 📝 BRAIN UPDATE PROTOCOL
Nach jedem Major-Task: Current/Next Task + Architecture Decisions aktualisieren.
Bug-Fixes → in `CHANGELOG.md` dokumentieren, nicht hier. Ziel: < 120 Zeilen.
