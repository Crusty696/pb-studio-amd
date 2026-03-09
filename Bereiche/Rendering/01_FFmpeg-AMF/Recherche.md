# FFmpeg AMF - Recherche

**Stand:** 04.01.2026
**Bereich:** Rendering
**Risiko:** 🟢 Niedrig

---

## 1. Aktueller Stand (NVIDIA)

NVIDIA-Version verwendet:
- FFmpeg mit NVENC (h264_nvenc, hevc_nvenc)
- GPU-beschleunigtes Encoding

---

## 2. AMD Lösung: AMF

### AMD Advanced Media Framework

AMD bietet vollständige FFmpeg-Integration über AMF:

| Encoder | Codec | RX 7800 XT |
|---------|-------|------------|
| h264_amf | H.264/AVC | ✅ |
| hevc_amf | H.265/HEVC | ✅ |
| av1_amf | AV1 | ✅ (RDNA3!) |

**Quelle:** https://github.com/GPUOpen-LibrariesAndSDKs/AMF

---

## 3. FFmpeg Parameter für 1080p

### H.264 (Beste Kompatibilität)
```bash
ffmpeg -i input.mp4 \
  -c:v h264_amf \
  -quality quality \
  -rc vbr_peak \
  -b:v 8000000 \
  -maxrate 12000000 \
  -bufsize 16000000 \
  -g 120 \
  output.mp4
```

### H.265 (Bessere Kompression)
```bash
ffmpeg -i input.mp4 \
  -c:v hevc_amf \
  -quality quality \
  -rc vbr_peak \
  -b:v 6000000 \
  -maxrate 10000000 \
  output.mp4
```

### AV1 (Beste Qualität - NUR RDNA3!)
```bash
ffmpeg -i input.mp4 \
  -c:v av1_amf \
  -quality quality \
  -b:v 5000000 \
  output.mp4
```

---

## 4. AMF Optionen

### Quality Presets
| Preset | Geschwindigkeit | Qualität |
|--------|-----------------|----------|
| speed | Schnellste | Niedrig |
| balanced | Mittel | Mittel |
| quality | Langsam | Beste |

### Rate Control
| Mode | Beschreibung |
|------|--------------|
| cqp | Constant QP |
| cbr | Constant Bitrate |
| vbr_peak | Variable Bitrate (empfohlen) |
| vbr_latency | VBR Low Latency |

---

## 5. NVENC → AMF Mapping

| NVENC | AMF | Hinweis |
|-------|-----|---------|
| -preset p4 | -quality balanced | Ähnlich |
| -preset p7 | -quality quality | Beste Qualität |
| -rc vbr | -rc vbr_peak | Ähnlich |
| -b:v | -b:v | Identisch |

---

## 6. 1080p Alignment Hinweis

**WICHTIG:** AMD padded 1080p intern auf 1082p (64x16 Alignment)

Das ist normal und beeinflusst die Ausgabe nicht negativ.

---

## 7. FFmpeg Build prüfen

```bash
ffmpeg -encoders | findstr amf
```

**Erwartete Ausgabe:**
```
V..... h264_amf    AMD AMF H.264 Encoder
V..... hevc_amf    AMD AMF HEVC Encoder
V..... av1_amf     AMD AMF AV1 Encoder
```

Falls nicht vorhanden → FFmpeg mit AMF Support neu installieren.

---

## 8. Quellen

1. AMD AMF Wiki: https://github.com/GPUOpen-LibrariesAndSDKs/AMF/wiki
2. FFmpeg Docs: https://trac.ffmpeg.org/wiki/Hardware/AMF
3. Encoder Settings: https://github.com/GPUOpen-LibrariesAndSDKs/AMF/wiki/Recommended-FFmpeg-Encoder-Settings

---

## 9. Validierung

| Aspekt | Status |
|--------|--------|
| h264_amf verfügbar | ✅ |
| hevc_amf verfügbar | ✅ |
| av1_amf verfügbar | ✅ (RDNA3) |
| 1080p Support | ✅ |

---

*Recherche: 04.01.2026*
