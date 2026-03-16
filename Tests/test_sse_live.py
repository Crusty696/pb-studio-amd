"""SSE Live Event Stream Test."""
import requests
import threading
import time
import json
import sys

BASE = "http://127.0.0.1:8765"
events = {"gpu": [], "progress": [], "log": []}


def listen(stream, timeout=12):
    try:
        r = requests.get(f"{BASE}/events/{stream}", stream=True, timeout=timeout)
        r.encoding = "utf-8"
        for line in r.iter_lines(decode_unicode=True):
            if line and line.startswith("data:"):
                data = line[5:].strip()
                if data:
                    try:
                        events[stream].append(json.loads(data))
                    except json.JSONDecodeError:
                        events[stream].append({"raw": data})
    except requests.exceptions.ReadTimeout:
        pass
    except Exception as e:
        print(f"  SSE {stream} error: {e}")


def main():
    print("=== SSE LIVE-UPDATE TEST (12s) ===")
    threads = []
    for stream in ["gpu", "progress", "log"]:
        t = threading.Thread(target=listen, args=(stream, 12))
        t.start()
        threads.append(t)

    for t in threads:
        t.join()

    print("\n--- ERGEBNISSE ---")
    for stream, evts in events.items():
        print(f"  {stream}: {len(evts)} Events")
        if evts:
            print(f"    Letztes: {json.dumps(evts[-1])[:150]}")

    gpu_ok = len(events["gpu"]) >= 1
    status = "PASS" if gpu_ok else "FAIL"
    print(f"\nSSE GPU-Stream: {status} ({len(events['gpu'])} events)")
    print("(Progress/Log 0 events wenn kein Task - NORMAL)")
    sys.exit(0 if gpu_ok else 1)


if __name__ == "__main__":
    main()
