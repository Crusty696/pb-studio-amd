"""CLI: Comprehensive Pacing Report Generator

Usage:
    python pace_report.py --data analysis.json [--visualize] [--output report.html]
    python pace_report.py --speech data.json --beat beat_data.json [--score-only]
"""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))


def generate_score_summary(score_dict):
    """Generate a human-readable score summary."""
    lines = []
    if not score_dict:
        return "Keine Pacing-Daten verfügbar."

    score = score_dict.get("overall_score", 50)
    tier = score_dict.get("tier", "?")
    lines.append(f"**Gesamtscore: {score}/100** [{tier}]")
    lines.append("")
    lines.append("| Komponente | Score | Status |")
    lines.append("|-----------|-------|--------|")

    wpm = score_dict.get("wpm_score", 70)
    if wpm >= 80: lines.append(f"| WPM       | {wpm}  | ✅ Gut |")
    elif wpm >= 60: lines.append(f"| WPM       | {wpm}  | ⚠️ Mittel |")
    else: lines.append(f"| WPM       | {wpm}  | ❌ Zu langsam/schnell |")

    silence = score_dict.get("silence_score", 70)
    if silence >= 80: lines.append(f"| Stille    | {silence}| ✅ Gut |")
    elif silence >= 60: lines.append(f"| Stille    | {silence}| ⚠️ Mittel |")
    else: lines.append(f"| Stille    | {silence}| ❌ Viel Stille |")

    pause = score_dict.get("pause_score", 70)
    if pause >= 80: lines.append(f"| Pausen    | {pause} | ✅ Gut |")
    elif pause >= 60: lines.append(f"| Pausen    | {pause} | ⚠️ Mittel |")
    else: lines.append(f"| Pausen    | {pause} | ❌ Inkonsistent |")

    variance = score_dict.get("variance_score", 70)
    if variance >= 80: lines.append(f"| Variance  | {variance}| ✅ Gut |")
    elif variance >= 60: lines.append(f"| Variance  | {variance}| ⚠️ Mittel |")
    else: lines.append(f"| Variance  | {variance}| ❌ Stark variabel |")

    beat_sync = score_dict.get("beat_sync_score", None)
    if beat_sync is not None and beat_sync >= 80:
        lines.append(f"| Beat-Sync | {beat_sync} | ✅ Sync |")
    elif beat_sync is not None and beat_sync >= 60:
        lines.append(f"| Beat-Sync | {beat_sync} | ⚠️ Mittel |")

    return "\n".join(lines)


def generate_suggestions_summary(suggestions):
    """Summarize optimization suggestions by severity."""
    if not suggestions:
        return "Keine Optimierungsvorschläge."

    counts = {}
    for s in suggestions:
        sev = s.get("severity", "UNKNOWN")
        counts[sev] = counts.get(sev, 0) + 1

    lines = [f"**{len(suggestions)} Vorschläge**:\n"]
    for sev in ["CRITICAL", "HIGH", "MEDIUM", "LOW"]:
        if sev in counts:
            lines.append(f"- {counts[sev]}x {sev}:")
            for s in suggestions:
                if s["severity"] == sev:
                    lines.append(f"  • [{s['category']}] {s['description']}")
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description="Pacing Report Generator")
    parser.add_argument("--data", "-d", type=str, help="Path to analysis JSON file")
    parser.add_argument("--score-only", action="store_true", help="Only output score summary (JSON)")
    args = parser.parse_args()

    if not args.data:
        print("Fehler: --data ist erforderlich.", file=sys.stderr)
        sys.exit(1)

    path = Path(args.data)
    if not path.exists():
        print(f"Fehler: Datei nicht gefunden: {path}", file=sys.stderr)
        sys.exit(1)

    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)

    # Normalize input data structure
    target_data = data.get("speech_analysis", data)
    score_data = target_data.get("score")

    if not score_data and "overall_score" in target_data:
        score_data = target_data
    elif not score_data and "wpm" in target_data:
        wpm = float(target_data.get("wpm", 140))
        silence = float(target_data.get("long_silence_ratio", 0.1))
        pause = float(target_data.get("avg_pause_between_phrases_ms", 500))
        variance = float(target_data.get("pace_variance", 1.0))
        from pace_analyzer.pacing_models import PacingOptimizer
        score_obj = PacingOptimizer.calculate_score(wpm=wpm, long_silence_ratio=silence, avg_pause_ms=pause, variance=variance)
        score_data = score_obj.to_dict()

    if score_data:
        print(f"# Pacing Report\n")
        print(generate_score_summary(score_data))

        if not args.score_only:
            suggestions = target_data.get("suggestions") or target_data.get("optimization_actions")
            if not suggestions and "wpm" in target_data:
                from pace_analyzer.pacing_models import PacingOptimizer
                s_objs = PacingOptimizer.generate_full_suggestions(
                    wpm=float(target_data.get("wpm", 140)),
                    long_silence_ratio=float(target_data.get("long_silence_ratio", 0.1)),
                    avg_pause_ms=float(target_data.get("avg_pause_between_phrases_ms", 500)),
                    variance=float(target_data.get("pace_variance", 1.0)),
                )
                suggestions = [s.to_dict() for s in s_objs]
            if suggestions:
                print("\n" + generate_suggestions_summary(suggestions))

        beat_data = data.get("beat_metrics")
        if beat_data:
            bpm = beat_data.get("bpm_global", "?")
            print(f"\n## Beat-Daten\n")
            print(f"- BPM: {bpm}")
    else:
        print("# Pacing-Analyse")
        for k, v in target_data.items():
            if not isinstance(v, (list, dict)):
                print(f"- **{k}**: {v}")

    if args.score_only and score_data:
        json.dump(score_data, sys.stdout, indent=2, ensure_ascii=False)


if __name__ == "__main__":
    main()
