"""
PB Studio AMD - DirectML Validierungstest
Stand: 04.01.2026

Testet ob DirectML auf der AMD RX 7800 XT funktioniert.
"""

import sys
import os

def check_python_version():
    """Prüft Python Version (3.10-3.13 erforderlich)"""
    print("=" * 60)
    print("1. PYTHON VERSION")
    print("=" * 60)
    
    version = sys.version_info
    print(f"   Python {version.major}.{version.minor}.{version.micro}")
    
    if 10 <= version.minor <= 13 and version.major == 3:
        print("   ✅ Python Version OK")
        return True
    else:
        print("   ❌ FEHLER: Python 3.10-3.13 erforderlich!")
        return False

def check_onnxruntime_directml():
    """Prüft onnxruntime-directml Installation"""
    print("\n" + "=" * 60)
    print("2. ONNX RUNTIME DIRECTML")
    print("=" * 60)
    
    try:
        import onnxruntime as ort
        print(f"   ONNX Runtime Version: {ort.__version__}")
        
        providers = ort.get_available_providers()
        print(f"   Verfügbare Provider: {providers}")
        
        if 'DmlExecutionProvider' in providers:
            print("   ✅ DirectML Provider verfügbar!")
            return True
        else:
            print("   ❌ DirectML Provider NICHT gefunden!")
            print("   → Installiere: pip install onnxruntime-directml")
            return False
            
    except ImportError as e:
        print(f"   ❌ FEHLER: onnxruntime nicht installiert!")
        print(f"   → {e}")
        print("   → Installiere: pip install onnxruntime-directml")
        return False

def test_directml_session():
    """Testet ob eine DirectML Session erstellt werden kann"""
    print("\n" + "=" * 60)
    print("3. DIRECTML SESSION TEST")
    print("=" * 60)
    
    try:
        import onnxruntime as ort
        import numpy as np
        
        # Minimales ONNX Modell erstellen (Identity)
        from onnx import helper, TensorProto, save
        import tempfile
        
        # Einfaches Identity-Modell
        X = helper.make_tensor_value_info('X', TensorProto.FLOAT, [1, 3, 224, 224])
        Y = helper.make_tensor_value_info('Y', TensorProto.FLOAT, [1, 3, 224, 224])
        
        identity_node = helper.make_node('Identity', ['X'], ['Y'])
        graph = helper.make_graph([identity_node], 'test_graph', [X], [Y])
        model = helper.make_model(graph, opset_imports=[helper.make_opsetid('', 13)])
        
        # Temporär speichern
        with tempfile.NamedTemporaryFile(suffix='.onnx', delete=False) as f:
            save(model, f.name)
            temp_path = f.name
        
        # DirectML Session erstellen
        session_options = ort.SessionOptions()
        session_options.enable_mem_pattern = False
        session_options.execution_mode = ort.ExecutionMode.ORT_SEQUENTIAL
        
        session = ort.InferenceSession(
            temp_path,
            sess_options=session_options,
            providers=[('DmlExecutionProvider', {'device_id': 0}), 'CPUExecutionProvider']
        )
        
        # Test-Inferenz
        test_input = np.random.randn(1, 3, 224, 224).astype(np.float32)
        result = session.run(None, {'X': test_input})
        
        # Aufräumen
        os.unlink(temp_path)
        
        print("   ✅ DirectML Session erfolgreich!")
        print(f"   → Input Shape: {test_input.shape}")
        print(f"   → Output Shape: {result[0].shape}")
        return True
        
    except Exception as e:
        print(f"   ❌ FEHLER: {e}")
        return False

def check_dependencies():
    """Prüft alle wichtigen Abhängigkeiten"""
    print("\n" + "=" * 60)
    print("4. ABHÄNGIGKEITEN")
    print("=" * 60)
    
    dependencies = {
        'transformers': 'transformers',
        'PIL': 'Pillow',
        'cv2': 'opencv-python',
        'numpy': 'numpy',
        'huggingface_hub': 'huggingface-hub'
    }
    
    all_ok = True
    for module, package in dependencies.items():
        try:
            __import__(module)
            print(f"   ✅ {package}")
        except ImportError:
            print(f"   ❌ {package} FEHLT")
            all_ok = False
    
    return all_ok

def get_gpu_info():
    """Versucht GPU-Informationen zu bekommen"""
    print("\n" + "=" * 60)
    print("5. GPU INFORMATIONEN")
    print("=" * 60)
    
    try:
        # Windows WMI für GPU Info
        import subprocess
        result = subprocess.run(
            ['wmic', 'path', 'win32_VideoController', 'get', 'name,AdapterRAM'],
            capture_output=True, text=True
        )
        print(result.stdout)
    except Exception as e:
        print(f"   Konnte GPU-Info nicht abrufen: {e}")

def main():
    print("\n" + "=" * 60)
    print("PB STUDIO AMD - DIRECTML VALIDIERUNGSTEST")
    print("=" * 60)
    print()
    
    results = {}
    
    results['python'] = check_python_version()
    results['onnxruntime'] = check_onnxruntime_directml()
    results['session'] = test_directml_session()
    results['deps'] = check_dependencies()
    get_gpu_info()
    
    print("\n" + "=" * 60)
    print("ZUSAMMENFASSUNG")
    print("=" * 60)
    
    all_passed = all(results.values())
    
    for test, passed in results.items():
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"   {test}: {status}")
    
    print()
    if all_passed:
        print("   🎉 ALLE TESTS BESTANDEN!")
        print("   → DirectML ist bereit für PB Studio AMD")
    else:
        print("   ⚠️ EINIGE TESTS FEHLGESCHLAGEN")
        print("   → Bitte Fehler beheben und erneut ausführen")
    
    print()
    return 0 if all_passed else 1

if __name__ == "__main__":
    sys.exit(main())
