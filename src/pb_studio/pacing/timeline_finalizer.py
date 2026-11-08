"""Shared timeline boundary normalization, independent of pacing orchestration."""

from copy import deepcopy
from pathlib import Path
from typing import Callable

from pb_studio.pacing.pacing_models import CutListEntry


def finalize_cut_list(
    cut_list: list[CutListEntry],
    target_duration: float,
    duration_resolver: Callable[[str], float],
) -> list[CutListEntry]:
    """Single exit-point post-processing for all auto-pacing return paths.
    Future cut-list invariants (e.g. min-gap normalization, last-cut stretch)
    belong here, not at each return site.

    BUGFIX H1: target_duration MUST be the same budget the cuts were generated
    against (duration_limit or total_duration), NOT the full song length.
    Passing total_duration here stretched the last cut of a duration_limit'd
    (preview/short) render across the entire song -> giant runaway final clip.
    """
    if not cut_list or target_duration <= 0.0:
        return cut_list

    cut_list[:] = [
        cut for cut in cut_list
        if float(cut.start_time) < target_duration
    ]
    if not cut_list:
        return cut_list

    originals = sorted(cut_list, key=lambda cut: float(cut.start_time))
    finalized: list[CutListEntry] = []

    for index, original in enumerate(originals):
        interval_start = 0.0 if index == 0 else max(
            0.0, float(original.start_time)
        )
        if finalized:
            interval_start = max(interval_start, finalized[-1].end_time)
        interval_end = (
            min(target_duration, float(originals[index + 1].start_time))
            if index + 1 < len(originals)
            else target_duration
        )
        if interval_end <= interval_start + 1e-9:
            continue

        base_metadata = deepcopy(
            original.metadata if isinstance(original.metadata, dict) else {}
        )
        original_start = float(original.start_time)
        original_end = float(original.end_time)
        clip_start = max(0.0, float(base_metadata.get("clip_start", 0.0) or 0.0))
        if index == 0 and abs(original_start) > 0.001:
            if original_start > 0.0:
                clip_start = max(0.0, clip_start - original_start)
            else:
                clip_start += abs(original_start)
            base_metadata["boundary_original_start"] = original_start
            base_metadata["boundary_normalized_start"] = 0.0

        source_duration = float(base_metadata.get("source_duration", 0.0) or 0.0)
        if source_duration <= 0.0:
            file_path = str(base_metadata.get("file_path", "") or "")
            if file_path and Path(file_path).is_file():
                source_duration = duration_resolver(file_path)
                if source_duration > 0.0:
                    base_metadata["source_duration"] = source_duration

        cursor = interval_start
        segment_clip_start = clip_start
        while cursor < interval_end - 1e-9:
            remaining = interval_end - cursor
            if source_duration > 0.0:
                available = source_duration - segment_clip_start
                if available <= 1e-9:
                    segment_clip_start = 0.0
                    available = source_duration
                segment_duration = min(remaining, available)
            else:
                # Legacy/manual entries can lack resolvable media metadata.
                # Preserve compatibility; generated entries always carry a
                # measured source_duration from the conversion step above.
                segment_duration = remaining

            metadata = deepcopy(base_metadata)
            metadata["clip_start"] = segment_clip_start
            if cursor > interval_start + 1e-9:
                metadata["trigger_type"] = "source_repeat"
                metadata["trigger_strength"] = 0.0
                metadata.pop("trigger_provenance", None)
            if index == len(originals) - 1 and abs(original_end - target_duration) > 0.001:
                metadata["boundary_original_end"] = original_end
                metadata["boundary_normalized_end"] = target_duration
            segment_end = min(interval_end, cursor + segment_duration)
            finalized.append(CutListEntry(
                clip_id=original.clip_id,
                start_time=cursor,
                end_time=segment_end,
                metadata=metadata,
            ))
            cursor = segment_end
            segment_clip_start = 0.0

    cut_list[:] = finalized
    return cut_list

