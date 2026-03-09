# Vision Language Model - AKTUALISIERTER PLAN v2

**Stand:** 04.01.2026  
**Status:** ✅ LÖSUNG GEFUNDEN

---

## 🎯 ZIEL

Moondream2 Vision Language Model auf AMD RX 7800 XT Windows mit GPU-Beschleunigung.

---

## ✅ GEWÄHLTE LÖSUNG: OLLAMA + VULKAN

### Warum diese Lösung?
1. **1:1 Ersatz** für Original-Moondream
2. **GPU-Beschleunigung** via Vulkan
3. **Einfachste Installation** und Wartung
4. **Offizielle Support** in Ollama Library

---

## 📋 IMPLEMENTIERUNGS-TASKS

### Phase 1: Umgebung einrichten (2-3 Stunden)

| # | Task | Beschreibung | Prüfkriterium |
|---|------|--------------|---------------|
| 1.1 | Ollama installieren | Download von ollama.com | `ollama --version` zeigt Version |
| 1.2 | Vulkan verifizieren | AMD-Treiber aktuell | `vulkaninfo` läuft |
| 1.3 | Vulkan aktivieren | `OLLAMA_VULKAN=1` setzen | Ollama Log zeigt "Vulkan" |
| 1.4 | Moondream laden | `ollama pull moondream` | Model verfügbar |

### Phase 2: Basis-Test (1-2 Stunden)

| # | Task | Beschreibung | Prüfkriterium |
|---|------|--------------|---------------|
| 2.1 | CLI-Test | Bild beschreiben lassen | Sinnvolle Ausgabe |
| 2.2 | GPU-Auslastung | Task Manager prüfen | GPU-Nutzung >0% |
| 2.3 | Performance-Test | 10 Bilder verarbeiten | <5s pro Bild |

### Phase 3: Python-Integration (4-6 Stunden)

| # | Task | Beschreibung | Prüfkriterium |
|---|------|--------------|---------------|
| 3.1 | ollama-python installieren | `pip install ollama` | Import funktioniert |
| 3.2 | Wrapper-Klasse erstellen | OllamaMoondreamVLM | Unit-Tests grün |
| 3.3 | API-Kompatibilität | Gleiche Signatur wie Original | Drop-in Ersatz |
| 3.4 | Batch-Verarbeitung | Mehrere Bilder | Stabil bei 100 Bildern |

### Phase 4: Integration (4-6 Stunden)

| # | Task | Beschreibung | Prüfkriterium |
|---|------|--------------|---------------|
| 4.1 | Original-Code anpassen | Import ändern | Keine Fehler |
| 4.2 | Funktionstest | Alle VLM-Aufrufe | Identische Ergebnisse |
| 4.3 | Performance-Vergleich | vs CPU-Version | Schneller |
| 4.4 | Dokumentation | README aktualisieren | Vollständig |

---

## 🔧 TECHNISCHE DETAILS

### Umgebungsvariablen (Windows)

```powershell
# System-Umgebungsvariable setzen (permanent)
[System.Environment]::SetEnvironmentVariable("OLLAMA_VULKAN", "1", "User")

# Oder in PowerShell-Profil
# $PROFILE öffnen und hinzufügen:
$env:OLLAMA_VULKAN = "1"
```

### Wrapper-Klasse (Python)

```python
# vlm_amd.py
import ollama
import base64
from pathlib import Path
from typing import Optional, Union

class MoondreamVLM:
    """
    AMD-kompatibler Moondream VLM Wrapper via Ollama.
    Drop-in Ersatz für Original-Implementation.
    """
    
    def __init__(self, model: str = "moondream"):
        self.model = model
        self._verify_model()
    
    def _verify_model(self):
        """Prüft ob Modell verfügbar ist."""
        models = ollama.list()
        if not any(m["name"].startswith(self.model) for m in models["models"]):
            print(f"Lade {self.model}...")
            ollama.pull(self.model)
    
    def _load_image(self, image_path: Union[str, Path]) -> str:
        """Lädt Bild als Base64."""
        with open(image_path, "rb") as f:
            return base64.b64encode(f.read()).decode()
    
    def describe(self, image_path: Union[str, Path], prompt: str = "Describe this image in detail.") -> str:
        """
        Beschreibt ein Bild.
        
        Args:
            image_path: Pfad zum Bild
            prompt: Anweisung für die Beschreibung
            
        Returns:
            Textuelle Beschreibung des Bildes
        """
        image_data = self._load_image(image_path)
        
        response = ollama.chat(
            model=self.model,
            messages=[{
                "role": "user",
                "content": prompt,
                "images": [image_data]
            }]
        )
        
        return response["message"]["content"]
    
    def query(self, image_path: Union[str, Path], question: str) -> str:
        """
        Beantwortet eine Frage zum Bild.
        
        Args:
            image_path: Pfad zum Bild
            question: Frage zum Bild
            
        Returns:
            Antwort auf die Frage
        """
        return self.describe(image_path, question)
    
    def batch_describe(self, image_paths: list, prompt: str = "Describe this image.") -> list:
        """
        Beschreibt mehrere Bilder.
        
        Args:
            image_paths: Liste von Bildpfaden
            prompt: Anweisung für die Beschreibung
            
        Returns:
            Liste von Beschreibungen
        """
        return [self.describe(p, prompt) for p in image_paths]


# Für Kompatibilität mit Original-Code
def create_vlm() -> MoondreamVLM:
    """Factory-Funktion für VLM-Instanz."""
    return MoondreamVLM()
```

---

## ⏱️ ZEITSCHÄTZUNG

| Phase | Stunden |
|-------|---------|
| Phase 1: Umgebung | 2-3h |
| Phase 2: Basis-Test | 1-2h |
| Phase 3: Python-Integration | 4-6h |
| Phase 4: Integration | 4-6h |
| **GESAMT** | **11-17h** |

---

## ⚠️ RISIKEN UND MITIGATION

| Risiko | Wahrscheinlichkeit | Mitigation |
|--------|-------------------|------------|
| Vulkan instabil | Mittel | Fallback: Phi-3.5-Vision ONNX |
| Performance unzureichend | Niedrig | CPU-Fallback möglich |
| Ollama-Update bricht Vulkan | Niedrig | Version pinnen |

---

## 📦 FALLBACK-OPTIONEN

Falls Ollama+Vulkan nicht funktioniert:

1. **llama-cpp-python + Vulkan** (siehe separate Doku)
2. **Phi-3.5-Vision ONNX DirectML** (bereits dokumentiert)
3. **Moondream CPU** (langsam aber stabil)

---

## ✅ ABNAHMEKRITERIEN

- [ ] Ollama mit Vulkan-Backend läuft
- [ ] Moondream beschreibt Bilder korrekt
- [ ] GPU wird verwendet (Task Manager)
- [ ] Performance <5s pro Bild
- [ ] Python-Wrapper funktioniert
- [ ] Integration in PB Studio erfolgreich

---

*Plan erstellt: 04.01.2026*
