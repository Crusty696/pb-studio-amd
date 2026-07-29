# 3-Band Waveform Analyzer Integration Guide

## Übersicht

Der neue **3-Band Waveform Analyzer** ermöglicht Rekordbox-Style Waveform-Visualisierung mit separaten Frequenzbändern (Bass, Mids, Highs).

## Module

### 1. `waveform_analyzer.py`

**Hauptklasse:** `WaveformAnalyzer`

Extrahiert Low/Mid/High Frequenzbänder aus Audio-Dateien mittels Butterworth-Bandpass-Filtern und berechnet RMS-Envelopes für Visualisierung.

**Frequenzbänder:**
- **Low (Bass):** 20-200 Hz
- **Mid (Midrange):** 200-2000 Hz
- **High (Treble):** 2000-20000 Hz

**Hauptmethoden:**

```python
# Volle 3-Band Extraktion
waveform = analyzer.extract_3band_waveform(audio_path, hop_length=512)
# Returns: {'low': np.array, 'mid': np.array, 'high': np.array}

# Downsampled für GUI (Performance)
waveform = analyzer.get_downsampled_waveform(audio_path, target_points=1000)
# Reduziert Datenpunkte auf Display-Auflösung

# Frequenz-Content Analyse
content = analyzer.analyze_frequency_content(audio_path)
# Returns: {'low_pct': 35.2, 'mid_pct': 52.1, 'high_pct': 12.7}
```

### 2. `waveform_cache.py`

**Hauptklasse:** `WaveformCache`

LRU-Cache für vorberechnete Waveform-Daten. Verhindert redundante Verarbeitung und beschleunigt UI-Ladezeiten.

**Features:**
- LRU (Least Recently Used) Eviction Policy
- File-Hash Verification (erkennt Dateiänderungen)
- Memory Size Estimation
- Hit-Rate Statistiken

**Hauptmethoden:**

```python
cache = WaveformCache(max_size=50, use_file_hash=True)

# Cache-Zugriff
waveform = cache.get(audio_path)
if waveform is None:
    # Cache miss - extract
    waveform = analyzer.extract_3band_waveform(audio_path)
    cache.put(audio_path, waveform)

# Statistiken
cache.print_stats()
# Output: "Cache Stats: 45 hits, 5 misses, 90.0% hit rate, 50/50 entries, 2 evictions, 15.3 MB"
```

## Integration mit WaveformWidget

### Schritt 1: Imports hinzufügen

```python
from pb_studio.audio import WaveformAnalyzer, WaveformCache
```

### Schritt 2: Initialisierung im Widget

```python
class WaveformWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)

        # Neuer Code: 3-Band Analyzer
        self.analyzer = WaveformAnalyzer(sr=44100)
        self.cache = WaveformCache(max_size=50)

        # Waveform-Daten (pro Band)
        self.waveform_low = None
        self.waveform_mid = None
        self.waveform_high = None

        # Existierender Code...
        self.zoom_level = 1.0
        self.scroll_offset = 0
        self.setMinimumHeight(100)
```

### Schritt 3: load_audio() anpassen

```python
def load_audio(self, file_path: str):
    """Loads audio and extracts 3-band waveform."""
    try:
        logger.info(f"Loading 3-band waveform: {file_path}")

        # Try cache first
        waveform = self.cache.get(file_path)

        if waveform is None:
            # Cache miss - extract waveform
            waveform = self.analyzer.get_downsampled_waveform(
                file_path,
                target_points=self.width() if self.width() > 0 else 1000
            )
            # Cache for future use
            self.cache.put(file_path, waveform)
        else:
            logger.info("Waveform loaded from cache")

        # Store band data
        self.waveform_low = waveform['low']
        self.waveform_mid = waveform['mid']
        self.waveform_high = waveform['high']

        # Reset view
        self.scroll_offset = 0
        self.zoom_level = 1.0

        self.update()  # Trigger repaint

    except Exception as e:
        logger.error(f"Failed to load 3-band waveform: {e}")
        self.waveform_low = None
        self.waveform_mid = None
        self.waveform_high = None
```

### Schritt 4: paintEvent() erweitern

```python
def paintEvent(self, event):
    if self.waveform_low is None:
        return

    painter = QPainter(self)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)

    w = self.width()
    h = self.height()

    # Rekordbox-Style: Gestapelte Bänder
    band_height = h // 3

    # Low Band (Bass) - Rot/Orange
    self._paint_band(
        painter,
        self.waveform_low,
        y_start=0,
        height=band_height,
        color=QColor("#ff6b35")  # Orange
    )

    # Mid Band (Mids) - Grün/Gelb
    self._paint_band(
        painter,
        self.waveform_mid,
        y_start=band_height,
        height=band_height,
        color=QColor("#52b788")  # Grün
    )

    # High Band (Highs) - Blau/Cyan
    self._paint_band(
        painter,
        self.waveform_high,
        y_start=band_height * 2,
        height=band_height,
        color=QColor("#00b4d8")  # Cyan
    )

def _paint_band(self, painter, band_data, y_start, height, color):
    """Paints single frequency band."""
    if band_data is None or len(band_data) == 0:
        return

    w = self.width()
    mid_y = y_start + height // 2

    # Calculate visible range (zoom support)
    visible = self._get_visible_range(band_data)

    pen = QPen(color, 2)
    painter.setPen(pen)

    x_scale = w / len(visible)

    for i in range(len(visible) - 1):
        x1 = int(i * x_scale)
        x2 = int((i + 1) * x_scale)

        # Map RMS amplitude to Y position
        y1 = int(mid_y - visible[i] * (height // 2 - 5))
        y2 = int(mid_y - visible[i + 1] * (height // 2 - 5))

        painter.drawLine(x1, y1, x2, y2)

    # Draw center line
    painter.setPen(QPen(QColor("#3e3e42"), 1))
    painter.drawLine(0, mid_y, w, mid_y)

def _get_visible_range(self, band_data):
    """Apply zoom and scroll to band data."""
    total_frames = len(band_data)
    visible_frames = int(total_frames / self.zoom_level)
    start_idx = max(0, self.scroll_offset)
    end_idx = min(total_frames, start_idx + visible_frames)

    return band_data[start_idx:end_idx]
```

## Alternative: Überlagertes Design

Statt gestapelten Bändern können die Frequenzen auch überlagert dargestellt werden:

```python
def paintEvent(self, event):
    painter = QPainter(self)
    w, h = self.width(), self.height()
    mid_y = h // 2

    # Draw all bands centered with transparency
    # Low band (bass) - Bright, thick
    self._paint_centered_band(painter, self.waveform_low, mid_y, h,
                              QColor(255, 107, 53, 200), thickness=3)

    # Mid band - Medium brightness
    self._paint_centered_band(painter, self.waveform_mid, mid_y, h,
                              QColor(82, 183, 136, 150), thickness=2)

    # High band - Subtle
    self._paint_centered_band(painter, self.waveform_high, mid_y, h,
                              QColor(0, 180, 216, 100), thickness=1)
```

## Performance-Tipps

1. **Downsampling:** Nutze `get_downsampled_waveform()` mit `target_points=self.width()` um nur Display-relevante Daten zu berechnen.

2. **Caching:** Cache ist persistent während der App-Laufzeit. Bei 50 gecachten Tracks (je ~2MB) = ~100MB RAM.

3. **Hop Length:** Kleinere `hop_length` = mehr Detail, aber auch mehr Datenpunkte:
   - `hop_length=512` (Standard): ~86 Frames pro Sekunde
   - `hop_length=1024`: ~43 Frames pro Sekunde
   - `hop_length=256`: ~172 Frames pro Sekunde

4. **Sample Rate:** Niedrigere SR = schnellere Verarbeitung:
   - `sr=44100` (Standard): Hi-Fi Qualität
   - `sr=22050`: Schnellere Verarbeitung, ausreichend für Visualisierung

## Testing

```bash
# Teste Waveform Analyzer
.\.venv\Scripts\python.exe -m pytest Tests/test_waveform_analyzer.py -v
```

## Beispiel-Usage

```python
from pb_studio.audio import WaveformAnalyzer, WaveformCache

# Setup
analyzer = WaveformAnalyzer(sr=44100)
cache = WaveformCache(max_size=50)

# Extract waveform
audio_path = "track.mp3"
waveform = analyzer.get_downsampled_waveform(audio_path, target_points=1000)

# Cache it
cache.put(audio_path, waveform)

# Use in GUI
for band_name, band_data in waveform.items():
    print(f"{band_name}: {len(band_data)} points, max={max(band_data):.3f}")

# Output:
# low: 1000 points, max=0.847
# mid: 1000 points, max=0.923
# high: 1000 points, max=0.612
```

## Weitere Features

### Frequenz-Content Analyse

```python
content = analyzer.analyze_frequency_content("track.mp3")
print(f"Low: {content['low_pct']:.1f}%")   # z.B. 35.2%
print(f"Mid: {content['mid_pct']:.1f}%")   # z.B. 52.1%
print(f"High: {content['high_pct']:.1f}%") # z.B. 12.7%

# Genre Detection Heuristik
if content['low_pct'] > 40:
    print("Bass-heavy track (EDM/Dubstep?)")
elif content['mid_pct'] > 60:
    print("Vocal-focused track (Pop/Rock?)")
```

### Cache-Statistiken im UI

```python
def show_cache_stats(self):
    stats = self.cache.get_stats()
    QMessageBox.information(
        self,
        "Waveform Cache Stats",
        f"Hit Rate: {stats['hit_rate']:.1f}%\n"
        f"Cached Files: {stats['size']}/{stats['max_size']}\n"
        f"Memory Usage: {stats['total_bytes'] / (1024*1024):.2f} MB\n"
        f"Evictions: {stats['evictions']}"
    )
```

## Kompatibilität

- **Python:** 3.10, 3.11 (nicht 3.12+)
- **librosa:** >=0.10.0
- **scipy:** >=1.10.0
- **numpy:** <2.0 (1.26.4 empfohlen)

## Known Issues

1. **Sehr lange Dateien (>30min):** Können bei `hop_length=512` viele Datenpunkte erzeugen. Nutze `get_downsampled_waveform()` oder erhöhe `hop_length`.

2. **Mono-Conversion:** Analyzer konvertiert automatisch auf Mono. Für Stereo-Waveforms müsste die Klasse erweitert werden.

3. **Echtzeit-Analyse:** Nicht implementiert. Für Live-Audio wäre ein Streaming-basierter Ansatz nötig.

## Roadmap

- [ ] Stereo-Support (L/R Channel separate Waveforms)
- [ ] Spectral Centroid Tracking
- [ ] Dynamic Band Ranges (User-Adjustable)
- [ ] GPU-Acceleration mit DirectML (für STFT)
- [ ] Real-time Analysis für Mikrofoneingang
