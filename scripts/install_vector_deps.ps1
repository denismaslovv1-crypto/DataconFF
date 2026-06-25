$ErrorActionPreference = "Stop"

$Python = Join-Path $PSScriptRoot "..\.venv\Scripts\python.exe"
if (-not (Test-Path $Python)) {
  throw "Project Python was not found at .venv\Scripts\python.exe. Create and activate .venv first."
}

& $Python -m pip install -e ".[vector]"
