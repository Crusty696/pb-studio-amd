"""Pacing Models — Scoring, report generation, optimization suggestions."""

import json
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class PacingScore:
    """Composite pacing score with breakdown."""
    overall_score: float = 50.0       # 0-100 engagement score
    wpm_score: float = 70.0           # Words-per-minute component
    silence_score: float = 70.0       # Silence ratio component
    pause_score: float = 70.0         # Pause consistency component
    variance_score: float = 70.0      # Pace variance component
    beat_sync_score: float = 50.0     # Beat synchronization score (if audio analyzed)
    tier: str = "MITTLERLICH"

    def to_dict(self) -> dict:
        return {
            "overall_score": round(self.overall_score, 1),
            "wpm_score": round(self.wpm_score, 1),
            "silence_score": round(self.silence_score, 1),
            "pause_score": round(self.pause_score, 1),
            "variance_score": round(self.variance_score, 1),
            "beat_sync_score": round(self.beat_sync_score, 1),
            "tier": self.tier,
        }


@dataclass
class OptimizationSuggestion:
    """A specific pacing optimization recommendation."""
    severity: str = "LOW"      # LOW | MEDIUM | HIGH | CRITICAL
    category: str = "general"  # wpm, silence, pause, variance, beat_sync
    description: str = ""
    recommended_action: str = ""
    affected_segment_start_ms: Optional[int] = None
    affected_segment_end_ms: Optional[int] = None
    current_value: Optional[float] = None
    target_value: Optional[float] = None

    def to_dict(self) -> dict:
        return {
            "severity": self.severity,
            "category": self.category,
            "description": self.description,
            "recommended_action": self.recommended_action,
            "affected_segment_start_ms": self.affected_segment_start_ms,
            "affected_segment_end_ms": self.affected_segment_end_ms,
            "current_value": self.current_value,
            "target_value": self.target_value,
        }


@dataclass
class PacingReport:
    """Complete pacing analysis report combining speech and beat data."""
    score: Optional[PacingScore] = None
    speech_metrics: dict = field(default_factory=dict)
    beat_metrics: Optional[dict] = None
    suggestions: list[OptimizationSuggestion] = field(default_factory=list)
    summary_text: str = ""

    def to_dict(self) -> dict:
        return {
            "score": self.score.to_dict() if self.score else None,
            "speech_metrics": self.speech_metrics,
            "beat_metrics": self.beat_metrics,
            "suggestions_count": len(self.suggestions),
            "summary_text": self.summary_text,
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2, ensure_ascii=False)


class PacingOptimizer:
    """Generates optimization suggestions based on pacing analysis results."""

    @staticmethod
    def calculate_score(
        wpm: float,
        long_silence_ratio: float,
        avg_pause_ms: float,
        variance: float,
        beat_sync_score: float = 50.0,
    ) -> PacingScore:
        """Calculate composite PacingScore from speech and audio metrics."""
        if 120 <= wpm <= 180:
            wpm_score = 95.0 - abs(wpm - 140.0) * 0.3
        elif 100 <= wpm < 120 or 180 < wpm <= 200:
            wpm_score = max(60.0, min(90.0, 70.0 + (wpm - 100.0 if wpm >= 100 else 120.0 - wpm) * 3.0))
        elif wpm > 200:
            wpm_score = max(40.0, 80.0 - (wpm - 200.0) * 5.0)
        else:
            wpm_score = max(30.0, 90.0 - (120.0 - wpm) * 6.0)

        if long_silence_ratio <= 0.15:
            silence_score = 95.0
        elif long_silence_ratio <= 0.30:
            silence_score = max(70.0, 95.0 - (long_silence_ratio - 0.15) * 40.0)
        else:
            silence_score = max(40.0, 70.0 - (long_silence_ratio - 0.30) * 60.0)

        avg_pause_s = avg_pause_ms / 1000.0
        if 0.2 <= avg_pause_s <= 0.8:
            pause_score = 90.0
        elif 0.05 <= avg_pause_s < 0.2 or 0.8 < avg_pause_s <= 1.5:
            pause_score = max(60.0, min(85.0, 75.0 + (avg_pause_s - 0.2) * 40.0 if avg_pause_s < 0.5 else 30.0 - (avg_pause_s - 1.0) * 40.0))
        else:
            pause_score = max(40.0, 60.0 - abs(avg_pause_s - 0.5) * 80.0)

        if variance <= 1.0:
            variance_score = 90.0
        elif variance <= 3.0:
            variance_score = max(65.0, min(88.0, 85.0 - (variance - 1.0) * 7.0))
        else:
            variance_score = max(40.0, 65.0 - (variance - 3.0) * 20.0)

        overall = wpm_score * 0.35 + silence_score * 0.30 + pause_score * 0.15 + variance_score * 0.20
        overall = round(max(0.0, min(100.0, overall)), 1)
        tier = "OPTIMAL" if overall >= 80 else ("GUT" if overall >= 65 else ("MITTLERLICH" if overall >= 45 else "KRITISCH"))

        return PacingScore(
            overall_score=overall,
            wpm_score=round(wpm_score, 1),
            silence_score=round(silence_score, 1),
            pause_score=round(pause_score, 1),
            variance_score=round(variance_score, 1),
            beat_sync_score=round(beat_sync_score, 1),
            tier=tier,
        )

    @staticmethod
    def suggest_wpm_adjustments(wpm: float) -> list[OptimizationSuggestion]:
        """Suggest WPM adjustments if out of optimal range."""
        suggestions = []

        if wpm > 180:
            target = min(165, max(140, wpm - 20))
            suggestions.append(OptimizationSuggestion(
                severity="HIGH" if wpm > 200 else "MEDIUM",
                category="wpm",
                description=f"Sprechrate {wpm:.0f} WPM ist deutlich zu schnell — Zuhörer haben keine Zeit zum Verarbeiten.",
                recommended_action="Schnittstellen hinzufügen oder Sätze verkürzen. Ziel: ~140-165 WPM.",
                current_value=wpm,
                target_value=target,
            ))

        elif wpm < 120:
            target = min(135, max(130, wpm + 15))
            suggestions.append(OptimizationSuggestion(
                severity="MEDIUM" if wpm > 90 else "HIGH",
                category="wpm",
                description=f"Sprechrate {wpm:.0f} WPM ist zu langsam — Gefahr des Aussteigens.",
                recommended_action="Tempo erhöhen oder Cut-Points nach ruhigen Passagen setzen. Ziel: ~130-150 WPM.",
                current_value=wpm,
                target_value=target,
            ))

        return suggestions

    @staticmethod
    def suggest_silence_adjustments(long_silence_ratio: float) -> list[OptimizationSuggestion]:
        """Suggest silence removal if long silences exceed threshold."""
        suggestions = []

        if long_silence_ratio > 0.50:
            suggestions.append(OptimizationSuggestion(
                severity="CRITICAL",
                category="silence",
                description=f"Über {long_silence_ratio * 100:.0f}% der Dauer sind lange Stille (>1s). Extrem langweilig.",
                recommended_action="Alle Stille >500ms entfernen. B-Clip Inserts oder Musik unterlegen.",
            ))

        elif long_silence_ratio > 0.30:
            suggestions.append(OptimizationSuggestion(
                severity="HIGH",
                category="silence",
                description=f"{long_silence_ratio * 100:.0f}% der Dauer sind lange Stille.",
                recommended_action="Stille >1s entfernen oder mit B-Roll/Unterhaltung füllen. Ziel: <20%.",
                current_value=long_silence_ratio,
                target_value=0.20,
            ))

        elif long_silence_ratio > 0.15:
            suggestions.append(OptimizationSuggestion(
                severity="MEDIUM",
                category="silience",
                description=f"{long_silence_ratio * 100:.0f}% der Dauer sind lange Stille.",
                recommended_action="Stille >800ms mit Musik-Unterlegung füllen oder als Dramaturgie nutzen.",
            ))

        return suggestions

    @staticmethod
    def suggest_pause_adjustments(avg_pause_ms: float) -> list[OptimizationSuggestion]:
        """Suggest pause adjustments."""
        suggestions = []

        if avg_pause_ms > 1200:
            target = max(500, avg_pause_ms - 400)
            suggestions.append(OptimizationSuggestion(
                severity="MEDIUM",
                category="pause",
                description=f"Durchschnittliche Pause {avg_pause_ms:.0f}ms ist zu lang — Fluss bricht auf.",
                recommended_action="Sätze verbinden oder Cut-Points setzen. Ziel: <600ms.",
                current_value=avg_pause_ms,
                target_value=target,
            ))

        elif avg_pause_ms > 800:
            suggestions.append(OptimizationSuggestion(
                severity="LOW",
                category="pause",
                description=f"Pausen ({avg_pause_ms:.0f}ms) sind länger als optimal.",
                recommended_action="Überprüfen ob Pausen dramaturgisch nötig, sonst kürzen.",
            ))

        elif avg_pause_ms < 200:
            suggestions.append(OptimizationSuggestion(
                severity="LOW",
                category="pause",
                description=f"Pausen ({avg_pause_ms:.0f}ms) sind sehr kurz — zu schnell.",
                recommended_action="Natürliche Atempunkte nutzen für Cut-Points. Ziel: 300-500ms.",
            ))

        return suggestions

    @staticmethod
    def suggest_variance_adjustments(variance: float, max_acceptable: float = 2.5) -> list[OptimizationSuggestion]:
        """Suggest pace consistency adjustments."""
        suggestions = []

        if variance > max_acceptable * 3:
            suggestions.append(OptimizationSuggestion(
                severity="HIGH",
                category="variance",
                description=f"Pace-Variance {variance:.1f} ist extrem — unvorhersehbare Rhythmik.",
                recommended_action="Pacing-Regel definieren und strikt einhalten. Slow-Motion für Highlights.",
            ))
        elif variance > max_acceptable:
            suggestions.append(OptimizationSuggestion(
                severity="MEDIUM",
                category="variance",
                description=f"Pace-Variance {variance:.1f} deutet auf inkonsistentes Tempo hin.",
                recommended_action="Zeitlupen für emotionale Momente einplanen. Schnitte auf Beat-Spitzen setzen.",
            ))

        return suggestions

    @staticmethod
    def suggest_beat_sync(drops: list[dict]) -> list[OptimizationSuggestion]:
        """Suggest cut points based on detected beats/drops."""
        if not drops:
            return []

        suggestions = [OptimizationSuggestion(
            severity="MEDIUM",
            category="beat_sync",
            description=f"{len(drops)} Energie-Spikes erkannt — ideale Cut-Points für Video.",
            recommended_action="Videoschnitte auf diese Spikes setzen. Für Musikvideos: Beat-aligned cuts.",
        )]

        # Check if drops are well-spaced (good for regular cutting)
        if len(drops) >= 2:
            intervals = [drops[i]["time_ms"] - drops[i-1]["time_ms"]
                        for i in range(1, len(drops))]
            avg_interval = sum(intervals) / len(intervals)
            spread = max(intervals) - min(intervals) if len(intervals) > 1 else 0

            if spread < avg_interval * 0.3:
                suggestions[0].recommended_action += " Regelmäßige Intervalle — gut für rhythmische Schnitte."
            elif spread < avg_interval * 0.7:
                suggestions[0].recommended_action += " Moderat regelmäßige Intervalle — Cut-Points anpassen."

        return suggestions

    @staticmethod
    def generate_full_suggestions(
        wpm: float,
        long_silence_ratio: float,
        avg_pause_ms: float,
        variance: float,
        drops: list[dict] | None = None,
    ) -> list[OptimizationSuggestion]:
        """Generate all optimization suggestions."""
        suggestions = []
        suggestions.extend(PacingOptimizer.suggest_wpm_adjustments(wpm))
        suggestions.extend(PacingOptimizer.suggest_silence_adjustments(long_silence_ratio))
        suggestions.extend(PacingOptimizer.suggest_pause_adjustments(avg_pause_ms))
        suggestions.extend(PacingOptimizer.suggest_variance_adjustments(variance))
        suggestions.extend(PacingOptimizer.suggest_beat_sync(drops or []))
        return suggestions
