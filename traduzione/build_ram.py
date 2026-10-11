#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
build_ram.py - eseguibile che si sposta in RAM chiesta al sistema.

    python3 build_ram.py rockstar_ita_img.bin \
            tabella_compatta.json tabella_estesa.json uscita.bin

IL PROBLEMA CHE RISOLVE
    Il decompressore scrive all'indietro da $8100+oLen verso il basso e legge
    all'indietro dai dati compressi, senza mai controllare che i due puntatori
    non si incontrino. Funziona solo se AmigaDOS ha caricato l'hunk abbastanza
    in basso: il conto dice sotto $8000 circa. Con sola chip RAM, e tanta chip
    libera, l'hunk finisce in alto e la decompressione divora la sorgente
    mentre la sta leggendo. Ecco perche' il gioco partiva solo dove c'era slow
    o fast RAM: li' AmigaDOS metteva l'hunk lontano dalla zona pericolosa.

LA SOLUZIONE
    Non allargare il margine: togliere la dipendenza. Lo stub chiede memoria
    al sistema con MEMF_ANY, ci copia l'intero pacchetto (se stesso, i dati
    compressi e la tabella estesa) e ci salta dentro. La sorgente della
    decompressione sta allora dove l'abbiamo messa noi, sopra $80000, e la
    collisione non puo' avvenire su nessuna configurazione.

    Il decompressore (s404_stub.py, nostro: prima c'era lo stub della
    versione su file) raggiunge il proprio header S404 con indirizzamento
    PC-relativo, quindi dentro la copia funziona identico, senza patch.

    Il pacchetto contiene anche il post-codice, che gira dopo la decompressione
    e riscrive le cinque basi perche' puntino alla tabella estesa. Sta nel
    blocco allocato, quindi sopravvive alla decompressione.

PIANO B
    Se non c'e' memoria libera sopra $80000, il blocco viene restituito con
    FreeMem, il salto finale dello stub viene riportato al "jmp $8100"
    originale e il gioco parte come l'inglese, usando la tabella compatta che
    sta dentro l'immagine.
"""

import json
import struct
import sys

import s404_compress
from asm68k import Asm

GIOCO    = 0x8100
TAB_MEM  = 0xEA57
TAB_OFF  = 26967
TAB_FINE = 37758
LIMITE   = 0x80000        # sopra l'immagine ($71000) e sopra lo schermo ($7EB46)

SITI_G_ABS = [GIOCO + 0x762, GIOCO + 0x892]
SITO_S_ABS = GIOCO + 0x786
SITO_G_PC  = GIOCO + 0x55E4
SITO_S_PC  = GIOCO + 0x560A
PTR_G, PTR_S = TAB_MEM + 1, TAB_MEM + 5   # NON a $EA57: li' c'e' il terminatore
                                          # dell'ultimo script


def codifica(s):
    b = bytearray()
    for i, c in enumerate(s):
        v = ord(c) & 0x7F
        if i == len(s) - 1: v |= 0x80
        b.append(v)
    return bytes(b)


def costruisci(voci):
    out = bytearray(); off_str = None
    gruppi = [v for v in voci if v['type'] == 'GROUP']
    for v in voci:
        if v['type'] == 'GROUP':
            out.append(0xFF)
            if v is gruppi[-1]: off_str = len(out)
            out.append(len(v['items']) - 1)
            for it in v['items']: out += codifica(str(it).upper())
        else:
            out += codifica(str(v['text']).upper())
    return bytes(out), off_str


def carica(p):
    r = json.load(open(p, encoding='utf-8'))
    return r['entries'] if isinstance(r, dict) else r


def fai_post(off_str, acc=None, whdload=False, trucchi=None):
    """Gira dopo la decompressione, dal blocco allocato. Ricava l'indirizzo
    della tabella dal proprio PC e riscrive le cinque basi.

    acc = {entrata: offset rispetto alla tabella} della routine di accordo;
    il post-codice scrive gli agganci (accordo.AGGANCI) che la chiamano.
    Vedi accordo.py.
    trucchi = offset della routine dei trucchi rispetto alla tabella: il
    post-codice scrive "jmp" a trucchi.SITO (vedi trucchi.py)."""
    p = bytearray(); w = p.extend
    if COLORI: w(b'\x33\xFC\x00\xF0\x00\xDF\xF1\x80')   # diagnosi: verde
    w(b'\x41\xFA\x00\x00'); q_qui = len(p) - 2     # lea 0(pc),a0
    w(b'\xD1\xFC\x00\x00\x00\x00'); q_delta = len(p) - 4   # adda.l #tab-qui,a0
    w(b'\x20\x08')                                 # move.l a0,d0
    w(b'\x22\x00\x52\x81')                         # move.l d0,d1 ; addq.l #1,d1
    for a in SITI_G_ABS + [PTR_G]:
        w(b'\x23\xC1' + struct.pack('>I', a))      # move.l d1,abs.l
    w(b'\x22\x00')
    w(b'\x06\x81' + struct.pack('>I', off_str))    # addi.l #off_str,d1
    for a in [SITO_S_ABS, PTR_S]:
        w(b'\x23\xC1' + struct.pack('>I', a))
    for indir, ptr in ((SITO_G_PC, PTR_G), (SITO_S_PC, PTR_S)):
        w(b'\x33\xFC\x26\x7A' + struct.pack('>I', indir))
        w(b'\x33\xFC' + struct.pack('>h', ptr - (indir + 2)) + struct.pack('>I', indir + 2))
    if acc:
        # acc: entrata -> spostamento dalla tabella. Per ogni aggancio:
        # move.l a0,d2; addi.l #delta,d2; move.w #$4EB9,ind; move.l d2,ind+2
        # e i nop che completano la lunghezza originale
        import accordo
        for ind, nome, n, _ in accordo.AGGANCI:
            w(b'\x24\x08')
            w(b'\x06\x82' + struct.pack('>i', acc[nome]))
            w(b'\x33\xFC\x4E\xB9' + struct.pack('>I', ind))
            w(b'\x23\xC2' + struct.pack('>I', ind + 2))
            coda = accordo.riempimento(ind, nome, n)   # nop, o il bra.b per 'nome'
            for k in range(0, len(coda), 2):
                w(b'\x33\xFC' + coda[k:k + 2] + struct.pack('>I', ind + 6 + k))
    if trucchi is not None:
        import trucchi as tr
        # move.l a0,d2; addi.l #delta,d2; move.w #$4EF9,sito; move.l d2,sito+2
        w(b'\x24\x08')
        w(b'\x06\x82' + struct.pack('>i', trucchi))
        w(b'\x33\xFC\x4E\xF9' + struct.pack('>I', tr.SITO))
        w(b'\x23\xC2' + struct.pack('>I', tr.SITO + 2))
    if whdload:
        w(b'\x4E\x75')                             # rts: cache e salto li fa lo slave
    else:
        w(b'\x2C\x78\x00\x04\x0C\x6E\x00\x25\x00\x14\x65\x04\x4E\xAE\xFD\x84')
        w(b'\x4E\xF9' + struct.pack('>I', GIOCO))
    while len(p) % 4: w(b'\x4E\x71')
    return p, q_qui, q_delta


def fai_pre(tot):
    """Cerca un blocco DAVVERO libero in alto, e ci copia tutto.

    Non basta guardare mh_Upper: la cima di una regione e' quasi sempre gia'
    occupata, e AllocAbs li' fallisce. Bisogna scorrere la lista dei chunk
    liberi di ogni MemHeader (mh_First -> MemChunk {mc_Next, mc_Bytes}) e
    scegliere il chunk libero che finisce piu' in alto ed e' grande abbastanza.
    Non lo si alloca: lo si prende dopo aver spento il sistema (vedi sotto).

    Se nessun chunk libero arriva sopra $80000 resta il ripiego.

    Prima di tutto pero': se AmigaDOS ha gia' caricato l'hunk sopra $80000
    (tipico A500 512K chip + 512K slow) il pacchetto e' gia' al sicuro e lo
    si usa dov'e', senza chiedere altri 250K che li' non ci sono.
    Dopo ogni scrittura di codice si svuotano le cache (68040/060).
    """
    a = Asm()
    a.saltoW(b'\x61\x00', 'menu')                 # bsr.w menu   trucchi, col sistema acceso
    a.b(b'\x2C\x78\x00\x04')                     # movea.l $4.w,a6
    a.b(b'\x41\xFA\x00\x00'); q0 = a.pos() - 2       # lea 0(pc),a0
    a.b(b'\xD1\xFC').rif32('pacchetto', q0)       # adda.l #pkg-qui,a0
    a.b(b'\xB1\xFC').dato32(LIMITE)               # cmpa.l #$80000,a0
    a.salto(b'\x65', 'cerca')                      # bcs.b cerca
    a.b(b'\x24\x48')                              # movea.l a0,a2   sul posto
    a.saltoW(b'\x60\x00', 'avvia')                # bra.w avvia
    a.eti('cerca')
    a.b(b'\x45\xEE\x01\x42')                     # lea $142(a6),a2   MemList
    a.b(b'\x20\x52')                              # movea.l (a2),a0   primo header
    a.b(b'\x78\x00')                              # moveq #0,d4       migliore
    a.eti('hdr')
    a.b(b'\x22\x50')                              # movea.l (a0),a1   ln_Succ
    a.b(b'\x20\x09')                              # move.l a1,d0  (0 = era la sentinella)
    a.salto(b'\x67', 'fine_hdr')                   # beq.b fine_hdr
    a.b(b'\x26\x68\x00\x10')                     # movea.l $10(a0),a3  mh_First
    a.eti('chunk')
    a.b(b'\x20\x0B')                              # move.l a3,d0
    a.salto(b'\x67', 'fine_chunk')                 # beq.b fine_chunk
    a.b(b'\x22\x2B\x00\x04')                     # move.l $4(a3),d1   mc_Bytes
    a.b(b'\x0C\x81').dato32(tot + 8)              # cmpi.l #tot+8,d1
    a.salto(b'\x65', 'prossimo')                   # bcs.b prossimo
    a.b(b'\x20\x0B')                              # move.l a3,d0
    a.b(b'\xD0\x81')                              # add.l d1,d0        fine chunk
    a.b(b'\x04\x80').dato32(tot)                  # subi.l #tot,d0
    a.b(b'\x02\x80\xFF\xFF\xFF\xF8')            # andi.l #-8,d0
    a.b(b'\xB0\x84')                              # cmp.l d4,d0
    a.salto(b'\x63', 'prossimo')                   # bls.b prossimo
    a.b(b'\x28\x00')                              # move.l d0,d4
    a.eti('prossimo')
    a.b(b'\x26\x53')                              # movea.l (a3),a3    mc_Next
    a.saltoW(b'\x60\x00', 'chunk')                # bra.w chunk
    a.eti('fine_chunk')
    a.b(b'\x20\x49')                              # movea.l a1,a0
    a.saltoW(b'\x60\x00', 'hdr')                  # bra.w hdr
    a.eti('fine_hdr')
    a.b(b'\x20\x04')                              # move.l d4,d0
    a.b(b'\x0C\x80').dato32(LIMITE)               # cmpi.l #$80000,d0
    a.saltoW(b'\x65\x00', 'ripiego')              # bcs.w ripiego
    # Niente AllocAbs/AllocMem: in 1.3 AllocAbs fallisce proprio sul blocco
    # in fondo a un chunk e MEMF_REVERSE non esiste. Il gioco non torna mai
    # al sistema: si spegne tutto e il chunk libero e' semplicemente nostro.
    a.b(SPEGNI)
    a.b(b'\x22\x40')                              # movea.l d0,a1   destinazione
    a.b(b'\x24\x49')                              # movea.l a1,a2   ricorda
    a.b(b'\x41\xFA\x00\x00'); qui = a.pos() - 2      # lea 0(pc),a0
    a.b(b'\xD1\xFC').rif32('pacchetto', qui)      # adda.l #pkg-qui,a0
    a.b(b'\x20\x3C').dato32(tot)                  # move.l #tot,d0
    a.b(b'\x12\xD8\x53\x80\x66\xFA')            # copia
    a.eti('avvia')
    a.b(CACHE)
    a.b(SPEGNI)
    if COLORI: a.b(b'\x33\xFC\x0F\x00\x00\xDF\xF1\x80')   # diagnosi: rosso
    a.b(b'\x2E\x4A')                              # movea.l a2,a7
    a.b(b'\xDF\xFC').dato32(tot)                  # adda.l #tot,a7   pila in coda
    a.b(b'\x20\x4A')                              # movea.l a2,a0
    a.b(b'\xD1\xFC').dato32(0)                    # adda.l #off_stub,a0 (dopo)
    pos_stub = a.pos() - 4
    a.b(b'\x4E\xD0')                              # jmp (a0)
    a.eti('ripiego')
    a.b(b'\x41\xFA\x00\x00'); qui2 = a.pos() - 2
    a.b(b'\xD1\xFC').rif32('jmp_stub', qui2)      # adda.l #jmp-qui,a0
    a.b(b'\x30\xFC\x4E\xF9')                     # move.w #$4EF9,(a0)+
    a.b(b'\x20\xBC').dato32(GIOCO)                # move.l #$8100,(a0)
    a.b(b'\x45\xFA\x00\x00'); qui3 = a.pos() - 2     # lea 0(pc),a2
    a.b(b'\xD5\xFC').rif32('stub_hunk', qui3)     # adda.l #stub-qui,a2
    a.b(CACHE)
    a.b(SPEGNI)
    if COLORI: a.b(b'\x33\xFC\x0F\xF0\x00\xDF\xF1\x80')   # diagnosi: giallo
    a.b(b'\x4F\xFA\x00\x00'); qui4 = a.pos() - 2     # lea 0(pc),a7
    a.b(b'\xDF\xFC').rif32('pacchetto', qui4)     # adda.l #pkg-qui,a7
    a.b(b'\xDF\xFC').dato32(tot)                  # adda.l #tot,a7
    a.b(b'\x4E\xD2')                              # jmp (a2)
    menu_trucchi(a)
    return a, pos_stub


def menu_trucchi(a):
    """Selettore dei trucchi: una finestra Intuition sul Workbench (va dal
    Kickstart 1.3), tre caselle da cliccare col mouse e il pulsante GIOCA;
    Invio o la chiusura della finestra fanno partire subito. I flag stanno nel
    pacchetto (etichetta trucchi_flag, vedi trucchi.py) e viaggiano con lui.
    Le strutture (NewWindow, Gadget, Border, IntuiText) hanno puntatori
    assoluti: li riloca AmigaDOS (a.rilocare -> HUNK_RELOC32)."""
    import trucchi
    import struct as st
    n = len(trucchi.NOMI)
    LARGO, ALTO = 420, 50 + 18 * n + 36 + 30
    def pari():
        while a.pos() % 2: a.dc_b(0)

    a.eti('menu')
    a.b(b'\x48\xE7\xFF\xFE')                     # movem.l d0-d7/a0-a6,-(a7)
    a.b(b'\x2C\x78\x00\x04')                     # movea.l $4.w,a6
    a.saltoW(b'\x43\xFA', 's_int')                # lea s_int(pc),a1
    a.b(b'\x70\x00')                              # moveq #0,d0
    a.b(b'\x4E\xAE\xFD\xD8')                     # jsr -552(a6)  OpenLibrary
    a.b(b'\x4A\x80')                              # tst.l d0
    a.saltoW(b'\x67\x00', 's_esci')               # beq.w
    a.b(b'\x2A\x40')                              # movea.l d0,a5   intuition
    a.b(b'\x2C\x4D')                              # movea.l a5,a6
    a.saltoW(b'\x41\xFA', 's_nw')                 # lea s_nw(pc),a0
    a.b(b'\x4E\xAE\xFF\x34')                     # jsr -204(a6)  OpenWindow
    a.b(b'\x2E\x00')                              # move.l d0,d7   finestra
    a.saltoW(b'\x67\x00', 's_lib')                # beq.w
    a.b(b'\x20\x47')                              # movea.l d7,a0
    a.b(b'\x20\x68\x00\x32')                     # movea.l $32(a0),a0   RPort
    a.saltoW(b'\x43\xFA', 's_testa')              # lea s_testa(pc),a1
    a.b(b'\x70\x00\x72\x00')                     # moveq #0,d0 ; moveq #0,d1
    a.b(b'\x4E\xAE\xFF\x28')                     # jsr -216(a6)  PrintIText
    a.eti('s_attendi')
    a.b(b'\x20\x47')                              # movea.l d7,a0
    a.b(b'\x20\x68\x00\x56')                     # movea.l $56(a0),a0   UserPort
    a.b(b'\x2C\x08')                              # move.l a0,d6
    a.b(b'\x2C\x78\x00\x04')                     # movea.l $4.w,a6
    a.b(b'\x4E\xAE\xFE\x80')                     # jsr -384(a6)  WaitPort
    a.eti('s_msg')
    a.b(b'\x20\x46')                              # movea.l d6,a0
    a.b(b'\x4E\xAE\xFE\x8C')                     # jsr -372(a6)  GetMsg
    a.b(b'\x4A\x80')                              # tst.l d0
    a.salto(b'\x67', 's_attendi')                 # beq.b
    a.b(b'\x22\x40')                              # movea.l d0,a1
    a.b(b'\x24\x29\x00\x14')                     # move.l $14(a1),d2   Class
    a.b(b'\x38\x29\x00\x18')                     # move.w $18(a1),d4   Code
    a.b(b'\x26\x29\x00\x1C')                     # move.l $1c(a1),d3   IAddress
    a.b(b'\x4E\xAE\xFE\x86')                     # jsr -378(a6)  ReplyMsg
    a.b(b'\x0C\x82\x00\x00\x02\x00')             # cmpi.l #CLOSEWINDOW,d2
    a.salto(b'\x67', 's_fine')
    a.b(b'\x0C\x82\x00\x20\x00\x00')             # cmpi.l #VANILLAKEY,d2
    a.salto(b'\x66', 's_gad')
    a.b(b'\x0C\x44\x00\x0D')                     # cmpi.w #13,d4   Invio
    a.salto(b'\x67', 's_fine')
    a.salto(b'\x60', 's_msg')
    a.eti('s_gad')
    a.b(b'\x0C\x82\x00\x00\x00\x40')             # cmpi.l #GADGETUP,d2
    a.salto(b'\x66', 's_msg')
    a.saltoW(b'\x41\xFA', 's_gioca')              # lea s_gioca(pc),a0
    a.b(b'\xB6\x88')                              # cmp.l a0,d3
    a.salto(b'\x66', 's_msg')
    a.eti('s_fine')
    a.b(b'\x45\xFA\x00\x00'); q = a.pos() - 2         # lea 0(pc),a2
    a.b(b'\xD5\xFC').rif32('trucchi_flag', q)    # adda.l #flag-qui,a2
    for i in range(n):
        a.saltoW(b'\x41\xFA', 's_g%d' % i)        # lea s_gN(pc),a0
        a.b(b'\x08\x28\x00\x07\x00\x0D')         # btst #7,13(a0)   SELECTED
        a.b(b'\x56\xDA')                          # sne (a2)+
    a.b(b'\x2C\x4D')                              # movea.l a5,a6
    a.b(b'\x20\x47')                              # movea.l d7,a0
    a.b(b'\x4E\xAE\xFF\xB8')                     # jsr -72(a6)  CloseWindow
    a.eti('s_lib')
    a.b(b'\x22\x4D')                              # movea.l a5,a1
    a.b(b'\x2C\x78\x00\x04')                     # movea.l $4.w,a6
    a.b(b'\x4E\xAE\xFE\x62')                     # jsr -414(a6)  CloseLibrary
    a.eti('s_esci')
    a.b(b'\x4C\xDF\x7F\xFF')                     # movem.l (a7)+,d0-d7/a0-a6
    a.b(b'\x4E\x75')                              # rts

    # ---- dati
    pari(); a.eti('s_nw')                          # NewWindow
    a.b(st.pack('>hhhh', 110, 25, LARGO, ALTO)).dc_b(0).dc_b(1)
    a.dc_l(0x40 | 0x200 | 0x200000)               # GADGETUP | CLOSEWINDOW | VANILLAKEY
    a.dc_l(0x2 | 0x4 | 0x8 | 0x1000 | 0x20000)    # DRAG DEPTH CLOSE ACTIVATE NOCAREREFRESH
    a.puntatore('s_g0'); a.dc_l(0); a.puntatore('s_titolo'); a.dc_l(0); a.dc_l(0)
    a.b(st.pack('>hhhhh', 0, 0, 0, 0, 1))         # WBENCHSCREEN
    for i in range(n):                             # Gadget: casella + nome, si accende col clic
        pari(); a.eti('s_g%d' % i)
        a.puntatore('s_g%d' % (i + 1) if i + 1 < n else 's_gioca')
        a.b(st.pack('>hhhh', 20, 32 + 18 * i, LARGO - 40, 12))
        a.b(st.pack('>hhh', 0x2, 0x100 | 0x2, 1))      # GADGHIMAGE, TOGGLESELECT|GADGIMMEDIATE, BOOL
        a.puntatore('s_spenta'); a.puntatore('s_accesa'); a.puntatore('s_t%d' % i)
        a.dc_l(0); a.dc_l(0); a.dc_w(i); a.dc_l(0)
    pari(); a.eti('s_gioca')                        # Gadget: GIOCA
    a.dc_l(0)
    a.b(st.pack('>hhhh', LARGO // 2 - 50, ALTO - 26, 100, 16))
    a.b(st.pack('>hhh', 0x0, 0x1, 1))                # GADGHCOMP, RELVERIFY, BOOL
    a.puntatore('s_b_tasto'); a.dc_l(0); a.puntatore('s_t_gioca')
    a.dc_l(0); a.dc_l(0); a.dc_w(9); a.dc_l(0)
    def bordo(nome, xy, penna, dopo):
        pari(); a.eti(nome)
        a.b(st.pack('>hh', 0, 1)).dc_b(penna).dc_b(0).dc_b(0).dc_b(len(xy) // 2)
        a.puntatore(nome + '_xy')
        if dopo: a.puntatore(dopo)
        else: a.dc_l(0)
        a.eti(nome + '_xy'); a.b(st.pack('>%dh' % len(xy), *xy))
    scatola = [0, 0, 15, 0, 15, 9, 0, 9, 0, 0]
    bordo('s_spenta', scatola, 1, 's_spenta_x1')    # spenta: casella e X cancellata
    bordo('s_spenta_x1', [3, 2, 12, 7], 0, 's_spenta_x2')
    bordo('s_spenta_x2', [12, 2, 3, 7], 0, None)
    bordo('s_accesa', scatola, 1, 's_accesa_x1')    # accesa: casella con la X
    bordo('s_accesa_x1', [3, 2, 12, 7], 3, 's_accesa_x2')
    bordo('s_accesa_x2', [12, 2, 3, 7], 3, None)
    bordo('s_b_tasto', [0, 0, 99, 0, 99, 15, 0, 15, 0, 0], 1, None)
    def testo(nome, x, y, s, dopo=None):
        pari(); a.eti(nome)
        a.dc_b(1).dc_b(0).dc_b(0).dc_b(0)          # FrontPen, BackPen, JAM1
        a.b(st.pack('>hh', x, y)); a.dc_l(0); a.puntatore(nome + '_s')
        if dopo: a.puntatore(dopo)
        else: a.dc_l(0)
        a.eti(nome + '_s'); a.stringa(s)
    testo('s_testa', 20, 16, 'Scegli i trucchi e premi GIOCA', 's_aiuto')
    y = 32 + 18 * n + 2                        # cosa fa il trucco originale, in gioco
    testo('s_aiuto', 44, y, 'F7: un milione di sterline in piu\'', 's_aiuto2')
    testo('s_aiuto2', 44, y + 11, 'F8: la band suona al massimo', 's_aiuto3')
    testo('s_aiuto3', 44, y + 22, 'F9: il pubblico piu\' numeroso')
    for i, nome in enumerate(trucchi.NOMI):
        testo('s_t%d' % i, 24, 2, nome)
    testo('s_t_gioca', 30, 4, 'GIOCA')
    a.eti('s_titolo'); a.stringa('Rock Star Ate My Hamster')
    a.eti('s_int'); a.stringa('intuition.library')
    pari()
    return

def _menu_numeri(a):
    """(vecchio menu a numeri nella finestra CLI, non piu' usato)"""
    import trucchi
    righe = ['\x0c\n',
             ' ROCK STAR ATE MY HAMSTER - traduzione italiana\n\n',
             ' TRUCCHI: scrivi i numeri da cambiare e premi INVIO\n\n']
    caselle = []
    for i, nome in enumerate(trucchi.NOMI):
        r = '  %d  [ ]  %s\n' % (i + 1, nome)
        caselle.append(sum(len(x) for x in righe) + r.index('[') + 1)
        righe.append(r)
    righe.append('\n Solo INVIO per giocare. ')
    testo = ''.join(righe).encode('latin1')

    a.eti('menu')
    a.b(b'\x48\xE7\xFF\xFE')                     # movem.l d0-d7/a0-a6,-(a7)
    a.b(b'\x2C\x78\x00\x04')                     # movea.l $4.w,a6
    a.saltoW(b'\x43\xFA', 'm_dos')                # lea m_dos(pc),a1
    a.b(b'\x70\x00')                              # moveq #0,d0
    a.b(b'\x4E\xAE\xFD\xD8')                     # jsr -552(a6)  OpenLibrary
    a.b(b'\x4A\x80')                              # tst.l d0
    a.saltoW(b'\x67\x00', 'm_esci')               # beq.w m_esci
    a.b(b'\x2C\x40')                              # movea.l d0,a6   dos
    a.b(b'\x4E\xAE\xFF\xC4')                     # jsr -60(a6)  Output
    a.b(b'\x2C\x00')                              # move.l d0,d6
    a.saltoW(b'\x67\x00', 'm_chiudi')             # beq.w m_chiudi
    a.b(b'\x4E\xAE\xFF\xCA')                     # jsr -54(a6)  Input
    a.b(b'\x2E\x00')                              # move.l d0,d7
    a.saltoW(b'\x67\x00', 'm_chiudi')             # beq.w m_chiudi
    a.b(b'\x45\xFA\x00\x00'); q = a.pos() - 2         # lea 0(pc),a2
    a.b(b'\xD5\xFC').rif32('trucchi_flag', q)    # adda.l #flag-qui,a2
    a.eti('m_ciclo')
    a.saltoW(b'\x47\xFA', 'm_testo')              # lea m_testo(pc),a3
    for i, c in enumerate(caselle):
        a.b(b'\x70\x20')                          # moveq #' ',d0
        a.b(b'\x4A\x2A' + bytes([0, i]))          # tst.b i(a2)
        a.salto(b'\x67', 'm_v%d' % i)             # beq.b
        a.b(b'\x70\x58')                          # moveq #'X',d0
        a.eti('m_v%d' % i)
        a.b(b'\x17\x40' + c.to_bytes(2, 'big'))   # move.b d0,c(a3)
    a.b(b'\x22\x06')                              # move.l d6,d1
    a.b(b'\x24\x0B')                              # move.l a3,d2
    a.b(b'\x26\x3C').dato32(len(testo))           # move.l #len,d3
    a.b(b'\x4E\xAE\xFF\xD0')                     # jsr -48(a6)  Write
    a.b(b'\x22\x07')                              # move.l d7,d1
    a.saltoW(b'\x41\xFA', 'm_buf')                # lea m_buf(pc),a0
    a.b(b'\x24\x08')                              # move.l a0,d2
    a.b(b'\x76\x20')                              # moveq #32,d3
    a.b(b'\x4E\xAE\xFF\xD6')                     # jsr -42(a6)  Read
    a.b(b'\x2A\x00')                              # move.l d0,d5   letti
    a.saltoW(b'\x6F\x00', 'm_chiudi')             # ble.w m_chiudi  fine input: si gioca
    a.saltoW(b'\x41\xFA', 'm_buf')                # lea m_buf(pc),a0
    a.b(b'\x78\x00')                              # moveq #0,d4    cambiato qualcosa?
    a.eti('m_scan')
    a.b(b'\x53\x85')                              # subq.l #1,d5
    a.salto(b'\x6B', 'm_fine_scan')               # bmi.b
    a.b(b'\x12\x18')                              # move.b (a0)+,d1
    a.b(b'\x04\x01\x00\x31')                     # subi.b #'1',d1
    a.b(b'\x0C\x01' + bytes([0, len(caselle) - 1]))   # cmpi.b #n-1,d1
    a.salto(b'\x62', 'm_scan')                    # bhi.b  (anche < '1': senza segno)
    a.b(b'\x48\x81')                              # ext.w d1
    a.b(b'\x0A\x32\x00\x01\x10\x00')             # eori.b #1,0(a2,d1.w)
    a.b(b'\x78\x01')                              # moveq #1,d4
    a.salto(b'\x60', 'm_scan')                    # bra.b
    a.eti('m_fine_scan')
    a.b(b'\x4A\x84')                              # tst.l d4
    a.saltoW(b'\x66\x00', 'm_ciclo')              # bne.w m_ciclo  ridisegna
    a.eti('m_chiudi')
    a.b(b'\x22\x4E')                              # movea.l a6,a1
    a.b(b'\x2C\x78\x00\x04')                     # movea.l $4.w,a6
    a.b(b'\x4E\xAE\xFE\x62')                     # jsr -414(a6)  CloseLibrary
    a.eti('m_esci')
    a.b(b'\x4C\xDF\x7F\xFF')                     # movem.l (a7)+,d0-d7/a0-a6
    a.b(b'\x4E\x75')                              # rts
    a.eti('m_dos'); a.stringa('dos.library')
    a.eti('m_testo'); a.stringa(testo, termina=False)
    while a.pos() % 2: a.dc_b(0)
    a.eti('m_buf'); a.b(bytes(32))


# cmpi.w #37,$14(a6) ; bcs.s +4 ; jsr _LVOCacheClearU(a6)  (sporca d0-d1/a0-a1)
CACHE = b'\x0C\x6E\x00\x25\x00\x14\x65\x04\x4E\xAE\xFD\x84'

# La decompressione scrive $8100-$71000 sopra il sistema ancora vivo. Con
# sola chip RAM (A600, A500 1MB chip, A1200 senza fast) li' ci sono pila del
# processo, copper list e dati degli interrupt: al primo VBlank, Guru.
# Quindi prima si spegne tutto (il gioco a $8100 riaccende da se'):
# move.w #$7fff,INTENA ; move.w #$7fff,INTREQ ; move.w #$7ff,DMACON
SPEGNI = (b'\x33\xFC\x7F\xFF\x00\xDF\xF0\x9A'
          b'\x33\xFC\x7F\xFF\x00\xDF\xF0\x9C'
          b'\x33\xFC\x07\xFF\x00\xDF\xF0\x96')
COLORI = bool(__import__('os').environ.get('RSAMH_COLORI'))  # sfondo per stadio
PILA = 512                # in coda al pacchetto, sopra $80000 come il resto


def costruisci_exe(imm, est_voci, comp_voci, avanzamento=None, generi=None, parti=None):
    """Costruisce l'eseguibile completo.

    imm       : l'immagine decompressa (verra' patchata con la tabella compatta)
    est_voci  : le voci della tabella estesa, che viaggia in RAM allocata
    comp_voci : le voci della tabella compatta, il piano B dentro l'immagine

    Restituisce (eseguibile, note) dove note e' un dizionario con le misure.
    parti (dict, facoltativo) riceve l'immagine compressa ('immagine') e la
    posizione e la lunghezza dei dati compressi nell'eseguibile ('blob_da',
    'blob_n'): servono al port per rifare l'eseguibile dal disco dell'utente.
    """
    imm = bytearray(imm)
    import patch_velocita
    patch_velocita.applica(imm)          # pause uguali su 68000 e 68020+
    import patch_finestre
    patch_finestre.applica(imm)          # finestre di testo larghe per l'italiano
    comp, _ = costruisci(comp_voci)
    if len(comp) > TAB_FINE - TAB_OFF:
        raise ValueError(f"la tabella compatta e' di {len(comp)} byte, "
                         f"il massimo dentro l'immagine e' {TAB_FINE - TAB_OFF}")
    imm[TAB_OFF:TAB_OFF + len(comp)] = comp
    imm[TAB_OFF + len(comp):TAB_FINE] = b'\xA0' * (TAB_FINE - TAB_OFF - len(comp))
    est, off_str = costruisci(est_voci)
    for v in comp_voci:
        testi = v['items'] if v['type'] == 'GROUP' else [v['text']]
        if any('{' in str(x) or '}' in str(x) for x in testi):
            raise ValueError("la tabella compatta contiene marcatori {..}: li capisce "
                             "solo la versione con la tabella estesa")

    # accordo di genere e numero: in coda al pacchetto, dopo la tabella
    import accordo, os
    if generi is None:
        generi = accordo.carica_generi(os.path.dirname(os.path.abspath(__file__)))
    accordo.verifica_agganci(imm)
    acc_blob, acc_ent, _ = accordo.codice(generi)
    import trucchi
    trucchi.verifica(imm)
    tru_blob, tru_flag = trucchi.codice()
    acc_blob += bytes(-len(acc_blob) % 4)             # i trucchi su un indirizzo pari

    blob, parz = s404_compress.compress(bytes(imm), avanzamento)
    pLen = len(blob) - 16
    import s404_stub
    stub, jp = s404_stub.stub()
    stub = bytearray(stub)

    # la lunghezza del post-codice non dipende dai valori: prima la misuro,
    # poi lo rifaccio con gli spostamenti veri
    post, _, _ = fai_post(off_str, {k: 0 for k in acc_ent}, trucchi=0)
    off_post_pkg = 0
    off_stub_pkg = len(post)
    off_s404_pkg = off_stub_pkg + len(stub)
    off_coda_pkg = off_s404_pkg + 16 + pLen
    off_tab_pkg  = off_coda_pkg + 4
    # la routine deve stare a un indirizzo pari: il blocco allocato e'
    # allineato a 8, quindi basta allineare l'offset nel pacchetto
    pad = (-(off_tab_pkg + len(est))) % 4
    est_pad = est + b'\x00' * pad
    post, q_qui, q_delta = fai_post(off_str, {k: len(est_pad) + v for k, v in acc_ent.items()},
                                    trucchi=len(est_pad) + len(acc_blob))
    assert len(post) == off_stub_pkg
    off_tru_pkg = off_tab_pkg + len(est_pad) + len(acc_blob)
    tot = off_tru_pkg + len(tru_blob) + PILA

    stub[jp:jp + 2] = b'\x4E\xFA'
    struct.pack_into('>h', stub, jp + 2, off_post_pkg - (off_stub_pkg + jp + 2))
    stub[jp + 4:jp + 6] = b'\x4E\x71'
    struct.pack_into('>I', post, q_delta, off_tab_pkg - (off_post_pkg + q_qui))

    a, pos_stub = fai_pre(tot)
    lungh = a.lunghezza()
    a.etichette['pacchetto'] = lungh
    a.etichette['stub_hunk'] = lungh + off_stub_pkg
    a.etichette['jmp_stub'] = lungh + off_stub_pkg + jp
    a.etichette['trucchi_flag'] = lungh + off_tru_pkg + tru_flag
    pre = bytearray(a.chiudi())
    struct.pack_into('>I', pre, pos_stub, off_stub_pkg)

    pacchetto = bytes(post) + bytes(stub) + blob + struct.pack('>H', parz) \
        + b'\x00\x00' + est_pad + acc_blob + tru_blob + bytes(PILA)
    assert len(pacchetto) == tot
    corpo = bytes(pre) + pacchetto
    while len(corpo) % 4: corpo += b'\x00'
    lw = len(corpo) // 4
    e = bytearray()
    for x in (0x3F3, 0, 1, 0, 0, lw, 0x3E9, lw): e += struct.pack('>I', x)
    e += corpo
    if a.rilocare:                                # puntatori del selettore dei trucchi
        e += struct.pack('>III', 0x3EC, len(a.rilocare), 0)
        e += b''.join(struct.pack('>I', p) for p in sorted(a.rilocare))
        e += struct.pack('>I', 0)
    e += struct.pack('>I', 0x3F2)
    note = dict(compatta=len(comp), estesa=len(est), pacchetto=tot,
                codice=len(pre) + len(post) + len(stub), eseguibile=len(e))
    if parti is not None:
        parti.update(immagine=bytes(imm), blob_da=32 + len(pre) + off_s404_pkg + 16,
                     blob_n=pLen)
    return bytes(e), note


def main():
    if len(sys.argv) != 5:
        print(__doc__); sys.exit(1)
    fimg, fcomp, fest, fout = sys.argv[1:5]
    imm = open(fimg, 'rb').read()
    e, n = costruisci_exe(imm, carica(fest), carica(fcomp))
    open(fout, 'wb').write(e)
    print(f"tabella compatta (piano B, nell'immagine): {n['compatta']} byte")
    print(f"tabella estesa (nel pacchetto):            {n['estesa']} byte")
    print(f"pacchetto copiato in RAM di sistema:       {n['pacchetto']} byte")
    print(f"codice aggiunto: {n['codice']} byte   eseguibile: {n['eseguibile']} byte")


if __name__ == '__main__':
    main()
