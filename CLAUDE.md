# CLAUDE.md - PB Studio (AMD Premium Edition)
# SYSTEM PROMPT, RULES & PROJECT BRAIN

Read this file ENTIRELY before executing any tasks. Do not look for other .agent files.

---

## 0. ⚡ COMMANDS (copy-paste ready)
```powershell
# Python Backend starten
.venv\Scripts\activate
$env:PYTHONPATH = "src"
python -m uvicorn backend.main:app --port 8765

# Tests ausführen
pytest Tests/ -x -q

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

---

## 3. 🧠 PROJECT BRAIN & CURRENT STATUS
- **Date:** 2026-05-11
- **Phase:** Production / Verified + Brain-Modul Phase 6 + Pipeline-Lueken Plan abgeschlossen + Timeline-Integrity Audit/Fixes + Deep-Audit Sweep laufend
- **Status:** Tests 503 passed / 8 skipped / 0 failed (vorher 239 → 264 neue durch K+M+N+TI). Session 2026-05-11 21+ commits. Plan `~/.claude/plans/2026-05-09-pipeline-luecken-fix.md` vollstaendig: Phase K 5/5, M 8/8, N 7/8 (N1 user-skipped → TI-Audit stattdessen), Timeline-Integrity-Audit 12 Findings (1 CRITICAL, 4 HIGH) — alle 7 priorisierten Fixes deployed. **Wurzel des "chaotischen Pacing"-User-Konzerns:** L-TI-1 — `ClipSelector.select_clip(prompt=...)` crashte live → Pacing fiel auf round-robin → 14 cuts statt 2184. Fix `700fedd`.
- **Next Task:** Deep-Audit Sweep konsolidieren (6 parallele Reports: Audio/Video/Render/Frontend/State+DB+Cache/GPU+Threading) → Priorisierte Fix-Liste → Plan.
- **Bug-History:** siehe `CHANGELOG.md` (BUG-001..046 archiviert 2026-03-09, HIGH-001..006 gefixt 2026-03-11, R12–R20 gefixt 2026-03-16, Brain-Modul Phase 0–6 abgeschlossen 2026-05-06, BUG-200..205 gefixt 2026-05-08/09, **2026-05-11 Pipeline-Lueken-Plan komplett abgearbeitet** L-K1..K5 + L-M1..M8 + L-N2..N8 + L-TI-1..TI-7).

**Kern-Architektur-Entscheidungen:**
- *AppState:* `backend/app_state.py` Singleton + SQLite-Persistenz + `current_project` (ADR-001+003)
- *VRAM Arbiter:* `with_gpu_task(model_id=...)` prüft VRAMBudgetManager
- *Vision LLM:* Moondream ONNX (FP16) via DirectML
- *Motion Analysis:* RAFT ONNX via DirectML (`raft.py → MotionAnalyzer`)
- *Stem Separation:* Demucs Hybrid patched for DirectML
- *Vector DB:* FAISS-CPU (1152-dim SigLIP SO400M embeddings) + sqlite-vec (Brain-Modul KNN)
- *Beat Detection:* BeatDetector mit librosa-Fallback (madmom nicht installierbar auf 3.11)
- *Key Detection:* `src/pb_studio/audio/key_detector.py` Krumhansl-Kessler via librosa
- *SSE Fan-out:* `publish_event` broadcastet an ALLE registrierten Queues
- *Path-Traversal-Schutz:* `Path.is_relative_to()` in project_router + render_router
- *Brain-Modul:* 17 Bridge-Achsen · Beta-Bernoulli WeightStore · 5-Level Hierarchical Backoff · CLAP + SigLIP-2 via torch-directml · 6 REST-Endpoints `/brain/{suggest,feedback,learning_session,stats,reset,explain}` · WPF HIRN-Tab + Confidence-Balken

---

## 4. 🏗️ ARCHITECTURE MAP
```
src/pb_studio/
├── audio/      # BeatNet(CPU), Demucs(DirectML), SpectralAnalyzer, StructureAnalyzer,
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
| FFmpeg | 6.x Gyan.dev | AMF encoders |
| FAISS-CPU | 1.7.4 | cp311-win_amd64 |

## 6. 📝 BRAIN UPDATE PROTOCOL
Nach jedem Major-Task: Current/Next Task + Architecture Decisions aktualisieren.
Bug-Fixes → in `CHANGELOG.md` dokumentieren, nicht hier. Ziel: < 120 Zeilen.
