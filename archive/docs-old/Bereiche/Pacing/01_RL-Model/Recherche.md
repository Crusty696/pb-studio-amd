# RL-Model - Recherche

**Stand:** 04.01.2026
**Bereich:** Pacing
**Risiko:** 🟢 Niedrig

---

## 1. Aktueller Stand

Das RL-Model (Reinforcement Learning) wird verwendet für:
- Pacing-Entscheidungen
- Schnitt-Timing-Optimierung

---

## 2. GPU-Relevanz

**NIEDRIG**

RL-Modelle für Pacing sind typischerweise klein:
- Wenige Layer
- Kleine State-Spaces
- Schnelle Inferenz auch auf CPU

---

## 3. AMD Lösung

### Empfehlung: CPU-Inferenz

Da das RL-Modell klein ist, empfehle ich:
1. ONNX-Export des PyTorch-Modells
2. ONNX Runtime CPU-Execution
3. GPU nur optional (DirectML)

### Export-Workflow:
```python
import torch

# Original PyTorch Model laden
model = RLModel()
model.load_state_dict(torch.load('rl_model.pth'))
model.eval()

# Nach ONNX exportieren
dummy_input = torch.randn(1, state_dim)
torch.onnx.export(
    model,
    dummy_input,
    'rl_model.onnx',
    opset_version=17
)
```

---

## 4. Inferenz

```python
import onnxruntime as ort

# CPU Session (schnell genug!)
session = ort.InferenceSession(
    'rl_model.onnx',
    providers=['CPUExecutionProvider']
)

# Oder DirectML wenn gewünscht
session = ort.InferenceSession(
    'rl_model.onnx',
    providers=[
        ('DmlExecutionProvider', {'device_id': 0}),
        'CPUExecutionProvider'
    ]
)
```

---

## 5. Validierung

| Aspekt | Status |
|--------|--------|
| Kleines Modell | ✅ |
| CPU ausreichend | ✅ |
| ONNX-Export möglich | ✅ |
| Risiko niedrig | ✅ |

---

*Recherche: 04.01.2026*
