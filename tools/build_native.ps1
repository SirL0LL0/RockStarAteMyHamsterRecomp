# build_native.ps1 - immagine + ricompilatore + C generato + runner, tutto via CMake.
#   tools\build_native.ps1 [-traduzione CARTELLA]
# L'eseguibile e' sempre build\cmake\RockStarAteMyHamsterRecomp.exe
param([string]$traduzione = "")
$repo = Split-Path $PSScriptRoot -Parent
Push-Location $repo
try {
    $a = @(); if ($traduzione) { $a = @("--traduzione", $traduzione) }
    python game\prepara_immagine.py @a | Out-Host
    python game\esporta_annotazioni.py | Out-Host
    if (-not (Test-Path build\cmake\build.ninja)) {
        cmake -S . -B build\cmake -G Ninja -DCMAKE_C_COMPILER=clang -DCMAKE_CXX_COMPILER=clang++ `
              -DCMAKE_BUILD_TYPE=Release -DRECOMP_UI_ENABLE_MODS:BOOL=ON | Out-Null
    }
    cmake --build build\cmake | Select-String -Pattern "error|FAILED|Linking CXX" | Out-Host
    Copy-Item build\rockstar_chipram.bin build\cmake\ -Force
    Get-Item build\cmake\RockStarAteMyHamsterRecomp.exe | Select-Object FullName, LastWriteTime | Out-Host
} finally { Pop-Location }
