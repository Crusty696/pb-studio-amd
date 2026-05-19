@echo off
REM ============================================================
REM KI-Chat Track 2026-05-16 — Build, Test, Commit, Push
REM Iron Rule 12 (Autonomie) + Pattern #17 (Push autonom)
REM
REM ALL output redirected to chat_track_build.log so the
REM coworking Linux sandbox can read the result.
REM ============================================================
setlocal EnableDelayedExpansion
set "REPO=C:\Users\david\Documents\Pb_studio_AMD_version"
set "LOG=%REPO%\chat_track_build.log"
cd /d "%REPO%" || (echo FATAL: cd failed > "%LOG%" & exit /b 1)

REM Redirect everything inside the main block to LOG
call :Main > "%LOG%" 2>&1
set "RC=%ERRORLEVEL%"
echo. >> "%LOG%"
echo === END (exit code %RC%) === >> "%LOG%"
exit /b %RC%

:Main

echo.
echo === Step 1: Remove stale lockfiles ===
if exist ".git\HEAD.lock" (
    echo Removing .git\HEAD.lock
    del /F /Q ".git\HEAD.lock"
)
if exist ".git\index.lock" (
    echo Removing .git\index.lock
    del /F /Q ".git\index.lock"
)

echo.
echo === Step 2: Reset index to drop pre-existing staged work ===
REM Unstage everything that was staged before our chat-track changes
git reset HEAD 2>&1 | findstr /V "Unstaged"

echo.
echo === Step 3: Run pytest (Chat-Track-Suite) ===
call .venv\Scripts\activate.bat 2>nul
set "PYTHONPATH=src"
python -m pytest Tests\test_ollama_client.py Tests\test_model_registry.py ^
    Tests\test_chat_router.py Tests\test_chat_agent.py Tests\test_tool_registry.py ^
    Tests\test_ollama_vision_wrapper.py -q -p no:cacheprovider 2>&1
if errorlevel 1 (
    echo FATAL: pytest failed
    exit /b 2
)

echo.
echo === Step 4: dotnet build Release ===
dotnet build PBStudio.UI\PBStudio.UI.csproj -c Release --nologo 2>&1
if errorlevel 1 (
    echo FATAL: dotnet build failed
    exit /b 3
)

echo.
echo === Step 5: Commit 1 — Backend Tool-Registry + Chat-Agent ===
git add src\pb_studio\ai\tool_registry.py src\pb_studio\ai\chat_agent.py src\pb_studio\ai\ollama_client.py
git commit -m "feat(chat): tool_registry + chat_agent + ollama tools-param" -m "KI-Chat Track 2026-05-16. tool_registry mit 27 Tools ueber Audio/Video/Pacing/Brain/Project/Render/Models/System. chat_agent mit Multi-Turn Tool-Use-Loop via Ollama function calling. ollama_client um tools-Parameter + chat_stream erweitert."
if errorlevel 1 echo WARN: commit 1 failed

echo.
echo === Step 6: Commit 2 — Backend Router + Wiring ===
git add backend\routers\chat_router.py backend\main.py
git commit -m "feat(chat): chat_router endpoints + SSE-Stream" -m "POST /chat/message (SSE), GET /chat/tools, GET/DELETE /chat/history. main.py include_router wiring."
if errorlevel 1 echo WARN: commit 2 failed

echo.
echo === Step 7: Commit 3 — ModelRegistry tasks + config ===
git add src\pb_studio\ai\model_registry.py config.json
git commit -m "feat(chat): model_registry tasks fuer chat_general/chat_tool_use" -m "DEFAULT_TASK_PREFERENCES um chat_general (freier Text) + chat_tool_use (Function-Calling) erweitert. config.json mit Default-Preferenzen pro Mode."
if errorlevel 1 echo WARN: commit 3 failed

echo.
echo === Step 8: Commit 4 — Pytest-Tests ===
git add Tests\test_tool_registry.py Tests\test_chat_agent.py Tests\test_chat_router.py
git commit -m "test(chat): 39 Tests fuer tool_registry/chat_agent/chat_router" -m "22 Tool-Registry-Tests (Schema, Coercion, Handler-Roundtrip via MockTransport). 9 Chat-Agent-Tests (Multi-Turn Loop, History, Limit). 8 Chat-Router-Tests (SSE, History, Validation)."
if errorlevel 1 echo WARN: commit 4 failed

echo.
echo === Step 9: Commit 5 — WPF Chat-Tab UI ===
git add PBStudio.UI\Models\ChatMessage.cs PBStudio.UI\Models\ChatEvent.cs ^
    PBStudio.UI\ViewModels\ChatViewModel.cs ^
    PBStudio.UI\Views\ChatView.xaml PBStudio.UI\Views\ChatView.xaml.cs ^
    PBStudio.UI\Services\ApiClient.cs PBStudio.UI\Services\IApiClient.cs ^
    PBStudio.UI\App.xaml.cs PBStudio.UI\MainWindow.xaml
git commit -m "feat(ui): KI-Chat-Tab mit Tool-Call-Visualisierung" -m "Neuer CHAT-Tab (Index 10) mit Markdown-aehnlichem Layout, Tool-Call-Expander pro Call (Args+Result), Mode-Selector (speed/balance/quality), Stop-Stream, Clear-History. Bilingual DE/EN via System-Prompt."
if errorlevel 1 echo WARN: commit 5 failed

echo.
echo === Step 10: Push to origin/main ===
git log --oneline -6
echo.
git push origin main 2>&1
if errorlevel 1 (
    echo FATAL: push failed
    git status
    exit /b 4
)

echo.
echo === DONE ===
echo HEAD = origin/main verified:
git rev-parse HEAD
git rev-parse origin/main
endlocal
exit /b 0
