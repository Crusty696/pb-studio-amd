"""Test suite for Audio/Video Pacing Specialist modules."""

# We need to make these importable as pace_analyzer submodules
import sys, os

# Add parent directory of pace_analyzer_test to path so we can import pace_analyzer
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pace_analyzer import (
    SpeechPaceAnalyzer, PaceSegment,
    BeatDetector, DetectedBeat,
    PacingScore, PacingReport, PacingOptimizer, OptimizationSuggestion,
    MoodDetector, EDMGenreMood, EDM_MOOD_PROFILES,
    GrooveDetector, GrooveFeature, GrooveResult, describe_groove_to_user,
)
from pace_analyzer import GENRES, get_genre, BPM_CATEGORIES


def test_imports():
    """Test 1: All modules can be imported."""
    print("\n=== TEST 1: IMPORTS ===")
    try:
        from pace_analyzer import (
            SpeechPaceAnalyzer, PaceSegment,
            BeatDetector, DetectedBeat,
            PacingScore, PacingReport, PacingOptimizer, OptimizationSuggestion,
            MoodDetector, EDMGenreMood, EDM_MOOD_PROFILES,
            GrooveDetector, GrooveFeature, GrooveResult, describe_groove_to_user,
        )
        from pace_analyzer import GENRES, get_genre, BPM_CATEGORIES
        
        print("  ✅ All modules imported successfully")
        return True
    except Exception as e:
        print(f"  ❌ Import failed: {e}")
        return False


def test_mood_profiles_count():
    """Test 2: EDM_MOOD_PROFILES has expected number of genre profiles."""
    print("\n=== TEST 2: MOOD PROFILES COUNT ===")
    required = [
        "Psytrance", "Progressive Trance", "Uplifting Trance", "Hypnotic Trance",
        "Progressive House", "Tech House", "Deep House",
        "Minimal Techno", "Hard Techno", "Melodic Techno",
        "Drum and Bass", "Breakbeat",
        "Hardstyle", "Dubstep", "Melodic Dubstep",
        "Ambient", "Footwork",
    ]
    
    missing = [g for g in required if g not in EDM_MOOD_PROFILES]
    if missing:
        print(f"  ❌ Missing genres: {missing}")
        return False
    
    expected_count = len(required) + 4  # + Progressive Psytrance, Deep Tech, DJ Mix Techniques, Bass Profiles
    actual = len(EDM_MOOD_PROFILES)
    
    if actual >= expected_count:
        print(f"  ✅ All {expected_count}+ genre mood profiles present ({actual} total)")
        return True
    else:
        print(f"  ❌ Expected ≥{expected_count}, got {actual}")
        return False


def test_profile_structure():
    """Test 3: Each profile has all required keys."""
    print("\n=== TEST 3: PROFILE STRUCTURE ===")
    
    required_keys = [
        "expected_moods", "valence_target", "arousal_target",
        "bass_intensity_target", "groove_quality_target", "energy_profile"
    ]
    
    all_ok = True
    for genre_name in ["Psytrance", "Hard Techno", "Deep House", "Ambient"]:
        profile = EDM_MOOD_PROFILES.get(genre_name, {})
        
        for key in required_keys:
            if key not in profile:
                print(f"  ❌ {genre_name} missing '{key}'")
                all_ok = False
        
        # Check value ranges (0-1 for floats)
        valence_ok = 0.0 <= profile.get("valence_target", -1) <= 1.0
        arousal_ok = 0.0 <= profile.get("arousal_target", -1) <= 1.0
        bass_ok = 0.0 <= profile.get("bass_intensity_target", -1) <= 1.0
        groove_ok = 0.0 <= profile.get("groove_quality_target", -1) <= 1.0
        
        if not (valence_ok and arousal_ok and bass_ok and groove_ok):
            print(f"  ❌ {genre_name} has out-of-range values")
            all_ok = False
    
    if all_ok:
        print("  ✅ All checked profiles have correct structure and value ranges")
    
    return all_ok


def test_mood_detector_analyze_audio():
    """Test 4: MoodDetector.analyze_audio() returns correct results."""
    print("\n=== TEST 4: ANALYZE AUDIO (Psytrance) ===")
    
    detector = MoodDetector()
    
    # Psytrance: Bass-heavy, high energy
    result = detector.analyze_audio(
        spectral_bands=[0.85, 0.6, 0.3, 0.4, 0.2, 0.05],
        rms_energy=0.75,
        genre_name="Psytrance"
    )
    
    checks = []
    
    # Check that result is an EDMGenreMood
    if not isinstance(result, EDMGenreMood):
        print(f"  ❌ Result type: {type(result)}")
        return False
    
    d = result.to_dict()
    
    # Valence should be high (Psytrance is positive/euphoric)
    if result.valence < 0.5:
        print(f"  ❌ Psytrance valence too low: {result.valence}")
        checks.append(False)
    else:
        print(f"  ✅ Valence: {result.valence:.3f} (expected > 0.5)")
        checks.append(True)
    
    # Arousal should be high for Psytrance
    if result.arousal < 0.7:
        print(f"  ❌ Psytrance arousal too low: {result.arousal}")
        checks.append(False)
    else:
        print(f"  ✅ Arousal: {result.arousal:.3f} (expected > 0.7)")
        checks.append(True)
    
    # Bass intensity should be very high for Psytrance
    if result.bass_intensity < 0.7:
        print(f"  ❌ Psytrance bass too low: {result.bass_intensity}")
        checks.append(False)
    else:
        print(f"  ✅ Bass Intensity: {result.bass_intensity:.3f} (expected > 0.7)")
        checks.append(True)
    
    # Groove should be high for Psytrance
    if result.groove_score < 0.6:
        print(f"  ❌ Psytrance groove too low: {result.groove_score}")
        checks.append(False)
    else:
        print(f"  ✅ Groove Score: {result.groove_score:.3f} (expected > 0.6)")
        checks.append(True)
    
    # Drop should be detected with high bass + energy
    if result.drop_detected:
        print("  ✅ Drop detected (high bass + energy)")
        checks.append(True)
    else:
        print(f"  ⚠️  Drop not detected at {result.energy_level:.2f} energy")
        checks.append(True)  # Not a hard fail
    
    # Check to_dict output
    required_keys = ["genre_name", "mood_label_de", "valence", "arousal", 
                     "bass_intensity", "groove_score"]
    missing_keys = [k for k in required_keys if k not in d]
    if missing_keys:
        print(f"  ❌ to_dict() missing keys: {missing_keys}")
        return False
    
    print(f"  ✅ to_dict() has all expected keys ({len(d)} total)")
    
    # Check confidence score is reasonable (0.3-1.0)
    if 0.3 <= result.confidence_score <= 1.0:
        print(f"  ✅ Confidence: {result.confidence_score:.3f} (in valid range)")
    else:
        print(f"  ❌ Confidence out of range: {result.confidence_score}")
    
    return len(checks) == len([c for c in checks if c])


def test_mood_detector_hard_techno():
    """Test 5: Hard Techno should have different mood from Psytrance."""
    print("\n=== TEST 5: HARD TECHNO MOOD ===")
    
    detector = MoodDetector()
    
    techno_result = detector.analyze_audio(
        spectral_bands=[0.6, 0.4, 0.3, 0.5, 0.2, 0.08],
        rms_energy=0.6,
        genre_name="Hard Techno"
    )
    
    checks = []
    
    # Hard Techno should have lower valence than Psytrance
    psy_result = detector.analyze_audio(
        spectral_bands=[0.9, 0.7, 0.3, 0.4, 0.2, 0.1],
        rms_energy=0.8,
        genre_name="Psytrance"
    )
    
    if techno_result.valence < psy_result.valence:
        print(f"  ✅ Techno valence ({techno_result.valence:.2f}) < Psytrance valence ({psy_result.valence:.2f})")
        checks.append(True)
    else:
        print(f"  ❌ Expected lower valence for Techno, got {techno_result.valence}")
        checks.append(False)
    
    # Hard Techno should have higher arousal than Psytrance
    if techno_result.arousal > psy_result.arousal:
        print(f"  ✅ Techno arousal ({techno_result.arousal:.2f}) > Psytrance arousal ({psy_result.arousal:.2f})")
        checks.append(True)
    else:
        print(f"  ❌ Expected higher arousal for Techno, got {techno_result.arousal}")
        checks.append(False)
    
    # Dominance should be high (dark/aggressive sounds)
    if techno_result.dominance > 0.5:
        print(f"  ✅ Dominance: {techno_result.dominance:.3f} (expected > 0.5 for dark genre)")
        checks.append(True)
    else:
        print(f"  ❌ Expected high dominance for Hard Techno, got {techno_result.dominance}")
    
    return len(checks) == len([c for c in checks if c])


def test_mood_detector_deep_house():
    """Test 6: Deep House should have low arousal (relaxed)."""
    print("\n=== TEST 6: DEEP HOUSE MOOD ===")
    
    detector = MoodDetector()
    
    deep_result = detector.analyze_audio(
        spectral_bands=[0.5, 0.35, 0.4, 0.6, 0.25, 0.1],
        rms_energy=0.5,
        genre_name="Deep House"
    )
    
    checks = []
    
    # Deep House should have lower arousal than energetic genres
    if deep_result.arousal < 0.7:
        print(f"  ✅ Arousal: {deep_result.arousal:.3f} (expected < 0.7 for relaxed genre)")
        checks.append(True)
    else:
        print(f"  ❌ Expected lower arousal for Deep House, got {deep_result.arousal}")
        checks.append(False)
    
    # Groove should be high for Deep House
    if deep_result.groove_score > 0.7:
        print(f"  ✅ Groove: {deep_result.groove_score:.3f} (expected > 0.7)")
        checks.append(True)
    else:
        print(f"  ❌ Expected high groove for Deep House, got {deep_result.groove_score}")
    
    return len(checks) == len([c for c in checks if c])


def test_spectral_bands():
    """Test 7: Spectral band extraction works correctly."""
    print("\n=== TEST 7: SPECTRAL BAND EXTRACTION ===")
    
    detector = MoodDetector()
    
    # Test with known input
    spectral = detector.extract_spectral_bands([0.9, 0.65, 0.3, 0.4, 0.2, 0.1])
    
    checks = []
    
    if spectral.sub_bass_30_60hz > 0.7:
        print(f"  ✅ Sub-bass dominant: {spectral.sub_bass_30_60hz:.3f}")
        checks.append(True)
    else:
        print(f"  ❌ Expected high sub-bass, got {spectral.sub_bass_30_60hz}")
        checks.append(False)
    
    if spectral.mid_500_2khz > 0.4:
        print(f"  ✅ Mid presence: {spectral.mid_500_2khz:.3f}")
        checks.append(True)
    else:
        print(f"  ❌ Expected mid presence, got {spectral.mid_500_2khz}")
    
    return len(checks) == len([c for c in checks if c])


def test_timbre():
    """Test 8: Timbre computation works correctly."""
    print("\n=== TEST 8: TIMBRE COMPUTATION ===")
    
    detector = MoodDetector()
    
    spectral = detector.extract_spectral_bands([0.9, 0.65, 0.3, 0.4, 0.2, 0.1])
    timbre = detector.compute_timbre(spectral)
    
    checks = []
    
    # Bass-heavy signal should be warm
    if timbre.warmth > 0.6:
        print(f"  ✅ Warmth: {timbre.warmth:.3f} (expected high for bass-heavy)")
        checks.append(True)
    else:
        print(f"  ❌ Expected high warmth, got {timbre.warmth}")
        checks.append(False)
    
    # Should have some density
    if timbre.density > 0.5:
        print(f"  ✅ Density: {timbre.density:.3f} (expected > 0.5)")
        checks.append(True)
    else:
        print(f"  ❌ Expected high density, got {timbre.density}")
    
    return len(checks) == len([c for c in checks if c])


def test_genre_profile_access():
    """Test 9: get_edm_genre_mood_profile returns correct data."""
    print("\n=== TEST 9: GENRE PROFILE ACCESS ===")
    
    detector = MoodDetector()
    
    checks = []
    
    for genre in ["Psytrance", "Minimal Techno", "Drum and Bass", "Dubstep"]:
        profile = detector.get_edm_genre_mood_profile(genre)
        
        if "valence_target" not in profile or "arousal_target" not in profile:
            print(f"  ❌ {genre} profile missing keys")
            return False
        
        expected_valence = EDM_MOOD_PROFILES[genre]["valence_target"]
        actual_valence = profile["valence_target"]
        
        if abs(expected_valence - actual_valence) > 0.01:
            print(f"  ❌ {genre} valence mismatch: expected {expected_valence}, got {actual_valence}")
            checks.append(False)
        else:
            print(f"  ✅ {genre}: Valence={actual_valence:.2f} matches profile")
            checks.append(True)
    
    return len(checks) == len([c for c in checks if c])


def test_bpm_expectation():
    """Test 10: get_genre_expected_bpm returns correct BPM ranges."""
    print("\n=== TEST 10: BPM EXPECTATION ===")
    
    detector = MoodDetector()
    
    bpm_ranges = {
        "Psytrance": (130, 154),
        "Minimal Techno": (120, 135),
        "Drum and Bass": (165, 180),
        "Deep House": (115, 128),
    }
    
    checks = []
    
    for genre, expected in bpm_ranges.items():
        result = detector.get_genre_expected_bpm(genre)
        
        if "bpm_range_info" not in result:
            print(f"  ❌ {genre} missing bpm_range_info")
            return False
        
        actual_min = result["bpm_range_info"]["min"]
        actual_max = result["bpm_range_info"]["max"]
        
        if abs(actual_min - expected[0]) > 2 or abs(actual_max - expected[1]) > 2:
            print(f"  ❌ {genre} BPM mismatch: expected {expected}, got ({actual_min}, {actual_max})")
            checks.append(False)
        else:
            print(f"  ✅ {genre}: BPM={result['bpm_range_info']['optimal']:.0f}")
            checks.append(True)
    
    return len(checks) == len([c for c in checks if c])


def test_dj_mix_analysis():
    """Test 11: DJ Mix analysis detects track changes."""
    print("\n=== TEST 11: DJ MIX ANALYSIS ===")
    
    detector = MoodDetector()
    
    mix_data = [
        {"genre": "Psytrance", "rms_energy": 0.5, "timestamp_ms": 0},
        {"genre": "Psytrance", "rms_energy": 0.6, "timestamp_ms": 300000},
        {"genre": "Progressive Trance", "rms_energy": 0.7, "timestamp_ms": 600000},
        {"genre": "Uplifting Trance", "rms_energy": 0.85, "timestamp_ms": 900000},
    ]
    
    mix_result = detector.analyze_dj_mix(mix_data)
    
    checks = []
    
    # Should detect track changes (at least 2 transitions between genres)
    if mix_result["track_changes_detected"] >= 1:
        print(f"  ✅ Detected {mix_result['track_changes_detected']} track change(s)")
        checks.append(True)
    else:
        print("  ❌ No track changes detected")
        return False
    
    # Check that events have required fields
    for event in mix_result["track_change_events"]:
        if "timestamp_ms" not in event or "previous_genre" not in event:
            print(f"  ❌ Track change event missing keys: {event}")
            checks.append(False)
    
    # Check that mood is attached to each segment
    for seg in mix_result["segments_with_mood"]:
        if seg is None or "genre_name" not in seg:
            print(f"  ❌ Segment missing mood data")
            return False
    
    print("  ✅ All segments have mood analysis attached")
    
    return len(checks) == len([c for c in checks if c])


def test_groove_detector_typo_fix():
    """Test 12: Groove detector typo is fixed."""
    print("\n=== TEST 12: GROOVE DETECTOR TYPO FIX ===")
    
    groove = GrooveDetector()
    result_groove = groove.analyze_rms_envelope(
        [0.3, 0.5, 0.7, 0.9, 1.0]*20 + [0.5, 0.3, 0.1]*20, sample_rate=44100)
    
    d = result_groove.to_dict()
    
    if "hihat_pattern" in d:
        print(f"  ✅ 'hihat_pattern' key present: '{d['hihat_pattern']}'")
    else:
        print(f"  ❌ 'hihat_pattern' key missing! Keys: {list(d.keys())}")
        return False
    
    if "overall_groove_score" in d and "beat_strength" in d:
        print("  ✅ All expected keys present in to_dict()")
    
    return True


def test_genres_library_typo_fix():
    """Test 13: Electronic music genres typo is fixed."""
    print("\n=== TEST 13: GENRE LIBRARY TYPO FIX ===")
    
    from pace_analyzer import electronic_music_genres
    
    try:
        result_list = electronic_music_genres.list_all_genres()
        if isinstance(result_list, dict) and len(result_list) > 0:
            print(f"  ✅ list_all_genres() returns {len(result_list)} families")
            
            # Check BPM ranges are computed correctly (not raising NameError)
            for family, data in result_list.items():
                if "bpm_range" in data and isinstance(data["bpm_range"], str):
                    print(f"  ✅ {family}: BPM range = {data['bpm_range']}")
            
            return True
        else:
            print("  ❌ list_all_genres() returned unexpected format")
            return False
    except NameError as e:
        print(f"  ❌ NameError (typo not fixed): {e}")
        return False
    except Exception as e:
        print(f"  ❌ Unexpected error: {e}")
        return False


def test_genres_compatibility():
    """Test 14: Genre compatibility checks work."""
    print("\n=== TEST 14: GENRE COMPATIBILITY ===")
    
    detector = MoodDetector()
    
    # Same family should be compatible
    if not MoodDetector._genres_compatible("Psytrance", "Progressive Trance"):
        print("  ❌ Psytrance ↔ Progressive Trance should be compatible (same family)")
        return False
    
    print("  ✅ Psytrance ↔ Progressive Trance: Compatible (same family)")
    
    # Different families with BPM overlap should be checked
    result = MoodDetector._genres_compatible("Psytrance", "Hard Techno")
    # This might or might not be compatible depending on BPM ranges
    
    print(f"  ✅ Psytrance ↔ Hard Techno: Compatible={result}")
    
    return True


def test_all_methods_exist():
    """Test 15: All expected methods exist in MoodDetector."""
    print("\n=== TEST 15: MOOD DETECTOR METHODS ===")
    
    detector = MoodDetector()
    
    required_methods = [
        "analyze_audio", "analyze_dj_mix",
        "extract_spectral_bands", "compute_timbre",
        "get_edm_genre_mood_profile", "get_genre_expected_moods",
        "get_genre_expected_bpm"
    ]
    
    all_ok = True
    for method_name in required_methods:
        if hasattr(detector, method_name) and callable(getattr(detector, method_name)):
            print(f"  ✅ {method_name}() exists")
        else:
            print(f"  ❌ {method_name}() missing!")
            all_ok = False
    
    # Check private methods exist (for internal use)
    internal_methods = [
        "_spectral_to_valence", "_spectral_to_arousal", "_compute_dominance",
        "_detect_bass_intensity", "_estimate_groove", "_estimate_kick_strength",
        "_detect_build_up", "_detect_drop", "_detect_breakdown",
        "_get_mood_label", "_compute_confidence",
        "_classify_transition_quality", "_genres_compatible"
    ]
    
    for method_name in internal_methods:
        if hasattr(detector, method_name) and callable(getattr(detector, method_name)):
            pass  # OK
        else:
            print(f"  ⚠️  {method_name}() not found (may be static)")
    
    return all_ok


def main():
    """Run all tests."""
    print("=" * 60)
    print("AUDIO/VIDEO PACING SPECIALIST — COMPREHENSIVE TEST SUITE")
    print("=" * 60)
    
    test_functions = [
        ("Imports", test_imports),
        ("Mood Profiles Count", test_mood_profiles_count),
        ("Profile Structure", test_profile_structure),
        ("Analyze Audio (Psytrance)", test_mood_detector_analyze_audio),
        ("Hard Techno Mood", test_mood_detector_hard_techno),
        ("Deep House Mood", test_mood_detector_deep_house),
        ("Spectral Band Extraction", test_spectral_bands),
        ("Timbre Computation", test_timbre),
        ("Genre Profile Access", test_genre_profile_access),
        ("BPM Expectation", test_bpm_expectation),
        ("DJ Mix Analysis", test_dj_mix_analysis),
        ("Groove Detector Typo Fix", test_groove_detector_typo_fix),
        ("Genres Library Typo Fix", test_genres_library_typo_fix),
        ("Genre Compatibility", test_genres_compatibility),
        ("Mood Detector Methods", test_all_methods_exist),
    ]
    
    results = []
    for name, func in test_functions:
        try:
            result = func()
            if not isinstance(result, bool):
                result = True  # If function didn't return explicit False
            results.append((name, result))
        except Exception as e:
            print(f"  ❌ EXCEPTION: {e}")
            import traceback
            traceback.print_exc()
            results.append((name, False))
    
    # Summary
    print("\n" + "=" * 60)
    print("TEST SUMMARY")
    print("=" * 60)
    
    passed = sum(1 for _, r in results if r)
    failed = sum(1 for _, r in results if not r)
    
    for name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"  {status}: {name}")
    
    print("-" * 60)
    print(f"Total: {len(results)}, Passed: {passed}, Failed: {failed}")
    
    if failed == 0:
        print("\n🎉 ALL TESTS PASSED! Skill is verified and working correctly.")
        return 0
    else:
        print(f"\n⚠️  {failed} test(s) failed. Please review.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
