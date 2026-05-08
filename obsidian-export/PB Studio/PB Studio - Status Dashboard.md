---
title: PB Studio - Status Dashboard
project: PB Studio (AMD Premium)
type: dashboard
phase: production-verified
last-update: 2026-05-08
current-status: 🟢 production-ready
test-status: 186 passed · 9 skipped · 0 failures
brain-snapshot: 2026-03-16
iron-rules: R1–R8 ✅
tags:
  - pbstudio
  - dashboard
  - moc
cssclasses:
  - dashboard
---

> [!success] Aktueller Status — 2026-05-08
> 🟢 **Production-Ready.** Alle 9 Hauptbereiche operational. IRON-Rules R1–R8 vollständig eingehalten. Tests: 186 passed · 9 skipped · 0 failures. Aktueller Snapshot: [[2026-05-08 Gesamtstatus]].

# PB Studio AMD Premium — Status Dashboard

Map-of-Content (MoC) für alle Audits, Status-Reports, Architektur-Notizen und IRON-Rule-Tracker.

---

## 📌 Schnellzugriff

| Element | Stand | Link |
|---------|-------|------|
| **Aktueller Status** | 2026-05-08 | [[2026-05-08 Gesamtstatus]] |
| **Letzter Deep-Audit** | 2026-03-16 | Brain-Snapshot in `CLAUDE.md` |
| **Bug-Historie** | laufend | `CHANGELOG.md` (im Repo) |
| **Projekt-Wurzel** | — | `C:\Users\david\Documents\Pb_studio_AMD_version` |
| **Backend-Port** | — | `localhost:8765` |
| **Python-Env** | — | `.venv\Scripts\activate` |

---

## 🎯 Aktuelle Phase

> [!note] Phase: Production / Verified
> 20-Runden Deep-Audit am 2026-03-16 abgeschlossen. Aktueller Pipeline-Level-Audit am 2026-05-08 bestätigt 🟢 Status über alle Schichten.

**Nächster Task** (laut CLAUDE.md): End-to-End GUI-Test der WPF-App (alle 12 Views).

---

## 🟢 Status nach Bereich

| Bereich | Status | Snapshot |
|---------|:-:|------|
| Backend FastAPI | 🟢 | [[2026-05-08 Gesamtstatus#2. Backend FastAPI]] |
| Audio-Pipeline | 🟢 | [[2026-05-08 Gesamtstatus#4. Audio-Pipeline]] |
| Video-Pipeline | 🟢 | [[2026-05-08 Gesamtstatus#5. Video-Pipeline]] |
| AI/ML & Pacing | 🟢 | [[2026-05-08 Gesamtstatus#6. AI ML & Pacing]] |
| Render-Pipeline | 🟢 | [[2026-05-08 Gesamtstatus#7. Render-Pipeline FFmpeg AMF]] |
| Core / VRAM / Data | 🟢 | [[2026-05-08 Gesamtstatus#3. Core VRAM Data]] |
| WPF Frontend | 🟢 | [[2026-05-08 Gesamtstatus#8. WPF-Frontend & E2E-Verdrahtung]] |
| IRON-Compliance | 🟢 | [[2026-05-08 Gesamtstatus#9. IRON-Rule-Compliance]] |
| Test-Suite | 🟢 | [[2026-05-08 Gesamtstatus#11. Test-Status]] |

---

## ⛔ IRON-Rules Tracker

| Regel | Stand | Wirksam in |
|-------|:-:|------------|
| **R1** AMD/DML only (kein CUDA/ROCm) | ✅ | Alle Pipelines |
| **R2** beide DML-Flags (mem_pattern + cpu_arena = False) | ✅ | RAFT, Moondream, SigLIP, CLAP, Demucs |
| **R3** Python 3.11 + NumPy 1.26.4 | ✅ | requirements.txt (gepinnt) |
| **R4** AMF-Encoder (h264/hevc/av1_amf) | ✅ | render_engine.py:70, proxy_service.py:39 |
| **R5** LibreHardwareMonitor (kein pynvml) | ✅ | system_monitor.py via pythonnet |
| **R6** pathlib / Windows-Pfade | ✅ | path_helpers.py, App.xaml.cs |
| **R7** PYTHONPATH=src | ✅ | PythonBridgeService.cs (WPF-Bootstrap) |
| **R8** `Tests/` Großbuchstabe | ✅ | pytest.ini |

---

## 📚 Architektur-Module

### Backend Routers
- project · audio · video · pacing · render · brain · events · health

### Audio-Pipeline
- BeatDetector (BeatNet 1.1.1, CPU)
- WaveformAnalyzer (3-Band RMS, librosa Butterworth O4)
- KeyDetector (Krumhansl-Kessler via librosa)
- StructureAnalyzer (Intro/Verse/Chorus/Drop)
- SpectralAnalyzer
- Demucs/MDX Stem-Separation (DirectML, optional)
- CLAP Audio-Embedding (DirectML, optional)

### Video-Pipeline
- FrameExtractor (OpenCV)
- RAFT Optical Flow (DirectML)
- PySceneDetect 0.6.3
- Moondream2 FP16 (DirectML)
- SigLIP SO400M-Patch14-384 (DirectML, 1152d)
- AutoTagger (Keyword-Matching)

### AI/ML & Pacing
- SmartDirector (`ai/smart_director.py`)
- SemanticMatcher (FAISS-CPU + Variety/Continuity)
- MoodGenerator + MotionPreference
- BrainService (Bayes-Bernoulli, 4-Klick-Feedback)

### Render
- FFmpeg AMF (hevc/h264/av1) + Concat-Demuxer + Audio-Mux
- RenderQueue mit SQLite-Persistenz + Resume-on-Crash

### WPF Frontend (12 Views)
- ProjectOverview · MediaIngest · AudioLibrary · VideoLibrary · Director
- Timeline · Production · Brain · Settings · VramTelemetry · Anchor
- LearningSessionDialog (Modal)

---

## 🚧 Offene Punkte

> [!todo] Empfohlene nächste Schritte
> - [ ] End-to-End-GUI-Test (`auto-qa-loop`-Skill über alle 12 Views)
> - [ ] Konsolidierung `pacing/smart_director.py` → `ai/smart_director.py`
> - [ ] WPF `NavigationService` entfernen (DEAD CODE)
> - [ ] `audio/streaming_analyzer.py` für Mixe >60min implementieren
> - [ ] Messenger-Keys auf strongly-typed Records migrieren
> - [ ] `data/database_core.py` Rollback-Semantik validieren

---

## 🟡 Legacy-Bereiche

| Bereich | Status | Aktion |
|---------|:-:|--------|
| `audio/streaming_analyzer.py` | 🔴 Stub | implementieren |
| `pacing/smart_director.py` | 🟡 Alias | Konsolidierung |
| `ai/clap_wrapper.py` (ONNX) | 🟡 | ONNX-Export finalisieren |
| `core/task_queue.py` | 🟡 | bei Bedarf erweitern |
| `services/final_renderer.py` | 🟡 | Mux-Integration |
| WPF `NavigationService` | 🟡 | Dead Code entfernen |

---

## 🗂️ Snapshot-Historie

| Datum | Typ | Link | Notiz |
|-------|-----|------|-------|
| 2026-05-08 | Pipeline-Audit | [[2026-05-08 Gesamtstatus]] | Aktueller Stand · 🟢 |
| 2026-03-16 | Deep-Audit (R16–R20) | im `CHANGELOG.md` | 186 passed · 0 failures |
| 2026-03-11 | HIGH-001..006 Fixes | im `CHANGELOG.md` | — |
| 2026-03-09 | BUG-001..046 archiviert | im `CHANGELOG.md` | — |

---

## 🔗 Externe Referenzen

- **Repo:** `C:\Users\david\Documents\Pb_studio_AMD_version`
- **Projekt-Brain (CLAUDE.md):** lokale Datei im Repo-Root
- **Bug-Historie:** `CHANGELOG.md` im Repo-Root
- **Modelle:** `models/` (RAFT, Moondream, SigLIP, CLAP, Demucs)

---

## 📋 Tags

`#pbstudio` · `#status` · `#audit` · `#amd` · `#directml` · `#fastapi` · `#wpf` · `#dashboard` · `#moc`
