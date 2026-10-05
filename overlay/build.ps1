$ErrorActionPreference = 'Stop'
$source = Join-Path $PSScriptRoot 'RecordingOverlay.cs'
$output = Join-Path $PSScriptRoot 'CapsWriter.Indicator.exe'
$compiler = @(
    "$env:WINDIR\Microsoft.NET\Framework64\v4.0.30319\csc.exe",
    "$env:WINDIR\Microsoft.NET\Framework\v4.0.30319\csc.exe"
) | Where-Object { Test-Path -LiteralPath $_ } | Select-Object -First 1
if (-not $compiler) { throw 'Microsoft .NET Framework 4.x C# compiler (csc.exe) was not found.' }
& $compiler /nologo /target:winexe /optimize+ /out:$output /reference:System.Windows.Forms.dll /reference:System.Drawing.dll $source
if ($LASTEXITCODE -ne 0) { throw "C# compilation failed with exit code $LASTEXITCODE" }
Write-Host "Built $output"
