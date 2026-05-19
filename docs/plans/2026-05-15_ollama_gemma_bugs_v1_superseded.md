# MEHR-PHASEN-PLAN — Bug/Task-Audit + Ollama/Gemma4-Integration
**Datum:** 2026-05-15
**Verfasser:** Claude (Cowork-Session, Brain-Stand 2026-05-15)
**Status:** ENTWURF — zur Freigabe durch David vorgelegt
**Iron-Rule-Compliance:** R1 (DirectML only), R10 (100% Honesty)

---

## 0. ⚡ KRITISCHE EHRLICHKEITS-ERKENNTNIS — bitte zuerst lesen

Ich habe systematisch alles untersucht (keine Annahmen). Folgendes habe ich VERIFIZIERT:

### Was ich GEPRÜFT habe (mit Tool + Treffer-Anzahl):
| Suche | Bereich | Treffer |
|-------|---------|---------|
| `ollama\|Ollama` | `src/` | **0 Treffer** |
| `ollama\|Ollama` | `backend/` | **0 Treffer** |
| `ollama\|Ollama` | `PBStudio.UI/` | **0 Treffer** |
| `ollama\|Ollama` | `Tests/` | **0 Treffer** |
| `ollama\|Ollama` | `scripts/` + `tools/` | **0 Treffer** |
| `ollama\|Ollama` | `requirements.txt` | **0 Treffer** |
| `ollama\|Ollama` | `.venv/Lib/site-packages/ollama*` | **0 Treffer (nicht installiert)** |
| `gemma\|Gemma` | `src/` + `backend/` + `Tests/` | **0 Treffer** |
| `gemma\|Gemma` | `config.json` + `requirements.txt` | **0 Treffer** |
| `11434\|api/generate\|api/chat` | aktiver Code | **0 Treffer** |
| Ollama-Referenzen im `archive/` | (Legacy, deaktiviert) | 4 Treffer — alles archivierter Code, kein aktiver Pfad |

### Was das bedeutet — 100% ehrlich:
**Ollama und Gemma sind AKTUELL NICHT in der PB-Studio-Codebasis integriert.**
- `config.json` zeigt: `"vision_model": "moondream2_fp16"`
- Vision-LLM ist ausschließlich Moondream2 ONNX (DirectML) via `src/pb_studio/video/moondream.py`
- Es gibt KEIN HTTP-Adapter, KEIN Ollama-Client-Modul, KEIN Gemma-Loader im aktiven Code

### Folge — drei mögliche Interpretationen deiner Aussage:
**Interpretation A** (am wahrscheinlichsten): Du hast Ollama als **externes Tool** auf Windows neu installiert (z. B. `winget install Ollama.Ollama`) — als **VORBEREITUNG** für eine zukünftige Integration in PB Studio. Die Integration selbst existiert noch nicht und muss in diesem Plan **neu entwickelt** werden.
**Interpretation B**: Es gab in einer früheren Cowork-Session bereits eine Ollama-Integration, die zwischenzeitlich rückgängig gemacht oder ins `archive/` verschoben wurde. (Hinweis: `archive/docs-old/.../Plan_v2_Ollama_Vulkan.md` zeigt, dass es **historisch** mal einen Plan dafür gab — der wurde aber aufgegeben.)
**Interpretation C**: Missverständnis — du erwartest, dass Ollama Teil der App ist, obwohl es das nicht ist.

**Ich werde nicht raten.** Der Plan setzt voraus, dass **A** gilt — Integration wird neu gebaut. Falls B oder C zutrifft, bitte korrigieren.

---

## 1. 📋 OFFENE BUGS / OPEN TASKS — vollständige Liste (verifiziert anhand `specs/`, `CHANGELOG.md`, Code-Grep)

### 1.1 Aus aktiven Spec-Dateien (Brownfield, Status `[ ]` = offen)

#### Spec 00007 — Release Hardening & UX Polish
- **T008** [OBJ2] [TR-002] — `src/tools/execute_4h_stress_test.py` mit `amdsmi`-Telemetrie + Batch-Loop implementieren
- **T009** [OBJ2] [TR-002] — VRAMArbiter-Eviction triggert bei Buffer <500 MB via Stress-Test verifizieren *(abhängig von T008)*
- **T010** [P] [TR-005] — GPU-accelerated RenderTransform Tab-Animations in `MainWindow.xaml` (laut CHANGELOG 2026-05-15 schon teils implementiert — Spec-Datei hängt nach: **Drift**)
- **T012** — Full-Run `verify_release_smoke.ps1` für Release-Readiness-Verdict

#### Spec 00009 — Audio/Video Data Depth
- **T006** [P1] — `storage.py`: komprimierte Depth-Metadaten in `media_cache` (laut CHANGELOG 2026-05-15 als `P2.2 / Spec 00009 T006` schon DONE — Spec-Datei zeigt aber noch `[ ]`: **Drift**, Sync nötig)
- **T008** [P1] — Dynamic Downsampling-Logik in `TimelineViewModel.cs` (AD-004, STF-001)

#### Spec 00010 — Resilience & Edge-Cases
- **T006** [OBJ2] [TR-002] — 4 GB-VRAM-Stress-Test ausführen + 0 OOM-Crashes verifizieren *(abhängig von T001+T005, die done sind)*
- **T007** [P] [OBJ1] — Backend killen während aktivem SSE-Progress → automatic UI-Recovery verifizieren
- **T008** [P] — Visuelles Review des „Connection Lost"-Overlays

### 1.2 Aus CHANGELOG.md → „Next Task" (2026-05-15)
- **P1.1** 4-Stunden-Stress-Test mit echtem AMF-Encoder (entspricht Spec 00007 T008/T009)
- **P1.2** 4 GB-VRAM-Stress-Test (entspricht Spec 00010 T006)
- **P3.2** Dep-Update-Cluster 2: scipy / soundfile / sklearn / sentencepiece / sqlite-vec (Audio/ML)

### 1.3 Aus CLAUDE.md → AMD-Treiber & Open-User-Action
- AMD Adrenalin Driver Update: per CHANGELOG 2026-05-15 als **RESOLVED** markiert (h264_amf runtime-verified). → **Erledigt**, kein offener Task.

### 1.4 Spec-vs-CHANGELOG-DRIFT (selbst-gefundene Inkonsistenz)
- Spec 00007 T010 ist als `[ ]` in tasks.md aber laut CHANGELOG 2026-05-15 implementiert.
- Spec 00009 T006 ist als `[ ]` in tasks.md aber laut CHANGELOG 2026-05-15 implementiert.
→ **Verlangt Cleanup-Task** (Spec-Files mit dem tatsächlichen Stand synchronisieren).

### 1.5 Modell-Stand (Discovery)
Im `models/`-Verzeichnis vorhanden:
- `moondream_pytorch.pt`, `moondream_tokenizer/`, `siglip_vision.onnx`, `siglip_tokenizer/`, `raft_small.onnx`, `UVR-MDX-NET-Inst_HQ_3.onnx`
- **NICHT vorhanden:** `moondream_encoder.onnx` und `moondream_decoder.onnx` (Code in `moondream.py:186-191` sucht sie, fällt aber zurück auf Lazy-Load mit Platzhaltertext). Das ist eine **latente Funktions-Lücke**: Moondream-ONNX-Pipeline ist nicht voll funktionsfähig, nur PyTorch-Fallback existiert (`moondream_pytorch.pt`). Der Code in `moondream.py:200-213` deaktiviert generate_caption() bei fehlendem ONNX. **Frage:** Wurde das je geprüft oder läuft die App stillschweigend mit Platzhalter-Captions?

---

## 2. 🎯 AKTUELLE LLM/AI-TOUCHPOINTS (für Gemma4-Replacement-Analyse)

| Modul | Aktuelles Modell | Was passiert | Gemma4-Eignung |
|-------|------------------|--------------|----------------|
| `src/pb_studio/video/moondream.py` | Moondream2 (Vision-LLM, SigLIP+Phi-Decoder) | Frame-Captioning, Scene-Description | **Hoch** — Gemma 3 12B-IT hat starkes Vision-Understanding und übertrifft Moondream2 bei Detail-Captions |
| `src/pb_studio/video/moondream_wrapper.py` | Moondream2 | Tag-Extraktion aus Captions (Keyword-basiert nach Caption) | **Hoch** — Gemma3 mit strukturiertem Prompt direkt JSON-Tags ausgeben |
| `src/pb_studio/video/auto_tagger.py` | Keine LLM — reines Keyword-Mapping | Tags aus Caption-String | **Mittel** — könnte durch Gemma3-Prompted-Classification ersetzt werden, oder hybrid bleiben |
| `src/pb_studio/ai/siglip_wrapper.py` | SigLIP-2 SO400M (Embeddings) | Image→1152-dim Embeddings für FAISS | **Nicht ersetzen** — Gemma ist kein Embedding-Modell. SigLIP bleibt |
| `src/pb_studio/ai/clap_wrapper.py` | CLAP | Audio→Text-Embeddings (Mood-Tags) | **Nicht ersetzen** — Audio-Spezialist, Gemma kann nicht Audio |
| `src/pb_studio/ai/smart_director.py` | Orchestrator (kein direkter LLM-Aufruf) | Audio + Video Analyse koordinieren | **Hoch** — könnte für Pacing-Rationale, Genre-Bestimmung, Schnitt-Erklärungen Gemma3 als Text-LLM nutzen |
| `backend/routers/brain_router.py` | Beta-Bernoulli WeightStore + CLAP/SigLIP-2 | Brain-Modul mit Suggestions | **Mittel** — Gemma3 könnte „warum dieser Cut" textuell erklären (Explainability) |
| Auto-Tag-Heuristik | regex/keyword | Brittle bei ungewöhnlichen Captions | **Hoch** — Gemma3 könnte zero-shot tags vergeben |

**Hinweis:** Ich kenne deine spezifische Ollama-Installation (gemma3:4b, 12b, 27b — welche Variante?) nicht. **Phase 1 muss das live verifizieren.**

---

## 3. 📐 MEHR-PHASEN-PLAN

### Phase 0 — KLÄRUNG (bevor Code-Änderung) — geschätzt 5 min
**Voraussetzung:** Drei Fragen, die ich nicht per Code-Audit beantworten kann:
- **Q1:** Welche Gemma-Variante hast du installiert? (`gemma3:4b` / `gemma3:12b` / `gemma3:27b` / `gemma2:9b` / andere?). Ich kann via Computer-Use `ollama list` ausführen, falls du genehmigst.
- **Q2:** Soll Gemma3 Moondream2 **ersetzen** oder **ergänzen** (Pluggable Backend mit Config-Switch)?
- **Q3:** Soll Ollama als **lokaler HTTP-Service** (default 11434) eingebunden werden, oder als **Subprocess** via CLI? (HTTP ist Standard und stabiler.)

### Phase 1 — LIVE-VERIFIKATION (kein Code-Edit) — geschätzt 15 min
1.1 — Pytest auf Windows ausführen: `pytest Tests/ -x -q` (verifiziert 537/10/0 aus CHANGELOG)
1.2 — Ollama-Status via Computer-Use prüfen: `ollama list`, `ollama ps`, `curl http://localhost:11434/api/version`
1.3 — Backend-Health prüfen: `python -m uvicorn backend.main:app --port 8765` + `/health/heartbeat`
1.4 — WPF Release-Build: `dotnet build PBStudio.UI\PBStudio.UI.csproj -c Release`
1.5 — Moondream-ONNX-Status klären: warum sind nur PyTorch-Files da, aber kein `moondream_encoder.onnx` / `moondream_decoder.onnx`?
**Output:** Verifikations-Report `LIVE_STATUS_2026-05-15.md` mit echten Ergebnissen (PASS/FAIL je Punkt)

### Phase 2 — OLLAMA-CLIENT-MODUL (neues Code-Modul) — geschätzt 2-3h
2.1 — Neu: `src/pb_studio/ai/ollama_client.py`
- HTTP-Client gegen `http://localhost:11434/api/generate` und `/api/chat`
- Vision-Support via `images=[base64]` Parameter (Gemma3-IT unterstützt Vision)
- Timeout-Handling, Retry-Logic, kein Streaming (synchron für deterministische Outputs)
- **IRON-RULE-Compliance:** kein CUDA, kein NVIDIA-spezifischer Code — reiner HTTP-Client
2.2 — Neu: `src/pb_studio/ai/llm_backend.py`
- Pluggable-Backend-Interface: `LLMBackend` (Protocol)
- Implementierungen: `MoondreamBackend`, `GemmaOllamaBackend`
- Auswahl via `config.json.ai.llm_backend: "moondream" | "gemma_ollama"`
2.3 — Config-Schema-Erweiterung in `config.json`:
```json
"ai": {
  "vision_model": "moondream2_fp16",     // bleibt für Fallback
  "llm_backend": "gemma_ollama",          // neu: aktiver Backend
  "ollama": {
    "host": "http://localhost:11434",
    "model": "gemma3:12b",                // wird in Phase 0 final bestimmt
    "timeout_s": 60,
    "fallback_to_moondream": true
  }
}
```
2.4 — Tests: `Tests/test_ollama_client.py` mit `httpx.MockTransport` (offline-fähig)

### Phase 3 — INTEGRATION an Touchpoints — geschätzt 3-4h
3.1 — `moondream_wrapper.py` → über `llm_backend.py` routen (kein Direct-Import von Moondream)
3.2 — `auto_tagger.py` → optional `LLMBackend.generate_tags(caption)` statt regex (Config-Switch)
3.3 — `backend/routers/video_router.py::_run_video_analysis` → Backend-Auswahl via Config
3.4 — `brain_router.py::/brain/explain` → Gemma3 für Textual-Explanation der Suggestions
3.5 — Backend-Schema-Erweiterung: SSE-Events publishen `llm_backend_used: "moondream"|"gemma"`
3.6 — Frontend (`PBStudio.UI/Views/HirnView.xaml`): Backend-Status-Anzeige
3.7 — Release-Build (`dotnet build -c Release`) — autonom, Iron Rule 10

### Phase 4 — OFFENE BUGS ABARBEITEN (parallel zu Phase 3 möglich) — geschätzt 4-6h
4.1 — Spec 00007 T008: `execute_4h_stress_test.py` implementieren
4.2 — Spec 00007 T009: VRAM-Eviction via T008 verifizieren
4.3 — Spec 00010 T006: 4 GB-Stress-Test ausführen
4.4 — Spec 00010 T007: Backend-Kill + SSE-Recovery-Test
4.5 — Spec 00010 T008: Visual-Review Overlay (Screenshot via Computer-Use)
4.6 — Spec 00009 T008: Dynamic Downsampling `TimelineViewModel.cs`
4.7 — Spec-Drift-Cleanup: Tasks.md-Files mit echtem Stand sync (00007 T010, 00009 T006 als `[X]`)
4.8 — Spec 00007 T012: `verify_release_smoke.ps1` Full-Run

### Phase 5 — DEPENDENCY-UPDATES (low-risk, Cluster 2) — geschätzt 1-2h
5.1 — P3.2 Audio/ML-Cluster: scipy / soundfile / sklearn / sentencepiece / sqlite-vec
5.2 — Pytest-Regression-Lauf (537 sollte 537 bleiben)
5.3 — Commit + CHANGELOG.md update

### Phase 6 — TESTS & VERIFIKATION — geschätzt 2-3h
6.1 — Qualitäts-Vergleich Moondream vs Gemma3 (kuratierte 20 Frames, manuelle Bewertung)
6.2 — VRAM-Benchmark: Gemma3 läuft via Ollama, also Ollama-VRAM separat von DirectML-Budget. Klären ob Konkurrenz oder unabhängig.
6.3 — Latency-Benchmark: Caption-Time Moondream vs Gemma3
6.4 — End-to-End-Test: DJ-Mix Analyse mit beiden Backends, Output-Vergleich
6.5 — Pytest erweitern: `test_llm_backend_pluggable.py`, `test_gemma_caption_quality.py`

### Phase 7 — DOKUMENTATION & OBSIDIAN-SYNC (Iron Rule 11) — geschätzt 1h
7.1 — CLAUDE.md: Architektur-Map um LLM-Backend-Pluggability erweitern
7.2 — CHANGELOG.md: alle Phasen dokumentieren
7.3 — Neue ADR: `specs/adrs/0002-pluggable-llm-backend-ollama-gemma.md`
7.4 — Obsidian-Vault `C:\Users\david\Brain\10_Projects\PB_studio\`: INDEX.md + log.md updaten, ADR in decisions/

### Phase 8 — DEPLOYMENT & END-REPORT (Iron Rule 9 + 10) — geschätzt 30 min
8.1 — Release-Build dotnet (autonom)
8.2 — Setup-Scripts checken: muss `start.bat` / `launch.ps1` Ollama-Health-Check vor Backend-Start prüfen?
8.3 — End-Report mit explizitem Audit: welche Binaries gebaut, welche Scripts validiert, welche Tests passed

---

## 4. ⚠️ RISIKEN & VORBEHALTE

| # | Risiko | Mitigation |
|---|--------|-----------|
| R1 | Ollama-VRAM-Konkurrenz mit DirectML-Modellen (CLAP/SigLIP/RAFT laufen gleichzeitig) | VRAMBudgetManager um Ollama-Tracking erweitern; oder Sequential-Mode |
| R2 | Gemma3-Vision-Quality eventuell schlechter als Moondream2 für **video-spezifische** Frames (Moondream ist auf Vision-LLM trainiert, Gemma3 generalist) | Phase 6.1 Qualitäts-Vergleich vor Default-Switch |
| R3 | Ollama-Service-Crash → kein Fallback definiert | `fallback_to_moondream: true` als Default; SSE-Event publishen |
| R4 | IRON RULE R3: Python 3.11 + NumPy 1.26.4. Ollama-Python-Client (falls verwendet) muss kompatibel sein. Wir nutzen aber **httpx pur**, kein `ollama` Python-Paket → R3 nicht berührt | n/a |
| R5 | IRON RULE R5: kein pynvml. Ollama nutzt intern AMD-GPU via DirectML/ROCm-on-Windows → muss live verifiziert werden | Phase 1.2 |
| R6 | Spec-vs-CHANGELOG-Drift kann zu Doppelarbeit führen | Phase 4.7 explizit als Cleanup-Task |
| R7 | Moondream-ONNX-Files fehlen → vielleicht läuft die App seit Wochen mit Platzhaltern | Phase 1.5 klärt das |

---

## 5. 🚦 FREIGABE-FRAGEN

Bevor ich beginne, brauche ich Antworten:
1. Stimmt meine Ehrlichkeits-Erkenntnis (Sektion 0)? Welche Interpretation A/B/C trifft zu?
2. Welche Gemma-Variante ist installiert? (Q1 in Phase 0)
3. Soll Gemma3 Moondream2 **ersetzen** oder **ergänzen**? (Q2 in Phase 0)
4. Darf ich Computer-Use zur Live-Verifikation einsetzen? (Phase 1.2 — `ollama list` lokal)
5. Genehmigung für Phasen 0–8 als Gesamtblock oder nur Phasen 0–2 freigeben, dann nachhaken?
6. Geschätzter Gesamtumfang: **~14–20 Stunden** Arbeitszeit. OK?

---

**Ich werde NICHT beginnen, bevor du explizit freigibst.** Iron Rule 10.
