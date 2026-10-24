param([string]$BuildRoot = 'D:\build\CodexMeter')
$standalone = Join-Path $PSScriptRoot 'dist\windows\CodexMeter.exe'
if (Test-Path -LiteralPath $standalone) {
    Start-Process -FilePath $standalone -WorkingDirectory (Split-Path $standalone) -WindowStyle Hidden
    return
}
. "$PSScriptRoot\scripts\windows-env.ps1" -BuildRoot $BuildRoot
if (-not (Test-Path -LiteralPath $MeterPythonW)) { throw 'Run build-windows.ps1 first.' }
Start-Process -FilePath $MeterPythonW -ArgumentList '-m codexmeter.windows_app' -WorkingDirectory $PSScriptRoot -WindowStyle Hidden
