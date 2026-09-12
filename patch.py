import re

# 1. Task 3.1 & 3.3 in video_router.py
vr = 'C:/Users/david/Documents/Pb_studio_AMD_version/backend/routers/video_router.py'
with open(vr, 'r', encoding='utf-8') as f:
    code = f.read()

code = code.replace(
'''        "avg_color_temp": 0.0,
        "status": "failed",
        "stage_status": {},
        "stage_errors": {},''',
'''        "avg_color_temp": 0.0,
        "status": "failed",
        "stage_status": {},
        "stage_errors": {},
        "provider_receipt": {},
        "model_receipt": {},
        "attempt_receipt": {},''')

code = code.replace(
'''    result["stage_status"] = dict(existing.get("stage_status") or {})
    result["stage_errors"] = dict(existing.get("stage_errors") or {})
    result["status"] = _video_analysis_status(''',
'''    result["stage_status"] = dict(existing.get("stage_status") or {})
    result["stage_errors"] = dict(existing.get("stage_errors") or {})
    result["provider_receipt"] = dict(existing.get("provider_receipt") or {})
    result["model_receipt"] = dict(existing.get("model_receipt") or {})
    result["attempt_receipt"] = dict(existing.get("attempt_receipt") or {})
    result["status"] = _video_analysis_status(''')

code = code.replace(
'''    stage_status = stage_result.get("stage_status") or {}
    stage_errors = stage_result.get("stage_errors") or {}
    status = str(stage_status.get(stage) or "failed")''',
'''    stage_status = stage_result.get("stage_status") or {}
    stage_errors = stage_result.get("stage_errors") or {}
    provider_receipt = stage_result.get("provider_receipt") or {}
    model_receipt = stage_result.get("model_receipt") or {}
    attempt_receipt = stage_result.get("attempt_receipt") or {}
    
    if stage in provider_receipt:
        result.setdefault("provider_receipt", {})[stage] = provider_receipt[stage]
    if stage in model_receipt:
        result.setdefault("model_receipt", {})[stage] = model_receipt[stage]
    if stage in attempt_receipt:
        result.setdefault("attempt_receipt", {})[stage] = attempt_receipt[stage]

    status = str(stage_status.get(stage) or "failed")''')

code = code.replace(
'''    stage_status = dict(result.get("stage_status") or {})
    stage_errors = dict(result.get("stage_errors") or {})
    is_analyzed = status == "completed"''',
'''    stage_status = dict(result.get("stage_status") or {})
    stage_errors = dict(result.get("stage_errors") or {})
    provider_receipt = dict(result.get("provider_receipt") or {})
    model_receipt = dict(result.get("model_receipt") or {})
    attempt_receipt = dict(result.get("attempt_receipt") or {})
    is_analyzed = status == "completed"''')

code = code.replace(
'''        "avg_color_temp",
        "mood_tags",
    ):''',
'''        "avg_color_temp",
        "mood_tags",
        "provider_receipt",
        "model_receipt",
        "attempt_receipt",
    ):''')

code = code.replace(
'''    cache_result.update({
        "analysis_status": status,
        "stage_status": stage_status,
        "stage_errors": stage_errors,
        "is_analyzed": is_analyzed,
    })''',
'''    cache_result.update({
        "analysis_status": status,
        "stage_status": stage_status,
        "stage_errors": stage_errors,
        "provider_receipt": provider_receipt,
        "model_receipt": model_receipt,
        "attempt_receipt": attempt_receipt,
        "is_analyzed": is_analyzed,
    })''')

# Task 3.3
code = code.replace(
'''def _derive_video_analysis_status(stage_status: dict[str, str]) -> str:
    failed = any(
        status in {"partial", "failed", "interrupted"}
        for status in stage_status.values()
    )
    if not failed:
        return "completed"
    return "partial" if "completed" in stage_status.values() else "failed"''',
'''def _derive_video_analysis_status(stage_status: dict[str, str]) -> str:
    failed = any(
        status in {"failed", "interrupted"}
        for status in stage_status.values()
    )
    partial = any(
        status in {"partial", "unavailable"}
        for status in stage_status.values()
    )
    if failed:
        return "partial" if "completed" in stage_status.values() else "failed"
    if partial:
        return "partial"
    return "completed"''')

# Task 3.5 in video_router
code = code.replace(
'''    for candidate in candidates:
        if not 0 <= candidate < addressable_frames or candidate in used_indices:
            continue
        cap.set(cv2.CAP_PROP_POS_FRAMES, candidate)
        ret, frame = cap.read()''',
'''    
    # Fast forward sequentially instead of using CAP_PROP_POS_FRAMES
    current_frame = int(cap.get(cv2.CAP_PROP_POS_FRAMES))
    for candidate in candidates:
        if not 0 <= candidate < addressable_frames or candidate in used_indices:
            continue
        if current_frame > candidate:
            cap.set(cv2.CAP_PROP_POS_FRAMES, candidate)
            current_frame = candidate
        while current_frame < candidate:
            cap.grab()
            current_frame += 1
        ret, frame = cap.read()
        current_frame += 1''')

code = code.replace(
'''                for idx in indices:
                    cap.set(cv2.CAP_PROP_POS_FRAMES, idx)
                    ret, frame = cap.read()''',
'''                current_frame = 0
                for idx in indices:
                    while current_frame < idx:
                        cap.grab()
                        current_frame += 1
                    ret, frame = cap.read()
                    current_frame += 1''')

with open(vr, 'w', encoding='utf-8') as f:
    f.write(code)


# 3.5 visual_curves.py
vc = 'C:/Users/david/Documents/Pb_studio_AMD_version/src/pb_studio/video/visual_curves.py'
with open(vc, 'r', encoding='utf-8') as f:
    vcode = f.read()

vcode = vcode.replace(
'''        frame_idx = 0
        while frame_idx < total_frames:
            cap.set(cv2.CAP_PROP_POS_FRAMES, frame_idx)
            ok, frame = cap.read()''',
'''        frame_idx = 0
        current_frame = 0
        while frame_idx < total_frames:
            while current_frame < frame_idx:
                cap.grab()
                current_frame += 1
            ok, frame = cap.read()
            current_frame += 1''')

with open(vc, 'w', encoding='utf-8') as f:
    f.write(vcode)

# 4.1 pacing_schemas.py
ps = 'C:/Users/david/Documents/Pb_studio_AMD_version/backend/schemas/pacing_schemas.py'
with open(ps, 'r', encoding='utf-8') as f:
    pscode = f.read()

pscode = pscode.replace(
'''    degradations: list[ModeDegradationSchema] = []''',
'''    degradations: list[ModeDegradationSchema] = []
    rejected_clips: list[dict[str, Any]] = []
    rejection_reasons: dict[str, int] = {}''')

# 4.2 nested min_cut_interval
pscode = pscode.replace(
'''    clip_length_variation: float = Field(0.0, ge=0.0, le=1.0)
    min_cut_interval: float = Field(0.5, ge=0.0)
    max_cut_interval: float = Field(10.0, gt=0.0)''',
'''    clip_length_variation: float = Field(0.0, ge=0.0, le=1.0)
    min_cut_interval: float = Field(0.5, ge=0.0)
    max_cut_interval: float = Field(10.0, gt=0.0)
    
    @field_validator("min_cut_interval", mode="before")
    @classmethod
    def extract_nested_min_cut(cls, v: Any, info: Any) -> float:
        if isinstance(v, dict) and "min_cut_interval" in v:
            return float(v["min_cut_interval"])
        return float(v)''')

with open(ps, 'w', encoding='utf-8') as f:
    f.write(pscode)

# 4.1 DirectorViewModel.cs
dvm = 'C:/Users/david/Documents/Pb_studio_AMD_version/PBStudio.UI/ViewModels/DirectorViewModel.cs'
with open(dvm, 'r', encoding='utf-8') as f:
    dcode = f.read()

dcode = dcode.replace(
'''    [ObservableProperty] private int _cutCount;
    [ObservableProperty] private double _totalDuration;''',
'''    [ObservableProperty] private int _cutCount;
    [ObservableProperty] private double _totalDuration;
    [ObservableProperty] private int _rejectedClipCount;
    [ObservableProperty] private string _rejectionSummary = "";''')

dcode = dcode.replace(
'''                    CutCount = result.CutCount;
                    TotalDuration = result.TotalDuration;
                });
                // FR-362: ein Modus ohne Datengrundlage darf nicht als aktiv
                // durchgehen. Das Backend schaltet ihn ab und meldet es hier.
                StatusText = $"{result.CutCount} Cuts generiert ({result.TotalDuration:F1}s)"
                    + FormatDegradations(result.Degradations);''',
'''                    CutCount = result.CutCount;
                    TotalDuration = result.TotalDuration;
                    
                    var rejected = result.GetType().GetProperty("RejectedClips")?.GetValue(result) as System.Collections.IList;
                    RejectedClipCount = rejected?.Count ?? 0;
                    
                    var reasonsObj = result.GetType().GetProperty("RejectionReasons")?.GetValue(result);
                    if (reasonsObj is System.Collections.IDictionary dict && dict.Count > 0)
                    {
                        var pairs = new System.Collections.Generic.List<string>();
                        foreach (System.Collections.DictionaryEntry kv in dict)
                            pairs.Add($"{kv.Key}: {kv.Value}");
                        RejectionSummary = string.Join(", ", pairs);
                    }
                    else
                    {
                        RejectionSummary = "";
                    }
                });
                
                string rejectedInfo = RejectedClipCount > 0 ? $" ({RejectedClipCount} verworfen)" : "";
                // FR-362: ein Modus ohne Datengrundlage darf nicht als aktiv
                // durchgehen. Das Backend schaltet ihn ab und meldet es hier.
                StatusText = $"{result.CutCount} Cuts generiert ({result.TotalDuration:F1}s){rejectedInfo}"
                    + FormatDegradations(result.Degradations);''')

with open(dvm, 'w', encoding='utf-8') as f:
    f.write(dcode)

print("Patch applied successfully.")
