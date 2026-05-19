# Load with explicit small context to avoid VRAM OOM
$lms = "$env:USERPROFILE\.lmstudio\bin\lms.exe"
$outFile = 'C:\Users\david\Documents\Pb_studio_AMD_version\.lms_load_smart.txt'

if (-not (Test-Path $lms)) { "lms not found at $lms" | Out-File $outFile; exit 1 }

# First unload any cached state
"--- unload all" | Out-File $outFile -Encoding UTF8
& $lms unload --all 2>&1 | Out-File $outFile -Append -Encoding UTF8

# Try smallest model first with tiny context
"--- load gemma-3-1b w/ context 4096 (smallest model)" | Out-File $outFile -Append -Encoding UTF8
& $lms load 'gemma-3-1b-it-glm-4.7-flash-heretic-uncensored-thinking_gguf' --context-length 4096 --gpu off --yes 2>&1 | Out-File $outFile -Append -Encoding UTF8

"--- lms ps after gemma load" | Out-File $outFile -Append -Encoding UTF8
& $lms ps 2>&1 | Out-File $outFile -Append -Encoding UTF8

# Try qwen 9B with reasonable context
"--- load qwen 9B w/ context 8192 + gpu max" | Out-File $outFile -Append -Encoding UTF8
& $lms load 'qwen3.5-9b-uncensored-hauhaucs-aggressive' --context-length 8192 --gpu max --yes 2>&1 | Out-File $outFile -Append -Encoding UTF8

"--- final lms ps" | Out-File $outFile -Append -Encoding UTF8
& $lms ps 2>&1 | Out-File $outFile -Append -Encoding UTF8

Write-Host "DONE"
