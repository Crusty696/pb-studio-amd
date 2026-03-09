\# PB Studio - Plan zur Umstellung auf AMD-GPUs



\[cite\_start]\*\*Ziel:\*\* Anpassung der PB Studio-Anwendung von NVIDIA (CUDA) auf AMD (ROCm) unter Windows\[cite: 3, 4, 5].



---



\## 1. Hardware-Anforderungen

\* \[cite\_start]\*\*GPU:\*\* Moderne AMD-Grafikkarten (Radeon RX 7000 / 9000 Serie oder Ryzen AI-APUs)\[cite: 9, 10]. \[cite\_start]Ältere Karten wie RX 580 werden nicht unterstützt\[cite: 10].

\* \[cite\_start]\*\*VRAM:\*\* Mindestens 8 GB, empfohlen 12 GB+ (für Demucs und Bildmodelle)\[cite: 12, 13].

\* \[cite\_start]\*\*RAM:\*\* 16 GB (empfohlen 32 GB)\[cite: 14].

\* \[cite\_start]\*\*CPU:\*\* 4 Kerne (empfohlen 8 Kerne)\[cite: 15].

\* \[cite\_start]\*\*Betriebssystem:\*\* Windows 11 (64-Bit) mit ROCm-Preview\[cite: 16, 17].



---



\## 2. Software-Basis

\* \[cite\_start]\*\*Python:\*\* Version 3.11 (bleibt unverändert)\[cite: 19].

\* \*\*ROCm:\*\* Ersetzt CUDA. \[cite\_start]Installation über den AMD-Installer für Windows (empfohlen ROCm 6.1 für PyTorch 2.4.1)\[cite: 20, 21].

\* \[cite\_start]\*\*FFmpeg:\*\* Nutzung von AMF-Encodern (`h264\_amf`, `hevc\_amf`) statt NVENC\[cite: 22]. \[cite\_start]AV1 läuft über CPU (`libaom-av1`)\[cite: 23].



---



\## 3. Core-Python-Abhängigkeiten



\### Deep-Learning-Framework (PyTorch)

\[cite\_start]Die Installation erfolgt über den speziellen Index-URL für ROCm 6.1\[cite: 27].



| Paket | Version | Zweck | Besonderheit |

| :--- | :--- | :--- | :--- |

| \*\*torch\*\* | `2.4.1+rocm6.1` | Tensor/GPU | Setzt ROCm 6.1 voraus. Device string `cuda` funktioniert weiterhin. |

| \*\*torchvision\*\* | `0.19.1+rocm6.1` | RAFT/Bild | Muss zur Torch-Version passen. |

| \*\*torchaudio\*\* | `2.4.1+rocm6.1` | Audio | Optional, Version passend zu Torch. |

| \*\*transformers\*\* | `>=4.46.3` | CLIP, SigLIP | Plattformunabhängig. |



\### \[cite\_start]Numerische Bibliotheken \[cite: 29-32]

\* \*\*numpy:\*\* `< 2.0` (Wichtig für `madmom`).

\* \*\*scipy:\*\* `< 1.16` (Verhindert Warnungen).

\* \*\*numba:\*\* `~= 0.58`.



---



\## 4. Audio-ML-Pipeline

\* \[cite\_start]\*\*CPU-Tasks:\*\* Beat-Detection (`beatnet`, `madmom`, `librosa`) bleibt auf der CPU\[cite: 34].

\* \*\*Stem-Separation (Demucs):\*\* Version `4.0` unterstützt ROCm. \[cite\_start]Startparameter `-d cuda` nutzen\[cite: 35].

\* \[cite\_start]\*\*Patches:\*\* Python 3.11 Patches für `madmom` bleiben notwendig\[cite: 36].



---



\## 5. Video-AI-Analyse

1\.  \[cite\_start]\*\*Semantische Analyse (CLIP):\*\* Läuft via `transformers` auf AMD-GPU (keine Änderung nötig)\[cite: 40, 41].

2\.  \[cite\_start]\*\*Motion Analysis (RAFT):\*\* Läuft via `torchvision` auf AMD-GPU\[cite: 44].

3\.  \*\*Video Captioning (Moondream):\*\* \*\*Achtung:\*\* Aktuell kein bestätigter ROCm-Support. \[cite\_start]Vorerst auf CPU ausführen oder deaktivieren\[cite: 47, 48].

4\.  \[cite\_start]\*\*Szeneerkennung:\*\* `scenedetect` und `opencv` laufen primär auf CPU (evtl. AMF-Decoding via FFmpeg möglich)\[cite: 50].



---



\## 6. Datenbanken \& GUI

\* \[cite\_start]\*\*ChromaDB:\*\* Läuft CPU-basiert (File-Lock beachten: `close()` vor Exit)\[cite: 53].

\* \*\*GUI (PyQt6):\*\* Bleibt unverändert. \[cite\_start]Worker nutzen weiterhin `device="cuda"`, was intern auf ROCm gemappt wird\[cite: 56, 57].



---



\## 7. Rendering-Pipeline (FFmpeg)

\* \[cite\_start]\*\*Encoder:\*\* Wechsel von NVENC zu AMF (`h264\_amf`, `hevc\_amf`)\[cite: 59, 60].

\* \[cite\_start]\*\*Einstellungen:\*\* Nutzung von `-usage` und `-quality` statt NVIDIA-Presets\[cite: 61, 62].

\* \[cite\_start]\*\*AV1:\*\* Nur Software-Encoding (`libaom-av1`) möglich\[cite: 64].



---



\## 8. GPU-Monitoring

\* \[cite\_start]\*\*Tool:\*\* `pynvml` (NVIDIA) wird durch \*\*AMD SMI\*\* ersetzt\[cite: 67, 69].

\* \*\*Bibliothek:\*\* `amd-smi` (Teil der ROCm-Tools) oder Python-Wrapper.

\* \[cite\_start]\*\*Funktion:\*\* Auslesen von VRAM und Temperatur via `amdsmi\_get\_gpu\_vram\_usage`\[cite: 69].



---



\## 9. Geplante AI-Modelle (Smart Director)

\* \[cite\_start]\*\*CLAP (Audio):\*\* Läuft auf ROCm\[cite: 72].

\* \[cite\_start]\*\*SigLIP (Video):\*\* Läuft auf ROCm\[cite: 74].

\* \[cite\_start]\*\*Aesthetic Scorer:\*\* Läuft auf CPU\[cite: 75].

\* \*\*LoRA Training:\*\* `bitsandbytes` hat aktuell \*\*keinen\*\* Windows-ROCm Support. \[cite\_start]Training muss auf anderer Hardware erfolgen\[cite: 76, 77].



---



\## 10. Konfigurationsdatei (requirements\_amd.txt)



```text

\# Deep-Learning (ROCm 6.1)

\# Installation mit: --extra-index-url \[https://download.pytorch.org/whl/rocm6.1](https://download.pytorch.org/whl/rocm6.1)

torch==2.4.1+rocm6.1

torchvision==0.19.1+rocm6.1

torchaudio==2.4.1+rocm6.1

transformers>=4.46.3



\# Numerisch

numpy<2.0

scipy<1.16

numba==0.58



\# Audio

librosa>=0.10.1

soundfile>=0.12.1

beatnet>=1.1.1

demucs>=4.0



\# Video

opencv-python>=4.8

scenedetect>=0.6



\# Datenbanken

chromadb>=0.4

sqlalchemy>=2.0

alembic>=1.12



\# GUI

PyQt6>=6.6

pyqtgraph>=0.13



\# Utilities

psutil>=5.9

\# amd-smi-python (Teil des Treibers/ROCm)

Pillow>=10.0

tqdm>=4.66

