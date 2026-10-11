#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
adf_depack.py - decomprime RockStarAteMyHamster dall'ADF "(1989)(Codemasters)"
(versione su file, 1998) senza emulare il 68000. Prototipo del codice C.

    python adf_depack.py RockStarAteMyHamster uscita.bin

Il programma (un solo hunk di codice) copia a $78000 646 byte di depacker e
salta a $78040:
  1. i dati compressi (dall'offset $2F8 dell'hunk, lunghi $398DC) finiscono
     a $8100; l'ultimo long e' la lunghezza decompressa, il penultimo il
     primo long del flusso di bit, che si legge all'indietro.
  2. stadio 1 (a ritroso, da $1A7A4 + lunghezza verso $1A7A4): letterali
     tramite una tabella di 256 byte (all'offset $186 del depacker) e copie
     all'indietro con distanza a 9 bit.
  3. stadio 2, RLE in avanti da $1A7A4 a $71000 verso $8100: il byte $6D
     introduce "n, valore" = n+3 copie; "$6D, 0" e' un $6D singolo.
"""
import struct
import sys

DEPACKER = 0x72          # nell'hunk: i 646 byte copiati a $78000
DATI = 0x2F8             # nell'hunk: inizio dei dati compressi
LUNG_DATI = 0x398DC
TABELLA = 0x186          # nel depacker: tabella dei letterali
INIZIO1 = 0x1A7A4        # destinazione dello stadio 1
FINE2 = 0x71000          # fine della sorgente dello stadio 2
GIOCO = 0x8100


def hunk_codice(exe):
    p = 0
    def u32():
        nonlocal p
        v = struct.unpack('>I', exe[p:p + 4])[0]; p += 4; return v
    if u32() != 0x3F3:
        raise ValueError('non e\' un eseguibile Amiga')
    while u32():
        pass
    u32(); primo = u32(); ultimo = u32()
    for _ in range(ultimo - primo + 1):
        u32()
    if u32() & 0x3FFFFFFF != 0x3E9:
        raise ValueError('manca l\'hunk di codice')
    n = u32()
    return exe[p:p + n * 4]


def depack(exe):
    h = hunk_codice(exe)
    tab = h[DEPACKER + TABELLA:DEPACKER + TABELLA + 256]
    mem = bytearray(0x80000)
    src = h[DATI:DATI + LUNG_DATI]
    mem[GIOCO:GIOCO + len(src)] = src           # copia dei dati compressi
    a0 = GIOCO + len(src)

    # ---- stadio 1
    def long_prec():
        nonlocal a0
        a0 -= 4
        return struct.unpack('>I', mem[a0:a0 + 4])[0]
    a1 = INIZIO1
    a2 = a1 + long_prec()
    d0 = long_prec()

    def bit():
        nonlocal d0
        c = d0 & 1
        d0 >>= 1
        if d0 == 0:                         # ricarica: X=1 entra da sinistra
            d0 = long_prec()
            c = d0 & 1
            d0 = (d0 >> 1) | 0x80000000
        return c

    def bits(n):
        v = 0
        for _ in range(n):
            v = (v << 1) | bit()
        return v

    while True:
        n = bits(3)
        if n:
            if n == 7:
                if not bit():
                    n = bits(2) + 7
                else:
                    n = bits(8)
                    if n:
                        n += 10
                    else:
                        n = bits(12)
                        n = n + 0x109 if n else bits(15) + 0x110B
            for _ in range(n):              # letterali
                if not bit():
                    d5, d1 = 8, 6
                elif not bit():
                    d5, d1 = 0, 3
                elif not bit():
                    d5, d1 = 0x48, 6
                else:
                    d5, d1 = 0x88, 7
                k = bits(d1) + d5
                a2 -= 1
                mem[a2] = tab[k] if k < 256 else 0
        if a1 >= a2:
            break
        # copia
        if not bit():
            conta = 2 if not bit() else 1
        else:
            s = bits(2)
            if s == 0:
                conta = 3
            elif s == 3:
                conta = bits(8) + 14
            elif s == 1:
                conta = 4 + bits(1)
            else:
                conta = 6 + bits(3)
        dist = bits(9)
        for _ in range(conta + 1):
            sorg = a2 - 1 + dist
            a2 -= 1
            mem[a2] = mem[sorg]
        if a1 >= a2:
            break

    # ---- stadio 2: RLE
    out = bytearray()
    i = INIZIO1
    while i < FINE2:
        b = mem[i]; i += 1
        if b == 0x6D:
            n = mem[i]; i += 1
            if n:
                v = mem[i]; i += 1
                out += bytes([v]) * (n + 3)
                continue
        out.append(b)
    return bytes(out)


if __name__ == '__main__':
    r = depack(open(sys.argv[1], 'rb').read())
    open(sys.argv[2], 'wb').write(r)
    print('decompressi %d byte' % len(r))
