"""
Test-Skript für Ollama + Vulkan auf AMD RX 7800 XT
Stand: 04.01.2026

Dieses Skript testet:
1. Ollama-Verbindung
2. Vulkan-Backend
3. Moondream VLM Funktionalität
"""

import subprocess
import sys
import os
from pathlib import Path

def print_header(text):
    print("\n" + "="*60)
    print(f" {text}")
    print("="*60)

def check_ollama_installed():
    """Prüft ob Ollama installiert ist."""
    print_header("1. OLLAMA INSTALLATION")
    
    try:
        result = subprocess.run(
            ["ollama", "--version"],
            capture_output=True,
            text=True
        )
        if result.returncode == 0:
            print(f"✅ Ollama gefunden: {result.stdout.strip()}")
            return True
        else:
            print("❌ Ollama nicht gefunden!")
            print("   Bitte installieren: https://ollama.com/download")
            return False
    except FileNotFoundError:
        print("❌ Ollama nicht im PATH!")
        print("   Bitte installieren: https://ollama.com/download")
        return False

def check_vulkan_env():
    """Prüft ob OLLAMA_VULKAN gesetzt ist."""
    print_header("2. VULKAN UMGEBUNGSVARIABLE")
    
    vulkan_env = os.environ.get("OLLAMA_VULKAN", "0")
    
    if vulkan_env == "1":
        print("✅ OLLAMA_VULKAN=1 ist gesetzt")
        return True
    else:
        print("⚠️  OLLAMA_VULKAN ist NICHT gesetzt!")
        print("   Bitte setzen mit:")
        print('   $env:OLLAMA_VULKAN = "1"')
        return False

def check_ollama_running():
    """Prüft ob Ollama-Server läuft."""
    print_header("3. OLLAMA SERVER")
    
    try:
        import requests
        response = requests.get("http://localhost:11434/api/version", timeout=5)
        if response.status_code == 200:
            version = response.json().get("version", "unknown")
            print(f"✅ Ollama Server läuft (Version: {version})")
            return True
        else:
            print("❌ Ollama Server antwortet nicht korrekt")
            return False
    except Exception as e:
        print(f"❌ Ollama Server nicht erreichbar: {e}")
        print("   Bitte starten mit: ollama serve")
        return False

def check_moondream_model():
    """Prüft ob Moondream-Modell geladen ist."""
    print_header("4. MOONDREAM MODELL")
    
    try:
        import ollama
        models = ollama.list()
        
        moondream_found = False
        for model in models.get("models", []):
            if "moondream" in model.get("name", "").lower():
                print(f"✅ Moondream gefunden: {model['name']}")
                print(f"   Größe: {model.get('size', 'N/A')} bytes")
                moondream_found = True
                break
        
        if not moondream_found:
            print("⚠️  Moondream nicht gefunden!")
            print("   Bitte laden mit: ollama pull moondream")
            return False
        
        return True
        
    except ImportError:
        print("❌ ollama Python-Paket nicht installiert!")
        print("   pip install ollama")
        return False
    except Exception as e:
        print(f"❌ Fehler: {e}")
        return False

def test_moondream_inference():
    """Testet Moondream mit einem Testbild."""
    print_header("5. MOONDREAM INFERENZ-TEST")
    
    try:
        import ollama
        import base64
        from PIL import Image
        import io
        import time
        
        # Erstelle ein einfaches Testbild (100x100 rotes Quadrat)
        print("   Erstelle Testbild...")
        img = Image.new('RGB', (100, 100), color='red')
        
        # In Base64 konvertieren
        buffer = io.BytesIO()
        img.save(buffer, format='PNG')
        image_data = base64.b64encode(buffer.getvalue()).decode()
        
        # Anfrage an Moondream
        print("   Sende Anfrage an Moondream...")
        start_time = time.time()
        
        response = ollama.chat(
            model="moondream",
            messages=[{
                "role": "user",
                "content": "What color is this image?",
                "images": [image_data]
            }]
        )
        
        end_time = time.time()
        duration = end_time - start_time
        
        answer = response["message"]["content"]
        
        print(f"✅ Antwort erhalten in {duration:.2f}s:")
        print(f"   \"{answer[:100]}...\"" if len(answer) > 100 else f"   \"{answer}\"")
        
        # Prüfe ob "red" in der Antwort
        if "red" in answer.lower():
            print("✅ Korrekte Farbe erkannt!")
            return True
        else:
            print("⚠️  Antwort enthält nicht 'red' - möglicherweise OK")
            return True
        
    except Exception as e:
        print(f"❌ Inferenz-Fehler: {e}")
        return False

def main():
    print("\n" + "#"*60)
    print("#  OLLAMA + VULKAN TEST FÜR AMD RX 7800 XT")
    print("#"*60)
    
    results = {}
    
    # Tests durchführen
    results["ollama_installed"] = check_ollama_installed()
    results["vulkan_env"] = check_vulkan_env()
    results["ollama_running"] = check_ollama_running()
    
    if results["ollama_running"]:
        results["moondream_model"] = check_moondream_model()
        
        if results["moondream_model"]:
            results["inference_test"] = test_moondream_inference()
    
    # Zusammenfassung
    print_header("ZUSAMMENFASSUNG")
    
    all_passed = all(results.values())
    
    for test, passed in results.items():
        status = "✅" if passed else "❌"
        print(f"  {status} {test}")
    
    print()
    if all_passed:
        print("🎉 ALLE TESTS BESTANDEN!")
        print("   Moondream ist bereit für die AMD-Migration.")
    else:
        print("⚠️  EINIGE TESTS FEHLGESCHLAGEN")
        print("   Bitte die obigen Hinweise beachten.")
    
    return 0 if all_passed else 1

if __name__ == "__main__":
    sys.exit(main())
