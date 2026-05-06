# Hirn-Modul — User Guide

## Was ist das Hirn?

Das Hirn lernt aus deinen Klicks, welche Cuts gut zu welchem Audio-Kontext
passen. Kein klassisches Training — du bewertest 4-stufig, das Hirn passt
17 Achsen-Gewichte über 5 Kontext-Levels an.

## Cold-Start

Bei Erst-Installation gibt es null Klick-Daten. Das Hirn nutzt sinnvolle
Defaults aus den existierenden Trigger-Settings (Audio) bzw. neutralen
0.5 (Video-Achsen). Sobald für eine Achse + Kontext mindestens **10 Samples**
existieren, wird der Default durch den gelernten Posterior Mean ersetzt.

## Wann lohnt eine Lern-Session?

- **Sehr früh** (0-50 Klicks): Cold-Start dominiert — viel zu lernen,
  Lern-Session-Dialog priorisiert die unsichersten Cuts (Bayes-Varianz).
- **50-500 Klicks**: Häufige Kontexte stabilisieren sich. Lern-Session
  liefert seltenere Kontexte (z.B. Drop+Dark+Extreme-Motion).
- **>500 Klicks**: Diminishing returns. Klicke gezielt bei Cuts, die
  überraschen oder schlecht wirken.

Pro Session = 15 Klicks → 17 Achsen × 5 Levels × 15 = **1275 Bucket-Updates**.

## 4-Klick-Mapping

| Klick                | α-Gewinn | β-Gewinn | Bedeutung |
|----------------------|----------|----------|-----------|
| 1 Passt perfekt      | +2.0     | 0        | starkes positives Signal |
| 2 Passt              | +1.0     | 0        | schwaches positives Signal |
| 3 Passt nicht ganz   | 0        | +1.0     | schwaches negatives Signal |
| 4 Passt gar nicht    | 0        | +2.0     | starkes negatives Signal |

Hotkeys 1-4 während Wiedergabe.

## Confidence-Balken (geplant)

Über jedem Cut zeigt ein dünner Balken den finalen Brain-Score:

- **Rot**: niedrige Score / hohe Unsicherheit
- **Gelb**: mittlere Score
- **Grün**: hohe Score / Hirn ist sehr sicher

Niedrige Confidence ist kein Bug — es heißt: hier lernst du am meisten.

## Reset

Bei `Reset` werden `weights.db` + `patterns.db` geleert.
**Embedding-Cache bleibt** — das spart Zeit bei Re-Imports.
Cold-Start-Defaults sind nach dem Reset wieder aktiv.

## Datenpfade

- `<Projekt>/embeddings.db` — Vektoren + Units (mit Projekt löschbar)
- `<Projekt>/state.db` — Timeline + Klick-Roh-Log
- `%APPDATA%\PB_Studio\brain\weights.db` — gelernte Gewichte (app-global)
- `%APPDATA%\PB_Studio\brain\patterns.db` — Profil-Korrelationen
- `%APPDATA%\PB_Studio\brain\embedding_cache.db` — Hash → .npy-Index
- `%APPDATA%\PB_Studio\brain\embeddings\` — Embedding-Files

## Backup

Manuell:
```python
from pb_studio.storage.backup import backup_brain_store, prune_backups
backup_brain_store(r"%APPDATA%\PB_Studio\brain", r"%APPDATA%\PB_Studio\backups")
prune_backups(r"%APPDATA%\PB_Studio\backups", keep=4)
```

Automatik wöchentlich kann via Windows Task Scheduler aufgerufen werden.

## Recovery

Falls `weights.db` korrupt: beim nächsten Start wird sie zu
`weights.db.corrupt` umbenannt und ein leeres Schema neu angelegt
(Cold-Start, alle Klick-Daten verloren).

Falls Backup vorhanden: manuell zurückkopieren VOR App-Start.
