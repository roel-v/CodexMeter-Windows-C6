[CmdletBinding()]
param(
    [string]$BuildRoot = 'D:\build\CodexMeter',
    [ValidateSet('onefile', 'standalone')][string]$Mode = 'onefile'
)
$ErrorActionPreference = 'Stop'
. "$PSScriptRoot\scripts\windows-env.ps1" -BuildRoot $BuildRoot
if ((Get-PSDrive D).Free -lt 8GB) { throw 'At least 8 GiB free on D: is required.' }
if (-not (Test-Path -LiteralPath $MeterPython)) { throw 'Run build-windows.ps1 first.' }
$env:NUITKA_CACHE_DIR = Join-Path $BuildRoot 'nuitka-cache'
$output = Join-Path $BuildRoot ('desktop-' + $Mode)
New-Item -ItemType Directory -Force -Path $output | Out-Null
& uv pip install -q --python $MeterPython -e $PSScriptRoot 'Nuitka==4.3.1' ordered-set zstandard
if ($LASTEXITCODE) { throw 'Nuitka dependency installation failed.' }
Push-Location $PSScriptRoot
try {
    & $MeterPython -m nuitka "--mode=$Mode" --msvc=latest --jobs=8 --lto=no `
        --enable-plugin=tk-inter --include-package=codexmeter --include-package=winrt `
        --include-package=bleak.backends.winrt --windows-console-mode=attach `
        --include-module=pystray._win32 --include-module=PIL.IcoImagePlugin `
        --assume-yes-for-downloads --output-filename=CodexMeter.exe "--output-dir=$output" `
        --company-name=CodexMeter --product-name=CodexMeter --file-version=3.12.1.5 `
        --product-version=3.12.1.5 --file-description='CodexMeter Windows companion' `
        "--report=$output\compilation-report.xml" windows_entry.py
    if ($LASTEXITCODE) { throw 'Standalone build failed.' }
} finally { Pop-Location }
Write-Host "Build output: $output"
