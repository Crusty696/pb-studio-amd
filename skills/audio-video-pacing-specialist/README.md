# Audio/Video Pacing Specialist 🎬🔊

Ein spezialisiertes Toolkit zur Analyse und Optimierung von **Audio- und Video-Pacing**.

## Was kann es?

| Funktion | Beschreibung |
|----------|-------------|
| 📊 **Speech-Pace-Analyse** | WPM, CPS, Pausen, Stille-Metriken aus Transkripten |
| 🥁 **Beat-Erkennung** | BPM-Detektion, Takt-Änderungen, Drop-Spikes |
| ✂️ **Cut-Optimierung** | Empfohlene Schnittpunkte basierend auf Audio-Pacing |
| ⚡ **Pacing Score** | 0-100 Engagement-Bewertung mit detailliertem Breakdown |
| 📈 **Optimierungsvorschläge** | Konkrete, priorisierte Empfehlungen pro Segment |

## Installation

```bash
pip install -r requirements.txt
# Für erweiterte Analyse:
pip install librosa pydub numpy
```

## Schnelleinstieg

### 1. Speech-Pace-Analyse

```bash
python scripts/analyze_pace.py --transcript talk_deutsch.txt --output pace.json
```

Für direkten Text-Eingabe:
```bash
python scripts/analyze_pace.py --text "Hallo, willkommen zu diesem Talk über Audio Pacing. Die meisten Creator unterschätzen das Tempo ihres Contents." --output quick.json
```

### 2. Beat- & Tempo-Analyse

```bash
python scripts/detect_beat_pattern.py --input track.mp3 --output beat_report.json
```

### 3. Combined Cut Optimization

```bash
python scripts/optimize_cuts.py --transcript talk_deutsch.txt --audio voiceover.wav --output cuts.json
```

### 4. Pacing Report aus bestehender Analyse

```bash
python scripts/pace_report.py --data pace_analysis.json
# Für kombinierte Analyse:
python scripts/pace_report.py --data analysis.json --beat beat_data.json --score-only
```

## Beispiel-Workflow für einen Podcast-Cut

```bash
# 1. Transkript parsen und Pace analysieren
python scripts/analyze_pace.py -t podcast_episode.txt -o episode_pace.json

# 2. Audio auf Beat-Muster prüfen (optional)
python scripts/detect_beat_pattern.py -i podcast_audio.wav -o beat_report.json

# 3. Cut-Optimierung mit beiden Daten
python scripts/optimize_cuts.py --data episode_pace.json --beat-data beat_report.json -o cuts.json

# 4. Score und Vorschläge anzeigen
python scripts/pace_report.py --data episode_pace.json
```

## Metriken im Detail

### Speech-Pacing
- **WPM** (Words Per Minute): Optimal 130–160 für Podcasts, 150+ für Talks
- **CPS** (Chars Per Second): Ideal 4.5–7.5 chars/s
- **Long Silence Ratio**: <20% ideal, >30% = Langeweile-Risiko
- **Pace Variance**: Niedriger = konsistentere Flow-Qualität

### Beat-Pacing
- **BPM-Detektion** mit Autokorrelation
- **Drop-Spike-Erkennung** für Cut-Points
- **Genre-Hint** basierend auf BPM-Bereich
- **Beat-Grid** als Referenz für Synchronisation

### Pacing Score (0–100)
| Bereich | Bedeutung |
|---------|-----------|
| 80+ | Optimal — kein Pacing-Probleme |
| 65–79 | Gut — leichte Optimierung nötig |
| 45–64 | Mittel — Pacing-Anpassung empfohlen |
| <45 | Kritisch — radikale Überarbeitung nötig |

## Python-Integration

```python
from pace_analyzer.speech_pace import SpeechPaceAnalyzer, PaceSegment
from pace_analyzer.beat_detector import BeatDetector
from pace_analyzer.pacing_models import PacingOptimizer, PacingScore

# Speech Analysis
analyzer = SpeechPaceAnalyzer()
result = analyzer.analyze("Willkommen zu diesem Talk über Audio Pacing...")
print(f"WPM: {result.wpm:.1f} | Score: {analyzer.get_pace_score()}")

# Beat Detection (mit pydub)
detector = BeatDetector()
beat_result = detector.analyze("track.mp3")
print(f"BPM: {beat_result.bpm_global}")

# Optimization Suggestions
suggestions = PacingOptimizer.generate_full_suggestions(
    wpm=result.wpm,
    long_silence_ratio=result.long_silence_ratio,
)
```

## Projektstruktur

```
audio-video-pacing-specialist/
├── SKILL.md                          # Skill-Dokumentation für Bionic
├── README.md                         # Dieses File
├── pace_analyzer/                    # Core Python-Bibliothek
│   ├── __init__.py
│   ├── speech_pace.py               # WPM, CPS, Pause-Analyse
│   ├── beat_detector.py             # BPM & Takt-Erkennung
│   └── pacing_models.py             # Scoring & Optimierung
├── scripts/                          # CLI-Tools
│   ├── analyze_pace.py              # Speech-Pace Analyzer
│   ├── detect_beat_pattern.py       # Beat Detector
│   ├── pace_report.py               # Report Generator
│   └── optimize_cuts.py             # Cut Optimization
├── examples/                         # Beispiel-Daten
│   └── example_transcript.json      # Demo-Transkript
└── requirements.txt                  # Abhängigkeiten
```

## Lizenz

MIT — frei für alle Projekte nutzbar.
