# build_native.ps1 - immagine, ricompilatore, C generato, runner.
#   tools\build_native.ps1 [-traduzione CARTELLA] [-sdl CARTELLA_SDL2]
# Provvisorio finche' il CMakeLists di primo livello non fa tutto da solo.
param([string]$traduzione = "", [string]$sdl = "")
$repo = Split-Path $PSScriptRoot -Parent
if (-not $sdl) { $sdl = Join-Path $repo "..\sdl\SDL2-2.32.2" }
Push-Location $repo
try {
    if (-not (Test-Path build\recompiler\AmigaRecomp.exe)) {
        cmake -S amigarecomp\recompiler -B build\recompiler -G Ninja -DCMAKE_C_COMPILER=clang -DCMAKE_BUILD_TYPE=Release | Out-Null
    }
    cmake --build build\recompiler | Select-String -Pattern "error" | Out-Host
    $a = @(); if ($traduzione) { $a = @("--traduzione", $traduzione) }
    python game\prepara_immagine.py @a | Out-Host
    python game\esporta_annotazioni.py | Out-Host
    Push-Location game
    ..\build\recompiler\AmigaRecomp.exe ..\build\rockstar_chipram.bin --game game.toml --output-dir ..\build\generated |
        Select-String -Pattern "Found|Final function count|error|Error" | Out-Host
    Pop-Location
    $gen = Get-ChildItem build\generated\rockstar_*.c | ForEach-Object FullName
    clang -O2 -w -Iamigarecomp\runner -Iamigarecomp\runner\include -Ibuild\generated -I"$sdl\include" @gen `
        amigarecomp\runner\amiga_glue.c amigarecomp\runner\amiga_hw.c game\rockstar_spec.c `
        -L"$sdl\lib\x64" -lSDL2 -o build\RockStarAteMyHamsterRecomp.exe 2>&1 | Select-String "error" | Out-Host
    if (-not (Test-Path build\SDL2.dll)) { Copy-Item "$sdl\lib\x64\SDL2.dll" build\ }
    Get-Item build\RockStarAteMyHamsterRecomp.exe | Select-Object Name, Length, LastWriteTime | Out-Host
} finally { Pop-Location }
