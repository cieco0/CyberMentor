$ErrorActionPreference = 'Stop'
$videoPython = Join-Path $PSScriptRoot '.venv\Scripts\python.exe'
if (-not (Test-Path $videoPython)) { throw 'Lance d abord Lancer.cmd pour preparer Python.' }
& $videoPython -m pip install -r (Join-Path $PSScriptRoot 'requirements.txt')
if ($LASTEXITCODE -ne 0) { throw 'Installation interrompue.' }
$env:HF_HUB_DISABLE_TELEMETRY = '1'
Push-Location $PSScriptRoot
try {
    & $videoPython -c "from faster_whisper.utils import download_model; download_model('small', output_dir='models/whisper-small')"
    if ($LASTEXITCODE -ne 0) { throw 'Telechargement interrompu. Relance ce script.' }
} finally { Pop-Location }
Write-Host 'Analyse video prete. La voix et les captures sont traitees sur ce PC.'
