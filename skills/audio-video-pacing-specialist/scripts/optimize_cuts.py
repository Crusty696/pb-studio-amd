"""CLI: Cut Optimization — Suggest Video/Audio Edits Based on Pacing

Usage:
    python optimize_cuts.py --transcript transcript.txt [--audio audio.wav] [--output cuts.json]
    python optimize_cuts.py --data analysis.json --beat beat_data.json --output cuts.json
"""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from pace_analyzer.speech_pace import SpeechPaceAnalyzer
from pace_analyzer.beat_detector import BeatDetector


def main():
    parser = argparse.ArgumentParser(description="Cut Optimization Suggestions")
    parser.add_argument("--transcript", "-t", type=str, help="Path to transcript file")
    parser.add_argument("--audio", "-a", type=str, default=None, help="Optional audio file for beat analysis")
    parser.add_argument("--data", type=str, help="Pre-computed speech analysis JSON (alternative to --transcript)")
    parser.add_argument("--beat-data", type=str, help="Pre-computed beat analysis JSON (alternative to --audio)")
    parser.add_argument("--output", "-o", type=str, default="cut_suggestions.json", help="Output JSON path")
    args = parser.parse_args()

    # Gather input data
    transcript_text = ""
    timing_data = []

    analysis_data = None
    if args.transcript:
        with open(args.transcript, "r", encoding="utf-8") as f:
            lines = [l.strip() for l in f.readlines()]
        transcript_text = "\n".join(l for l in lines if l.strip())
    elif args.data and Path(args.data).exists():
        with open(args.data, "r", encoding="utf-8") as f:
            analysis_data = json.load(f)
        # Extract timing from segments
        for seg in analysis_data.get("segments", []):
            if "start_ms" in seg and "end_ms" in seg and "text" in seg:
                timing_data.append({"start_ms": seg["start_ms"], "end_ms": seg["end_ms"], "text": seg["text"]})
        if timing_data and not transcript_text:
            transcript_text = "\n".join(seg["text"] for seg in timing_data if seg["text"])

    # Beat detection
    beat_drops = []
    if args.audio or (args.beat_data and Path(args.beat_data).exists()):
        try:
            detector = BeatDetector()
            if args.beat_data and Path(args.beat_data).exists():
                with open(args.beat_data, "r") as f:
                    beat_result = json.load(f)
                beat_drops = beat_result.get("drops", [])
            else:
                result = detector.analyze(args.audio)
                beat_drops = result.drops
        except Exception as e:
            print(f"Beat-Analyse fehlgeschlagen ({e}). Fortsetzung ohne Beat-Daten.", file=sys.stderr)

    # Run or load speech analysis
    analyzer = SpeechPaceAnalyzer()
    if analysis_data and "wpm" in analysis_data:
        wpm = float(analysis_data.get("wpm", 140))
        long_silence_ratio = float(analysis_data.get("long_silence_ratio", 0.1))
        avg_pause_ms = float(analysis_data.get("avg_pause_between_phrases_ms", 500))
        variance = float(analysis_data.get("pace_variance", 1.0))
        result = analyzer.analyze_with_timing(transcript_text, timing_data) if timing_data else analyzer.analyze(transcript_text)
    elif timing_data:
        result = analyzer.analyze_with_timing(transcript_text, timing_data)
        wpm = result.wpm
        long_silence_ratio = result.long_silence_ratio
        avg_pause_ms = result.avg_pause_between_phrases_ms
        variance = result.pace_variance
    else:
        result = analyzer.analyze(transcript_text)
        wpm = result.wpm
        long_silence_ratio = result.long_silence_ratio
        avg_pause_ms = result.avg_pause_between_phrases_ms
        variance = result.pace_variance

    # Generate optimization suggestions
    from pace_analyzer.pacing_models import PacingOptimizer, OptimizationSuggestion

    all_suggestions = PacingOptimizer.generate_full_suggestions(
        wpm=wpm,
        long_silence_ratio=long_silence_ratio,
        avg_pause_ms=avg_pause_ms,
        variance=variance,
        drops=beat_drops[:20],  # Use top 20 drop points for cut suggestions
    )

    # Add segment-level cut recommendations based on pace changes
    if len(result.segments) >= 3:
        segment_rates = [(s.start_ms, s.end_ms, s.avg_word_rate) for s in result.segments if s.avg_word_rate is not None]

        # Find pace transitions (segments where word rate changes significantly)
        cut_points = []
        for i in range(1, len(segment_rates)):
            prev_rate = segment_rates[i-1][2]
            curr_rate = segment_rates[i][2]
            if prev_rate > 0 and curr_rate > 0:
                rate_change = abs(curr_rate - prev_rate) / prev_rate * 100  # % change
                if rate_change > 30:  # Significant pace shift
                    cut_points.append({
                        "time_ms": int((segment_rates[i-1][0] + segment_rates[i][0]) / 2),
                        "description": f"Pace-Sprung: {prev_rate:.1f} → {curr_rate:.1f} words/s ({rate_change:.0f}% Änderung)",
                    })

        for cp in cut_points[:15]:  # Top 15 most important cuts
            all_suggestions.append(OptimizationSuggestion(
                severity="MEDIUM",
                category="pace_transition",
                description=cp["description"],
                recommended_action=f"Cut-Point setzen bei {cp['time_ms']/1000:.2f}s — deutlicher Rhythmuswechsel.",
                affected_segment_start_ms=cp["time_ms"],
            ))

    # Build output
    suggestion_dicts = [s.to_dict() if hasattr(s, "to_dict") else dict(s) for s in all_suggestions]
    cut_points = [d for d in suggestion_dicts if d.get("affected_segment_start_ms") is not None]
    optimization_actions = [d for d in suggestion_dicts if d.get("affected_segment_start_ms") is None]

    cuts_output = {
        "source_file": Path(args.transcript or args.data).name if (args.transcript or args.data) else "unknown",
        "speech_analysis": result.to_dict(),
        "beat_drops_analyzed": len(beat_drops),
        "total_suggestions": len(suggestion_dicts),
        "cut_points": cut_points,
        "optimization_actions": optimization_actions,
    }

    output_path = Path(args.output)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(cuts_output, f, indent=2, ensure_ascii=False)

    print(f"✓ Cut-Vorschläge gespeichert: {output_path}")
    print(f"\n--- Cut-Optimierung ---")
    print(f"WPM: {wpm:.1f} | Lange Stille: {long_silence_ratio * 100:.1f}% | Pausen: {avg_pause_ms:.0f}ms")

    # Print top cut points
    if cuts_output["cut_points"]:
        print(f"\nTop Cut-Points ({len(cuts_output['cut_points'])}):")
        for cp in sorted(cuts_output["cut_points"], key=lambda x: x.get("affected_segment_start_ms") or 0)[:10]:
            t = (cp.get("affected_segment_start_ms") or 0) / 1000.0
            desc = cp.get("description", "")[:60]
            print(f"  ✂️ {t:.2f}s — {desc}")

    # Print optimization actions
    if cuts_output["optimization_actions"]:
        print(f"\nOptimierungs-Aktionen ({len(cuts_output['optimization_actions'])}):")
        for action in sorted(cuts_output["optimization_actions"], key=lambda x: {"CRITICAL": 0, "HIGH": 1, "MEDIUM": 2, "LOW": 3}.get(x.get("severity", "LOW"), 4))[:5]:
            print(f"  📝 [{action['severity']}] {action['description']}")


if __name__ == "__main__":
    main()
