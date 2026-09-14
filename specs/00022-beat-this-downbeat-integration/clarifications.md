# Clarifications: Beat-This-Downbeat-Integration

## Geklärt

- Nutzerfreigabe 2026-09-04: native Beat-This-Zeitpunkte ersetzen bei gültiger
  Inferenz das Legacy-Raster. Aktuelles BPM wird daraus konsistent berechnet;
  Legacy-BPM und Beatanzahl bleiben in Provenance. Separates Fourier-Beatgrid
  bleibt unverändert. Bestandsanalysen werden nicht automatisch neu berechnet.
- Fehlendes oder hashfalsches Modell degradiert auf librosa-Beats ohne
  Downbeats; kein CPU-ML-Fallback.
- Modellartefakte bleiben außerhalb Git und werden über versionierte Metadaten
  validiert. Automatische Provisionierung ist noch nicht implementiert.
- Live-Test darf nur normale Analyseergebnisse im aktiven Testprojekt schreiben;
  Originalmedien bleiben read-only.
- Vollsuite mit eigenem `--basetemp`. Der bereits laufende Integrationslauf
  begann vor der nachträglichen Raster-Freigabe und Review-Härtung; deshalb
  ist nach finaler Implementierung ein neuer vollständiger Abschlusslauf nötig.

## Offen

Keine produktentscheidende Frage vor Planung.
