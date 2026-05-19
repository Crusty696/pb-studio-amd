# V2-PLAN — Ollama Full Headless Integration
**Datum:** 2026-05-15
**Verfasser:** Claude (Cowork-Session, Brain-Stand 2026-05-15)
**Status:** ENTWURF V2 — ersetzt `PLAN_2026-05-15_Ollama_Gemma_Bugs.md` (V1)
**Iron-Rule-Compliance:** R1 (DirectML — siehe Sektion 1 für Reconciliation-Vorschlag), R10 (100% Honesty), R13 (Verify-Before-Change)
**Scope-Reset:** V1 war "Feature-Swap Moondream→Gemma". V2 ist "Multi-Monats-Architektur-Umbau zur Headless-Ollama-Plattform."

---

## 1. 📊 EHRLICHKEITS-ERKENNTNIS V2 (was war im V1 zu eng)

### 1.1 V1-Scope war ein Feature-Swap, kein Architektur-Umbau
V1 hat das Vorhaben als "Moondream durch Gemma4 ersetzen + offene Bugs gleichzeitig fixen" begriffen, geschätzt mit 14–20 Stunden. Das war zu eng. Die User-Vision umfasst:
- **5 separate Migrations-Tracks** (Audio · Video · Pacing · HIRN · KI-Chat), wobei KI-Chat überhaupt nicht existiert (Greenfield-Feature)
- **In-App Model-Manager** als neuen Top-Level-Tab inkl. Download/Delete/Recommendations-Flow
- **Hybrid-Mode-Slider** (Speed/Balance/Quality) plus **Per-Task-Override** für Auto-Selection
- **Pluggable LLM-Backend** als Kernarchitektur, nicht als One-Off-Patch
- **Cross-Track-VRAM-Koordination** zwischen Ollama (out-of-process) und DirectML/ONNX (in-process)

Realistische Schätzung Sektion 7 unten: **120–200 Stunden** = ca. 3–5 Personen-Wochen Full-Time, kalendarisch **3–6 Monate bei Cowork-Pace** mit den parallelen Bug-Fixes & Stress-Tests.

### 1.2 V1 hat Iron-Rule-1-Konflikt nicht adressiert
R1 sagt heute wörtlich: **"AMD DIRECTML ONLY: NO CUDA, NO ROCm. Use `onnxruntime-directml`."**
Ollama auf AMD-Windows nutzt aber NICHT DirectML. Stand 2026: Ollama-Backend ist entweder **Vulkan** (Standard auf Windows-AMD via llama.cpp Vulkan-Compute) oder **ROCm** (experimentell, Linux-besser). Beides verletzt R1 in der heutigen Formulierung.

**Reconciliation-Vorschlag — drei Varianten, eine zu wählen:**

**Variante A — R1 erweitern (Empfehlung):**
> "AMD GPU only. NO CUDA, NO NVIDIA. Erlaubte AMD-GPU-Stacks: DirectML für in-process Python/ONNX-Workloads; Vulkan oder ROCm via Ollama für headless out-of-process LLM-Inferenz. NumPy/PyTorch dürfen NICHT direkt ROCm/Vulkan nutzen."

Vorteil: explizite Liste erlaubter Stacks, Ollama integriert sich sauber.
Nachteil: R1 wird länger, weniger schnell überprüfbar.

**Variante B — Ollama als R1-Ausnahme dokumentieren:**
> R1 bleibt unverändert. Neue R1.1 (Ausnahme): "Ollama als externer Headless-Service ist von R1 ausgenommen. Welcher Compute-Backend Ollama intern nutzt (Vulkan/ROCm/CPU) wird über `/api/ps` verifiziert, nicht über R1 reguliert."

Vorteil: R1 bleibt knapp.
Nachteil: erzeugt eine "Sondertür", neue Maintainer könnten verwirrt werden.

**Variante C — R1 nicht erweitern, dafür Ollama als zweite Top-Level-Rule R1B:**
> R1 bleibt. Neue R1B: "AMD GPU-only Headless-LLMs via Ollama: GPU-only erzwingen (`OLLAMA_LLM_LIBRARY=rocm` oder Vulkan-Backend; CPU-Fallback ist verboten und löst Hard-Fail aus, siehe Modell-Manager)."

Vorteil: parallele, gleich-prominente Regel.
Nachteil: R1 + R1B können sich faktisch widersprechen, wenn Vulkan-Backend ausfällt und Ollama still auf CPU fällt.

**Claude empfiehlt Variante A.** Klare positive Liste, kein Pförtner-Pattern, einfach zu kommunizieren. **Erste Freigabe-Frage ist genau das** (siehe Sektion 9).

### 1.3 V1 hat den Moondream-ONNX-Ausfall unterschätzt
V1 hat `moondream_encoder.onnx` / `moondream_decoder.onnx`-Fehlen als "latente Funktions-Lücke" markiert und in Phase 1.5 zur Klärung verschoben. Heutiges (15.05.) Read-Only-Audit bestätigt das. Folge: `extract_tags_via_moondream` returnt `[]` (ehrlich gelogt), aber das macht **semantic-tag-basiertes Pacing real funktionsschwach**. Heisst: der Video-Pilot-Track ersetzt nicht nur theoretisch ein Modell, sondern stellt eine **defekte Pipeline-Stufe** wieder her. Das ist hoher User-Wert ab Tag 1 vom Video-Track.

### 1.4 V1 hat die Cross-Track-Komponenten als Phasen verkettet
V1 baute "Ollama-Client → Touchpoint-Integration → Bugs" linear. V2 erkennt: **Ollama-Client + Model-Registry + Model-Manager-UI + Auto-Selection** sind alle vier **Backbone** und müssen vor Track-Migration stehen, sonst macht jeder Track sein eigenes Auto-Selection-Snowflake.

---

## 2. 🔬 VERIFIZIERTE LIVE-FAKTEN (heute, read-only)

| Fakt | Quelle | Status |
|------|--------|--------|
| pytest: 542 passed / 10 skipped / 0 failed | Windows native Lauf 2026-05-15 | ✅ verifiziert |
| 256/256 Python-Files py_compile clean | Lokaler Lauf vorab durch User | ✅ User-bestätigt |
| Ollama läuft: `api/version` → 0.24.0 | HTTP-Check `http://localhost:11434/api/version` | ✅ verifiziert |
| Modell installiert: `gemma4:latest` 9.6 GB | `ollama list` ca. 1h vor V2-Plan | ✅ verifiziert |
| Backend NICHT gerade laufend | Port 8765 Check | ✅ verifiziert |
| Moondream ONNX-Files FEHLEN | `models/` zeigt nur `moondream_pytorch.pt` + `moondream_tokenizer/` | ✅ verifiziert |
| `extract_tags_via_moondream` returnt `[]` (ehrlich gelogt) | `src/pb_studio/video/moondream_wrapper.py` + Test `test_video_moondream.py` | ✅ verifiziert |
| Repo HEAD: `d08a6b0a`, 16 Commits vor `origin/main` | git status | ✅ verifiziert |
| config.json `ai.vision_model = "moondream2_fp16"` | gelesen | ✅ verifiziert |
| Keine Ollama/Gemma-Referenzen in aktivem Code | Grep `src/` + `backend/` + `Tests/` | ✅ verifiziert (V1 hat das auch schon belegt) |

**Was NICHT verifiziert ist** (geht in Sektion 6 als Verify-Punkt):
- Welcher Compute-Backend (Vulkan/ROCm/CPU) Ollama tatsächlich nutzt
- Ob Ollama unter Last GPU-only bleibt oder auf CPU fällt
- Latenz und Qualität von `gemma4:latest` für PB-Studio-Video-Frames
- VRAM-Footprint gleichzeitig: Ollama + DirectML-CLAP + DirectML-SigLIP + DirectML-RAFT
- Ob `gemma4:latest` Vision unterstützt — Modellname allein gibt das nicht her (Gemma 3 IT hat Vision, "Gemma 4" Naming müsste verifiziert werden)

---

## 3. 🏗️ 5-TRACK-ARCHITEKTUR

### 3.1 Track 1 — AUDIO
**Aktueller Stand (Read-Only-Audit):**
- `src/pb_studio/audio/separator.py` — Demucs Hybrid via patched DirectML
- `src/pb_studio/audio/beat_detector.py` — BeatNet 1.1.1 (CPU) + librosa-Fallback
- `src/pb_studio/audio/spectral_analyzer.py` — librosa STFT + mel-bands
- `src/pb_studio/audio/structure_analyzer.py` — Self-Similarity-Matrix + Segmentation
- `src/pb_studio/audio/dj_mix_analyzer.py` — High-Level-Orchestrierung für DJ-Mixes
- `src/pb_studio/audio/key_detector.py` — Krumhansl-Kessler (mathematisch, librosa)
- `src/pb_studio/audio/subtrack_detector.py`, `audio/analyzer.py`, `audio/anchor_features.py`, `audio/stem_runner.py`
- `src/pb_studio/ai/clap_pytorch.py` — CLAP via torch-directml für Audio→Text-Embeddings
- Workers: `workers/audio/{import,analyze,stem,embedding}_worker.py`
- Backend: `backend/routers/audio_router.py`

**Was Ollama hier ersetzen KANN (begrenzte Surface):**
- ❌ Demucs Stem-Separation: **nicht ersetzbar.** Audio-Source-Separation ist keine Aufgabe für Text-/Vision-LLMs.
- ❌ BeatNet/Beat-Detection: **nicht ersetzbar.** Signal-Processing-Task.
- ❌ KeyDetector: **nicht ersetzbar.** Math-Modell.
- ❌ Spectral-Analyzer: **nicht ersetzbar.**
- ❌ CLAP-Embeddings: **nicht ersetzbar** durch Ollama. Ollama hat keine Audio-Embedder.
- ⚠️ `structure_analyzer.py` Narration: **könnte** ein Text-LLM Erklärungen liefern ("Track-Struktur: Intro 0-15s, Build-Up 15-32s, Drop 32-60s, …") — aber das ist UI-Layer, kein Detection-Layer.
- ⚠️ `dj_mix_analyzer.py` Genre-Classification / Mood-Beschreibung: **könnte** Text-LLM nutzen, gegeben CLAP-Audio-Tags als Input.

**Fazit Track 1:** Audio ist mathematisch dominiert, Ollama bietet nur **Narration/Erklärungs-Schicht**, kein Replacement. Track-Umfang deutlich kleiner als Video.

### 3.2 Track 2 — VIDEO (PILOT)
**Aktueller Stand:**
- `src/pb_studio/video/moondream.py` — ONNX-DirectML-Pipeline, **aktuell defekt** weil ONNX-Files fehlen
- `src/pb_studio/video/moondream_wrapper.py` — `extract_tags_via_moondream(frame_path) → []` ehrlich
- `src/pb_studio/ai/moondream_pytorch.py` — PyTorch-Fallback
- `src/pb_studio/video/auto_tagger.py` — Regex/Keyword-Mapping Caption→Tags
- `src/pb_studio/video/engine.py` — High-Level-Video-Pipeline
- `src/pb_studio/ai/siglip_wrapper.py` — SigLIP-2 SO400M 1152-dim Embeddings → FAISS
- `src/pb_studio/video/scene_detect.py` — PySceneDetect
- RAFT optical flow ONNX
- Workers: `workers/video/{import,vision,motion,scene}_worker.py`
- Backend: `backend/routers/video_router.py`

**Was Ollama hier ersetzen KANN:**
- ✅ **Moondream2 → Ollama-Vision-Modell** (Captioning + Tag-Generierung). Kandidaten siehe Phase 0 Recherche-Punkt.
- ✅ **`auto_tagger.py` Regex-Heuristik → strukturiertes LLM-Prompt mit JSON-Schema-Output.**
- ❌ SigLIP-Embeddings: **bleibt.** Ollama hat keine 1152-dim-Bild-Embedder mit dieser FAISS-Kompatibilität.
- ❌ RAFT Optical Flow: **bleibt.** Mathematisches Modell.
- ❌ PySceneDetect: **bleibt.** Signal-Processing.

**Pilot-Begründung:** (1) defekte Pipeline-Stufe wird repariert (hoher User-Wert sofort); (2) Vision-Captioning ist die LLM-Disziplin mit klarstem Multi-Modell-Vergleich (LLaVA, llama3.2-vision, qwen2.5-vl, gemma3-vision, MiniCPM-V — perfekt für Multi-Model-Backbone von Tag 1); (3) Output ist text-strukturiert und einfach mit Moondream's-Output zu vergleichen → klare Qualitäts-Metrik.

**Geschätzte Modell-Größen:**
- LLaVA 7B: 4.5 GB GGUF Q4
- llama3.2-vision 11B: 7.9 GB
- qwen2.5-vl 7B: 5–6 GB
- gemma3 12B: 8.5 GB (Vision unterstützt? **Verify in Phase 0**)
- MiniCPM-V 8B: 5.5 GB

### 3.3 Track 3 — PACING
**Aktueller Stand:**
- `src/pb_studio/pacing/{constants,mood_generator,motion_preference,anchor_manager,export_handler,timeline_models}.py`
- `src/pb_studio/ai/smart_director.py` — Pacing-Orchestrierung
- Backend: `backend/routers/pacing_router.py`
- Bridge-Achsen-Scorer in `brain/scorer.py` (Cross-Track mit HIRN)

**Was Ollama hier ersetzen KANN:**
- ✅ **Pacing-Rationale-Generation:** "Warum dieser Schnitt jetzt?" als natürlich-sprachliche Erklärung statt Score-Tupel.
- ✅ **Mood-Derivation:** aus CLAP-Tags + Video-Tags + BPM → Mood-Label via Text-LLM.
- ❌ Scoring-Math, Bridge-Achsen-Berechnung, Beta-Bernoulli: **bleibt.** Deterministisch & schnell.
- ❌ Motion-Preference-Math: **bleibt.**

### 3.4 Track 4 — HIRN-Tab
**Aktueller Stand:**
- `src/pb_studio/brain/*` — 13 Module: brain_service, scorer, weight_store, reranker, post_processor, smart_sampler, cold_start, context_resolver, feedback_logger, projector_trainer, cross_modal_projector, bridge_dimensions, loader_cache
- Backend: `backend/routers/brain_router.py` mit 6 REST-Endpoints `/brain/{suggest,feedback,learning_session,stats,reset,explain}`
- WPF: `Views/BrainView.xaml` + `ViewModels/BrainViewModel.cs` + Confidence-Balken
- 17 Bridge-Achsen · Beta-Bernoulli WeightStore · 5-Level Hierarchical Backoff · CLAP + SigLIP-2 via torch-directml

**Was Ollama hier ersetzen KANN:**
- ✅ **`/brain/explain` Endpoint:** Text-LLM für "Warum dieser Suggestion? Welche Bridge-Achsen waren ausschlaggebend?" — derzeit vermutlich Score-Tupel-Rückgabe (Verify).
- ⚠️ **Confidence-Erklärung:** Beta-Bernoulli liefert Posterior-Verteilung; Text-LLM könnte sie in user-verständliche Sprache übersetzen ("Hoch sicher, weil 12 ähnliche Cuts in deinem Feedback waren").
- ❌ Beta-Bernoulli-Math, Bridge-Achsen, WeightStore: **bleibt.**
- ❌ CLAP + SigLIP-2 Cross-Modal-Projector: **bleibt.**

### 3.5 Track 5 — KI-CHAT-FENSTER (GREENFIELD)
**Aktueller Stand:** **existiert nicht.** Keine `ChatView.xaml`, kein `ChatViewModel.cs`, kein `backend/routers/chat_router.py`.

**Was neu gebaut werden muss:**
- WPF `Views/ChatView.xaml` + `Views/ChatView.xaml.cs`
- WPF `ViewModels/ChatViewModel.cs` mit Message-History, Streaming-Token-Display, Project-Context-Integration
- Backend `backend/routers/chat_router.py` mit:
  - `POST /chat/send` (multi-turn, streaming via SSE)
  - `GET /chat/history/{project_id}`
  - `DELETE /chat/history/{project_id}`
- `src/pb_studio/ai/chat_service.py` — Wrapper auf Ollama-Client mit System-Prompt-Injection (current_project, media_db Read-Access, Pacing-State)
- Models: ChatMessage, ChatSession, ChatHistory (SQLAlchemy-Tabelle)
- Frontend `Services/ChatApiClient.cs` + Streaming-Handler
- MainWindow-Tab oder Side-Panel — **User-Entscheidung in Sektion 9**

### 3.6 Cross-Track-Komponenten (Backbone)
| Komponente | Wo | Beschreibung |
|------------|-----|--------------|
| `OllamaClient` | `src/pb_studio/ai/ollama_client.py` (neu) | httpx-basierter HTTP-Client. `/api/generate`, `/api/chat`, `/api/embeddings`, `/api/tags`, `/api/pull`, `/api/delete`, `/api/show`, `/api/ps`. Vision via `images=[base64]`. Sync + Streaming (SSE-friendly). Timeout, Retry, Circuit-Breaker. |
| `LLMBackend` Protocol | `src/pb_studio/ai/llm_backend.py` (neu) | Abstraktion mit `generate_caption`, `generate_tags`, `generate_text`, `chat`. Implementierungen: `OllamaBackend`, `MoondreamBackend` (legacy), `FallbackBackend`. |
| `ModelRegistry` | `src/pb_studio/ai/model_registry.py` (neu) | Katalog aller bekannten Ollama-Modelle mit Metadaten: Name, Größe (GB), Capabilities (`vision`, `text`, `embedding`), Speed-Tier, Quality-Tier, Recommended-Slider-Position. Quelle: kuratierter JSON in `models/ollama_catalog.json`. Sync mit `ollama list` für Installed-Status. |
| `AutoSelector` | `src/pb_studio/ai/auto_selector.py` (neu) | Wählt Modell pro Task gegeben (Slider-Position, Per-Task-Override, Installed-Status, VRAM-Budget). |
| Model-Manager-UI | `PBStudio.UI/Views/ModelsView.xaml` (neu) | Top-Level-Tab "MODELLE" mit Liste, Status, VRAM, Download-Flow (SSE Progress), Delete, Recommendations. |
| Settings-Slider | Erweiterung von `Views/SettingsView.xaml` | Speed/Balance/Quality + 5 Per-Task-Override-Dropdowns (Video-Vision, Audio-Narration, Pacing-Rationale, HIRN-Explain, KI-Chat). |
| VRAM-Koordination | Erweiterung von `src/pb_studio/core/vram_arbiter.py` (oder VRAMBudgetManager wherever lebt) | Tracke Ollama-Footprint via `/api/ps` + LibreHardwareMonitor-Reading. Wenn DirectML-Task ansteht und Ollama gerade läuft → entweder Sequential oder Ollama-Unload via `ollama stop`. |

---

## 4. 🎚️ AUTO-SELECTION-ARCHITEKTUR (Hybrid + User-Override)

### 4.1 Slider-Modell
Drei Modi via Settings-Slider:
- **Speed** (links): kleinste, schnellste Modelle. Beispiel-Default: LLaVA 7B (Video), Gemma 2B (Text-Tasks). Ziel: <500ms pro Inference auf RX-6700-XT-Klasse.
- **Balance** (mittig, Default): mid-tier. Beispiel: LLaVA 13B oder qwen2.5-vl 7B (Video), Llama 3.1 8B (Text). Ziel: <2s pro Inference.
- **Quality** (rechts): grösste, beste Modelle. Beispiel: llama3.2-vision 11B oder Gemma 3 12B (Video), Llama 3.1 70B-Q4 wenn VRAM reicht (Text). Ziel: Qualität first, Latenz egal.

### 4.2 Per-Task-Override
Pro Track ein eigenes Dropdown im Settings-Tab:
- **Video-Vision-Modell:** Default = Slider, Override = explizites Ollama-Modell aus Installed-List.
- **Audio-Narration-Modell:** dito.
- **Pacing-Rationale-Modell:** dito.
- **HIRN-Explain-Modell:** dito.
- **KI-Chat-Modell:** dito.

Persistenz in `config.json`:
```json
"ai": {
  "auto_select": {
    "mode": "balance",
    "overrides": {
      "video_vision": null,
      "audio_narration": null,
      "pacing_rationale": null,
      "hirn_explain": null,
      "ki_chat": null
    }
  }
}
```

### 4.3 Default-Heuristik pro Mode pro Task (Beispiel-Werte, kommen aus Phase 0 Recherche)
| Mode | Video-Vision | Audio-Narration | Pacing-Rationale | HIRN-Explain | KI-Chat |
|------|-------------|------------------|------------------|--------------|---------|
| Speed | LLaVA 7B Q4 | Gemma 2B | Gemma 2B | Gemma 2B | Llama 3.2 3B |
| Balance | qwen2.5-vl 7B | Llama 3.1 8B | Llama 3.1 8B | Llama 3.1 8B | Llama 3.1 8B |
| Quality | llama3.2-vision 11B oder gemma3-vision 12B | Llama 3.1 8B | Llama 3.1 8B | Llama 3.1 8B | Llama 3.1 70B-Q4 (falls VRAM) sonst Llama 3.1 8B |

**WICHTIG:** diese Tabelle ist ein **Strawman** — die echten Default-Listen werden in Phase 0 nach AMD-Vulkan-Benchmark + Quality-Vergleich finalisiert.

### 4.4 Wo in der UI
- **Settings-Tab** bekommt einen neuen Sub-Tab "KI-MODELLE" mit:
  - Mode-Slider (Speed/Balance/Quality)
  - 5 Override-Dropdowns
  - Status-Anzeige: aktuell aktive Modelle pro Task
  - Link zum Model-Manager-Tab für Install/Update
- **Performance-Tab** bleibt unberührt (das ist VRAM-Telemetrie, kein AI-Setting).

---

## 5. 📦 MODEL-MANAGER-UI

### 5.1 Position im Hauptfenster
Neuer Top-Level-Tab **"MODELLE"** in `MainWindow.xaml`, zwischen "HIRN" und "Einstellungen". Tab-Icon: Pakete/Box. Visibility-Bound an `OllamaAvailable` Property (versteckt sich, falls Ollama nicht erreichbar).

### 5.2 Tab-Inhalt (UI-Mockup-Beschreibung)
Drei Sektionen:

**Sektion A — Installierte Modelle** (DataGrid)
| Name | Größe | VRAM-Geschätzt | Capabilities | Status | Aktionen |
|------|-------|----------------|--------------|--------|----------|
| gemma4:latest | 9.6 GB | ~7 GB | text, vision? | ● running | [Unload] [Delete] |
| llava:7b-q4 | 4.5 GB | ~4 GB | text, vision | ● idle | [Load] [Delete] |
| llama3.1:8b | 4.7 GB | ~5 GB | text | ● idle | [Load] [Delete] |

**Sektion B — Empfohlene Modelle** (Cards)
Pro Slider-Mode 3 Karten mit Empfehlungen (aus `ModelRegistry`). Karte zeigt: Name, Größe, Capabilities, "Geeignet für: Video-Vision / Audio-Narration / …", Button [Download].

**Sektion C — Custom Pull** (TextBox + Button)
Eingabe `<modell>:<tag>` → Button "Pull". Validierung gegen Ollama-Registry-Suche.

### 5.3 Download-Flow (mit SSE-Progress)
1. User klickt [Download] auf einer Empfehlung oder gibt Custom-Pull ein.
2. Frontend ruft `POST /models/pull` mit `{model: "llava:7b"}`.
3. Backend startet `ollama pull llava:7b` Subprocess + parsed stdout für Progress.
4. Backend emit'tet SSE-Events `{phase: "downloading", percent: 42, downloaded_mb: 1900, total_mb: 4500}` an `/events/sse`.
5. Frontend zeigt Progressbar + abbrechbarer Cancel-Button.
6. On-Complete: SSE-Event `{phase: "complete"}` → Frontend refresht Installed-Liste.

### 5.4 Delete-Flow
1. User klickt [Delete] auf installiertem Modell.
2. Confirm-Dialog (deutlich, zeigt Größe + ob das Modell gerade Default für ein Track ist).
3. `DELETE /models/{name}` → Backend ruft `ollama rm <name>`.
4. Falls Modell gerade als Per-Task-Override aktiv: Config wird auf `null` zurückgesetzt + Notification.

### 5.5 Backend-Endpoints (neu in `backend/routers/models_router.py`)
| Methode | Pfad | Beschreibung |
|---------|------|--------------|
| GET | `/models/list` | Liste installierter Modelle inkl. Capabilities und Running-Status (`ollama list` + `ollama ps`). |
| GET | `/models/recommendations?mode=balance` | Empfehlungen aus `ModelRegistry` gefiltert nach Mode + Installed-Status. |
| POST | `/models/pull` | Body `{model: "llava:7b"}`. Startet Pull + SSE-Progress. Returns task-id. |
| POST | `/models/cancel-pull/{task_id}` | Bricht laufenden Pull ab. |
| DELETE | `/models/{name}` | Removes Modell. |
| POST | `/models/load/{name}` | Forciert `ollama run <name>` (Pre-Load für Latency). |
| POST | `/models/unload/{name}` | `ollama stop <name>` für VRAM-Freigabe. |

---

## 6. 🔍 VERIFY-BEFORE-CHANGE PUNKTE (R13)

Jede Phase MUSS einen expliziten `verify`-Schritt VOR Implementation haben. Hier die Pflicht-Verifikationen:

### 6.1 Vor Phase 0
- **VRF-0.1:** Läuft Ollama wirklich auf der AMD-GPU? Befehl: nach Inference-Start `curl http://localhost:11434/api/ps` → Feld `"size_vram"` muss > 0 sein. Cross-Check: LibreHardwareMonitor während eines Test-Calls beobachten — VRAM-Usage muss steigen.
- **VRF-0.2:** Wenn VRF-0.1 positiv: welcher Backend (Vulkan oder ROCm)? `ollama serve` Logs lesen (`OLLAMA_LLM_LIBRARY=...` Pattern). Wenn CPU-Backend aktiv → **Hard-Block,** Plan kann nicht starten.
- **VRF-0.3:** Hat `gemma4:latest` Vision? Probe-Call: ein Test-Frame als Base64 an `/api/generate` mit `images=[...]`. Antwort lesen. Falls 400er oder generischer Text ohne Bild-Referenz → kein Vision-Modell → für Video-Track brauchen wir LLaVA/qwen2.5-vl/llama3.2-vision.
- **VRF-0.4:** Welche Vision-Modelle in Ollama liefern für PB Studio's Video-Frames sinnvolle Captions+Tags? Recherche-Task: kuratiere 5 echte Test-Frames aus `tests/fixtures` (oder media_db falls vorhanden). Lass jedes Kandidaten-Modell laufen. Manuelle Bewertung Quality-Rang.

### 6.2 Vor Phase 1 (Backbone)
- **VRF-1.1:** OllamaClient — Mock-Server-Tests mit `httpx.MockTransport` definieren BEVOR Implementation. Test-Cases: 200-OK, 404-Modell-fehlt, 500-Timeout, Streaming-Chunk-Parse.
- **VRF-1.2:** LLMBackend Protocol — `pb-master`-Skill aufrufen mit Frage "welche Module rufen heute moondream/auto_tagger/clap/etc. auf?" → kompletter Caller-Audit, damit Phase 3 keine Caller übersieht.
- **VRF-1.3:** ModelRegistry — JSON-Schema gegen Ollama-API-Schema validieren (Felder `name`, `digest`, `size`, `details.parameter_size`).

### 6.3 Vor Phase 2 (Model-Manager UI)
- **VRF-2.1:** SSE-Progress: gibt es schon SSE-Infrastruktur (siehe `backend/routers/events_router.py`)? **Ja** — `publish_event` Fan-out existiert (CLAUDE.md belegt). Re-Use, nicht neu bauen.
- **VRF-2.2:** Frontend `ApiClient.cs` mit neuen Endpoints erweitern — `full-stack-auditor`-Skill: was ist die heutige Konvention (sync/async Methode, Cancel-Token)?
- **VRF-2.3:** XAML-Designer: läuft die App noch nach hinzufügen eines neuen `Views/ModelsView.xaml` ohne kaputte StartupUri / DI-Registration? Verifiziere `App.xaml` / `App.xaml.cs` DI-Setup.

### 6.4 Vor Phase 3 (Video-Pilot)
- **VRF-3.1:** Welche Files rufen `extract_tags_via_moondream` heute auf? Grep schon gemacht: `backend/routers/video_router.py`, `src/pb_studio/video/moondream_wrapper.py`, `Tests/test_video_moondream.py`. Alle drei müssen über `LLMBackend` geroutet werden.
- **VRF-3.2:** Welche Files rufen `MoondreamAnalyzer.generate_caption` heute auf? Grep gegen `moondream.py::MoondreamAnalyzer`-Methoden.
- **VRF-3.3:** Quality-Baseline: zuerst mit aktuellem (defekten) Moondream einen Lauf machen → was kommt raus? Dann mit Ollama-Vision-Modell → Diff. Ohne Baseline kein Verify.
- **VRF-3.4:** VRAM-Stress-Test: gleichzeitig SigLIP + RAFT + Ollama-Vision-Inference laufen lassen → bleibt Budget < 6 GB auf RX-6700-XT (oder dem User-System)? Wenn nicht → Sequential-Mode aktivieren.

### 6.5 Vor Phase 4 (Audio)
- **VRF-4.1:** Bestand klären: gibt es heute eine `structure_analyzer.py`-Output-Narration, oder ist das aktuell nur ein Daten-Tupel? Bei Daten-Tupel → Phase 4 erweitert auf UI-Display-Schicht.

### 6.6 Vor Phase 5 (Pacing)
- **VRF-5.1:** `smart_director.py` Caller-Audit: wo wird heute Pacing-Output text-formatiert? Ist das Frontend-Format-Logic oder Backend?

### 6.7 Vor Phase 6 (HIRN)
- **VRF-6.1:** `/brain/explain` Endpoint heute: was ist das Response-Schema? Liefert es schon natürlich-sprachliche Erklärung oder Score-Tupel? Read-Only-Audit von `brain_router.py`.

### 6.8 Vor Phase 7 (KI-Chat)
- **VRF-7.1:** WPF Multi-Window-Architektur: ist KI-Chat ein Tab oder ein Side-Panel oder ein Floating-Window? User-Entscheidung Sektion 9.
- **VRF-7.2:** SSE Multi-Stream-Capacity: kann der Backend gleichzeitig Pacing-SSE + Render-SSE + Chat-Streaming-SSE? Load-Test vorher.

### 6.9 Vor Phase 8 (Cleanup)
- **VRF-8.1:** Hat irgendein Test noch eine harte Dependency auf alten Moondream-Code? Pytest-Lauf mit deaktivierten Moondream-Imports → was bricht?

---

## 7. 📅 PHASENPLAN — REALISTISCHE STUNDEN-SCHÄTZUNG

> **Wichtig:** alle Schätzungen sind in Effektiv-Stunden, **mit** Verify-Schritten, **ohne** Wartezeit auf User-Freigabe. Cowork-Pace bedeutet meist 30–50% Reduktion gegenüber Solo-Coding wegen Erklär-Aufwand und Iteration.

### Phase 0 — VERIFY-FOUNDATION (Live-Verifikation + Recherche + R1-Reconciliation)
**Geschätzt: 4–8 Stunden**
- 0.1 VRF-0.1 bis VRF-0.4 ausführen (Computer-Use für `ollama list`, `ollama ps`, Test-Frame-Probe-Calls)
- 0.2 Vision-Modell-Recherche: 5 Kandidaten-Modelle pullen (jeweils 4–10 GB Download), kuratiere 5 Test-Frames, manuelle Bewertung
- 0.3 R1-Reconciliation User-Entscheidung dokumentieren → CLAUDE.md-Edit-Vorschlag (kein Apply ohne Phase-Freigabe)
- 0.4 LIVE_STATUS_2026-05-15.md schreiben mit echten Ergebnissen

### Phase 1 — BACKBONE (Ollama-Client + Model-Registry + Auto-Selection + Settings-Slider)
**Geschätzt: 12–20 Stunden**
- 1.1 `src/pb_studio/ai/ollama_client.py` (4–6h: HTTP-Client + Vision-Support + Streaming + Tests)
- 1.2 `src/pb_studio/ai/llm_backend.py` Protocol + OllamaBackend + MoondreamBackend (Legacy) + FallbackBackend (2–4h)
- 1.3 `src/pb_studio/ai/model_registry.py` + `models/ollama_catalog.json` (2–3h)
- 1.4 `src/pb_studio/ai/auto_selector.py` mit Slider-Logic + Override-Resolution (2–3h)
- 1.5 `config.json`-Schema-Erweiterung + Migration für bestehende Configs (1–2h)
- 1.6 SettingsView.xaml + SettingsViewModel.cs erweitern um Sub-Tab "KI-MODELLE" (3–4h)
- 1.7 Tests (mock-server-basiert, offline-fähig): `test_ollama_client.py`, `test_auto_selector.py`, `test_model_registry.py` (2–4h)

### Phase 2 — MODEL-MANAGER UI (Tab + Endpoints + Download-Flow)
**Geschätzt: 16–24 Stunden**
- 2.1 `backend/routers/models_router.py` mit 7 Endpoints + SSE-Progress (4–6h)
- 2.2 Frontend `Services/ModelsApiClient.cs` + `ApiClient.cs` erweitern (2–3h)
- 2.3 `PBStudio.UI/Views/ModelsView.xaml` (4–6h: DataGrid + Cards + Custom-Pull + Progress)
- 2.4 `PBStudio.UI/ViewModels/ModelsViewModel.cs` mit SSE-Subscription (3–4h)
- 2.5 MainWindow Tab-Integration + Visibility-Binding (1h)
- 2.6 End-to-End-Test: Pull eines neuen Modells, Cancel, Delete (2–3h)
- 2.7 Tests: `test_models_router.py`, ViewModel-Tests soweit möglich (2–3h)

### Phase 3 — VIDEO-PILOT (Moondream-Replace + extract_tags_via_moondream-Repair)
**Geschätzt: 16–24 Stunden**
- 3.1 Quality-Baseline-Lauf (Moondream-Output capture) + Ollama-Vision-Lauf + Diff-Bewertung (3–4h)
- 3.2 `extract_tags_via_moondream` durch `llm_backend.generate_tags(frame_path)` ersetzen (mit Strukturiertem JSON-Prompt) (3–4h)
- 3.3 `MoondreamAnalyzer.generate_caption`-Caller via LLMBackend routen (2–3h)
- 3.4 `auto_tagger.py` Regex-Pfad als Fallback behalten, LLM-Pfad als Default einbauen (Config-Switch) (2–3h)
- 3.5 SSE-Events um `llm_backend_used`-Feld erweitern (1–2h)
- 3.6 `Views/MediaIngestView.xaml` oder `VideoLibraryView.xaml` zeigt aktives Modell pro Clip-Analyse (1–2h)
- 3.7 VRAM-Konkurrenz-Test (VRF-3.4): SigLIP+RAFT+Ollama parallel (2–4h)
- 3.8 Tests: `test_llm_backend_video.py` mit Mock-Ollama, Integration-Test mit echtem Ollama lokal markiert (2–3h)
- 3.9 Release-Build dotnet + autonom-Deploy (Iron Rule 9) (0.5h)

### Phase 4 — AUDIO-TRACK (Strukturen-Narration + Mood-Beschreibung — kleiner Track)
**Geschätzt: 8–16 Stunden**
- 4.1 VRF-4.1 Bestand klären (1h)
- 4.2 `structure_analyzer.py` mit optionalem LLM-Narration-Layer (3–5h)
- 4.3 `dj_mix_analyzer.py` Genre+Mood-Text via LLM (gegeben CLAP-Tags + BPM + Key) (3–5h)
- 4.4 `audio_router.py` SSE-Event-Erweiterung (1–2h)
- 4.5 Tests (1–3h)

### Phase 5 — PACING-TRACK
**Geschätzt: 12–20 Stunden**
- 5.1 VRF-5.1 Caller-Audit (1h)
- 5.2 `smart_director.py` Rationale-Generation via LLM (4–6h)
- 5.3 `mood_generator.py` LLM-derived-Mood (3–5h)
- 5.4 `pacing_router.py` Response-Schema-Erweiterung um `rationale_text` (2–3h)
- 5.5 Frontend (TimelineView oder DirectorView) zeigt LLM-Rationale-Popups (2–3h)
- 5.6 Tests (Verify mit echtem DJ-Mix-Sample) (1–3h)

### Phase 6 — HIRN-TAB-TRACK
**Geschätzt: 8–16 Stunden**
- 6.1 VRF-6.1 Response-Schema-Audit `/brain/explain` (1h)
- 6.2 `/brain/explain` LLM-Erklärung (3–5h)
- 6.3 Confidence-zu-Sprache-Übersetzung (Posterior-Distribution → natürlich-sprachliche Aussage) (2–4h)
- 6.4 `BrainView.xaml` zeigt LLM-Erklärung statt Score-Tupel (2–3h)
- 6.5 Tests (1–3h)

### Phase 7 — KI-CHAT-FENSTER (Greenfield)
**Geschätzt: 24–40 Stunden** (mit Abstand grösste Phase)
- 7.1 VRF-7.1 UI-Form-Entscheidung (Tab/Panel/Window) — User in Sektion 9 (0.5h)
- 7.2 `backend/routers/chat_router.py` mit 3 Endpoints + Streaming-SSE (5–8h)
- 7.3 `src/pb_studio/ai/chat_service.py` mit System-Prompt-Builder (current_project, media_db read-only, pacing-state) (4–6h)
- 7.4 SQLAlchemy Tabellen: ChatSession, ChatMessage + Migrations (2–3h)
- 7.5 `Views/ChatView.xaml` mit Message-Bubble-Layout, Streaming-Token-Display, Send-Box, Markdown-Rendering (6–10h)
- 7.6 `ViewModels/ChatViewModel.cs` mit SSE-Subscription + History-Management (4–6h)
- 7.7 `Services/ChatApiClient.cs` + Streaming-Handler (2–3h)
- 7.8 MainWindow-Integration (1h)
- 7.9 VRF-7.2 Multi-Stream-SSE-Load-Test (2–3h)
- 7.10 Tests: chat_router, chat_service, ChatViewModel (Mock-SSE) (3–5h)

### Phase 8 — CLEANUP (R1-Decision umsetzen, alten Code entfernen oder als Fallback behalten)
**Geschätzt: 8–16 Stunden**
- 8.1 R1-Reconciliation in CLAUDE.md anwenden (User-Entscheidung aus Sektion 9) (1h)
- 8.2 **Entscheidung pro Modul:** Moondream-Code entfernen (riskant, kein Rollback) ODER als `FallbackBackend` behalten (sicherer, +Tech-Debt)? **User-Entscheidung Sektion 9.**
- 8.3 Bei "entfernen": `src/pb_studio/video/moondream*.py`, `models/moondream_*` raus; bei "behalten": Documentation + Test-Coverage für Fallback-Pfad
- 8.4 Setup-Scripts (`setup.bat`, `start.bat`, `launch.ps1`) prüfen: Ollama-Health-Check VOR Backend-Start hinzufügen
- 8.5 Iron Rule 9 Deployment-Audit + Release-Build (1h)
- 8.6 Spec-Drift-Cleanup: Spec 00007 T010, 00009 T006 als `[X]` markieren (1h)

### Phase 9 — TESTS + DOKU + OBSIDIAN-SYNC (Iron Rule 11)
**Geschätzt: 8–12 Stunden**
- 9.1 CLAUDE.md update: Architektur-Map um Ollama-Backbone erweitern, Iron-Rule-1-Edit, neue Iron-Rule für Vulkan-Backend-Verify? (2h)
- 9.2 CHANGELOG.md: alle Phasen mit Datum + Commit-Hash dokumentieren (1–2h)
- 9.3 Neue ADR(s): `specs/adrs/0002-ollama-headless-integration.md`, `0003-llm-backend-pluggable.md`, `0004-model-manager-ui.md`, `0005-ki-chat-greenfield.md` (3–5h)
- 9.4 Obsidian-Vault `C:\Users\david\Brain\10_Projects\PB_studio\`: INDEX.md + log.md + decisions/ aktualisieren (1–2h)
- 9.5 Full-Pytest-Lauf + Verify 542+ green (1h)

### 🔢 GESAMT-SCHÄTZUNG
| Phase | Stunden (Min) | Stunden (Max) |
|-------|---------------|---------------|
| 0 Verify-Foundation | 4 | 8 |
| 1 Backbone | 12 | 20 |
| 2 Model-Manager UI | 16 | 24 |
| 3 Video-Pilot | 16 | 24 |
| 4 Audio-Track | 8 | 16 |
| 5 Pacing-Track | 12 | 20 |
| 6 HIRN-Track | 8 | 16 |
| 7 KI-Chat (Greenfield) | 24 | 40 |
| 8 Cleanup | 8 | 16 |
| 9 Tests+Doku+Obsidian | 8 | 12 |
| **TOTAL** | **116** | **196** |

= **ca. 3–5 Personen-Wochen Full-Time**, kalendarisch **3–6 Monate** bei Cowork-Pace mit parallelen Bug-Fixes & Stress-Tests.

---

## 8. 📂 OFFENE BUGS / TASKS (Bestandsaufnahme, NICHT in Plan integriert)

Diese sind **nicht Teil** des Ollama-V2-Plans, aber müssen vom User priorisiert werden — parallel oder vorher abschließen?

### 8.1 Aus aktiven Spec-Dateien
- **Spec 00007 T008** [OBJ2] [TR-002] — `src/tools/execute_4h_stress_test.py` mit `amdsmi`-Telemetrie + Batch-Loop
- **Spec 00007 T009** [OBJ2] [TR-002] — VRAMArbiter-Eviction-Verifikation via Stress-Test
- **Spec 00007 T010** [P] [TR-005] — GPU-accelerated RenderTransform Tab-Animations (laut CHANGELOG schon implementiert → Drift)
- **Spec 00007 T012** — Full-Run `verify_release_smoke.ps1`
- **Spec 00009 T006** [P1] — `storage.py` Depth-Metadaten (laut CHANGELOG done → Drift)
- **Spec 00009 T008** [P1] — Dynamic Downsampling-Logik in `TimelineViewModel.cs`
- **Spec 00010 T006** [OBJ2] [TR-002] — 4 GB-VRAM-Stress-Test
- **Spec 00010 T007** [P] [OBJ1] — Backend-Kill während SSE-Progress + UI-Recovery
- **Spec 00010 T008** [P] — Visuelles Review "Connection Lost"-Overlay

### 8.2 Aus CHANGELOG.md → "Next Task"
- **P1.1** 4h-Stress-Test mit echtem AMF-Encoder
- **P1.2** 4 GB-VRAM-Stress-Test
- **P3.2** Dep-Update-Cluster 2: scipy / soundfile / sklearn / sentencepiece / sqlite-vec

### 8.3 Spec-vs-CHANGELOG-Drifts
Spec 00007 T010 + Spec 00009 T006 sind in Tasks.md noch `[ ]` aber laut CHANGELOG done → Cleanup-Task

### 8.4 Latente Funktions-Lücke (heute entdeckt)
- Moondream ONNX-Files fehlen → `extract_tags_via_moondream` returnt `[]`. **Wird durch Phase 3 mitgefixt.** (Das ist der Hauptgrund warum Video als Pilot-Track sinnvoll ist.)

### 8.5 User-Entscheidung erforderlich
Sequenziell vor Ollama-V2 abschließen? Oder parallel? Oder ignorieren bis nach Ollama-V2? → Sektion 9, Folge-Frage 2.

---

## 9. ❓ FREIGABE-FRAGEN (einzeln nacheinander, nicht gebündelt)

Pro AskUserQuestion-Aufruf genau EINE Frage. Reihenfolge:

**FRAGE 1 (jetzt zu stellen):** Iron-Rule-1-Reconciliation
> Drei Varianten zur Auflösung des Konflikts "R1 sagt DirectML only, Ollama nutzt Vulkan/ROCm":
> - **Variante A:** R1 erweitern auf "AMD GPU only" mit expliziter Liste erlaubter Stacks (DirectML in-process + Vulkan/ROCm via Ollama out-of-process). **Empfehlung Claude.**
> - **Variante B:** R1 unverändert + neue R1.1 Ausnahme für Ollama.
> - **Variante C:** R1 unverändert + neue Top-Level R1B "Ollama GPU-only erzwingen".
> → Welche Variante?

**FRAGE 2 (Folge):** Spec-Backlog parallel oder sequenziell?
> Die 9 offenen Spec-Tasks aus 00007/00009/00010 + 3 CHANGELOG-Next-Tasks (P1.1/P1.2/P3.2) — wie verzahnen wir das mit den 10 Ollama-V2-Phasen?
> - **A:** Spec-Backlog zuerst komplett abschließen, dann Ollama-V2 starten.
> - **B:** Parallel: jede Cowork-Session 50/50 splitten.
> - **C:** Ollama-V2 zuerst (Phasen 0–3 = Pilot), dann Spec-Backlog, dann Phasen 4–9.
> - **D:** Spec-Backlog pausieren bis Ollama-V2 done.

**FRAGE 3 (Folge):** Stunden-Schätzung 116–196h OK?
> Ist das realistische Investment-Volumen tragfähig? Falls nicht: welche Track-Phasen abspecken oder streichen?

**FRAGE 4 (Folge):** KI-Chat UI-Form?
> Tab in MainWindow, Side-Panel, oder Floating-Window? (VRF-7.1)

**FRAGE 5 (Folge):** Phase-8-Cleanup: Moondream entfernen oder als Fallback behalten?
> - **A:** Entfernen (riskant, kein Rollback, weniger Tech-Debt).
> - **B:** Als `FallbackBackend` behalten (sicher, +Tech-Debt, Wartungs-Last).
> Claude empfiehlt **B** für die ersten 3 Monate nach Ollama-Live-Going, dann re-evaluate.

**FRAGE 6 (optional, später):** Standard-Vision-Modell für Phase 3 Pilot?
> Wird sich aus VRF-0.4-Recherche ergeben. Frage stellt sich erst nach Phase-0-Lauf.

---

## 10. ⚠️ RISIKEN & VORBEHALTE

| # | Risiko | Wahrscheinlichkeit | Mitigation |
|---|--------|--------------------|-----------|
| R-V2-01 | Ollama fällt unter Last still auf CPU zurück (Vulkan-Driver-Crash) → Latenz explodiert, kein Fail-Loud-Signal | mittel | Phase-0 Hard-Block-Gate + Continuous-Health-Check via `/api/ps` + Model-Manager-UI zeigt aktiven Backend (Vulkan/ROCm/CPU) prominent. CPU = rote Warnung. |
| R-V2-02 | Gemma3/4-Vision-Quality schlechter als Moondream2 für DJ-Mix-Video-Frames (Gemma generalist) | mittel-hoch | Phase 3 hat Quality-Baseline VRF-3.3. Falls Regression → Per-Track-Override auf besseres Modell (z. B. qwen2.5-vl). Auto-Selector behält Mode-Fähigkeit, nicht Modell-Lock-In. |
| R-V2-03 | VRAM-Konkurrenz: Ollama belegt 6–9 GB, gleichzeitig wollen CLAP+SigLIP+RAFT via DirectML → OOM | hoch | VRAM-Arbiter erweitern (Cross-Track-Komponente). Default: Sequential-Mode bis 8 GB VRAM, Parallel-Mode ab 12 GB. Per-System-Tuning. |
| R-V2-04 | Ollama Service crasht mitten in Render-Pipeline → kein Fallback | mittel | `FallbackBackend` (Moondream) immer mitloaded (kostet 4–5 GB Disk, kein VRAM bis aktiv) ODER Hard-Fail + User-Notification. **User-Entscheidung Frage 5.** |
| R-V2-05 | KI-Chat-System-Prompt mit Project-Context wird zu groß → Context-Length-Limit erreicht (Llama 3.1 8B = 128k OK, kleinere Modelle = 8k–32k tight) | mittel | Context-Pruning + Sliding-Window. System-Prompt-Builder muss Context-Tokens zählen vor Ollama-Call. |
| R-V2-06 | Ollama-Service nicht installiert auf User-System → App-Crash beim Start | hoch | Setup-Script (`setup_pb_studio.ps1`) erweitern um Ollama-Install-Check + Install-Prompt. App-Start mit Ollama-Health-Check und falls fehlt: Banner "Ollama nicht erreichbar — Klick hier zum Installieren". |
| R-V2-07 | Model-Manager-UI Pull blockiert Backend-Thread → andere Requests timeout | mittel | Pull in Background-Task + SSE-Progress, nicht synchron im Request-Handler. |
| R-V2-08 | Spec-Backlog stale, weil Ollama-V2 alle Aufmerksamkeit zieht → Drift wächst | hoch (bei Wahl C/D in Frage 2) | Sektion 8 explizit als User-Entscheidung markiert. Cowork-Sessions immer mit Standing-Check "Was sind die ältesten offenen Spec-Tasks?". |
| R-V2-09 | R1-Reconciliation-Entscheidung kommt zu spät → Phase 1 schreibt Code der gegen alte R1 verstösst | niedrig | Phase 0 = R1-Reconciliation. Phase 1 darf erst starten wenn R1-Decision dokumentiert. |
| R-V2-10 | Iron-Rule-10 (100% Honesty) leidet bei Phase 7 KI-Chat: User stellt Frage, LLM halluziniert eine PB-Studio-Feature-Antwort die es nicht gibt | hoch | System-Prompt explizit constraint: "Du bist nicht Anthropic Claude. Du bist PB-Studio-Chat. Wenn du eine Funktion nicht in `current_project` findest, sag 'unbekannt' statt zu raten." Plus Disclaimer im Chat-UI. |
| R-V2-11 | CLAUDE.md wird größer als 120 Zeilen durch Architektur-Erweiterung — verstösst gegen Ziel in Sektion 6 BRAIN UPDATE PROTOCOL | sicher | Architektur-Details in ADRs auslagern (Phase 9.3), CLAUDE.md bleibt knapper Pointer. |
| R-V2-12 | Phase-7 KI-Chat braucht Streaming-Token-Display in WPF → komplexer als typische REST-Anbindung | mittel | Prototyp-Phase explizit in 7.5/7.6 mit Buffer-Time. Falls Streaming zu schwierig → Fall-Back auf Non-Streaming-First-Version. |

---

## 11. 🚦 NÄCHSTER SCHRITT

Plan-File ist geschrieben unter `PLAN_2026-05-15_Ollama_Full_Integration_v2.md` im Repo-Root.

Claude stellt jetzt **Frage 1 (Iron-Rule-1-Reconciliation)** via AskUserQuestion. Keine weiteren Fragen bevor Frage 1 beantwortet ist.

**Kein Code-Edit, kein Commit, keine Modell-Downloads bis explizite Phase-Freigabe.** Iron Rule 10.
