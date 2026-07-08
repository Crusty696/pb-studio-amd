import logging
import numpy as np
from pathlib import Path

logger = logging.getLogger(__name__)

class AudioAnalyzer:
    def __init__(self):
        # ffmpeg-Pfad aus Config (statt hartcodiert "ffmpeg")
        try:
            from pb_studio.config_manager import ConfigManager
            self.ffmpeg_path = ConfigManager().ffmpeg_path
        except Exception:
            try:
                from pb_studio.video.encoder_utils import _get_ffmpeg_path
                self.ffmpeg_path = _get_ffmpeg_path()
            except Exception:
                self.ffmpeg_path = "ffmpeg"  # Fallback: System-PATH

        try:
            # Lazy import to avoid loading heavyweight models on app start if not needed
            from BeatNet.BeatNet import BeatNet
            self.estimator = BeatNet(1, mode='offline', inference_model='DBN', plot=[], thread=False)
            self.model_loaded = True
        except ImportError as e:
            logger.error(f"BeatNet import failed: {e}")
            self.model_loaded = False
        except Exception as e:
            logger.error(f"BeatNet Init failed: {e}")
            self.model_loaded = False

    def analyze_file(self, file_path: str):
        """
        Runs BeatNet analysis.
        Returns dict with bpm, downbeats, etc.
        """
        if not self.model_loaded:
            return {"error": "Model not loaded"}
        
        try:
            # Pre-conversion: Extract/Convert to clean WAV 16-bit
            # This is critical for AMD/Windows environments where librosa/audioread
            # fail to detect ffmpeg via pipes.
            import subprocess
            import tempfile
            import os
            import uuid
            
            # Use system temp dir to avoid permission/path issues
            temp_dir = tempfile.gettempdir()
            unique_name = f"pb_studio_analyze_{uuid.uuid4().hex}.wav"
            temp_wav = str(Path(temp_dir) / unique_name)
            
            analyze_path = file_path # Default fallback
            conversion_success = False
            
            try:
                logger.info(f"Preparing to analyze: {file_path}")
                
                # ffmpeg: 22.05kHz mono 16-bit PCM WAV
                # -vn = no video, -y = overwrite
                command = [
                    self.ffmpeg_path, "-y", "-i", file_path,
                    "-vn", "-acodec", "pcm_s16le", "-ar", "22050", "-ac", "1",
                    temp_wav
                ]
                
                # Run conversion
                result = subprocess.run(command, capture_output=True, text=True, timeout=120)
                
                if result.returncode == 0 and Path(temp_wav).exists() and Path(temp_wav).stat().st_size > 0:
                     logger.debug(f"Audio extraction success. Size: {Path(temp_wav).stat().st_size} bytes")
                     analyze_path = temp_wav
                     conversion_success = True
                else:
                    err_output = result.stderr
                    # Check if failure is due to missing audio stream (Silent Video)
                    if "does not contain any stream" in err_output or "Output file does not contain any stream" in err_output:
                        logger.warning(f"No audio stream found in {Path(file_path).name}. Returning 0 BPM.")
                        # Temp-Datei aufräumen bevor Early-Return
                        if Path(temp_wav).exists():
                            try:
                                os.remove(temp_wav)
                            except Exception:
                                pass
                        return {"bpm": 0, "beat_data": [], "count": 0, "warning": "No Audio Stream"}
                    else:
                        logger.warning(f"FFmpeg conversion failed (Code {result.returncode}). Stderr: {err_output[:200]}...")
                        # Fallback to original file implies hoping BeatNet can read it directly
                        pass
                    
            except Exception as e:
                logger.warning(f"Audio conversion crash: {e}")
                import traceback
                logger.debug(traceback.format_exc())

            logger.info(f"Running BeatNet on: {analyze_path}")

            # BeatNet processing
            output = self.estimator.process(analyze_path)

            # RMS-Energie extrahieren (vor Temp-Cleanup!)
            energy_curve = []
            energy_times = []
            try:
                import librosa
                wav_path = analyze_path  # Nutzt die bereits konvertierte 22kHz WAV
                y, sr = librosa.load(wav_path, sr=22050, mono=True)
                # RMS in Frames berechnen (hop_length=512 -> ~43 Werte/Sek)
                hop = 512
                rms = librosa.feature.rms(y=y, frame_length=2048, hop_length=hop)[0]
                # Zeitachse
                energy_times = librosa.frames_to_time(
                    np.arange(len(rms)), sr=sr, hop_length=hop
                ).tolist()
                # Normalisieren auf 0-1
                rms_max = float(np.max(rms)) if len(rms) > 0 else 1.0
                if rms_max > 0:
                    energy_curve = (rms / rms_max).tolist()
                else:
                    energy_curve = rms.tolist()
                logger.info(f"RMS Energy extracted: {len(energy_curve)} frames")
            except Exception as e:
                logger.warning(f"RMS energy extraction failed: {e}")

            # Temp-Datei immer aufraeumen
            if Path(temp_wav).exists():
                try:
                    os.remove(temp_wav)
                except Exception as e:
                    logger.debug(f"Could not remove temp file: {e}")

            if output is None or len(output) == 0:
                logger.info("BeatNet returned empty results.")
                return {"bpm": 0, "beat_data": [], "count": 0}

            # BeatNet Output validieren (muss 2D array sein)
            if not isinstance(output, np.ndarray):
                output = np.array(output)
            if output.ndim != 2 or output.shape[1] < 1:
                logger.error(f"Invalid BeatNet output shape: {output.shape}")
                return {"bpm": 0, "beat_data": [], "count": 0}

            # Calculate Average BPM
            # Time differences between beats
            times = output[:, 0]
            if len(times) > 1:
                intervals = np.diff(times)
                avg_interval = np.median(intervals)
                bpm = 60.0 / avg_interval if avg_interval > 0 else 0
            else:
                bpm = 0
            
            logger.info(f"Analysis Success. BPM: {round(bpm, 2)}, Beats: {len(output)}")
            
            return {
                "bpm": round(bpm, 2),
                "beat_data": output.tolist(),
                "count": len(output),
                "energy_curve": energy_curve,
                "energy_times": energy_times,
            }
            
        except Exception as e:
            import traceback
            logger.error(f"Analysis failed: {e}")
            logger.error(traceback.format_exc())
            
            # Cleanup temp if error (best effort)
            if 'temp_wav' in locals() and temp_wav and Path(temp_wav).exists():
                try:
                    os.remove(temp_wav)
                except Exception as cleanup_err:
                    logger.debug(f"Could not cleanup temp: {cleanup_err}")
                
            return {"error": str(e)}
