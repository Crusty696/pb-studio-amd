import sys
sys.path.append('src')
from pb_studio.audio.separator import StemSeparator

sep = StemSeparator()
print("Versuche Modell 'Demucs' zu laden...")
try:
    sep.separator.load_model("Demucs")
    print("Modell 'Demucs' erfolgreich geladen!")
except Exception as e:
    print(f"Laden fehlgeschlagen: {e}")
