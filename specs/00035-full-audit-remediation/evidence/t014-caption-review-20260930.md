# T014 – Caption-Plausibilitätsprüfung (2026-09-30)

## Provider-Provenienz
- LM Studio, geladenes Modell `qwen3.5-9b` (`lmstudio-community/Qwen3.5-9B-GGUF`, Q8_0, VLM),
  Lizenz laut Hugging-Face-Metadaten **Apache-2.0**.
- Runtime `llama.cpp-win-x86_64-vulkan-avx2@2.47.0` (`llama-server.exe` PID 11596).
  **Vulkan, nicht ROCm und nicht DirectML.** Um 07:01 belegte der Prozess 9.822 MB
  dediziert auf LUID `0x000116f2` (die einzige Karte mit >512 MB, also die RX 7800 XT).
  Um ~07:40 meldeten die Windows-GPU-Zähler für alle Adapter 0 MB – Zähler dort unzuverlässig.
- Eine DirectML-Caption-Strecke gibt es im Repo derzeit nicht (Moondream-Decoder fehlt,
  `caption_ready=false`).
- **Policy-Entscheid David, 2026-09-30:** „Ja“ – Vulkan-Inferenz über LM Studio ist für die
  Caption-Strecke zulässig. Ausnahme zu IRON RULE 1 gilt nur für LLM/VLM über LM Studio (Vulkan);
  ROCm bleibt verboten; alle ONNX-Pfade bleiben DirectML. Eingetragen in `CLAUDE.md` §2 und
  `clarifications.md`.
- Konfiguration nach Commit `8a91eed`: alle Caption-/Chat-/Brain-Aufgaben auf `qwen3.5-9b`.

## Methode
- 12 Clips aus Projekt 10 (`t013_psy_20260930`), jeder ~4. Clip nach `media.id`.
- Pro Clip: gespeicherte Produktions-Tags (Lauf vom 30.09. mit `8a91eed`) und ein frischer
  Produktionsaufruf `extract_tags_and_model_via_lmstudio_async` auf dem Mittelbild.
  Frische Aufrufe: 1,05–2,46 s je Bild, Modell jedes Mal `qwen3.5-9b`.
- Kontaktbögen (20/50/80 %) und Rohdaten: `t014-caption-review-20260930/`
  (`clip_<id>.jpg`, `t014_results.json`).
- Bewertung durch Claude nach Sichtprüfung der Kontaktbögen. **Kein menschliches Urteil** –
  Davids Bewertung steht aus.

## Ergebnis (Claude-Sichtprüfung)
Tags gesamt: gespeichert 120, frisch 114.

| | falsch | unsicher | Rest plausibel |
|---|---:|---:|---:|
| gespeichert | 2 | 6 | 112 |
| frisch | 5 | 4 | 105 |

Hauptmotiv (Person/Anzahl-Personen/Szene) in 11/12 Clips richtig; Ausnahme 939.

Falsch:
- 935 gespeichert „schwarze haut“ – Figur von hinten, Hautton nicht erkennbar schwarz.
- 939 gespeichert „zwei frauen“ – nur eine Frau im Bild.
- 923 frisch „dunkle haut“, „rote lippen“ (Lippen sind dunkel), „durchsichtige weiße flügel“ (Ärmel, keine Flügel).
- 927 frisch „schwarze haut“ – von hinten, violettes Licht.
- 959 frisch „schwarze strumpfhosen mit tattoos“ – nackte Beine mit Tattoos.

Unsicher: 919 „schwarze lederkleidung“, „rücken zur kamera“; 923 „person in weißem gewand“;
935 „kurze dunkle haare“ (Dutt); 955 „metallischer rüstung“ (Körperbemalung?);
959 „grünes oberteil mit ärmeln“; 963 „bauchtänzerin“, „schwert in der hand“.

Muster: Hautfarbe wird unter farbigem Licht/von hinten geraten; einzelne halluzinierte Details;
Tags zwischen zwei Läufen desselben Clips nicht identisch (nicht deterministisch).

Nachtrag GUI-Lauf (5 neue Clips `test_*`, `media.id` 975–979): 977 enthält gleichzeitig
„keine personen“ und „elf-frau“; 978 enthält englische Tags („fairy-like figures“, „floating women“,
„glowing dresses“) trotz deutscher Ausgabe der übrigen.

## Status
Plausibel, aber **nicht abgeschlossen**: T014 verlangt menschlich geprüfte Labels.
Policy geklärt (s. o.). Offen: Davids inhaltliche Bewertung (richtig/falsch/unsicher) der
Auswahl in `t014-caption-review-20260930/`.
