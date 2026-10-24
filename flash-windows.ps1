[CmdletBinding()]
param(
    [Parameter(Mandatory)][ValidatePattern('^COM[0-9]+$')][string]$Port,
    [ValidateSet('waveshare_c6_amoled_216', 'waveshare_amoled_216')]
    [string]$Board = 'waveshare_c6_amoled_216',
    [string]$BuildRoot = 'D:\build\CodexMeter',
    [switch]$FirstFlash
)
$ErrorActionPreference = 'Stop'
. "$PSScriptRoot\scripts\windows-env.ps1" -BuildRoot $BuildRoot
if (-not (Test-Path -LiteralPath $MeterPython)) { throw 'Run build-windows.ps1 -Firmware first.' }
if (-not $FirstFlash) {
    & $MeterPython "$PSScriptRoot\tools\serial_device.py" --identify $Port
    if ($LASTEXITCODE) { throw 'The port is not a running CodexMeter. For initial setup, verify the board and use -FirstFlash.' }
}
Write-Host "Writing $Board to $Port. This replaces the board's installed application."
# esptool checks the chip family. Never use --force to bypass that check.
& $MeterPython -m platformio run -d "$PSScriptRoot\firmware" -e $Board -t upload --upload-port $Port
if ($LASTEXITCODE) { throw 'Firmware upload failed.' }
# C6's normal upload includes the raw artwork pack through FLASH_EXTRA_IMAGES.
# Its artwork partition is not LittleFS; do not run uploadfs for C6.
if ($Board -eq 'waveshare_amoled_216') {
    & $MeterPython -m platformio run -d "$PSScriptRoot\firmware" -e $Board -t uploadfs --upload-port $Port
    if ($LASTEXITCODE) { throw 'Filesystem upload failed.' }
}
