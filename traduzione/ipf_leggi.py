#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ipf_leggi.py - legge un'immagine IPF (CAPS/SPS) di un disco Amiga e ne
ricava i settori AmigaDOS, cioe' un ADF. Prototipo del lettore in C del port.

    python ipf_leggi.py disco.ipf [uscita.adf]

FORMATO (record con intestazione: tipo[4] lunghezza[4] crc[4])
    CAPS  firma
    INFO  encoder, cilindri e testine min/max, ...
    IMGE  per traccia: cil, testa, ..., numero di blocchi, chiave dati
    DATA  per chiave: lunghezza extra, bit, crc, chiave; poi l'extra:
          descrittori dei blocchi (32 byte l'uno) e i flussi gap/dati.
    Nei flussi ogni elemento ha un byte di testa: tipo nei 5 bit bassi
    (1 sync MFM gia' codificato, 2 dati da codificare, 3 gap, 4 MFM grezzo,
    5 bit casuali), nei 3 alti quanti byte segue il conteggio; il conteggio e'
    in byte (o in bit se il blocco ha il flag 2), poi i campioni. Tipo 0 = fine.

Ricostruito il flusso MFM della traccia, i settori Amiga si cercano dal
sync $4489 $4489 e si decodificano nel modo dispari/pari del trackdisk.
"""
import struct
import sys


def mfm_codifica(dati, prec=0):
    """byte di dati -> parole MFM (bit di clock = 1 solo fra due zeri)"""
    out = bytearray()
    for b in dati:
        w = 0
        for k in range(7, -1, -1):
            d = (b >> k) & 1
            c = 1 if (prec == 0 and d == 0) else 0
            w = (w << 2) | (c << 1) | d
            prec = d
        out += struct.pack('>H', w)
    return out, prec


def leggi_record(d):
    p = 0
    while p + 12 <= len(d):
        tipo = d[p:p + 4].decode('latin1')
        lung = struct.unpack('>I', d[p + 4:p + 8])[0]
        corpo = d[p + 12:p + lung]
        p += lung
        extra = b''
        if tipo == 'DATA':
            n = struct.unpack('>I', corpo[0:4])[0]
            extra = d[p:p + n]
            p += n
        yield tipo, corpo, extra


def traccia_mfm(imge, extra):
    (cil, testa, den, sig, tbyte, sbyte, sbit, dbit, gbit, tbit, nblocchi,
     proc, flag, chiave) = struct.unpack('>14I', imge[:56])
    out = bytearray()
    prec = 0
    for b in range(nblocchi):
        (bbit, gapbit, gapoff, celltype, enc, bflag, gapdef, dataoff) = \
            struct.unpack('>8I', extra[b * 32:b * 32 + 32])
        p = dataoff
        while True:
            testa_el = extra[p]; p += 1
            tipo = testa_el & 0x1F
            if tipo == 0:
                break
            nb = testa_el >> 5
            conta = int.from_bytes(extra[p:p + nb], 'big'); p += nb
            if bflag & 2:                       # conteggio in bit
                conta = (conta + 7) // 8
            camp = extra[p:p + conta]; p += conta
            if tipo == 2:                       # dati: da codificare in MFM
                w, prec = mfm_codifica(camp, prec)
                out += w
            elif tipo in (1, 4):                # sync / MFM grezzo
                out += camp
                prec = camp[-1] & 1 if camp else prec
            else:                               # gap e casuali: zeri codificati
                w, prec = mfm_codifica(bytes(len(camp)), prec)
                out += w
    return cil, testa, out


def settori_amiga(mfm):
    """trova i settori trackdisk in una traccia MFM; restituisce {n: 512 byte}"""
    m = bytes(mfm) + bytes(mfm[:1200])          # la traccia e' circolare

    def lungo(o):
        return struct.unpack('>I', m[o:o + 4])[0]

    def dec(o_disp, o_pari, n):
        r = bytearray()
        for i in range(0, n, 4):
            a = lungo(o_disp + i) & 0x55555555
            b = lungo(o_pari + i) & 0x55555555
            r += struct.pack('>I', (a << 1) | b)
        return bytes(r)
    trovati = {}
    i = 0
    while True:
        i = m.find(b'\x44\x89\x44\x89', i)
        if i < 0 or i + 4 + 1080 > len(m):
            break
        s = i + 4
        info = dec(s, s + 4, 4)
        fmt, trk, sec, alla = info
        dati = dec(s + 56, s + 56 + 512, 512)
        if fmt == 0xFF and sec < 11 and sec not in trovati:
            trovati[sec] = (trk, dati)
        i += 4
    return trovati


def adf_da_ipf(d):
    """i 1760 settori AmigaDOS di un IPF; errore se una traccia non e' completa"""
    imge, dati = {}, {}
    for tipo, corpo, extra in leggi_record(d):
        if tipo == 'IMGE':
            imge[struct.unpack('>I', corpo[52:56])[0]] = corpo
        elif tipo == 'DATA':
            dati[struct.unpack('>I', corpo[12:16])[0]] = extra
    adf = bytearray(1760 * 512)
    for chiave, im in imge.items():
        cil, testa, mfm = traccia_mfm(im, dati.get(chiave, b''))
        if cil > 79:
            continue
        t = cil * 2 + testa
        sett = settori_amiga(mfm)
        if len(sett) != 11:
            raise ValueError('traccia %d: %d settori' % (t, len(sett)))
        for n, (trk, contenuto) in sett.items():
            adf[(t * 11 + n) * 512:(t * 11 + n + 1) * 512] = contenuto
    return bytes(adf)


def main():
    d = open(sys.argv[1], 'rb').read()
    imge = {}
    dati = {}
    for tipo, corpo, extra in leggi_record(d):
        if tipo == 'IMGE':
            chiave = struct.unpack('>I', corpo[52:56])[0]
            imge[chiave] = corpo
        elif tipo == 'DATA':
            chiave = struct.unpack('>I', corpo[12:16])[0]
            dati[chiave] = extra
    adf = bytearray(1760 * 512)
    stato = []
    for chiave, im in sorted(imge.items(), key=lambda kv: struct.unpack('>2I', kv[1][:8])):
        cil, testa, mfm = traccia_mfm(im, dati.get(chiave, b''))
        if cil > 79:
            continue
        sett = settori_amiga(mfm)
        t = cil * 2 + testa
        stato.append((t, len(sett), len(mfm)))
        for n, (trk, contenuto) in sett.items():
            adf[(t * 11 + n) * 512:(t * 11 + n + 1) * 512] = contenuto
    piene = sum(1 for _, n, _ in stato if n == 11)
    print('tracce con 11 settori AmigaDOS: %d su %d' % (piene, len(stato)))
    strane = [(t, n, l) for t, n, l in stato if n != 11]
    if strane:
        print('tracce non standard (traccia, settori, byte MFM):', strane[:20])
    print('bootblock:', adf[:4], 'DOS' if adf[:3] == b'DOS' else 'non DOS')
    if len(sys.argv) > 2:
        open(sys.argv[2], 'wb').write(adf)
        print('scritto', sys.argv[2])


if __name__ == '__main__':
    main()
