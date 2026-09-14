# Baseline: Chat Token Deltas Streaming (Spec 00026)

Datum: 2026-09-12

## Status Quo vor Refactoring
1. src/pb_studio/ai/chat_agent.py:
   - Verwendete blockierendes chat() statt chat_stream().
   - UI empfing erst den finalen kompletten Text ohne Zwischen-Streaming.
   - reasoning_content und content waren in manchen LM-Studio-Versionen unsauber getrennt.

## Geaenderte Dateien
- src/pb_studio/ai/chat_agent.py: Vollstaendige Streaming-Pipeline mit token_delta Events, strikter Trennung von reasoning_content und content, Tool-Call-Fragmentassemblierung und Fehlerabbruch nach veroeffentlichtem Inhalt.
- PBStudio.UI/Services/SSEClient.cs, PBStudio.UI/ViewModels/ChatViewModel.cs: Empfang und fliessende UI-Anzeige von Streaming-Tokens.
- Tests/test_chat_agent.py: 24 umfassende Unittests fuer Token-Deltas, Fragment-Assemblierung, Tool-Validation und Fallback-Verhalten.
