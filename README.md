# Rock Star Ate My Hamster — Recomp (Italian translation)

**English** | [Italiano](README.it.md)

A native port of *Rock Star Ate My Hamster* (Amiga, Codemasters 1989, by
Colin Jones) built by **static recompilation**, with a complete Italian
translation; the original English text is available too. The game's 68000
code is translated to C before compiling and runs natively: there is no CPU
emulator. The Amiga hardware (copper, bitplanes, CIAs, interrupts) is
reproduced by the runner.

Built with the [Retro Porting Toolkit](https://retroportingtoolkit.com/docs):

- [`m68k-recomp-core`](https://github.com/mstan/m68k-recomp-core): the 68000
  front end (decoder, validator, C generator);
- [`recomp-ui`](https://github.com/mstan/recomp-ui): the launcher, with an
  added **Amiga** profile (`amiga` branch).

**The repository contains no game files**, and no generated C either.

## Layout

| Folder | Contents |
|---|---|
| `amigarecomp/recompiler` | AmigaRecomp: the recompiler (Amiga image → C) |
| `amigarecomp/runner` | the Amiga runner: ABI of the generated C, custom chips, CIAs, video, SDL |
| `game/` | Rock Star: `game.toml`, function names, game spec, image preparation |
| `traduzione/` | the translation: texts, patches, added 68000 code, editor, Amiga builds (ADF, WHDLoad) |
| `external/` | toolkit submodules |
| `tools/` | build and test scripts |

## The game

*Rock Star Ate My Hamster* (Codemasters, 1989; also on Atari ST, C64,
Amstrad CPC and ZX Spectrum). Designed and programmed by Colin Jones,
graphics by Brian Hartley and Chris Graham, music by Allister Brimble, Colin
Jones, Gavin Raeburn and Paul Hiley. The title spoofs the famous 1986 tabloid
headline about Freddie Starr; the box included *The Stun*, a fake tabloid
(horoscopes, comics, gossip about the stars the game parodies).

You manage a band: starting from the £50,000 left by Aunt Mabel, you pick
rock stars at auditions, rehearse them, take them on tour, and record and
release singles and albums. You win by earning **4 silver discs** within a
year; you lose by going broke or running out of stars.

The main menu: **REHEARSE**, **GIG** (tours: venues, ticket price, number of
nights; your main source of income), **PRESS** (publicity stunts: they raise
your fame but can backfire), **GIFTS** (to keep the stars happy), **RECORD** /
**RELEASE** (studio, titles, singles, albums, videos), **SAVE/LOAD**, **QUIT**.
Along the way come charity gigs, sponsors, record companies, pirates and the
taxman.

Tips from the manual's *Cecil Pitt Guide to Rock Management*:

- the more stars you have, the more popular you are; cheap stars are usually
  less talented, less loved and touchier (but not always);
- rehearse before looking for a deal: record companies want bands that
  already have fans;
- choose venues and prices carefully: a new band won't fill a stadium at £20
  a ticket;
- don't wear the band out: let them rest and give them gifts, or the stars
  make trouble, demand artistic control or quit;
- weigh record deals but don't play too hard to get: when popularity drops,
  the offers vanish;
- use the best studio you can afford; hit singles sell the album; make a
  video when you can, choosing the director, location and content carefully.

**Original cheat**: during the game type `COLBOPS`, then F7 adds money (a
million pounds in this version; the guides say 100,000), F8 makes the band
play at its best, F9 maximises the audience. It can also be switched on from
the launcher's Mods page or the in-game menu.

**Why stars quit.** Every star has a hidden happiness value. Before each
night of a tour the game looks at the unhappiest one: at 9 or more the night
goes smoothly and everybody loses a point; below 9 the demands start (go-go
girls, then the Porsche blackmail: refuse and the star is fired) and, with 2
silver discs (below 4) or 3 (below 9), the star just walks out. Every
departure halves the band's quality; with no stars left it's game over.
Gifts raise everyone (car +12, jewels +11, clothes +10, drinks +9, food +8).

**Tickets.** Tickets sold are the lower of the venue capacity and
10 × price factor × band quality (1-255), with factors 9, 6, 4, 2, 1 for
£2, 5, 10, 15, 20: at £15 and £20 a stadium never sells out, not even with
the band at its best (5,100 and 2,550 tickets). At a stadium the best price
is £10.

Among the mods (launcher and F1 menu), besides the cheats: **Always happy
stars** (nobody quits, no blackmail) and **Stadiums sell out at any price**
(factors 9, 8, 6, 5, 4: a top band fills a stadium even at £20).

Sources: the original manual, the manual at
[Games Database](https://www.gamesdatabase.org/Media/SYSTEM/Commodore_Amiga//Manual/formated/Rock_Star_Ate_my_Hamster_-_1989_-_Codemasters.htm),
[The Codemasters Archive](https://thecodemastersarchive.co.uk/games/rock-star-ate-my-hamster/),
[Lemon Amiga](https://www.lemonamiga.com/doc/rock-star-ate-my-hamster/1372).

## Playing

The program needs one of the two supported disks, recognised by the CRC32
of the file (the name doesn't matter):

| Disk | CRC32 |
|---|---|
| `Rock Star Ate My Hamster (Europe).ipf` (the original disk) | `53EC7260` |
| `Rock Star Ate My Hamster (1989)(Codemasters).adf` | `BB9DD80B` |

Pick it in the launcher (Browse For DISK) and choose the language under
Localization: **Italiano** (the translation) or **English** (the original
text); the launcher's own texts follow the same language. Once the disk is
recognised the cover art appears. The program does the rest: it reads the
disk (the IPF too, MFM tracks included), unpacks the game, brings it to one
known version (CRC checked), applies the language and starts.

The launcher settings also have:

- **Screen model**: *Sharp* (crisp pixels; softened with *Linear
  filtering*), *Commodore 1084S* (the Amiga monitor: gaussian beam, slot
  mask, halation, light curvature), *CRT Easymode* (a flat CRT in the style
  of crt-easymode: Lanczos, gaussian beam, light mask), *Scanlines*. In game
  Shift+F12 switches to the next model;
- **Aspect ratio**: *PAL (4:3)* (the default: wide pixels as on a PAL
  monitor) or *Square pixels*;
- **Integer scaling** (on by default): pixel perfect, the largest whole
  factor that fits; off, the picture fills the screen. Either way only the
  lines the game uses are shown (320x200 out of the 256 PAL lines), so there
  is no black band at the bottom;
- **Amiga model**: *A4000* (the default, smoother) or *A500* (original), as
  in the F1 menu.

### The translation on a real or emulated Amiga

In Settings, under the language, **Create Italian Amiga disks (ADF +
WHDLoad)** builds from the chosen disk, in the `Amiga ITA` folder next to the
program:

- `RockStar_ITA_1MB.adf`: the Italian floppy, bootable on any Amiga with
  1 MB (A500 512K+512K, A500/A600 with 1 MB chip, A1200, 68040). Before
  starting it asks which cheats to enable;
- `RockStarAteMyHamster_v1.0_It.lha`: the WHDLoad install (WHDLoad 17+, F10
  to quit; cheats are chosen in WHDLoad's start window).

Without a window: `RockStarAteMyHamsterRecomp.exe --esporta-amiga <disk> [folder]`.

## Building

You need clang (mingw target), CMake with Ninja, Python 3 with `unicorn`,
and the SDL2 development package (in `../sdl/SDL2-2.32.2`, or
`-DROCKSTAR_SDL2_DIR`).

```
python traduzione/base_canonica.py "Rock Star Ate My Hamster (Europe).ipf" ../rockstar_base.bin
python game/prepara_immagine.py
cmake -S . -B build/cmake -G Ninja -DCMAKE_C_COMPILER=clang -DCMAKE_CXX_COMPILER=clang++
cmake --build build/cmake
```

The game base (`rockstar_base.bin`, from your disk) lives outside the
repository, in the folder that contains it (or in `RSAMH_DATI`): see
`traduzione/percorsi.py` and `traduzione/LEGGIMI.txt`. `prepara_immagine.py`
starts from there and from the translation (`traduzione/`) and produces:

- `build/rockstar_chipram.bin`, the Italian chip RAM image: the recompiled C
  is generated from it;
- `build/rockstar_chipram_en.bin`, the English one: same code, data from the
  disk;
- `build/lingue_dati.h`, the differences between the base and the two images
  (only our own data: translation, patches, added code) and the CRCs. The
  executable applies them to the base it extracts from the user's disk
  (`amiga_disco.c`, `amiga_lingue.c`);
- `build/amiga_kit.h`, what the Amiga builds need (`amiga_esporta.c`): the
  image patch, the Amiga executable without the game's compressed data
  (loader, our own S404 decruncher, extended text table, gender agreement,
  cheats), the WHDLoad files and the CRCs the result must match. The program
  recompresses the image with the same algorithm as `s404_compress.py`.

The Amiga builds can also be made with the Python pipeline:
`traduzione/ricostruisci_tutto.ps1`.

## Testing without a window

```
tools/prova_quadri.ps1 -quadri 3500 -exe build/cmake/RockStarAteMyHamsterRecomp.exe
```

Runs 3500 frames (70 seconds of play), saves `build/quadro.png` and the final
memory. `AMIGA_INGRESSI="f:300,k44:500"` simulates fire and key presses.

With `--debug` (or `AMIGA_DEBUG=1`) a console opens too (otherwise you only
see the launcher and the game) and the debug tools are on: F11 opens the
window (variables, messages, writes, calls), Shift+F11 writes
`debug_dump.txt` and `debug_memoria.bin`, and the game's messages go to
`messaggi.log`. Without it the program writes nothing of its own.

## Controls

As on the Amiga, you choose in three ways: mouse (up and down to point, left
button to choose), joystick in port 2 (up and down, fire), keyboard (up and
down arrows, Space). The same input skips the intro and advances the speech
bubbles. The first click in the window captures the pointer (without choosing
anything); the middle button or F12 releases it.

Keys and gamepad are bound in the launcher (Mouse & Keyboard → Keys and
gamepad...). Defaults: arrows and Ctrl = joystick (up/down in menus, fire
chooses); holding Space stops the text scrolling; Return, Backspace and Esc
are for typing names. Gamepad: d-pad = joystick, A = fire, RB/B = left/right
click, X = Space, Y = Return, LB = Backspace, Back = Esc; the left stick moves
the pointer. Unbound keys go to the Amiga keyboard.

**F1** (or the gamepad's Start) opens the in-game menu and pauses the game:
save and load in four slots (from the game's main menu, where the game itself
saves too), cheats, screen model, fullscreen, integer scaling, pixel shape,
volume, Amiga model, quit. **Amiga: A4000** (the default) runs the CPU like a
25 MHz 68040: windows, texts and animations are drawn faster, as on fast
Amigas, while the game's pace and the music stay at 50 Hz; **A500** is the
original 68000. The game's own save (SAVE/LOAD in the main menu), which on
the Amiga only stayed in memory, is now kept in a file
(`salvataggi/partita.sav`) and reloaded the next time.

## Licences

The code derived from `segagenesisrecomp` (`amigarecomp/recompiler/src`,
`amigarecomp/runner/include`) and the `m68k-recomp-core` submodule are under
PolyForm Noncommercial 1.0.0 (see `amigarecomp/LICENSE-recompiler`);
`recomp-ui` is MIT. Non-commercial use. The original game is © Codemasters.
