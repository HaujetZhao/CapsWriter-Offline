param(
    [string]$AppDir = (Join-Path $PSScriptRoot '..')
)

$ErrorActionPreference = 'Stop'
$AppDir = (Resolve-Path -LiteralPath $AppDir).Path

foreach ($exe in @('start_server.exe', 'start_client.exe')) {
    $path = Join-Path $AppDir $exe
    if (-not (Test-Path -LiteralPath $path)) {
        throw "CapsWriter executable not found: $path"
    }
    $running = Get-CimInstance Win32_Process -Filter "name='$exe'" |
        Where-Object { $_.ExecutablePath -eq $path }
    if (-not $running) {
        Start-Process -FilePath $path -WorkingDirectory $AppDir -WindowStyle Hidden
    }
}

$indicator = Join-Path $PSScriptRoot 'CapsWriter.Indicator.exe'
if (Test-Path -LiteralPath $indicator) {
    $env:CAPSWRITER_APP_DIR = $AppDir
    Start-Process -FilePath $indicator -WorkingDirectory $PSScriptRoot -WindowStyle Hidden
} else {
    Write-Warning 'Recording overlay executable is missing. Build it with build.ps1.'
}
