# SigLIP Text Capability — 2026-08-11

## Asset-Entscheidung

- `config/directml-model-assets.json` und das registrierte Bundle enthalten kein
  freigegebenes SigLIP-Text-ONNX-Artefakt.
- Eine bloß lokal vorhandene `siglip_text.onnx` aktiviert die Capability nicht.
- Aktivierung setzt Manifest-Registrierung, freigegebenen Bundle-Status,
  Zielpfadbindung und übereinstimmenden SHA-256 voraus.
- Bei fehlendem oder abweichendem Asset bleibt Textsemantik fail-closed
  unavailable; es gibt keinen CPU-, PyTorch-, CUDA- oder ROCm-Fallback.
- Die Unavailable-Warnung wird thread-sicher pro Capability-Generation
  dedupliziert.

## Fokussierter Verify-Receipt

- `pytest Tests/test_siglip_text_capability.py Tests/test_siglip_video.py -q`
- Ergebnis: 20 passed, 4 skipped, 0 failures.
- T016: abgeschlossen. Scene-Ground-Truth T017 wurde separat geprüft.
