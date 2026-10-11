# prova_quadri.ps1 - fa girare il port senza finestra e salva l'ultimo quadro.
#   tools\prova_quadri.ps1 [-quadri 3500] [-ingressi "f:3000"] [-exe build\...exe]
param([int]$quadri = 300, [string]$ingressi = "",
      [string]$exe = "build\RockStarAteMyHamsterRecomp.exe",
      [string]$immagine = "build\rockstar_chipram.bin")
$repo = Split-Path $PSScriptRoot -Parent
$dir = Join-Path $repo "build"
$sdl = Join-Path $repo "..\sdl\SDL2-2.32.2\lib\x64\SDL2.dll"
if (-not (Test-Path "$dir\SDL2.dll") -and (Test-Path $sdl)) { Copy-Item $sdl $dir }
$env:AMIGA_QUADRI = "$quadri"; $env:AMIGA_INGRESSI = $ingressi
$p = Start-Process -FilePath (Join-Path $repo $exe) -ArgumentList ("`"" + (Join-Path $repo $immagine) + "`"") -WorkingDirectory $dir `
    -NoNewWindow -PassThru -RedirectStandardOutput "$dir\out.txt" -RedirectStandardError "$dir\err.txt"
if (-not $p.WaitForExit(300000)) { $p.Kill(); "TIMEOUT (bloccato)" }
$env:AMIGA_QUADRI = $null; $env:AMIGA_INGRESSI = $null
Get-Content "$dir\out.txt", "$dir\err.txt"
if (Test-Path "$dir\quadro.bmp") {
    Add-Type -AssemblyName System.Drawing
    $b = [Drawing.Image]::FromFile("$dir\quadro.bmp"); $b2 = New-Object Drawing.Bitmap 640, 512
    $g = [Drawing.Graphics]::FromImage($b2); $g.InterpolationMode = 'NearestNeighbor'; $g.DrawImage($b, 0, 0, 640, 512)
    $b2.Save("$dir\quadro.png"); $b.Dispose(); $b2.Dispose()
}
