"""Smoke-Test fuer lmstudio_client.py gegen den laufenden Server.

Verifiziert end-to-end:
  - list_models() liefert >= 1 Modell
  - chat() liefert non-empty content
  - chat_stream() yieldet >= 1 Event mit done=True
  - is_alive() == True

Output: scripts liest stdout/stderr — kein JSON-File.
"""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path

# repo-root auf sys.path damit src/ als pb_studio importierbar ist
REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "src"))

from pb_studio.ai.lmstudio_client import LMStudioClient  # noqa: E402


async def main() -> int:
    failures: list[str] = []
    print("=== LM Studio Client Smoke ===")
    async with LMStudioClient() as client:
        # 1. alive
        alive = await client.is_alive()
        print(f"is_alive: {alive}")
        if not alive:
            failures.append("is_alive=False")

        # 2. list_models
        models = await client.list_models()
        print(f"list_models: {len(models)} models")
        for m in models[:5]:
            print(f"  - {m.name}")
        if not models:
            failures.append("no models")

        # 3. chat
        if models:
            m = "vk-test"  # currently loaded
            try:
                resp = await client.chat(
                    model=m,
                    messages=[{"role": "user", "content": "Antworte mit genau 3 Woertern."}],
                    options={"temperature": 0.2, "num_predict": 24},
                )
                content = (resp.get("message") or {}).get("content", "")
                print(f"chat content (model={m}): {content[:200]!r}")
                if not content.strip():
                    failures.append("chat content empty")
            except Exception as exc:
                print(f"chat ERROR: {exc}")
                failures.append(f"chat error: {exc}")

            # 4. chat_stream
            try:
                events = []
                async for ev in client.chat_stream(
                    model=m,
                    messages=[{"role": "user", "content": "Zaehle 1 2 3"}],
                    options={"temperature": 0.2, "num_predict": 16},
                ):
                    events.append(ev)
                done_events = [e for e in events if e.get("done")]
                content_total = "".join(
                    (e.get("message") or {}).get("content", "") for e in events
                )
                print(f"chat_stream: {len(events)} events, done={len(done_events)}, content={content_total[:200]!r}")
                if not done_events:
                    failures.append("chat_stream no done event")
                if not content_total.strip():
                    failures.append("chat_stream content empty")
            except Exception as exc:
                print(f"chat_stream ERROR: {exc}")
                failures.append(f"chat_stream error: {exc}")

    print("\n=== RESULT ===")
    if failures:
        print(f"FAIL: {len(failures)} issues")
        for f in failures:
            print(f"  - {f}")
        return 1
    print("PASS — all checks green")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
