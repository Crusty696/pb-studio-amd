import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch
from pb_studio.rendering.preview_renderer import TimelineEntry, PreviewGenerator

class TestTimelineEntry:
    def test_duration(self):
        entry = TimelineEntry(
            video_path="test.mp4",
            start_time=10.0,
            end_time=25.0,
            timeline_start=0.0,
            timeline_end=15.0
        )
        assert entry.duration == 15.0

    def test_timeline_duration(self):
        entry = TimelineEntry(
            video_path="test.mp4",
            start_time=10.0,
            end_time=25.0,
            timeline_start=5.0,
            timeline_end=20.0
        )
        assert entry.timeline_duration == 15.0

class TestPreviewGeneratorFilterClips:
    def test_filter_clips_for_interval(self, temp_dir):
        generator = PreviewGenerator(output_dir=temp_dir)

        # Timeline entries
        e1 = TimelineEntry("v1.mp4", 0, 10, 0, 10)   # 0-10
        e2 = TimelineEntry("v2.mp4", 0, 10, 10, 20)  # 10-20
        e3 = TimelineEntry("v3.mp4", 0, 10, 20, 30)  # 20-30
        e4 = TimelineEntry("v4.mp4", 0, 10, 5, 15)   # 5-15 (overlapping e1, e2)

        timeline = [e3, e1, e2, e4] # Unsorted

        # Interval 5 to 15
        filtered = generator._filter_clips_for_interval(timeline, 5.0, 15.0)

        # Expected:
        # e1 (ends at 10 > 5 and starts at 0 < 15)
        # e2 (ends at 20 > 5 and starts at 10 < 15)
        # e4 (ends at 15 > 5 and starts at 5 < 15)
        # Sorted by timeline_start: e1 (0), e4 (5), e2 (10)

        assert len(filtered) == 3
        assert filtered[0] == e1
        assert filtered[1] == e4
        assert filtered[2] == e2

    def test_filter_clips_no_overlap(self, temp_dir):
        generator = PreviewGenerator(output_dir=temp_dir)
        timeline = [TimelineEntry("v1.mp4", 0, 10, 0, 10)]

        assert len(generator._filter_clips_for_interval(timeline, 10.0, 20.0)) == 0
        assert len(generator._filter_clips_for_interval(timeline, -10.0, 0.0)) == 0

    def test_filter_clips_exact_boundary(self, temp_dir):
        generator = PreviewGenerator(output_dir=temp_dir)
        timeline = [TimelineEntry("v1.mp4", 0, 10, 0, 10)]

        # e.timeline_end > start and e.timeline_start < end
        # 10 > 10 is False -> not included
        assert len(generator._filter_clips_for_interval(timeline, 10.0, 15.0)) == 0
        # 0 < 0 is False -> not included
        assert len(generator._filter_clips_for_interval(timeline, -5.0, 0.0)) == 0

class TestPreviewGeneratorGeneratePreview:
    def test_generate_preview_empty_timeline(self, temp_dir):
        generator = PreviewGenerator(output_dir=temp_dir)
        assert generator.generate_preview([]) is None

    def test_generate_preview_no_clips_in_interval(self, temp_dir):
        generator = PreviewGenerator(output_dir=temp_dir)
        timeline = [TimelineEntry("v1.mp4", 0, 10, 0, 10)]
        assert generator.generate_preview(timeline, start_time_sec=20.0) is None

    @patch.object(PreviewGenerator, '_render_clips')
    def test_generate_preview_calls_render(self, mock_render, temp_dir):
        generator = PreviewGenerator(output_dir=temp_dir)
        timeline = [TimelineEntry("v1.mp4", 0, 10, 0, 10)]
        mock_render.return_value = True

        output_path = generator.generate_preview(timeline, start_time_sec=0.0, duration=5.0)

        assert output_path == temp_dir / "preview.mp4"
        mock_render.assert_called_once()
        # Check arguments of _render_clips
        args, _ = mock_render.call_args
        assert args[0] == timeline # All clips in this case
        assert args[1] == 0.0 # start_time_sec
        assert args[2] == 5.0 # duration
        assert args[3] == temp_dir / "preview.mp4"

class TestPreviewGeneratorRenderClips:
    @patch('subprocess.run')
    def test_render_clips_success(self, mock_run, temp_dir):
        generator = PreviewGenerator(output_dir=temp_dir)
        clip = TimelineEntry("test.mp4", 0, 10, 0, 10)
        output_path = temp_dir / "preview.mp4"

        # Setup mock for subprocess.run
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_run.return_value = mock_result

        def side_effect(cmd, **kwargs):
            out_file = Path(cmd[-1])
            out_file.parent.mkdir(parents=True, exist_ok=True)
            out_file.touch()
            with open(out_file, "wb") as f:
                f.write(b"fake video data")
            return mock_result

        mock_run.side_effect = side_effect

        success = generator._render_clips([clip], 0.0, 10.0, output_path)

        assert success is True
        # Should have called ffmpeg twice: once for segment, once for concat
        assert mock_run.call_count == 2

        # Verify segment command
        seg_args = mock_run.call_args_list[0][0][0]
        assert "ffmpeg" in seg_args
        assert "-ss" in seg_args
        assert "test.mp4" in seg_args
        assert "mpegts" in seg_args

        # Verify concat command
        concat_args = mock_run.call_args_list[1][0][0]
        assert "ffmpeg" in concat_args
        assert any("concat:" in arg for arg in concat_args)

    @patch('subprocess.run')
    def test_render_clips_ffmpeg_fail(self, mock_run, temp_dir):
        generator = PreviewGenerator(output_dir=temp_dir)
        clip = TimelineEntry("test.mp4", 0, 10, 0, 10)
        output_path = temp_dir / "preview.mp4"

        mock_result = MagicMock()
        mock_result.returncode = 1
        mock_run.return_value = mock_result

        success = generator._render_clips([clip], 0.0, 10.0, output_path)
        assert success is False

class TestPreviewGeneratorCleanup:
    def test_cleanup(self, temp_dir):
        generator = PreviewGenerator(output_dir=temp_dir)

        # Create some files
        p1 = temp_dir / "preview_1.mp4"
        p2 = temp_dir / "preview_abc.mp4"
        t1 = temp_dir / "thumb_1.jpg"
        other = temp_dir / "other.txt"

        p1.touch()
        p2.touch()
        t1.touch()
        other.touch()

        generator.cleanup()

        assert not p1.exists()
        assert not p2.exists()
        assert not t1.exists()
        assert other.exists()
