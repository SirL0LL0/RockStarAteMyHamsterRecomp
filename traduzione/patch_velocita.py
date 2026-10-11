#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
patch_velocita.py - stessa velocita' su 68000 e su 68020/030/040/060.

IL PROBLEMA
    Tutte le pause del gioco (messaggi, menu, introduzione) passano da
    f_0b4a4, che chiama sei volte f_0b4be:

        f_0b4be: aspetta finche' il byte basso di VHPOSR ($dff006) e' 0,
                 cioe' finche' il pennello e' sulla riga 0 o sulla 256.

    Su un 68000 sei chiamate durano piu' di una riga di schermo (64 us),
    quindi ogni f_0b4a4 aspetta un nuovo passaggio del pennello (circa mezzo
    quadro). Su un 68020 o piu' le sei chiamate stanno tutte dentro la stessa
    riga 0: nessuna attesa, e i testi scorrono troppo in fretta.

LA CORREZIONE
    f_0b4a4 riscritta nei suoi 26 byte: prima esce dalla riga 0/256, poi
    aspetta di rientrarci. Un passaggio del pennello per chiamata, come sul
    68000, su qualsiasi CPU. All'uscita d0 = 0 come nell'originale.
"""

GIOCO = 0x8100
INDIRIZZO = 0x0B4A4

ORIGINALE = bytes.fromhex(
    '6100 0018 6100 0014 6100 0010 6100 000c 6100 0008 6100 0004 4e75'
    .replace(' ', ''))

NUOVO = bytes.fromhex(
    '2f0d'            # move.l  a5,-(a7)
    '4bf9 00df f000'  # lea     $dff000,a5
    '4a2d 0006'       # .fuori: tst.b $6(a5)   ancora sulla riga 0/256?
    '67fa'            #         beq.b .fuori
    '4a2d 0006'       # .dentro: tst.b $6(a5)  aspetta la prossima
    '66fa'            #         bne.b .dentro
    '7000'            # moveq   #0,d0
    '2a5f'            # movea.l (a7)+,a5
    '4e75'            # rts
    .replace(' ', ''))

assert len(NUOVO) <= len(ORIGINALE)


def applica(imm):
    """imm: bytearray dell'immagine (offset 0 = $8100). La modifica sul posto.
    Accetta anche un'immagine gia' corretta."""
    o = INDIRIZZO - GIOCO
    attuale = bytes(imm[o:o + len(ORIGINALE)])
    if attuale.startswith(NUOVO):
        return imm
    if attuale != ORIGINALE:
        raise ValueError("f_0b4a4 non e' quella attesa: immagine diversa?")
    imm[o:o + len(ORIGINALE)] = NUOVO + b'\x4e\x71' * ((len(ORIGINALE) - len(NUOVO)) // 2)
    return imm
