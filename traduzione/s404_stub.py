#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
s404_stub.py - il nostro decompressore StoneCracker S404 in 68000.

Prende il posto dello stub dell'eseguibile inglese (i 244 byte che stavano in
testa all'hunk della versione su file): cosi' l'eseguibile italiano si puo'
costruire anche dal disco IPF o ADF dell'utente, che quello stub non hanno.

Stesse regole dello stub originale:
    - l'header S404 sta subito dopo lo stub e lo si trova PC-relativo;
    - decomprime a $8100, all'indietro, come s404_decompress.py;
    - alla fine svuota le cache (68040/060) e salta: "jmp $8100", che
      l'eseguibile (build_ram.py) cambia in un salto al post-codice; la
      posizione del jmp e' il secondo valore restituito da stub().

Registri: a0 sorgente (word, all'indietro), a3 destinazione, d4 byte che
mancano, d5 efficienza, d6/d7 parola corrente e bit rimasti.
    python s404_stub.py      prova in Unicorn contro s404_decompress.py
"""
from asm68k import Asm

GIOCO = 0x8100


def stub():
    """(byte, posizione del jmp finale: 6 byte, 4EF9 00008100)"""
    a = Asm()
    a.b(b'\x45\xF9').dato32(GIOCO)                 # lea $8100,a2
    a.saltoW(b'\x43\xFA', 'hdr')                   # lea hdr(pc),a1
    a.b(b'\x20\x29\x00\x08')                       # move.l 8(a1),d0     oLen
    a.b(b'\x47\xF2\x08\x00')                       # lea 0(a2,d0.l),a3   fine dell'uscita
    a.b(b'\x28\x00')                               # move.l d0,d4
    a.b(b'\x22\x29\x00\x0C')                       # move.l 12(a1),d1    pLen
    a.b(b'\x41\xE9\x00\x10')                       # lea 16(a1),a0
    a.b(b'\xD1\xC1')                               # adda.l d1,a0        -> contatore di bit
    a.b(b'\x3E\x10\x02\x47\x00\x0F')               # move.w (a0),d7 ; andi.w #$f,d7
    a.b(b'\x3C\x20')                               # move.w -(a0),d6     parola iniziale
    a.b(b'\x3A\x20')                               # move.w -(a0),d5     efficienza

    def getb(n=None):
        if n is not None:
            a.b(bytes([0x70, n]))                  # moveq #n,d0
        a.saltoW(b'\x61\x00', 'getb')              # bsr.w getb
    OR = b'\x84\x41'                               # or.w d1,d2
    PIU544 = b'\x06\x42\x02\x20'                   # addi.w #544,d2
    PIU32 = b'\x06\x42\x00\x20'                    # addi.w #32,d2
    def copia():
        a.saltoW(b'\x60\x00', 'copia')             # bra.w copia

    a.eti('ciclo')
    a.b(b'\x4A\x84')                               # tst.l d4
    a.saltoW(b'\x6F\x00', 'fine')                  # ble.w fine
    getb(9)
    a.b(b'\x34\x01')                               # move.w d1,d2
    a.b(b'\x0C\x42\x01\x00')                       # cmpi.w #$100,d2
    a.salto(b'\x64', 'non_lett')                   # bcc.b
    a.b(b'\x17\x02\x53\x84')                       # move.b d2,-(a3) ; subq.l #1,d4
    a.salto(b'\x60', 'ciclo')
    a.eti('non_lett')
    a.b(b'\x0C\x42\x01\x3E')                       # cmpi.w #$13e,d2
    a.saltoW(b'\x67\x00', 'serie')
    a.b(b'\x0C\x42\x01\x3F')                       # cmpi.w #$13f,d2
    a.saltoW(b'\x67\x00', 'serie')
    # ---- $180-$1FF: 2-3 byte
    a.b(b'\x0C\x42\x01\x80')                       # cmpi.w #$180,d2
    a.salto(b'\x65', 'n140')                       # bcs.b
    a.b(b'\x76\x02\x08\x02\x00\x06')               # moveq #2,d3 ; btst #6,d2
    a.salto(b'\x67', 'a1')
    a.b(b'\x76\x03')                               # moveq #3,d3
    a.eti('a1')
    a.b(b'\x08\x02\x00\x05')                       # btst #5,d2
    a.salto(b'\x67', 'a2')
    a.b(b'\x02\x42\x00\x1F\x30\x05\x5B\x40\xE1\x6A')   # andi.w #$1f,d2 ; move.w d5,d0 ; subq.w #5,d0 ; lsl.w d0,d2
    getb(); a.b(OR + PIU544); copia()
    a.eti('a2')
    a.b(b'\x30\x02\x02\x40\x00\x30')               # move.w d2,d0 ; andi.w #$30,d0
    a.salto(b'\x67', 'a3')
    a.b(b'\x02\x42\x00\x0F\xD4\x42')               # andi.w #$f,d2 ; add.w d2,d2
    getb(1); a.b(OR); copia()
    a.eti('a3')
    a.b(b'\x02\x42\x00\x0F\xEB\x4A')               # andi.w #$f,d2 ; lsl.w #5,d2
    getb(5); a.b(OR + PIU32); copia()
    # ---- $140-$17F: 4-7 byte
    a.eti('n140')
    a.b(b'\x0C\x42\x01\x40')                       # cmpi.w #$140,d2
    a.salto(b'\x65', 'n120')
    a.b(b'\x36\x02\x02\x43\x00\x30\xE8\x4B\x58\x43')   # move.w d2,d3 ; andi.w #$30,d3 ; lsr.w #4,d3 ; addq.w #4,d3
    a.b(b'\x08\x02\x00\x03')                       # btst #3,d2
    a.salto(b'\x67', 'b1')
    a.b(b'\x02\x42\x00\x07\x30\x05\x57\x40\xE1\x6A')   # andi.w #7,d2 ; move.w d5,d0 ; subq.w #3,d0 ; lsl.w d0,d2
    getb(); a.b(OR + PIU544); copia()
    a.eti('b1')
    a.b(b'\x30\x02\x02\x40\x00\x0C')               # move.w d2,d0 ; andi.w #$c,d0
    a.salto(b'\x67', 'b2')
    a.b(b'\x02\x42\x00\x03\xE7\x4A')               # andi.w #3,d2 ; lsl.w #3,d2
    getb(3); a.b(OR); copia()
    a.eti('b2')
    a.b(b'\x02\x42\x00\x03\xEF\x4A')               # andi.w #3,d2 ; lsl.w #7,d2
    getb(7); a.b(OR + PIU32); copia()
    # ---- $120-$13D: 8-22 byte
    a.eti('n120')
    a.b(b'\x0C\x42\x01\x20')                       # cmpi.w #$120,d2
    a.salto(b'\x65', 'lungo')
    a.b(b'\x36\x02\x02\x43\x00\x1E\xE2\x4B\x50\x43')   # move.w d2,d3 ; andi.w #$1e,d3 ; lsr.w #1,d3 ; addq.w #8,d3
    a.b(b'\x08\x02\x00\x00')                       # btst #0,d2
    a.salto(b'\x67', 'c1')
    a.b(b'\x30\x05')                               # move.w d5,d0
    getb(); a.b(b'\x34\x01' + PIU544); copia()     # move.w d1,d2
    a.eti('c1')
    getb(6)
    a.b(b'\x34\x01\x08\x02\x00\x05')               # move.w d1,d2 ; btst #5,d2
    a.salto(b'\x67', 'c2')
    a.b(b'\x02\x42\x00\x1F')                       # andi.w #$1f,d2
    copia()
    a.eti('c2')
    a.b(b'\xE9\x4A')                               # lsl.w #4,d2
    getb(4); a.b(OR + PIU32); copia()
    # ---- $100-$11F: 23 byte e oltre
    a.eti('lungo')
    a.b(b'\x02\x42\x00\x1F\xE7\x4A')               # andi.w #$1f,d2 ; lsl.w #3,d2
    getb(3); a.b(OR)
    a.b(b'\x76\x17')                               # moveq #23,d3
    a.eti('d_ff')
    a.b(b'\x0C\x42\x00\xFF')                       # cmpi.w #$ff,d2
    a.salto(b'\x66', 'd_fine')
    a.b(b'\xD6\x42')                               # add.w d2,d3
    getb(8); a.b(b'\x34\x01')                      # move.w d1,d2
    a.salto(b'\x60', 'd_ff')
    a.eti('d_fine')
    a.b(b'\xD6\x42')                               # add.w d2,d3
    getb(7)
    a.b(b'\x34\x01\x08\x02\x00\x06')               # move.w d1,d2 ; btst #6,d2
    a.salto(b'\x67', 'd1')
    a.b(b'\x02\x42\x00\x3F\x30\x05\x5D\x40\xE1\x6A')   # andi.w #$3f,d2 ; move.w d5,d0 ; subq.w #6,d0 ; lsl.w d0,d2
    getb(); a.b(OR + PIU544); copia()
    a.eti('d1')
    a.b(b'\x08\x02\x00\x05')                       # btst #5,d2
    a.salto(b'\x67', 'd2')
    a.b(b'\x02\x42\x00\x1F')                       # andi.w #$1f,d2
    copia()
    a.eti('d2')
    a.b(b'\xE9\x4A')                               # lsl.w #4,d2
    getb(4); a.b(OR + PIU32)
    # ---- copia all'indietro: d3 byte da dist = d2 + 1
    a.eti('copia')
    a.b(b'\x02\x83\x00\x00\xFF\xFF')               # andi.l #$ffff,d3
    a.b(b'\x98\x83')                               # sub.l d3,d4
    a.b(b'\x49\xF3\x20\x01')                       # lea 1(a3,d2.w),a4
    a.b(b'\x53\x43')                               # subq.w #1,d3
    a.eti('c_byte')
    a.b(b'\x17\x24')                               # move.b -(a4),-(a3)
    a.saltoW(b'\x51\xCB', 'c_byte')                # dbra d3,c_byte
    a.saltoW(b'\x60\x00', 'ciclo')
    # ---- $13E-$13F: serie di letterali
    a.eti('serie')
    a.b(b'\xE9\x4A')                               # lsl.w #4,d2
    getb(4)
    a.b(OR + b'\x02\x42\x00\x1F\x06\x42\x00\x0E')  # or.w d1,d2 ; andi.w #$1f,d2 ; addi.w #14,d2
    a.b(b'\x76\x00\x36\x02\x98\x83\x53\x43')       # moveq #0,d3 ; move.w d2,d3 ; sub.l d3,d4 ; subq.w #1,d3
    a.eti('s_byte')
    getb(8)
    a.b(b'\x17\x01')                               # move.b d1,-(a3)
    a.saltoW(b'\x51\xCB', 's_byte')                # dbra d3,s_byte
    a.saltoW(b'\x60\x00', 'ciclo')
    # ---- d0 bit in d1.w (sporca d0)
    a.eti('getb')
    a.b(b'\x02\x86\x00\x00\xFF\xFF')               # andi.l #$ffff,d6
    a.b(b'\xBE\x40')                               # cmp.w d0,d7
    a.salto(b'\x64', 'g_ok')                       # bcc.b   bastano
    a.b(b'\xEF\xAE')                               # lsl.l d7,d6
    a.b(b'\x3C\x20')                               # move.w -(a0),d6
    a.b(b'\x90\x47\x7E\x10')                       # sub.w d7,d0 ; moveq #16,d7
    a.eti('g_ok')
    a.b(b'\x9E\x40')                               # sub.w d0,d7
    a.b(b'\xE1\xAE')                               # lsl.l d0,d6
    a.b(b'\x48\x46\x32\x06\x48\x46')               # swap d6 ; move.w d6,d1 ; swap d6
    a.b(b'\x4E\x75')                               # rts
    # ---- fine: cache, poi il salto (vedi sopra)
    a.eti('fine')
    a.b(b'\x2C\x78\x00\x04')                       # movea.l $4.w,a6
    a.b(b'\x0C\x6E\x00\x25\x00\x14\x65\x04\x4E\xAE\xFD\x84')   # CacheClearU se KS >= 37
    jp = a.pos()
    a.b(b'\x4E\xF9').dato32(GIOCO)                 # jmp $8100
    a.eti('hdr')
    return a.chiudi(), jp


def prova():
    import os, struct, s404_compress, s404_decompress
    from unicorn import Uc, UC_ARCH_M68K, UC_MODE_BIG_ENDIAN, UC_HOOK_CODE
    from unicorn.m68k_const import UC_M68K_REG_PC, UC_M68K_REG_A7, UC_CPU_M68K_M68000
    import percorsi
    imm = percorsi.immagine_ita()
    s, jp = stub()
    blob, parz = s404_compress.compress(imm)
    assert s404_decompress.decompress(blob + struct.pack('>H', parz)) == imm
    pkg = s + blob + struct.pack('>H', parz)
    uc = Uc(UC_ARCH_M68K, UC_MODE_BIG_ENDIAN)
    uc.ctl_set_cpu_model(UC_CPU_M68K_M68000)
    uc.mem_map(0, 0x100000)
    dove = 0x90000
    uc.mem_write(dove, pkg)
    uc.reg_write(UC_M68K_REG_A7, 0x8000)
    uc.emu_start(dove, dove + jp, count=200_000_000)
    pc = uc.reg_read(UC_M68K_REG_PC)
    assert pc == dove + jp, hex(pc)
    out = bytes(uc.mem_read(GIOCO, len(imm)))
    print('stub %d byte, jmp a +%d; decompressione %s' % (len(s), jp, 'GIUSTA' if out == imm else 'SBAGLIATA'))
    return out == imm


if __name__ == '__main__':
    raise SystemExit(0 if prova() else 1)
