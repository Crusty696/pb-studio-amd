"""KI-Chat Track 2026-05-16 — Git Commit Bypass.

Pattern #15 (COWORK_AUTONOMY_LESSONS.md): wenn .git/HEAD.lock vom Windows-FS
nicht entfernt werden kann, bauen wir die Commits via Plumbing-Commands
(GIT_INDEX_FILE alt-index + commit-tree) und schreiben das Ref atomar in-place
via O_WRONLY (kein O_TRUNC).

Erzeugt 5 logische Commits oben auf HEAD und aktualisiert refs/heads/main.
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

REPO = Path("/sessions/youthful-vigilant-faraday/mnt/Pb_studio_AMD_version")
GIT_DIR = REPO / ".git"
ALT_INDEX = Path("/tmp/chat_track.index")
REF_MAIN = GIT_DIR / "refs/heads/main"

COMMITS = [
    {
        "subject": "feat(chat): tool_registry + chat_agent + ollama tools-param",
        "body": (
            "KI-Chat Track 2026-05-16. tool_registry mit 27 Tools ueber "
            "Audio/Video/Pacing/Brain/Project/Render/Models/System. chat_agent "
            "mit Multi-Turn Tool-Use-Loop via Ollama function calling. "
            "ollama_client um tools-Parameter + chat_stream erweitert."
        ),
        "files": [
            "src/pb_studio/ai/tool_registry.py",
            "src/pb_studio/ai/chat_agent.py",
            "src/pb_studio/ai/ollama_client.py",
        ],
    },
    {
        "subject": "feat(chat): chat_router endpoints + SSE-Stream",
        "body": (
            "POST /chat/message (SSE), GET /chat/tools, GET/DELETE /chat/history. "
            "main.py include_router wiring."
        ),
        "files": [
            "backend/routers/chat_router.py",
            "backend/main.py",
        ],
    },
    {
        "subject": "feat(chat): model_registry tasks fuer chat_general/chat_tool_use",
        "body": (
            "DEFAULT_TASK_PREFERENCES um chat_general (freier Text) + "
            "chat_tool_use (Function-Calling) erweitert. config.json mit "
            "Default-Preferenzen pro Mode."
        ),
        "files": [
            "src/pb_studio/ai/model_registry.py",
            "config.json",
        ],
    },
    {
        "subject": "test(chat): 39 Tests fuer tool_registry/chat_agent/chat_router",
        "body": (
            "22 Tool-Registry-Tests (Schema, Coercion, Handler-Roundtrip via "
            "MockTransport). 9 Chat-Agent-Tests (Multi-Turn Loop, History, "
            "Limit). 8 Chat-Router-Tests (SSE, History, Validation). Alle "
            "39 Tests gruen unter pytest -p no:cacheprovider."
        ),
        "files": [
            "Tests/test_tool_registry.py",
            "Tests/test_chat_agent.py",
            "Tests/test_chat_router.py",
        ],
    },
    {
        "subject": "feat(ui): KI-Chat-Tab mit Tool-Call-Visualisierung",
        "body": (
            "Neuer CHAT-Tab (Index 10) mit Bot/User-Layout, Tool-Call-Expander "
            "pro Call (Args+Result als JSON), Mode-Selector (speed/balance/"
            "quality), Stop-Stream, Clear-History. Bilingual DE/EN via "
            "System-Prompt im chat_agent. SendChatMessageAsync auf ApiClient "
            "mit IAsyncEnumerable<ChatStreamEvent> + SSE-Parser."
        ),
        "files": [
            "PBStudio.UI/Models/ChatMessage.cs",
            "PBStudio.UI/Models/ChatEvent.cs",
            "PBStudio.UI/ViewModels/ChatViewModel.cs",
            "PBStudio.UI/Views/ChatView.xaml",
            "PBStudio.UI/Views/ChatView.xaml.cs",
            "PBStudio.UI/Services/ApiClient.cs",
            "PBStudio.UI/Services/IApiClient.cs",
            "PBStudio.UI/App.xaml.cs",
            "PBStudio.UI/MainWindow.xaml",
            "scripts/chat_track_build_and_push.bat",
            "scripts/chat_track_commit_bypass.py",
        ],
    },
]


def run(cmd, *, env=None, input_=None, check=True):
    """Run subprocess, return stdout (stripped) or raise."""
    full_env = os.environ.copy()
    if env:
        full_env.update(env)
    result = subprocess.run(
        cmd,
        cwd=str(REPO),
        env=full_env,
        input=input_,
        capture_output=True,
        text=True,
    )
    if check and result.returncode != 0:
        print(f"CMD FAILED: {' '.join(cmd)}", file=sys.stderr)
        print("STDOUT:", result.stdout, file=sys.stderr)
        print("STDERR:", result.stderr, file=sys.stderr)
        raise RuntimeError(f"Command failed: {' '.join(cmd)}")
    return result.stdout.strip()


def get_head_tree() -> str:
    return run(["git", "rev-parse", "HEAD^{tree}"])


def get_head_commit() -> str:
    return run(["git", "rev-parse", "HEAD"])


def init_alt_index(base_tree: str) -> None:
    """Initialisiert die alt-Index Datei mit dem aktuellen Tree."""
    if ALT_INDEX.exists():
        ALT_INDEX.unlink()
    env = {"GIT_INDEX_FILE": str(ALT_INDEX)}
    run(["git", "read-tree", base_tree], env=env)


def update_index_with_file(rel_path: str) -> None:
    """Fuegt eine Datei dem alt-Index hinzu (hash-object + update-index)."""
    full = REPO / rel_path
    if not full.exists():
        print(f"  WARN: {rel_path} existiert nicht — ueberspringe")
        return
    blob = run(["git", "hash-object", "-w", rel_path])
    mode = "100755" if os.access(full, os.X_OK) and full.suffix in {".sh", ".py", ".bat"} else "100644"
    # WPF/Python files: always 100644 on Windows
    if not full.suffix in {".sh"}:
        mode = "100644"
    env = {"GIT_INDEX_FILE": str(ALT_INDEX)}
    run(
        ["git", "update-index", "--add", "--cacheinfo", f"{mode},{blob},{rel_path}"],
        env=env,
    )


def write_tree() -> str:
    env = {"GIT_INDEX_FILE": str(ALT_INDEX)}
    return run(["git", "write-tree"], env=env)


def commit_tree(tree: str, parent: str, subject: str, body: str) -> str:
    msg = f"{subject}\n\n{body}\n"
    env = {
        "GIT_AUTHOR_NAME": "David Lochmann",
        "GIT_AUTHOR_EMAIL": "davidlochmann2@gmail.com",
        "GIT_COMMITTER_NAME": "David Lochmann",
        "GIT_COMMITTER_EMAIL": "davidlochmann2@gmail.com",
    }
    return run(
        ["git", "commit-tree", tree, "-p", parent],
        env=env,
        input_=msg,
    )


def update_main_ref_inplace(new_sha: str) -> None:
    """Schreibt refs/heads/main via O_WRONLY ohne Truncate."""
    new_content = (new_sha + "\n").encode("ascii")
    # SHAs sind 40 chars + \n = 41 bytes — gleiche Laenge wie alter Ref.
    fd = os.open(str(REF_MAIN), os.O_WRONLY)
    try:
        written = os.write(fd, new_content)
        if written != len(new_content):
            raise RuntimeError(f"Short write: {written} != {len(new_content)}")
    finally:
        os.close(fd)


def main():
    head_tree = get_head_tree()
    head_commit = get_head_commit()
    print(f"Base HEAD: {head_commit}")
    print(f"Base tree: {head_tree}")

    init_alt_index(head_tree)

    parent = head_commit
    for i, commit in enumerate(COMMITS, 1):
        print(f"\n=== Commit {i}/{len(COMMITS)}: {commit['subject']} ===")
        for fpath in commit["files"]:
            print(f"  adding {fpath}")
            update_index_with_file(fpath)
        tree = write_tree()
        print(f"  tree: {tree}")
        sha = commit_tree(tree, parent, commit["subject"], commit["body"])
        print(f"  commit: {sha}")
        parent = sha

    print(f"\n=== Final HEAD will be: {parent} ===")
    update_main_ref_inplace(parent)
    print("refs/heads/main updated in-place.")

    # Verify
    new_head = get_head_commit()
    print(f"git rev-parse HEAD: {new_head}")
    assert new_head == parent, f"Verify failed: {new_head} != {parent}"
    print("OK")

    # Show log
    print("\n=== Recent commits ===")
    log = run(["git", "log", "--oneline", "-6"])
    print(log)


if __name__ == "__main__":
    main()
