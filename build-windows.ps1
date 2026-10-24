[CmdletBinding()]
param(
    [string]$BuildRoot = 'D:\build\CodexMeter',
    [switch]$Firmware,
    [switch]$Test,
    [ValidateSet('waveshare_c6_amoled_216', 'waveshare_amoled_216')]
    [string]$Board = 'waveshare_c6_amoled_216'
)
$ErrorActionPreference = 'Stop'
. "$PSScriptRoot\scripts\windows-env.ps1" -BuildRoot $BuildRoot
if ((Get-PSDrive D).Free -lt 8GB) { throw 'At least 8 GiB free on D: is required. Review cold storage before building.' }
if (-not (Get-Command uv -ErrorAction SilentlyContinue)) { throw 'Install uv and put it on PATH first.' }
if (-not (Test-Path -LiteralPath $MeterPython)) {
    & uv venv --python 3.12 (Join-Path $BuildRoot 'venv')
    if ($LASTEXITCODE) { throw 'Python environment creation failed.' }
}
& uv pip install --python $MeterPython -e $PSScriptRoot pytest platformio
if ($LASTEXITCODE) { throw 'Dependency installation failed.' }
Push-Location $PSScriptRoot
try {
    if ($Test) {
        & $MeterPython -m pytest -q -p no:cacheprovider
        if ($LASTEXITCODE) { throw 'Tests failed.' }
    }
    if ($Firmware) {
        if ($Board -eq 'waveshare_c6_amoled_216' -and -not (Test-Path -LiteralPath $env:CODEXMETER_FONT_CONVERTER)) {
            & npm.cmd install --prefix (Join-Path $BuildRoot 'font-tools') --no-audit --no-fund lv_font_conv@1.5.3
            if ($LASTEXITCODE) { throw 'C6 font converter installation failed.' }
        }
        & $MeterPython -m platformio run -d firmware -e $Board
        if ($LASTEXITCODE) { throw 'Firmware build failed.' }
    }
} finally { Pop-Location }
Write-Host "Ready. Python: $MeterPython"
