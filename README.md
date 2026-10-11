# Rock Star Ate My Hamster — Recomp (traduzione italiana)

Port nativo per **ricompilazione statica** di *Rock Star Ate My Hamster*
(Amiga, Codemasters 1989, di Colin Jones), con la traduzione italiana completa.
Il codice 68000 del gioco viene tradotto in C prima della compilazione e
gira in modo nativo: nessun emulatore di CPU. L'hardware dell'Amiga (copper,
bitplane, CIA, interrupt) è riprodotto dal runner.

Basato sugli strumenti della [Retro Porting Toolkit](https://retroportingtoolkit.com/docs):

- [`m68k-recomp-core`](https://github.com/mstan/m68k-recomp-core): il frontend
  68000 (decoder, validatore, generatore di C);
- [`recomp-ui`](https://github.com/mstan/recomp-ui): il launcher, con un
  profilo **Amiga** aggiunto (ramo `amiga`).

**Il repository non contiene file del gioco** e nemmeno il C generato.

## Struttura

| Cartella | Contenuto |
|---|---|
| `amigarecomp/recompiler` | AmigaRecomp: il ricompilatore (immagine Amiga → C) |
| `amigarecomp/runner` | il runner Amiga: ABI del C generato, chip custom, CIA, video, SDL |
| `game/` | Rock Star: `game.toml`, nomi delle funzioni, specifica, preparazione dell'immagine |
| `external/` | sottomoduli del toolkit |
| `tools/` | script di build e di prova |

## Compilare

Servono clang (target mingw), CMake con Ninja, Python 3 con `unicorn`, e il
pacchetto di sviluppo SDL2.

```
python game/prepara_immagine.py --traduzione <cartella della traduzione>
cmake -S . -B build/cmake -G Ninja -DCMAKE_C_COMPILER=clang -DCMAKE_CXX_COMPILER=clang++
cmake --build build/cmake
```

`prepara_immagine.py` costruisce la fotografia della chip RAM dai tuoi file
(l'immagine del gioco decompressa e le tabelle dei testi della traduzione).

## Provare senza finestra

```
tools/prova_quadri.ps1 -quadri 3500 -exe build/cmake/RockStarAteMyHamsterRecomp.exe
```

Gira 3500 quadri (70 secondi di gioco), salva `build/quadro.png` e la memoria
finale. `AMIGA_INGRESSI="f:300,k44:500"` simula fuoco e tasti.

## Comandi

Joystick in porta 2: frecce e Ctrl. Mouse: pulsante sinistro. Tastiera: i
tasti vanno alla tastiera dell'Amiga.

## Licenze

Il codice derivato da `segagenesisrecomp` (`amigarecomp/recompiler/src`,
`amigarecomp/runner/include`) e i sottomoduli `m68k-recomp-core` sono sotto
PolyForm Noncommercial 1.0.0 (vedi `amigarecomp/LICENSE-recompiler`);
`recomp-ui` è MIT. Uso non commerciale. Il gioco originale è © Codemasters.
