# crea_release.ps1 - lo zip della release: eseguibile, SDL2.dll, assets del
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

# libc++ e libunwind sono dentro l'eseguibile (CMakeLists.txt)
Copy-Item (Join-Path $build "RockStarAteMyHamsterRecomp.exe"), (Join-Path $build "SDL2.dll"), $leggimi $d
Copy-Item -Recurse (Join-Path $build "assets") $d
# del launcher bastano i font Lato, il logo Amiga, il joypad e la copertina:
# emoji e bandiere (chat del netplay), verdetti dei dischi PSX e logo
# generico non servono a un gioco Amiga e pesano 3 MB
foreach ($x in "fonts\OpenMoji-black-glyf.ttf", "fonts\NotoSansSymbols2-Regular.ttf", "img\flags.png",
               "img\brand_mark.tga", "img\verdict_ok.tga", "img\verdict_warn.tga", "img\verdict_bad.tga",
               "img\verdict_none.tga") { Remove-Item -LiteralPath (Join-Path $d "assets\$x") }

$zip = Join-Path $uscita "${nome}_Windows.zip"
Compress-Archive -Path $d -DestinationPath $zip -Force
Get-ChildItem -Recurse $d -File | ForEach-Object { $_.FullName.Substring($d.Length + 1) }
"zip: $zip ($((Get-Item $zip).Length) byte)"
