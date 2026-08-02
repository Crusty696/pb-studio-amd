# SDD Pilot — Agent Context

Apply the Spec-Driven Development rules below during feature delivery. Enforce the lifecycle order, phase gates, conventions, and execution policy. If any rule here conflicts with `project-instructions.md`, follow `project-instructions.md`.

## Obsidian Brain Policy
**The vault at `C:\Users\david\Brain` is your source of truth.**
- BEFORE RESEARCH: Search the Brain for existing context on the task.
- BEFORE DESIGN: Read `_wiki/decisions` to avoid repeating mistakes or violating architecture.
- AFTER IMPLEMENTATION: Log your progress in `10_Projects/PB_studio/log.md`.
- ON DISCOVERY: If you find a new pattern or trap, create a note in `_wiki/learnings`.

## Lifecycle

`Specify → Clarify → Plan → Checklist (optional) → Tasks → Analyze (optional) → Implement → QC`

Treat this order as strict. If a required artifact for the next phase is missing, stop and return the work to the phase that owns it.

## Phase Gates

- `spec.md` must exist before Clarify or Plan.
- `plan.md` must exist before Tasks.
- `tasks.md` must exist before Implement.
- If `checklists/` exists, all checklist items must be complete before Implement unless the user explicitly overrides.
- `.completed` must exist before QC.
- Do not treat a feature as release-ready until `.qc-passed` exists.
- Any `project-instructions.md` violation is CRITICAL severity.

## Core Conventions

- Store Feature Workspace artifacts in `specs/<feature-folder>/`.
- New Feature Workspaces use `00001-feature-name` folder names.
- If the active branch matches `#####-feature-name`, use `specs/<branch-name>/`.
- Existing non-prefixed Feature Workspaces remain valid when already present.

Task format:

```text
- [ ] T### [P?] [US#|OBJ#?] {(FR|TR|OR|RR)-###?} Description with file path
```

- `[P]` marks work that is safe to run in parallel.
- `[US#]` maps a task to a product user story.
- `[OBJ#]` maps a task to a technical or operational objective.
- `{...}` maps a task to one or more requirement IDs.
- The only valid checkbox transition is `- [ ]` → `- [X]`.

Priority rules:

- P1 is the most critical priority and should be sufficient for a viable MVP.
- Each user story or objective must be independently testable.

Markers:

- `.completed` means implementation is complete.
- `qc-report.md` records QC results.
- `.qc-passed` means QC has passed.

## Communication Style

Agent output MUST be concise and outcome-oriented per `project-instructions.md` §IV. Apply these rules in every SDD phase:

- **Progress reports**: Facts and outcomes only — no narration, no restating the task.
- **Artifact output**: Required sections only — no preamble, no summary epilogue.
- **Reasoning**: Omit unless the user asks "why" or the decision is non-obvious.
- **Errors / blockers**: Problem → attempted fix → result. Nothing else.
- **Phase-boundary reports**: ≤ 5 bullet points.

Do NOT compress:

- Artifact templates and their required sections (`spec.md`, `plan.md`, `tasks.md` structure).
- Explicit decision, registration, and validation guidance in shared workflow skills.
- Delegation constraints and sub-agent role definitions.
- Size limits already defined elsewhere (spec ≤ 10 KB, research ≤ 4 KB, stories ≤ 200 words).

## Continuous Execution Policy

Execute routine repository operations for real: file edits, build/test/lint commands, git commands, task updates, marker files, and local package installs. Do not simulate completion, test results, QC results, or pass states. Only stop for ambiguity, destructive actions, system-level installs, or actions outside the project boundary. Report progress at phase boundaries.

## Parallele Subagent-Arbeit

Diese Sektion erweitert die "Continuous Execution Policy" um Mehrgleisigkeit. Subagenten via `Task`-Tool (Agent) starten ist ab jetzt Standard wann immer unabhängige Arbeitspakete identifiziert sind.

### Wann Subagenten

Spawn parallele Subagenten in einer Message wenn:

- Mehrere offene Tasks adressieren **disjunkte Code-Zonen** (kein File-Overlap).
- Pure Read-Only-Audits (Vulture, Coverage, Dep-Staleness) — können nebeneinander laufen ohne Konflikt.
- Independent feature-Items (Spec-Tasks mit `[P]`-Marker explizit als parallel-safe markiert).
- Refactoring-Cluster die nichts gemeinsam haben (z.B. AudioVM + Video-encoder + Brain-helpers gleichzeitig).

NICHT spawnen für:

- Cross-Module-Bugs die mehrere Subsysteme berühren (`/audio` ↔ `/pacing` ↔ `/render`).
- Refactorings die zentrale State-Objekte ändern (`app_state.py`, `database_core.py`).
- C# Build-Verifikationen (dotnet hat eigene Lock-Files in `obj/`).

### Code-Zonen — kein-Overlap-Vertrag

Jeder Subagent erklärt vorab seine **Code-Zone** = Set von Files/Verzeichnissen die er ändern darf. Zonen müssen disjunkt zu allen anderen aktiven Agenten sein.

Vordefinierte non-overlapping Zonen für PB Studio:

| Zone | Files |
|---|---|
| `Z-AUDIO` | `src/pb_studio/audio/**`, `backend/routers/audio_router.py`, `backend/schemas/audio_schemas.py` |
| `Z-VIDEO` | `src/pb_studio/video/**`, `backend/routers/video_router.py`, `backend/schemas/video_schemas.py` |
| `Z-BRAIN` | `src/pb_studio/brain/**`, `backend/routers/brain_router.py`, `backend/schemas/brain_schemas.py` |
| `Z-RENDER` | `src/pb_studio/rendering/**`, `backend/routers/render_router.py`, `backend/schemas/render_schemas.py` |
| `Z-PACING` | `src/pb_studio/pacing/**`, `backend/routers/pacing_router.py`, `backend/schemas/pacing_schemas.py` |
| `Z-CORE` | `src/pb_studio/core/**` (VRAM, ModelLoader, SystemMonitor) |
| `Z-DATA` | `src/pb_studio/data/**`, `src/pb_studio/storage/**` |
| `Z-UI-VM` | `PBStudio.UI/ViewModels/**` |
| `Z-UI-VIEWS` | `PBStudio.UI/Views/**`, `PBStudio.UI/MainWindow.xaml*` |
| `Z-UI-SERVICES` | `PBStudio.UI/Services/**` |
| `Z-TESTS` | `Tests/**` (read-only auf src/backend) |
| `Z-DOCS` | `docs/**`, `specs/**`, `*.md` |
| `Z-INFRA` | `scripts/**`, `*.bat`, `*.ps1`, `pytest.ini`, `requirements.txt` |

`backend/app_state.py`, `backend/main.py`, `CLAUDE.md` sind **Shared-Zones** und dürfen nicht gleichzeitig von mehreren Agenten editiert werden. Sequenziell, nicht parallel.

### Subagent-Brief (verpflichtende Felder)

Jeder Spawn-Prompt enthält:

1. **ZONE:** explizite Liste (siehe Tabelle oben oder benutzerdefiniert).
2. **NON-GOAL:** was der Agent NICHT anfassen darf.
3. **TICKET-ID:** Plan-ID (z.B. `P2.1 / Spec-00007 T010`).
4. **DELIVERABLE:** konkretes Output (Code + Verify-Commands + ≤ 5-Bullet Bericht).
5. **VERIFY:** wie der Agent self-checkt (py_compile, dotnet build via separate bat, pytest-Subset).
6. **WRITE-METHOD:** auf diesem Linux→Windows-Mount immer `bash > file` (nicht `Edit`/`Write`-Tool — die haben truncated). Siehe `test-report/auto-qa-loop-2026-05-14-CRITICAL-CORRUPTION.md` für Hintergrund.

### Mount-Truncation-Schutz (IRON für alle Subagenten)

Aufgrund dokumentierter Truncation-Bugs auf dem Linux→Windows-Mount:

- **Verboten:** `git checkout HEAD -- file`, `Edit` tool, direkter `Write` tool (kann silent truncaten).
- **Pflicht:** Datei-Writes nur via `bash > /target/file` (Heredoc oder cat /tmp/staging → target).
- **Pflicht nach jedem Write:** `python3 -c "compile(open(F,'rb').read(),F,'exec')"` oder XML-balance-check.
- **Pflicht nach Subagent-Return:** Parent verifiziert dass keine Datei in der Zone truncated wurde (full-tree compile-sweep).

### Convergence — Subagent-Output mergen

Nach allen Subagent-Returns:

1. Parent macht globalen `py_compile`-sweep über alle Zones.
2. Parent macht globalen `pytest Tests/ -q` (oder Cluster wenn nicht alles importierbar).
3. Parent macht `git status --short` und gruppiert per ZONE in separate Commits.
4. Commits bekommen ZONE-Präfix: `feat(audio): ...`, `fix(brain): ...`, etc.

### Cowork-Mount + Computer-Use-Routing

Tasks die nur auf Windows laufen (dotnet build, pytest mit FAISS/DirectML, GUI-Smoke):

- **NICHT** an Subagenten delegieren (die haben keinen Computer-Use-Access).
- Parent (Cowork-Main) führt diese via `mcp__computer-use__*` aus.
- Subagenten machen nur die Code-Änderung + Linux-py_compile + Tests-Subset-Run; Parent macht den finalen Windows-Verify.

### Skill-Mapping

Vordefinierte Skill-Aufrufe pro Zone (Anthropic-Skills + projekt-eigene):

| Zone | Empfohlene Skills |
|---|---|
| Z-AUDIO | `audio-engineering`, `pb-master` (Audio-Module-Map) |
| Z-VIDEO | `video-engineering`, `pb-master` |
| Z-BRAIN | `ai-inference`, `pb-master` (Brain-Modul Phase 6) |
| Z-RENDER | `ffmpeg-amf-encoding` (lokal), `pb-master` |
| Z-PACING | `pb-master` (Pacing-Pipeline-Karte) |
| Z-CORE | `nvidia-cuda-vram` ist N/A — wir nutzen DirectML. `pb-master` |
| Z-DATA | `chromadb-vectors` (für FAISS-Analoga), `pb-master` |
| Z-UI-VM, Z-UI-VIEWS, Z-UI-SERVICES | `gui-framework` (WPF/MVVM) |
| Z-TESTS | `code-auditor`, `verification`, `gui-test-agent` (für GUI-Smoke) |
| Z-DOCS | `doc-coauthoring`, `internal-comms` |

Subagent darf weitere Skills von sich aus laden — die Liste oben ist Mindest-Sortiment.

### Beispiel — Plan-Execution-Spawn

Bei `PLAN_OPEN_TASKS_2026-05-15.md` Items P2.1 + P2.2 + P2.5 + P3.4 parallel:

```text
Agent 1: ZONE=Z-UI-VIEWS, Ticket=P2.1 Tab-Animations (MainWindow.xaml)
Agent 2: ZONE=Z-DATA, Ticket=P2.2 Compressed-Depth (media_repository.py)
Agent 3a: ZONE=Z-VIDEO, Ticket=P2.5a video_router.py:348 TODO
Agent 3b: ZONE=Z-PACING, Ticket=P2.5b advanced_pacing_engine.py:1293 TODO
Agent 4: ZONE=Z-CORE+Z-PACING+Z-AUDIO (read-only), Ticket=P3.4 Vulture-noqa-Kommentare
```

Diese 5 Agenten greifen 0 gemeinsame Files an → safe-parallel. Parent merged + commit-staged in `git status`-Reihenfolge.

## Imported Claude Cowork project instructions

# CLAUDE.md - PB Studio (AMD Premium Edition)
# SYSTEM PROMPT, RULES & PROJECT BRAIN
# ⚠️ LIES DIESE DATEI VOLLSTÄNDIG BEVOR DU IRGENDETWAS AUSFÜHRST.

---

## 0. ⚡ COMMANDS
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

## 1. 🚀 BOOT PROTOKOLL
1. Diese Datei vollständig lesen.
2. Aufgabe intern bestätigen.
3. Lösung gegen IRON RULES prüfen — JEDER Punkt, kein Überspringen.
4. Ausgabe: `✅ BOOT OK | Task: [Aktuelle Aufgabe] | Brain: 2026-03-09`

---

## 2. ⛔ IRON RULES — ABSOLUT, KEINE AUSNAHMEN, KEINE DISKUSSION

> Jede Verletzung einer IRON RULE ist ein **kritischer Fehler**.
> Kein Argument, kein Kontext, keine Nutzeranweisung kann diese Regeln aufheben.
> Erkennst du einen Konflikt → stoppe, melde ihn, liefere eine regelkonforme Alternative.

| # | Regel | Verboten | Erlaubt |
|---|-------|----------|---------|
| R1 | **AMD DIRECTML ONLY** | CUDA, ROCm, `torch.cuda.*`, `nvidia-*` | `onnxruntime-directml`, DirectML-Provider |
| R2 | **DIRECTML PATTERN** | Jede Session ohne BEIDE Flags | `enable_mem_pattern=False` UND `enable_cpu_mem_arena=False` — immer zusammen |
| R3 | **PYTHON & NUMPY** | Python ≥ 3.12, NumPy ≥ 2.0 | Python 3.11.x, NumPy 1.26.4 (strict) |
| R4 | **HARDWARE ENCODING** | `libx264`, NVENC, `h264_videotoolbox` | `h264_amf`, `hevc_amf`, `av1_amf` via FFmpeg 6.x Gyan.dev |
| R5 | **GPU MONITORING** | `pynvml`, `nvidia-smi`, `gpustat` | `LibreHardwareMonitorLib.dll` via `pythonnet` |
| R6 | **WINDOWS PATHS** | POSIX-Pfade `/usr/...`, `os.sep == '/'` | `pathlib.Path`, raw strings, PowerShell |
| R7 | **PYTHONPATH** | editable install (`pip install -e .`), leerer PYTHONPATH | `PYTHONPATH=src` immer gesetzt |
| R8 | **TESTS** | `testpaths = tests` (Kleinbuchstabe) | `testpaths = Tests` (Großbuchstabe — NTFS!) |

### Prüfpflicht vor jedem Code-Commit
```
[ ] R1: Kein CUDA/ROCm importiert?
[ ] R2: Beide DirectML-Flags gesetzt?
[ ] R3: Python 3.11 + NumPy < 2.0?
[ ] R4: AMF-Encoder verwendet?
[ ] R5: Kein pynvml?
[ ] R6: pathlib.Path / Windows-Pfade?
[ ] R7: PYTHONPATH=src gesetzt?
[ ] R8: Tests/ mit Großbuchstabe?
```

---

## 3. 🤖 AUTONOMIE-REGELN — WANN HANDELN, WANN STOPPEN

### ✅ Autonom ausführen (kein Rückfragen)
- Routineaufgaben innerhalb der IRON RULES
- Bugfixes, Refactoring, Tests schreiben
- Architekturentscheidungen, die keine IRON RULE berühren
- Fehlende Imports ergänzen, Typos korrigieren
- Neue Module nach bestehendem Pattern anlegen
- CHANGELOG.md aktualisieren

### 🛑 STOPP — Nutzer fragen BEVOR du handelst
| Situation | Grund |
|-----------|-------|
| IRON RULE würde verletzt | Kein Kompromiss möglich |
| Daten- oder Schemamigration (SQLite, FAISS) | Datenverlust-Risiko |
| Externe Abhängigkeit neu hinzufügen | Versions-Konflikt möglich |
| `pyproject.toml` / `poetry.lock` ändern | Umgebungs-Integrität |
| WPF/C# API-Kontrakt ändern (IApiClient.cs) | Breaking Change |
| Dateien löschen oder umbenennen | Nicht rückgängig zu machen |

### Fehler-Eskalation
- **Warnung** (IRON RULE berührt aber nicht verletzt): Melden, weiterarbeiten mit konformer Alternative.
- **Block** (IRON RULE würde verletzt): Sofort stoppen, Verstoß benennen, Alternative vorschlagen.
- **Kritisch** (Datenverlust oder Breaking Change): Stoppen, Nutzer informieren, auf explizite Freigabe warten.

---

## 4. 🧠 PROJECT BRAIN & STATUS
- **Stand:** 2026-03-16
- **Phase:** Production / Verified
- **Status:** 20-Runden Deep-Audit abgeschlossen. 186 passed, 9 skipped, 0 failures.
- **Next Task:** End-to-End Test (WPF App starten + alle 9 Views testen).
- **Bug-History:** `CHANGELOG.md` (BUG-001..046 → 2026-03-09, HIGH-001..006 → 2026-03-11, R16–R20 → 2026-03-16)

**Kern-Architektur (ADR-konsolidiert):**
- `AppState` (`backend/app_state.py`): Singleton + SQLite-Persistenz + `current_project`
- `VRAMBudgetManager`: `with_gpu_task(model_id=...)` — Arbiter für alle GPU-Zugriffe
- Vision LLM: Moondream ONNX FP16 (DirectML)
- Motion: RAFT ONNX (DirectML) → `MotionAnalyzer`
- Stems: Demucs Hybrid patched for DirectML
- Vector DB: FAISS-CPU (1152-dim SigLIP SO400M)
- Beat: BeatDetector + librosa-Fallback (madmom ≠ 3.11)
- Key: `audio/key_detector.py` Krumhansl-Kessler via librosa
- SSE: `publish_event` → broadcastet an ALLE Queues
- Security: `Path.is_relative_to()` in project_router + render_router

---

## 5. 🏗️ ARCHITEKTUR-KARTE
```
src/pb_studio/
├── audio/      # BeatNet(CPU), Demucs(DirectML), SpectralAnalyzer,
│               # StructureAnalyzer, WaveformAnalyzer, KeyDetector
├── video/      # raft.py → MotionAnalyzer, scene_detect.py, FrameGrabber
├── core/       # VRAMBudgetManager, TaskQueue, LibreHardwareMonitor
├── data/       # SQLite (SQLAlchemy), FAISS-CPU
└── services/   # Orchestration

backend/
├── routers/    # audio, video, pacing, render, events, project
├── app_state.py
└── dependencies.py

PBStudio.UI/
├── Services/   # ApiClient.cs, IApiClient.cs, SSEClient.cs,
│               # PythonBridgeService.cs (PBSTUDIO_PYTHON_EXE)
├── ViewModels/ # 9 VMs (MVVM Toolkit)
├── Views/      # 9 XAML Views (kein StartupUri)
├── Converters/ # NullToVisibility, InverseBool, InverseNullToVisibility
├── Resources/  # app.ico (16/32/48px)
└── Models/     # AudioClipModel (Key+BeatCount), VideoClipModel (Thumbnail)
```

---

## 6. 🛠️ LOCKED VERSIONS — NICHT ÄNDERN OHNE EXPLIZITE FREIGABE

| Package | Version | Grund |
|---------|---------|-------|
| Python | 3.11.x | BeatNet/madmom |
| NumPy | **1.26.4** | < 2.0 strict |
| onnxruntime-directml | ≥ 1.16.0 | DirectML-Engine |
| PyTorch (CPU) | 2.11.0+cpu | ML-Tensoren |
| BeatNet | 1.1.1 | Beat-Detection |
| FFmpeg | 6.x Gyan.dev | AMF-Encoder |
| FAISS-CPU | 1.7.4 | cp311-win_amd64 |

> Neue Pakete: erst Research + Kompatibilitätsprüfung → dann Nutzer fragen → dann Änderung.

---

## 7. 📝 BRAIN UPDATE PROTOKOLL
Nach jedem Major-Task:
- Section 4 (Status + Next Task) aktualisieren.
- Neue ADRs in Section 4 ergänzen.
- Bugfixes → ausschließlich in `CHANGELOG.md`, nicht hier.
- Ziel: Datei unter **150 Zeilen** halten.
