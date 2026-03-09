"""
3-Band Waveform Demo

Demonstrates how to use WaveformAnalyzer and WaveformCache
for Rekordbox-style multi-band waveform visualization.
"""
import sys
import logging
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.pb_studio.audio.waveform_analyzer import WaveformAnalyzer
from src.pb_studio.audio.waveform_cache import WaveformCache

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)


def demo_basic_extraction():
    """Demo: Basic 3-band waveform extraction."""
    logger.info("=" * 60)
    logger.info("Demo 1: Basic 3-Band Extraction")
    logger.info("=" * 60)

    analyzer = WaveformAnalyzer(sr=44100)

    # Example audio file (replace with your path)
    audio_path = "path/to/your/audio.mp3"

    if not Path(audio_path).exists():
        logger.warning(f"Demo audio not found: {audio_path}")
        logger.info("Creating synthetic test signal...")

        # Use synthetic audio for demo
        import numpy as np
        duration = 5.0
        t = np.linspace(0, duration, int(analyzer.sr * duration))
        y = np.sin(2 * np.pi * 440 * t)  # 440Hz sine wave

        # Save to temp file
        import tempfile
        import soundfile as sf

        temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.wav')
        sf.write(temp_file.name, y, analyzer.sr)
        audio_path = temp_file.name
        logger.info(f"Using synthetic audio: {audio_path}")

    # Extract waveform
    waveform = analyzer.extract_3band_waveform(audio_path)

    logger.info(f"Low band: {len(waveform['low'])} frames")
    logger.info(f"Mid band: {len(waveform['mid'])} frames")
    logger.info(f"High band: {len(waveform['high'])} frames")

    # Analyze frequency content
    content = analyzer.analyze_frequency_content(audio_path)
    logger.info(f"Frequency distribution:")
    logger.info(f"  Low: {content['low_pct']:.1f}%")
    logger.info(f"  Mid: {content['mid_pct']:.1f}%")
    logger.info(f"  High: {content['high_pct']:.1f}%")


def demo_downsampled_waveform():
    """Demo: Downsampled waveform for GUI display."""
    logger.info("=" * 60)
    logger.info("Demo 2: Downsampled Waveform for GUI")
    logger.info("=" * 60)

    analyzer = WaveformAnalyzer(sr=44100)

    # Create synthetic audio
    import numpy as np
    duration = 10.0
    t = np.linspace(0, duration, int(analyzer.sr * duration))
    y = np.sin(2 * np.pi * 440 * t)

    import tempfile
    import soundfile as sf
    temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.wav')
    sf.write(temp_file.name, y, analyzer.sr)
    audio_path = temp_file.name

    # Get downsampled waveform (e.g., for 1000-pixel display)
    waveform = analyzer.get_downsampled_waveform(audio_path, target_points=1000)

    logger.info(f"Downsampled to {len(waveform['low'])} points")
    logger.info(f"Perfect for a {len(waveform['low'])}-pixel wide display")


def demo_caching():
    """Demo: Waveform caching for performance."""
    logger.info("=" * 60)
    logger.info("Demo 3: Waveform Caching")
    logger.info("=" * 60)

    analyzer = WaveformAnalyzer(sr=44100)
    cache = WaveformCache(max_size=10)

    # Create synthetic audio
    import numpy as np
    duration = 5.0
    t = np.linspace(0, duration, int(analyzer.sr * duration))
    y = np.sin(2 * np.pi * 440 * t)

    import tempfile
    import soundfile as sf
    temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.wav')
    sf.write(temp_file.name, y, analyzer.sr)
    audio_path = temp_file.name

    # First access - cache miss
    logger.info("First access (cache miss):")
    cached = cache.get(audio_path)
    logger.info(f"  Cached: {cached is not None}")

    # Extract and cache
    logger.info("Extracting waveform...")
    waveform = analyzer.extract_3band_waveform(audio_path)
    cache.put(audio_path, waveform)

    # Second access - cache hit
    logger.info("Second access (cache hit):")
    cached = cache.get(audio_path)
    logger.info(f"  Cached: {cached is not None}")

    # Print cache stats
    cache.print_stats()


def demo_gui_integration():
    """Demo: Integration with WaveformWidget."""
    logger.info("=" * 60)
    logger.info("Demo 4: GUI Integration Pattern")
    logger.info("=" * 60)

    logger.info("Example integration with existing WaveformWidget:")
    logger.info("")

    code = '''
# In your WaveformWidget or controller class:

from src.pb_studio.audio.waveform_analyzer import WaveformAnalyzer
from src.pb_studio.audio.waveform_cache import WaveformCache

class EnhancedWaveformWidget:
    def __init__(self):
        self.analyzer = WaveformAnalyzer(sr=44100)
        self.cache = WaveformCache(max_size=50)

    def load_audio(self, file_path: str):
        # Try cache first
        waveform = self.cache.get(file_path)

        if waveform is None:
            # Cache miss - extract
            waveform = self.analyzer.get_downsampled_waveform(
                file_path,
                target_points=self.width()  # Match display width
            )
            self.cache.put(file_path, waveform)

        # Now you have 3-band waveform data
        self.waveform_low = waveform['low']
        self.waveform_mid = waveform['mid']
        self.waveform_high = waveform['high']

        self.update()  # Trigger repaint

    def paintEvent(self, event):
        painter = QPainter(self)

        # Draw low band (bass) in red
        painter.setPen(QColor("#ff4d4d"))
        self._draw_band(painter, self.waveform_low, y_offset=0)

        # Draw mid band (mids) in green
        painter.setPen(QColor("#4dff4d"))
        self._draw_band(painter, self.waveform_mid, y_offset=50)

        # Draw high band (highs) in blue
        painter.setPen(QColor("#4d4dff"))
        self._draw_band(painter, self.waveform_high, y_offset=100)

    def _draw_band(self, painter, band_data, y_offset):
        w = self.width()
        x_scale = w / len(band_data)

        for i in range(len(band_data) - 1):
            x1 = int(i * x_scale)
            x2 = int((i + 1) * x_scale)
            y1 = int(y_offset + band_data[i] * 40)
            y2 = int(y_offset + band_data[i + 1] * 40)
            painter.drawLine(x1, y1, x2, y2)
    '''

    print(code)


def main():
    """Run all demos."""
    try:
        demo_basic_extraction()
        print()

        demo_downsampled_waveform()
        print()

        demo_caching()
        print()

        demo_gui_integration()

    except Exception as e:
        logger.error(f"Demo failed: {e}")
        import traceback
        logger.error(traceback.format_exc())


if __name__ == "__main__":
    main()
