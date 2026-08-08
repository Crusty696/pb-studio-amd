# T393 – UI-Ergebniswahrheit

Status: PASS
Datum: 2026-07-31
Requirement: FR-348

## Ergebnis

- Chat-History wird lokal nur nach bestätigtem `success=true` geleert; false, Exception und Transportfehler bleiben sichtbar.
- `/gpu/cleanup` entlädt ausschließlich inaktive LOW/BACKGROUND-Modelle über bestätigte Unload-Callbacks und antwortet typisiert mit `success`, `freed_mb` und redigiertem `error`.
- GPU-UI wertet false, null, Exception und ungültige Ergebnisse ohne optimistische Erfolgsmeldung aus.
- Modell-Empfehlungen sind an CTS, Request-Generation, Projekt-Generation, Projektpfad, Projektkontext und angefragten Modus gebunden; alte oder vertauschte Antworten werden verworfen.
- Der T392-Settings-/FFmpeg-Vertrag blieb bei der Integration erhalten.

## Verifikation

- `backend/main.py` Python-Compile: PASS.
- OpenAPI-Snapshot enthält den typisierten `GpuCleanupResponse`.
- NuGet Locked Restore und WPF Release Build: PASS, 0 Warnungen, 0 Fehler.
- `git diff --check`: PASS.
- Funktionale Race-/Failure-Injection bleibt planmäßig T404–T410.

## Implementierungssnapshot

| Datei | SHA-256 |
|---|---|
| `PBStudio.UI/ViewModels/ChatViewModel.cs` | `82f9c69f1e6ae01efe87265b691f15b91a2e926382c4181d45992d47c85d1d4c` |
| `PBStudio.UI/ViewModels/SettingsViewModel.cs` | `a3635be8901d2092a719935df85a0db5db5533ad79a2b41178f6ddd8cf612420` |
| `PBStudio.UI/Services/ApiClient.cs` | `8235549bc99b0ba132a6c593ce395f00405b6525cb8f88c89e0d67e60a55ac81` |
| `PBStudio.UI/Services/IApiClient.cs` | `608e7de4e4171dff6d03ff44a47f1f9c25b95b349ef6542c49544ccfddb17a14` |
| `backend/main.py` | `1e51a9edde0dc38d248fac5ef6c2451a7f4acb60a6c2745c2b4d6bf5ffc00c4d` |
| `PBStudio.UI/openapi.snapshot.json` | `8456bf2c1c3e9c36b8a8d781e17026f241c6bfce4bd020b6907e2cfbd870554b` |
