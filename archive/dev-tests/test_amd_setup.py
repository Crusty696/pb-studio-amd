# PB Studio AMD - Test Setup Script
# Führt grundlegende Validierung der AMD-Umgebung durch

import sys
import subprocess

def print_header(text):
    print(f"\n{'='*60}")
    print(f"  {text}")
    print(f"{'='*60}")

def print_ok(text):
    print(f"  ✅ {text}")

def print_fail(text):
    print(f"  ❌ {text}")

def print_warn(text):
    print(f"  ⚠️  {text}")

def main():
    print_header("PB Studio AMD - Setup Test")
    print(f"Python Version: {sys.version}")
    
    errors = []
    
    # 1. ONNX Runtime DirectML
    print_header("1. ONNX Runtime DirectML")
    try:
        import onnxruntime as ort
        version = ort.__version__
        providers = ort.get_available_providers()
        
        print_ok(f"onnxruntime version: {version}")
        
        if 'DmlExecutionProvider' in providers:
            print_ok("DirectML Provider verfügbar")
        else:
            print_fail("DirectML Provider NICHT verfügbar!")
            errors.append("DirectML Provider fehlt")
        
        print(f"     Alle Provider: {providers}")
        
    except ImportError:
        print_fail("onnxruntime-directml nicht installiert!")
        errors.append("onnxruntime-directml fehlt")
    
    # 2. Audio-Separator
    print_header("2. Audio-Separator")
    try:
        from audio_separator.separator import Separator
        print_ok("audio-separator importiert")
    except ImportError:
        print_warn("audio-separator nicht installiert (optional für Stem-Separation)")
    
    # 3. Transformers
    print_header("3. Transformers")
    try:
        import transformers
        print_ok(f"transformers version: {transformers.__version__}")
    except ImportError:
        print_fail("transformers nicht installiert!")
        errors.append("transformers fehlt")
    
    # 4. Pillow
    print_header("4. Pillow")
    try:
        from PIL import Image
        import PIL
        print_ok(f"Pillow version: {PIL.__version__}")
    except ImportError:
        print_fail("Pillow nicht installiert!")
        errors.append("Pillow fehlt")
    
    # 5. OpenCV
    print_header("5. OpenCV")
    try:
        import cv2
        print_ok(f"OpenCV version: {cv2.__version__}")
    except ImportError:
        print_warn("OpenCV nicht installiert (benötigt für Video)")
    
    # 6. ChromaDB
    print_header("6. ChromaDB")
    try:
        import chromadb
        print_ok(f"ChromaDB version: {chromadb.__version__}")
    except ImportError:
        print_warn("ChromaDB nicht installiert (benötigt für Vector Store)")
    
    # 7. Librosa
    print_header("7. Librosa")
    try:
        import librosa
        print_ok(f"Librosa version: {librosa.__version__}")
    except ImportError:
        print_warn("Librosa nicht installiert (benötigt für Audio-Analyse)")
    
    # 8. FFmpeg AMF
    print_header("8. FFmpeg AMF")
    try:
        result = subprocess.run(
            ['ffmpeg', '-encoders'],
            capture_output=True,
            text=True,
            timeout=10
        )
        
        if 'h264_amf' in result.stdout:
            print_ok("h264_amf Encoder verfügbar")
        else:
            print_fail("h264_amf NICHT verfügbar!")
            errors.append("h264_amf fehlt")
        
        if 'hevc_amf' in result.stdout:
            print_ok("hevc_amf Encoder verfügbar")
        else:
            print_warn("hevc_amf nicht verfügbar")
        
        if 'av1_amf' in result.stdout:
            print_ok("av1_amf Encoder verfügbar (RDNA3)")
        else:
            print_warn("av1_amf nicht verfügbar (nur RDNA3)")
            
    except FileNotFoundError:
        print_fail("FFmpeg nicht gefunden!")
        errors.append("FFmpeg nicht installiert")
    except subprocess.TimeoutExpired:
        print_fail("FFmpeg Timeout!")
    
    # Zusammenfassung
    print_header("ZUSAMMENFASSUNG")
    
    if errors:
        print_fail(f"{len(errors)} kritische Fehler gefunden:")
        for err in errors:
            print(f"     - {err}")
        print("\n  Bitte beheben vor dem Fortfahren!")
        return 1
    else:
        print_ok("Alle kritischen Komponenten verfügbar!")
        print("\n  Die AMD-Umgebung ist bereit.")
        return 0

if __name__ == "__main__":
    sys.exit(main())
