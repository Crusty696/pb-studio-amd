# Parallele Subagent-Arbeit (aus AGENTS.md ausgelagert)

Bei Bedarf lesen, wenn mehrere Subagenten parallel arbeiten sollen.


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
| `Z-DOCS` | `docs/**`, `specs/**`, `*.md` (ausser `CLAUDE.md`, `AGENTS.md`, `GEMINI.md`: Shared-Zones) |
| `Z-INFRA` | `scripts/**`, `*.bat`, `*.ps1`, `pytest.ini`, `requirements.txt` |

`backend/app_state.py`, `backend/main.py`, `CLAUDE.md` sind **Shared-Zones** und dürfen nicht gleichzeitig von mehreren Agenten editiert werden. Sequenziell, nicht parallel.

### Subagent-Brief (verpflichtende Felder)

Jeder Spawn-Prompt enthält:

1. **ZONE:** explizite Liste (siehe Tabelle oben oder benutzerdefiniert).
2. **NON-GOAL:** was der Agent NICHT anfassen darf.
3. **TICKET-ID:** Plan-ID (z.B. `P2.1 / Spec-00007 T010`).
4. **DELIVERABLE:** konkretes Output (Code + Verify-Commands + ≤ 5-Bullet Bericht).
5. **VERIFY:** wie der Agent self-checkt (py_compile, dotnet build via separate bat, pytest-Subset).

### Convergence — Subagent-Output mergen

Nach allen Subagent-Returns:

1. Parent macht globalen `py_compile`-sweep über alle Zones.
2. Parent macht globalen `pytest Tests/ -q` (oder Cluster wenn nicht alles importierbar).
3. Parent macht `git status --short` und gruppiert per ZONE in separate Commits.
4. Commits bekommen ZONE-Präfix: `feat(audio): ...`, `fix(brain): ...`, etc.

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
