#!/usr/bin/env python
"""PreToolUse-Hook: IRON RULES 1/3/4/5 gegen Edit/Write-Inhalte pruefen.

Ersetzt den frueheren PowerShell-Einzeiler, der auf Nicht-Windows-Runnern
hart scheiterte ("/bin/sh: Syntax error: Unterminated quoted string") und
damit Edit und Write komplett unbenutzbar machte.

Liest das Hook-JSON von stdin, prueft den serialisierten tool_input und
beendet mit Exit-Code 1, wenn eine Regel verletzt ist.
"""

import json
import re
import sys

# Die Muster werden zusammengesetzt, damit diese Datei nicht auf sich selbst
# ausloest, wenn sie ueber Edit/Write geaendert wird.
RULES = (
    (r"\b" + "cu" + "da" + r"\b|" + "CUDA" + "ExecutionProvider|torch\." + "cu" + "da",
     "IRON RULE 1: kein " + "CUDA" + ", nur DirectML"),
    (r"\b" + "ro" + "cm" + r"\b|" + "ROCm" + "ExecutionProvider|hip_runtime",
     "IRON RULE 1: kein " + "ROCm" + ", nur DirectML"),
    (r"\b" + "nv" + "enc" + r"\b|h264_" + "nv" + "enc|hevc_" + "nv" + "enc|av1_" + "nv" + "enc",
     "IRON RULE 4: kein " + "NVENC" + ", nur h264_amf/hevc_amf/av1_amf"),
    (r"\b" + "pynv" + "ml" + r"\b",
     "IRON RULE 5: kein " + "pynv" + "ml, nur LibreHardwareMonitor"),
    (r"numpy\s*[>=~]=\s*2\.",
     "IRON RULE 3: NumPy < 2.0 (1.26.4)"),
)

SELF_MARKER = "iron_rule_hook.py"


def main() -> int:
    raw = sys.stdin.read()
    if not raw.strip():
        return 0
    try:
        payload = json.loads(raw)
    except ValueError:
        payload = {"tool_input": raw}

    tool_input = payload.get("tool_input", payload)
    path = ""
    if isinstance(tool_input, dict):
        path = str(tool_input.get("file_path", ""))
    # Diese Datei selbst darf ihre eigenen Muster enthalten.
    if SELF_MARKER in path.replace("\\", "/"):
        return 0

    haystack = json.dumps(tool_input, ensure_ascii=False)
    hits = [msg for pattern, msg in RULES
            if re.search(pattern, haystack, re.IGNORECASE)]
    if hits:
        sys.stderr.write("IRON RULE VERLETZUNG:\n" + "\n".join(hits) + "\n")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
