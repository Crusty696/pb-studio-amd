# Critical System Hardening & Memory Optimization Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement proactive VRAM budgeting, chunked chroma CQT processing, hybrid LLM list merging, and WPF transient ViewModel scope lifecycles to prevent memory leaks and OOM crashes under high load.

**Architecture:** Centralized VRAMBudgetManager tracking, incremental audio processing blocks, asynchronous provider merging API router, and IServiceScopeFactory in WPF View code-behinds.

**Tech Stack:** C#, WPF, .NET 9, Python 3.11, FastAPI, librosa, numpy, onnxruntime, torch-directml.

---

### Task 1: Z-CORE StemSeparator VRAM Härtung

**Files:**
- Modify: `src/pb_studio/audio/separator.py:180-267`
- Test: `Tests/test_separator.py:20-80`

- [ ] **Step 1: Implement VRAMBudgetManager integration in separator.py**

Write the code to reserve, commit, and release the VRAM budget based on the loaded model name.
```python
def _get_vram_model_id(model_name: str) -> str:
    name_lower = model_name.lower()
    if "mdxc" in name_lower or "demucs" in name_lower:
        return "mdxc_models"
    elif "voc" in name_lower:
        return "mdx_net_voc"
    else:
        return "mdx_net_inst"
```

- [ ] **Step 2: Add reserve and commit inside separate()**

```python
        # VRAM Budget Manager integration
        vram_reserved = False
        model_id = None
        try:
            from pb_studio.core.vram_budget_manager import get_vram_manager
            vram_mgr = get_vram_manager()
            model_id = _get_vram_model_id(model_name)
            vram_reserved = vram_mgr.reserve(model_id, force=True)
        except Exception as ve:
            logger.warning(f"Failed to integrate with VRAMBudgetManager reserve: {ve}")

        try:
            # ... loading model ...
            if vram_reserved and model_id:
                vram_mgr.commit(model_id)
```

- [ ] **Step 3: Add release in finally block and unload()**

```python
        finally:
            if vram_reserved and model_id:
                vram_mgr.release(model_id)
```

- [ ] **Step 4: Run tests to verify VRAM integration**

Run: `.venv\Scripts\pytest Tests/test_separator.py -v`
Expected: 5 passed

- [ ] **Step 5: Commit changes**

```bash
git add src/pb_studio/audio/separator.py
git commit -m "feat(audio): integrate separator VRAM budgeting via central VRAMBudgetManager"
```

---

### Task 2: Z-AUDIO SubtrackDetector RAM-Härtung

**Files:**
- Modify: `src/pb_studio/audio/subtrack_detector.py:141-142`
- Test: `Tests/test_subtrack_detector.py:20-60`

- [ ] **Step 1: Write chunked CQT calculation to prevent memory spikes**

```python
        # Compute chroma in chunks to prevent memory spikes on long files
        chunk_size_sec = 300  # 5 minutes
        chunk_samples = chunk_size_sec * sr
        chroma_list = []
        
        starts = list(range(0, y.size, chunk_samples))
        for i, start in enumerate(starts):
            if i == len(starts) - 1 and len(y) - start < 2048 and i > 0:
                continue
            if i == len(starts) - 2 and len(y) - starts[i+1] < 2048:
                end = len(y)
            else:
                end = min(start + chunk_samples, y.size)
                
            y_chunk = y[start:end]
            if len(y_chunk) < 2048:
                if len(y_chunk) == 0:
                    continue
                pad_len = 2048 - len(y_chunk)
                y_chunk = np.pad(y_chunk, (0, pad_len), mode="constant")
                chroma_chunk = librosa.feature.chroma_cqt(y=y_chunk, sr=sr, hop_length=self.hop_length)
                expected_frames = max(1, int(round(len(y) / self.hop_length)))
                chroma_chunk = chroma_chunk[:, :expected_frames]
            else:
                chroma_chunk = librosa.feature.chroma_cqt(y=y_chunk, sr=sr, hop_length=self.hop_length)
            chroma_list.append(chroma_chunk)
            
        if chroma_list:
            chroma = np.concatenate(chroma_list, axis=1)
        else:
            chroma = librosa.feature.chroma_cqt(y=y, sr=sr, hop_length=self.hop_length)
```

- [ ] **Step 2: Run tests to verify chunked chroma calculation**

Run: `.venv\Scripts\pytest Tests/test_subtrack_detector.py -v`
Expected: 2 passed, 1 skipped

- [ ] **Step 3: Commit changes**

```bash
git add src/pb_studio/audio/subtrack_detector.py
git commit -m "feat(audio): chunk chroma CQT processing in SubtrackDetector to prevent memory spikes"
```

---

### Task 3: Z-BRAIN Registry & Fallback-Härtung

**Files:**
- Modify: `backend/routers/models_router.py:30-100`, `src/pb_studio/ai/model_registry.py:50-120`
- Test: `Tests/test_chat_agent.py:100-200`

- [ ] **Step 1: Implement Ollama-Download-Bypass in models_router.py**

If Ollama is reachable, route pull requests directly to Ollama.
```python
@router.post("/models/pull")
async def pull_model(request: PullModelRequest):
    # If Ollama is online, stream pull directly from Ollama client
```

- [ ] **Step 2: Implement Hybrid-Model-Merger in list_models**

Fetch both LM Studio and Ollama active lists and return a consolidated merged output.

- [ ] **Step 3: Run backend model tests**

Run: `.venv\Scripts\pytest Tests/test_chat_agent.py -v`
Expected: PASS

- [ ] **Step 4: Commit changes**

```bash
git add backend/routers/models_router.py src/pb_studio/ai/model_registry.py
git commit -m "fix(brain): implement universal Ollama download bypass and hybrid list merging"
```

---

### Task 4: Z-UI WPF DI-Scope Härtung

**Files:**
- Modify: `PBStudio.UI/Views/AudioLibraryView.xaml.cs:1-23`, `PBStudio.UI/Views/VideoLibraryView.xaml.cs:1-23`, `PBStudio.UI/Views/ChatView.xaml.cs:1-34`
- Test: Build project using dotnet build CLI.

- [ ] **Step 1: Update AudioLibraryView.xaml.cs to use IServiceScope**

```csharp
    private IServiceScope? _scope;

    public AudioLibraryView()
    {
        InitializeComponent();
        Loaded += OnLoaded;
        Unloaded += OnUnloaded;
    }

    private void OnLoaded(object sender, RoutedEventArgs e)
    {
        if (_scope == null)
        {
            _scope = Ioc.Default.GetRequiredService<IServiceScopeFactory>().CreateScope();
            DataContext = _scope.ServiceProvider.GetRequiredService<AudioLibraryViewModel>();
        }
    }

    private void OnUnloaded(object sender, RoutedEventArgs e)
    {
        DataContext = null;
        _scope?.Dispose();
        _scope = null;
    }
```

- [ ] **Step 2: Update VideoLibraryView.xaml.cs to use IServiceScope**

Implement the same Loaded/Unloaded pattern resolving `VideoLibraryViewModel`.

- [ ] **Step 3: Update ChatView.xaml.cs to use IServiceScope**

Implement the same Loaded/Unloaded pattern resolving `ChatViewModel`.

- [ ] **Step 4: Build the WPF project to verify compile success**

Run: `dotnet build PBStudio.UI --configuration Release`
Expected: 0 warnings, 0 errors

- [ ] **Step 5: Commit changes**

```bash
git add PBStudio.UI/Views/AudioLibraryView.xaml.cs PBStudio.UI/Views/VideoLibraryView.xaml.cs PBStudio.UI/Views/ChatView.xaml.cs
git commit -m "fix(ui): resolve DI transient IDisposable VM memory leaks via localized IServiceScope"
```

---

### Task 5: Z-DOCS Root-Verzeichnis Bereinigung

**Files:**
- Modify: Root files audit logs.

- [ ] **Step 1: Move legacy markdown reports to archive/audits**

Run: `powershell -Command "Move-Item AUDIT_*.md archive/audits/ -Force; Move-Item STATUS_REPORT_*.md archive/audits/ -Force; Move-Item system_audit_report.md archive/audits/ -Force"`

- [ ] **Step 2: Stage and commit moves in Git**

```bash
git add .
git commit -m "docs(archive): move legacy markdown audit reports from root to archive/audits"
```
