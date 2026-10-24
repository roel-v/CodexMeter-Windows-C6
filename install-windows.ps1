[CmdletBinding()]
param(
    [string]$BuildRoot = 'D:\build\CodexMeter',
    [switch]$InstallHooks,
    [switch]$StartAtLogin
)
$ErrorActionPreference = 'Stop'
& "$PSScriptRoot\build-windows.ps1" -BuildRoot $BuildRoot
. "$PSScriptRoot\scripts\windows-env.ps1" -BuildRoot $BuildRoot
$shell = New-Object -ComObject WScript.Shell
$link = $shell.CreateShortcut((Join-Path $PSScriptRoot 'CodexMeter.lnk'))
$link.TargetPath = $MeterPythonW
$link.Arguments = '-m codexmeter.windows_app'
$link.WorkingDirectory = $PSScriptRoot
$link.Description = 'CodexMeter — usage, displays and task alerts'
$link.Save()

if ($InstallHooks) {
    $hookHome = if ($env:CODEX_HOME) { $env:CODEX_HOME } else { Join-Path $env:USERPROFILE '.codex' }
    foreach ($hook in @(@('UserPromptSubmit', 'codexmeter_start_hook.py'), @('Stop', 'codexmeter_stop_hook.py'))) {
        $script = Join-Path $PSScriptRoot ('hooks\' + $hook[1])
        & $MeterPython "$PSScriptRoot\scripts\install_hook.py" --hooks-json (Join-Path $hookHome 'hooks.json') --event $hook[0] --windows-python $MeterPython --script $script
        if ($LASTEXITCODE) { throw "Could not install $($hook[0]) hook." }
    }
    Write-Host 'Review and trust the two new hooks in Codex /hooks before using task alerts.'
}
if ($StartAtLogin) {
    $startup = [Environment]::GetFolderPath('Startup')
    $link = $shell.CreateShortcut((Join-Path $startup 'CodexMeter Bridge.lnk'))
    $link.TargetPath = $MeterPythonW
    $link.Arguments = '-m codexmeter.daemon'
    $link.WorkingDirectory = $PSScriptRoot
    $link.WindowStyle = 7
    $link.Description = 'CodexMeter background Bluetooth bridge'
    $link.Save()
}
Write-Host "Installed launcher: $PSScriptRoot\CodexMeter.lnk"
