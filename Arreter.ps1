$mentorPidFile = Join-Path $PSScriptRoot 'server.pid'
if (Test-Path $mentorPidFile) {
    $mentorProcessId = [int](Get-Content $mentorPidFile)
    $mentorProcess = Get-CimInstance Win32_Process -Filter "ProcessId = $mentorProcessId" -ErrorAction SilentlyContinue
    $mentorExpectedScript = Join-Path $PSScriptRoot 'app.py'
    if ($mentorProcess -and $mentorProcess.Name -match '^python(w)?\.exe$' -and $mentorProcess.CommandLine.Contains($mentorExpectedScript)) {
        Stop-Process -Id $mentorProcessId
    }
    Remove-Item -LiteralPath $mentorPidFile
}
