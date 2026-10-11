#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
patch_finestre.py - finestre di testo e impaginazione.

Le finestre di testo sono nella tabella a $11AF6, 4 byte ciascuna:
riga iniziale, colonna iniziale, riga finale, colonna finale (esclusa).
f_0d7e4 le legge dal numero in d6 passato a f_0d638.

    $3A  manifesto del concerto, messaggio #152 (a $0C804)
         EN "PRESENT" (7) in riga 5, colonne 17-25: 8 caratteri.
         IT "PRESENTANO" (10) va a capo e si vedeva solo "NO".
         Diventa colonne 16-26: 10 caratteri, stesso centro. La finestra
         $3A la usa solo quel messaggio. (Solo italiano: FINESTRE.)

MANIFESTO DEL CONCERTO (tutte e due le lingue: MANIFESTO)
    Il riquadro bianco delle foto ($C50E, liste a $C840: finestre $65-$68
    per 1-4 star) parte dalla riga 6 ma il suo bordo sale di qualche pixel
    nella riga 5, dove c'e' PRESENTANO / PRESENT, e ne taglia il fondo delle
    lettere (succede anche all'originale). Riquadro e foto scendono di una
    riga: finestre $65-$68 dalle righe 6-14 alle 7-15, foto dalla riga 7
    alla 8 (il byte alto di "move.w #$700,d4" a $C7C4). Sotto, il nome
    della band comincia alla riga 15: c'e' posto. Finestre e codice li usa
    solo il manifesto. La finestra $32 (nome della band) va dalle colonne
    6-20 alle 5-21, per la routine che centra le scritte (accordo.py).
"""

GIOCO = 0x8100
TABELLA = 0x11AF6

#            finestra  originale            nuova
# (10 colonne non bastano a una parola di 10: il testo va a capo quando tocca
# il bordo, e sotto non c'e' una riga. 11 colonne, centrate sul riquadro.)
FINESTRE = [(0x3A, bytes([5, 17, 6, 25]), bytes([5, 15, 6, 26]))]

MANIFESTO_FINESTRE = [
    (0x65, bytes([6, 16, 14, 23]), bytes([7, 16, 15, 23])),
    (0x66, bytes([6, 13, 14, 27]), bytes([7, 13, 15, 27])),
    (0x67, bytes([6, 8, 14, 31]), bytes([7, 8, 15, 31])),
    (0x68, bytes([6, 5, 14, 35]), bytes([7, 5, 15, 35])),
    # nome della band: una colonna in piu' per lato (5-21), cosi' la routine
    # che centra (accordo.py, CENTRATE) ha posto per il rientro anche nelle
    # righe di 12-13 caratteri; il centro dello schermo non cambia
    (0x32, bytes([15, 6, 21, 20]), bytes([15, 5, 21, 21])),
]
#              indirizzo  originale               nuovo
MANIFESTO_CODICE = [(0x0C7C4, bytes.fromhex('383C0700'), bytes.fromhex('383C0800'))]   # move.w #$800,d4


def _metti(imm, ind, orig, nuova, cosa):
    o = ind - GIOCO
    attuale = bytes(imm[o:o + len(orig)])
    if attuale == nuova:
        return
    if attuale != orig:
        raise ValueError("%s a $%X non e' quello atteso: immagine diversa?" % (cosa, ind))
    imm[o:o + len(nuova)] = nuova


def applica(imm):
    """imm: bytearray dell'immagine (offset 0 = $8100). La modifica sul posto.
    Accetta anche un'immagine gia' corretta."""
    for n, orig, nuova in FINESTRE + MANIFESTO_FINESTRE:
        _metti(imm, TABELLA + 4 * n, orig, nuova, 'finestra $%02X' % n)
    for ind, orig, nuova in MANIFESTO_CODICE:
        _metti(imm, ind, orig, nuova, 'codice')
    return imm
