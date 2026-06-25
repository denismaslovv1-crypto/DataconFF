param(
  [Parameter(Mandatory = $true, Position = 0)]
  [ValidateSet("build", "query")]
  [string]$Command,

  [Parameter(Position = 1)]
  [string]$Query,

  [string]$Collection = "methodology_notes",
  [string]$IndexDir = "rag_index",
  [string]$Config = "config/rag_models.json",
  [int]$TopK = 5
)

$ErrorActionPreference = "Stop"
$env:PYTHONPATH = "src"

function Test-Python {
  param([string]$Candidate)

  if (-not $Candidate -or -not (Test-Path $Candidate)) {
    return $false
  }

  try {
    & $Candidate -c "import sys; raise SystemExit(0 if sys.version_info >= (3, 11) else 1)" *> $null
    return $LASTEXITCODE -eq 0
  }
  catch {
    return $false
  }
}

function Get-ProjectPython {
  if ($env:VIRTUAL_ENV) {
    $activePython = Join-Path $env:VIRTUAL_ENV "Scripts\python.exe"
    if (Test-Python $activePython) {
      return $activePython
    }
  }

  $localPython = Join-Path $PSScriptRoot "..\.venv\Scripts\python.exe"
  if (Test-Python $localPython) {
    return (Resolve-Path $localPython).Path
  }

  $pathPython = Get-Command python -ErrorAction SilentlyContinue
  if ($pathPython -and (Test-Python $pathPython.Source)) {
    return $pathPython.Source
  }

  throw "Python was not found. Activate .venv or install Python 3.11+."
}

$Python = Get-ProjectPython

if ($Command -eq "build") {
  & $Python -m rag_core vector-build --root . --index-dir $IndexDir --config $Config --collection $Collection
}
else {
  if (-not $Query) {
    throw "Query is required for query command."
  }
  & $Python -m rag_core vector-query $Query --root . --config $Config --collection $Collection --top-k $TopK
}
