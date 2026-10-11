cmake_minimum_required(VERSION 3.16)
project(AmigaRecomp C)

# Ricompilatore statico 68000 -> C per giochi Amiga (OCS/ECS).
# Frontend: m68k-recomp-core, profilo "genesis" (68000 puro, senza le
# estensioni SCC68070). Di Genesis qui c'e' solo il nome del profilo: decoder,
# validatore e generatore sono quelli del 68000 e non conoscono l'hardware.
# L'immagine e' una fotografia della chip RAM (src/rom_parser.c).

set(CMAKE_C_STANDARD 11)

if(NOT M68K_RECOMP_CORE_DIR)
    set(M68K_RECOMP_CORE_DIR "${CMAKE_CURRENT_SOURCE_DIR}/../../external/m68k-recomp-core")
endif()
include("${M68K_RECOMP_CORE_DIR}/cmake/M68kRecompCore.cmake")
m68k_recomp_core_sources(M68K_RECOMP_CORE_SOURCES genesis)
m68k_recomp_core_include_dirs(M68K_RECOMP_CORE_INCLUDE_DIRS genesis)

add_executable(AmigaRecomp
    src/main_amiga.c
    src/rom_parser.c
    ${M68K_RECOMP_CORE_SOURCES}
    src/game_config.c
    src/toml.c
)

target_include_directories(AmigaRecomp PRIVATE
    src
    ${M68K_RECOMP_CORE_INCLUDE_DIRS}
)

set_target_properties(AmigaRecomp PROPERTIES
    RUNTIME_OUTPUT_DIRECTORY "${CMAKE_BINARY_DIR}"
)
