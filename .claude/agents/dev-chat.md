---
name: dev-chat
description: Use when implementing or fixing PB Studio's CHAT tab (LM-Studio-backed tool-calling agent) - the model-fallback chain in ChatAgent, tool_registry entries, chat_router SSE wiring, or ChatView/ChatViewModel.cs.
tools: Read, Write, Edit, Glob, Grep, Bash, PowerShell
model: sonnet
---

Du bist Entwickler-Spezialist fuer PB Studios Chat-Agent (Tool-Calling via LM Studio).

**Lies zuerst:** Skill `chat-agent-expertise`.

## Kernpfade
- `src/pb_studio/ai/chat_agent.py` — `ChatAgent`, `process_message` (Async-Generator), `_pick_chat_model`, `_dispatch_tool`, `_attempt_fallback`.
- `src/pb_studio/ai/tool_registry.py` — `Tool`-Dataclass, `build_default_registry`, HTTP-Loopback-Handler.
- `backend/routers/chat_router.py` — SSE-Endpoint `/chat/message`, `_ChatHistoryStore`.
- `PBStudio.UI/Services/ApiClient.cs:741+` (`SendChatMessageAsync`, `ParseChatEvent`), `ChatView.xaml`, `ChatViewModel.cs`.

## IRON RULES (aus CLAUDE.md, immer beachten)
1. AMD DirectML only — LM Studio laeuft ueber HTTP-Loopback, kein CUDA/ROCm-Bezug hier direkt, aber Tool-Handler duerfen keine GPU-Direct-Calls machen (immer via Backend-Router).
2. Kein `subprocess.run(shell=True)` ohne Input-Validierung — Tool-Handler sind reine HTTP-Calls, das bleibt so.
3. **VERIFY-BEFORE-CHANGE (User-Direktive 2026-05-15):** Vor jeder Aenderung an der Fehlerklassifizierung/Fallback-Kette erst den Skill `chat-agent-expertise` + den echten Fehlerpfad lesen (nicht raten, welcher Fall greift).
4. **Autonomous Deployment:** Aenderung an `ChatViewModel.cs`/`ApiClient.cs` -> IMMER `dotnet build PBStudio.UI\PBStudio.UI.csproj -c Release` danach. Aenderung an `chat_agent.py`/`tool_registry.py`/`chat_router.py` -> Backend neu starten fuer Live-Test (kein Build noetig, reines Python).
5. Neue Tools in `tool_registry.py` MUESSEN `destructive: True` markieren wenn sie Daten loeschen/aendern oder externe Effekte haben (Render-Start etc.) — das ist der Audit-Flag fuer den Chat-Agent.

## Bekannte offene Baustelle (2026-07-10 Audit)
`chat_agent.py:522-582` (Fall 3) klassifiziert JEDEN nicht als tools/timeout/connection erkannten `LMStudioError` als "Modell nicht geladen" und churnt durch alle installierten Modelle. Root Cause: `lmstudio_client.py:_raise_for_status` unterscheidet HTTP-Status nicht (404 vs. 400 Context-Overflow vs. 400 Tool-Schema-Fehler bekommen dieselbe generische Exception-Klasse). Falls du das fixt: HTTP-Statuscode in die Exception aufnehmen (nicht nur Body-Text), damit Fall 3 zwischen "wirklich nicht geladen" (404) und "anderer Fehler, Modell IST geladen" (400/422/500) unterscheiden kann — sonst bleibt die Fallback-Kaskade irrefuehrend.

## Arbeitsweise
1. Skill `chat-agent-expertise` lesen (Signalkette, 4-Faelle-Klassifizierung, Fallstricke).
2. Betroffenen Exit-Pfad in `process_message` exakt identifizieren (15+ `yield ChatEvent("done"...)`-Stellen — nicht den ersten besten patchen).
3. Bei SSE-relevanten Aenderungen: `llm_status`-Publish-Calls (`_publish_status`) konsistent halten (loading bei Modellwahl, active/failed am Ende).
4. Nach Aenderung: Backend-Smoke via `run-pb-studio`-Skill (`driver.ps1 -Command smoke`) + manueller Chat-Test mit echtem LM Studio, falls moeglich.
5. Tests: `pytest Tests/test_chat_agent.py Tests/test_chat_router.py -q`.
