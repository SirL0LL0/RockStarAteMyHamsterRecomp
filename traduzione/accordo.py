# -*- coding: utf-8 -*-
"""
accordo.py - genere e numero nei messaggi italiani.

L'inglese non ne ha bisogno: dice <BAND> e il verbo resta uguale. In
italiano "<BAND> E' PERFETTO" va bene per un cantante solo, non per una
cantante ne' per un gruppo. Qui c'e' tutto quello che serve per farlo
decidere al gioco, a runtime.

IL MARCATORE (nel testo della tabella, mai visibile a video)

    {A|B}         singolare | plurale
    {A|B|C}       maschile | femminile | plurale
    {A|B|C|D}     masch. sing. | femm. sing. | masch. plur. | femm. plur.
    {=F} {=M} {=P} {=FP}   da qui in poi il soggetto e' questo
    {=}           torna al soggetto del messaggio

    "<BAND>{E'|SONO} PERFETT{O|A|I|E}"
    "CREPA{|TE} PURE"            (alternativa vuota: niente)
    "{=F}LA GIRAFFA "            (un item di gruppo che dice il suo genere)

IL SOGGETTO DEL MESSAGGIO

    - se il messaggio contiene il nome di una star (token RAM32 72-75, le
      ancore che il gioco riscrive con 72 + posto nella band), e' quella
      star, al singolare;
    - i messaggi in SOGGETTI hanno il soggetto fisso: 'M', 'F', 'P', 'FP',
      oppure 'ultima' per quelli che non nominano nessuno ma parlano alla
      star del messaggio prima (210, 212: "crepa pure, bello", "sei
      licenziato"), che usano l'ultima star incontrata;
    - altrimenti e' la band: un membro solo = il suo genere; piu' membri =
      plurale, femminile solo se sono tutte donne.

    Il genere delle 52 star e' in rockstar_generi.json (si modifica a mano).

DOVE GIRA

    Tre agganci nel codice del gioco (AGGANCI):
      $D63A  (inizio del compositore)  jsr ingresso   ricorda il numero del messaggio
      $D586  (prima di mostrare)       jsr filtro;nop risolve i marcatori nel buffer
      $D6D4  (espansione di un nome)   jsr nome;nop   mette $1E/$1F attorno al nome

    I nomi (titoli di canzoni e album, band, star) si leggono sempre al
    maschile singolare: dentro $1E..$1F il soggetto e' m.sing. Cosi' un pezzo
    con i marcatori che finisce anche in un titolo non lo fa cambiare con la
    band. Anche i testi composti fuori da un messaggio (classifiche) sono al
    maschile singolare.
    $D586 e' anche la strada di classifiche e manifesti, quindi il filtro vede
    ogni testo composto. Il filtro lavora sul buffer finito ($122C8, chiuso da
    $FF): i marcatori possono stare in qualunque stringa o item di gruppo.
    Rifa' anche la regola del gioco che mangia lo spazio prima di ! , . ?
    (un'alternativa vuota puo' lasciare uno spazio davanti alla punteggiatura).

    Nella versione con loader il codice viaggia nel pacchetto in RAM, come la
    tabella estesa, e il post-codice scrive gli agganci. Se la RAM non c'e'
    (piano B, tabella compatta) gli agganci non vengono scritti: per questo la
    tabella compatta non deve contenere marcatori.
"""

import json
import os
import struct

from asm68k import Asm

# indirizzi del gioco (immagine a $8100)
MESSAGGI = 0xDD70        # inizio dei messaggi (lea $dd70(pc),a3 in $D638)
TROVA_MSG = 0xD5CA       # salta d4 terminatori
BUFFER = 0x122C8         # testo composto, chiuso da $FF
CONTATORE = 0x1285C
STATO = 0x128FC          # stato dei 4 posti: bit 7 = andato via
POSTI = 0x129C6          # indice della star (0-51) in ciascun posto
CANDIDATA = 0x96FC       # la star mostrata in sala audizioni (il #21 la nomina
                         # col token fisso 75, ma il posto 3 a quel punto e'
                         # gia' stato azzerato: $094CE)
FINESTRA = 0xD7E4        # la bsr che $D586 fa per prima
FLAG_D586 = 0x1286A      # la lea che $D586 fa dopo

SOTTOCOMPOSITORE = 0x8842   # espande un nome (canzone, album, band, star)
DOPO_NOME = 0xD71C           # dove $D638 riprende dopo un nome

# i punti del gioco che diventano chiamate alla routine:
# (indirizzo, entrata, byte da sostituire, byte originali da verificare)
AGGANCI = [
    (0xD63A, 'ingresso', 8, bytes.fromhex('41FA522010BC0000')),  # lea $1285c(pc),a0; move.b #0,(a0)
    (0xD586, 'filtro', 8, bytes.fromhex('6100025C41FA')),    # bsr.w $d7e4; lea $1286a(pc),a0
    (0xD6D4, 'nome', 8, bytes.fromhex('6100B16C60000042')),  # bsr.w $8842; bra.w $d71c
]
INIZIO_NOME, FINE_NOME = 0x1E, 0x1F   # attorno ai nomi espansi, nel buffer

# soggetto fisso per messaggio (vedi sopra). Servono dove un pezzo con i
# marcatori e' condiviso da messaggi che parlano a soggetti diversi: CREPA
# PURE e' detto all'ente benefico (plurale), al discografico e a Clive
# (maschile), alla star capricciosa (l'ultima star).
SOGGETTI = {9: 'P', 10: 'P', 25: 'M', 114: 'M', 201: 'M',
            210: 'ultima', 212: 'ultima', 21: 'candidata',
            23: 'F', 39: 'M', 45: 'M', 46: 'P'}
_MODI = {'M': 0, 'F': 1, 'P': 2, 'MP': 2, 'FP': 3, 'ultima': 0xFF, 'candidata': 0xFE}
N_STAR = 52

# genere di default: le parodie di artiste
_FEMMINE = {1, 4, 9, 16, 19, 20, 31, 40, 51}

FILE_GENERI = 'rockstar_generi.json'


def generi_default(nomi=None):
    out = []
    for i in range(N_STAR):
        out.append({'record': i, 'nome': (nomi[i] if nomi else ''),
                     'genere': 'F' if i in _FEMMINE else 'M'})
    return out


def carica_generi(cartella='.'):
    p = os.path.join(cartella, FILE_GENERI)
    if os.path.isfile(p):
        d = json.load(open(p, encoding='utf-8'))
        g = [0] * N_STAR
        for r in d:
            g[int(r['record'])] = 1 if str(r['genere']).upper().startswith('F') else 0
        return g
    return [1 if i in _FEMMINE else 0 for i in range(N_STAR)]


# ------------------------------------------------------------ risolutore
#
# Stesse regole della routine 68000: serve all'editor per l'anteprima e ai
# controlli. acc: 0 = m.sing, 1 = f.sing, 2 = m.plur, 3 = f.plur.

SCELTA = [[0, 0, 0, 0],     # 1 alternativa
          [0, 0, 1, 1],     # sing | plur
          [0, 1, 2, 2],     # m | f | plur
          [0, 1, 2, 3]]     # ms | fs | mp | fp

NOMI_ACC = ('m', 'f', 'pl', 'f.pl')


def risolvi(s, acc):
    out = []
    base = acc
    i = 0
    n = len(s)

    def metti(c):
        if c in '!,.?' and out and out[-1] == ' ':
            out[-1] = c
        else:
            out.append(c)

    salvato = acc
    while i < n:
        c = s[i]; i += 1
        if c == chr(INIZIO_NOME):
            salvato, acc = acc, 0; continue
        if c == chr(FINE_NOME):
            acc = salvato; continue
        if c != '{':
            metti(c); continue
        j = s.find('}', i)
        if j < 0:
            break                       # come il gioco: si ferma
        dentro = s[i:j]; i = j + 1
        if dentro.startswith('='):
            cod = dentro[1:].upper()
            if not cod:
                acc = base
            else:
                acc = (1 if 'F' in cod else 0) | (2 if 'P' in cod else 0)
            continue
        alt = dentro.split('|')
        k = SCELTA[min(len(alt), 4) - 1][acc]
        for c2 in (alt[k] if k < len(alt) else ''):
            metti(c2)
    return ''.join(out)


def ha_marcatori(s):
    return '{' in s


def varianti(s):
    """Le forme diverse che il testo puo' prendere: [(acc, testo)]."""
    visti = {}
    for acc in range(4):
        r = risolvi(s, acc)
        visti.setdefault(r, acc)
    return [(a, t) for t, a in sorted(visti.items(), key=lambda x: x[1])]


def errori_marcatori(s):
    """Graffe sbilanciate o annidate, alternative in eccesso."""
    err = []
    prof = 0
    k = 0
    for c in s:
        if c == '{':
            prof += 1
            if prof > 1: err.append("graffe una dentro l'altra")
            k = 0
        elif c == '}':
            prof -= 1
            if prof < 0: err.append("} senza {"); prof = 0
        elif c == '|' and prof:
            k += 1
            if k > 3: err.append("piu' di 4 alternative")
        elif c == '|' and not prof:
            err.append("| fuori dalle graffe")
    if prof > 0:
        err.append("{ senza }")
    return sorted(set(err))


# ------------------------------------------------------------ codice 68000

# scritte grandi del manifesto del concerto: (finestra, larghezza per andare a
# capo, larghezza per centrare, larghezza della finestra). Ogni carattere
# grande occupa due colonne e la finestra parte da una colonna fissa, quindi
# una riga di L caratteri e' centrata sullo schermo (40 colonne) se ha davanti
# (W - L) / 2 spazi, con W = (40 - 2*colonna) / 2.
#
# Come stampa il gioco ($D48E), per ogni riga: guarda S caratteri (S =
# larghezza della finestra), va a capo dopo l'ultimo spazio che vi trova (o
# alla fine del testo) e stampa fin li' compreso; ma se la riga comincia con
# uno spazio lo salta e stampa comunque lo stesso numero di caratteri, cioe'
# uno in piu' preso dalla riga dopo. Percio' ogni riga diventa un blocco di
# lunghezza fissa che lo spazio in fondo fa spezzare sempre allo stesso punto:
#   senza rientro    T + spazi fino a S caratteri
#   rientro I >= 1   (I+1) spazi + T + spazi fino a S+1 caratteri
#                    (il primo spazio salta, l'ultimo e' quello in piu')
# Serve I + 1 + L <= S - 2, quindi I = min((W-L)/2, S-2-L). L'ultima riga
# finisce col testo, senza spazi dietro.
CENTRATE = [(0x31, 16, 14, 16),     # sponsor         colonne 6-22
            (0x32, 14, 15, 16),     # nome della band colonne 5-21 (patch_finestre)
            (0x33, 17, 13, 17)]     # slogan          colonne 7-24


def centra(a):
    """Routine 'centra', chiamata alla fine del filtro: nelle finestre di
    CENTRATE riscrive il buffer ($122C8, chiuso da $FF) riga per riga, come le
    spezza il gioco, senza gli spazi iniziali e con quelli che la centrano.
    La finestra e' il d6 salvato dal filtro (pila: 28(a7) dentro la bsr)."""
    a.eti('centra')
    a.b(b'\x20\x2F\x00\x1C')               # move.l 28(a7),d0   finestra
    a.saltoW(b'\x45\xFA', 'c_tab')         # lea c_tab(pc),a2
    a.eti('c_cerca')
    a.b(b'\x12\x1A')                       # move.b (a2)+,d1
    a.saltoW(b'\x67\x00', 'c_fine')        # beq.w c_fine      non e' una delle nostre
    a.b(b'\x74\x00\x14\x1A')               # moveq #0,d2 ; move.b (a2)+,d2   a capo
    a.b(b'\x7C\x00\x1C\x1A')               # moveq #0,d6 ; move.b (a2)+,d6   centro
    a.b(b'\x7E\x00\x1E\x1A')               # moveq #0,d7 ; move.b (a2)+,d7   finestra
    a.b(b'\xB0\x01')                       # cmp.b d1,d0
    a.salto(b'\x66', 'c_cerca')            # bne.b c_cerca
    a.b(b'\x41\xF9').dato32(BUFFER)        # lea BUFFER,a0
    a.saltoW(b'\x43\xFA', 'c_tmp')         # lea c_tmp(pc),a1
    a.eti('c_copia')
    a.b(b'\x12\x18\x12\xC1')               # move.b (a0)+,d1 ; move.b d1,(a1)+
    a.b(b'\x0C\x01\x00\xFF')               # cmp.b #$ff,d1
    a.salto(b'\x66', 'c_copia')            # bne.b c_copia
    a.saltoW(b'\x41\xFA', 'c_tmp')         # lea c_tmp(pc),a0   sorgente
    a.b(b'\x43\xF9').dato32(BUFFER)        # lea BUFFER,a1      destinazione
    a.eti('c_riga')
    a.b(b'\x0C\x10\x00\x20')               # cmp.b #' ',(a0)
    a.salto(b'\x66', 'c_m')                # bne.b c_m
    a.b(b'\x52\x88')                       # addq.l #1,a0
    a.salto(b'\x60', 'c_riga')             # bra.b c_riga
    a.eti('c_m')
    a.b(b'\x0C\x10\x00\xFF')               # cmp.b #$ff,(a0)
    a.saltoW(b'\x67\x00', 'c_end')         # beq.w c_end
    a.b(b'\x26\x48\x76\x00\x28\x48')       # movea.l a0,a3 ; moveq #0,d3 ; movea.l a0,a4
    a.eti('c_parola')
    a.b(b'\x78\x00\x2A\x4C')               # moveq #0,d4 ; movea.l a4,a5
    a.eti('c_pl')
    a.b(b'\x12\x15')                       # move.b (a5),d1
    a.b(b'\x0C\x01\x00\x20')               # cmp.b #' ',d1
    a.salto(b'\x67', 'c_pf')               # beq.b c_pf
    a.b(b'\x0C\x01\x00\xFF')               # cmp.b #$ff,d1
    a.salto(b'\x67', 'c_pf')               # beq.b c_pf
    a.b(b'\x52\x44\x52\x8D')               # addq.w #1,d4 ; addq.l #1,a5
    a.salto(b'\x60', 'c_pl')               # bra.b c_pl
    a.eti('c_pf')
    a.b(b'\x4A\x44')                       # tst.w d4         solo spazi: la riga e' finita
    a.salto(b'\x67', 'c_scrivi')           # beq.b c_scrivi
    a.b(b'\x3A\x03')                       # move.w d3,d5
    a.salto(b'\x67', 'c_primo')            # beq.b c_primo
    a.b(b'\x52\x45')                       # addq.w #1,d5
    a.eti('c_primo')
    a.b(b'\xDA\x44')                       # add.w d4,d5      lunghezza con questa parola
    a.b(b'\x4A\x43')                       # tst.w d3
    a.salto(b'\x67', 'c_prende')           # beq.b c_prende   la prima parola entra sempre
    a.b(b'\xBA\x42')                       # cmp.w d2,d5
    a.salto(b'\x62', 'c_scrivi')           # bhi.b c_scrivi   non entra: a capo
    a.eti('c_prende')
    a.b(b'\x36\x05\x28\x4D')               # move.w d5,d3 ; movea.l a5,a4
    a.b(b'\x0C\x14\x00\xFF')               # cmp.b #$ff,(a4)
    a.salto(b'\x67', 'c_scrivi')           # beq.b c_scrivi
    a.b(b'\x52\x8C')                       # addq.l #1,a4
    a.salto(b'\x60', 'c_parola')           # bra.b c_parola
    # riga di d3 caratteri da a3: rientro I in d5, lunghezza del blocco in d0
    a.eti('c_scrivi')
    a.b(b'\x3A\x06\x9A\x43')               # move.w d6,d5 ; sub.w d3,d5     W - L
    a.salto(b'\x6F', 'c_i0')               # ble.b c_i0
    a.b(b'\xE2\x4D')                       # lsr.w #1,d5
    a.b(b'\x30\x07\x55\x40\x90\x43')       # move.w d7,d0 ; subq.w #2,d0 ; sub.w d3,d0   S-2-L
    a.b(b'\xBA\x40')                       # cmp.w d0,d5
    a.salto(b'\x6F', 'c_iok')              # ble.b c_iok
    a.b(b'\x3A\x00')                       # move.w d0,d5
    a.eti('c_iok')
    a.b(b'\x4A\x45')                       # tst.w d5
    a.salto(b'\x6E', 'c_ind')              # bgt.b c_ind
    a.eti('c_i0')
    a.b(b'\x30\x07')                       # move.w d7,d0     blocco di S
    a.salto(b'\x60', 'c_testo')            # bra.b c_testo
    a.eti('c_ind')
    a.b(b'\x30\x07\x52\x40')               # move.w d7,d0 ; addq.w #1,d0    blocco di S+1
    a.b(b'\x90\x45\x53\x40')               # sub.w d5,d0 ; subq.w #1,d0     meno I+1 spazi
    a.eti('c_pad')
    a.b(b'\x12\xFC\x00\x20')               # move.b #' ',(a1)+
    a.saltoW(b'\x51\xCD', 'c_pad')         # dbra d5,c_pad    I+1 volte
    a.eti('c_testo')
    a.b(b'\x90\x43')                       # sub.w d3,d0      spazi dietro
    a.b(b'\x3A\x03\x53\x45')               # move.w d3,d5 ; subq.w #1,d5
    a.eti('c_cp')
    a.b(b'\x12\xDB')                       # move.b (a3)+,(a1)+
    a.saltoW(b'\x51\xCD', 'c_cp')          # dbra d5,c_cp
    a.b(b'\x20\x4B\x24\x4B')               # movea.l a3,a0 ; movea.l a3,a2
    a.eti('c_pk')
    a.b(b'\x0C\x1A\x00\x20')               # cmp.b #' ',(a2)+
    a.salto(b'\x67', 'c_pk')               # beq.b c_pk
    a.b(b'\x0C\x2A\x00\xFF\xFF\xFF')       # cmp.b #$ff,-1(a2)
    a.saltoW(b'\x67\x00', 'c_riga')        # beq.w c_riga     ultima riga: niente spazi dietro
    a.salto(b'\x60', 'c_trp')              # bra.b c_trp
    a.eti('c_tr')
    a.b(b'\x12\xFC\x00\x20')               # move.b #' ',(a1)+
    a.eti('c_trp')
    a.b(b'\x53\x40')                       # subq.w #1,d0
    a.salto(b'\x6C', 'c_tr')               # bge.b c_tr
    a.saltoW(b'\x60\x00', 'c_riga')        # bra.w c_riga
    a.eti('c_end')
    a.b(b'\x12\xBC\x00\xFF')               # move.b #$ff,(a1)
    a.eti('c_fine')
    a.b(b'\x4E\x75')                       # rts
    a.eti('c_tab')
    for f, c, w, s in CENTRATE:
        a.b(bytes([f, c, w, s]))
    a.b(b'\x00')
    while a.pos() % 2: a.b(b'\x00')
    a.eti('c_tmp')
    a.b(bytes(264))


def codice(generi, soggetti=None):
    """Restituisce (byte, ingresso, filtro, assoluti).

    ingresso, filtro: offset dei due punti d'ingresso nel blocco.
    assoluti: offset dei longword che contengono indirizzi del gioco (per
    la versione rilocabile, dove vanno rilocati).
    """
    if soggetti is None:
        soggetti = SOGGETTI
    a = Asm()
    assoluti = []

    def ass(v):
        assoluti.append(a.pos())
        a.dato32(v)

    # ---------------- ingresso: al posto di "lea $1285c(pc),a0; move.b #0,(a0)"
    # Il "move.l d6,-(a7)" che le precede resta nel compositore, accanto al
    # "move.l (a7)+,d6" che lo toglie: push e pop nella stessa funzione, come
    # nell'originale. (Prima l'aggancio stava a $D638 e spingeva d6 lui,
    # rigirando l'indirizzo di ritorno: giusto sul 68000, ma un ricompilatore
    # statico vede nel compositore un pop senza push e lo tratta come un
    # ritorno al chiamante del chiamante.)
    a.eti('ingresso')
    a.saltoW(b'\x41\xFA', 'msgnum')        # lea msgnum(pc),a0
    a.b(b'\x30\x84')                       # move.w d4,(a0)
    a.b(b'\x41\xF9'); ass(CONTATORE)       # lea $1285c,a0
    a.b(b'\x10\xBC\x00\x00')               # move.b #0,(a0)
    a.b(b'\x4E\x75')                       # rts

    # ---------------- filtro: al posto di "bsr.w $d7e4; lea $1286a(pc),a0"
    a.eti('filtro')
    a.b(b'\x48\xE7\xFF\xFE')               # movem.l d0-d7/a0-a6,-(a7)
    a.saltoW(b'\x4B\xFA', 'msgnum')        # lea msgnum(pc),a5
    a.b(b'\x38\x15')                       # move.w (a5),d4
    a.b(b'\x3A\xBC\xFF\xFF')               # move.w #$ffff,(a5)
    a.b(b'\x7E\x00')                       # moveq #0,d7
    a.b(b'\xB8\x7C\xFF\xFF')               # cmp.w #$ffff,d4   fuori da un messaggio:
    a.saltoW(b'\x67\x00', 'filtra')        # beq.w filtra       maschile singolare
    a.saltoW(b'\x41\xFA', 'soggetti')      # lea soggetti(pc),a0
    a.eti('ov')
    a.b(b'\x30\x18')                       # move.w (a0)+,d0     messaggio
    a.b(b'\x32\x18')                       # move.w (a0)+,d1     modo
    a.b(b'\xB0\x7C\xFF\xFF')               # cmp.w #$ffff,d0
    a.salto(b'\x67', 'auto')               # beq.b auto
    a.b(b'\xB8\x40')                       # cmp.w d0,d4
    a.salto(b'\x66', 'ov')                 # bne.b ov
    a.b(b'\x7E\x00')                       # moveq #0,d7
    a.b(b'\x1E\x01')                       # move.b d1,d7
    a.b(b'\x0C\x01\x00\xFE')               # cmp.b #$fe,d1
    a.salto(b'\x66', 'non_cand')           # bne.b non_cand
    a.b(b'\x74\x00')                       # moveq #0,d2
    a.b(b'\x14\x39'); ass(CANDIDATA)      # move.b $96fc,d2
    a.saltoW(b'\x60\x00', 'genere')        # bra.w genere
    a.eti('non_cand')
    a.b(b'\x0C\x01\x00\xFF')               # cmp.b #$ff,d1
    a.saltoW(b'\x66\x00', 'filtra')        # bne.w filtra   soggetto fisso
    a.saltoW(b'\x41\xFA', 'ultima')        # lea ultima(pc),a0
    a.b(b'\x74\x00')                       # moveq #0,d2
    a.b(b'\x14\x10')                       # move.b (a0),d2
    a.b(b'\x0C\x02\x00\xFF')               # cmp.b #$ff,d2
    a.saltoW(b'\x67\x00', 'banda')         # beq.w banda
    a.saltoW(b'\x60\x00', 'genere')        # bra.w genere

    a.eti('auto')
    a.b(b'\x47\xF9'); ass(MESSAGGI)        # lea $dd70,a3
    a.b(b'\x4E\xB9'); ass(TROVA_MSG)       # jsr $d5ca
    a.eti('scan')
    a.b(b'\x10\x1B')                       # move.b (a3)+,d0
    a.b(b'\x0C\x00\x00\xFF')               # cmp.b #$ff,d0
    a.saltoW(b'\x67\x00', 'banda')         # beq.w banda
    a.b(b'\x12\x1B')                       # move.b (a3)+,d1
    a.b(b'\x08\x00\x00\x05')               # btst #5,d0      RAM9
    a.salto(b'\x66', 'scan')               # bne.b scan
    a.b(b'\x08\x00\x00\x06')               # btst #6,d0      RAM32
    a.salto(b'\x67', 'scan')               # beq.b scan
    a.b(b'\x0C\x01\x00\x48')               # cmp.b #72,d1
    a.salto(b'\x65', 'scan')               # bcs.b scan
    a.b(b'\x0C\x01\x00\x4C')               # cmp.b #76,d1
    a.salto(b'\x64', 'scan')               # bcc.b scan
    a.b(b'\x74\x00')                       # moveq #0,d2
    a.b(b'\x14\x01')                       # move.b d1,d2
    a.b(b'\x04\x42\x00\x48')               # subi.w #72,d2   posto 0-3
    a.b(b'\x41\xF9'); ass(POSTI)           # lea $129c6,a0
    a.b(b'\x14\x30\x20\x00')               # move.b 0(a0,d2.w),d2
    a.b(b'\x02\x42\x00\xFF')               # andi.w #$ff,d2
    a.saltoW(b'\x41\xFA', 'ultima')        # lea ultima(pc),a0
    a.b(b'\x10\x82')                       # move.b d2,(a0)

    a.eti('genere')                        # d2 = star 0-51
    a.b(b'\x7E\x00')                       # moveq #0,d7
    a.b(b'\x0C\x42\x00' + bytes([N_STAR])) # cmp.w #52,d2
    a.saltoW(b'\x64\x00', 'filtra')        # bcc.w filtra  (sconosciuta: m)
    a.saltoW(b'\x41\xFA', 'generi')        # lea generi(pc),a0
    a.b(b'\x1E\x30\x20\x00')               # move.b 0(a0,d2.w),d7
    a.saltoW(b'\x60\x00', 'filtra')        # bra.w filtra

    a.eti('banda')
    a.b(b'\x41\xF9'); ass(STATO)           # lea $128fc,a0
    a.b(b'\x43\xF9'); ass(POSTI)           # lea $129c6,a1
    a.saltoW(b'\x45\xFA', 'generi')        # lea generi(pc),a2
    a.b(b'\x76\x00')                       # moveq #0,d3    presenti
    a.b(b'\x7A\x00')                       # moveq #0,d5    donne
    a.b(b'\x7E\x00')                       # moveq #0,d7
    a.b(b'\x72\x03')                       # moveq #3,d1
    a.eti('bl')
    a.b(b'\x10\x18')                       # move.b (a0)+,d0
    a.b(b'\x14\x19')                       # move.b (a1)+,d2
    a.b(b'\x08\x00\x00\x07')               # btst #7,d0
    a.salto(b'\x66', 'bnext')              # bne.b bnext
    a.b(b'\x52\x03')                       # addq.b #1,d3
    a.b(b'\x02\x42\x00\xFF')               # andi.w #$ff,d2
    a.b(b'\x7C\x00')                       # moveq #0,d6
    a.b(b'\x0C\x42\x00' + bytes([N_STAR])) # cmp.w #52,d2
    a.salto(b'\x64', 'bm')                 # bcc.b bm
    a.b(b'\x1C\x32\x20\x00')               # move.b 0(a2,d2.w),d6
    a.eti('bm')
    a.b(b'\x1E\x06')                       # move.b d6,d7
    a.b(b'\xDA\x06')                       # add.b d6,d5
    a.eti('bnext')
    a.saltoW(b'\x51\xC9', 'bl')            # dbra d1,bl
    a.b(b'\x0C\x03\x00\x01')               # cmp.b #1,d3
    a.salto(b'\x67', 'filtra')             # beq.b filtra   uno solo: il suo genere
    a.b(b'\x7E\x02')                       # moveq #2,d7
    a.b(b'\x4A\x03')                       # tst.b d3
    a.salto(b'\x67', 'filtra')             # beq.b filtra
    a.b(b'\xBA\x03')                       # cmp.b d3,d5
    a.salto(b'\x66', 'filtra')             # bne.b filtra
    a.b(b'\x7E\x03')                       # moveq #3,d7    tutte donne

    # ---------------- risoluzione: d7 = soggetto, d4 = soggetto del messaggio
    a.eti('filtra')
    a.b(b'\x18\x07')                       # move.b d7,d4
    a.b(b'\x16\x07')                       # move.b d7,d3   (soggetto fuori dai nomi)
    a.b(b'\x41\xF9'); ass(BUFFER)          # lea $122c8,a0   lettura
    a.b(b'\x22\x48')                       # movea.l a0,a1   scrittura
    a.b(b'\x24\x48')                       # movea.l a0,a2   inizio
    a.eti('fl')
    a.b(b'\x10\x18')                       # move.b (a0)+,d0
    a.b(b'\x0C\x00\x00\xFF')               # cmp.b #$ff,d0
    a.saltoW(b'\x67\x00', 'fend')          # beq.w fend
    a.b(b'\x0C\x00\x00\x7B')               # cmp.b #'{',d0
    a.salto(b'\x67', 'falt')               # beq.b falt
    a.b(b'\x0C\x00\x00' + bytes([INIZIO_NOME]))  # cmp.b #$1e,d0
    a.salto(b'\x66', 'fl2')                # bne.b fl2
    a.b(b'\x16\x07')                       # move.b d7,d3   ricorda il soggetto
    a.b(b'\x7E\x00')                       # moveq #0,d7    il nome e' m.sing.
    a.salto(b'\x60', 'fl')                 # bra.b fl
    a.eti('fl2')
    a.b(b'\x0C\x00\x00' + bytes([FINE_NOME]))    # cmp.b #$1f,d0
    a.salto(b'\x66', 'fl3')                # bne.b fl3
    a.b(b'\x1E\x03')                       # move.b d3,d7   torna al soggetto
    a.salto(b'\x60', 'fl')                 # bra.b fl
    a.eti('fl3')
    a.saltoW(b'\x61\x00', 'put')           # bsr.w put
    a.salto(b'\x60', 'fl')                 # bra.b fl

    a.eti('falt')
    a.b(b'\x0C\x10\x00\x3D')               # cmp.b #'=',(a0)
    a.salto(b'\x67', 'fset')               # beq.b fset
    a.b(b'\x26\x48')                       # movea.l a0,a3
    a.b(b'\x72\x00')                       # moveq #0,d1
    a.eti('fc')
    a.b(b'\x10\x1B')                       # move.b (a3)+,d0
    a.b(b'\x0C\x00\x00\xFF')               # cmp.b #$ff,d0
    a.saltoW(b'\x67\x00', 'fend')          # beq.w fend   (troncato)
    a.b(b'\x0C\x00\x00\x7C')               # cmp.b #'|',d0
    a.salto(b'\x66', 'fc2')                # bne.b fc2
    a.b(b'\x52\x41')                       # addq.w #1,d1
    a.salto(b'\x60', 'fc')                 # bra.b fc
    a.eti('fc2')
    a.b(b'\x0C\x00\x00\x7D')               # cmp.b #'}',d0
    a.salto(b'\x66', 'fc')                 # bne.b fc
    a.b(b'\x0C\x41\x00\x03')               # cmp.w #3,d1
    a.salto(b'\x63', 'fok')                # bls.b fok
    a.b(b'\x72\x03')                       # moveq #3,d1
    a.eti('fok')
    a.b(b'\xE5\x49')                       # lsl.w #2,d1
    a.b(b'\xD2\x47')                       # add.w d7,d1
    a.saltoW(b'\x47\xFA', 'scelta')        # lea scelta(pc),a3
    a.b(b'\x7C\x00')                       # moveq #0,d6
    a.b(b'\x1C\x33\x10\x00')               # move.b 0(a3,d1.w),d6
    a.b(b'\x7A\x00')                       # moveq #0,d5
    a.eti('fs')
    a.b(b'\x10\x18')                       # move.b (a0)+,d0
    a.b(b'\x0C\x00\x00\xFF')               # cmp.b #$ff,d0
    a.saltoW(b'\x67\x00', 'fend')          # beq.w fend   (troncato)
    a.b(b'\x0C\x00\x00\x7D')               # cmp.b #'}',d0
    a.salto(b'\x67', 'fl')                 # beq.b fl
    a.b(b'\x0C\x00\x00\x7C')               # cmp.b #'|',d0
    a.salto(b'\x66', 'fs2')                # bne.b fs2
    a.b(b'\x52\x45')                       # addq.w #1,d5
    a.salto(b'\x60', 'fs')                 # bra.b fs
    a.eti('fs2')
    a.b(b'\xBC\x45')                       # cmp.w d5,d6
    a.salto(b'\x66', 'fs')                 # bne.b fs
    a.saltoW(b'\x61\x00', 'put')           # bsr.w put
    a.salto(b'\x60', 'fs')                 # bra.b fs

    a.eti('fset')                          # {=...}
    a.b(b'\x52\x88')                       # addq.l #1,a0
    a.b(b'\x0C\x10\x00\x7D')               # cmp.b #'}',(a0)
    a.salto(b'\x66', 'fset2')              # bne.b fset2
    a.b(b'\x52\x88')                       # addq.l #1,a0
    a.b(b'\x1E\x04')                       # move.b d4,d7   {=}: torna al soggetto
    a.saltoW(b'\x60\x00', 'fl')            # bra.w fl
    a.eti('fset2')
    a.b(b'\x7E\x00')                       # moveq #0,d7
    a.eti('fsl')
    a.b(b'\x10\x18')                       # move.b (a0)+,d0
    a.b(b'\x0C\x00\x00\xFF')               # cmp.b #$ff,d0
    a.saltoW(b'\x67\x00', 'fend')          # beq.w fend
    a.b(b'\x0C\x00\x00\x7D')               # cmp.b #'}',d0
    a.saltoW(b'\x67\x00', 'fl')            # beq.w fl
    a.b(b'\x0C\x00\x00\x46')               # cmp.b #'F',d0
    a.salto(b'\x66', 'fsl2')               # bne.b fsl2
    a.b(b'\x08\xC7\x00\x00')               # bset #0,d7
    a.eti('fsl2')
    a.b(b'\x0C\x00\x00\x50')               # cmp.b #'P',d0
    a.salto(b'\x66', 'fsl')                # bne.b fsl
    a.b(b'\x08\xC7\x00\x01')               # bset #1,d7
    a.salto(b'\x60', 'fsl')                # bra.b fsl

    a.eti('put')                           # d0 -> (a1)+, con la regola dello spazio
    for ch in b'!,.?':
        a.b(b'\x0C\x00\x00' + bytes([ch])) # cmp.b #ch,d0
        a.salto(b'\x67', 'pp')             # beq.b pp
    a.salto(b'\x60', 'pn')                 # bra.b pn
    a.eti('pp')
    a.b(b'\xB3\xCA')                       # cmpa.l a2,a1
    a.salto(b'\x67', 'pn')                 # beq.b pn
    a.b(b'\x0C\x29\x00\x20\xFF\xFF')       # cmp.b #' ',-1(a1)
    a.salto(b'\x66', 'pn')                 # bne.b pn
    a.b(b'\x13\x40\xFF\xFF')               # move.b d0,-1(a1)
    a.b(b'\x4E\x75')                       # rts
    a.eti('pn')
    a.b(b'\x12\xC0')                       # move.b d0,(a1)+
    a.b(b'\x4E\x75')                       # rts

    a.eti('fend')
    a.b(b'\x12\xBC\x00\xFF')               # move.b #$ff,(a1)
    a.saltoW(b'\x61\x00', 'centra')        # bsr.w centra   (manifesto: scritte centrate)
    a.b(b'\x4C\xDF\x7F\xFF')               # movem.l (a7)+,d0-d7/a0-a6
    a.b(b'\x4E\xB9'); ass(FINESTRA)        # jsr $d7e4
    a.b(b'\x41\xF9'); ass(FLAG_D586)       # lea $1286a,a0
    a.b(b'\x4E\x75')                       # rts
    centra(a)

    # ---------------- nome: al posto di "bsr.w $8842; bra.w $d71c"
    a.eti('nome')
    a.b(b'\x48\xE7\xC0\xC0')               # movem.l d0-d1/a0-a1,-(a7)
    a.b(b'\x72' + bytes([INIZIO_NOME]))    # moveq #$1e,d1
    a.saltoW(b'\x61\x00', 'segno')         # bsr.w segno
    a.b(b'\x4C\xDF\x03\x03')               # movem.l (a7)+,d0-d1/a0-a1
    a.b(b'\x4E\xB9'); ass(SOTTOCOMPOSITORE)   # jsr $8842
    a.b(b'\x48\xE7\xC0\xC0')               # movem.l d0-d1/a0-a1,-(a7)
    a.b(b'\x72' + bytes([FINE_NOME]))      # moveq #$1f,d1
    a.saltoW(b'\x61\x00', 'segno')         # bsr.w segno
    a.b(b'\x4C\xDF\x03\x03')               # movem.l (a7)+,d0-d1/a0-a1
    # Si torna con un rts normale: il "bra.b $d71c" che seguiva il bsr
    # originale e' scritto nell'aggancio subito dopo il jsr (RIEMPIMENTO).
    # Prima qui c'era "addq.l #4,a7; jmp $d71c" (salto fuori dalla routine
    # scartando il ritorno): stesso effetto sul 68000, ma i ricompilatori
    # statici vedono una chiamata che non torna e rieseguono il compositore.
    a.b(b'\x4E\x75')                       # rts
    # segno: scrive d1 nel buffer e avanza il contatore, se c'e' posto
    a.eti('segno')
    a.b(b'\x41\xF9'); ass(CONTATORE)      # lea $1285c,a0
    a.b(b'\x70\x00')                       # moveq #0,d0
    a.b(b'\x10\x10')                       # move.b (a0),d0
    a.b(b'\x0C\x00\x00\xF0')               # cmp.b #$f0,d0
    a.salto(b'\x64', 'segno_no')           # bcc.b segno_no
    a.b(b'\x43\xF9'); ass(BUFFER)         # lea $122c8,a1
    a.b(b'\x13\x81\x00\x00')               # move.b d1,0(a1,d0.w)
    a.b(b'\x13\xBC\x00\xFF\x00\x01')       # move.b #$ff,1(a1,d0.w)
    a.b(b'\x52\x10')                       # addq.b #1,(a0)
    a.eti('segno_no')
    a.b(b'\x4E\x75')                       # rts

    # ---------------- dati
    a.eti('msgnum'); a.b(b'\xFF\xFF')
    a.eti('ultima'); a.b(b'\xFF\x00')
    a.eti('scelta'); a.b(bytes(sum(SCELTA, [])))
    a.eti('soggetti')
    for m, modo in sorted(soggetti.items()):
        a.b(struct.pack('>HH', m, _MODI[modo]))
    a.b(b'\xFF\xFF\xFF\xFF')
    a.eti('generi'); a.b(bytes(generi[:N_STAR]))
    blob = a.chiudi(allinea=4)
    entrate = {k: a.etichette[k] for k in ('ingresso', 'filtro', 'nome')}
    return blob, entrate, assoluti


def verifica_agganci(img, base=0x8100):
    """I byte da sostituire devono essere quelli originali."""
    for ind, _, n, orig in AGGANCI:
        o = ind - base
        if img[o:o + len(orig)] != orig:
            raise ValueError(f"${ind:X}: byte inattesi {img[o:o+n].hex()}")


def riempimento(ind, nome, n):
    """I byte dopo il jsr di un aggancio, fino alla lunghezza originale n.
    Di norma nop; per 'nome' il salto che nel codice originale seguiva il bsr
    (bra.w $d71c), accorciato a bra.b: la routine torna con rts e si riprende
    da qui, come nell'originale."""
    if nome == 'nome':
        pc = ind + 6 + 2                       # il bra.b sta a ind+6
        d = DOPO_NOME - pc
        assert -128 <= d <= 127 and d != 0
        b = bytes([0x60, d & 0xFF])
        return b + b'\x4E\x71' * ((n - 8) // 2)
    return b'\x4E\x71' * ((n - 6) // 2)


def agganci(indirizzi):
    """indirizzi: entrata -> indirizzo della routine. Restituisce
    [(indirizzo nel gioco, byte da scrivere)]: jsr e riempimento."""
    out = []
    for ind, nome, n, _ in AGGANCI:
        b = b'\x4E\xB9' + struct.pack('>I', indirizzi[nome])
        b += riempimento(ind, nome, n)
        out.append((ind, b))
    return out


if __name__ == '__main__':
    import sys
    nomi = None
    if os.path.isfile('rockstar_band_rivali.json'):
        nomi = [r['nome'].strip() for r in json.load(open('rockstar_band_rivali.json'))]
    if len(sys.argv) > 1 and sys.argv[1] == 'generi':
        json.dump(generi_default(nomi), open(FILE_GENERI, 'w', encoding='utf-8'),
                  indent=1, ensure_ascii=False)
        print('scritto', FILE_GENERI)
    else:
        b, e, ab = codice(carica_generi())
        print(len(b), 'byte; entrate', e, 'assoluti', ab)


def soggetti_possibili(n, token):
    """I valori di soggetto che il messaggio n puo' avere a runtime, per
    l'anteprima: [0..3]. token: la lista dei token del messaggio."""
    if n in SOGGETTI:
        m = _MODI[SOGGETTI[n]]
        return [0, 1] if m >= 0xFE else [m]
    for t in token:
        if not (t & 0x2000) and (t & 0x4000) and 72 <= (t & 0xFF) <= 75:
            return [0, 1]
    return [0, 1, 2, 3]
