# T392 – Settings- und FFmpeg-Runtime-Wahrheit

Status: PASS
Datum: 2026-07-31
Requirement: FR-347

## Ergebnis

- Die UI zeigt ausschließlich den kanonischen Projektpfad und erlaubt keine manuelle FFmpeg-Auswahl.
- Runtime-Version, FFmpeg-/FFprobe-SHA-256 und Manifestquelle werden gemeinsam geprüft und sichtbar gemacht.
- Settings-Load liefert typisierte Fehler statt stiller Defaults; Save nutzt Same-Directory-Tempdatei, Disk-Flush, atomaren Replace/Move und Byte-Verifikation.
- UI-Erfolg wird erst nach bestätigtem Write angezeigt; ein nachgelagerter Apply-/Backend-Sync-Fehler bleibt als separater Teilfehler sichtbar.

## Verifikation

- Aktive Runtime: `8.0.1-essentials_build-www.gyan.dev`.
- `h264_amf`, `hevc_amf` und `av1_amf`: vorhanden.
- FFmpeg SHA-256: `5AF82A0D4FE2B9EAE211B967332EA97EDFC51C6B328CA35B827E73EAC560DC0D`.
- FFprobe SHA-256: `192A1D6899059765AC8C39764FC3148D4E6049955956DC2029F81F4BD6A8972D`.
- Beide Hashes stimmen mit `config/ffmpeg-runtime.json` überein.
- XAML-XML-Parsing: PASS.
- NuGet Locked Restore und WPF Release Build: PASS, 0 Warnungen, 0 Fehler.
- Funktions- und GUI-Matrix bleiben planmäßig T404–T412.

## Implementierungssnapshot

| Datei | SHA-256 |
|---|---|
| `PBStudio.UI/Services/SettingsService.cs` | `8e0af1032203ea50a3ea994e8b173809c3b7e1ecae96590d27efd5e280579033` |
| `PBStudio.UI/ViewModels/SettingsViewModel.cs` | `a3635be8901d2092a719935df85a0db5db5533ad79a2b41178f6ddd8cf612420` |
| `PBStudio.UI/Views/SettingsView.xaml` | `e51b4617dc551479840683733dc35ee6c104ca7b08c849d6ba2a33d643a53a1c` |

Hinweis: Die aktive 8.0.1-Runtime wurde nicht verändert. Die separate Freigabe der
manifestierten 6.1.1-Kandidatenruntime bleibt am Hardware-/Release-Gate offen.
