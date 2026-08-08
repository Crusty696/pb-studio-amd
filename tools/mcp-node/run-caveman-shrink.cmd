@echo off
setlocal
set "MCP_TOOL_DIR=%~dp0"
set "MCP_VERIFY=%MCP_TOOL_DIR%verify-lock.mjs"
set "MCP_CAVEMAN_BIN=%MCP_TOOL_DIR%node_modules\.bin\caveman-shrink.cmd"
set "MCP_CONTEXT7_ENTRY=%MCP_TOOL_DIR%node_modules\@upstash\context7-mcp\dist\index.js"
if not exist "%MCP_VERIFY%" (
  >&2 echo PB Studio MCP lock verifier is missing.
  exit /b 69
)
if not exist "%MCP_CAVEMAN_BIN%" (
  >&2 echo PB Studio MCP dependencies are missing. Run npm ci --ignore-scripts in "%MCP_TOOL_DIR%".
  exit /b 69
)
if not exist "%MCP_CONTEXT7_ENTRY%" (
  >&2 echo PB Studio MCP upstream is missing. Run npm ci --ignore-scripts in "%MCP_TOOL_DIR%".
  exit /b 69
)
set "npm_config_offline=true"
set "npm_config_ignore_scripts=true"
node -e "const v=process.versions.node.split('.').map(Number);process.exit(v[0]>20||(v[0]===20&&(v[1]>18||(v[1]===18&&v[2]>=1)))?0:1)"
if errorlevel 1 (
  >&2 echo PB Studio MCP requires Node.js 20.18.1 or newer.
  exit /b 69
)
node "%MCP_VERIFY%" --runtime
if errorlevel 1 exit /b 69
call "%MCP_CAVEMAN_BIN%" node "%MCP_CONTEXT7_ENTRY%" %*
exit /b %errorlevel%
