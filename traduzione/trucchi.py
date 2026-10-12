#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
trucchi.py - i trucchi nelle versioni Amiga (floppy e WHDLoad), scelti
all'avvio. Sono gli stessi delle mod del port (rockstar_mods.c).

    1  soldi infiniti      i soldi (8 cifre decimali a $123CA) tornano a
                           999.999 e il flag del saldo negativo ($128BD) a 0
    2  trucco originale    il conto dei tasti giusti di C O L B O P S ($BB8D)
                           a 7: F7, F8 e F9 funzionano subito
    3  sempre primi        singolo ($128C4, migliore $1289C, settimane $128C6)
                           e album ($128C5) al primo posto, se sono usciti
    4  star contente       la contentezza delle star ($129B7, 4 byte; 0 e $FF
                           = posto vuoto) non scende sotto 20: prima delle
                           serate dei tour niente richieste ne' partenze
    5  stadio pieno        i fattori del prezzo dei biglietti ($12161, 9 6 4 2
                           1) diventano 9 8 6 5 4: una band al top riempie lo
                           stadio anche a 15 e 20 sterline

DOVE GIRA
    La routine sta nel blocco esteso, dopo l'accordo. Il gioco la raggiunge
    da $B4A4, la pausa di un passaggio del pennello (patch_velocita.py), che
    chiama di continuo: le ultime tre istruzioni ($B4B8: moveq #0,d0;
    movea.l (a7)+,a5; rts) diventano "jmp trucchi" (lo scrive il post-codice,
    come gli agganci dell'accordo) e la routine, finito il suo lavoro, le
    esegue lei. Senza post-codice (piano B dell'eseguibile) restano quelle
    originali e niente trucchi.

    I flag sono cinque byte in coda alla routine: li scrive il menu del
    caricatore (floppy) o lo slave dai CUSTOM1-5 (WHDLoad). Nel port restano 0.
    La routine usa solo a5 (ripresa dalla pila nella coda originale) e d0
    (che la coda azzera): gli altri registri del chiamante restano intatti.
"""
from asm68k import Asm

SITO = 0x0B4B8
ORIGINALE = bytes.fromhex('70002A5F4E75')     # moveq #0,d0; movea.l (a7)+,a5; rts
NOMI = ['Soldi infiniti', 'Trucco originale (F7 F8 F9)', 'Sempre primi in classifica',
        'Star sempre contente', 'Stadio pieno a ogni prezzo']


def verifica(imm, gioco=0x8100):
    o = SITO - gioco
    if bytes(imm[o:o + 6]) != ORIGINALE:
        raise ValueError("trucchi: a $%X non c'e' la coda della pausa attesa "
                         "(patch_velocita applicata?)" % SITO)


def codice():
    """(blob, posizione dei tre flag nel blob). L'entrata e' all'inizio."""
    a = Asm()
    a.saltoW(b'\x4B\xFA', 'flag')                   # lea flag(pc),a5  (a5 torna dalla pila)
    a.b(b'\x4A\x15')                                # tst.b (a5)
    a.salto(b'\x67', 'no_soldi')                    # beq.b
    a.b(b'\x23\xFC\x00\x00\x09\x09\x00\x01\x23\xCA')  # move.l #$00000909,$123ca
    a.b(b'\x23\xFC\x09\x09\x09\x09\x00\x01\x23\xCE')  # move.l #$09090909,$123ce  = 999.999
    a.b(b'\x42\x39\x00\x01\x28\xBD')                # clr.b $128bd
    a.eti('no_soldi')
    a.b(b'\x4A\x2D\x00\x01')                        # tst.b 1(a5)
    a.salto(b'\x67', 'no_trucco')
    a.b(b'\x13\xFC\x00\x07\x00\x00\xBB\x8D')        # move.b #7,$bb8d
    a.eti('no_trucco')
    a.b(b'\x4A\x2D\x00\x02')                        # tst.b 2(a5)
    a.salto(b'\x67', 'no_primi')
    a.b(b'\x4A\x39\x00\x01\x28\xC4')                # tst.b $128c4   singolo uscito?
    a.salto(b'\x67', 'no_singolo')
    a.b(b'\x13\xFC\x00\x01\x00\x01\x28\xC4')        # move.b #1,$128c4
    a.b(b'\x13\xFC\x00\x01\x00\x01\x28\x9C')        # move.b #1,$1289c
    a.b(b'\x13\xFC\x00\x05\x00\x01\x28\xC6')        # move.b #5,$128c6   sempre in salita
    a.eti('no_singolo')
    a.b(b'\x4A\x39\x00\x01\x28\xC5')                # tst.b $128c5   album uscito?
    a.salto(b'\x67', 'no_primi')
    a.b(b'\x13\xFC\x00\x01\x00\x01\x28\xC5')        # move.b #1,$128c5
    a.eti('no_primi')
    a.b(b'\x4A\x2D\x00\x03')                        # tst.b 3(a5)
    a.salto(b'\x67', 'no_contente')
    for i in range(4):                                  # contentezza di ogni star
        ind = (0x129B7 + i).to_bytes(4, 'big')
        a.b(b'\x10\x39' + ind)                         # move.b $129b7+i,d0
        a.salto(b'\x67', 'c%d' % i)                     # beq.b   posto vuoto
        a.b(b'\x0C\x00\x00\xFF')                     # cmpi.b #$ff,d0
        a.salto(b'\x67', 'c%d' % i)
        a.b(b'\x0C\x00\x00\x14')                     # cmpi.b #20,d0
        a.salto(b'\x64', 'c%d' % i)                     # bcc.b   gia' contenta
        a.b(b'\x13\xFC\x00\x14' + ind)               # move.b #20,$129b7+i
        a.eti('c%d' % i)
    a.eti('no_contente')
    a.b(b'\x4A\x2D\x00\x04')                        # tst.b 4(a5)
    a.salto(b'\x67', 'fine')
    for i, v in enumerate((9, 8, 6, 5, 4)):             # fattori del prezzo (indirizzo dispari:
        a.b(b'\x13\xFC\x00' + bytes([v]) + (0x12161 + i).to_bytes(4, 'big'))   # un byte alla volta)
    a.eti('fine')
    a.b(ORIGINALE)                                  # cio' che il jmp ha sostituito
    a.eti('flag')
    a.b(bytes(6))                                   # 5 flag + allineamento
    blob = a.chiudi(4)
    return blob, a.etichette['flag']


if __name__ == '__main__':
    from capstone import Cs, CS_ARCH_M68K, CS_MODE_BIG_ENDIAN
    b, f = codice()
    md = Cs(CS_ARCH_M68K, CS_MODE_BIG_ENDIAN)
    for i in md.disasm(b[:f], 0):
        print('%04x %-8s %s' % (i.address, i.mnemonic, i.op_str))
    print('flag a +%d, %d byte' % (f, len(b)))
