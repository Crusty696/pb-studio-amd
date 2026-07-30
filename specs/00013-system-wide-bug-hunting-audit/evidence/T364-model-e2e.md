# T364 — LM Studio and Ollama model E2E

Status: CONFIRMED

## Live baseline

- Captured 2026-07-30 on the configured loopback endpoints.
- LM Studio JIT: enabled in
  `C:\Users\david\.lmstudio\.internal\http-server-config.json`.
- LM Studio: port `1234`, 14 installed models, one loaded model
  (`hermes-ha-qwen35`, `qwen/qwen3.5-9b`, chat + vision).
- Ollama: port `11434`, 15 installed models, zero loaded models.
- Raw provider receipt:
  `evidence/T364-provider-baseline.json`
  (`04EF8B4BB67943F27663F2EA3F211E4EC72AA237C02879BB4A702812BDDD7A28`).

## Startup refresh and inventory truth

- Fresh backend start logged at `07:55:18`:
  `Modellinventar aktualisiert: 29 Modelle (lmstudio=ready, ollama=ready)`.
- `GET /models/list?refresh=true` returned generation `2`, 29 cards and both
  providers as `ready`.
- Installed/loaded truth agreed with the native provider endpoints:
  LM Studio `/v1/models` + `/api/v0/models`, Ollama `/api/tags` + `/api/ps`.
- Every displayed card was installed and had provider-specific inventory
  sources. No unverified downloadable card was emitted.

## Capability routing

- `video_captioning/balance` selected
  `lmstudio:qwen/qwen3.5-9b`.
- Receipt required `vision`; verified capabilities were `chat, vision`.
- `chat_tool_use/balance` selected
  `lmstudio:hermes-ha-qwen35` with verified `chat, vision`.
- With LM Studio offline, `video_captioning/balance` selected
  `ollama:gemma4:12b`, still with verified `chat, vision`.
- No text-only model was accepted for a vision task.

## Provider/model switch and persistence

- Owner-authorized activation persisted only
  `chat_tool_use -> ollama:gpt-oss:20b`.
- The response named the same provider/model and reported
  `vision_enabled=false`.
- After a real backend restart, the recommendation receipt returned
  `ollama:gpt-oss:20b`, source `persisted_task_preference`.
- The Ollama card was active only for `Tool-Ausführung`.
- Test-only override values were removed after the proof. Final configuration:
  zero task overrides, zero provider overrides, LM Studio URL restored to
  `http://127.0.0.1:1234/v1`.

## Offline and online-empty states

- Stopping the real LM Studio server produced:
  `lmstudio=offline`, `ollama=ready`, 15 Ollama cards.
- Restarting LM Studio restored `lmstudio=ready`; the prior loaded
  `hermes-ha-qwen35` model remained loaded and usable.
- The isolated loopback empty-provider stub produced:
  `lmstudio=online_empty`, `ollama=ready`, zero LM Studio cards and zero
  downloadable cards.
- Only provider discovery actions remained visible; no individual model was
  claimed downloadable without verification.
- Stub source:
  `evidence/T364-empty-provider-stub.py`
  (`BF335A4B9A78A1AFF26AF20ABFB9EA6B273B2A02F0B872D27434A58B55BAFB32`).

## Bounded receipt-bound failover

- Live first receipt:
  `lmstudio:hermes-ha-qwen35` (`explicit_override`).
- LM Studio was stopped after receipt selection; the bound chat request failed
  with a real connection error.
- Exactly one invalidation and two total refreshes occurred.
- Second receipt:
  `ollama:moondream:latest` (`persisted_task_preference`).
- The real OpenAI-compatible HTTP response reported the exact same provider
  model, `moondream:latest`.
- Total candidates: 2 of the allowed maximum 3.
- Raw receipt:
  `evidence/T364-failover-e2e.json`
  (`49D75BB2C9DC3F649F296406746A273E50DB5449C1377922393E544CE1A6276B`).
- Harness:
  `evidence/T364-failover-e2e.py`
  (`76132767C96F191AF2BF2A294EA62E80BD36409A70F3A327F95AA9C4B2BF1203`).

## Recovery

- LM Studio server restored on port `1234`, JIT enabled.
- LM Studio restored to 14 installed / one loaded model.
- Ollama restored to 15 installed / zero loaded models.
- Backend and empty-provider stub stopped.
- `config.json` parses successfully and contains only the planned T344/T353
  semantic changes relative to Git.

## Gate

CONFIRMED: startup refresh, truthful provider inventory, capability-safe
selection, provider/model persistence, offline/empty states and bounded
receipt-bound failover all passed against live local providers.
