# T411 — DirectML-/AMF-Fresh-Install

Status: PASS
Datum: 2026-08-01
Geprüfter Produkt-SHA: `a115585cc274a0c0fc6b18b624ef82cf2fdf98b6`
Anforderung: `TR-352`

## Installationsgrenze

- Externer, sauberer Detached-Checkout unter `%LOCALAPPDATA%\Temp`; `git status` war vor und nach dem Lauf leer.
- Isolierte Python-3.11.9-Umgebung aus dem bestandenen T407-Clean-Checkout; `requirements.txt` ist byte-identisch zum T411-Checkout (SHA-256 `6CEFB05B319105BAFF0D78D72D7EFB50BEC43594CBA97CCF61A373F8865FF7A7`).
- NumPy `1.26.4`, ONNX Runtime `1.19.2`; verfügbare Provider: `DmlExecutionProvider`, `CPUExecutionProvider`.
- Das externe DirectML-Bundle `pb-studio-directml-assets-2026.08.01.zip` wurde in den frischen Checkout provisioniert und anschließend erneut exakt verifiziert: 18/18 Einträge, 3.286.356.033 Bytes, SHA-256 `008AAC9E637F95C349826667D0F1926C12D92DF9BF201F4EF77134BEE30029EB`.
- Der zuvor fehlende Audio-MDX-Pflichtbestandteil ist enthalten: `UVR-MDX-NET-Inst_HQ_3.onnx`, 66.759.214 Bytes, SHA-256 `317554B07FE1EA5279A77F2B1520A41EA4B93432560C4FFD08792C30FDDF9ADC`, freigegebene MIT-Provenienz aus `TRvlvr/model_repo` Revision `356bbd334a0ebb8449c602503ac204a3c06df4f6`.

## Adapteridentität

- Ausgewählt: `AMD Radeon RX 7800 XT`, DXGI-Gerät `1`, LUID `0x00000000_0x00012a2a`, 16.963.137.536 Bytes dedizierter VRAM.
- Auswahlregel: AMD-Hardwareadapter mit dem höchsten dedizierten VRAM.
- Der physische DirectML-/LibreHardwareMonitor-Identitätstest bestand: `1 passed`.
- Die produktive AMF-Bindung erzeugt dynamisch `-init_hw_device d3d11va=pb_amf:1`; kein Adapterindex und keine LUID sind im Produktcode fest verdrahtet.

## DirectML-Inferenz

| Workload | Iterationen | Sessions | RX-Maximum | Fremd-LUID | Ergebnis |
|---|---:|---:|---:|---:|---|
| RAFT | 939 | 1 | 61,184568 % | keine | PASS |
| SigLIP | 198 | 1 | 100,573335 % | keine | PASS |
| Moondream | 329 | 1 | 91,545539 % | keine | PASS |
| CLAP | 3.040 | 2 | 96,759222 % | keine | PASS |
| Audio-MDX | 382 | 1 | 95,719505 % | keine | PASS |

Jede erfasste Session meldet `DmlExecutionProvider` an erster Stelle, `enable_mem_pattern=false`, `enable_cpu_mem_arena=false` und `session.disable_cpu_ep_fallback="1"`. Die SigLIP-Erstzusammenfassung hatte den Launcher statt Ergebnis-PID `8544` gefiltert; die korrigierte Auswertung der unveränderten Rohdaten enthält 128 RX-Samples, keine Fremd-LUID und ist separat abgelegt.

`TR-352` bezeichnete den Workload verkürzt als „Moondream“. Die vor dieser Spec akzeptierte Architekturentscheidung ADR-0003 und der Brain-Entscheid vom 2026-07-30 definieren ausdrücklich partielle Bereitschaft: Moondream Vision darf bereit sein, während Caption ohne DirectML-fähigen Decoder unavailable bleibt. Die Spec wurde deshalb auf „Moondream Vision“ präzisiert; die Anforderung wurde nicht nachträglich reduziert.

## AMF-Encoding

Aktive Runtime: Gyan FFmpeg `6.1.1-essentials_build`, FFmpeg SHA-256 `04E1307997530F9CF2FE35CBA2CA7E8875CA91DA02F89D6C7243DF819C94AD00`, FFprobe SHA-256 `3A7E2DC003DC2CD1472827E4C7C4F056AE1AE0AE7C5BBC580C99B49827351BA4`.

| Encoder | Ausgabe | Lesbare Frames | RX-Maximum | Fremd-LUID | Ergebnis |
|---|---|---:|---:|---:|---|
| H.264 AMF | 1920×1080, 60 fps, 12 s | 720 | 1,943063 % | keine | PASS |
| HEVC AMF | 1920×1080, 60 fps, 12 s | 720 | 1,958463 % | keine | PASS |

Beide Dateien wurden vollständig dekodiert, per FFprobe geprüft und gehasht. Einzelne vom Windows-Counter selbst als ungültig gemeldete Stichproben wurden verworfen; die akzeptierten Samples hatten Status `0`, endliche Werte von 0–110 % und die exakte RX-LUID. Die produktiven `check_amf_available`-, H.264- und HEVC-Render-Probes bestanden ebenfalls.

## Geschlossene Abweichungen

- Der alte Asset-Satz ließ Audio-MDX bei einer Neuinstallation fehlen; Manifest, Bundle, Provenienz und Lizenz wurden ergänzt.
- FFmpeg `8.0.1` war nur ein temporärer Runtime-Stand; die bereits freigegebene und auf dieser Hardware belegte Zielruntime `6.1.1` ist nun aktiv und hashgebunden.
- AMF wählte ohne explizite D3D11VA-Initialisierung die integrierte AMD-GPU. Alle produktiven Probe-, Transcode-, Render-, Preview-, VideoGenerator- und Verifikationspfade binden nun dynamisch denselben DXGI-Adapter wie DirectML.
- `encoder_utils.py` konnte nach erfolgreichem Probe wegen eines fehlenden `os`-Imports beim Aufräumen scheitern; der Import ist ergänzt.

## Regression und Belege

- Gespeicherter kombinierter Beleg für Render-/Encoder-, Runtime- und physische DirectML-/LHM-Verträge: `103 passed` in 16,32 Sekunden.
- Testbelege: `T411-hardware-receipts/T411-targeted-tests.xml` und `T411-hardware-receipts/T411-targeted-tests.log`.
- Autoritative Dateien: `T411-hardware-receipts/fresh-install-runtime.json`, die fünf `*-summary.json`-Dateien, `siglip-summary-corrected.json`, `h264-summary.json`, `hevc-summary.json`, zugehörige GPU-/Progress-/Stderr-Belege sowie `inventory.log` und `asset-provision.log`.

## Begrenzung

T411 beweist die lokale Release-Hardwarefähigkeit für den geprüften Produkt-SHA. Gesamt-Suite, Security/SCA/SBOM und die Bindung an den endgültigen Release-SHA gehören zu T413–T415 und werden hier nicht vorweggenommen.
