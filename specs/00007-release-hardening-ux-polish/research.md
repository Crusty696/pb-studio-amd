# Research Report: Release Hardening & UX Polish

**Context**: Researching best practices for native Windows integration, AMD-specific VRAM stability, and WPF UI performance to finalize PB Studio for MVP release.

## WPF Native Dialogs
- **Key findings**: .NET 8+ introduced a truly native `Microsoft.Win32.OpenFolderDialog` that matches the Windows 11 File Explorer style.
- **Recommended**: Replace all legacy folder pickers with `Microsoft.Win32.OpenFolderDialog`. Wrap in an `IDialogService` to maintain MVVM testability.
- **Avoid**: `System.Windows.Forms.FolderBrowserDialog` (bloats app with WinForms) and `WindowsAPICodePack` (unstable/unmaintained).
### Sources
- https://learn.microsoft.com/en-us/dotnet/api/microsoft.win32.openfolderdialog — Official .NET 8 API docs.

## VRAM & DirectML Stability
- **Key findings**: DirectML manages memory on-demand and does not support standard ONNX "memory pattern" optimizations. AMD-specific monitoring is best done via `amdsmi`.
- **Recommended**: Disable `enable_mem_pattern` in ONNX SessionOptions. Explicitly call `gc.collect()` after heavy inference blocks.
- **Avoid**: Keeping too many active `InferenceSession` objects; reuse sessions but clear IO bindings.
### Sources
- https://onnxruntime.ai/docs/execution-providers/DirectML-Execution-Provider.html — Official DirectML EP performance guide.

## UI Performance & Polish
- **Key findings**: Animating layout properties (Width/Height) causes expensive layout passes. `RenderTransform` is GPU-accelerated and much smoother.
- **Recommended**: Use `ScaleTransform` and `TranslateTransform` for all UI transitions. Enable `VirtualizingStackPanel` for clip libraries.
- **Avoid**: Global "Loading" spinners; use local "shimmer" effects or task-specific progress indicators.
### Sources
- https://learn.microsoft.com/en-us/dotnet/desktop/wpf/graphics-multimedia/animation-tips-and-tricks — Microsoft WPF performance best practices.

## Long-Running Stability
- **Key findings**: Local AI apps suffer from "memory bloat." Checkpointing is critical for 4h+ renders.
- **Recommended**: Implement an "Atomic Checkpoint" pattern (save EDL state every N frames). Use a heartbeat mechanism for backend worker processes.
- **Avoid**: Running heavy inference on the main FastAPI event loop; always use `asyncio.to_thread` or separate processes.
### Summary
Transitioning to .NET 8 native dialogs and implementing strict VRAM reservation/cleanup patterns are the highest-impact stability improvements. UI polish should focus on GPU-accelerated transforms to maintain responsiveness during background AI tasks.

### Sources Index
| URL | Topic | Fetched |
|-----|-------|---------|
| https://learn.microsoft.com/en-us/dotnet/api/microsoft.win32.openfolderdialog | WPF Native Dialogs | 2026-04-25 |
| https://onnxruntime.ai/docs/execution-providers/DirectML-Execution-Provider.html | VRAM & DirectML | 2026-04-25 |
| https://learn.microsoft.com/en-us/dotnet/desktop/wpf/graphics-multimedia/animation-tips-and-tricks | WPF UI Polish | 2026-04-25 |
