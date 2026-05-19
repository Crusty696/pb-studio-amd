# LM Studio Phase-A Verify Report — 2026-05-17

**Status:** BLOCKED — Refactor NICHT gestartet (per Rollback-Contract).

## TL;DR

LM Studio Server läuft, 9 Modelle sind heruntergeladen, aber **kein Modell lässt sich in die Runtime laden**. Identischer Fehler bei JEDEM Modell, JEDER Konfiguration — auch bei 1 GB Modell mit `--gpu off`. Das deutet auf ein Runtime/Backend-Problem auf System-Ebene hin, nicht auf ein Model- oder VRAM-Problem. Ich kann das nicht autonom fixen (Settings müssen via UI/Reinstallation angepasst werden). Per Iron Rule 10: ich refactore NICHT bis das gelöst ist.

## Was funktioniert (live verifiziert)

- LM Studio **0.4.13** installiert
- Local Server **Status: Running** an `http://localhost:1234`
- `GET /v1/models` → 200, listet 9 Modelle
- `lms` CLI vorhanden unter `C:\Users\david\.lmstudio\bin\lms.exe`
- `lms ps` → zeigt Modelle als "IDLE" nach Load-Versuch (aber tatsächlich nicht funktional)
- Models-Storage liegt unter `C:\Users\david\.ollama\models\` (geteilt mit Ollama-Install)

## Verfügbare Modelle (aus `lms ls`)

| Modell | Params | Arch | Größe |
|---|---|---|---|
| dirty-muse-writer-v01-uncensored-erotica-nsfw-i1 | 9B | Gemma 2 | 5.48 GB |
| gemma-3-1b-it-glm-4.7-flash-heretic-uncensored-thinking_gguf | 1B | gemma3 | 1.07 GB |
| gemma-4-26b-a4b-it-ultra-uncensored-heretic | 26B-A4B | gemma4 | 14.48 GB |
| gemma-4-31b-it-uncensored | 31B | gemma4 | 13.12 GB |
| google/gemma-4-e4b | 7.5B | gemma4 | 9.02 GB |
| qwen/qwen3-vl-8b | 8B | qwen3vl | 6.19 GB |
| qwen3.5-9b-uncensored-hauhaucs-aggressive | 9B | qwen35 | 6.55 GB |
| raw-uncensored-qwen3-14b-heretic-recovered | 14B | qwen3 | 5.75 GB |
| text-embedding-nomic-embed-text-v1.5 | — | Nomic BERT | 84.11 MB (Embedding) |

## Was nicht funktioniert (live verifiziert)

Jeder Load-Versuch bricht ab mit:

```
Error: Error loading model.
(Exit code: 18446744072635810000). Unknown error. Try a different model and/or config.
```

Hex: `0xFFFFFFFE_FB4A8048` — generischer Runtime-Error.

Versuchte Pfade:

1. **LM Studio App UI** — Modell-Dropdown → Klick auf Modellzeile → schließt nur, lädt nicht
2. **Toast „Load Model"-Button** nach qwen/qwen3-vl-8b Download → „Failed to load the model. Error loading model."
3. **REST API `POST /api/v1/models/load`** → HTTP 400 mit leerem Body bei jedem Modell
4. **REST API `POST /v1/chat/completions`** → HTTP 400 (JIT-Load wird intern getriggert und scheitert)
5. **`lms load` CLI** mit Default-Config → Error loading model
6. **`lms load` CLI** mit `--context-length 4096 --gpu off` (Minimal-Config, smallest 1GB Modell) → Error loading model
7. **`lms load` CLI** mit `--context-length 8192 --gpu max` (Qwen 9B) → Error loading model
8. **Embedding-Modell** `text-embedding-nomic-embed-text-v1.5` (84 MB, LM-Studio-bundled) → Error loading model

**Auch das LM-Studio-eigene bundled Embedding-Modell scheitert.** Das schließt model-spezifische Probleme aus.

## Developer-Log-Auszug (LM Studio UI)

```
2026-05-17 22:16:08 [DEBUG] LlamaV4::load called with model path C:\Users\david\.ollama\models\HauhauCS\Qwen3.5-9B-Uncensored-HauhauCS\Qwen3.5-9B-Uncensored-HauhauCS-Aggressive-Q4_K_M.gguf
                   LlamaV4::load config: n_parallel=4 n_ctx=262144 kv_unified=true
2026-05-17 22:16:09 [ERROR] Failed to load model "qwen3.5-9b-uncensored-hauhaucs-aggressive". Error: Error loading model.
2026-05-17 22:16:09 [DEBUG] Received request: POST to /v1/embeddings with body { "input": "Hello world", "model": "text-embedding-nomic-embed-text-v1.5" }
2026-05-17 22:16:10 [INFO] [LlamaEmbeddingEngine] Loading model from path: C:\Users\david\.lmstudio\internal\bundled-models\nomic-ai\nomic-embed-text-v1.5-GGUF\nomic-embed-text-v1.5.Q4_K_M.gguf
2026-05-17 22:16:10 [ERROR] Failed to load model "text-embedding-nomic-embed-text-v1.5". Error: Error loading model.
```

## Hypothesen für Root-Cause

- **Wahrscheinlichste Ursache:** Runtime-Engine (LlamaV4 / Vulkan / ROCm) ist nach LM-Studio-Install defekt oder inkompatibel mit der aktuellen AMD-Driver-Version (AMD Bug Report Tool ist installiert → AMD-GPU-System).
- Modell-Storage zeigt auf `C:\Users\david\.ollama\models\` — geteilt mit Ollama. LM Studio scannt Ollama-Pfade auch, Models werden korrekt erkannt aber Runtime kann die GGUF-Dateien nicht öffnen.
- Auch CPU-Fallback (`--gpu off`) failed identisch → das schließt reine GPU-Driver-Probleme aus, das Problem ist tiefer im LlamaV4 Engine-Code oder einer Native-DLL.
- Build/Install-Reste vom 0.4.13-Update könnten die Runtime kaputtgemacht haben.

## Was der User tun muss

1. **LM Studio Logs** noch tiefer öffnen → es sollte eine konkrete Native-Exception unterhalb von „Error loading model" geben (Stack-Trace, fehlende DLL, etc.). Im Developer-Logs-Panel ist das auf Default-Level nicht sichtbar — Log-Level auf VERBOSE/DEBUG hochziehen (rechts oben im Developer Logs-Panel).
2. **In LM Studio Settings → Hardware/Runtime** prüfen:
   - Welche Runtime ist gewählt? (CPU / Vulkan / ROCm?)
   - Auf jede Variante einzeln umschalten und Modell laden versuchen
3. **LM Studio reparieren** via App-Settings → "Manage LM Runtimes" → Reinstall Runtime
4. **Falls 3. nicht hilft:** LM Studio neu installieren (Settings sichern, dann Programm + `%LOCALAPPDATA%\LM-Studio` löschen und neu installieren)
5. Sobald **mindestens ein Text-Modell + ein Embedding-Modell** erfolgreich laden (`lms ps` zeigt STATUS=Loaded statt IDLE und API-Test `/v1/chat/completions` antwortet mit Status 200): bitte mir Bescheid geben.

## Was ich gemacht habe (autonom)

- 5 Verify-Scripts geschrieben in `scripts/verify_lmstudio*.ps1` und `scripts/lmstudio_*.ps1`
- 10 Tasks angelegt (Phase A in_progress, B1–D pending)
- Per Computer-Use Run-Dialog die Scripts ausgeführt, Outputs nach `.lm_studio_*.json/.txt` in der Repo-Root
- LM Studio App geöffnet, Modell-Dropdown durchgeklickt, Developer-Tab angeschaut

## Was ich NICHT gemacht habe (per Rollback-Contract)

- Kein Code-Edit an `src/pb_studio/ai/`, `backend/`, `PBStudio.UI/`
- Kein `git add`, kein Commit, kein Push
- Keine bestehenden Ollama-Imports gelöscht
- Kein Refactor des `model_registry`/`chat_agent`/`llm_narrator`

Per Iron Rule 10: ich werde nicht behaupten, der Refactor wäre erfolgt, weil ich ihn nicht live verifizieren kann, solange kein Modell lädt.
Per Iron Rule 13 (Verify-Before-Change): erst funktionierende LM-Studio-Runtime, dann Refactor.

## Artefakte in der Repo-Root

- `.lm_studio_check.json` — initialer Server-Status (server_up=true, 9 Modelle gelistet)
- `.lm_studio_tools_check.json` — Tool-Use Test (alle 4 Text-Modelle 400)
- `.lm_studio_debug.json` — Raw HTTP Response (Body leer bei 400)
- `.lm_studio_load.json` — `POST /api/v1/models/load` (alle 400 leer)
- `.lms_cli_output.txt` — lms CLI ps/ls/load Output (model registered, load failed)
- `.lms_load_smart.txt` — lms CLI mit kleinem Context (immer noch failed)
- `.lm_studio_verify_full.json` — alle 4 Probes (chat/tool/stream/embed) gegen geladenes Modell (alle 400)

Diese Dateien können nach Resolution gelöscht werden (sind `.gitignore`-Kandidaten oder direkt `rm`).

## Bereit zum Weitermachen sobald

```powershell
& "$env:USERPROFILE\.lmstudio\bin\lms.exe" ps
```

mindestens ein Modell mit STATUS=**Loaded** zeigt und

```powershell
$body = '{"model":"<modelname>","messages":[{"role":"user","content":"PING"}],"max_tokens":8}'
Invoke-RestMethod -Uri http://localhost:1234/v1/chat/completions -Method Post -Body $body -ContentType 'application/json'
```

eine echte Antwort (Status 200, Content "PONG"/"PING"/whatever) zurückgibt.

Dann poste den Modellnamen und ich mache mit Phase B (Refactor) weiter — dauert ab dann ~30–45 Min für Code + Tests + Build + Commits + Push.
