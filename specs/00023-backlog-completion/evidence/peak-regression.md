# T008: peak-Multiplikator

Implementiert 2026-09-06: peak=1.5 im gemeinsamen
STRUCTURE_INTENSITY_MULTIPLIERS. Designentscheidung: gleiche Intensitaet wie
die vorhandenen maximalen drop-/high_energy-Phasen statt verse-Fallback 0.8.
Dies ist eine explizite Implementierungsentscheidung, keine Hoerbewertung.

Neue Regression in Tests/test_pacing_cached_structure.py prueft direkte
Analyzer-Abbildung und gecachte Struktur, Gewichtung 0.5 -> 0.75 sowie
tatsaechliche Auswahl des peak-Triggers gegen den benachbarten verse-Trigger.
Agentenbeleg: vor Fix 2 failed, nach Fix 2 passed (2 deselected).
Parent hat den kompletten Diff gegen diese Behauptung geprueft.

Fokustests --noconftest und eigene LOCALAPPDATA/APPDATA/basetemp verhindern
Zugriffe des Import-Recovery auf Produktdaten. Kompilierung der beiden
kompletten Dateien und git diff --check bestanden. Vollsuite gestartet,
Ergebnis noch offen: fullsuite-20260906.log. Keine finale Live-QC behauptet.
