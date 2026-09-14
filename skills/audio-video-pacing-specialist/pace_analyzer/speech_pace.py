"""Speech Pacing Analysis — WPM, CPS, pause detection, pace segments."""

import json
from dataclasses import dataclass, field, asdict
from typing import Optional


@dataclass
class PaceSegment:
    """A time-ordered segment of speech with pacing characteristics."""
    start_ms: int = 0
    end_ms: int = 0
    text: str = ""
    word_count: int = 0
    char_count: float = 0.0
    pause_duration_ms: Optional[float] = None  # Duration of preceding silence
    avg_word_rate: Optional[float] = None      # words per second in this segment
    is_pause: bool = False                      # True if segment is non-speech

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class SpeechPaceResult:
    """Complete speech pacing analysis result."""
    total_duration_ms: int
    total_words: int
    total_chars: float
    wpm: float = 0.0              # Words Per Minute (overall)
    cps: float = 0.0              # Characters Per Second (overall)
    avg_pause_between_phrases_ms: float = 0.0
    long_silence_ratio: float = 0.0   # Fraction of total time >1s silence
    pace_variance: float = 0.0       # Std deviation of word rates across segments
    segments: list[PaceSegment] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "total_duration_ms": self.total_duration_ms,
            "total_words": self.total_words,
            "total_chars": round(self.total_chars, 1),
            "wpm": round(self.wpm, 1),
            "cps": round(self.cps, 2),
            "avg_pause_between_phrases_ms": round(self.avg_pause_between_phrases_ms, 1),
            "long_silence_ratio": round(self.long_silence_ratio, 3),
            "pace_variance": round(self.pace_variance, 2),
            "segments_count": len(self.segments),
        }


class SpeechPaceAnalyzer:
    """
    Analyzes speech pacing from a transcript (with optional audio timing).

    Usage:
        analyzer = SpeechPaceAnalyzer()
        result = analyzer.analyze(transcript)
        print(result.wpm, result.cps)
    """

    # Thresholds for pace scoring
    WPM_OPTIMAL_MIN = 120
    WPM_OPTIMAL_MAX = 180
    CPS_OPTIMAL_MIN = 4.0
    CPS_OPTIMAL_MAX = 9.0
    LONG_SILENCE_THRESHOLD_SEC = 1.0
    IDEAL_AVG_PAUSE_MS = 500

    def __init__(self):
        self.segments: list[PaceSegment] = []
        self.result: Optional[SpeechPaceResult] = None

    def analyze(self, transcript: str) -> SpeechPaceResult:
        """
        Analyze a full transcript for pacing metrics.

        Args:
            transcript: Plain text transcript (speaker labels stripped).
                       Lines ending with "..." or ", ...," indicate pauses.
                       Speaker names on their own lines are ignored.

        Returns:
            SpeechPaceResult with WPM, CPS, pause stats, and segments.
        """
        self.segments = []
        words = transcript.split()
        total_chars = len(transcript.replace(" ", "").replace("\n", ""))
        total_words = len(words) if words else 0

        # Detect phrase boundaries (natural pauses marked by punctuation)
        phrases = self._split_phrases(transcript, words)
        if not phrases:
            return SpeechPaceResult(
                total_duration_ms=0, total_words=total_words,
                total_chars=float(total_chars), wpm=0.0, cps=0.0
            )

        # Estimate total duration from speaking rate (iterative refinement)
        est_wpm = self._estimate_initial_wpm(words)
        estimated_duration_ms = int((estimated_duration_ms := (total_words / est_wpm)) * 60000) if est_wpm > 0 else 0

        # Build segments from phrase boundaries
        current_phrase_start = 0
        for i, end_idx in enumerate(phrases):
            phrase_text = " ".join(words[current_phrase_start:end_idx + 1])
            segment_words = len(phrase_text.split()) if phrase_text.strip() else 0
            duration_ms = int((segment_words / est_wpm) * 60000) if est_wpm > 0 and segment_words > 0 else 1

            avg_word_rate = (segment_words / (duration_ms / 1000)) if duration_ms >= 200 else None
            pause_dur = estimated_duration_ms - sum(
                int((len(words[j:end_idx+1]) / est_wpm) * 60000) if est_wpm > 0 and len(words[j:end_idx+1]) > 0 else 0
                for j in range(current_phrase_start, end_idx + 1)
            )

            seg = PaceSegment(
                start_ms=current_phrase_start * 33,  # ~1 phrase per 33ms proxy
                end_ms=duration_ms,
                text=phrase_text.strip(),
                word_count=segment_words,
                char_count=len(phrase_text.replace(" ", "")),
                avg_word_rate=avg_word_rate,
            )
            self.segments.append(seg)

            current_phrase_start = end_idx + 1

        # Calculate aggregate metrics
        total_duration_ms = estimated_duration_ms if est_wpm > 0 else max(1, int(total_words * 250))  # ~4 chars/s fallback
        wpm = (total_words / (total_duration_ms / 60000)) if total_duration_ms > 0 and total_words > 0 else 0.0
        cps = (total_chars / (total_duration_ms / 1000)) if total_duration_ms > 0 and total_chars > 0 else 0.0

        # Estimate pause metrics from punctuation density
        avg_pause = self._estimate_avg_pause(transcript, words)
        long_silence_ratio = self._estimate_long_silence_ratio(words, total_duration_ms)
        pace_variance = self._calculate_pace_variance(
            [s.avg_word_rate for s in self.segments if s.avg_word_rate is not None]
        )

        self.result = SpeechPaceResult(
            total_duration_ms=total_duration_ms,
            total_words=int(total_words),
            total_chars=float(total_chars),
            wpm=wpm,
            cps=cps,
            avg_pause_between_phrases_ms=avg_pause,
            long_silence_ratio=long_silence_ratio,
            pace_variance=pace_variance,
            segments=self.segments,
        )

        return self.result

    def analyze_with_timing(self, transcript: str, timing_data: list[dict]) -> SpeechPaceResult:
        """
        Analyze with explicit audio timing per line.

        Args:
            transcript: Full text including speaker labels.
            timing_data: List of dicts with keys: start_ms, end_ms, text.

        Returns:
            Enhanced SpeechPaceResult with accurate timing.
        """
        self.segments = []
        lines = [l.strip() for l in transcript.split("\n") if l.strip()]

        # Clean up speaker labels from lines
        cleaned_lines = []
        for line in lines:
            if ":" in line and not line.startswith(":"):
                parts = line.split(":", 1)
                text = parts[1].strip()
                cleaned_lines.append(text)
            elif "|" in line:
                # Speaker | text format (SRT-ish)
                text = line.split("|", 1)[1].strip() if len(line.split("|")) > 1 else line.strip()
                cleaned_lines.append(text)
            else:
                cleaned_lines.append(line)

        total_words = sum(len(t.split()) for t in cleaned_lines)
        total_chars = sum(len(t.replace(" ", "")) for t in cleaned_lines if t.strip())

        # Use explicit timing if available, otherwise estimate
        if timing_data:
            timed_segments = []
            for td in timing_data:
                text = td.get("text", "").strip()
                duration_ms = td["end_ms"] - td["start_ms"]
                words_in_seg = len(text.split()) if text.strip() else 0
                char_count = float(len(text.replace(" ", "")))

                seg = PaceSegment(
                    start_ms=td["start_ms"],
                    end_ms=td["end_ms"],
                    text=text,
                    word_count=words_in_seg,
                    char_count=char_count,
                    avg_word_rate=(words_in_seg / (duration_ms / 1000)) if duration_ms >= 200 else None,
                )
                timed_segments.append(seg)

            self.segments = timed_segments
            total_duration_ms = int(timing_data[-1]["end_ms"]) if timing_data else max(1, int(total_words * 250))
        else:
            est_wpm = self._estimate_initial_wpm(cleaned_lines)
            total_duration_ms = int((total_words / est_wpm) * 60000) if est_wpm > 0 and total_words > 0 else max(1, int(total_words * 250))

        wpm = (total_words / (total_duration_ms / 60000)) if total_duration_ms > 0 and total_words > 0 else 0.0
        cps = (total_chars / (total_duration_ms / 1000)) if total_duration_ms > 0 and total_chars > 0 else 0.0

        avg_pause = self._estimate_avg_pause(transcript, cleaned_lines)
        long_silence_ratio = self._estimate_long_silence_ratio(cleaned_lines, total_duration_ms)
        pace_variance = self._calculate_pace_variance(
            [s.avg_word_rate for s in self.segments if s.avg_word_rate is not None]
        )

        self.result = SpeechPaceResult(
            total_duration_ms=total_duration_ms,
            total_words=int(total_words),
            total_chars=float(total_chars),
            wpm=wpm,
            cps=cps,
            avg_pause_between_phrases_ms=avg_pause,
            long_silence_ratio=long_silence_ratio,
            pace_variance=pace_variance,
            segments=self.segments,
        )

        return self.result

    def get_pace_score(self) -> float:
        """Calculate a 0-100 engagement pacing score."""
        if not self.result or not self.segments:
            return 50.0  # Neutral default

        score = 100.0

        # WPM scoring (bell curve, optimal ~140)
        wpm = self.result.wpm
        if 120 <= wpm <= 180:
            wpm_score = 95 - abs(wpm - 140) * 0.3
        elif 100 <= wpm < 120 or 180 < wpm <= 200:
            wpm_score = max(60, min(90, 70 + (wpm - 100 if wpm >= 100 else 120 - wpm) * 3))
        elif wpm > 200:
            wpm_score = max(40, 80 - (wpm - 200) * 5)
        else:
            wpm_score = max(30, 90 - (120 - wpm) * 6)

        # Long silence ratio scoring
        ls_ratio = self.result.long_silence_ratio
        if ls_ratio <= 0.15:
            silence_score = 95
        elif ls_ratio <= 0.30:
            silence_score = max(70, 95 - (ls_ratio - 0.15) * 40)
        else:
            silence_score = max(40, 70 - (ls_ratio - 0.30) * 60)

        # Pause consistency scoring
        if self.result.avg_pause_between_phrases_ms > 0:
            avg_pause = self.result.avg_pause_between_phrases_ms / 1000.0  # convert to seconds
            if 0.2 <= avg_pause <= 0.8:
                pause_score = 90
            elif 0.05 <= avg_pause < 0.2 or 0.8 < avg_pause <= 1.5:
                pause_score = max(60, min(85, 75 + (avg_pause - 0.2) * 40 if avg_pause < 0.5 else 30 - (avg_pause - 1.0) * 40))
            else:
                pause_score = max(40, 60 - abs(avg_pause - 0.5) * 80)
        else:
            pause_score = 70

        # Pace variance scoring
        pv = self.result.pace_variance
        if pv <= 1.0:
            variance_score = 90
        elif pv <= 3.0:
            variance_score = max(65, min(88, 85 - (pv - 1) * 7))
        else:
            variance_score = max(40, 65 - (pv - 3) * 20)

        # Weighted composite
        score = (wpm_score * 0.35 + silence_score * 0.30 + pause_score * 0.15 + variance_score * 0.20)

        return round(max(0, min(100, score)), 1)

    def get_pace_tier(self) -> str:
        """Get a human-readable pacing tier."""
        score = self.get_pace_score()
        if score >= 80:
            return "OPTIMAL — Kein Pacing-Probleme"
        elif score >= 65:
            return "GUT — Nur leichte Optimierung nötig"
        elif score >= 45:
            return "MITTLERLICH — Bedarf an Pacing-Anpassung"
        else:
            return "KRIITISCH — Radikale Überarbeitung nötig"

    # --- Helper Methods ---

    def _estimate_initial_wpm(self, words: list[str]) -> float:
        """Estimate initial speaking rate from punctuation density."""
        text = "".join(words)
        if not text.strip():
            return 140.0  # Default assumption

        # Count sentence-ending punctuation as pause indicators
        sentences = [s.strip() for s in text.split(".") if s.strip()]
        sentences += [s.strip() for s in text.split("!", 1) if len(s.split("!")) > 1]
        sentences += [s.strip() for s in text.split("?", 1) if len(s.split("?")) > 1]

        avg_sentence_words = sum(len(s.split()) for s in sentences) / max(1, len(sentences))
        # Longer average sentences suggest faster speech or denser content
        base_wpm = 4.0 * (avg_sentence_words + 5) if words else 140.0

        # Adjust based on punctuation density (more commas = slower cadence)
        comma_ratio = text.count(",") / max(1, len(words))
        adjustment = -comma_ratio * 20

        return round(max(80, base_wpm + adjustment), 1)

    def _split_phrases(self, transcript: str, words: list[str]) -> list[int]:
        """Split text into phrase boundaries based on punctuation."""
        phrases = []
        for i, word in enumerate(words):
            clean_w = word.rstrip("\"')]}»›")
            if (
                clean_w.endswith("...")
                or clean_w.endswith(".")
                or clean_w.endswith("!")
                or clean_w.endswith("?")
                or clean_w.endswith(";")
                or clean_w.endswith(":")
            ):
                phrases.append(i)

        if not phrases and words:
            phrases.append(len(words) - 1)

        return phrases

    def _estimate_avg_pause(self, transcript: str, words: list[str]) -> float:
        """Estimate average pause duration between phrases."""
        if len(words) < 3 or not transcript.strip():
            return 500.0  # Default ~500ms

        text = "".join(words)
        sentence_count = max(1, text.count(".") + text.count("!") + text.count("?"))
        avg_sentence_words = sum(len(s.split()) for s in text.split(".")) / max(1, len(text.split(".")))

        # Typical pause duration per sentence boundary
        base_pause_ms = 400 * (avg_sentence_words / 15.0)  # Scale with content density

        return round(base_pause_ms + (text.count(",") / max(1, sentence_count)) * 300, 1)

    def _estimate_long_silence_ratio(self, lines: list[str], total_duration_ms: int) -> float:
        """Estimate the fraction of time in long silences (>1s)."""
        if not lines or len(lines) < 2:
            return 0.05  # Small default

        text = "\n".join(l for l in lines if l.strip())
        sentence_count = max(1, text.count(".") + text.count("!") + text.count("?"))
        avg_words_per_sentence = sum(len(s.split()) for s in text.split(".")) / sentence_count

        # Estimate: if there are many sentences, long silences are less likely
        silence_ratio = 0.5 * (1.0 - min(1.0, sentence_count / max(20, sentence_count)))
        return round(max(0.0, min(0.9, silence_ratio)), 3)

    def _calculate_pace_variance(self, rates: list[float]) -> float:
        """Calculate standard deviation of word rates."""
        if len(rates) < 2:
            return 0.0
        mean = sum(rates) / len(rates)
        variance = sum((r - mean) ** 2 for r in rates) / len(rates)
        import math
        return round(math.sqrt(variance), 4)
