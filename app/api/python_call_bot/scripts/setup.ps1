try {
    $ErrorActionPreference = "Stop"

    $ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
    $ProjectRoot = Resolve-Path (Join-Path $ScriptDir "..")
    Set-Location $ProjectRoot

    $VenvDir = Join-Path $ProjectRoot ".venv"
    $VenvPython = Join-Path $VenvDir "Scripts\python.exe"

    if (-not (Test-Path "requirements.txt")) {
        throw "requirements.txt was not found in $ProjectRoot"
    }

    if (-not (Test-Path $VenvPython)) {
        if (Test-Path $VenvDir) {
            throw ".venv exists, but .venv\Scripts\python.exe was not found. Remove the incompatible .venv and run this script again."
        }

        if (Get-Command py -ErrorAction SilentlyContinue) {
            py -3 -m venv .venv
        }
        elseif (Get-Command python -ErrorAction SilentlyContinue) {
            python -m venv .venv
        }
        else {
            throw "Could not find Python. Install Python 3.11+ or make it available as 'py' or 'python'."
        }
    }

    & $VenvPython -c "import sys; raise SystemExit(0 if sys.version_info >= (3, 11) else 1)"
    if ($LASTEXITCODE -ne 0) {
        throw ".venv must use Python 3.11+. Remove .venv and recreate it with Python 3.11 or newer."
    }

    & $VenvPython -m pip install -r requirements.txt
    & $VenvPython -m playwright install chromium

    Write-Host ""
    Write-Host "Setup complete."
    Write-Host "Activate with: .\.venv\Scripts\Activate.ps1"
    Write-Host "Run with:      .\.venv\Scripts\python.exe main.py"
}
catch {
    Write-Host ""
    Write-Host "Error:"
    Write-Host $_
}
finally {
    Write-Host ""
    Read-Host "Press Enter to close"
}
