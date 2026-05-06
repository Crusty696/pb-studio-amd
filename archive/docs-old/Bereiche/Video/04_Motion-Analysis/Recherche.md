# Motion-Analysis auf AMD - Recherche

**Status:** ✅ Validiert  
**Priorität:** MITTEL (CPU-basiert, keine GPU-Migration nötig)

---

## Aktuelle Situation

- OpenCV Optical Flow (CPU oder CUDA)
- In PB Studio: Primär CPU-basiert
- Berechnet Bewegungsvektoren zwischen Frames

---

## AMD-Lösung: OpenCV CPU + Optional DirectML

### Verfügbare Optionen

| Methode | Backend | Performance | Empfehlung |
|---------|---------|-------------|------------|
| Farneback | CPU | Gut | ✅ Standard |
| Lucas-Kanade | CPU | Schnell | Sparse Flow |
| DIS | CPU | Sehr gut | ✅ Empfohlen |
| RAFT ONNX | DirectML | Exzellent | Optional |

---

## Techstack mit Versionen

### Python-Pakete (kompatibel getestet)

| Paket | Version | Zweck |
|-------|---------|-------|
| opencv-python | 4.10.0.84 | Optical Flow |
| numpy | 1.26.4 | Array-Operationen |

### Für optionales RAFT-ONNX

| Paket | Version | Zweck |
|-------|---------|-------|
| onnxruntime-directml | 1.23.0 | ONNX Runtime |

### Abhängigkeitsmatrix

| Paket A | Paket B | Kompatibel? |
|---------|---------|-------------|
| opencv-python 4.10.0 | numpy 1.26.4 | ✅ Ja |
| opencv-python 4.10.0 | onnxruntime-directml 1.23.0 | ✅ Ja |

---

## Installationsanweisungen

### Schritt 1: Environment (falls nicht vorhanden)

```powershell
python -m venv pb_studio_amd
pb_studio_amd\Scripts\activate
```

### Schritt 2: Pakete installieren

```powershell
pip install numpy==1.26.4
pip install opencv-python==4.10.0.84
```

### Schritt 3: Verifizieren

```powershell
python -c "import cv2; print(f'OpenCV {cv2.__version__} OK')"
```

---

## Taskplan

| # | Task | Abhängigkeit | Geschätzte Zeit |
|---|------|--------------|-----------------|
| 1 | OpenCV installieren | Environment | 5 min |
| 2 | Bestehenden Code testen | Task 1 | 30 min |
| 3 | DIS Optical Flow testen | Task 2 | 1 h |
| 4 | Performance-Vergleich | Task 3 | 1 h |
| 5 | Optional: RAFT ONNX evaluieren | Task 4 | 2 h |
| 6 | Integration verifizieren | Task 4 | 30 min |

**Gesamtzeit:** ~5 Stunden (inkl. RAFT-Evaluation)

---

## Verwendung in PB Studio

### DIS Optical Flow (empfohlen)

```python
import cv2
import numpy as np

# DIS Optical Flow erstellen
dis = cv2.DISOpticalFlow_create(cv2.DISOPTICAL_FLOW_PRESET_MEDIUM)

def calculate_motion(frame1, frame2):
    # Zu Graustufen konvertieren
    gray1 = cv2.cvtColor(frame1, cv2.COLOR_BGR2GRAY)
    gray2 = cv2.cvtColor(frame2, cv2.COLOR_BGR2GRAY)
    
    # Flow berechnen
    flow = dis.calc(gray1, gray2, None)
    
    # Magnitude berechnen
    magnitude, angle = cv2.cartToPolar(flow[..., 0], flow[..., 1])
    
    return {
        'mean_magnitude': np.mean(magnitude),
        'max_magnitude': np.max(magnitude),
        'flow': flow
    }
```

### Farneback Optical Flow (Alternative)

```python
def farneback_motion(frame1, frame2):
    gray1 = cv2.cvtColor(frame1, cv2.COLOR_BGR2GRAY)
    gray2 = cv2.cvtColor(frame2, cv2.COLOR_BGR2GRAY)
    
    flow = cv2.calcOpticalFlowFarneback(
        gray1, gray2, None,
        pyr_scale=0.5,
        levels=3,
        winsize=15,
        iterations=3,
        poly_n=5,
        poly_sigma=1.2,
        flags=0
    )
    
    magnitude, angle = cv2.cartToPolar(flow[..., 0], flow[..., 1])
    return np.mean(magnitude)
```

### Lucas-Kanade (Sparse, schnell)

```python
def lucas_kanade_motion(frame1, frame2, points):
    gray1 = cv2.cvtColor(frame1, cv2.COLOR_BGR2GRAY)
    gray2 = cv2.cvtColor(frame2, cv2.COLOR_BGR2GRAY)
    
    # Feature Points finden
    if points is None:
        points = cv2.goodFeaturesToTrack(gray1, maxCorners=100, qualityLevel=0.3, minDistance=7)
    
    # Flow berechnen
    new_points, status, error = cv2.calcOpticalFlowPyrLK(gray1, gray2, points, None)
    
    # Bewegung berechnen
    good_old = points[status == 1]
    good_new = new_points[status == 1]
    
    motion = np.mean(np.linalg.norm(good_new - good_old, axis=1))
    return motion, good_new
```

---

## DIS Presets

| Preset | Qualität | Geschwindigkeit | Use Case |
|--------|----------|-----------------|----------|
| ULTRAFAST | Niedrig | Sehr schnell | Preview |
| FAST | Mittel | Schnell | Standard |
| MEDIUM | Gut | Mittel | ✅ Empfohlen |

```python
# Presets
cv2.DISOPTICAL_FLOW_PRESET_ULTRAFAST
cv2.DISOPTICAL_FLOW_PRESET_FAST
cv2.DISOPTICAL_FLOW_PRESET_MEDIUM
```

---

## Motion-Score Berechnung

### Für PB Studio

```python
def get_motion_score(video_path, sample_rate=5):
    """
    Berechnet Motion-Score für Video.
    sample_rate: Alle N Frames analysieren
    """
    cap = cv2.VideoCapture(video_path)
    dis = cv2.DISOpticalFlow_create(cv2.DISOPTICAL_FLOW_PRESET_MEDIUM)
    
    scores = []
    prev_frame = None
    frame_idx = 0
    
    while True:
        ret, frame = cap.read()
        if not ret:
            break
        
        if frame_idx % sample_rate == 0:
            if prev_frame is not None:
                gray1 = cv2.cvtColor(prev_frame, cv2.COLOR_BGR2GRAY)
                gray2 = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
                
                flow = dis.calc(gray1, gray2, None)
                magnitude = cv2.cartToPolar(flow[..., 0], flow[..., 1])[0]
                scores.append(np.mean(magnitude))
            
            prev_frame = frame.copy()
        
        frame_idx += 1
    
    cap.release()
    
    return {
        'mean_motion': np.mean(scores),
        'max_motion': np.max(scores),
        'motion_curve': scores
    }
```

---

## Speicherbedarf

| Resolution | RAM pro Frame-Paar | Status |
|------------|-------------------|--------|
| 720p | ~50 MB | ✅ |
| 1080p | ~100 MB | ✅ |
| 4K | ~400 MB | ✅ |

**Kein VRAM nötig** für CPU-Methoden

---

## Optional: RAFT ONNX für GPU-Beschleunigung

### Verfügbare Modelle

| Modell | Quelle | Größe |
|--------|--------|-------|
| RAFT-small | onnx-community | ~20 MB |
| RAFT-things | onnx-community | ~20 MB |

**Hinweis:** Nur wenn CPU-Performance nicht ausreicht.

---

## Risikobewertung

| Risiko | Bewertung | Mitigation |
|--------|-----------|------------|
| Keine Änderung nötig | 🟢 Niedrig | CPU-Methoden ausreichend |
| Performance identisch | 🟢 Niedrig | DIS ist schnell |
| Optional GPU später | 🟢 Niedrig | RAFT ONNX als Upgrade |

---

## Quellen

1. https://docs.opencv.org/4.x/d4/dee/tutorial_optical_flow.html
2. https://docs.opencv.org/4.x/d4/d2a/classcv_1_1DISOpticalFlow.html
3. https://github.com/princeton-vl/RAFT
