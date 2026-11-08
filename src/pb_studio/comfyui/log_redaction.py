"""Bounded diagnostic redaction; not a detector for arbitrary unlabeled secrets.

Recognized credential-bearing text is removed as a whole, deliberately preferring
lost diagnostic detail to partial secret leakage. Never log raw workflow graphs.
"""
from __future__ import annotations
import json
import math
import re

_SENSITIVE = re.compile(r"api[_ -]?key|access[_ -]?token|auth(?:orization)?|password|passwd|secret|credential|private[_ -]?key|client[_ -]?secret|bearer|capability|session[_ -]?(?:id|key)|token", re.I)
_URL_CREDENTIAL = re.compile(r"https?://[^\s<>]+(?:@|\?)[^\s<>]*", re.I)
_REDACTED = "[REDACTED]"
_TRUNCATED = "[TRUNCATED]"

def redact_log_value(value):
    """Return detached JSON-like diagnostics; depth, count and string bounds apply."""
    remaining = [512]
    active = set()
    def visit(item, depth=0):
        remaining[0] -= 1
        if remaining[0] < 0 or depth > 8:
            return _TRUNCATED
        if isinstance(item, str):
            if len(item) > 16384:
                return _TRUNCATED
            # Scan before JSON decoding too: malformed credential JSON fails closed.
            if _SENSITIVE.search(item) or _URL_CREDENTIAL.search(item):
                return _REDACTED
            if item.lstrip().startswith(("{", "[")):
                try:
                    parsed = json.loads(item)
                except (ValueError, RecursionError):
                    return _REDACTED
                return json.dumps(visit(parsed, depth + 1), ensure_ascii=True)
            return item
        if item is None or type(item) in (bool, int):
            return item
        if type(item) is float:
            return item if math.isfinite(item) else _TRUNCATED
        if isinstance(item, (dict, list, tuple)):
            identity = id(item)
            if identity in active:
                return _TRUNCATED
            active.add(identity)
            try:
                if isinstance(item, dict):
                    result = {}
                    for key, child in item.items():
                        if remaining[0] <= 0:
                            result["truncated"] = _TRUNCATED
                            break
                        remaining[0] -= 1
                        safe_key = key if isinstance(key, str) and len(key) <= 128 else "unknown_field"
                        if _SENSITIVE.search(safe_key) or _URL_CREDENTIAL.search(safe_key) or any(ord(c)<32 for c in safe_key):
                            result["[REDACTED_FIELD]"] = _REDACTED
                        else:
                            result[safe_key] = visit(child, depth + 1)
                    return result
                result = []
                for child in item:
                    if remaining[0] <= 0:
                        result.append(_TRUNCATED)
                        break
                    result.append(visit(child, depth + 1))
                return result
            finally:
                active.remove(identity)
        return "[UNSUPPORTED]"
    return visit(value)
