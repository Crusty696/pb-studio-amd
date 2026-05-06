# Scene Detection - Recherche

**Stand:** 04.01.2026
**Bereich:** Video
**Risiko:** 🟢 Niedrig

---

## 1. Aktueller Stand

Scene Detection verwendet:
- PySceneDetect
- OpenCV

---

## 2. GPU-Relevanz

**Minimal bis keine GPU-Abhängigkeit!**

PySceneDetect arbeitet primär auf CPU. OpenCV kann GPU nutzen, aber für Scene Detection nicht kritisch.

---

## 3. AMD Migration

### Erforderliche Änderungen: Minimal

PySceneDetect und OpenCV funktionieren identisch auf AMD-Systemen.

### Pakete:
- `scenedetect>=0.6.0`
- `opencv-python>=4.8.0`

---

## 4. Optionale GPU-Beschleunigung

Falls gewünscht, kann OpenCV mit DirectX-Backend kompiliert werden:
```python
import cv2
# Prüfen ob GPU verfügbar
print(cv2.cuda.getCudaEnabledDeviceCount())  # Nur für CUDA
```

Für AMD gibt es keine direkte OpenCV-GPU-Unterstützung unter Windows.

**Empfehlung:** CPU reicht völlig aus!

---

## 5. Validierung

| Aspekt | Status |
|--------|--------|
| PySceneDetect | ✅ CPU-basiert |
| OpenCV | ✅ CPU reicht |
| Keine Änderung nötig | ✅ |

---

*Recherche: 04.01.2026*
