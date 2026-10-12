cmake_minimum_required(VERSION 3.16)
project(RockStarAteMyHamsterRecomp C CXX)

# Rock Star Ate My Hamster (Amiga, Codemasters 1989) - port nativo per
# ricompilazione statica, traduzione italiana.
#
#   0. python traduzione/base_canonica.py <disco.ipf|disco.adf> ../rockstar_base.bin
#   1. python game/prepara_immagine.py      (build/rockstar_chipram.bin e i dati per l'eseguibile)
#   2. cmake -S . -B build -G Ninja -DCMAKE_C_COMPILER=clang -DCMAKE_CXX_COMPILER=clang++
#   3. cmake --build build
#
# Il C generato sta solo nella cartella di build e non si modifica a mano.

set(CMAKE_C_STANDARD 11)
set(CMAKE_CXX_STANDARD 17)

set(ROCKSTAR_IMAGE "${CMAKE_SOURCE_DIR}/build/rockstar_chipram.bin" CACHE FILEPATH
    "Immagine della chip RAM preparata da game/prepara_immagine.py")
set(ROCKSTAR_SDL2_DIR "${CMAKE_SOURCE_DIR}/../sdl/SDL2-2.32.2" CACHE PATH
    "Pacchetto di sviluppo SDL2 (include/ e lib/x64/)")
option(ROCKSTAR_LAUNCHER "Launcher recomp-ui all'avvio" ON)

# ---- ricompilatore ---------------------------------------------------------------
add_subdirectory(amigarecomp/recompiler)

set(GEN_DIR "${CMAKE_BINARY_DIR}/generated")
set(GEN_FILES "${GEN_DIR}/rockstar_decls.h" "${GEN_DIR}/rockstar_dispatch.c"
              "${GEN_DIR}/rockstar_layout.c" "${GEN_DIR}/rockstar_cycles.c")
foreach(i RANGE 0 31)
    string(LENGTH "${i}" _n)
    if(_n EQUAL 1)
        set(i "0${i}")
    endif()
    list(APPEND GEN_FILES "${GEN_DIR}/rockstar_part${i}.c")
endforeach()

add_custom_command(
    OUTPUT ${GEN_FILES}
    COMMAND AmigaRecomp "${ROCKSTAR_IMAGE}" --game game.toml --output-dir "${GEN_DIR}"
    WORKING_DIRECTORY "${CMAKE_SOURCE_DIR}/game"
    DEPENDS AmigaRecomp "${ROCKSTAR_IMAGE}"
            "${CMAKE_SOURCE_DIR}/game/game.toml"
            "${CMAKE_SOURCE_DIR}/game/rockstar_annotations.csv"
    COMMENT "AmigaRecomp: 68000 -> C"
    VERBATIM)

# CRC dell'immagine da cui nasce il C: l'eseguibile rifiuta un'immagine diversa
find_package(Python3 REQUIRED COMPONENTS Interpreter)
add_custom_command(
    OUTPUT "${GEN_DIR}/immagine_crc.h"
    COMMAND Python3::Interpreter "${CMAKE_SOURCE_DIR}/tools/crc_immagine.py"
            "${ROCKSTAR_IMAGE}" "${GEN_DIR}/immagine_crc.h"
    DEPENDS "${ROCKSTAR_IMAGE}" "${CMAKE_SOURCE_DIR}/tools/crc_immagine.py"
    COMMENT "CRC dell'immagine"
    VERBATIM)
list(APPEND GEN_FILES "${GEN_DIR}/immagine_crc.h")

# ---- runner + gioco ----------------------------------------------------------------
add_executable(RockStarAteMyHamsterRecomp
    amigarecomp/runner/amiga_glue.c
    amigarecomp/runner/amiga_hw.c
    amigarecomp/runner/amiga_debug.c
    amigarecomp/runner/amiga_paula.c
    amigarecomp/runner/amiga_video_gl.c
    amigarecomp/runner/amiga_ingressi.c
    amigarecomp/runner/amiga_disco.c
    amigarecomp/runner/amiga_lingue.c
    amigarecomp/runner/amiga_esporta.c
    amigarecomp/runner/amiga_console.c
    amigarecomp/runner/amiga_menu.c
    game/rockstar_menu.c
    game/rockstar_spec.c
    game/rockstar_debug.c
    game/rockstar_mods.c
    ${GEN_FILES})

target_include_directories(RockStarAteMyHamsterRecomp PRIVATE
    amigarecomp/runner
    amigarecomp/runner/include
    game
    external/recomp-ui/src
    "${GEN_DIR}"
    "${CMAKE_SOURCE_DIR}/build"            # lingue_dati.h e amiga_kit.h da game/prepara_immagine.py
    "${ROCKSTAR_SDL2_DIR}/include")

target_link_directories(RockStarAteMyHamsterRecomp PRIVATE "${ROCKSTAR_SDL2_DIR}/lib/x64")
target_link_libraries(RockStarAteMyHamsterRecomp PRIVATE SDL2 opengl32)
# applicazione grafica: niente finestra della shell (la apre --debug,
# amiga_console.c)
if(WIN32)
    target_link_options(RockStarAteMyHamsterRecomp PRIVATE -mwindows)
endif()
# libc++ e libunwind dentro l'eseguibile: niente DLL del compilatore da
# distribuire (resta solo SDL2.dll)
if(MINGW OR CMAKE_CXX_COMPILER_TARGET MATCHES "mingw" OR CMAKE_C_COMPILER_ID STREQUAL "Clang")
    target_link_options(RockStarAteMyHamsterRecomp PRIVATE -static-libstdc++ -static-libgcc
                        "-Wl,-Bstatic" -lc++ -lunwind "-Wl,-Bdynamic"
                        $<$<CONFIG:Release>:-s>)   # senza simboli: piu' leggero
endif()
# il C generato e' grande e ripetitivo: niente avvisi da li'
set_source_files_properties(${GEN_FILES} PROPERTIES COMPILE_OPTIONS "-w")

if(ROCKSTAR_LAUNCHER)
    set(RECOMP_UI_SDL3 OFF CACHE BOOL "" FORCE)
    if(NOT DEFINED RECOMP_UI_ENABLE_MODS)
        set(RECOMP_UI_ENABLE_MODS ON CACHE BOOL "Menu Mods del launcher (trucchi)")
    endif()
    include("${CMAKE_SOURCE_DIR}/external/recomp-ui/recomp_ui.cmake")
    recomp_target_launcher_ui(RockStarAteMyHamsterRecomp CONSOLE amiga)
    # la copertina (tools/disegna_copertina.py), che il launcher mostra quando
    # il disco e' riconosciuto: copiata a ogni build, anche se l'eseguibile non cambia
    add_custom_target(rockstar_copertina ALL
        COMMAND ${CMAKE_COMMAND} -E copy_if_different
                "${CMAKE_SOURCE_DIR}/game/copertina.jpg"
                "$<TARGET_FILE_DIR:RockStarAteMyHamsterRecomp>/assets/img/copertina.jpg"
        DEPENDS RockStarAteMyHamsterRecomp
        COMMENT "copertina accanto all'eseguibile")
    target_include_directories(RockStarAteMyHamsterRecomp PRIVATE
        "${CMAKE_SOURCE_DIR}/external/recomp-ui/src")
endif()

add_custom_command(TARGET RockStarAteMyHamsterRecomp POST_BUILD
    COMMAND ${CMAKE_COMMAND} -E copy_if_different
            "${ROCKSTAR_SDL2_DIR}/lib/x64/SDL2.dll" "$<TARGET_FILE_DIR:RockStarAteMyHamsterRecomp>"
    COMMAND ${CMAKE_COMMAND} -E copy_if_different
            "${CMAKE_SOURCE_DIR}/game/rockstar_annotations.csv" "$<TARGET_FILE_DIR:RockStarAteMyHamsterRecomp>")

# L'eseguibile carica l'immagine che gli sta accanto: va tenuta allineata a
# ogni build, anche quando cambiano solo i dati e il C generato no.
add_custom_target(rockstar_immagine ALL
    COMMAND ${CMAKE_COMMAND} -E copy_if_different
            "${ROCKSTAR_IMAGE}" "$<TARGET_FILE_DIR:RockStarAteMyHamsterRecomp>/rockstar_chipram.bin"
    DEPENDS RockStarAteMyHamsterRecomp
    COMMENT "immagine della chip RAM accanto all'eseguibile")
