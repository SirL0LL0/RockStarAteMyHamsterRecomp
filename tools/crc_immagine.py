#!/usr/bin/env python3
"""crc_immagine.py - CRC32 dell'immagine da cui e' stato generato il C.

    python tools/crc_immagine.py immagine.bin uscita.h

L'eseguibile lo confronta con l'immagine che carica: se non coincidono, il
codice ricompilato e i dati non sono della stessa versione (costanti come
gli indirizzi delle tabelle dei testi sarebbero sfasate) e il gioco non parte.
"""
import sys
import zlib

dati = open(sys.argv[1], 'rb').read()
open(sys.argv[2], 'w').write(
    '/* generato da tools/crc_immagine.py: non modificare */\n'
    '#define AMIGA_IMMAGINE_CRC 0x%08Xu\n'
    '#define AMIGA_IMMAGINE_DIM %du\n' % (zlib.crc32(dati) & 0xFFFFFFFF, len(dati)))
