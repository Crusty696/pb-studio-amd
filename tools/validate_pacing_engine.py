"""
Pacing Engine Validation Script

Validates the pacing engine installation and functionality.
Performs comprehensive checks on:
- Module imports
- Configuration validation
- Timeline generation
- Clip selection
- Integration compatibility
"""

import sys
import logging
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

logging.basicConfig(
    level=logging.INFO,
    format='%(levelname)s: %(message)s'
)
logger = logging.getLogger(__name__)

# Fix console encoding for Windows
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')


def check_imports():
    """Validate all pacing engine imports."""
    print("\n" + "="*60)
    print("1. CHECKING IMPORTS")
    print("="*60)

    try:
        from src.pb_studio.pacing import (
            AdvancedPacingEngine,
            PacingConfig,
            CutPoint,
            ClipSelector
        )
        print("✓ Main imports successful")
    except ImportError as e:
        print(f"✗ Main imports failed: {e}")
        return False

    try:
        from src.pb_studio.pacing.advanced_pacing_engine import SyncMode, TransitionType
        print("✓ Enum imports successful")
    except ImportError as e:
        print(f"✗ Enum imports failed: {e}")
        return False

    try:
        from src.pb_studio.pacing.clip_selector import ClipMetadata
        print("✓ ClipMetadata import successful")
    except ImportError as e:
        print(f"✗ ClipMetadata import failed: {e}")
        return False

    print("\n✓ All imports validated successfully!")
    return True


def check_configuration():
    """Validate PacingConfig creation and conversion."""
    print("\n" + "="*60)
    print("2. CHECKING CONFIGURATION")
    print("="*60)

    try:
        from src.pb_studio.pacing import PacingConfig
        from src.pb_studio.pacing.advanced_pacing_engine import SyncMode

        # Test default config
        config = PacingConfig()
        print(f"✓ Default config created")
        print(f"  - Pacing: {config.pacing}")
        print(f"  - Precision: {config.precision}")
        print(f"  - Sync Mode: {config.sync_mode.value}")

        # Test custom config
        custom = PacingConfig(
            pacing=5,
            precision=10,
            energy_react=8,
            chaos=3,
            min_clip_length=1.5,
            max_clip_length=5.0,
            sync_mode=SyncMode.BEAT_SYNC
        )
        print(f"✓ Custom config created")

        # Test legacy conversion
        legacy = custom.to_legacy_dict()
        assert "pacing" in legacy
        assert "precision" in legacy
        assert legacy["min_dur"] == 1.5
        print(f"✓ Legacy conversion works")

        print("\n✓ Configuration validation successful!")
        return True

    except Exception as e:
        print(f"✗ Configuration check failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def check_timeline_generation():
    """Validate timeline generation with mock data."""
    print("\n" + "="*60)
    print("3. CHECKING TIMELINE GENERATION")
    print("="*60)

    try:
        import numpy as np
        from src.pb_studio.pacing import AdvancedPacingEngine, PacingConfig
        from src.pb_studio.pacing.advanced_pacing_engine import SyncMode

        # Create mock audio analysis
        beats = [[i * 0.5, 1 if i % 4 == 0 else 2] for i in range(40)]
        analysis = {
            "bpm": 120,
            "beat_data": beats,
            "count": len(beats)
        }

        # Create mock energy curve
        rms = 0.5 + 0.3 * np.sin(2 * np.pi * 0.2 * np.linspace(0, 20, 100))
        times = np.linspace(0, 20, 100)

        print(f"✓ Mock data created (BPM: {analysis['bpm']}, Duration: 20s)")

        # Test each sync mode
        modes = [
            SyncMode.HYBRID,
            SyncMode.BEAT_SYNC,
            SyncMode.ENERGY_SYNC,
            SyncMode.EMOTIONAL_SYNC
        ]

        for mode in modes:
            config = PacingConfig(sync_mode=mode, pacing=3, precision=8)
            engine = AdvancedPacingEngine(config)

            engine.analyze_audio_structure(analysis, rms, times)
            cuts = engine.plan_cuts(20.0)

            assert len(cuts) > 0, f"No cuts generated for {mode.value}"
            assert all(cut.time >= 0 for cut in cuts), "Negative cut times"
            assert all(cut.duration > 0 for cut in cuts), "Zero duration cuts"

            stats = engine.get_statistics()
            print(f"✓ {mode.value}: {len(cuts)} cuts, "
                  f"{stats['beat_alignment_ratio']:.1%} beat-aligned")

        print("\n✓ Timeline generation validation successful!")
        return True

    except Exception as e:
        print(f"✗ Timeline generation check failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def check_clip_selection():
    """Validate clip selector functionality."""
    print("\n" + "="*60)
    print("4. CHECKING CLIP SELECTION")
    print("="*60)

    try:
        import numpy as np
        from src.pb_studio.pacing import ClipSelector
        from src.pb_studio.pacing.clip_selector import ClipMetadata

        # Create selector
        selector = ClipSelector()
        print("✓ ClipSelector created")

        # Add sample clips
        clips = [
            ClipMetadata(
                video_id=i,
                file_path=f"video{i}.mp4",
                start_time=0.0,
                duration=10.0,
                motion_score=np.random.random(),
                energy_score=np.random.random(),
                tags=["test"],
                embedding=np.random.random(768)
            )
            for i in range(10)
        ]

        for clip in clips:
            selector.add_clip(clip)

        print(f"✓ Added {len(clips)} clips")

        # Test motion selection
        high_motion = selector.select_by_motion(0.5, operator="greater", k=5)
        print(f"✓ Motion selection: {len(high_motion)} clips")

        # Test energy selection
        medium_energy = selector.select_by_energy(0.5, tolerance=0.2, k=5)
        print(f"✓ Energy selection: {len(medium_energy)} clips")

        # Test tag selection
        tagged = selector.select_by_tags(["test"], any_match=True, k=5)
        print(f"✓ Tag selection: {len(tagged)} clips")

        # Test hybrid selection
        hybrid = selector.select_hybrid(
            energy_target=0.5,
            motion_threshold=0.3,
            weights={"energy": 0.5, "motion": 0.5},
            k=5
        )
        print(f"✓ Hybrid selection: {len(hybrid)} results")

        # Test statistics
        stats = selector.get_statistics()
        assert stats["total_clips"] == len(clips)
        print(f"✓ Statistics: {stats['total_clips']} clips, "
              f"avg motion {stats['avg_motion']:.2f}")

        print("\n✓ Clip selection validation successful!")
        return True

    except Exception as e:
        print(f"✗ Clip selection check failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def check_integration_compatibility():
    """Check compatibility with existing VideoGenerator."""
    print("\n" + "="*60)
    print("5. CHECKING INTEGRATION COMPATIBILITY")
    print("="*60)

    try:
        import numpy as np
        from src.pb_studio.pacing import AdvancedPacingEngine, PacingConfig

        # Simulate VideoGenerator config
        video_config = {
            "pacing": 4,
            "precision": 8,
            "energy_react": 6,
            "chaos": 3,
            "min_dur": 2.0,
            "max_dur": 6.0
        }

        # Convert to PacingConfig
        pacing_config = PacingConfig(
            pacing=video_config["pacing"],
            precision=video_config["precision"],
            energy_react=video_config["energy_react"],
            chaos=video_config["chaos"],
            min_clip_length=video_config["min_dur"],
            max_clip_length=video_config["max_dur"]
        )

        print("✓ Config conversion successful")

        # Generate timeline
        analysis = {
            "bpm": 128,
            "beat_data": [[i * 0.46875, 1] for i in range(40)],
            "count": 40
        }
        rms = np.random.random(100)
        times = np.linspace(0, 20, 100)

        engine = AdvancedPacingEngine(pacing_config)
        engine.analyze_audio_structure(analysis, rms, times)
        cuts = engine.plan_cuts(20.0)

        print(f"✓ Generated {len(cuts)} cuts")

        # Generate EDL in VideoGenerator format
        edl = engine.generate_edit_decision_list()

        # Verify format
        for entry in edl:
            assert "time" in entry
            assert "duration" in entry
            assert "energy" in entry
            assert isinstance(entry["time"], float)
            assert isinstance(entry["duration"], float)

        print("✓ EDL format compatible")

        # Convert to legacy cut_list format
        cut_list = [
            {
                "time": cut.time,
                "duration": cut.duration,
                "energy": cut.energy
            }
            for cut in cuts
        ]

        print(f"✓ Legacy format conversion: {len(cut_list)} entries")

        print("\n✓ Integration compatibility validated!")
        return True

    except Exception as e:
        print(f"✗ Integration check failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def check_performance():
    """Basic performance benchmarks."""
    print("\n" + "="*60)
    print("6. PERFORMANCE BENCHMARKS")
    print("="*60)

    try:
        import time
        import numpy as np
        from src.pb_studio.pacing import AdvancedPacingEngine, PacingConfig

        # Large dataset (4 minutes @ 120 BPM = ~480 beats)
        beats = [[i * 0.5, 1 if i % 4 == 0 else 2] for i in range(480)]
        analysis = {
            "bpm": 120,
            "beat_data": beats,
            "count": len(beats)
        }
        rms = np.random.random(1000)
        times = np.linspace(0, 240, 1000)

        config = PacingConfig()
        engine = AdvancedPacingEngine(config)

        # Benchmark analysis
        start = time.time()
        engine.analyze_audio_structure(analysis, rms, times)
        analysis_time = time.time() - start

        # Benchmark planning
        start = time.time()
        cuts = engine.plan_cuts(240.0)
        planning_time = time.time() - start

        # Benchmark EDL generation
        start = time.time()
        edl = engine.generate_edit_decision_list()
        edl_time = time.time() - start

        print(f"✓ Analysis time: {analysis_time*1000:.2f}ms")
        print(f"✓ Planning time: {planning_time*1000:.2f}ms")
        print(f"✓ EDL generation: {edl_time*1000:.2f}ms")
        print(f"✓ Total time: {(analysis_time + planning_time + edl_time)*1000:.2f}ms")
        print(f"✓ Generated {len(cuts)} cuts for 240s audio")

        # Performance targets
        total_time = analysis_time + planning_time + edl_time
        if total_time < 1.0:
            print("\n✓ Performance: EXCELLENT (< 1s)")
        elif total_time < 3.0:
            print("\n✓ Performance: GOOD (< 3s)")
        else:
            print(f"\n⚠ Performance: OK ({total_time:.2f}s - consider optimization)")

        return True

    except Exception as e:
        print(f"✗ Performance check failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Run all validation checks."""
    print("\n" + "="*70)
    print(" "*15 + "PACING ENGINE VALIDATION")
    print("="*70)

    results = []

    # Run checks
    results.append(("Imports", check_imports()))
    results.append(("Configuration", check_configuration()))
    results.append(("Timeline Generation", check_timeline_generation()))
    results.append(("Clip Selection", check_clip_selection()))
    results.append(("Integration Compatibility", check_integration_compatibility()))
    results.append(("Performance", check_performance()))

    # Summary
    print("\n" + "="*70)
    print(" "*25 + "SUMMARY")
    print("="*70 + "\n")

    passed = sum(1 for _, result in results if result)
    total = len(results)

    for name, result in results:
        status = "✓ PASSED" if result else "✗ FAILED"
        print(f"{name:30s} {status}")

    print("\n" + "-"*70)
    print(f"Total: {passed}/{total} checks passed")

    if passed == total:
        print("\n✓ All validation checks passed!")
        print("The pacing engine is ready for production use.")
        return 0
    else:
        print(f"\n✗ {total - passed} check(s) failed.")
        print("Please review the errors above.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
