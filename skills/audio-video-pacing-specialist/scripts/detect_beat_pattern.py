"""CLI: Beat Pattern & Tempo Detector

Usage:
    python detect_beat_pattern.py --input track.mp3 [--output report.json]
    python detect_beat_pattern.py --input audio.wav --output report.json
"""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from pace_analyzer.beat_detector import BeatDetector


def main():
    parser = argparse.ArgumentParser(description="Beat & Tempo Pattern Detector")
    parser.add_argument("--input", "-i", type=str, required=True, help="Audio file path (WAV/MP3/AAC)")
    parser.add_argument("--output", "-o", type=str, default="beat_report.json", help="Output JSON path")
    args = parser.parse_args()

    input_path = Path(args.input)
    if not input_path.exists():
        print(f"Fehler: Datei nicht gefunden: {input_path}", file=sys.stderr)
        sys.exit(1)

    detector = BeatDetector()
    result = detector.analyze(input_path)

    output_path = Path(args.output)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(result.to_dict(), f, indent=2, ensure_ascii=False)

    print(f"✓ Beat-Analyse gespeichert: {output_path}")
    print(f"\n--- Beat-Zusammenfassung ---")
    print(f"Dauer:              {result.duration_ms / 1000:.1f}s")
    print(f"Globales BPM:       {result.bpm_global}")
    print(f"BPM-Bereich:        {result.bpm_min} - {result.bpm_max}")
    print(f"Tempo-Änderungen:   {len(result.tempo_changes)}")
    if result.tempo_changes:
        for tc in result.tempo_changes[:5]:
            print(f"  → bei {tc['time_ms']/1000:.1f}s: {tc['from_bpm']:.0f} → {tc['to_bpm']:.0f} BPM")

    print(f"\nGenres (heuristic): {', '.join(result.dominant_genre_hints)}")
    print(f"Drop-Spikes erkannt: {len(result.drops)}")
    for drop in result.drops[:5]:
        print(f"  ✂️ Drop bei {drop['time_ms']/1000:.1f}s (Energie: {drop['energy_spike_db']:+.1f}dB, Conf: {drop['confidence']:.2f})")

    # Print beat grid for sync reference
    sample_bpm = result.bpm_global if result.bpm_global > 60 else 120
    print(f"\nBeat-Grid (BPM={sample_bpm}):")
    grid = detector.get_beat_grid(sample_bpm)
    for i, ts in enumerate(grid):
        marker = " 🎵" if i % 4 == 0 else ""
        print(f"  {ts/1000:.2f}s ({i+1:03d}){marker}")


if __name__ == "__main__":
    main()
