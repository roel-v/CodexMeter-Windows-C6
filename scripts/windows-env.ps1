param([string]$BuildRoot = 'D:\build\CodexMeter')
$ErrorActionPreference = 'Stop'
$BuildRoot = [IO.Path]::GetFullPath($BuildRoot)
if ([IO.Path]::GetPathRoot($BuildRoot) -ne 'D:\') {
    throw 'Active builds and dependency caches must be on D:.'
}
$env:UV_CACHE_DIR = Join-Path $BuildRoot 'uv-cache'
$env:UV_PYTHON_INSTALL_DIR = Join-Path $BuildRoot 'python'
$env:UV_TOOL_DIR = Join-Path $BuildRoot 'uv-tools'
$env:PIP_CACHE_DIR = Join-Path $BuildRoot 'pip-cache'
$env:npm_config_cache = Join-Path $BuildRoot 'npm-cache'
$env:CODEXMETER_FONT_CONVERTER = Join-Path $BuildRoot 'font-tools\node_modules\lv_font_conv\lv_font_conv.js'
$env:PLATFORMIO_CORE_DIR = Join-Path $BuildRoot 'platformio'
$env:PLATFORMIO_BUILD_DIR = Join-Path $BuildRoot 'firmware-build'
$env:PLATFORMIO_LIBDEPS_DIR = Join-Path $BuildRoot 'libdeps'
$env:PLATFORMIO_CACHE_DIR = Join-Path $BuildRoot 'pio-cache'
$env:TEMP = Join-Path $BuildRoot 'tmp'
$env:TMP = $env:TEMP
$env:PYTHONDONTWRITEBYTECODE = '1'
$env:PYTHONUTF8 = '1'
New-Item -ItemType Directory -Force -Path $env:TEMP | Out-Null
$MeterPython = Join-Path $BuildRoot 'venv\Scripts\python.exe'
$MeterPythonW = Join-Path $BuildRoot 'venv\Scripts\pythonw.exe'
