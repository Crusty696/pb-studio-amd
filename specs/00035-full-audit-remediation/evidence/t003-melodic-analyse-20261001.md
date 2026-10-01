# T003 – Analyse des Melodic-Holdouts (2026-10-01, Cowork)

Frage: warum bleibt `melodic_bm` (10 Titel „Melodic – Techno“, auf 124 BPM gezogen,
56-s-Blenden) mit F1 0,556 unter dem Ziel 0,65? Nur lesend auf den gecachten Merkmalen
(`%TEMP%\pbcw-t003-lab\h_melodic_bm.npz`), Code unverändert.

## Befund (Produktionslauf, Toleranz 15 s)

```
Referenz (Blendenmitte)  502   996  1348  1745  2036  2398  2699  2916  3232
gefunden            119  528  1000  1357  1746  2056  2405  2718  2921    –
Abstand                   26     4     9     1    20     7    19     5   311
```

TP 5 / FP 4 / FN 4. Die vier Fehlerarten:

1. **Drei Grenzen liegen in der Blende, aber hinter ihrer Mitte** (+26, +20, +19 s; halbe
   Blendenlänge 28 s). Die Zerlegung setzt die Grenze dorthin, wo die *Harmonie* wechselt;
   beim ersten Fall liegt sie praktisch am Blendenende (528 vs. Titelende 530,2 s). Die
   ankommenden Titel beginnen offenbar perkussiv, ihr harmonischer Teil setzt erst gegen
   Ende der Blende ein. Ob das ein Fehler ist, hängt an der Konvention der Referenz
   („Blendenmitte“). Bei 32-s-Blenden (psy-Mixe) tritt das nicht auf.
2. **Eine Fehlgrenze bei 119 s** im ersten Titel (Intro → Hauptthema), genau an der
   Mindestabschnittslänge von 120 s.
3. **Letzter Wechsel (3232 s) fehlt.**

Diagnosewert: Anteil der Referenzgrenzen mit einer Erkennung innerhalb ±30 s
(„in der Blende“) – melodic 8/9, über alle sieben Mixe 0,905. Das ist **keine**
Abnahmemetrik, nur eine Einordnung.

## Gemessen und verworfen

`scripts/dev/t003_refine_lab.py`: Nachverortung jeder Grenze auf den Vorzeichenwechsel
„passt besser zum linken als zum rechten Titelkern“ (Kerne ohne ±30–60 s um die Grenze,
Suchfenster ±30–60 s). Ergebnis über alle sieben Mixe: Mittel-F1 **0,806 → 0,790**,
melodic unverändert 0,556, techno 0,889 → 0,778. Verworfen. Die Zerlegung liegt damit
bereits am Übergang der Harmonie; mehr Präzision gibt diese Merkmalsart nicht her.

Bewusst **nicht** gemacht: Parameter (Mindestlänge, Preis, Randsperre) an diesem Mix
nachstellen. Das würde den letzten unberührten Holdout verbrauchen und die Zahl schönen,
ohne dass ein echter DJ-Mitschnitt dafür spricht.

## Stand T003

Offen. Weiter nur mit einem von beidem (Davids Entscheid):
- echter DJ-Mitschnitt mit von Hand gesetzten Wechselzeiten
  (Vorlage `t003-referenz-vorlage.boundaries.txt`), oder
- Festlegung, dass bei langen Blenden „Grenze innerhalb der Blende“ als richtig gilt
  (dann melodic 8/9 statt 5/9 – das wäre eine Änderung der Abnahmeregel, keine Verbesserung
  des Algorithmus, und muss so benannt bleiben).
