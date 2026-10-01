# T014 – Caption-Prüfung, Neulauf mit aktuellem Prompt (2026-10-01)

## Lauf
- LM Studio, `qwen3.5-9b` (Q8_0, VLM, Apache-2.0), Runtime
  `llama.cpp-win-x86_64-vulkan-avx2-2.49.0` (Prozesszeile geprüft: Vulkan, nicht ROCm).
  ComfyUI vorher beendet (Davids Freigabe), VRAM vor dem Laden 880 MB belegt.
- Aktueller Produktionsstand (Prompt, Parser, Merge inkl. Wortreihenfolge-Fix `58b8bca`).
- `scripts/dev/t014_caption_eval.py --project-id 10 --clips 12`, DB nur lesend, isoliertes APPDATA.
  Je Clip 3 Bilder (20/50/80 %), je Bild ein Produktionsaufruf (1,5–3,7 s), dazu
  `live_merged` = die Liste, die die App für den Clip speichern würde.
- **Clip-Auswahl weicht vom 30.09. ab** (919, 924, 929 … 974 statt 919, 923 …): das Projekt
  hat seitdem 5 Clips mehr, die Schrittweite verschiebt sich. Bilder + Rohdaten in
  `t014-caption-review-20261001/` (`clip_<id>.jpg`, `results.json`).
- Bewertung unten: **Claude-Sichtprüfung, kein menschliches Urteil.** T014 braucht weiter
  Davids Bewertung.

## Pro Clip (gespeicherte Liste = was die App ablegt)

| Clip | Tags (App-Liste) | Einschätzung Claude |
|---|---|---|
| 919 | high heels, nebel am boden, zwei scheinwerferlichter, mystische atmosphäre, frau mit blonden haaren, schwarze lederkleidung, schwarzer glitzer-korsett-top, strümpfe und high heels, tanzbewegung, steht im wald | Gut. Blonde Frau, Glitzer-Korsett, Strümpfe, High Heels, Nebel, Scheinwerfer, Tanz stimmen. Unsicher: „lederkleidung“ (eher Glitzer/Lack), „steht im wald“ (Bühne vor Wald). Doppelt: „high heels“ / „strümpfe und high heels“. |
| 924 | grünes leuchten am boden, geheimnisvolle stimmung, kühle farbpalette, hornträgerin, vier frauen mit hörnern, drei horntragende frauen, elfenohren, tanzende pose, mystische tanzhaltung, dunkles haar | Inhaltlich richtig (Hörner, Elfenohren, leuchtende Bodenmuster, Tanz). Schwäche: „vier“ und „drei“ Frauen gleichzeitig – je Bild verschieden viele sichtbar, beides bleibt stehen. |
| 929 | mystische atmosphäre, magischer zauber, grünes und lila licht, schwarze outfits mit glitzerbesatz, kühle farbpalette aus blau-grün-tönen, kronen auf dem kopf, futuristische naturästhetik, tiefes grün und neonfarben, dunkle baumstämme im vordergrund, düsterer hintergrund | Plausibel (Neonlicht, Glitzer-Outfits, Krone, Bäume). Fehlt: die tanzenden Frauen selbst; viele Stimmungs-Tags. |
| 934 | frau von hinten, digitale kunst, frau mit zopf, arme ausgestreckt, schwarze kleidung, schwarzes haar, mystischer wald, rücken zur kamera, langer schwarzer rock, neon-schilder an bäumen | Gut, alles sichtbar. Leicht doppelt: „frau von hinten“ / „rücken zur kamera“. |
| 939 | dunkle kleidung, moosbedeckter boden, geheimnisvolle stimmung, silhouette frau, schwarzer fließender kleidung, schwarzer umhang, rücken zur kamera, lange haare, alte steinerne säulen, steht im profil | Gut. Fehlt: der leuchtende Kristall (stand in Einzelbildern, fiel beim Zusammenführen raus). |
| 944 | mystische gesten, neblige atmosphäre, verfallene gotische bögen, silhouetten, nebliger waldtempel, dichter wald, vier figuren, tiefgrünes und bläuliches licht, grünes und blaues licht, dunkle gewänder | Szene richtig (Ruine, Nebel, Silhouetten, grünes Licht). **Falsch:** „vier figuren“ – es sind deutlich mehr. Doppelt: zwei Licht-Tags. |
| 949 | distant city lights, leuchtende pflanzen, glowing green leaves, glowing plants, große blätter, large dark lotus-like foliage, bioluminescent leaves, nächtliche landschaft, bioluminescent plant installation, night garden | Inhalt stimmt (leuchtende Pflanzen, große Blätter, Nacht, Lichter am Horizont). **Fehler:** 6 von 10 Tags englisch (Bild 2+3 kamen englisch zurück), dazu Dubletten über Sprachgrenzen. |
| 954 | keine personen, person, person mit federkronenkleidung, mystische grotte, zwei beine, stehend am wasser, wehende weidenzweige, barfuß, blick auf leuchtendes altarobjekt, leuchtende blumen | Clip mit 3 verschiedenen Szenen; Einzel-Tags stimmen. **Fehler:** „keine personen“ (nur Bild 1) steht neben „person“ – Widerspruch. |
| 959 | frau, kniend, dunkles haar, magische atmosphäre, mystischer wald, frau mit dunklem haar, schwarze bikini-top und shorts, tätowierte arme und beine, grünes neonlicht, grüner umhang | Gut (kniend, Tattoos, Bikini, Neon). Unsicher: „grüner umhang“ – türkises Tuch. Doppelt: „frau“ / „frau mit dunklem haar“. |
| 964 | barfuß, frau, leuchtende pilze, mystische atmosphäre, eine frau, schwarze crop-top, person, silhouette, schwarzer rock mit schleife, schwarze bikini-top und shorts | Inhalt richtig (Frau, barfuß, leuchtende Pilze, Crop-Top). Unsicher: „rock mit schleife“, „shorts“ (langer transparenter Rock). Vier Tags für dieselbe Person: frau / eine frau / person / silhouette. |
| 969 | frau, dunkle haut, moosbedeckter boden, dichte vegetation, geheimnisvolle atmosphäre, eine frau, langhaarig, kniet auf moos, schwarze bikini-top und bottoms, streckt hand aus | Wald, Moos, Bikini, lange Haare, ausgestreckte Hand stimmen. **Falsch:** „dunkle haut“ (helle Haut). Unsicher: „kniet“ (eher gebückt/gehend). Fehlt: gemusterter Mantel, großer Pilz. |
| 974 | eine frau, tanzpose, mystischer wald, alte säulen, hängende ranken, frau, sitzend, dunkle haut, schwarze bikini-top, dunkle kleidung mit fransen | Gut (Tanz, Säulen, Ranken, kauernd in Bild 2). Unsicher: „dunkle haut“ (Gegenlicht-Silhouette), „fransen“ (transparenter Rock). Doppelt: „eine frau“ / „frau“. |

## Zählung (120 gespeicherte Tags, Claude)
- **falsch: 3** (944 „vier figuren“, 954 „keine personen“, 969 „dunkle haut“)
- **unsicher: 9** (919 ×2, 924 Anzahl, 959, 964 ×2, 969 „kniet“, 974 ×2)
- **Sprache falsch: 6** (949, englisch)
- **Dubletten/Synonyme: ~12** (frau/eine frau/person, Licht-Doppel, high heels …)
- Hauptmotiv (Personen/Szene) in **12/12** Clips richtig erkannt.

## Erkenntnisse (für spätere Fixes, nicht umgesetzt)
1. **Zusammenführen behält Widersprüche** („keine personen“ + „person“, „vier“ + „drei“ Frauen).
2. **Englische Antworten** werden nicht verworfen oder übersetzt (949: ganze Bilder englisch).
3. **Synonym-Dubletten** „frau“ / „eine frau“ / „person“ fallen nicht zusammen (Artikel „eine“ zählt als Wort).
4. **Hautfarbe unter farbigem Licht / Gegenlicht** wird weiterhin geraten (wie am 30.09.).
5. Detail-Tags aus späteren Bildern fallen beim Merge zugunsten mehrfach gesehener Stimmungs-Tags raus (Kristall 939, Pilz 969).

## Menschliche Bewertung (David, 2026-10-01)
- Gesehen: Kontaktbögen **919, 924, 944, 954, 969, 974** zusammen mit der Claude-Einschätzung
  aus der Tabelle oben (per Handy übermittelt).
- Urteil, wörtlich: **„Ja“** – Bestätigung, dass Tags und Einschätzung passen.
- Damit sind für diese 6 Clips die Einstufungen richtig/falsch/unsicher menschlich bestätigt,
  darunter alle drei als falsch markierten Fälle (944, 954, 969) und beide „dunkle haut“-Fälle
  (969, 974).
- **Grenze:** Die übrigen 6 Clips (929, 934, 939, 949, 959, 964) sind nur von Claude bewertet.
  Davids Urteil ist eine Gesamtbestätigung, keine eigene Tag-für-Tag-Auszählung.

## Status
T014 abgenommen am 2026-10-01: konformer, geladener Provider (LM Studio Vulkan, `qwen3.5-9b`)
mit Provenienz, Einstufung richtig/falsch/unsicher je Clip, menschlich bestätigt an 6 von 12
Clips. Die Merge-Schwächen oben sind als Folgearbeit erfasst.
