param(
    [string]$PythonCommand = "py",
    [string]$PythonVersion = "3.13",
    [string]$ExpectedPythonVersion = "3.13.5"
)

$ErrorActionPreference = "Stop"
$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
Set-Location $repoRoot

if (Test-Path ".venv-rag") {
    throw ".venv-rag already exists. Remove it explicitly before recreating the fixed environment."
}

$actualPythonVersion = (& $PythonCommand "-$PythonVersion" -c "import platform; print(platform.python_version())").Trim()
if ($actualPythonVersion -ne $ExpectedPythonVersion) {
    throw "Python version mismatch: expected $ExpectedPythonVersion, got $actualPythonVersion"
}

& $PythonCommand "-$PythonVersion" -m venv .venv-rag
& .\.venv-rag\Scripts\python.exe -m pip install `
    --require-hashes `
    --only-binary=:all: `
    -r requirements\rag.lock.txt
& .\.venv-rag\Scripts\python.exe scripts\rag\check_environment.py
