$ErrorActionPreference = 'Stop'
$mentorRoot = $PSScriptRoot
$mentorUrl = 'http://127.0.0.1:8765'
try {
    $mentorExisting = Invoke-RestMethod "$mentorUrl/api/state" -TimeoutSec 2
    if ($mentorExisting.settings -and $mentorExisting.token) {
        Start-Process $mentorUrl -WindowStyle Hidden
        exit 0
    }
} catch { }
$mentorVenv = Join-Path $mentorRoot '.venv\Scripts\python.exe'
if (Test-Path $mentorVenv) { $mentorPython = $mentorVenv }
else {
    $mentorPy = Get-Command py -ErrorAction SilentlyContinue
    $mentorSystem = Get-Command python -ErrorAction SilentlyContinue
    if ($mentorPy) { & $mentorPy.Source -3 -m venv (Join-Path $mentorRoot '.venv') }
    elseif ($mentorSystem) { & $mentorSystem.Source -m venv (Join-Path $mentorRoot '.venv') }
    else { throw 'Installe Python 3.11 ou plus recent depuis python.org, puis relance.' }
    if ($LASTEXITCODE -ne 0) { throw 'Creation de l environnement Python impossible.' }
    $mentorPython = $mentorVenv
}
& $mentorPython -c 'import pypdf, docx, reportlab, faster_whisper, rapidocr_onnxruntime' 2>$null
if ($LASTEXITCODE -ne 0) {
    & $mentorPython -m pip install -r (Join-Path $mentorRoot 'requirements.txt')
    if ($LASTEXITCODE -ne 0) { throw 'Installation des dependances impossible.' }
}
$mentorOllama = Join-Path $env:LOCALAPPDATA 'Programs\Ollama\ollama.exe'
if (Test-Path $mentorOllama) {
    try { $null = Invoke-RestMethod 'http://127.0.0.1:11434/api/tags' -TimeoutSec 2 }
    catch { Start-Process $mentorOllama -ArgumentList 'serve' -WindowStyle Hidden }
}
$mentorProcess = Start-Process $mentorPython -ArgumentList @('"' + (Join-Path $mentorRoot 'app.py') + '"') -WorkingDirectory $mentorRoot -WindowStyle Hidden -RedirectStandardOutput (Join-Path $mentorRoot 'server.log') -RedirectStandardError (Join-Path $mentorRoot 'server-error.log') -PassThru
$mentorProcess.Id | Set-Content (Join-Path $mentorRoot 'server.pid')
for ($mentorAttempt=0; $mentorAttempt -lt 30; $mentorAttempt++) {
    Start-Sleep -Milliseconds 400
    try {
        $mentorReady = Invoke-RestMethod "$mentorUrl/api/state" -TimeoutSec 2
        if ($mentorReady.token) { Start-Process $mentorUrl -WindowStyle Hidden; exit 0 }
    } catch { }
    if ($mentorProcess.HasExited) { throw 'Le serveur s est arrete. Consulte server-error.log.' }
}
throw 'Le serveur ne repond pas. Consulte server-error.log.'
