#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
icone.py - le icone Workbench dell'installazione WHDLoad, disegnate qui.

Icone classiche (DiskObject, immagine a 2 bitplane: 0 sfondo, 1 nero,
2 bianco, 3 colore), che vanno dal Kickstart 1.3 in poi:
    cassetto()      la cartella RockStarAteMyHamsterIt
    gioco(slave)    progetto: WHDLoad con SLAVE=, PRELOAD e CONFIGDELAY=-1
                    (la finestra di WHDLoad aspetta il pulsante Start e mostra
                    le caselle dei trucchi)
    leggimi()       il ReadMe, da aprire con MultiView

    python icone.py CARTELLA      scrive le tre icone, per guardarle
"""
import math
import struct

NO_POSIZIONE = 0x80000000


def _piani(pix):
    """righe di indici di colore -> dati dell'Image (piano 0, poi piano 1)"""
    h = len(pix)
    w = len(pix[0])
    parole = (w + 15) // 16
    out = bytearray()
    for piano in range(2):
        for riga in pix:
            bit = bytearray(parole * 2)
            for x, c in enumerate(riga):
                if (c >> piano) & 1:
                    bit[x >> 3] |= 0x80 >> (x & 7)
            out += bit
    return w, h, bytes(out)


def _icona(tipo, pix, strumento=None, tooltype=None, cassetto=False):
    w, h, dati = _piani(pix)
    d = bytearray()
    d += struct.pack('>HH', 0xE310, 1)                   # magic, versione
    # Gadget: NextGadget, Left, Top, Width, Height, Flags (GADGIMAGE),
    # Activation (RELVERIFY|GADGIMMEDIATE), GadgetType (BOOLGADGET),
    # GadgetRender, SelectRender, GadgetText, MutualExclude, SpecialInfo,
    # GadgetID, UserData
    d += struct.pack('>IhhhhHHHIIIIIHI', 0, 0, 0, w, h + 1, 0x0004, 0x0003, 0x0001,
                     1, 0, 0, 0, 0, 0, 0)
    d += struct.pack('>BB', tipo, 0)
    d += struct.pack('>II', 1 if strumento else 0, 1 if tooltype else 0)
    d += struct.pack('>II', NO_POSIZIONE, NO_POSIZIONE)
    d += struct.pack('>III', 1 if cassetto else 0, 0, 4096 if tipo == 4 else 0)
    assert len(d) == 78
    if cassetto:
        # NewWindow della finestra del cassetto, poi CurrentX/Y
        d += struct.pack('>hhhhBBIIIIIIIhhHHH', 60, 40, 360, 120, 255, 255, 0,
                         0x0200127F, 0, 0, 0, 0, 0, 90, 40, 0xFFFF, 0xFFFF, 1)
        d += struct.pack('>ii', 0, 0)
    d += struct.pack('>hhhhhIBBI', 0, 0, w, h, 2, 1, 3, 0, 0) + dati
    if strumento:
        s = strumento.encode('latin1') + b'\0'
        d += struct.pack('>I', len(s)) + s
    if tooltype:
        d += struct.pack('>I', (len(tooltype) + 1) * 4)
        for t in tooltype:
            s = t.encode('latin1') + b'\0'
            d += struct.pack('>I', len(s)) + s
    return bytes(d)


def _tela(w, h):
    return [[0] * w for _ in range(h)]


def _bordo(pix, dentro, colore=1):
    """contorna di nero i pixel colorati che toccano lo sfondo"""
    h, w = len(pix), len(pix[0])
    for y in range(h):
        for x in range(w):
            if not dentro(x, y):
                continue
            if any(not (0 <= x + dx < w and 0 <= y + dy < h and dentro(x + dx, y + dy))
                   for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1))):
                pix[y][x] = colore


def cassetto():
    w, h = 48, 22
    pix = _tela(w, h)
    for y in range(4, h):
        for x in range(2, w - 2):
            pix[y][x] = 2
    for x in range(8, 22):                               # linguetta della cartella
        for y in range(1, 4):
            pix[y][x] = 3
    _bordo(pix, lambda x, y: pix[y][x] != 0)
    for x in range(18, 30):                              # maniglia
        pix[12][x] = 1
    for y in range(10, 13):
        pix[y][18] = pix[y][29] = 1
    return _icona(2, pix, cassetto=True)


def gioco(slave):
    w, h = 44, 26
    pix = _tela(w, h)
    cx, cy, r1, r2 = w / 2, h / 2 + 1, 12.5, 5.0          # stella a 5 punte
    vertici = []
    for k in range(10):
        a = -math.pi / 2 + k * math.pi / 5
        r = r1 if k % 2 == 0 else r2
        vertici.append((cx + r * math.cos(a) * 1.6, cy + r * math.sin(a)))  # pixel larghi
    def dentro(x, y):
        px, py = x + 0.5, y + 0.5
        c = False
        for i in range(10):
            (x1, y1), (x2, y2) = vertici[i], vertici[i - 1]
            if (y1 > py) != (y2 > py) and px < (x2 - x1) * (py - y1) / (y2 - y1) + x1:
                c = not c
        return c
    for y in range(h):
        for x in range(w):
            if dentro(x, y):
                pix[y][x] = 3
    _bordo(pix, dentro)
    for x, y in ((21, 11), (22, 11), (20, 12), (23, 12)):  # luccichio
        pix[y][x] = 2
    return _icona(4, pix, 'WHDLoad', ['SLAVE=' + slave, 'PRELOAD', 'CONFIGDELAY=-1'])


def leggimi():
    w, h = 30, 26
    pix = _tela(w, h)
    for y in range(1, h - 1):
        for x in range(4, w - 4):
            pix[y][x] = 2
    _bordo(pix, lambda x, y: pix[y][x] != 0)
    for y in range(5, h - 4, 3):                         # righe di testo
        for x in range(8, w - 8 - (y % 2) * 4):
            pix[y][x] = 1
    return _icona(4, pix, 'MultiView')


if __name__ == '__main__':
    import os, sys
    out = sys.argv[1] if len(sys.argv) > 1 else '.'
    os.makedirs(out, exist_ok=True)
    for nome, d in (('cassetto.info', cassetto()), ('gioco.info', gioco('Gioco.slave')),
                    ('ReadMe.info', leggimi())):
        open(os.path.join(out, nome), 'wb').write(d)
        print(nome, len(d))
