# -*- coding: utf-8 -*-
"""
build_riloc.py - il gioco come eseguibile AmigaDOS vero, rilocabile.

Niente stub, niente decompressione, niente copia: AmigaDOS carica gli hunk
dove vuole, applica HUNK_RELOC32 e parte dal primo byte del codice, che e'
l'ingresso originale del gioco ($8100).

HUNK
    0  CODE, chip   l'immagine ($8100-$71000), poi la zona di lavoro fino a
                    $80000 (buffer e stack), poi il codice aggiunto e la
                    tabella estesa dei testi
    1  BSS,  chip   lo schermo ($400-$8100, 4 bitplane da 8000 byte)

Tutti e due in chip: grafica e musica stanno nell'immagine e le legge il DMA.
Serve 1MB di chip (A500 con Agnus da 1MB, A500+, A600, A1200, A3000, A4000).

COSA SI RILOCA
    - ogni campo a 32 bit del codice che contiene un indirizzo fra $400 e
      $80000 (tools/rilocazioni.py, dal disassemblato)
    - i puntatori nei dati trovati facendo girare il gioco in emulazione
      (PUNTATORI_DATI qui sotto)
    - la lista copper: i puntatori ai bitplane sono spezzati in due mezze
      parole, che RELOC32 non sa correggere. L'istruzione che la attiva
      ($81A8) diventa una chiamata a una routine aggiunta in fondo all'hunk
      che scrive le due meta' dall'indirizzo vero dello schermo.
    - la tabella dei testi: le cinque basi puntano direttamente alla tabella
      estesa in fondo all'hunk. Qui la tabella compatta non serve piu'.
"""
import struct
import sys

import os as _os
sys.path.insert(0, _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), 'tools'))
from asm68k import Asm
from build_ram import (costruisci, carica, GIOCO, SITI_G_ABS, SITO_S_ABS,
                       SITO_G_PC, SITO_S_PC, PTR_G, PTR_S)

SCHERMO, FINE_SCHERMO = 0x400, 0x8100
FINE_LAVORO = 0x80000
COPPER = 0x82D6
SITO_COPPER = 0x81A8            # move.l #$82d6,$80(a5)
LUNG_IMM = 0x71000 - GIOCO

# puntatori nei dati (indirizzo nell'immagine della longword), trovati in
# emulazione: vedi tools/emula.py
PUNTATORI_DATI = []

# immediati a 32 bit nella zona che NON sono indirizzi (conteggi, maschere,
# spostamenti): esaminati uno per uno
NON_INDIRIZZI_MNEM = ('adda.l', 'suba.l')


FILE_RILOCAZIONI = _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), 'rilocazioni.json')


def trova_rilocazioni(img):
    """Gli indirizzi dei campi da rilocare dipendono solo dal codice, che la
    traduzione non tocca: si calcolano una volta (serve capstone) e si
    salvano in rilocazioni.json, che l'editor usa senza bisogno d'altro."""
    import json, os
    if os.path.isfile(FILE_RILOCAZIONI):
        return json.load(open(FILE_RILOCAZIONI))
    from disasm_rsamh import analizza
    from rilocazioni import campi
    d = analizza(img)
    sicuri, dubbi, corti = campi(img, d)
    if corti:
        raise ValueError(f"operandi assoluti a 16 bit nella zona: {corti[:5]}")
    out = []
    for campo, a, m, ops in sicuri:
        if m in NON_INDIRIZZI_MNEM and '#' in ops:
            continue
        out.append(campo + GIOCO)       # indirizzo della longword
    out = sorted(set(out))
    try:
        json.dump(out, open(FILE_RILOCAZIONI, 'w'))
    except OSError:
        pass
    return out


def costruisci_riloc(imm, est_voci, rilocazioni=None, generi=None):
    """imm: immagine italiana (testi fissi e riordini gia' applicati).
    Restituisce (eseguibile, info) con info['hunk0'], info['riloc0'],
    info['riloc1'] per l'emulatore."""
    imm = bytearray(imm[:LUNG_IMM])
    rel = list(rilocazioni if rilocazioni is not None else trova_rilocazioni(bytes(imm)))
    rel += PUNTATORI_DATI
    h0 = bytearray(imm) + bytes(FINE_LAVORO - GIOCO - len(imm))
    agg = len(h0)                                  # codice aggiunto: offset nell'hunk 0

    # ---- routine della lista copper
    a = Asm()
    a.b(b'\x41\xF9').dato32(0); f_scher = a.pos() - 4          # lea schermo,a0
    a.b(b'\x43\xF9').dato32(0); f_cop = a.pos() - 4            # lea copper,a1
    a.b(b'\x20\x08')                                           # move.l a0,d0
    a.b(b'\x72\x03')                                           # moveq #3,d1
    a.eti('piano')
    a.b(b'\x48\x40\x33\x40\x00\x02\x48\x40\x33\x40\x00\x06')   # swap;move.w d0,2(a1);swap;move.w d0,6(a1)
    a.b(b'\x06\x80\x00\x00\x1F\x40')                           # addi.l #$1f40,d0
    a.b(b'\x50\x89')                                           # addq.l #8,a1
    a.b(b'\x51\xC9'); a.da_fare.append((a.pos(), 'piano', 'w', a.pos())); a.b(b'\x00\x00')
    a.b(b'\x2B\x7C').dato32(0); f_cop2 = a.pos() - 4           # move.l #copper,$80(a5)
    a.b(b'\x00\x80')
    a.b(b'\x4E\x75')                                           # rts
    rout = a.chiudi(4)
    h0 += rout
    tab_off = len(h0)
    est, off_str = costruisci(est_voci)
    h0 += est
    while len(h0) % 4: h0 += b'\x00'

    # ---- accordo di genere e numero (accordo.py)
    import accordo
    if generi is None:
        generi = accordo.carica_generi(_os.path.dirname(_os.path.abspath(__file__)))
    accordo.verifica_agganci(imm)
    acc_blob, acc_ent, acc_abs = accordo.codice(generi)
    acc_off = len(h0)
    h0 += acc_blob
    while len(h0) % 4: h0 += b'\x00'

    r0, r1 = [], []                                # offset di longword da rilocare

    def rel_a(off_campo, valore):
        """scrive il valore (indirizzo del gioco) come offset nell'hunk giusto"""
        if SCHERMO <= valore < FINE_SCHERMO:
            struct.pack_into('>I', h0, off_campo, valore - SCHERMO); r1.append(off_campo)
        elif FINE_SCHERMO <= valore <= FINE_LAVORO:
            struct.pack_into('>I', h0, off_campo, valore - GIOCO); r0.append(off_campo)
        else:
            raise ValueError(f"valore {valore:#x} fuori zona")

    sc = SITO_COPPER - GIOCO
    assert h0[sc:sc + 8] == bytes.fromhex('2B7C000082D60080'), h0[sc:sc + 8].hex()
    for ind in rel:
        o = ind - GIOCO
        rel_a(o, struct.unpack_from('>I', h0, o)[0])

    # copper
    struct.pack_into('>I', h0, agg + f_scher, 0); r1.append(agg + f_scher)
    struct.pack_into('>I', h0, agg + f_cop, COPPER - GIOCO); r0.append(agg + f_cop)
    struct.pack_into('>I', h0, agg + f_cop2, COPPER - GIOCO); r0.append(agg + f_cop2)
    s = sc
    h0[s:s + 8] = b'\x4E\xB9' + struct.pack('>I', agg) + b'\x4E\x71'   # jsr routine ; nop
    if s + 2 in r0 or s + 2 in r1:
        r0 = [x for x in r0 if x != s + 2]; r1 = [x for x in r1 if x != s + 2]
    r0.append(s + 2)

    # tabella estesa: le cinque basi
    for ind in SITI_G_ABS + [PTR_G]:
        o = ind - GIOCO
        struct.pack_into('>I', h0, o, tab_off + 1)
        r1 = [x for x in r1 if x != o]
        if o not in r0: r0.append(o)
    for ind in (SITO_S_ABS, PTR_S):
        o = ind - GIOCO
        struct.pack_into('>I', h0, o, tab_off + off_str)
        r1 = [x for x in r1 if x != o]
        if o not in r0: r0.append(o)
    for indir, ptr in ((SITO_G_PC, PTR_G), (SITO_S_PC, PTR_S)):
        o = indir - GIOCO
        struct.pack_into('>H', h0, o, 0x267A)                      # movea.l d16(pc),a3
        struct.pack_into('>h', h0, o + 2, ptr - (indir + 2))

    # accordo: indirizzi del gioco dentro la routine, e i due agganci
    for o in acc_abs:
        rel_a(acc_off + o, struct.unpack_from('>I', h0, acc_off + o)[0])
    for ind, dest in accordo.agganci({k: acc_off + v for k, v in acc_ent.items()}):
        o = ind - GIOCO
        h0[o:o + len(dest)] = dest
        r0 = [x for x in r0 if x != o + 2]; r1 = [x for x in r1 if x != o + 2]
        r0.append(o + 2)

    r0 = sorted(set(r0)); r1 = sorted(set(r1))
    lw0 = len(h0) // 4
    lw1 = (FINE_SCHERMO - SCHERMO) // 4
    CHIP = 0x40000000
    e = bytearray()
    for x in (0x3F3, 0, 2, 0, 1, lw0 | CHIP, lw1 | CHIP): e += struct.pack('>I', x)
    e += struct.pack('>II', 0x3E9, lw0) + h0
    e += struct.pack('>I', 0x3EC)                                   # HUNK_RELOC32
    for dest, lista in ((0, r0), (1, r1)):
        if lista:
            e += struct.pack('>II', len(lista), dest)
            for x in lista: e += struct.pack('>I', x)
    e += struct.pack('>I', 0)
    e += struct.pack('>I', 0x3F2)
    e += struct.pack('>II', 0x3EB, lw1) + struct.pack('>I', 0x3F2)   # HUNK_BSS
    info = dict(hunk0=bytes(h0), riloc0=r0, riloc1=r1, tabella=tab_off,
                eseguibile=len(e), estesa=len(est), rilocazioni=len(r0) + len(r1))
    return bytes(e), info


if __name__ == '__main__':
    import json
    imm = open(sys.argv[1], 'rb').read()
    e, info = costruisci_riloc(imm, carica(sys.argv[2]))
    open(sys.argv[3], 'wb').write(e)
    print(f"eseguibile {info['eseguibile']} byte, {info['rilocazioni']} rilocazioni")
