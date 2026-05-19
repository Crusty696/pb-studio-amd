# KONSOLIDIERTER STATUS — Ollama/Gemma-Integration (verifiziert)
**Datum:** 2026-05-15, 13:30 Uhr
**Iron Rule 10 — 100% Honesty:** Dieser Bericht ersetzt frühere Audit-Aussagen aus dieser Session.

---

## 0. ⚡ KRITISCHE EHRLICHKEITS-KORREKTUR

Mein erstes Audit dieser Session hat **NULL Ollama-Treffer in `src/`/`backend/`** gemeldet. **Das war falsch.** Die Files existieren, mein erstes Grep hat sie aus unbekanntem Grund nicht erfasst. Korrektur via `Glob` + Explorer-Sichtprüfung + Live-Read.

**Iron Rule 13 (Verify-Before-Change) hätte das früher gefangen** — ich hätte vor dem Plan-Schreiben einen Glob auf `src/pb_studio/ai/ollama*` machen müssen. Lesson Learned.

---

## 1. ✅ WAS BEREITS IMPLEMENTIERT IST (live verifiziert via Read)

### 1.1 Backend Ollama-Stack
| Datei | Zeilen | Status |
|-------|--------|--------|
| `src/pb_studio/ai/ollama_client.py` | 422 | ✅ vollständig — async httpx Client, Vision-Support, Retry, Exception-Hierarchie |
| `src/pb_studio/ai/model_registry.py` | 269 | ✅ Auto-Selection mit speed/balance/quality + User-Override |
| `src/pb_studio/video/ollama_vision_wrapper.py` | 271 | ✅ sync wrapper für video_router, In-Memory-Cache (256 Einträge), deutscher Default-Prompt |
| `backend/routers/models_router.py` | 318 | ✅ 5 Endpoints: GET /list, GET /available, POST /pull (SSE), DELETE /{name}, GET /recommendations |
| `backend/main.py` Line 255+265 | — | ✅ `models_router` importiert + registriert |
| `backend/routers/video_router.py` Lines 839-883 | — | ✅ Ollama primary, Moondream fallback, `tag_source` Audit-Trail (R10) |
| `config.json` | erweitert | ✅ `ai.ollama_base_url`, `ai.default_mode`, `ai.task_preferences` (video/image_captioning × speed/balance/quality), `ai.task_overrides: {}` |

### 1.2 Tests (alle in pytest 542 passed enthalten)
- ✅ `Tests/test_ollama_client.py` — 19 Tests via `httpx.MockTransport`
- ✅ `Tests/test_model_registry.py` — 21 Tests
- ✅ `Tests/test_ollama_vision_wrapper.py` — 16 Tests
- Total Ollama-Test-Coverage: **56 Tests, alle grün**

### 1.3 Live-Verifikation (aus `_verify_part2.log` + meiner Phase 1.2)
- ✅ Ollama API: `0.24.0` läuft auf `localhost:11434`
- ✅ Installiertes Modell: **`gemma4:latest` (9.6 GB)** — einziges
- ⚠️ `ollama ps`: aktuell kein Modell im VRAM
- ❌ Backend NICHT laufend (Port 8765 unerreichbar)
- ⚠️ Moondream-ONNX-Files fehlen weiterhin (`moondream_encoder.onnx`/`decoder.onnx`) — nur `moondream_pytorch.pt`. `extract_tags_via_moondream` returnt `[]` ehrlich → **Fallback-Pfad de facto defekt**

### 1.4 Geplanter aber noch nicht erfolgter Commit
`_ollama_pilot_commit.bat` (im Repo, untracked) plant **3 Commits** für das implementierte Backend:
1. `feat(ai): Ollama HTTP-Client + ModelRegistry mit Auto-Selection`
2. `feat(video): Ollama-Vision-Wrapper für Frame-Tag-Extraktion`
3. `feat(backend): /models/* Router + Ollama primary in Phase-4 Captioning`

Diese 3 Commits sind **noch nicht ausgeführt** — alle Source-Files sind aktuell `untracked` im git.

---

## 2. ❌ WAS NOCH FEHLT (laut V2-Plan)

### 2.1 Frontend Ollama-Integration (komplett offen)
- ❌ `PBStudio.UI/Views/ModelsView.xaml` — neuer Top-Level-Tab "MODELLE"
- ❌ `PBStudio.UI/ViewModels/ModelsViewModel.cs` mit SSE-Subscription
- ❌ `PBStudio.UI/Services/ModelsApiClient.cs` (oder ApiClient.cs-Erweiterung)
- ❌ `MainWindow.xaml` Tab-Integration für "MODELLE"
- ❌ `SettingsView.xaml`-Erweiterung: Sub-Tab "KI-MODELLE" mit Slider + Per-Task-Override-Dropdowns

### 2.2 KI-Chat-Greenfield (Phase 7 in V2-Plan, größte Phase, 24-40h)
- ❌ `backend/routers/chat_router.py` — POST /chat/send (streaming), GET/DELETE /chat/history
- ❌ `src/pb_studio/ai/chat_service.py` — System-Prompt-Builder mit Project-Context
- ❌ SQLAlchemy: ChatSession + ChatMessage + Migration
- ❌ `PBStudio.UI/Views/ChatView.xaml` mit Streaming-Token-Display
- ❌ `PBStudio.UI/ViewModels/ChatViewModel.cs`
- ❌ `PBStudio.UI/Services/ChatApiClient.cs`

### 2.3 Audio-Track LLM-Erweiterung (Phase 4, 8-16h)
- ❌ `structure_analyzer.py` LLM-Narration-Layer
- ❌ `dj_mix_analyzer.py` Genre+Mood-Text via LLM
- ❌ `audio_router.py` SSE-Event-Erweiterung

### 2.4 Pacing-Track LLM-Integration (Phase 5, 12-20h)
- ❌ `smart_director.py` Rationale-Generation via LLM
- ❌ `mood_generator.py` LLM-derived-Mood
- ❌ `pacing_router.py` `rationale_text`-Field
- ❌ Frontend TimelineView/DirectorView Rationale-Popups

### 2.5 HIRN-Track LLM-Erweiterung (Phase 6, 8-16h)
- ❌ `/brain/explain` LLM-Erklärung statt Score-Tupel
- ❌ Confidence-zu-Sprache-Übersetzung
- ❌ `BrainView.xaml` zeigt LLM-Erklärung

### 2.6 Cleanup + Doku (Phase 8+9, 16-28h)
- ❌ CLAUDE.md Section 3 update mit Ollama-Architektur-Map
- ❌ CLAUDE.md Iron-Rule-1-Reconciliation (siehe unten)
- ❌ CHANGELOG.md Eintrag
- ❌ Neue ADRs: 0002-ollama-headless-integration, 0003-llm-backend-pluggable, 0004-model-manager-ui, 0005-ki-chat-greenfield
- ❌ Obsidian-Vault `C:\Users\david\Brain\10_Projects\PB_studio\` (INDEX.md + log.md + decisions/)

### 2.7 Spec-Backlog (8 offene Tasks, unabhängig von Ollama)
- 00007: T008 (4h-Stress-Test), T009 (VRAM-Eviction-Verify), T012 (verify_release_smoke)
- 00009: T008 (Dynamic Downsampling)
- 00010: T006 (4 GB-Stress-Test), T007 (Backend-Kill SSE), T008 (Visual Overlay-Review)
- CHANGELOG-Next: P1.1, P1.2, P3.2 (Dep-Update Cluster 2)
- Drift: Spec 00007 T010 + 00009 T006 — in tasks.md noch `[ ]` aber laut CHANGELOG done

---

## 3. ⚠️ OFFENER IRON-RULE-1-KONFLIKT (V2-Plan FRAGE 1)

**Kern:** CLAUDE.md Iron Rule 1 sagt heute "AMD DirectML ONLY — NO ROCm". Ollama nutzt unter Windows-AMD aber Vulkan (oder ROCm experimentell). Das ist ein Widerspruch.

Drei Varianten zur Auflösung (V2-Plan Sektion 1.2):
- **Variante A (Claude empfiehlt):** R1 erweitern auf "AMD GPU only" mit positiver Liste: DirectML in-process + Vulkan/ROCm via Ollama out-of-process. NumPy/PyTorch direkt dürfen weiter nur DirectML.
- **Variante B:** R1 unverändert + neue R1.1 als Ollama-Ausnahme.
- **Variante C:** R1 unverändert + neue R1B "Ollama GPU-only" als parallele Top-Level-Regel.

**Status:** Frage 1 wurde **noch nicht beantwortet**, aber Code wurde trotzdem geschrieben. Strenge R1-Auslegung würde das implementierte Backend faktisch illegal machen.

---

## 4. 🚦 EMPFEHLUNG — was JETZT als nächstes zu tun ist

In dieser Reihenfolge, jeder Schritt mit Verifikations-Output:

### Schritt 1 (sofort, low-risk): Iron-Rule-1-Reconciliation entscheiden
User-Antwort auf Variante A/B/C nötig. Ich kann **A empfehlen**, weil:
- klare positive Liste (kein Sondertür-Pattern)
- explizit aussagt was erlaubt UND was verboten
- erlaubt Ollama sauber als Headless-Service ohne R1-Verbiegung

### Schritt 2: VRF-0.3 ausführen — hat `gemma4:latest` Vision?
Probe-Call gegen `/api/generate` mit Test-Frame als base64. Wenn NEIN → für Video-Pilot brauchen wir LLaVA/qwen2.5-vl. Aktuell ist `gemma4:latest` das einzige installierte Modell — falls nicht Vision-fähig, muss erst etwas Anderes gepullt werden.

### Schritt 3: 3 pending Commits ausführen
`_ollama_pilot_commit.bat` ausführen. Das macht das implementierte Backend sichtbar im git-log und unblockt weitere Arbeit.

### Schritt 4: Backend live starten + Endpoints durchtesten
Phase 1.3 — `uvicorn` starten, `/models/list`, `/models/available`, `/models/recommendations` durchtesten.

### Schritt 5: Pytest live-Verifikation (542/10/0 bestätigen oder neuere Zahl)

### Schritt 6: Frontend ModelsView bauen (V2-Plan Phase 2.3–2.5)

### Schritt 7-N: Weitere Phasen nach V2-Plan (Sektion 7)

---

## 5. 📋 PRAGMATISCHE FRAGEN AN USER (vor weiterem Code-Edit)

1. **Iron-Rule-1-Variante:** A / B / C?
2. **3 Pending Commits ausführen?** (sicher, weil Code schon getestet via pytest 542 passed)
3. **VRF-0.3 Vision-Probe-Call ausführen?** (klärt ob gemma4:latest Vision hat — Hard-Block für Phase 3)
4. **Wenn gemma4:latest KEIN Vision: Welches Vision-Modell pullen?** Kandidaten:
   - LLaVA 7B Q4 (4.5 GB, balance)
   - qwen2.5-vl 7B (5-6 GB, quality)
   - llama3.2-vision 11B (7.9 GB, quality)
   - MiniCPM-V 8B (5.5 GB, speed)

---

## 6. 🛑 IRON RULE 10 — was ich NICHT weiß

- Hat `gemma4:latest` Vision-Support? (Modellname ist mehrdeutig — Gemma 3 IT hat Vision, "Gemma 4" als Tag könnte alles sein.) → Probe-Call nötig
- Welcher Compute-Backend (Vulkan/ROCm/CPU) Ollama tatsächlich nutzt? → `ollama serve` Logs lesen oder `/api/ps` `size_vram` checken
- VRAM-Konkurrenz Ollama + DirectML-CLAP+SigLIP+RAFT? → Stress-Test nötig
- Quality-Vergleich Moondream vs Ollama-Gemma für DJ-Mix-Frames? → Baseline-Lauf nötig

---

**Ich warte jetzt auf User-Antworten auf Fragen 1-4 in Sektion 5, bevor ich Code-Edits, Commits oder Modell-Downloads starte.**
