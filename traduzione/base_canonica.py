#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
base_canonica.py - l'immagine del gioco (a $8100) da uno dei due dischi
supportati, sempre la stessa, verificata col CRC.

    python base_canonica.py disco.ipf|disco.adf [uscita.bin]

DISCHI SUPPORTATI (riconosciuti dal CRC32 del file, non dal nome)
  53EC7260  Rock Star Ate My Hamster (Europe).ipf
            il disco originale: AmigaDOS, "boot" carica "RSTAR", che e' gia'
            il gioco decompresso da mettere a $8100.
  BB9DD80B  Rock Star Ate My Hamster (1989)(Codemasters).adf
            versione su file (1998): "RockStarAteMyHamster" e' compresso
            (adf_depack.py) ed e' la versione craccata: quattro testi diversi,
            due nei messaggi e due nomi di star. Si riportano all'originale.

LA BASE CANONICA e' RSTAR fino a $71400 (430848 byte; oltre ci sono zeri e
un avanzo mai chiamato), CRC32 5BF4600A. E' il punto di partenza della
traduzione e del port; il port fa gli stessi passi in C (amiga_disco.c).
"""
import os
import sys
import zlib

QUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, QUI)

GIOCO = 0x8100
LUNGHEZZA = 0x71400 - GIOCO      # 430848
CRC_BASE = 0x5BF4600A
CRC_IPF = 0x53EC7260
CRC_ADF = 0xBB9DD80B

# versione su file -> originale: (indirizzo, testo dell'originale)
RIPRISTINI_ADF = [
    (0x112EA, b'RELEASED THROUGH CODEMASTERS\xa0'),
    (0x11401, b'THANKS TO THE MANAGERS OF NEW ORDER, HAPPY MONDAYS'),
    (0x1149C, b'BIMBO '),
    (0x117A8, b'ANNIE SMALLPOX\xa0'),
]


def leggi_file_ofs(adf, nome):
    """un file dalla radice di un disco AmigaDOS OFS (blocchi da 512, dati 488)"""
    import struct
    def blocco(n):
        return adf[n * 512:(n + 1) * 512]
    radice = blocco(880)
    def hash_nome(s):
        h = len(s)
        for c in s.upper():
            h = (h * 13 + ord(c)) & 0x7FF
        return h % 72
    n = struct.unpack('>I', radice[24 + hash_nome(nome) * 4:28 + hash_nome(nome) * 4])[0]
    while n:
        b = blocco(n)
        l = b[432]
        if b[433:433 + l].decode('latin1').upper() == nome.upper():
            dim = struct.unpack('>I', b[324:328])[0]
            dati = bytearray()
            d = struct.unpack('>I', b[16:20])[0]          # primo blocco dati
            while d and len(dati) < dim:
                bd = blocco(d)
                k = struct.unpack('>I', bd[12:16])[0]
                dati += bd[24:24 + k]
                d = struct.unpack('>I', bd[16:20])[0]
            return bytes(dati[:dim])
        n = struct.unpack('>I', b[496:500])[0]          # catena dell'hash
    raise FileNotFoundError(nome)


def base_da_disco(dati):
    crc = zlib.crc32(dati) & 0xFFFFFFFF
    if crc == CRC_IPF:
        import ipf_leggi
        adf = ipf_leggi.adf_da_ipf(dati)
        base = bytearray(leggi_file_ofs(adf, 'RSTAR')[:LUNGHEZZA])
    elif crc == CRC_ADF:
        import adf_depack
        base = bytearray(adf_depack.depack(leggi_file_ofs(dati, 'RockStarAteMyHamster')))
        for a, testo in RIPRISTINI_ADF:
            base[a - GIOCO:a - GIOCO + len(testo)] = testo
    else:
        raise ValueError('disco non riconosciuto (CRC %08X)' % crc)
    base += bytes(LUNGHEZZA - len(base))
    base = bytes(base[:LUNGHEZZA])
    if zlib.crc32(base) & 0xFFFFFFFF != CRC_BASE:
        raise ValueError('base diversa da quella attesa (CRC %08X)' % (zlib.crc32(base) & 0xFFFFFFFF))
    return base


if __name__ == '__main__':
    b = base_da_disco(open(sys.argv[1], 'rb').read())
    print('base canonica: %d byte, CRC %08X' % (len(b), zlib.crc32(b) & 0xFFFFFFFF))
    if len(sys.argv) > 2:
        open(sys.argv[2], 'wb').write(b)
