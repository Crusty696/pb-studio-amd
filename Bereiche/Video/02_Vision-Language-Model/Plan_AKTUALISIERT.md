# Vision-Language-Model - Migrationsplan (AKTUALISIERT)

**Stand:** 04.01.2026
**Bereich:** Video
**Zugehörige Recherche:** `Recherche_AKTUALISIERT.md`
**Risiko:** 🟡 MITTEL (nach Recherche reduziert von HOCH)

---

## Ziel

Moondream durch Phi-3.5-Vision ONNX ersetzen für AMD DirectML.

---

## WICHTIG: Moondream ist NICHT portierbar!

Nach intensiver Recherche: **Moondream hat keinen funktionierenden ONNX-Export**.
Die Alternative ist **Phi-3.5-Vision ONNX** von Microsoft.

---

## Tasks

### Task 1: Umgebung vorbereiten
**Priorität:** HOCH
**Dauer:** 1 Stunde

**Schritte:**
1. Python 3.10 Virtual Environment erstellen
2. `pip install onnxruntime-directml==1.23.0`
3. `pip install huggingface-hub[cli] transformers pillow`
4. DirectML-Verfügbarkeit testen

**Erfolgskriterium:** ONNX Session mit DML-Provider startet

---

### Task 2: Phi-3.5-Vision herunterladen
**Priorität:** HOCH
**Dauer:** 30 Min (je nach Internet)

**Schritte:**
```bash
huggingface-cli download microsoft/Phi-3.5-vision-instruct-onnx --local-dir ./models/phi35-vision
```

**Erfolgskriterium:** Modell-Dateien vollständig heruntergeladen (~10 GB)

---

### Task 3: Wrapper-Klasse erstellen
**Priorität:** HOCH
**Dauer:** 4-6 Stunden

**Schritte:**
1. `VisionLanguageModel` Klasse erstellen
2. Interface kompatibel zu bisherigem Moondream-Code
3. Methoden: `load_model()`, `generate_caption()`, `unload()`
4. DirectML Session-Konfiguration implementieren

**Code-Vorlage:**
```python
import onnxruntime as ort
from PIL import Image

class VisionLanguageModel:
    def __init__(self, model_path: str):
        self.session = None
        self.model_path = model_path
    
    def load_model(self):
        options = ort.SessionOptions()
        options.enable_mem_pattern = False
        options.execution_mode = ort.ExecutionMode.ORT_SEQUENTIAL
        
        self.session = ort.InferenceSession(
            self.model_path,
            sess_options=options,
            providers=[('DmlExecutionProvider', {'device_id': 0})]
        )
    
    def generate_caption(self, image: Image.Image, prompt: str = "Describe this image.") -> str:
        # Preprocessing + Inference
        pass
    
    def unload(self):
        del self.session
        self.session = None
```

**Erfolgskriterium:** Klasse lädt Modell und gibt Caption zurück

---

### Task 4: Integration in bestehenden Code
**Priorität:** HOCH
**Dauer:** 3-4 Stunden

**Schritte:**
1. `semantic_engine.py` anpassen
2. Moondream-Referenzen durch Phi-3.5 ersetzen
3. Prompt-Format anpassen (unterschiedliches Format!)
4. Error-Handling für DirectML-Fehler

**Erfolgskriterium:** Bestehende Funktionsaufrufe funktionieren

---

### Task 5: Performance-Optimierung
**Priorität:** MITTEL
**Dauer:** 2-3 Stunden

**Schritte:**
1. INT4-Quantisierung testen
2. Batch-Processing evaluieren
3. VRAM-Monitoring implementieren
4. Warm-up für Session (erster Call langsam)

**Erfolgskriterium:** Stabile Performance ohne OOM-Fehler

---

### Task 6: Testing
**Priorität:** HOCH
**Dauer:** 2 Stunden

**Schritte:**
1. Unit-Tests für VLM-Wrapper
2. Integration-Tests mit Video-Pipeline
3. Vergleich Output-Qualität mit NVIDIA-Version
4. Edge-Cases (große Bilder, leere Bilder, etc.)

**Erfolgskriterium:** Alle Tests grün

---

## Zeitschätzung

| Task | Dauer |
|------|-------|
| Task 1: Umgebung | 1h |
| Task 2: Download | 0.5h |
| Task 3: Wrapper | 4-6h |
| Task 4: Integration | 3-4h |
| Task 5: Optimierung | 2-3h |
| Task 6: Testing | 2h |
| **Gesamt** | **12-16 Stunden** |

---

## Abhängigkeiten

```txt
onnxruntime-directml==1.23.0
transformers>=4.36.0
pillow>=10.0.0
huggingface-hub>=0.20.0
```

---

## Fallback-Plan

Falls Phi-3.5-Vision Probleme macht:
1. **Florence-2 ONNX** - Einfachere Architektur
2. **SmolVLM ONNX** - Minimaler VRAM
3. **CPU-Fallback** - Langsam aber funktioniert

---

## Risiken

| Risiko | Wahrscheinlichkeit | Mitigation |
|--------|-------------------|------------|
| VRAM-Überlauf | Niedrig | INT4-Quantisierung |
| Performance zu langsam | Mittel | Batch-Optimierung |
| Prompt-Format inkompatibel | Niedrig | Adapter-Layer |

---

*Plan erstellt: 04.01.2026*
