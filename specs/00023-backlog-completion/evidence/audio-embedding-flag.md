# T007: has_audio_embedding

Implementiert 2026-09-07. `GET /audio/clips` leitet das Flag aus einem
vorhandenen Cache-Eintrag der aktuellen CLAP-Modellidentitaet und dem
Medientyp `audio` ab. Ein alter In-Memory-Wert kann deshalb weder falsch gruen
noch falsch rot bleiben. Fehlender Hash, Cache oder Lesefehler ergibt
fail-closed `False`.

Der Producer liefert jetzt `True` nur bei einem bereits gueltigen Audio-Eintrag
oder nach erfolgreichem `EmbeddingCache.store`. Der Analysepfad uebernimmt
diesen belegten Rueckgabewert in seine Clip-Kopie; Analysefehler bleiben davon
unberuehrt.

Isolierte Verifikation mit eigenem LOCALAPPDATA/APPDATA/basetemp und
`--noconftest`: 8 passed, darunter Listing-Wahrheit, Modell-/Medientypbindung,
fail-closed Cachefehler, erfolgreicher Store sowie Audio-Resume- und
Batch-Interrupt-Vertraege. Beide geaenderten Dateien kompilieren.

Zwei Testanlauf-Fehler wurden nicht verschwiegen: zuerst importierte
`from backend.routers` das APIRouter-Objekt statt des Moduls; danach brauchte
der direkte Funktionsaufruf explizite page/limit-Werte statt FastAPI-Query-
Defaults. Beide Ursachen wurden getrennt korrigiert; der dritte Lauf war gruen.
Eine neue Vollsuite nach dieser Aenderung bleibt T021.
