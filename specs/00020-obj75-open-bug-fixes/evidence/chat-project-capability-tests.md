# T034/T035 Chat Project-Capability Verification

**Result:** PASS

## Implemented contract

- Chat captures one project ID/root/epoch context for the full SSE turn.
- An opaque per-turn capability is propagated only to canonical PB Studio
  loopback requests, including long-running tools.
- Middleware rejects missing, revoked or stale project identity with HTTP 409.
- Project switch cancels/drains the bound turn; History commit remains bound to A.
- After SSE start, context loss produces typed `error`/`done` events.
- Confirmation cancellation and client disconnect revoke pending capability state.

## Parent verification

```text
PYTHONPATH=src .venv\Scripts\python.exe -m pytest \
  Tests\test_chat_router.py Tests\test_chat_agent.py \
  Tests\test_owner_capability_global.py -q
```

Result: **35 passed**, 4 third-party deprecation warnings, 14.91 s.

No WPF API DTO change was required; `/chat/message` remains HTTP-200 SSE and uses
the existing typed `error`/`done` event surface after the response has started.
