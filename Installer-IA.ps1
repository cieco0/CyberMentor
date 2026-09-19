$ErrorActionPreference = 'Stop'
$mentorOllama = Join-Path $env:LOCALAPPDATA 'Programs\Ollama\ollama.exe'
if (-not (Test-Path $mentorOllama)) {
    winget install --id Ollama.Ollama --exact --silent --accept-package-agreements --accept-source-agreements --disable-interactivity
    if ($LASTEXITCODE -ne 0) { throw 'Installation impossible. Installe Ollama depuis https://ollama.com/download/windows puis relance ce script.' }
}
if (-not (Test-Path $mentorOllama)) { throw 'Ollama introuvable dans le dossier utilisateur.' }
try { $null = Invoke-RestMethod 'http://127.0.0.1:11434/api/tags' -TimeoutSec 3 }
catch {
    Start-Process $mentorOllama -ArgumentList 'serve' -WindowStyle Hidden
    Start-Sleep -Seconds 4
}
Write-Host 'Telechargement du modele local qwen2.5:7b (environ 4,7 Go)...'
& $mentorOllama pull qwen2.5:7b
if ($LASTEXITCODE -ne 0) { throw 'Telechargement interrompu. Relance ce script pour reprendre.' }
Write-Host 'Ton moteur IA est pret. Lance Lancer.cmd.'


