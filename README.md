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

## Giocare

Il programma vuole uno dei due dischi supportati, riconosciuti dal CRC32 del
file (il nome non conta):

| Disco | CRC32 |
|---|---|
| `Rock Star Ate My Hamster (Europe).ipf` (il disco originale) | `53EC7260` |
| `Rock Star Ate My Hamster (1989)(Codemasters).adf` | `BB9DD80B` |

Lo si sceglie nel launcher (Browse For DISK), e nel menu Localization si
sceglie la lingua: **Italiano** (la traduzione) o **English** (il testo
originale). Il resto lo fa il programma: legge il disco (anche l'IPF, tracce
MFM comprese), decomprime il gioco, lo porta sempre alla stessa versione
(CRC verificato), applica la lingua e parte.

## Compilare

Servono clang (target mingw), CMake con Ninja, Python 3 con `unicorn`, e il
pacchetto di sviluppo SDL2.

```
python game/prepara_immagine.py --traduzione <cartella della traduzione>
cmake -S . -B build/cmake -G Ninja -DCMAKE_C_COMPILER=clang -DCMAKE_CXX_COMPILER=clang++
cmake --build build/cmake
```

`prepara_immagine.py` parte dai file della traduzione (la base del gioco
ricavata dal disco con `base_canonica.py`, l'immagine tradotta e le tabelle
dei testi) e produce:

- `build/rockstar_chipram.bin`, l'immagine italiana della chip RAM: da qui
  nasce il C ricompilato;
- `build/rockstar_chipram_en.bin`, l'inglese: stesso codice, dati del disco;
- `build/lingue_dati.h`, le differenze fra la base e le due immagini (solo
  dati nostri: traduzione, patch, codice aggiunto) e i CRC. L'eseguibile le
  applica alla base che ricava dal disco dell'utente (`amiga_disco.c`,
  `amiga_lingue.c`).

## Provare senza finestra

```
tools/prova_quadri.ps1 -quadri 3500 -exe build/cmake/RockStarAteMyHamsterRecomp.exe
```

Gira 3500 quadri (70 secondi di gioco), salva `build/quadro.png` e la memoria
finale. `AMIGA_INGRESSI="f:300,k44:500"` simula fuoco e tasti.

## Comandi

Il gioco si gioca col mouse: il pulsante sinistro sceglie e fa avanzare i
fumetti. Il primo clic nella finestra cattura il puntatore (senza scegliere
nulla); il pulsante centrale o F12 lo liberano.

Tasti e joypad si associano nel launcher (Mouse & Keyboard → Keys and
gamepad...). Predefiniti: frecce e Ctrl = joystick (su/giù nei menu, fuoco
sceglie); Spazio tenuto premuto ferma lo scorrere dei testi; Invio, Backspace
ed Esc servono a scrivere i nomi. Joypad: croce = joystick, A = fuoco,
RB/B = clic sinistro/destro, X = Spazio, Y = Invio, LB = Backspace,
Back = Esc; lo stick sinistro muove il puntatore. I tasti non associati vanno
alla tastiera dell'Amiga.

## Licenze

Il codice derivato da `segagenesisrecomp` (`amigarecomp/recompiler/src`,
`amigarecomp/runner/include`) e i sottomoduli `m68k-recomp-core` sono sotto
PolyForm Noncommercial 1.0.0 (vedi `amigarecomp/LICENSE-recompiler`);
`recomp-ui` è MIT. Uso non commerciale. Il gioco originale è © Codemasters.
