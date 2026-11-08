from pathlib import Path

from scripts.record_app_session import Recorder, redact


def make_recorder(tmp_path):
    logs = tmp_path / 'sources'
    logs.mkdir()
    output = tmp_path / 'session.log'
    return logs, output, Recorder(logs, output)


def test_excludes_history_and_flushes_live_lines(tmp_path):
    logs = tmp_path / 'sources'
    logs.mkdir()
    source = logs / 'wpf_app.log'
    source.write_text('old\n', encoding='utf8')
    output = tmp_path / 'session.log'
    recorder = Recorder(logs, output)
    with source.open('a', encoding='utf8') as stream:
        stream.write('UI-Aktion: Klick\n')
    recorder.poll()
    text = output.read_text(encoding='utf8')
    assert 'UI-Aktion: Klick' in text
    assert '] old' not in text
    recorder.close()


def test_split_utf8_and_final_fragment(tmp_path):
    logs, output, recorder = make_recorder(tmp_path)
    source = logs / 'backend.log'
    source.write_bytes(b'Gr\xc3')
    recorder.poll()
    with source.open('ab') as stream:
        stream.write(b'\xbcne\nRest')
    recorder.poll()
    assert 'Grüne' in output.read_text(encoding='utf8')
    recorder.close()
    assert 'Rest' in output.read_text(encoding='utf8')


def test_replacement_longer_than_old_file_detected(tmp_path):
    logs, output, recorder = make_recorder(tmp_path)
    source = logs / 'wpf_app.log'
    source.write_text('first\n', encoding='utf8')
    recorder.poll()
    replacement = logs / 'replacement'
    replacement.write_text('new session much longer\n', encoding='utf8')
    replacement.replace(source)
    recorder.poll()
    recorder.close()
    text = output.read_text(encoding='utf8')
    assert 'SOURCE_RESET' in text and 'new session much longer' in text


def test_same_file_truncate_and_regrow_detected(tmp_path):
    logs, output, recorder = make_recorder(tmp_path)
    source = logs / 'backend.log'
    source.write_text('old partial', encoding='utf8')
    recorder.poll()
    source.write_text('different new session\n', encoding='utf8')
    recorder.poll()
    recorder.close()
    text = output.read_text(encoding='utf8')
    assert 'SOURCE_RESET' in text and 'different new session' in text


def test_output_never_overwrites_existing_file(tmp_path):
    logs = tmp_path / 'sources'
    logs.mkdir()
    output = tmp_path / 'session.log'
    output.write_text('keep', encoding='utf8')
    import pytest
    with pytest.raises(FileExistsError):
        Recorder(logs, output)
    assert output.read_text() == 'keep'


def test_redacts_credentials_in_text_and_json():
    text = redact('Bearer abcdefghi "api_key": "my-secret" password=hidden '
                  'PBSTUDIO_OWNER_CAPABILITY=owner https://user:pass@host '
                  'sk-abcdefghijklmnopqr')
    for secret in ['abcdefghi', 'my-secret', 'hidden', '=owner', 'user:pass', 'sk-abcdefgh']:
        assert secret not in text
    assert redact('http://user:pass@host') == 'http://[REDACTED]@host'


def test_overlong_line_dropped_with_gap_marker(tmp_path):
    logs, output, recorder = make_recorder(tmp_path)
    (logs / 'backend.log').write_bytes(b'x' * (recorder.MAX_LINE + 1) + b'\nnext\n')
    recorder.poll()
    recorder.close()
    text = output.read_text(encoding='utf8')
    assert 'LINE_DROPPED' in text and 'next' in text


def test_observes_rotated_backend_before_original_recreated(tmp_path):
    logs, output, recorder = make_recorder(tmp_path)
    source = logs / 'backend.log'
    source.write_text('one\n', encoding='utf8')
    recorder.poll()
    with source.open('a', encoding='utf8') as stream:
        stream.write('last before rotation\n')
    source.rename(logs / 'backend.log.1')
    source.write_text('new\n', encoding='utf8')
    recorder.poll()
    recorder.close()
    assert 'last before rotation' in output.read_text(encoding='utf8')


def test_cli_persists_source_line_and_clean_end(tmp_path):
    import subprocess
    import sys
    logs = tmp_path / 'sources'
    logs.mkdir()
    output = tmp_path / 'session.log'
    script = Path(__file__).resolve().parents[1] / 'scripts' / 'record_app_session.py'
    process = subprocess.Popen(
        [sys.executable, str(script), '--logs-dir', str(logs), '--output', str(output),
         '--duration', '1'], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    try:
        assert process.stdout and 'LOGDATEI:' in process.stdout.readline()
        (logs / 'wpf_app.log').write_text('UI-Aktion: Test\napi_key=secret-test\n', encoding='utf8')
        stdout, stderr = process.communicate(timeout=15)
        assert process.returncode == 0, stderr
        text = output.read_text(encoding='utf8')
        assert 'UI-Aktion: Test' in text and 'secret-test' not in text
        assert '[RECORDER] END' in text and 'LOG GESICHERT:' in stdout
    finally:
        if process.poll() is None:
            process.terminate()
            process.wait(timeout=5)
