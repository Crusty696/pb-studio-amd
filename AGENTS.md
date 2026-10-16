# SDD Pilot — Agent Context

Apply the Spec-Driven Development rules below during feature delivery. Enforce the lifecycle order, phase gates, conventions, and execution policy.

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
- Any violation of the Iron Rules below is CRITICAL severity.

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

## Communication Style & Core Principles

Caveman-Stil, 100% Ehrlichkeit/Live-Verifikation, Anti-Starrheit: siehe Iron Rules 10, 14, 15 weiter unten (einzige Quelle).

### SDD Phase Output Rules
Agent output MUST be concise and outcome-oriented. Apply these rules in every SDD phase:

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

Zonen, Subagent-Brief, Convergence und Skill-Mapping: `docs/agents/subagent-parallel-work.md` (nur bei parallelen Subagenten lesen). Shared-Zonen (`backend/app_state.py`, `backend/main.py`, `AGENTS.md`, `CLAUDE.md`, `GEMINI.md`) nie parallel editieren.

---

# PB Studio - Projektregeln (gemeinsame Quelle fuer Claude, Codex, Gemini)

Historie/Status: `docs/archive/CLAUDE-project-brain-history-2026-10-17.md` (nicht automatisch laden). Aktueller Stand: CHANGELOG.md, specs/, Vault.

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
## 2. ⚠️ IRON RULES (NEVER OVERRIDE)
1. **AMD DIRECTML ONLY:** NO CUDA, NO ROCm. Use `onnxruntime-directml`.
   **Einzige Ausnahme (User-Entscheid 2026-09-30, Spec 00035 T014):** LLM/VLM-Inferenz über LM Studio mit der **Vulkan**-Runtime (`llama.cpp-win-x86_64-vulkan-*`) auf der RX 7800 XT ist zulässig (z. B. `qwen3.5-9b`, Apache-2.0). ROCm bleibt auch dort verboten (auch Ollama-ROCm); alle ONNX-Pfade bleiben DirectML.
2. **DIRECTML PATTERN:** `enable_mem_pattern = False` AND `enable_cpu_mem_arena = False` (BOTH MANDATORY).
3. **PYTHON & NUMPY:** Python 3.11.x | NumPy 1.26.4 (< 2.0 strict — BeatNet).
4. **HARDWARE ENCODING:** NO NVENC. Use `h264_amf`, `hevc_amf`, `av1_amf` via FFmpeg.
5. **GPU MONITORING:** NO `pynvml`. Use `LibreHardwareMonitorLib.dll` via `pythonnet`.
6. **WINDOWS:** `pathlib.Path` oder raw strings. PowerShell für Shell-Befehle.
7. **PYTHONPATH:** Immer `PYTHONPATH=src` setzen (kein editable install).
8. **TESTS:** `testpaths = Tests` (Großbuchstabe! Windows NTFS).
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
   - CHANGELOG.md + Status-Quelle (die alte CLAUDE.md-Historie liegt in docs/archive/): aktuell
   - Bei Drift erkannt: ZUERST sync, dann melden — nicht "kommt naechste Session". **Hintergrund:** User-Direktive 2026-05-11 "ein alles muss auf dem selben stand sein wie das projekt selber ist nicht das kleinste detail darf ausgelassen oder uebersprungen werden — das ist eine eiserne regel".

12b. **AUTONOMIE-LESSONS:** Bei JEDER User-Anweisung wo der User sagt "warum machst du das nicht selbst" oder aequivalent → Eintrag in `COWORK_AUTONOMY_LESSONS.md`. Pattern-Liste in dieser Datei vor jeder Code-Aktion mental durchgehen.

   **2026-05-16 User-Direktive: AUTONOMIE-DEFAULT-ON.** Default ist autonom handeln, nicht zurueckfragen. Ich darf und MUSS ohne Nachfrage: .bat/.ps1 schreiben + selber ausfuehren (Computer-Use ODER Bash), Git add/commit/push/mv/plumbing inkl. Lock/Index-Recovery (siehe COWORK_AUTONOMY_LESSONS.md Pattern #15 Bypass-Toolkit: `mv` statt `rm`, `GIT_INDEX_FILE=/tmp/...`, `commit-tree`, `dd conv=notrunc` auf refs), Builds (dotnet, pytest, ffmpeg-Probes), Sandbox-Workarounds, Computer-Use bei Bash-Fehler, Cleanup von temp-Files. **User-Action only:** Hardware-Steckaktionen, UAC-Prompts, Reboot. Vor jeder „du musst"/„mach selber"/„autonom"-Antwort des Users: COWORK_AUTONOMY_LESSONS.md scrollen + handeln statt zurueckfragen. **Hintergrund:** 2026-05-16 Ollama-Pilot — bei `.git/index.lock` "Hard-Block" gemeldet statt Bypass-Toolkit angewandt; User: „mach das selber du hast alle tools dafür". **2026-05-16 (Korrektur):** Push war fälschlicherweise in der User-Action-Liste — User hat klargestellt dass Push autonom passiert („Dann pushe sie über mein system du hast alle tools dafür warum muss ich dir das jedes mal sagen"). Diese Regel zieht nach, siehe COWORK_AUTONOMY_LESSONS.md Pattern #17.

13. **VERIFY-BEFORE-CHANGE (User-Direktive 2026-05-15):** Vor jeder Code-Änderung muss die vorgeschlagene Lösung erst verifiziert werden, dass sie funktioniert. Skills einsetzen (`pb-master` für Cross-Module-Analyse, `code-auditor` für Static-Analysis, `full-stack-auditor` für End-to-End, `code-review`, etc.). Erst nach erfolgreichem Verifizieren wird der Code angepasst.
   - **Bug-Fix:** erst Reproduktion, dann verify dass Fix die Root-Cause adressiert (nicht nur Symptom), dann anwenden
   - **Neues Feature:** erst Cross-Module-Verdrahtung mit `pb-master` prüfen, dann implementieren
   - **Refactor:** erst Caller/Dependents via `full-stack-auditor` oder Grep prüfen, dann anwenden
   - **Config/Doc-Change:** mindestens current state lesen + auf Konflikte prüfen, dann anwenden
   - **Hintergrund:** heute (2026-05-15) mehrere Edit-Versuche an Files ohne ausreichende Vorverifizierung → mid-edit Truncations und broken Files. Diese Regel verhindert das.
14. **CAVEMAN-MODUS & TOKEN-EFFIZIENZ (Standard-Kommunikation):**
   - Standardmäßig im **Caveman-Stil** antworten (`[Subjekt] [Aktion] [Grund]. [Nächster Schritt].`).
   - Spart ~75% Token durch Weglassen von Floskeln, Wiederholungen und narrativer Prosa.
   - 100% Präzision bei Pfaden (`file:///...`), Code-Blöcken, Shell-Befehlen und Fehlermeldungen bleibt unberührt.
15. **ADAPTIVE FLEXIBILITÄT & ANTI-STARRHEITS-PRINZIP (Soft Constraints):**
   - **Keine blinden, starren Regeln**: Regeln und Standardparameter sind Leitplanken, keine Dogmen. Bei Abweichungen von der Norm flexibel anpassen.
   - **Ganzheitliche Full-Stack-Betrachtung**: Frontend (WPF XAML, C# ViewModels), Backend (FastAPI, Python), Signalverarbeitung (DSP, DirectML) und deren Verdrahtung gemeinsam verstehen.
   - **Ergonomie & Nutzen**: Prüfen ob bestehende oder geplante Ansätze echten Nutzen stiften und nutzerfreundlich sind, statt stur Parameter einzufordern.
   - **Spezialisierte Coding-Skills**: Für Audio-Video-Pacing, BPM/Beat-Grid, EDM-Groove & Cut-Point-Kalkulation steht der Full-Stack-Coding-Skill `audio-video-pacing-specialist` bereit.

## Architecture Map
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
├── ViewModels/ # 15 VMs (MVVM Toolkit; Stand 2026-10-01, INGEST-Tab entfernt)
├── Views/      # 13 XAML Views + 2 Dialoge (kein StartupUri)
├── Converters/ # NullToVisibility, InverseBool, InverseNullToVisibility
├── Resources/  # app.ico (3-size, 16/32/48px)
└── Models/     # AudioClipModel (Key+BeatCount), VideoClipModel (Thumbnail)
```

## Locked Versions
| Tool | Version | Constraint |
|------|---------|-----------|
| Python | 3.11.x | madmom/BeatNet |
| NumPy | 1.26.4 | < 2.0 strict |
| onnxruntime-directml | >=1.16.0 | GPU engine |
| PyTorch (CPU) | 2.11.0+cpu | ML tensors. **2026-08-30: venv aus dem Lock neu gebaut**, Lock und Installation stimmen wieder überein. Vorher wich sie an 14 Versionen ab (torch 2.4.1, transformers 4.49, hf-hub 0.36.2, starlette 1.0.0), hatte 13 Zusatzpakete und 6 fehlende. Die alte Umgebung liegt als `.venv-pre-lock-20260830` daneben. `torch-directml` ist ersatzlos weg — es hatte null Nutzer im Code; DirectML läuft über `onnxruntime-directml`. |
| BeatNet | 1.1.1 im Lock, **zur Laufzeit wirkungslos** | `madmom` steht nicht in `requirements.txt`, `BEATNET_AVAILABLE` ist seit dem venv-Neubau `False`. Kein Verlust: madmom 0.16.1 wirft auf NumPy ≥ 1.24 ohnehin bei jeder Datei (siehe §4). Beats kommen von librosa. |
| FFmpeg | aktives Manifest: 6.1.1 Gyan.dev; T411-Hardware-QC bestanden | AMF encoders |
| FAISS-CPU | 1.7.4 | cp311-win_amd64 |