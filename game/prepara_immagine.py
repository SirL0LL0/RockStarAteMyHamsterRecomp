#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
prepara_immagine.py - l'immagine della chip RAM da dare ad AmigaRecomp.

    python game/prepara_immagine.py [--traduzione CARTELLA] [--uscita FILE]

Il repository non contiene file del gioco. L'immagine si costruisce dai tuoi:
la cartella della traduzione (default: quella che contiene il repository)
deve avere rockstar_ita_img.bin e le tabelle dei testi, cioe' cio' che
produce la pipeline della traduzione (build_whdload.py, build_ram.py).

Come fa lo slave WHDLoad: immagine a $8100, blocco esteso (post-codice,
tabella estesa, accordo) a $90000; il post-codice viene eseguito in Unicorn e
collega tabella e agganci. Poi in testa si scrive la tabella dei vettori che
il gioco installa da se', cosi' il ricompilatore sa da dove partire:

    $00 SSP    $04 ingresso $8100    $68 livello 2 (tastiera)
    $6C livello 3 (VBlank, player musicale)    $80 trap #0 ($810A)
"""
import argparse
import os
import struct
import sys

QUI = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(QUI)

DIMENSIONE = 0x100000
GIOCO = 0x8100
EXT = 0x90000
SSP = 0x7F000
SENTINELLA = 0xFFF0
VETTORI = {0x00: SSP, 0x04: GIOCO, 0x68: 0xB95A, 0x6C: 0x132EA, 0x80: 0x810A}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--traduzione", default=os.path.dirname(REPO))
    ap.add_argument("--uscita", default=os.path.join(REPO, "build", "rockstar_chipram.bin"))
    o = ap.parse_args()

    sys.path.insert(0, o.traduzione)
    import build_whdload as bw
    import build_ram as br
    from unicorn import Uc, UC_ARCH_M68K, UC_MODE_BIG_ENDIAN
    from unicorn.m68k_const import UC_M68K_REG_A7, UC_M68K_REG_PC, UC_CPU_M68K_M68000

    t = lambda n: os.path.join(o.traduzione, n)
    imm = open(t('rockstar_ita_img.bin'), 'rb').read()
    img, ext = bw.file_dati(imm, br.carica(t('rockstar_text_table_ESTESA.json')),
                            br.carica(t('rockstar_text_table_ITA.json')))
    m = bytearray(DIMENSIONE)
    m[GIOCO:GIOCO + len(img)] = img
    m[EXT:EXT + len(ext)] = ext

    uc = Uc(UC_ARCH_M68K, UC_MODE_BIG_ENDIAN)
    uc.ctl_set_cpu_model(UC_CPU_M68K_M68000)
    uc.mem_map(0, DIMENSIONE)
    for i in range(0, DIMENSIONE, 0x8000):          # a blocchi: bug del binding
        uc.mem_write(i, bytes(m[i:i + 0x8000]))
    pila = 0x7F000
    uc.mem_write(pila, struct.pack('>I', SENTINELLA))
    uc.reg_write(UC_M68K_REG_A7, pila)
    uc.emu_start(EXT, SENTINELLA, count=200000)
    if uc.reg_read(UC_M68K_REG_PC) != SENTINELLA:
        raise SystemExit("il post-codice non e' tornato")
    out = bytearray()
    for i in range(0, DIMENSIONE, 0x8000):
        out += uc.mem_read(i, 0x8000)
    out[pila:pila + 4] = bytes(4)
    for a, v in VETTORI.items():
        struct.pack_into('>I', out, a, v)
    os.makedirs(os.path.dirname(o.uscita), exist_ok=True)
    open(o.uscita, 'wb').write(out)
    print("immagine: %s (%d byte), blocco esteso %d byte a $%X" % (o.uscita, len(out), len(ext), EXT))


if __name__ == '__main__':
    main()
