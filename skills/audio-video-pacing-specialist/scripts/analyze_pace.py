"""CLI: Speech Pacing Analyzer

Usage:
    python analyze_pace.py --transcript transcript.txt [--audio audio.wav] [--output report.json]
    python analyze_pace.py --text "Some spoken text here..." [--output report.json]
"""

import argparse
import json
import sys
from pathlib import Path

# Add parent to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from pace_analyzer.speech_pace import SpeechPaceAnalyzer


def main():
    parser = argparse.ArgumentParser(description="Speech Pacing Analyzer")
    parser.add_argument("--transcript", "-t", type=str, help="Path to transcript file (plain text with speaker labels)")
    parser.add_argument("--text", type=str, help="Direct speech text to analyze")
    parser.add_argument("--audio", "-a", type=str, default=None, help="Optional audio file for timing data")
    parser.add_argument("--output", "-o", type=str, default="pace_analysis.json", help="Output JSON path")
    args = parser.parse_args()

    if not (args.transcript or args.text):
        print("Fehler: --transcript oder --text ist erforderlich.", file=sys.stderr)
        sys.exit(1)

    # Load transcript
    lines = []
    if args.transcript:
        path = Path(args.transcript)
        if not path.exists():
            print(f"Fehler: Datei nicht gefunden: {path}", file=sys.stderr)
            sys.exit(1)
        with open(path, "r", encoding="utf-8") as f:
            lines = [l.strip() for l in f.readlines()]
    elif args.text:
        lines = [l.strip() for l in args.text.split("\n")]

    transcript_text = "\n".join(l for l in lines if l.strip())

    # Load timing data from audio (basic: estimate without pydub)
    timing_data = None
    if args.audio and Path(args.audio).exists():
        try:
            import pydub
            audio = pydub.AudioSegment.from_file(args.audio)
            sample_rate = getattr(audio, "frame_rate", getattr(audio, "sample_rate", 44100))

            chunk_ms = 50
            rms_frames = [float(audio[i:i + chunk_ms].rms) for i in range(0, len(audio), chunk_ms)]
            max_rms = max(rms_frames) if rms_frames else 1.0
            norm_rms = [r / (max_rms + 1e-6) for r in rms_frames]

            timestamps_ms = []
            for i, r in enumerate(norm_rms):
                if r < 0.05:  # Quiet = likely pause
                    timestamps_ms.append(i * chunk_ms)

            timing_data = [
                {"start_ms": ts, "end_ms": ts + chunk_ms * 4, "text": ""}
                for ts in timestamps_ms[:len(lines)]
            ] if timestamps_ms else None

        except ImportError:
            print("Hinweis: pydub nicht installiert. Timing wird aus Text geschätzt.", file=sys.stderr)
        except Exception as e:
            print(f"Audio-Analyse fehlgeschlagen ({e}). Verwende Text-Nachbetrachtung.", file=sys.stderr)

    # Run analysis
    analyzer = SpeechPaceAnalyzer()

    if timing_data and len(timing_data) == len(lines):
        result = analyzer.analyze_with_timing(transcript_text, timing_data)
    else:
        result = analyzer.analyze(transcript_text)

    # Output
    output_path = Path(args.output)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(result.to_dict(), f, indent=2, ensure_ascii=False)

    print(f"✓ Analyse gespeichert: {output_path}")
    print(f"\n--- Pacing-Zusammenfassung ---")
    print(f"Dauer:         {result.total_duration_ms / 1000:.1f}s")
    print(f"Wörter gesamt: {result.total_words:,}")
    print(f"WPM:           {result.wpm:.1f} {'✅ optimal' if 120 <= result.wpm <= 180 else '⚠️ außerhalb optimalen Bereichs'}")
    print(f"CPS:           {result.cps:.2f}")
    print(f"Durchschnittspause: {result.avg_pause_between_phrases_ms:.0f}ms")
    print(f"Lange Stille (>1s): {result.long_silence_ratio * 100:.1f}%{' ⚠️' if result.long_silence_ratio > 0.3 else ''}")
    print(f"Pace-Variance: {result.pace_variance:.2f}")

    score = analyzer.get_pace_score()
    tier = analyzer.get_pace_tier()
    print(f"\nPacing-Score:  {score}/100 [{tier}]")


if __name__ == "__main__":
    main()
