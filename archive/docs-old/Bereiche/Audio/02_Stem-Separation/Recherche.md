# Stem Separation - Recherche

**Stand:** 04.01.2026
**Bereich:** Audio
**Risiko:** 🟡 Mittel

---

## 1. Aktueller Stand (NVIDIA)

Die NVIDIA-Version verwendet vermutlich:
- Demucs (Meta Research)
- PyTorch mit CUDA
- GPU-beschleunigte Inferenz

---

## 2. AMD Lösung: audio-separator

### WICHTIGER FUND!

Das Python-Paket `audio-separator` hat **offiziellen DirectML Support**!

**Repository:** https://github.com/nomadkaraoke/python-audio-separator

### Installation

```bash
pip install audio-separator[dml]
```

Dies installiert automatisch:
- `onnxruntime-directml`
- `torch-directml` (optional)
- UVR ONNX Modelle

### Unterstützte Modelle

| Modell | Beschreibung | Qualität |
|--------|--------------|----------|
| htdemucs | Hybrid Transformer | Sehr gut |
| htdemucs_ft | Fine-tuned | Beste |
| mdx_extra | MDX-Net | Gut |
| mdx_extra_q | Quantisiert | Schnell |

---

## 3. Code-Beispiel

```python
from audio_separator.separator import Separator

# Initialisieren
separator = Separator()

# Modell laden (automatischer Download)
separator.load_model(model_filename='htdemucs_ft.yaml')

# Audio trennen
outputs = separator.separate('input_audio.mp3')

# Ergebnis: Liste von Pfaden zu den Stems
# [vocals.wav, drums.wav, bass.wav, other.wav]
```

---

## 4. DirectML Konfiguration

audio-separator erkennt DirectML automatisch. Falls Probleme:

```python
import os
os.environ['AUDIO_SEPARATOR_DEVICE'] = 'dml'

from audio_separator.separator import Separator
sep = Separator(device='dml')
```

---

## 5. VRAM-Verbrauch

| Modell | VRAM |
|--------|------|
| htdemucs | ~1.5 GB |
| htdemucs_ft | ~2 GB |
| mdx_extra | ~1 GB |

✅ Passt problemlos in 16 GB!

---

## 6. Vergleich zu Demucs direkt

| Aspekt | Demucs direkt | audio-separator |
|--------|---------------|-----------------|
| AMD Support | ❌ Schwierig | ✅ Nativ |
| Installation | Komplex | Einfach |
| Modell-Auswahl | Begrenzt | Viele UVR |
| ONNX | Selbst konvertieren | Fertig |

**Empfehlung:** audio-separator verwenden!

---

## 7. Quellen

1. GitHub: https://github.com/nomadkaraoke/python-audio-separator
2. PyPI: https://pypi.org/project/audio-separator/
3. DirectML Extras: pyproject.toml zeigt `dml` Extra

---

## 8. Risiken

| Risiko | Wahrscheinlichkeit | Mitigation |
|--------|-------------------|------------|
| Modell-Inkompatibilität | Niedrig | Andere Modelle testen |
| VRAM-Probleme | Sehr niedrig | mdx_extra nutzen |
| Qualitäts-Unterschiede | Mittel | htdemucs_ft verwenden |

---

*Recherche: 04.01.2026*
