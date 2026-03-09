# Ollama + Vulkan Installation für AMD RX 7800 XT

**Stand:** 04.01.2026 (KORRIGIERT)  
**Ollama Version:** v0.13.5 (aktuell)  
**Vulkan-Support:** ab v0.12.11

---

## 📋 VORAUSSETZUNGEN

| Komponente | Anforderung |
|------------|-------------|
| Windows | 10/11 (64-bit) |
| GPU | AMD RX 7800 XT |
| Treiber | Adrenalin 24.8.1+ |
| Vulkan | Im Treiber enthalten |
| RAM | Mind. 16 GB empfohlen |
| Ollama | v0.12.11+ (für Vulkan) |

---

## 🔧 INSTALLATION

### Schritt 1: Ollama installieren

```powershell
# Option A: Via winget (empfohlen)
winget install Ollama.Ollama

# Option B: Manueller Download
# https://ollama.com/download/windows
```

**Aktuelle Version prüfen:**
```powershell
ollama --version
# Sollte v0.13.5 oder höher sein
```

### Schritt 2: Vulkan-Backend aktivieren

**WICHTIG:** Vulkan-Support ist ab Ollama v0.12.11 verfügbar!

```powershell
# Temporär (nur diese Session)
$env:OLLAMA_VULKAN = "1"

# ODER permanent als System-Variable
[System.Environment]::SetEnvironmentVariable("OLLAMA_VULKAN", "1", "User")
```

### Schritt 3: Ollama Server starten

```powershell
# Neues Terminal öffnen (nach Setzen der Variable!)
ollama serve
```

**Erwartete Ausgabe (v0.13.5):**
```
Vulkan: found 1 device(s)
Vulkan: Device: AMD Radeon RX 7800 XT (driver: xxx)
```

### Schritt 4: Moondream laden

```powershell
# In neuem Terminal
ollama pull moondream
```

### Schritt 5: Test durchführen

```powershell
# Text-Test
ollama run moondream "Hello, describe what you can do."

# Bild-Test (mit Beispielbild)
ollama run moondream "Describe this image:" < C:\path\to\image.jpg
```

---

## 🐍 PYTHON-INTEGRATION

### Installation

```powershell
# Aktuelle Version: ollama 0.6.1
pip install ollama>=0.6.0 pillow httpx
```

### Beispiel-Code

```python
import ollama
import base64

def describe_image(image_path: str, prompt: str = "Describe this image.") -> str:
    """Beschreibt ein Bild mit Moondream via Ollama."""
    
    # Bild als Base64 laden
    with open(image_path, "rb") as f:
        image_data = base64.b64encode(f.read()).decode()
    
    # Anfrage an Moondream
    response = ollama.chat(
        model="moondream",
        messages=[{
            "role": "user",
            "content": prompt,
            "images": [image_data]
        }]
    )
    
    return response["message"]["content"]

# Verwendung
result = describe_image("test.jpg", "What objects are in this image?")
print(result)
```

---

## 🔍 FEHLERBEHEBUNG

### Problem: "Vulkan not found"

**Ursachen:**
1. Ollama-Version zu alt (<v0.12.11)
2. AMD-Treiber veraltet
3. OLLAMA_VULKAN nicht gesetzt

**Lösung:**
```powershell
# 1. Version prüfen
ollama --version
# Falls < 0.12.11: Update über winget install Ollama.Ollama

# 2. Vulkan-Variable prüfen
echo $env:OLLAMA_VULKAN
# Muss "1" sein

# 3. Vulkan SDK installieren (falls nötig)
# https://vulkan.lunarg.com/sdk/home
```

### Problem: "GPU not detected"

**Lösung:**
```powershell
# Vulkan-Geräte prüfen
vulkaninfo --summary

# Falls nicht gefunden: Treiber neu installieren
```

### Problem: "Out of memory"

**Lösung:**
- Andere GPU-intensive Programme schließen
- Moondream VRAM: ~2-3 GB
- RX 7800 XT hat 16 GB → Sollte nie passieren

### Problem: Langsame Performance

**Checkliste:**
1. `$env:OLLAMA_VULKAN` = "1"?
2. Ollama >=v0.12.11?
3. Adrenalin-Treiber aktuell?

---

## 📊 PERFORMANCE-ERWARTUNGEN

| Metrik | Wert |
|--------|------|
| Erste Inferenz | 3-5 Sekunden (Modell laden) |
| Folgende Inferenzen | 1-3 Sekunden |
| VRAM-Verbrauch | ~2-3 GB |
| GPU-Auslastung | 40-80% während Inferenz |

---

## 📌 VERSIONS-HISTORIE

| Ollama | Feature |
|--------|---------|
| v0.12.11 | Vulkan-Support eingeführt |
| v0.13.0 | Stabilisierung |
| v0.13.5 | Aktuell (Stand: Jan 2026) |

---

## 🔗 QUELLEN

1. https://ollama.com/download
2. https://github.com/ollama/ollama/releases
3. https://docs.ollama.com/gpu
4. https://ollama.com/library/moondream
5. https://pypi.org/project/ollama/

---

*Dokumentation aktualisiert: 04.01.2026*
