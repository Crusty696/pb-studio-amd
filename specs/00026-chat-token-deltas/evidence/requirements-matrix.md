# Requirements Matrix: Chat Token Deltas (Spec 00026)

| Anforderung | Beschreibung | Implementierung | Test | Status |
|---|---|---|---|---|
| FR-001 | Streaming Textdeltas vor Abschluss | src/pb_studio/ai/chat_agent.py | test_chat_streaming_text_deltas_before_final_text | VERIFIED |
| FR-002 | Reasoning-Isolation | src/pb_studio/ai/chat_agent.py | test_chat_reasoning_content_is_isolated_from_content | VERIFIED |
| FR-003 | Tool-Call Assemblierung ueber Fragmente | src/pb_studio/ai/chat_agent.py | test_chat_fragmented_tool_calls_assembled_and_executed_once | VERIFIED |
| FR-004 | Fallback-Verhalten vor/nach Token-Veroeffentlichung | src/pb_studio/ai/chat_agent.py | test_chat_stream_interrupted_after_published_content_prevents_fallback | VERIFIED |
| FR-005 | Sauberes Schliessen bei Abbruch/EOF | src/pb_studio/ai/chat_agent.py | test_chat_stream_unexpected_eof_raises_error | VERIFIED |
| FR-006 | Kompatibilitaet finaler Text & UI | PBStudio.UI/ViewModels/ChatViewModel.cs | test_chat_streaming_text_deltas_before_final_text | VERIFIED |
| TR-001 | Timeout- und Modellstatus-Erhalt | src/pb_studio/ai/chat_agent.py | test_long_running_tool_dispatch_uses_extended_timeout | VERIFIED |
