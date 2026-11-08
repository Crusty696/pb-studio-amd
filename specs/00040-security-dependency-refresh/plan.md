# Plan

## Vorgehen
1. Scanartefakt aus PR 34 gegen Advisory-Quellen und Produktaufrufe pruefen.
2. Bestehende Ausnahme-/Skip-Konfiguration sichern, befristet aktualisieren;
   vorhandene Negativtests und Guard erhalten.
3. Direkte Pins minimal aktualisieren, mit vorhandenem Lockgenerator exakt
   ausgewaehlte transitive Updates aufloesen; keine Vollaktualisierung.
4. Vollstaendige neue Umgebung isoliert aus dem Hashlock installieren und
   Abhaengigkeits-/Import-/Regressionschecks ausfuehren.
5. Ergebnis und verbleibende Grenzen dokumentieren, committen/pushen, acht
   Pflichtchecks abwarten und PR 34 regulaer mergen.

## Risiken und Verifikation
Pillow/Filelock haben Major-Updates; Transformers kann transitive Pins aendern.
Resolverkonflikte zuerst untersuchen. Alte venv behalten; kein blindes Upgrade.
Nur erforderliche Tests nach Aenderungen wiederholen; finaler CI-Gesamtlauf.
