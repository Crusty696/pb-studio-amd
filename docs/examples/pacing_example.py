"""
Historical Pacing Engine API sketch.

This script demonstrates:
1. Audio analysis and beat detection
2. Timeline generation with different sync modes
3. Clip selection using embeddings
4. Integration with VideoGenerator

This file is retained as reference and is not the production pacing workflow.
Production media must be imported into the active project's media catalog and
referenced by registered clip IDs. Paths below are local fixtures only.
"""

import numpy as np
import logging
from pathlib import Path

# PB Studio imports
from pb_studio.pacing import (
    AdvancedPacingEngine,
    PacingConfig,
    ClipSelector,
)
from pb_studio.pacing.advanced_pacing_engine import SyncMode
from pb_studio.pacing.clip_selector import ClipMetadata
from pb_studio.audio.analyzer import AudioAnalyzer
from pb_studio.data.vector_store import VectorStore

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def example_basic_timeline_generation():
    """
    Example 1: Basic timeline generation from audio file.
    """
    print("\n" + "="*60)
    print("EXAMPLE 1: Basic Timeline Generation")
    print("="*60 + "\n")

    # 1. Analyze audio
    audio_path = "data/audio/song.mp3"  # Replace with your audio file
    analyzer = AudioAnalyzer()

    print(f"Analyzing audio: {audio_path}")
    analysis = analyzer.analyze_file(audio_path)

    if "error" in analysis:
        print(f"Analysis failed: {analysis['error']}")
        return

    print(f"BPM: {analysis['bpm']}")
    print(f"Beats detected: {analysis['count']}")

    # 2. Get energy curve
    import librosa
    y, sr = librosa.load(audio_path, sr=22050, mono=True)
    duration = librosa.get_duration(y=y, sr=sr)
    rms = librosa.feature.rms(y=y)[0]
    times = librosa.times_like(rms, sr=sr)

    print(f"Duration: {duration:.2f}s")
    print(f"Energy samples: {len(rms)}")

    # 3. Configure pacing engine
    config = PacingConfig(
        pacing=4,              # Fast pacing
        precision=8,           # High precision
        energy_react=6,        # Moderate energy reactivity
        chaos=2,               # Low chaos
        min_clip_length=2.0,
        max_clip_length=6.0,
        sync_mode=SyncMode.HYBRID
    )

    # 4. Generate timeline
    engine = AdvancedPacingEngine(config)
    engine.analyze_audio_structure(analysis, rms, times)
    cuts = engine.plan_cuts(duration)

    print(f"\nGenerated {len(cuts)} cuts:")
    for i, cut in enumerate(cuts[:5]):  # Show first 5
        print(f"  Cut {i+1}: {cut.time:.2f}s -> {cut.end_time:.2f}s "
              f"(dur: {cut.duration:.2f}s, energy: {cut.energy:.2f}, "
              f"beat_aligned: {cut.beat_aligned})")

    # 5. Get statistics
    stats = engine.get_statistics()
    print(f"\nStatistics:")
    print(f"  Total cuts: {stats['total_cuts']}")
    print(f"  Beat alignment: {stats['beat_alignment_ratio']:.1%}")
    print(f"  Avg duration: {stats['avg_cut_duration']:.2f}s")
    print(f"  Avg confidence: {stats['avg_confidence']:.2f}")


def example_sync_mode_comparison():
    """
    Example 2: Compare different sync modes on the same audio.
    """
    print("\n" + "="*60)
    print("EXAMPLE 2: Sync Mode Comparison")
    print("="*60 + "\n")

    # Mock audio data (replace with real analysis)
    analysis = {
        "bpm": 128,
        "beat_data": [[i * 0.46875, 1 if i % 4 == 0 else 2] for i in range(85)],  # 40s @ 128 BPM
        "count": 85
    }
    duration = 40.0
    rms = 0.5 + 0.3 * np.sin(2 * np.pi * 0.1 * np.linspace(0, duration, 200))
    times = np.linspace(0, duration, 200)

    modes = [
        (SyncMode.BEAT_SYNC, "Beat Sync (Exact beat alignment)"),
        (SyncMode.ENERGY_SYNC, "Energy Sync (Energy peaks)"),
        (SyncMode.EMOTIONAL_SYNC, "Emotional Sync (Musical phrases)"),
        (SyncMode.HYBRID, "Hybrid (Combined approach)")
    ]

    for mode, description in modes:
        config = PacingConfig(
            pacing=3,
            precision=8,
            sync_mode=mode
        )

        engine = AdvancedPacingEngine(config)
        engine.analyze_audio_structure(analysis, rms, times)
        cuts = engine.plan_cuts(duration)

        stats = engine.get_statistics()

        print(f"\n{description}:")
        print(f"  Cuts: {stats['total_cuts']}")
        print(f"  Beat aligned: {stats['beat_alignment_ratio']:.1%}")
        print(f"  Avg duration: {stats['avg_cut_duration']:.2f}s")


def example_clip_selection():
    """
    Example 3: Intelligent clip selection using embeddings.
    """
    print("\n" + "="*60)
    print("EXAMPLE 3: Intelligent Clip Selection")
    print("="*60 + "\n")

    # Initialize selector (without vector store for demo)
    selector = ClipSelector()

    # Add sample clips
    clips = [
        ClipMetadata(
            video_id=1,
            file_path="data/video/action_scene.mp4",
            start_time=0.0,
            duration=10.0,
            motion_score=0.9,
            energy_score=0.8,
            tags=["action", "fast", "outdoor"],
            embedding=np.random.random(1152)  # Canonical SigLIP mock embedding
        ),
        ClipMetadata(
            video_id=2,
            file_path="data/video/calm_landscape.mp4",
            start_time=0.0,
            duration=15.0,
            motion_score=0.2,
            energy_score=0.3,
            tags=["calm", "nature", "slow"],
            embedding=np.random.random(1152)
        ),
        ClipMetadata(
            video_id=3,
            file_path="data/video/city_timelapse.mp4",
            start_time=0.0,
            duration=12.0,
            motion_score=0.7,
            energy_score=0.6,
            tags=["urban", "medium", "timelapse"],
            embedding=np.random.random(1152)
        )
    ]

    for clip in clips:
        selector.add_clip(clip)

    print(f"Added {len(clips)} clips to selector.\n")

    # 1. Select by motion
    print("1. High motion clips (motion > 0.5):")
    high_motion = selector.select_by_motion(0.5, operator="greater", k=5)
    for clip in high_motion:
        print(f"   - {Path(clip.file_path).name}: motion={clip.motion_score:.2f}")

    # 2. Select by energy
    print("\n2. Medium energy clips (energy ~ 0.6):")
    medium_energy = selector.select_by_energy(0.6, tolerance=0.15, k=5)
    for clip in medium_energy:
        print(f"   - {Path(clip.file_path).name}: energy={clip.energy_score:.2f}")

    # 3. Select by tags
    print("\n3. Clips with 'outdoor' or 'nature' tags:")
    nature_clips = selector.select_by_tags(["outdoor", "nature"], any_match=True, k=5)
    for clip in nature_clips:
        print(f"   - {Path(clip.file_path).name}: tags={clip.tags}")

    # 4. Hybrid selection
    print("\n4. Hybrid selection (high energy + high motion):")
    best_clips = selector.select_hybrid(
        energy_target=0.7,
        motion_threshold=0.5,
        weights={"energy": 0.5, "motion": 0.5},
        k=3
    )
    for clip, score in best_clips:
        print(f"   - {Path(clip.file_path).name}: score={score:.3f}, "
              f"motion={clip.motion_score:.2f}, energy={clip.energy_score:.2f}")

    # Statistics
    stats = selector.get_statistics()
    print(f"\nSelector Statistics:")
    print(f"  Total clips: {stats['total_clips']}")
    print(f"  Avg motion: {stats['avg_motion']:.2f}")
    print(f"  Avg energy: {stats['avg_energy']:.2f}")
    print(f"  Unique tags: {stats['unique_tags']}")


def example_pacing_presets():
    """
    Example 4: Genre-specific pacing presets.
    """
    print("\n" + "="*60)
    print("EXAMPLE 4: Genre-Specific Pacing Presets")
    print("="*60 + "\n")

    presets = {
        "EDM": PacingConfig(
            pacing=5,
            precision=10,
            energy_react=8,
            chaos=3,
            min_clip_length=1.5,
            max_clip_length=4.0,
            sync_mode=SyncMode.BEAT_SYNC
        ),
        "Hip-Hop": PacingConfig(
            pacing=3,
            precision=9,
            energy_react=6,
            chaos=4,
            min_clip_length=2.0,
            max_clip_length=6.0,
            sync_mode=SyncMode.BEAT_SYNC
        ),
        "Classical": PacingConfig(
            pacing=2,
            precision=5,
            energy_react=7,
            chaos=1,
            min_clip_length=4.0,
            max_clip_length=10.0,
            sync_mode=SyncMode.ENERGY_SYNC
        ),
        "Ambient": PacingConfig(
            pacing=1,
            precision=3,
            energy_react=4,
            chaos=2,
            min_clip_length=5.0,
            max_clip_length=15.0,
            sync_mode=SyncMode.EMOTIONAL_SYNC
        ),
        "Rock": PacingConfig(
            pacing=4,
            precision=7,
            energy_react=8,
            chaos=5,
            min_clip_length=2.0,
            max_clip_length=7.0,
            sync_mode=SyncMode.HYBRID
        )
    }

    for genre, config in presets.items():
        print(f"\n{genre}:")
        print(f"  Pacing: {config.pacing}/5")
        print(f"  Precision: {config.precision}/10")
        print(f"  Energy React: {config.energy_react}/10")
        print(f"  Chaos: {config.chaos}/10")
        print(f"  Clip Length: {config.min_clip_length}s - {config.max_clip_length}s")
        print(f"  Sync Mode: {config.sync_mode.value}")


def example_full_integration():
    """
    Example 5: Full integration with mock video generation.
    """
    print("\n" + "="*60)
    print("EXAMPLE 5: Full VideoGenerator Integration")
    print("="*60 + "\n")

    # Mock configuration (would come from UI)
    video_config = {
        "master_audio": "data/audio/song.mp3",
        "source_videos": [
            "data/video/video1.mp4",
            "data/video/video2.mp4",
            "data/video/video3.mp4"
        ],
        "output_path": "output/final_video.mp4",
        "pacing": 4,
        "precision": 8,
        "energy_react": 6,
        "chaos": 3,
        "min_dur": 2.0,
        "max_dur": 6.0
    }

    print("Configuration:")
    print(f"  Audio: {video_config['master_audio']}")
    print(f"  Sources: {len(video_config['source_videos'])} videos")
    print(f"  Pacing: {video_config['pacing']}/5")
    print(f"  Precision: {video_config['precision']}/10")

    # Convert to PacingConfig
    pacing_config = PacingConfig(
        pacing=video_config["pacing"],
        precision=video_config["precision"],
        energy_react=video_config["energy_react"],
        chaos=video_config["chaos"],
        min_clip_length=video_config["min_dur"],
        max_clip_length=video_config["max_dur"]
    )

    print(f"\nPacing Config:")
    print(f"  Sync Mode: {pacing_config.sync_mode.value}")
    print(f"  Clip Range: {pacing_config.min_clip_length}s - {pacing_config.max_clip_length}s")

    # This would integrate with VideoGenerator._plan_cuts()
    print("\nIntegration point: Replace VideoGenerator._plan_cuts() with:")
    print("""
    engine = AdvancedPacingEngine(pacing_config)
    engine.analyze_audio_structure(analysis, rms, times)
    cuts = engine.plan_cuts(duration)

    # Convert to legacy format
    cut_list = [
        {"time": cut.time, "duration": cut.duration, "energy": cut.energy}
        for cut in cuts
    ]
    """)


def main():
    """Run all examples."""
    print("\n" + "="*70)
    print(" "*15 + "PACING ENGINE EXAMPLES")
    print("="*70)

    try:
        # Example 1: Basic usage (requires real audio file)
        # example_basic_timeline_generation()

        # Example 2: Sync mode comparison
        example_sync_mode_comparison()

        # Example 3: Clip selection
        example_clip_selection()

        # Example 4: Genre presets
        example_pacing_presets()

        # Example 5: Integration guide
        example_full_integration()

        print("\n" + "="*70)
        print("All examples completed successfully!")
        print("="*70 + "\n")

    except Exception as e:
        logger.error(f"Example failed: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
