# crea_release.ps1 - lo zip della release: eseguibile, DLL, assets del
# launcher (font, logo Amiga, copertina) e LEGGIMI. Niente file del gioco.
#   tools\crea_release.ps1 -versione 1.1.0 [-leggimi ..\release\LEGGIMI.txt] [-uscita ..\release]
param([Parameter(Mandatory)][string]$versione,
      [string]$leggimi = "", [string]$uscita = "")
$ErrorActionPreference = "Stop"
$repo = Split-Path $PSScriptRoot -Parent
$build = Join-Path $repo "build\cmake"
if (-not $uscita) { $uscita = Join-Path (Split-Path $repo -Parent) "release" }
if (-not $leggimi) { $leggimi = Join-Path $uscita "LEGGIMI.txt" }
$nome = "RockStarAteMyHamster_ITA_v$versione"
$d = Join-Path $uscita $nome
if (Test-Path $d) { throw "$d esiste gia'" }
New-Item -ItemType Directory -Force $d | Out-Null

# le DLL del runtime di clang (libc++, libunwind) stanno accanto a clang
$clang = (Get-Command clang).Source
$rt = Join-Path (Split-Path (Split-Path $clang)) "x86_64-w64-mingw32\bin"
Copy-Item (Join-Path $build "RockStarAteMyHamsterRecomp.exe"), (Join-Path $build "SDL2.dll"),
          (Join-Path $rt "libc++.dll"), (Join-Path $rt "libunwind.dll"), $leggimi $d
Copy-Item -Recurse (Join-Path $build "assets") $d

$zip = Join-Path $uscita "${nome}_Windows.zip"
Compress-Archive -Path $d -DestinationPath $zip -Force
Get-ChildItem -Recurse $d -File | ForEach-Object { $_.FullName.Substring($d.Length + 1) }
"zip: $zip ($((Get-Item $zip).Length) byte)"
