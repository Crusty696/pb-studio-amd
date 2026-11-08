"""Read-only live collection of emitted PB Studio diagnostics. No app control."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
from pathlib import Path
import re
import time
import uuid


def redact(text: str) -> str:
    text = re.sub(r'(?i)\bBearer\s+[A-Za-z0-9._~+/=-]+', 'Bearer [REDACTED]', text)
    text = re.sub(
        r'''(?ix)(["']?(?:[\w-]*?(?:api[_-]?key|token|password|passwd|pwd|secret|authorization|capability))["']?\s*[:=]\s*)(?:"[^"\r\n]*"|'[^'\r\n]*'|[^\s,;}]+)''',
        r'\1[REDACTED]', text,
    )
    text = re.sub(r'(?i)(https?://)[^/\s:@]+:[^@\s/]+@', r'\1[REDACTED]@', text)
    return re.sub(
        r'(?:sk-(?:proj-)?[A-Za-z0-9_-]{16,}|(?:gh[pousr]|github_pat)_[A-Za-z0-9_]{16,}|eyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,})',
        '[REDACTED]', text,
    )


class Recorder:
    MAX_LINE = 131072
    CHUNK = 65536
    PATTERNS = ('wpf_app.log', 'backend.log*', 'backend_live.*.log',
                'native_crash.log', 'launch_*.log', 'start_*.log')

    def __init__(self, logs: Path, output: Path):
        self.logs = logs.resolve()
        self.output = output.resolve()
        self.output.parent.mkdir(parents=True, exist_ok=True)
        self.writer = self.output.open('x', encoding='utf8', buffering=1)
        self.states: dict[tuple[int, int], dict] = {}
        self.path_ids: dict[Path, tuple[int, int]] = {}
        self.errors: set[str] = set()
        self.closed = False
        self.emit('RECORDER', 'START; existing content excluded; no app control. '
                  'Sources: WPF/backend/stdout/stderr/native/launcher. '
                  'Not exhaustive tracing. Rotation/recreation may lose lines between polls. '
                  'Local paths retained; common credentials redacted, not a privacy guarantee.')
        for path in self.sources():
            self.read(path, initial=True)

    def emit(self, source: str, text: str):
        stamp = datetime.now(timezone.utc).isoformat(timespec='milliseconds')
        self.writer.write(f'{stamp} [{source}] {redact(text)}\n')
        self.writer.flush()

    def sources(self):
        paths = {p for pattern in self.PATTERNS for p in self.logs.glob(pattern)
                 if p.is_file() and p.resolve() != self.output and not p.name.endswith('.gz')}
        # Read uncompressed rotated files before their replacements.
        return sorted(paths, key=lambda p: (p.name == 'backend.log', p.name))

    def read(self, path: Path, initial=False):
        try:
            with path.open('rb') as stream:
                stat = path.stat()
                identity = (stat.st_dev, stat.st_ino)
                previous = self.path_ids.get(path)
                self.path_ids[path] = identity
                state = self.states.get(identity)
                if previous is not None and previous != identity:
                    self.emit('RECORDER', f'SOURCE_RESET {path.name}; replacement; possible gap')
                if state is None:
                    size = stat.st_size if initial else 0
                    prefix = stream.read(min(64, size))
                    state = dict(offset=size, prefix=prefix, pending=b'', dropping=False,
                                 name=path.name)
                    if initial and size:
                        stream.seek(size - 1)
                        state['dropping'] = stream.read(1) != b'\n'
                    self.states[identity] = state
                    self.emit('RECORDER', f'SOURCE {path.name}; start_offset={size}')
                else:
                    prefix = state['prefix']
                    stream.seek(0)
                    if stat.st_size < state['offset'] or stream.read(len(prefix)) != prefix:
                        self.finish_fragment(state)
                        self.emit('RECORDER', f'SOURCE_RESET {path.name}; truncated/rewritten; possible gap')
                        state.update(offset=0, prefix=b'', pending=b'', dropping=False)
                stream.seek(state['offset'])
                # Bound work per source/poll; continue backlog on next poll.
                for _ in range(16):
                    chunk = stream.read(self.CHUNK)
                    if not chunk:
                        break
                    state['offset'] += len(chunk)
                    self.consume(state, chunk)
                if not state['prefix'] and state['offset']:
                    stream.seek(0)
                    state['prefix'] = stream.read(min(64, state['offset']))
                state['remaining'] = max(0, path.stat().st_size - state['offset'])
        except OSError as exc:
            key = f'{path.name}:{type(exc).__name__}:{exc.errno}'
            if key not in self.errors:
                self.errors.add(key)
                self.emit('RECORDER', f'SOURCE_READ_ERROR {key}; retry on next poll')

    def consume(self, state: dict, chunk: bytes):
        for fragment in chunk.splitlines(keepends=True):
            # Only LF ends a record; preserve split UTF-8 and CRLF.
            ends = fragment.endswith(b'\n')
            if not state['dropping']:
                state['pending'] += fragment
                if len(state['pending']) > self.MAX_LINE:
                    state['pending'] = b''
                    state['dropping'] = True
                    self.emit('RECORDER', f'LINE_DROPPED {state["name"]}; over {self.MAX_LINE} bytes')
            if ends:
                if not state['dropping']:
                    self.emit(state['name'], state['pending'].decode('utf8', errors='replace').rstrip('\r\n'))
                state['pending'] = b''
                state['dropping'] = False

    def finish_fragment(self, state):
        if state['pending']:
            self.emit(state['name'], '[PARTIAL_LINE] ' + state['pending'].decode('utf8', errors='replace'))
            state['pending'] = b''

    def poll(self):
        for path in self.sources():
            self.read(path)

    def close(self):
        if self.closed:
            return
        self.poll()
        for state in self.states.values():
            self.finish_fragment(state)
            if state.get('remaining', 0):
                self.emit('RECORDER', f'SOURCE_BACKLOG {state["name"]}; '
                          f'{state["remaining"]} unread bytes at stop; incomplete capture')
        self.emit('RECORDER', 'END; recording stopped independently of PB Studio.')
        self.writer.close()
        self.closed = True


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    root = Path(__file__).resolve().parents[1]
    parser.add_argument('--logs-dir', type=Path, default=root / 'logs')
    parser.add_argument('--output', type=Path)
    parser.add_argument('--duration', type=float, help='Stop after N seconds (verification).')
    args = parser.parse_args(argv)
    if args.duration is not None and args.duration <= 0:
        parser.error('--duration must be positive')
    output = args.output or root / 'logs' / 'sessions' / (
        'manual_' + datetime.now().strftime('%Y%m%d_%H%M%S') + '_' + uuid.uuid4().hex[:8] + '.log')
    recorder = Recorder(args.logs_dir, output)
    print(f'LOGDATEI: {recorder.output}', flush=True)
    print('Aufzeichnung aktiv. PB Studio manuell bedienen. Ende: Strg+C.', flush=True)
    started = time.monotonic()
    try:
        while args.duration is None or time.monotonic() - started < args.duration:
            recorder.poll()
            time.sleep(0.25)
    except KeyboardInterrupt:
        pass
    finally:
        recorder.close()
        print(f'LOG GESICHERT: {recorder.output}', flush=True)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
