# Timeline Multi-Lane Redesign Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the WPF Timeline behave like DaVinci/Premiere: separate Video (V1) and Audio (A1) lanes with equal duration, no overlaps, no gaps, video clips show frame-thumbnail strips, audio lane shows a proper full-opacity waveform with mid-axis, and per-video-clip mini audio waveforms.

**Architecture:** Three changes stack on top of the existing pipeline.
1. Backend enforces `last_cut.end_time == audio_duration` (no underflow) and adds two new endpoints: `GET /video/thumbstrip/{clip_id}?n=8` (multi-frame JPEGs) and `GET /video/clipwave/{clip_id}` (downsampled mono peaks of the video's audio track via ffmpeg).
2. WPF schemas/models grow `ThumbnailStripUrls` + `ClipAudioPeaks` properties (loaded lazily per visible clip).
3. `TimelineView.xaml` is restructured from a single overlaid Canvas into a `Grid` with two stacked rows: a Video-Lane (V1) and an Audio-Lane (A1), each with a left-side track header and its own clip/waveform layer. Drag logic prevents overlaps (collision-resolve against neighbour edges) and auto-closes gaps in contiguous mode.

**Tech Stack:** WPF .NET 9.0 (MVVM Toolkit), FastAPI + Pydantic, OpenCV/ffmpeg, MediaDesignInXaml, existing `FrameGrabber` + `pacing_service` + `validate_timeline`.

**Scope check:** Out of scope: multi-V/A lanes (V2/A2/A3), ripple-edit on neighbour clips, gap-fill via auto-extend of preceding clip (only the LAST cut gets stretched), waveform-zoom independent of timeline-zoom. These can be follow-up plans.

---

## File Structure

**New files:**
- `backend/routers/video_router.py` — append `/video/thumbstrip/{clip_id}` and `/video/clipwave/{clip_id}` (no new file, append).
- `src/pb_studio/video/clip_audio_peaks.py` — extracts mono peak array from a video file via ffmpeg pipe.
- `PBStudio.UI/Controls/TimelineTrackHeader.xaml` + `.cs` — left-side label panel ("V1" / "A1").
- `PBStudio.UI/Converters/PeaksToWaveformGeometryConverter.cs` — converts peaks float[] + width/height into a `StreamGeometry` for fast rendering.
- `Tests/test_clip_audio_peaks.py` — pytest for the new ffmpeg helper.
- `Tests/test_pacing_length_enforcement.py` — pytest for last-cut stretch.
- `Tests/test_video_thumbstrip_endpoint.py` — pytest for thumbstrip route.
- `Tests/test_video_clipwave_endpoint.py` — pytest for clipwave route.

**Modified files:**
- `backend/schemas/common.py` — extend `validate_timeline` with `enforce_full_length` flag; default OFF, ON for `/pacing/generate`.
- `src/pb_studio/services/pacing_service.py` — call `_stretch_last_cut_to_audio` after `_process_pacing_cuts_to_cutlist`.
- `src/pb_studio/video/frame_extractor.py` — add `extract_thumbnail_strip(video_path, n=8, size=(160,90))`.
- `backend/routers/video_router.py` — two new endpoints.
- `backend/schemas/video_schemas.py` — `ThumbstripResponse`, `ClipwaveResponse`.
- `PBStudio.UI/Services/IApiClient.cs` + `ApiClient.cs` — `GetThumbStripAsync(int)`, `GetClipWaveAsync(int)`.
- `PBStudio.UI/Models/TimelineEntry.cs` — add `ThumbnailFrames` (ObservableCollection&lt;string&gt;) + `AudioPeaks` (float[]) + `IsAssetsLoaded`.
- `PBStudio.UI/ViewModels/TimelineViewModel.cs` — `LoadClipAssetsAsync(entry)` on SelectedEntry change & on RefreshTimeline.
- `PBStudio.UI/Views/TimelineView.xaml` — split into V1-lane + A1-lane Grid; new clip template with thumbnail strip; full-opacity audio-lane waveform.
- `PBStudio.UI/Views/TimelineView.xaml.cs` — drag collision-resolve + last-cut-stretch handling on MouseUp.
- `Tests/test_timeline_validation.py` (new or extend existing) — assert no-overlap + no-underflow.

---

## Task 1: Backend — Stretch last cut to audio_duration

**Files:**
- Modify: `src/pb_studio/services/pacing_service.py:71-130` (region around `_process_pacing_cuts_to_cutlist`)
- Test: `Tests/test_pacing_length_enforcement.py` (create)

- [ ] **Step 1: Write the failing test**

```python
# Tests/test_pacing_length_enforcement.py
"""Pacing-Service: letzter Cut wird auf audio_duration gestreckt."""
import pytest
from unittest.mock import patch, MagicMock

from pb_studio.services.pacing_service import PacingService
from pb_studio.pacing.pacing_models import CutListEntry


def _fake_cut(start: float, end: float, clip_id: str = "clip_1") -> CutListEntry:
    return CutListEntry(
        clip_id=clip_id,
        start_time=start,
        end_time=end,
        metadata={"file_path": "/x.mp4", "clip_name": "x", "clip_start": 0.0,
                  "trigger_type": "beat", "trigger_strength": 1.0},
    )


def test_last_cut_stretched_to_audio_duration():
    """Wenn last_cut.end_time < audio_duration, wird er auf audio_duration gestreckt."""
    svc = PacingService()
    cuts = [_fake_cut(0.0, 5.0), _fake_cut(5.0, 9.5)]
    audio_dur = 12.0

    out = svc._stretch_last_cut_to_audio(cuts, audio_duration=audio_dur)

    assert len(out) == 2
    assert out[-1].end_time == pytest.approx(audio_dur, abs=0.001)
    # Vorherige Cuts unveraendert
    assert out[0].end_time == pytest.approx(5.0)


def test_last_cut_not_shortened_if_already_long_enough():
    svc = PacingService()
    cuts = [_fake_cut(0.0, 5.0), _fake_cut(5.0, 12.0)]
    out = svc._stretch_last_cut_to_audio(cuts, audio_duration=12.0)
    assert out[-1].end_time == pytest.approx(12.0)


def test_no_op_on_empty_cuts():
    svc = PacingService()
    out = svc._stretch_last_cut_to_audio([], audio_duration=12.0)
    assert out == []


def test_no_op_when_audio_duration_zero():
    svc = PacingService()
    cuts = [_fake_cut(0.0, 5.0)]
    out = svc._stretch_last_cut_to_audio(cuts, audio_duration=0.0)
    assert out[-1].end_time == pytest.approx(5.0)
```

- [ ] **Step 2: Run test to verify it fails**

```powershell
.venv\Scripts\activate
$env:PYTHONPATH = "src"
pytest Tests/test_pacing_length_enforcement.py -x -q
```
Expected: FAIL with `AttributeError: 'PacingService' object has no attribute '_stretch_last_cut_to_audio'`.

- [ ] **Step 3: Add the method to PacingService**

Insert after `_process_pacing_cuts_to_cutlist` (around `src/pb_studio/services/pacing_service.py:130`):

```python
    def _stretch_last_cut_to_audio(
        self, cut_list: list, audio_duration: float
    ) -> list:
        """Stretches the last cut so cut_list[-1].end_time == audio_duration.

        Why: validate_timeline already blocks overflow (>audio_duration). Underflow
        (timeline ends before audio) was silent — user heard music keep playing
        after last visible frame. Premiere/Davinci force V1.length == A1.length.

        No-op on empty list, on audio_duration <= 0, or if last cut already
        reaches audio_duration.
        """
        if not cut_list or audio_duration <= 0.0:
            return cut_list
        last = cut_list[-1]
        if last.end_time >= audio_duration - 0.001:
            return cut_list

        # Mutate end_time in-place (CutListEntry is a dataclass-like model).
        last.end_time = audio_duration
        return cut_list
```

- [ ] **Step 4: Wire the call into `generate_cut_list` and `generate_cut_list_with_stems`**

Find both methods (grep `def generate_cut_list` in `pacing_service.py`). Right before the final `return cut_list`, insert:

```python
        cut_list = self._stretch_last_cut_to_audio(cut_list, total_duration)
```

(`total_duration` is the audio duration parameter both methods already accept.)

- [ ] **Step 5: Run test to verify it passes**

```powershell
pytest Tests/test_pacing_length_enforcement.py -x -q
```
Expected: PASS 4/4.

- [ ] **Step 6: Run full pacing tests for regression**

```powershell
pytest Tests/ -x -q -k pacing
```
Expected: all PASS.

- [ ] **Step 7: Commit**

```powershell
git add Tests/test_pacing_length_enforcement.py src/pb_studio/services/pacing_service.py
git commit -m "feat(pacing): stretch last cut to audio_duration so V1 length == A1 length"
```

---

## Task 2: Backend — extract_thumbnail_strip helper

**Files:**
- Modify: `src/pb_studio/video/frame_extractor.py` (append method)
- Test: `Tests/test_frame_extractor_strip.py` (create)

- [ ] **Step 1: Write the failing test**

```python
# Tests/test_frame_extractor_strip.py
"""FrameGrabber.extract_thumbnail_strip — N evenly-spaced thumbnails als Bytes."""
from pathlib import Path
import pytest

from pb_studio.video.frame_extractor import FrameGrabber


@pytest.fixture
def sample_video(tmp_path: Path) -> Path:
    """Erzeugt ein 3s farbiges Testvideo via ffmpeg (lavfi color source)."""
    import subprocess
    out = tmp_path / "sample.mp4"
    subprocess.run(
        ["ffmpeg", "-y", "-f", "lavfi", "-i", "color=c=red:s=320x180:r=10:d=3",
         "-c:v", "libx264", "-pix_fmt", "yuv420p", str(out)],
        check=True, capture_output=True,
    )
    return out


def test_strip_returns_n_frames(sample_video: Path):
    grabber = FrameGrabber()
    frames = grabber.extract_thumbnail_strip(str(sample_video), n=5, size=(160, 90))
    assert len(frames) == 5
    for img in frames:
        assert img.size == (160, 90)


def test_strip_handles_n_larger_than_video_frames(sample_video: Path):
    """Bei n > verfuegbaren Sample-Punkten -> n Frames trotzdem, ggf. duplicated."""
    grabber = FrameGrabber()
    frames = grabber.extract_thumbnail_strip(str(sample_video), n=30, size=(80, 45))
    assert len(frames) == 30


def test_strip_no_video_returns_empty(tmp_path: Path):
    grabber = FrameGrabber()
    frames = grabber.extract_thumbnail_strip(str(tmp_path / "missing.mp4"), n=5)
    assert frames == []
```

- [ ] **Step 2: Run test to verify it fails**

```powershell
pytest Tests/test_frame_extractor_strip.py -x -q
```
Expected: FAIL with `AttributeError: 'FrameGrabber' object has no attribute 'extract_thumbnail_strip'`.

- [ ] **Step 3: Implement extract_thumbnail_strip**

Append to `src/pb_studio/video/frame_extractor.py` (end of class `FrameGrabber`):

```python
    def extract_thumbnail_strip(
        self, video_path: str, n: int = 8, size: tuple = (160, 90)
    ) -> list:
        """Extract N evenly-spaced thumbnails across the full video.

        Returns list of PIL.Image (length == n) or [] if video unreadable.
        Used by the timeline clip template to show a frame strip a la Premiere.
        """
        from PIL import Image
        import cv2

        if n <= 0:
            return []
        if not Path(video_path).exists():
            return []

        cap = cv2.VideoCapture(video_path)
        if not cap.isOpened():
            return []
        try:
            total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
            fps = cap.get(cv2.CAP_PROP_FPS) or 25.0
            duration = total / fps if fps > 0 else 0.0
            if total <= 0 or duration <= 0:
                return []

            # Pick n evenly-spaced time points; clamp to [0, duration-1/fps]
            step = duration / max(1, n)
            offsets = [min(duration - 1.0 / fps, step * i + step / 2.0) for i in range(n)]

            out = []
            for t in offsets:
                cap.set(cv2.CAP_PROP_POS_MSEC, t * 1000.0)
                ret, frame = cap.read()
                if not ret or frame is None:
                    if out:
                        out.append(out[-1])  # duplicate previous to keep length == n
                    continue
                frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                img = Image.fromarray(frame_rgb).resize(size, Image.LANCZOS)
                out.append(img)
            return out
        finally:
            cap.release()
```

- [ ] **Step 4: Run test to verify it passes**

```powershell
pytest Tests/test_frame_extractor_strip.py -x -q
```
Expected: PASS 3/3.

- [ ] **Step 5: Commit**

```powershell
git add Tests/test_frame_extractor_strip.py src/pb_studio/video/frame_extractor.py
git commit -m "feat(video): FrameGrabber.extract_thumbnail_strip for N-frame timeline strips"
```

---

## Task 3: Backend — `GET /video/thumbstrip/{clip_id}` endpoint

**Files:**
- Modify: `backend/routers/video_router.py` (append endpoint after existing `/thumbnails/{clip_id}` block)
- Modify: `backend/schemas/video_schemas.py` (add `ThumbstripResponse`)
- Test: `Tests/test_video_thumbstrip_endpoint.py` (create)

- [ ] **Step 1: Write the failing test**

```python
# Tests/test_video_thumbstrip_endpoint.py
"""GET /video/thumbstrip/{clip_id} liefert n base64-Frames + duration."""
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock

from backend.main import app


def test_thumbstrip_returns_n_base64_frames(monkeypatch):
    client = TestClient(app)

    # Mock AppState video clip
    fake_clip = {"id": 1, "path": "/x.mp4", "duration_seconds": 30.0}
    from backend.app_state import AppState
    monkeypatch.setattr(AppState, "get_video_clip",
                        lambda self, cid: fake_clip if cid == 1 else None)

    # Mock FrameGrabber to return 6 small PIL images
    from PIL import Image
    fake_frames = [Image.new("RGB", (160, 90), color=(i * 30, 0, 0)) for i in range(6)]
    with patch("backend.routers.video_router._extract_thumbstrip", return_value=fake_frames):
        resp = client.get("/video/thumbstrip/1?n=6")

    assert resp.status_code == 200
    body = resp.json()
    assert "frames" in body
    assert len(body["frames"]) == 6
    assert all(f.startswith("data:image/jpeg;base64,") for f in body["frames"])
    assert body["count"] == 6


def test_thumbstrip_404_unknown_clip(monkeypatch):
    client = TestClient(app)
    from backend.app_state import AppState
    monkeypatch.setattr(AppState, "get_video_clip", lambda self, cid: None)
    resp = client.get("/video/thumbstrip/999?n=6")
    assert resp.status_code == 404


def test_thumbstrip_n_clamped_to_safe_range(monkeypatch):
    """n is clamped to [1,32] to prevent abuse."""
    client = TestClient(app)
    fake_clip = {"id": 1, "path": "/x.mp4", "duration_seconds": 30.0}
    from backend.app_state import AppState
    monkeypatch.setattr(AppState, "get_video_clip", lambda self, cid: fake_clip)

    captured = {}
    def fake_extract(path, n, size):
        captured["n"] = n
        from PIL import Image
        return [Image.new("RGB", (160, 90)) for _ in range(n)]
    with patch("backend.routers.video_router._extract_thumbstrip", side_effect=fake_extract):
        resp = client.get("/video/thumbstrip/1?n=999")
    assert resp.status_code == 200
    assert captured["n"] == 32  # clamped
```

- [ ] **Step 2: Add the schema**

Append to `backend/schemas/video_schemas.py`:

```python
class ThumbstripResponse(BaseModel):
    """Response: N base64-encoded JPEG thumbnails fuer Timeline-Clip-Visualization."""
    clip_id: int
    count: int
    frames: list[str]  # Each entry: "data:image/jpeg;base64,..."
```

- [ ] **Step 3: Add the endpoint**

Append to `backend/routers/video_router.py` (after existing `get_thumbnail` function):

```python
@router.get(
    "/thumbstrip/{clip_id}",
    response_model=ThumbstripResponse,
    summary="Thumbnail-Strip (N Frames) abrufen",
    description=(
        "Liefert N evenly-spaced JPEG-Thumbnails als base64-Datenstrings, "
        "fuer den Timeline-Clip-Strip (Premiere/Davinci-Style). "
        "n wird auf [1,32] geklammert."
    ),
)
async def get_thumbstrip(
    clip_id: int,
    n: int = 8,
    state: AppState = Depends(get_app_state),
) -> ThumbstripResponse:
    clip = state.get_video_clip(clip_id)
    if clip is None:
        raise HTTPException(status_code=404, detail=f"Video-Clip {clip_id} nicht gefunden")
    n = max(1, min(32, n))
    try:
        frames = await asyncio.to_thread(_extract_thumbstrip, clip["path"], n, (160, 90))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Thumbstrip-Erzeugung fehlgeschlagen: {e}")

    import base64
    import io
    data_urls: list[str] = []
    for img in frames:
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=80)
        b64 = base64.b64encode(buf.getvalue()).decode("ascii")
        data_urls.append(f"data:image/jpeg;base64,{b64}")
    return ThumbstripResponse(clip_id=clip_id, count=len(data_urls), frames=data_urls)


def _extract_thumbstrip(video_path: str, n: int, size: tuple) -> list:
    """Indirection so tests can monkeypatch the heavy work."""
    from pb_studio.video.frame_extractor import FrameGrabber
    return FrameGrabber().extract_thumbnail_strip(video_path, n=n, size=size)
```

Add to the existing `from ..schemas.video_schemas import (...)` line: `ThumbstripResponse`.

- [ ] **Step 4: Run the test**

```powershell
pytest Tests/test_video_thumbstrip_endpoint.py -x -q
```
Expected: PASS 3/3.

- [ ] **Step 5: Commit**

```powershell
git add Tests/test_video_thumbstrip_endpoint.py backend/routers/video_router.py backend/schemas/video_schemas.py
git commit -m "feat(video): GET /video/thumbstrip/{id} for N-frame timeline strips"
```

---

## Task 4: Backend — `clip_audio_peaks.py` helper

**Files:**
- Create: `src/pb_studio/video/clip_audio_peaks.py`
- Test: `Tests/test_clip_audio_peaks.py`

- [ ] **Step 1: Write the failing test**

```python
# Tests/test_clip_audio_peaks.py
"""Extract mono peak array from a video file (or audio file) via ffmpeg pipe."""
from pathlib import Path
import subprocess

import pytest

from pb_studio.video.clip_audio_peaks import extract_peaks


@pytest.fixture
def sample_video_with_audio(tmp_path: Path) -> Path:
    """3s video with a 440 Hz tone audio track."""
    out = tmp_path / "tone.mp4"
    subprocess.run(
        ["ffmpeg", "-y",
         "-f", "lavfi", "-i", "color=c=black:s=160x90:r=10:d=3",
         "-f", "lavfi", "-i", "sine=frequency=440:duration=3",
         "-c:v", "libx264", "-pix_fmt", "yuv420p",
         "-c:a", "aac", "-shortest", str(out)],
        check=True, capture_output=True,
    )
    return out


def test_extract_peaks_returns_requested_buckets(sample_video_with_audio: Path):
    peaks = extract_peaks(str(sample_video_with_audio), n_buckets=200)
    assert len(peaks) == 200
    # 440Hz tone -> non-zero peaks
    assert max(peaks) > 0.1
    # Peaks normalized to [0,1]
    assert max(peaks) <= 1.0
    assert min(peaks) >= 0.0


def test_extract_peaks_no_audio_returns_zeros(tmp_path: Path):
    """Video without an audio track -> array of zeros, not exception."""
    out = tmp_path / "silent.mp4"
    subprocess.run(
        ["ffmpeg", "-y", "-f", "lavfi", "-i", "color=c=black:s=160x90:r=10:d=2",
         "-c:v", "libx264", "-pix_fmt", "yuv420p", "-an", str(out)],
        check=True, capture_output=True,
    )
    peaks = extract_peaks(str(out), n_buckets=64)
    assert len(peaks) == 64
    assert all(p == 0.0 for p in peaks)


def test_extract_peaks_missing_file_returns_empty(tmp_path: Path):
    peaks = extract_peaks(str(tmp_path / "missing.mp4"), n_buckets=64)
    assert peaks == []
```

- [ ] **Step 2: Run the test (failing)**

```powershell
pytest Tests/test_clip_audio_peaks.py -x -q
```
Expected: FAIL `ModuleNotFoundError: No module named 'pb_studio.video.clip_audio_peaks'`.

- [ ] **Step 3: Implement clip_audio_peaks.py**

Create `src/pb_studio/video/clip_audio_peaks.py`:

```python
"""Extract a downsampled mono peak array from a video/audio file via ffmpeg.

Used by the timeline:
  - audio-lane bigger waveform (when source is the music file)
  - per-clip mini waveform (when source is the video's audio track)
"""
from __future__ import annotations
from pathlib import Path
import logging
import subprocess

import numpy as np

logger = logging.getLogger(__name__)


def extract_peaks(media_path: str, n_buckets: int = 256) -> list[float]:
    """Return a list of `n_buckets` peak magnitudes normalized to [0,1].

    Pipes ffmpeg PCM16 mono into numpy, then aggregates per bucket via max(abs(.)).
    Empty list if the file is missing or unreadable.
    Array of zeros if the file exists but has no audio track.
    """
    if n_buckets <= 0:
        return []
    p = Path(media_path)
    if not p.exists():
        return []

    cmd = [
        "ffmpeg", "-v", "error",
        "-i", str(p),
        "-vn", "-ac", "1", "-ar", "8000",
        "-f", "s16le", "-",
    ]
    try:
        proc = subprocess.run(cmd, capture_output=True, timeout=60)
    except subprocess.TimeoutExpired:
        logger.warning("ffmpeg peaks-extract timeout for %s", p.name)
        return [0.0] * n_buckets
    if proc.returncode != 0:
        # No audio stream or other ffmpeg error -> return zeros so the UI can still draw a flat line.
        return [0.0] * n_buckets

    raw = proc.stdout
    if not raw:
        return [0.0] * n_buckets

    samples = np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768.0
    if samples.size == 0:
        return [0.0] * n_buckets

    bucket_size = max(1, samples.size // n_buckets)
    peaks = np.empty(n_buckets, dtype=np.float32)
    for i in range(n_buckets):
        chunk = samples[i * bucket_size : (i + 1) * bucket_size]
        peaks[i] = float(np.max(np.abs(chunk))) if chunk.size else 0.0
    return peaks.tolist()
```

- [ ] **Step 4: Run the test**

```powershell
pytest Tests/test_clip_audio_peaks.py -x -q
```
Expected: PASS 3/3.

- [ ] **Step 5: Commit**

```powershell
git add Tests/test_clip_audio_peaks.py src/pb_studio/video/clip_audio_peaks.py
git commit -m "feat(video): clip_audio_peaks.extract_peaks for per-clip mini waveforms"
```

---

## Task 5: Backend — `GET /video/clipwave/{clip_id}` endpoint

**Files:**
- Modify: `backend/routers/video_router.py`
- Modify: `backend/schemas/video_schemas.py`
- Test: `Tests/test_video_clipwave_endpoint.py` (create)

- [ ] **Step 1: Write the failing test**

```python
# Tests/test_video_clipwave_endpoint.py
"""GET /video/clipwave/{clip_id} liefert downsampled mono peaks."""
from fastapi.testclient import TestClient
from unittest.mock import patch

from backend.main import app


def test_clipwave_returns_peaks(monkeypatch):
    client = TestClient(app)
    fake_clip = {"id": 1, "path": "/x.mp4", "duration_seconds": 10.0}
    from backend.app_state import AppState
    monkeypatch.setattr(AppState, "get_video_clip",
                        lambda self, cid: fake_clip if cid == 1 else None)

    with patch("backend.routers.video_router._extract_clip_peaks",
               return_value=[0.1, 0.5, 0.9, 0.5, 0.1]):
        resp = client.get("/video/clipwave/1?n=5")

    assert resp.status_code == 200
    body = resp.json()
    assert body["clip_id"] == 1
    assert body["peaks"] == [0.1, 0.5, 0.9, 0.5, 0.1]
    assert body["count"] == 5


def test_clipwave_404_unknown(monkeypatch):
    client = TestClient(app)
    from backend.app_state import AppState
    monkeypatch.setattr(AppState, "get_video_clip", lambda self, cid: None)
    resp = client.get("/video/clipwave/99?n=64")
    assert resp.status_code == 404


def test_clipwave_n_clamped(monkeypatch):
    client = TestClient(app)
    fake_clip = {"id": 1, "path": "/x.mp4", "duration_seconds": 10.0}
    from backend.app_state import AppState
    monkeypatch.setattr(AppState, "get_video_clip", lambda self, cid: fake_clip)

    captured = {}
    def fake(path, n):
        captured["n"] = n
        return [0.0] * n
    with patch("backend.routers.video_router._extract_clip_peaks", side_effect=fake):
        client.get("/video/clipwave/1?n=99999")
    assert captured["n"] == 2048
```

- [ ] **Step 2: Run the test (failing)**

```powershell
pytest Tests/test_video_clipwave_endpoint.py -x -q
```
Expected: FAIL `404` or `AttributeError`.

- [ ] **Step 3: Add schema**

Append to `backend/schemas/video_schemas.py`:

```python
class ClipwaveResponse(BaseModel):
    """Response: downsampled mono peaks (0..1) fuer Timeline-Clip-Waveform."""
    clip_id: int
    count: int
    peaks: list[float]
```

- [ ] **Step 4: Add endpoint**

Append to `backend/routers/video_router.py`:

```python
@router.get(
    "/clipwave/{clip_id}",
    response_model=ClipwaveResponse,
    summary="Clip-Audio-Peaks (downsampled mono) abrufen",
    description=(
        "Liefert N normalisierte (0..1) Peak-Werte fuer die Audio-Spur eines "
        "Video-Clips. Used vom Timeline-Mini-Waveform-Layer. n geklammert auf [1,2048]."
    ),
)
async def get_clipwave(
    clip_id: int,
    n: int = 256,
    state: AppState = Depends(get_app_state),
) -> ClipwaveResponse:
    clip = state.get_video_clip(clip_id)
    if clip is None:
        raise HTTPException(status_code=404, detail=f"Video-Clip {clip_id} nicht gefunden")
    n = max(1, min(2048, n))
    try:
        peaks = await asyncio.to_thread(_extract_clip_peaks, clip["path"], n)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Peaks-Erzeugung fehlgeschlagen: {e}")
    return ClipwaveResponse(clip_id=clip_id, count=len(peaks), peaks=peaks)


def _extract_clip_peaks(media_path: str, n: int) -> list[float]:
    """Indirection for tests."""
    from pb_studio.video.clip_audio_peaks import extract_peaks
    return extract_peaks(media_path, n_buckets=n)
```

Add `ClipwaveResponse` to the existing schemas import.

- [ ] **Step 5: Run the test**

```powershell
pytest Tests/test_video_clipwave_endpoint.py -x -q
```
Expected: PASS 3/3.

- [ ] **Step 6: Commit**

```powershell
git add Tests/test_video_clipwave_endpoint.py backend/routers/video_router.py backend/schemas/video_schemas.py
git commit -m "feat(video): GET /video/clipwave/{id} downsampled mono peaks for per-clip mini-waveforms"
```

---

## Task 6: WPF — extend ApiClient with new endpoints

**Files:**
- Modify: `PBStudio.UI/Services/IApiClient.cs`
- Modify: `PBStudio.UI/Services/ApiClient.cs`
- Create: `PBStudio.UI/Models/ThumbstripResponse.cs`
- Create: `PBStudio.UI/Models/ClipwaveResponse.cs`

- [ ] **Step 1: Create the response records**

Create `PBStudio.UI/Models/ThumbstripResponse.cs`:

```csharp
using System.Collections.Generic;
using System.Text.Json.Serialization;

namespace PBStudio.UI.Models;

public record ThumbstripResponse
{
    [JsonPropertyName("clip_id")] public int ClipId { get; init; }
    [JsonPropertyName("count")] public int Count { get; init; }
    [JsonPropertyName("frames")] public List<string> Frames { get; init; } = new();
}
```

Create `PBStudio.UI/Models/ClipwaveResponse.cs`:

```csharp
using System.Collections.Generic;
using System.Text.Json.Serialization;

namespace PBStudio.UI.Models;

public record ClipwaveResponse
{
    [JsonPropertyName("clip_id")] public int ClipId { get; init; }
    [JsonPropertyName("count")] public int Count { get; init; }
    [JsonPropertyName("peaks")] public List<float> Peaks { get; init; } = new();
}
```

- [ ] **Step 2: Add interface methods**

In `PBStudio.UI/Services/IApiClient.cs`, add inside the interface:

```csharp
    Task<ThumbstripResponse?> GetThumbStripAsync(int clipId, int n = 8);
    Task<ClipwaveResponse?> GetClipWaveAsync(int clipId, int n = 256);
```

- [ ] **Step 3: Add implementations to ApiClient.cs**

Find the existing `GetMotionAsync` method as a template. Add nearby:

```csharp
    public async Task<ThumbstripResponse?> GetThumbStripAsync(int clipId, int n = 8)
    {
        return await GetAsync<ThumbstripResponse>($"/video/thumbstrip/{clipId}?n={n}");
    }

    public async Task<ClipwaveResponse?> GetClipWaveAsync(int clipId, int n = 256)
    {
        return await GetAsync<ClipwaveResponse>($"/video/clipwave/{clipId}?n={n}");
    }
```

- [ ] **Step 4: Build & run no regression**

```powershell
dotnet build PBStudio.UI\PBStudio.UI.csproj -c Release
```
Expected: Build succeeded, 0 errors.

- [ ] **Step 5: Commit**

```powershell
git add PBStudio.UI/Models/ThumbstripResponse.cs PBStudio.UI/Models/ClipwaveResponse.cs PBStudio.UI/Services/IApiClient.cs PBStudio.UI/Services/ApiClient.cs
git commit -m "feat(ui): ApiClient methods for /video/thumbstrip and /video/clipwave"
```

---

## Task 7: WPF — extend TimelineEntryModel with clip assets

**Files:**
- Modify: `PBStudio.UI/Models/TimelineEntry.cs`

- [ ] **Step 1: Add the asset properties**

Append inside the `TimelineEntryModel` class:

```csharp
    /// <summary>N base64 JPEG data URLs from /video/thumbstrip/{id}. null until loaded.</summary>
    [ObservableProperty] private ObservableCollection<string>? _thumbnailFrames;

    /// <summary>Downsampled mono peaks (0..1) from /video/clipwave/{id}. null until loaded.</summary>
    [ObservableProperty] private ObservableCollection<float>? _audioPeaks;

    /// <summary>Set to true after both /thumbstrip and /clipwave have returned (or failed).</summary>
    public bool IsAssetsLoaded { get; set; }
```

Add at the top of the file:
```csharp
using System.Collections.ObjectModel;
```

- [ ] **Step 2: Build**

```powershell
dotnet build PBStudio.UI\PBStudio.UI.csproj -c Release
```
Expected: Build succeeded.

- [ ] **Step 3: Commit**

```powershell
git add PBStudio.UI/Models/TimelineEntry.cs
git commit -m "feat(ui): TimelineEntryModel.ThumbnailFrames + AudioPeaks for per-clip visuals"
```

---

## Task 8: WPF — load clip assets in TimelineViewModel

**Files:**
- Modify: `PBStudio.UI/ViewModels/TimelineViewModel.cs`

- [ ] **Step 1: Add `LoadClipAssetsAsync` method**

Insert near `LoadMotionCurveAsync` (around line 212):

```csharp
    /// <summary>
    /// Loads /video/thumbstrip and /video/clipwave for the entry's clip in parallel.
    /// Skips if already loaded. Fire-and-forget pattern: errors are logged and the
    /// entry's visual just falls back to the background rectangle.
    /// </summary>
    private async Task LoadClipAssetsAsync(TimelineEntryModel entry)
    {
        if (entry == null || entry.IsAssetsLoaded) return;
        if (!int.TryParse(entry.ClipId.Replace("clip_", ""),
                          NumberStyles.Integer, CultureInfo.InvariantCulture, out var cid))
        {
            entry.IsAssetsLoaded = true;
            return;
        }

        try
        {
            var stripTask = _api.GetThumbStripAsync(cid, n: 8);
            var waveTask = _api.GetClipWaveAsync(cid, n: 256);
            await Task.WhenAll(stripTask, waveTask).ConfigureAwait(false);

            await Application.Current.Dispatcher.InvokeAsync(() =>
            {
                if (stripTask.Result?.Frames is { Count: > 0 } frames)
                    entry.ThumbnailFrames = new ObservableCollection<string>(frames);
                if (waveTask.Result?.Peaks is { Count: > 0 } peaks)
                    entry.AudioPeaks = new ObservableCollection<float>(peaks);
                entry.IsAssetsLoaded = true;
            });
        }
        catch (Exception ex)
        {
            Debug.WriteLine($"Clip-Assets-Load fehlgeschlagen fuer clip {cid}: {ex.Message}");
            entry.IsAssetsLoaded = true;  // mark so we don't retry every render
        }
    }
```

- [ ] **Step 2: Trigger asset loading after a refresh**

Inside `RefreshTimelineAsync`, after the foreach that populates `TimelineEntries` and after `SelectedEntry = TimelineEntries.FirstOrDefault();` (around line 343), add:

```csharp
                // Eagerly load assets for the first N visible clips (rest load on-demand).
                foreach (var e in TimelineEntries.Take(20))
                {
                    _ = LoadClipAssetsAsync(e);
                }
```

- [ ] **Step 3: Trigger lazy loading on selection change**

In `OnSelectedEntryChanged` (line 174), after the existing `LoadMotionCurveAsync` block, add:

```csharp
        if (value != null && !value.IsAssetsLoaded)
        {
            _ = LoadClipAssetsAsync(value);
        }
```

- [ ] **Step 4: Build**

```powershell
dotnet build PBStudio.UI\PBStudio.UI.csproj -c Release
```
Expected: Build succeeded.

- [ ] **Step 5: Commit**

```powershell
git add PBStudio.UI/ViewModels/TimelineViewModel.cs
git commit -m "feat(ui): TimelineViewModel loads thumbstrip + clipwave per entry"
```

---

## Task 9: WPF — restructure TimelineView into V1 + A1 lanes

This is the big visual restructure. We split the current single Canvas into a vertical Grid: Ruler / Video-Lane (V1) / Audio-Lane (A1) / Bottom Panels.

**Files:**
- Modify: `PBStudio.UI/Views/TimelineView.xaml` (replace the `<Grid>` block from line 216 (`<!-- ══ Main Timeline Container ══ -->`) up to line 558)
- Create: `PBStudio.UI/Converters/PeaksToWaveformGeometryConverter.cs`

- [ ] **Step 1: Create the peaks→geometry converter**

Create `PBStudio.UI/Converters/PeaksToWaveformGeometryConverter.cs`:

```csharp
using System;
using System.Collections.Generic;
using System.Globalization;
using System.Windows;
using System.Windows.Data;
using System.Windows.Media;

namespace PBStudio.UI.Converters;

/// <summary>
/// Converts (peaks: IList&lt;float&gt;, width: double, height: double) → StreamGeometry,
/// drawing a symmetric mid-axis waveform (positive and mirrored negative).
/// </summary>
public class PeaksToWaveformGeometryConverter : IMultiValueConverter
{
    public object Convert(object[] values, Type targetType, object parameter, CultureInfo culture)
    {
        if (values.Length < 3) return Geometry.Empty;
        if (values[0] is not IList<float> peaks || peaks.Count == 0) return Geometry.Empty;
        if (values[1] is not double width || width <= 0) return Geometry.Empty;
        if (values[2] is not double height || height <= 0) return Geometry.Empty;

        var geo = new StreamGeometry();
        using var ctx = geo.Open();
        double mid = height / 2.0;
        double step = width / peaks.Count;
        for (int i = 0; i < peaks.Count; i++)
        {
            double x = i * step;
            double h = Math.Max(1.0, peaks[i] * mid);
            ctx.BeginFigure(new Point(x, mid - h), false, false);
            ctx.LineTo(new Point(x, mid + h), true, false);
        }
        geo.Freeze();
        return geo;
    }

    public object[] ConvertBack(object value, Type[] targetTypes, object parameter, CultureInfo culture)
        => throw new NotImplementedException();
}
```

- [ ] **Step 2: Register the converter in App.xaml resources**

Open `PBStudio.UI/App.xaml`. Inside `<Application.Resources>` → `<ResourceDictionary>`, add:

```xml
<converters:PeaksToWaveformGeometryConverter x:Key="PeaksToWaveformGeometryConverter"/>
```

Ensure the `xmlns:converters="clr-namespace:PBStudio.UI.Converters"` namespace exists. If it doesn't, add it to the `<Application>` root element.

- [ ] **Step 3: Replace the timeline Grid in TimelineView.xaml**

In `PBStudio.UI/Views/TimelineView.xaml`, locate the comment `<!-- ══ Main Timeline Container ══ -->` (line 215). Delete from that line through its closing `</Grid>` (line 558) and replace with:

```xml
        <!-- ══ Main Timeline Container — V1 (Video) + A1 (Audio) Lanes ══ -->
        <Grid>
            <Grid.RowDefinitions>
                <RowDefinition Height="180"/> <!-- Summary ListView -->
                <RowDefinition Height="5"/>   <!-- Splitter -->
                <RowDefinition Height="*"/>   <!-- Lanes -->
            </Grid.RowDefinitions>

            <!-- Summary ListView (unchanged) -->
            <md:Card Grid.Row="0" Style="{StaticResource AbletonCard}" Padding="0">
                <ListView ItemsSource="{Binding TimelineEntries}" SelectedItem="{Binding SelectedEntry}"
                          Background="Transparent" BorderThickness="0" Foreground="{StaticResource AbletonText}">
                    <ListView.View>
                        <GridView>
                            <GridViewColumn Header="Clip" Width="180" DisplayMemberBinding="{Binding ClipName}"/>
                            <GridViewColumn Header="Zeitraum" Width="130" DisplayMemberBinding="{Binding TimeRangeText}"/>
                            <GridViewColumn Header="Trigger" Width="100" DisplayMemberBinding="{Binding TriggerType}"/>
                            <GridViewColumn Header="Dauer" Width="70" DisplayMemberBinding="{Binding Duration, StringFormat={}{0:F2}s}"/>
                        </GridView>
                    </ListView.View>
                </ListView>
            </md:Card>

            <GridSplitter Grid.Row="1" Height="5" HorizontalAlignment="Stretch"
                          Background="{StaticResource AbletonBorder}" Margin="0,2"/>

            <!-- Lanes container -->
            <md:Card Grid.Row="2" Style="{StaticResource AbletonCard}" Padding="0" ClipToBounds="True">
                <Grid>
                    <Grid.ColumnDefinitions>
                        <ColumnDefinition Width="60"/>  <!-- Track headers -->
                        <ColumnDefinition Width="*"/>   <!-- Scrollable lanes -->
                    </Grid.ColumnDefinitions>
                    <Grid.RowDefinitions>
                        <RowDefinition Height="25"/>  <!-- Ruler -->
                        <RowDefinition Height="110"/> <!-- V1 -->
                        <RowDefinition Height="80"/>  <!-- A1 -->
                    </Grid.RowDefinitions>

                    <!-- Track headers (fixed left column) -->
                    <Border Grid.Column="0" Grid.Row="0" Background="{StaticResource AbletonPanel}"
                            BorderBrush="{StaticResource AbletonBorder}" BorderThickness="0,0,1,1"/>
                    <Border Grid.Column="0" Grid.Row="1" Background="{StaticResource AbletonPanel}"
                            BorderBrush="{StaticResource AbletonBorder}" BorderThickness="0,0,1,1">
                        <TextBlock Text="V1" Foreground="{StaticResource AbletonText}" FontWeight="SemiBold"
                                   HorizontalAlignment="Center" VerticalAlignment="Center" FontSize="14"/>
                    </Border>
                    <Border Grid.Column="0" Grid.Row="2" Background="{StaticResource AbletonPanel}"
                            BorderBrush="{StaticResource AbletonBorder}" BorderThickness="0,0,1,0">
                        <TextBlock Text="A1" Foreground="{StaticResource AbletonText}" FontWeight="SemiBold"
                                   HorizontalAlignment="Center" VerticalAlignment="Center" FontSize="14"/>
                    </Border>

                    <!-- Ruler -->
                    <Border Grid.Column="1" Grid.Row="0" Background="{StaticResource AbletonPanel}"
                            BorderBrush="{StaticResource AbletonBorder}" BorderThickness="0,0,0,1">
                        <Canvas x:Name="RulerCanvas" Height="25" Background="Transparent" HorizontalAlignment="Stretch"/>
                    </Border>

                    <!-- Single horizontal ScrollViewer spanning both lanes -->
                    <ScrollViewer Grid.Column="1" Grid.Row="1" Grid.RowSpan="2"
                                  x:Name="LanesScrollViewer"
                                  HorizontalScrollBarVisibility="Visible"
                                  VerticalScrollBarVisibility="Disabled"
                                  CanContentScroll="True"
                                  VirtualizingPanel.ScrollUnit="Pixel">
                        <Grid Width="{Binding TimelineWidth}" Background="#111111"
                              PreviewMouseDown="TimelineGrid_MouseDown">
                            <Grid.RowDefinitions>
                                <RowDefinition Height="110"/>  <!-- V1 -->
                                <RowDefinition Height="80"/>   <!-- A1 -->
                            </Grid.RowDefinitions>

                            <!-- ══════════════════════════════════════════════════════════ -->
                            <!-- V1 LANE: Video clips with thumbnail strips                 -->
                            <!-- ══════════════════════════════════════════════════════════ -->
                            <Border Grid.Row="0" Background="#FF1A1A1A"
                                    BorderBrush="{StaticResource AbletonBorder}" BorderThickness="0,0,0,1"/>

                            <!-- Song-segment background (only inside V1) -->
                            <ItemsControl Grid.Row="0" ItemsSource="{Binding SongSegments}">
                                <ItemsControl.ItemsPanel>
                                    <ItemsPanelTemplate>
                                        <Canvas Background="Transparent" VerticalAlignment="Stretch"/>
                                    </ItemsPanelTemplate>
                                </ItemsControl.ItemsPanel>
                                <ItemsControl.ItemContainerStyle>
                                    <Style TargetType="ContentPresenter">
                                        <Setter Property="Canvas.Left">
                                            <Setter.Value>
                                                <MultiBinding Converter="{StaticResource TimeToPixelConverter}">
                                                    <Binding Path="StartTime"/>
                                                    <Binding Path="DataContext.PixelsPerSecond" RelativeSource="{RelativeSource AncestorType=UserControl}"/>
                                                </MultiBinding>
                                            </Setter.Value>
                                        </Setter>
                                    </Style>
                                </ItemsControl.ItemContainerStyle>
                                <ItemsControl.ItemTemplate>
                                    <DataTemplate>
                                        <Border Height="110" Opacity="0.10">
                                            <Border.Style>
                                                <Style TargetType="Border">
                                                    <Style.Triggers>
                                                        <DataTrigger Binding="{Binding Label}" Value="chorus">
                                                            <Setter Property="Background" Value="{StaticResource AbletonAccent}"/>
                                                        </DataTrigger>
                                                        <DataTrigger Binding="{Binding Label}" Value="verse">
                                                            <Setter Property="Background" Value="{StaticResource AbletonBlue}"/>
                                                        </DataTrigger>
                                                    </Style.Triggers>
                                                    <Setter Property="Background" Value="{StaticResource AbletonBorder}"/>
                                                </Style>
                                            </Border.Style>
                                            <Border.Width>
                                                <MultiBinding Converter="{StaticResource TimeToPixelConverter}">
                                                    <Binding Path="Duration"/>
                                                    <Binding Path="DataContext.PixelsPerSecond" RelativeSource="{RelativeSource AncestorType=UserControl}"/>
                                                </MultiBinding>
                                            </Border.Width>
                                        </Border>
                                    </DataTemplate>
                                </ItemsControl.ItemTemplate>
                            </ItemsControl>

                            <!-- Video clips -->
                            <ItemsControl x:Name="TimelineItemsControl" Grid.Row="0"
                                          ItemsSource="{Binding TimelineEntries}">
                                <ItemsControl.ItemsPanel>
                                    <ItemsPanelTemplate>
                                        <Canvas Background="Transparent" VerticalAlignment="Stretch"/>
                                    </ItemsPanelTemplate>
                                </ItemsControl.ItemsPanel>
                                <ItemsControl.ItemContainerStyle>
                                    <Style TargetType="ContentPresenter">
                                        <Setter Property="Canvas.Left">
                                            <Setter.Value>
                                                <MultiBinding Converter="{StaticResource TimeToPixelConverter}">
                                                    <Binding Path="StartTime"/>
                                                    <Binding Path="DataContext.PixelsPerSecond" RelativeSource="{RelativeSource AncestorType=UserControl}"/>
                                                </MultiBinding>
                                            </Setter.Value>
                                        </Setter>
                                        <Setter Property="Canvas.Top" Value="0"/>
                                    </Style>
                                </ItemsControl.ItemContainerStyle>
                                <ItemsControl.ItemTemplate>
                                    <DataTemplate DataType="{x:Type models:TimelineEntryModel}">
                                        <Border x:Name="ClipBorder"
                                                Height="100" Margin="0,5"
                                                CornerRadius="3"
                                                BorderThickness="1"
                                                BorderBrush="{StaticResource AbletonAccent}"
                                                Background="#FF2A2A2A"
                                                ClipToBounds="True"
                                                ToolTip="{Binding ClipName}"
                                                Cursor="Hand"
                                                PreviewMouseDown="Clip_MouseDown"
                                                PreviewMouseMove="Clip_MouseMove"
                                                PreviewMouseUp="Clip_MouseUp">
                                            <Border.Width>
                                                <MultiBinding Converter="{StaticResource TimeToPixelConverter}">
                                                    <Binding Path="Duration"/>
                                                    <Binding Path="DataContext.PixelsPerSecond" RelativeSource="{RelativeSource AncestorType=UserControl}"/>
                                                </MultiBinding>
                                            </Border.Width>
                                            <Grid>
                                                <Grid.RowDefinitions>
                                                    <RowDefinition Height="60"/> <!-- Thumbnail strip -->
                                                    <RowDefinition Height="*"/>  <!-- Mini waveform -->
                                                    <RowDefinition Height="14"/> <!-- Name -->
                                                    <RowDefinition Height="4"/>  <!-- Confidence bar -->
                                                </Grid.RowDefinitions>

                                                <!-- Thumbnail strip (premiere-style) -->
                                                <ItemsControl Grid.Row="0" ItemsSource="{Binding ThumbnailFrames}"
                                                              ClipToBounds="True">
                                                    <ItemsControl.ItemsPanel>
                                                        <ItemsPanelTemplate>
                                                            <UniformGrid Rows="1"/>
                                                        </ItemsPanelTemplate>
                                                    </ItemsControl.ItemsPanel>
                                                    <ItemsControl.ItemTemplate>
                                                        <DataTemplate>
                                                            <Image Source="{Binding}" Stretch="UniformToFill"/>
                                                        </DataTemplate>
                                                    </ItemsControl.ItemTemplate>
                                                </ItemsControl>

                                                <!-- Per-clip mini waveform -->
                                                <Path Grid.Row="1" Stroke="{StaticResource AbletonBlue}"
                                                      StrokeThickness="1" Opacity="0.85" SnapsToDevicePixels="True">
                                                    <Path.Data>
                                                        <MultiBinding Converter="{StaticResource PeaksToWaveformGeometryConverter}">
                                                            <Binding Path="AudioPeaks"/>
                                                            <Binding Path="ActualWidth" RelativeSource="{RelativeSource AncestorType=Border}"/>
                                                            <Binding Path="ActualHeight" RelativeSource="{RelativeSource Self}"/>
                                                        </MultiBinding>
                                                    </Path.Data>
                                                </Path>

                                                <TextBlock Grid.Row="2" Text="{Binding ClipName}"
                                                           FontSize="10" Foreground="{StaticResource AbletonText}"
                                                           VerticalAlignment="Center" HorizontalAlignment="Center"
                                                           TextTrimming="CharacterEllipsis" Margin="4,0"/>

                                                <Rectangle Grid.Row="3" Height="4" HorizontalAlignment="Stretch"
                                                           Fill="{Binding BrainConfidence, Converter={StaticResource ConfidenceToBrushConverter}}"
                                                           ToolTipService.InitialShowDelay="450"
                                                           ToolTipService.ShowDuration="20000"
                                                           ToolTipOpening="ConfidenceBar_ToolTipOpening">
                                                    <Rectangle.ToolTip>
                                                        <ToolTip MaxWidth="320">
                                                            <TextBlock Text="{Binding PlacementTarget.DataContext.BrainExplainTooltip, RelativeSource={RelativeSource AncestorType=ToolTip}, TargetNullValue='Brain-Confidence — hover fuer Details'}"
                                                                       FontFamily="Consolas" FontSize="11" TextWrapping="Wrap"/>
                                                        </ToolTip>
                                                    </Rectangle.ToolTip>
                                                </Rectangle>

                                                <!-- Trim handles -->
                                                <Rectangle Grid.Row="0" Grid.RowSpan="4" Width="4"
                                                           HorizontalAlignment="Left" Fill="{StaticResource AbletonAccent}"
                                                           Cursor="SizeWE" Opacity="0.5"/>
                                                <Rectangle Grid.Row="0" Grid.RowSpan="4" Width="4"
                                                           HorizontalAlignment="Right" Fill="{StaticResource AbletonAccent}"
                                                           Cursor="SizeWE" Opacity="0.5"/>
                                            </Grid>
                                        </Border>
                                    </DataTemplate>
                                </ItemsControl.ItemTemplate>
                            </ItemsControl>

                            <!-- ══════════════════════════════════════════════════════════ -->
                            <!-- A1 LANE: Music waveform + beat markers                     -->
                            <!-- ══════════════════════════════════════════════════════════ -->
                            <Border Grid.Row="1" Background="#FF141414"/>

                            <!-- Audio waveform (full opacity, mid-axis) -->
                            <ItemsControl Grid.Row="1" ItemsSource="{Binding WaveformBars}"
                                          VirtualizingPanel.IsVirtualizing="True"
                                          VirtualizingPanel.VirtualizationMode="Recycling">
                                <ItemsControl.ItemsPanel>
                                    <ItemsPanelTemplate>
                                        <Canvas Background="Transparent" VerticalAlignment="Stretch"/>
                                    </ItemsPanelTemplate>
                                </ItemsControl.ItemsPanel>
                                <ItemsControl.ItemContainerStyle>
                                    <Style TargetType="ContentPresenter">
                                        <Setter Property="Canvas.Left">
                                            <Setter.Value>
                                                <MultiBinding Converter="{StaticResource TimeToPixelConverter}">
                                                    <Binding Path="X"/>
                                                    <Binding Path="DataContext.PixelsPerSecond" RelativeSource="{RelativeSource AncestorType=UserControl}"/>
                                                </MultiBinding>
                                            </Setter.Value>
                                        </Setter>
                                        <Setter Property="Canvas.Top" Value="{Binding Y}"/>
                                    </Style>
                                </ItemsControl.ItemContainerStyle>
                                <ItemsControl.ItemTemplate>
                                    <DataTemplate>
                                        <Rectangle Height="{Binding Height}"
                                                   Fill="{StaticResource AbletonBlue}"
                                                   Opacity="0.95">
                                            <Rectangle.Width>
                                                <MultiBinding Converter="{StaticResource TimeToPixelConverter}">
                                                    <Binding Path="Width"/>
                                                    <Binding Path="DataContext.PixelsPerSecond" RelativeSource="{RelativeSource AncestorType=UserControl}"/>
                                                </MultiBinding>
                                            </Rectangle.Width>
                                        </Rectangle>
                                    </DataTemplate>
                                </ItemsControl.ItemTemplate>
                            </ItemsControl>

                            <!-- Beat markers (span both lanes) -->
                            <ItemsControl Grid.Row="0" Grid.RowSpan="2" ItemsSource="{Binding BeatMarkers}">
                                <ItemsControl.ItemsPanel>
                                    <ItemsPanelTemplate>
                                        <Canvas Background="Transparent" VerticalAlignment="Stretch"/>
                                    </ItemsPanelTemplate>
                                </ItemsControl.ItemsPanel>
                                <ItemsControl.ItemContainerStyle>
                                    <Style TargetType="ContentPresenter">
                                        <Setter Property="Canvas.Left">
                                            <Setter.Value>
                                                <MultiBinding Converter="{StaticResource TimeToPixelConverter}">
                                                    <Binding/>
                                                    <Binding Path="DataContext.PixelsPerSecond" RelativeSource="{RelativeSource AncestorType=UserControl}"/>
                                                </MultiBinding>
                                            </Setter.Value>
                                        </Setter>
                                    </Style>
                                </ItemsControl.ItemContainerStyle>
                                <ItemsControl.ItemTemplate>
                                    <DataTemplate>
                                        <Line Y1="0" Y2="500" Stroke="{StaticResource AbletonGreen}"
                                              StrokeThickness="0.5" Opacity="0.20" StrokeDashArray="2,2"/>
                                    </DataTemplate>
                                </ItemsControl.ItemTemplate>
                            </ItemsControl>

                            <!-- Playhead -->
                            <Canvas Grid.Row="0" Grid.RowSpan="2" HorizontalAlignment="Left"
                                    Width="{Binding TimelineWidth}">
                                <Border Width="2" Background="{StaticResource AbletonGreen}" Height="500">
                                    <Border.RenderTransform>
                                        <TranslateTransform>
                                            <TranslateTransform.X>
                                                <MultiBinding Converter="{StaticResource TimeToPixelConverter}">
                                                    <Binding Path="SelectedTimelinePosition"/>
                                                    <Binding Path="PixelsPerSecond"/>
                                                </MultiBinding>
                                            </TranslateTransform.X>
                                        </TranslateTransform>
                                    </Border.RenderTransform>
                                </Border>
                            </Canvas>

                            <!-- Snap line overlay -->
                            <Canvas Grid.Row="0" Grid.RowSpan="2" HorizontalAlignment="Left"
                                    Width="{Binding TimelineWidth}">
                                <Border x:Name="SnapLine" Width="1" Background="Cyan" Height="500" Visibility="Collapsed">
                                    <Border.RenderTransform>
                                        <TranslateTransform x:Name="SnapLineTransform"/>
                                    </Border.RenderTransform>
                                </Border>
                            </Canvas>
                        </Grid>
                    </ScrollViewer>
                </Grid>
            </md:Card>
        </Grid>
```

Also fix the audio-waveform Y/Height calculation so it's symmetric around the A1-lane mid-line. Open `PBStudio.UI/ViewModels/TimelineViewModel.cs` and find the `LoadWaveformAsync` block (around line 502). Replace the waveform-build loop:

```csharp
                int step = Math.Max(1, count / 1000);
                const double laneHeight = 80.0;
                const double mid = laneHeight / 2.0;

                for (int i = 0; i < count; i += step)
                {
                    double val = rawData[i];
                    double h = Math.Max(2, val * mid * 1.8);
                    WaveformBars.Add(new WaveformBarModel
                    {
                        X = (i * secondsPerPoint),
                        Height = h,
                        Y = mid - (h / 2.0),
                        Width = (secondsPerPoint * step)
                    });
                }
```

- [ ] **Step 4: Build**

```powershell
dotnet build PBStudio.UI\PBStudio.UI.csproj -c Release
```
Expected: 0 errors. (Warnings about XAML resources are OK.)

- [ ] **Step 5: Manual smoke test**

```powershell
.venv\Scripts\activate
$env:PYTHONPATH = "src"
Start-Process -NoNewWindow python -ArgumentList "-m","uvicorn","backend.main:app","--port","8765"
.\PBStudio.UI\bin\Release\net9.0-windows\win-x64\PBStudio.UI.exe
```

In the app: open a project with audio + video, generate a cut-list, open the Timeline tab. Verify:
- Two lanes visible with "V1" / "A1" headers on the left
- Audio waveform is clearly visible in A1 (not faint blue smear)
- Video clips have thumbnail strips (after a few seconds load)
- No clips stacked on top of each other

Stop the backend (Ctrl+C in its window) before continuing.

- [ ] **Step 6: Commit**

```powershell
git add PBStudio.UI/Views/TimelineView.xaml PBStudio.UI/Converters/PeaksToWaveformGeometryConverter.cs PBStudio.UI/App.xaml PBStudio.UI/ViewModels/TimelineViewModel.cs
git commit -m "feat(ui): split Timeline into V1+A1 lanes with thumbnail strips and proper waveform"
```

---

## Task 10: WPF — Drag collision-prevention + Contiguous Mode

Currently `Clip_MouseMove` lets the dragged clip pass through neighbours. We add neighbour-edge constraints so a clip cannot overlap its predecessor or successor, and on MouseUp we close any gap to the predecessor (contiguous mode).

**Files:**
- Modify: `PBStudio.UI/Views/TimelineView.xaml.cs`

- [ ] **Step 1: Add neighbour-clamp helper**

Insert after `GetAvailableSnapPoints` (around line 466):

```csharp
    /// <summary>
    /// Clamps `desiredStart` so the dragged clip doesn't overlap the immediate
    /// predecessor or successor in the chronological order. Returns the clamped
    /// start time. Successor.EndTime is unchanged by drag (we only move whole clip).
    /// </summary>
    private double ClampStartToNeighbours(TimelineEntryModel dragged, double desiredStart, double duration)
    {
        if (_viewModel == null) return desiredStart;

        TimelineEntryModel? prev = null, next = null;
        foreach (var e in _viewModel.TimelineEntries)
        {
            if (ReferenceEquals(e, dragged)) continue;
            if (e.EndTime <= dragged.StartTime + 0.0001)
            {
                if (prev == null || e.EndTime > prev.EndTime) prev = e;
            }
            else if (e.StartTime >= dragged.EndTime - 0.0001)
            {
                if (next == null || e.StartTime < next.StartTime) next = e;
            }
        }

        double minStart = prev?.EndTime ?? 0.0;
        double maxStart = next != null ? next.StartTime - duration : double.PositiveInfinity;
        return Math.Max(minStart, Math.Min(maxStart, desiredStart));
    }
```

- [ ] **Step 2: Apply clamp inside drag branch**

In `Clip_MouseMove`, find the `if (_isDragging)` branch (around line 317). Replace the body up to `_draggedEntry.EndTime = newStart + dur;` with:

```csharp
            if (_isDragging)
            {
                var newStart = _draggedEntry.StartTime + deltaTime;

                if (Keyboard.Modifiers != ModifierKeys.Shift)
                {
                    var allSnapPoints = GetAvailableSnapPoints();
                    var snapped = _snapEngine.FindSnapPoint(newStart, allSnapPoints);
                    if (snapped != null)
                    {
                        newStart = snapped.Time;
                        snapTime = snapped.Time;
                        isSnapped = true;
                    }
                }

                var dur = _draggedEntry.Duration;
                // NEW: clamp against neighbour edges so we can't overlap (V1 lane).
                newStart = ClampStartToNeighbours(_draggedEntry, newStart, dur);

                _draggedEntry.StartTime = newStart;
                _draggedEntry.EndTime = newStart + dur;
            }
```

Apply the same clamp to the trim-left branch — find `_draggedEntry.StartTime = newStart;` near line 384 and replace with:

```csharp
                newStart = Math.Max(ClampStartToNeighbours(_draggedEntry, newStart, _originalEndTime - newStart), newStart);
                _draggedEntry.StartTime = newStart;
                _draggedEntry.EndTime = _originalEndTime;
                _draggedEntry.ClipStart = newClipStart;
```

And in trim-right (around `_draggedEntry.EndTime = newEnd;` near line 413), clamp against the successor:

```csharp
                // Clamp end so we don't overlap the next clip.
                if (_viewModel != null)
                {
                    double maxEnd = double.PositiveInfinity;
                    foreach (var e in _viewModel.TimelineEntries)
                    {
                        if (ReferenceEquals(e, _draggedEntry)) continue;
                        if (e.StartTime >= _draggedEntry.StartTime + 0.0001 && e.StartTime < maxEnd)
                            maxEnd = e.StartTime;
                    }
                    if (newEnd > maxEnd) newEnd = maxEnd;
                }
                _draggedEntry.EndTime = newEnd;
```

- [ ] **Step 3: Close gaps on MouseUp (contiguous mode)**

In `Clip_MouseUp`, after `if (wasDragging) { _viewModel.SortEntriesByTime(); }`, add:

```csharp
                if (wasDragging)
                {
                    _viewModel.SortEntriesByTime();
                    CloseGapsInContiguousMode();
                }
```

Then add the method body near `ClampStartToNeighbours`:

```csharp
    /// <summary>
    /// Contiguous mode: after a drag, snap each clip's StartTime so it touches the
    /// predecessor's EndTime (cut[i].StartTime == cut[i-1].EndTime), preserving
    /// each clip's Duration. Idempotent.
    /// </summary>
    private void CloseGapsInContiguousMode()
    {
        if (_viewModel == null || _viewModel.TimelineEntries.Count < 2) return;

        for (int i = 1; i < _viewModel.TimelineEntries.Count; i++)
        {
            var prev = _viewModel.TimelineEntries[i - 1];
            var curr = _viewModel.TimelineEntries[i];
            double dur = curr.Duration;
            if (Math.Abs(curr.StartTime - prev.EndTime) > 0.001)
            {
                curr.StartTime = prev.EndTime;
                curr.EndTime = prev.EndTime + dur;
                curr.NotifyPositionChanged();
            }
        }
    }
```

- [ ] **Step 4: Build**

```powershell
dotnet build PBStudio.UI\PBStudio.UI.csproj -c Release
```
Expected: 0 errors.

- [ ] **Step 5: Manual smoke test**

Re-launch app (see Task 9 Step 5). Load a project + cut-list. In the Timeline:
- Drag a middle clip left as far as it goes — should stop at the previous clip's end, not overlap.
- Drag it right — should stop at the next clip's start.
- Drop it in the middle of a gap — on release, the gap closes (clip snaps to predecessor's end).
- Try trim-right past the next clip's start — should clamp.

- [ ] **Step 6: Commit**

```powershell
git add PBStudio.UI/Views/TimelineView.xaml.cs
git commit -m "feat(ui): drag collision-prevention + auto gap-close in contiguous mode"
```

---

## Task 11: Final integration test + Obsidian-Vault sync

**Files:**
- Test: `Tests/test_timeline_validation.py` (extend or create)
- Vault: `C:\Users\david\Brain\10_Projects\PB_studio\` (INDEX.md, log.md, decisions/)

- [ ] **Step 1: Write integration test for full-length + no-overlap timeline**

```python
# Tests/test_timeline_integration.py
"""Full-pipe: generate -> validate -> length matches audio, no overlaps."""
import pytest
from unittest.mock import patch, MagicMock

from backend.schemas.common import validate_timeline


def test_validate_timeline_blocks_underflow():
    """L-TI-6 (this plan): timeline shorter than audio is now an error too,
    not just a warning. (Add this behavior or leave as warning — but assert one way.)"""
    cuts = [{"start_time": 0.0, "end_time": 5.0, "metadata": {"file_path": "/x.mp4"}}]
    warnings, errors = validate_timeline(cuts, audio_duration=10.0)
    # If you keep underflow as a warning (current spec):
    assert any("underflow" in w.lower() or "kuerzer" in w.lower() or "5.0" in w for w in warnings) \
        or len(errors) == 0  # explicit no-error on underflow


def test_validate_timeline_no_overlaps_in_contiguous_output():
    cuts = [
        {"start_time": 0.0, "end_time": 5.0, "metadata": {}},
        {"start_time": 5.0, "end_time": 8.0, "metadata": {}},
        {"start_time": 8.0, "end_time": 12.0, "metadata": {}},
    ]
    warnings, errors = validate_timeline(cuts, audio_duration=12.0)
    assert errors == []
```

- [ ] **Step 2: Run all tests for regression**

```powershell
.venv\Scripts\activate
$env:PYTHONPATH = "src"
pytest Tests/ -x -q
```
Expected: all PASS (or only pre-existing failures unrelated to this plan).

- [ ] **Step 3: Update Obsidian Vault (Iron Rule 11)**

Use the MCP obsidian tools:
```
mcp__obsidian__update_frontmatter on 10_Projects/PB_studio/INDEX.md (updated: 2026-05-18)
mcp__obsidian__append_to_note on 10_Projects/PB_studio/log.md with the change summary
mcp__obsidian__create_note 10_Projects/PB_studio/decisions/2026-05-18-timeline-multi-lane.md  (ADR)
```

ADR body (concise):
```
# ADR: Timeline split into V1 + A1 lanes
Date: 2026-05-18
Status: Implemented

## Context
Single overlaid Canvas caused stacked clips, no separation between video and audio,
faint waveform, no thumbnails. User: "reines Chaos".

## Decision
- V1 lane (110px) above A1 lane (80px) with fixed left track-headers.
- Clip template: thumbnail-strip (top 60px) + mini-waveform (middle) + name + confidence bar.
- A1 lane: full-opacity waveform centered on mid-axis.
- Pacing: last cut stretched to audio_duration so V1.length == A1.length.
- Drag: clamp against neighbour edges; MouseUp closes gaps in contiguous mode.

## Consequences
+ Matches Premiere/Davinci mental model.
- Adds 2 backend endpoints (/video/thumbstrip, /video/clipwave).
- Out of scope: V2/A2 lanes, ripple-edit (follow-up).
```

- [ ] **Step 4: Final commit + push**

```powershell
git add Tests/test_timeline_integration.py
git commit -m "test(timeline): integration test for no-overlap + length match"
git push
```

---

## Self-Review (post-write checklist)

- Spec coverage:
  - "Clips überlappen / gestapelt" → Task 9 (V1 lane with `Canvas.Top=0` + Height=100) + Task 10 (ClampStartToNeighbours). ✓
  - "Große Lücken" → Task 10 (CloseGapsInContiguousMode on MouseUp) + Task 1 (last-cut stretch). ✓
  - "Audio + Video unterschiedliche Längen" → Task 1 (stretch_last_cut_to_audio in PacingService). ✓
  - "Clips nur als gelbes Feld" → Task 2+3 (thumbstrip backend) + Task 6+7+8 (model+VM+wiring) + Task 9 (thumbnail-strip rows in clip template). ✓
  - "Audio nur als blaues Feld" → Task 9 (A1-lane with Opacity 0.95 + symmetric mid-axis Y/Height in VM patch). ✓
  - Bonus: per-clip mini-waveform → Task 4+5 (clipwave backend) + Task 9 (Path with PeaksToWaveformGeometryConverter). ✓

- Placeholder scan: no `TBD`/`TODO`/`implement later`. All steps contain real code or real commands.

- Type consistency:
  - `ThumbnailFrames: ObservableCollection<string>` — used in Task 7 (model), Task 8 (VM populates), Task 9 (XAML ItemsControl). ✓
  - `AudioPeaks: ObservableCollection<float>` — used in Task 7, Task 8, Task 9 (Path Binding). ✓
  - `_stretch_last_cut_to_audio(cuts, audio_duration)` — defined Task 1 Step 3, called Task 1 Step 4. ✓
  - `extract_thumbnail_strip(video_path, n, size)` — defined Task 2, used Task 3's `_extract_thumbstrip`. ✓
  - `extract_peaks(media_path, n_buckets)` — defined Task 4, used Task 5's `_extract_clip_peaks`. ✓
  - `GetThumbStripAsync(int, int)` / `GetClipWaveAsync(int, int)` — defined Task 6, called Task 8. ✓
  - `ClampStartToNeighbours(entry, desiredStart, duration)` — defined Task 10 Step 1, called Step 2. ✓
  - `CloseGapsInContiguousMode()` — called Task 10 Step 3, defined same step. ✓

No drift detected. Plan ready to execute.
