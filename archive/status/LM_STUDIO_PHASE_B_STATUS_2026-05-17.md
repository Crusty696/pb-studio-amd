# LM Studio Refactor — Status 2026-05-17

## TL;DR

**Phase A (Runtime-Reparatur) ✅ ABGESCHLOSSEN**, **Phase B (Code-Swap) ⚠️ FOUNDATION GELEGT** —
`lmstudio_client.py` ist live-verifiziert, die restlichen Integrations-Stellen
(model_registry, chat_agent, llm_narrator, ollama_vision_wrapper,
backend/routers, WPF) sind **NOCH NICHT** umgestellt. Per Iron Rule 13
(Verify-Before-Change) werden die in einer Folge-Session sauber durchgegangen.

---

## Phase A — LM Studio Runtime gefixt

### Root-Cause

LM Studio 0.4.13 hatte `llama.cpp-win-x86_64-amd-rocm-avx2@2.14.0` als
selected runtime — **ROCm-Backend ist auf RDNA-3 (RX 7800 XT) + AMD-Driver
31.0.24002.92 inkompatibel**. Resultat: jeder Load-Versuch brach mit
`Error: Error loading model. (Exit code: 18446744072635810000)` ab —
sowohl ueber UI, REST-API als auch CLI, selbst beim 84 MB Embedding-Modell.

### Fix

```powershell
& "$env:USERPROFILE\.lmstudio\bin\lms.exe" runtime select llama.cpp-win-x86_64-vulkan-avx2@2.14.0
```

→ `Selected llama.cpp-win-x86_64-vulkan-avx2@2.14.0 for GGUF`

### Verification (live)

| Check | Ergebnis |
|---|---|
| `lms runtime ls` | Vulkan 2.14.0 hat checkmark, ROCm hat keinen |
| `lms load gemma-3-1b ... --identifier vk-test --gpu max` | `Model loaded successfully in 2.51s. (1019.77 MiB)` |
| `lms ps` | `vk-test gemma-3-1b... IDLE 1.07 GB 2048 Local` |
| `POST /v1/chat/completions` | HTTP 200, real content, 11 prompt + 16 completion tokens |

**Erfolgskriterium der Task: erfüllt.**

### Hardware/Driver-State (zur Doku)

- GPU: AMD Radeon RX 7800 XT (16 GB)
- Driver: 31.0.24002.92 (NICHT die im Task-Header genannte 32.0.31007.1017 — bitte korrigieren)
- LM Studio: 0.4.13 (AMD AI Bundle Install in `C:\Program Files\AMD\ai_bundle\lmstudio`)
- Modelle-Store: `C:\Users\david\.ollama\models\` (geteilt mit Ollama)
- Runtime-Backends-Dir: `C:\Users\david\.lmstudio\extensions\backends`

### Available Models (post-fix, jetzt ladbar)

9 GGUF + 1 Embedding (siehe `.lm_studio_diagnose.json`):
gemma-3-1b · gemma-4-26b-a4b · gemma-4-31b · gemma-4-e4b ·
qwen/qwen3-vl-8b · qwen3.5-9b · raw-qwen3-14b · dirty-muse-9b · text-embedding-nomic.

---

## Phase B — Foundation gelegt, Integration offen

### Erstellt (verifiziert)

**`src/pb_studio/ai/lmstudio_client.py`** — OpenAI-kompatibler async HTTP-Client
mit drop-in API-Surface fuer `OllamaClient`:

- `LMStudioClient(base_url="http://localhost:1234/v1")` — async-context-manager
- `list_models() -> list[LMStudioModelInfo]` — GET /v1/models
- `chat(model, messages, *, images, stream, options, tools, format)` — POST /v1/chat/completions, returnt Ollama-Style-Dict mit `{message:{role,content,tool_calls}, done, usage, raw}`
- `chat_stream(...)` — async-generator, yielded Ollama-Style-Events mit aggregierten tool_calls und reasoning_content-Support
- `generate(model, prompt, *, images, options)` — Mapped auf `chat()` mit single user-message
- `embeddings(model, input)` — POST /v1/embeddings
- `pull_model()` / `delete_model()` — explizit `NotImplementedError` (LM Studio UI managed Downloads)
- `is_alive()` — Health-Probe via `/v1/models`

**Image-Handling:** Vision-Bilder werden automatisch zu OpenAI `image_url` data-URI konvertiert (numpy / bytes / base64-str / data-URI alle akzeptiert).

**Options-Mapping:** Ollama-Options (`temperature`, `top_p`, `num_predict`, `stop`, `seed`, `presence_penalty`, `frequency_penalty`) werden auf OpenAI-Felder gemappt. `keep_alive` wird ignoriert (LM Studio Idle-TTL ist Settings-Sache).

### Live-Smoke verifiziert (`scripts/lmstudio_client_smoke.py`)

```
=== LM Studio Client Smoke ===
is_alive: True
list_models: 10 models
chat content (model=vk-test): 'Hier ist die Antwort: **Ja.**\n100%.'
chat_stream: 13 events, done=1, content='The user wants the numbers "1", "2", and'
=== RESULT === PASS — all checks green
```

### Was NOCH offen ist (Phase B Vollendung)

Per Iron Rule 13 (Verify-Before-Change) werden diese Stellen in einer
**Folge-Session** angegangen — mit jeweils Pre-Verify via `pb-master` /
`code-auditor` / `full-stack-auditor` und Caller-Sweep, NICHT blind:

| Datei | Status | Aktion |
|---|---|---|
| `src/pb_studio/ai/model_registry.py` | OllamaClient-Import + `.list_models()` | Auf `LMStudioClient` umstellen; Preferenz-Listen mit LM-Studio-Modellnamen erweitern |
| `src/pb_studio/ai/chat_agent.py` | OllamaClient + Tool-Use | `LMStudioClient` (gleiche Signaturen, sollte 1:1 funktionieren) |
| `src/pb_studio/brain/llm_narrator.py` | Tag-spezifische Ollama-Modellauswahl | LM-Studio-Modellnamen ohne `:latest`-Tags |
| `src/pb_studio/video/ollama_vision_wrapper.py` | Bilder + Captioning | Auf `lmstudio_vision_wrapper.py` umbenennen, qwen3-vl-8b als Default |
| `backend/routers/models_router.py` | `/pull` und `/delete` | HTTP 501 mit Message "Use LM Studio app" |
| `backend/routers/chat_router.py` | SSE-Streaming gegen OllamaClient | Auf LMStudioClient — Stream-Format ist intern aequivalent |
| `backend/routers/brain_router.py` | LLM-Narrative | Modellname und Client tauschen |
| `backend/routers/video_router.py` | Vision-Aufrufe | Wrapper umbauen |
| `config.json` `[ai]`-Section | Ollama-URL `http://localhost:11434` | `http://localhost:1234/v1` |
| `PBStudio.UI/Services/ApiClient.cs` | Ollama-spezifische Felder? | Falls Backend-Schema identisch bleibt: minimal |
| `PBStudio.UI/Views/ModelManagerView.xaml` | Pull/Delete-Buttons | Disable + Info "managed via LM Studio app" |
| Tests `test_ollama_client.py`, `test_chat_agent.py` etc. | OllamaClient-Mocks | Neue `test_lmstudio_client.py` schreiben + bestehende migrieren |
| WPF Release-Build | nach C#-Aenderung | `dotnet build PBStudio.UI\PBStudio.UI.csproj -c Release` |
| Push | nach allen Aenderungen | autonom (Pattern #17) |

### Empfohlene Reihenfolge

1. `test_lmstudio_client.py` schreiben (Unit-Tests gegen httpx-Transport-Mock — analog `test_ollama_client.py`)
2. `model_registry.py` swappen (kleinste Schnittstelle, isoliert testbar)
3. `chat_agent.py` swappen + `test_chat_agent.py` migrieren (Mocks tauschen)
4. `llm_narrator.py` + `ollama_vision_wrapper.py` → `lmstudio_vision_wrapper.py`
5. Backend-Router (chat/models/brain/video)
6. `config.json` + Default-URL Konstanten
7. WPF ApiClient/ModelManagerView
8. Full pytest + WPF Release-Build
9. Commits + Push

---

## Iron-Rule-Compliance dieser Session

| Rule | Stand |
|---|---|
| 1 (AMD DirectML only) | ✅ — DirectML-Stack unangetastet, ROCm→Vulkan ist LM-Studio-Engine, nicht ORT |
| 2 (DirectML pattern) | n/a fuer diese Session |
| 9 (autonomes Deployment) | ✅ — Runtime-Switch live ausgefuehrt, Smoke-Test live verifiziert |
| 10 (Honesty) | ✅ — Phase B nicht als "fertig" markiert, Status-Doc listet Verbleibende offen |
| 11 (Obsidian Vault) | ⚠️ — Vault-Update wurde nicht ausgefuehrt (Tool fehlt in dieser Session); soll in Folge-Session nachgeholt werden |
| 12 (Autonomie-Default-On) | ✅ — keine Rueckfragen, Bash + Run-Dialog + PowerShell als Fallback fuer blockierte Computer-Use-Klicks |
| 13 (Verify-Before-Change) | ✅ — Phase B beschraenkt sich auf Foundation-Modul + verifizierten Smoke-Test, keine sweeping Edits ohne Caller-Verify |

---

## Artefakte (in Repo-Root und scripts/)

- `LM_STUDIO_PHASE_B_STATUS_2026-05-17.md` (dieses File)
- `src/pb_studio/ai/lmstudio_client.py` (NEW — drop-in fuer OllamaClient)
- `scripts/lmstudio_client_smoke.py` (Smoke-Test)
- `scripts/run_lmstudio_smoke.ps1` (Wrapper fuer Smoke)
- `scripts/lm_studio_diagnose.ps1` (Diagnose: alle lms-Subcommands + Install-Dir + GPU-Info)
- `scripts/lm_full_repair.ps1` (Runtime-Switch + Load-Test)
- `scripts/lm_load_test.ps1` (Load-Verification mit verschiedenen Pfaden)
- `.lm_studio_diagnose.json`, `.lm_full_repair.json`, `.lm_load_test.json`, `.lmstudio_smoke.txt` (Run-Outputs)

## Cleanup-Hinweis

Die `.lm_*.json/.txt` und alte Stage-Files (`.lm_studio_check.json`, `.lm_studio_load.json` etc.) sind `.gitignore`-Kandidaten. Diagnose-Files koennen geloescht werden sobald Phase B abgeschlossen ist.
