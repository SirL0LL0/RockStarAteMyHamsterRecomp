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
| `traduzione/` | la traduzione: testi, patch, codice 68000 aggiunto, editor, versioni Amiga (ADF, WHDLoad) |
| `external/` | sottomoduli del toolkit |
| `tools/` | script di build e di prova |

## Il gioco

*Rock Star Ate My Hamster* (Codemasters, 1989; anche per Atari ST, C64,
Amstrad CPC e ZX Spectrum). Ideato e programmato da Colin Jones, grafica di
Brian Hartley e Chris Graham, musica di Allister Brimble, Colin Jones, Gavin
Raeburn e Paul Hiley. Il titolo prende in giro il celebre titolo di giornale
del 1986 su Freddie Starr; nella confezione c'era *The Stun*, un finto
tabloid (oroscopi, fumetti, pettegolezzi sulle star parodiate dal gioco).

Sei il manager di una band: parti dalle 50.000 sterline lasciate dalla zia
Mabel, scegli le rock star alle audizioni, le fai provare, le porti in tour,
incidi e pubblichi singoli e album. Si vince conquistando **4 dischi
d'argento** entro un anno; si perde andando in rovina o restando senza star.

Il menu principale: **PROVE**, **CONCERTO** (tour: locali, prezzo dei
biglietti, numero di serate; e' la fonte principale di guadagno),
**STAMPA** (trovate pubblicitarie: alzano la fama, ma possono finire male),
**REGALI** (per tenere contente le star), **INCIDI** / **LANCIA DISCO**
(studio, titoli, singoli, album, video), **SALVATAGGI** (salva o carica la
partita), **ESCI**. Strada facendo arrivano concerti di beneficenza, sponsor,
case discografiche, pirati e il fisco.

Consigli dalla *Cecil Pitt Guide to Rock Management* del manuale:

- piu' star hai, piu' sei popolare; quelle che costano poco di solito sono
  meno brave, meno amate e piu' permalose (ma non sempre);
- fai provare la band prima di cercare un contratto: le case discografiche
  vogliono gruppi che hanno gia' dei fan;
- scegli bene locali e prezzi: un gruppo alle prime armi non riempie uno
  stadio a 20 sterline a biglietto;
- non spremere la band: falle riposare e falle regali, o le star fanno
  storie, pretendono il controllo artistico o se ne vanno;
- valuta le offerte dei discografici ma non fare troppo il difficile: quando
  la popolarita' cala, le offerte spariscono;
- usa lo studio migliore che ti puoi permettere; i singoli di successo fanno
  vendere l'album; fai un video quando puoi, scegliendo con cura regista,
  luogo e contenuto.

**Trucco originale**: durante la partita scrivi `COLBOPS`, poi F7 aggiunge
soldi (in questa versione un milione di sterline, le guide dicono 100.000),
F8 fa suonare la band al massimo, F9 porta il pubblico al massimo. Si attiva
anche dal menu Mods del launcher o dal menu in gioco.

**Perche' le star se ne vanno.** Ogni star ha una contentezza nascosta. Prima
di ogni serata di un tour il gioco guarda la piu' scontenta: se e' a 9 o piu'
la serata va liscia e tutte perdono un punto; sotto 9 partono le richieste
(go-go girls, poi il ricatto della Porsche: se rifiuti, licenziata) e, con 2
dischi d'argento (sotto 4) o 3 (sotto 9), la star se ne va senza chiedere
niente. Ogni partenza dimezza la qualita' della band; senza star e' game over.
I regali alzano tutte (auto +12, gioielli +11, vestiti +10, bevute +9, cibo +8).

**Biglietti.** I biglietti venduti sono il minore fra la capienza e
10 x fattore del prezzo x qualita' della band (1-255), con fattori 9, 6, 4, 2,
1 per 2, 5, 10, 15, 20 sterline: a 15 e 20 lo stadio non si riempie mai,
nemmeno con la band al massimo (5.100 e 2.550 biglietti). Allo stadio il
prezzo migliore e' 10 sterline.

Fra le mod (launcher e menu F1), oltre ai trucchi: **Star sempre contente**
(nessuno se ne va, niente ricatti) e **Stadio pieno a ogni prezzo** (fattori
9, 8, 6, 5, 4: una band al top riempie lo stadio anche a 20 sterline).

Fonti: il manuale originale, il manuale su
[Games Database](https://www.gamesdatabase.org/Media/SYSTEM/Commodore_Amiga//Manual/formated/Rock_Star_Ate_my_Hamster_-_1989_-_Codemasters.htm),
[The Codemasters Archive](https://thecodemastersarchive.co.uk/games/rock-star-ate-my-hamster/),
[Lemon Amiga](https://www.lemonamiga.com/doc/rock-star-ate-my-hamster/1372).

## Giocare

Il programma vuole uno dei due dischi supportati, riconosciuti dal CRC32 del
file (il nome non conta):

| Disco | CRC32 |
|---|---|
| `Rock Star Ate My Hamster (Europe).ipf` (il disco originale) | `53EC7260` |
| `Rock Star Ate My Hamster (1989)(Codemasters).adf` | `BB9DD80B` |

Lo si sceglie nel launcher (Browse For DISK), e nel menu Localization si
sceglie la lingua: **Italiano** (la traduzione) o **English** (il testo
originale); nella stessa lingua sono anche i testi del launcher. Quando il
disco e' riconosciuto compare la copertina del gioco. Il resto lo fa il
programma: legge il disco (anche l'IPF, tracce MFM comprese), decomprime il
gioco, lo porta sempre alla stessa versione (CRC verificato), applica la
lingua e parte.

Nelle impostazioni del launcher ci sono anche:

- **Screen model**: *Sharp* (pixel netti; con *Linear filtering*
  ammorbiditi), *Commodore 1084S* (il monitor dell'Amiga: fascio gaussiano,
  maschera a fessure, alone, leggera curvatura), *CRT Easymode* (CRT piatto
  alla maniera di crt-easymode: Lanczos, fascio gaussiano, maschera leggera),
  *Scanlines*. In gioco Shift+F12 passa al modello successivo;
- **Aspect ratio**: *PAL (4:3)* (il predefinito: i pixel larghi come su un
  monitor PAL) o *Square pixels*;
- **Integer scaling** (scala intera, attiva di partenza): pixel perfetti, il
  fattore intero piu' grande che entra; spenta, l'immagine riempie lo schermo.
  In tutti e due i casi si mostrano solo le righe che il gioco usa (320x200
  delle 256 PAL), quindi niente fascia nera in basso;
- **Amiga model**: *A4000* (il predefinito, piu' fluido) o *A500* (originale),
  come nel menu F1.

### La traduzione su Amiga (vero o emulato)

In Settings, sotto la lingua, **Create Italian Amiga disks (ADF + WHDLoad)**
crea dal disco scelto, nella cartella `Amiga ITA` accanto al programma:

- `RockStar_ITA_1MB.adf`: il floppy in italiano, avviabile, per ogni Amiga
  con 1 MB (A500 512K+512K, A500/A600 con 1 MB di chip, A1200, 68040). Prima
  di partire chiede quali trucchi attivare;
- `RockStarAteMyHamster_v1.0_It.lha`: l'installazione WHDLoad (WHDLoad 17+,
  F10 per uscire; i trucchi si scelgono nella finestra iniziale di WHDLoad).

Senza finestra: `RockStarAteMyHamsterRecomp.exe --esporta-amiga <disco> [cartella]`.

## Compilare

Servono clang (target mingw), CMake con Ninja, Python 3 con `unicorn`, e il
pacchetto di sviluppo SDL2 (in `../sdl/SDL2-2.32.2`, o `-DROCKSTAR_SDL2_DIR`).

```
python traduzione/base_canonica.py "Rock Star Ate My Hamster (Europe).ipf" ../rockstar_base.bin
python game/prepara_immagine.py
cmake -S . -B build/cmake -G Ninja -DCMAKE_C_COMPILER=clang -DCMAKE_CXX_COMPILER=clang++
cmake --build build/cmake
```

La base del gioco (`rockstar_base.bin`, dal tuo disco) sta fuori dal
repository, nella cartella che lo contiene (o in `RSAMH_DATI`): vedi
`traduzione/percorsi.py` e `traduzione/LEGGIMI.txt`. `prepara_immagine.py`
parte da lì e dalla traduzione (`traduzione/`) e produce:

- `build/rockstar_chipram.bin`, l'immagine italiana della chip RAM: da qui
  nasce il C ricompilato;
- `build/rockstar_chipram_en.bin`, l'inglese: stesso codice, dati del disco;
- `build/lingue_dati.h`, le differenze fra la base e le due immagini (solo
  dati nostri: traduzione, patch, codice aggiunto) e i CRC. L'eseguibile le
  applica alla base che ricava dal disco dell'utente (`amiga_disco.c`,
  `amiga_lingue.c`);
- `build/amiga_kit.h`, quello che serve per le versioni Amiga (`amiga_esporta.c`):
  la patch dell'immagine, l'eseguibile Amiga senza i dati compressi del gioco
  (caricatore, decompressore S404 nostro, tabella estesa, accordo, trucchi),
  i file di WHDLoad e i CRC che il risultato deve avere. Il programma
  ricomprime l'immagine con lo stesso algoritmo di `s404_compress.py`.

Per le versioni Amiga anche dalla pipeline Python: `traduzione/ricostruisci_tutto.ps1`.

## Provare senza finestra

```
tools/prova_quadri.ps1 -quadri 3500 -exe build/cmake/RockStarAteMyHamsterRecomp.exe
```

Gira 3500 quadri (70 secondi di gioco), salva `build/quadro.png` e la memoria
finale. `AMIGA_INGRESSI="f:300,k44:500"` simula fuoco e tasti.

Con `--debug` (o `AMIGA_DEBUG=1`) si accendono gli strumenti di debug: F11
apre la finestra (variabili, messaggi, scritture, chiamate), Shift+F11 scrive
`debug_dump.txt` e `debug_memoria.bin`, e i messaggi del gioco finiscono in
`messaggi.log`. Senza, il programma non scrive nulla di suo.

## Comandi

Come sull'Amiga, si sceglie in tre modi: mouse (su e giu' per indicare,
pulsante sinistro per scegliere), joystick in porta 2 (su e giu', fuoco),
tastiera (frecce su e giu', Spazio). Lo stesso salta l'introduzione e fa
avanzare i fumetti. Il primo clic nella finestra cattura il puntatore (senza scegliere
nulla); il pulsante centrale o F12 lo liberano.

Tasti e joypad si associano nel launcher (Mouse & Keyboard → Keys and
gamepad...). Predefiniti: frecce e Ctrl = joystick (su/giù nei menu, fuoco
sceglie); Spazio tenuto premuto ferma lo scorrere dei testi; Invio, Backspace
ed Esc servono a scrivere i nomi. Joypad: croce = joystick, A = fuoco,
RB/B = clic sinistro/destro, X = Spazio, Y = Invio, LB = Backspace,
Back = Esc; lo stick sinistro muove il puntatore. I tasti non associati vanno
alla tastiera dell'Amiga.

**F1** (o Start del joypad) apre il menu in gioco e ferma la partita:
salvataggio e caricamento in quattro slot (dal menu principale del gioco,
dove salva anche il gioco stesso), trucchi, modello di schermo,
schermo intero, volume, Amiga, uscita. **Amiga: A4000** (il predefinito) fa
girare la CPU come un 68040 a 25 MHz: finestre, testi e animazioni si
disegnano piu' in fretta, come sugli Amiga veloci, mentre il ritmo del gioco e
la musica restano quelli dei 50 Hz; **A500** e' il 68000 originale. Anche il salvataggio del gioco (opzione
SALVATAGGI del menu principale), che sull'Amiga restava solo in memoria, ora resta su
file (`salvataggi/partita.sav`) e si ricarica le volte successive.

## Licenze

Il codice derivato da `segagenesisrecomp` (`amigarecomp/recompiler/src`,
`amigarecomp/runner/include`) e i sottomoduli `m68k-recomp-core` sono sotto
PolyForm Noncommercial 1.0.0 (vedi `amigarecomp/LICENSE-recompiler`);
`recomp-ui` è MIT. Uso non commerciale. Il gioco originale è © Codemasters.
