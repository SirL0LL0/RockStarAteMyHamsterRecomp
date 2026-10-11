#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
build_whdload.py - installazione WHDLoad con la versione estesa decrunchata.

    python build_whdload.py [cartella_uscita]

COME FUNZIONA
    WHDLoad da' al gioco 512K di chip a partire dall'indirizzo 0: il gioco
    gira ai suoi indirizzi originali, senza rilocazioni e senza decompressione.

        rockstar.img   l'immagine decrunchata, caricata a $8100
                       (correzione della velocita' gia' applicata)
        rockstar.ext   post-codice + tabella estesa + accordo, caricato nella
                       memoria di espansione (ExpMem): il post-codice, lo
                       stesso dell'eseguibile con loader, collega al gioco le
                       basi della tabella estesa e gli agganci dell'accordo
        RockStar.slave carica i due file, chiama il post-codice, salta a $8100

    Lo slave aggancia la lettura della tastiera del gioco ($B9DE) per il tasto
    di uscita (F10) e per allungare l'handshake della tastiera sulle CPU
    veloci (deve durare almeno 85 us).
"""
import os
import struct
import sys

import build_ram as br
import patch_velocita
from asm68k import Asm

QUI = os.path.dirname(os.path.abspath(__file__))

BASEMEM = 0x80000
EXPMEM = 0x10000
QUITKEY = 0x59                   # F10
FLAGS = 0x0002 | 0x0004 | 0x1000  # NoError | EmulTrap | ClearMem
TASTIERA = 0xB9DE                # move.b $bfec01.l,d0 nel gestore livello 2

R_ABORT, R_LOADFILE, R_FLUSHCACHE = 4, 8, 32
TDREASON_OK = -1


def file_dati(imm, est_voci, comp_voci, generi=None, info=None):
    """(immagine, ext): l'immagine come la vuole lo slave e il blocco ExpMem.
    info (dict, facoltativo) riceve le misure del blocco: off_tab (inizio della
    tabella estesa nel blocco), len_tab (tabella con il riempimento),
    off_str (inizio della parte stringhe nella tabella)."""
    import accordo
    imm = bytearray(imm)
    patch_velocita.applica(imm)
    import patch_finestre
    patch_finestre.applica(imm)
    comp, _ = br.costruisci(comp_voci)
    imm[br.TAB_OFF:br.TAB_OFF + len(comp)] = comp
    imm[br.TAB_OFF + len(comp):br.TAB_FINE] = b'\xA0' * (br.TAB_FINE - br.TAB_OFF - len(comp))
    assert imm[TASTIERA - br.GIOCO:TASTIERA - br.GIOCO + 6] == bytes.fromhex('103900bfec01')
    est, off_str = br.costruisci(est_voci)
    if generi is None:
        generi = accordo.carica_generi(QUI)
    accordo.verifica_agganci(imm)
    acc_blob, acc_ent, _ = accordo.codice(generi)
    import trucchi
    trucchi.verifica(imm)
    tru_blob, tru_flag = trucchi.codice()
    acc_blob += bytes(-len(acc_blob) % 4)

    post, _, _ = br.fai_post(off_str, {k: 0 for k in acc_ent}, whdload=True, trucchi=0)
    off_tab = len(post)
    pad = (-(off_tab + len(est))) % 4
    est_pad = est + bytes(pad)
    post, q_qui, q_delta = br.fai_post(
        off_str, {k: len(est_pad) + v for k, v in acc_ent.items()}, whdload=True,
        trucchi=len(est_pad) + len(acc_blob))
    assert len(post) == off_tab
    struct.pack_into('>I', post, q_delta, off_tab - q_qui)
    ext = bytes(post) + est_pad + acc_blob + tru_blob
    if info is not None:
        info.update(off_tab=off_tab, len_tab=len(est_pad), off_str=off_str,
                    flag_trucchi=off_tab + len(est_pad) + len(acc_blob) + tru_flag)
    if len(ext) > EXPMEM:
        raise ValueError(f"rockstar.ext e' di {len(ext)} byte, ExpMem {EXPMEM}")
    return bytes(imm), ext


CUSTOM_GET = [0x88000007, 0x88000008, 0x88000009]   # WHDLTAG_CUSTOM1..3_GET
R_CONTROL = 0x34


def slave(flag_trucchi):
    """flag_trucchi: posizione dei flag dei trucchi nel blocco esteso"""
    import trucchi
    a = Asm()
    # ---- intestazione (versione 17)
    a.b(b'\x70\xFF\x4E\x75')                     # moveq #-1,d0 ; rts
    a.b(b'WHDLOADS')
    a.dc_w(17)                                    # ws_Version
    a.dc_w(FLAGS)                                 # ws_Flags
    a.dc_l(BASEMEM)                               # ws_BaseMemSize
    a.dc_l(0)                                     # ws_ExecInstall
    a.dc_w('inizio')                              # ws_GameLoader
    a.dc_w('cartella')                            # ws_CurrentDir: data/
    a.dc_w(0)                                     # ws_DontCache
    a.dc_b(0)                                     # ws_keydebug
    a.eti('keyexit'); a.dc_b(QUITKEY)             # ws_keyexit
    a.eti('expmem'); a.dc_l(EXPMEM)               # ws_ExpMem (WHDLoad ci scrive l'indirizzo)
    a.dc_w('nome')                                # ws_name
    a.dc_w('copia')                               # ws_copy
    a.dc_w('info')                                # ws_info
    a.dc_w(0)                                     # ws_kickname
    a.dc_l(0)                                     # ws_kicksize
    a.dc_w(0)                                     # ws_kickcrc
    a.dc_w('config')                              # ws_config: caselle dei trucchi

    # ---- caricatore: a0 = resload
    a.eti('inizio')
    a.b(b'\x43\xFA'); a.da_fare.append((a.pos(), 'resload', 'w', a.pos())); a.b(b'\x00\x00')  # lea resload(pc),a1
    a.b(b'\x22\x88')                              # move.l a0,(a1)
    a.b(b'\x28\x48')                              # movea.l a0,a4
    a.b(b'\x41\xFA'); a.da_fare.append((a.pos(), 'f_img', 'w', a.pos())); a.b(b'\x00\x00')    # lea f_img(pc),a0
    a.b(b'\x43\xF9').dato32(br.GIOCO)             # lea $8100,a1
    a.b(b'\x4E\xAC').b(struct.pack('>h', R_LOADFILE))   # jsr resload_LoadFile(a4)
    a.b(b'\x41\xFA'); a.da_fare.append((a.pos(), 'f_ext', 'w', a.pos())); a.b(b'\x00\x00')    # lea f_ext(pc),a0
    a.b(b'\x22\x7A'); a.da_fare.append((a.pos(), 'expmem', 'w', a.pos())); a.b(b'\x00\x00')  # movea.l expmem(pc),a1
    a.b(b'\x4E\xAC').b(struct.pack('>h', R_LOADFILE))
    # aggancio tastiera: jsr tastiera.l al posto di move.b $bfec01.l,d0
    a.b(b'\x33\xFC\x4E\xB9').dato32(TASTIERA)     # move.w #$4eb9,TASTIERA
    a.b(b'\x41\xFA'); a.da_fare.append((a.pos(), 'tastiera', 'w', a.pos())); a.b(b'\x00\x00')  # lea tastiera(pc),a0
    a.b(b'\x23\xC8').dato32(TASTIERA + 2)         # move.l a0,TASTIERA+2
    # trucchi scelti nella finestra di WHDLoad (CUSTOM1-3) -> flag nel blocco esteso
    a.b(b'\x41\xFA'); a.da_fare.append((a.pos(), 'tag', 'w', a.pos())); a.b(b'\x00\x00')     # lea tag(pc),a0
    a.b(b'\x4E\xAC').b(struct.pack('>h', R_CONTROL))   # jsr resload_Control(a4)
    a.b(b'\x22\x7A'); a.da_fare.append((a.pos(), 'expmem', 'w', a.pos())); a.b(b'\x00\x00')  # movea.l expmem(pc),a1
    a.b(b'\xD3\xFC').dato32(flag_trucchi)         # adda.l #flag,a1
    for i in range(len(CUSTOM_GET)):
        a.b(b'\x20\x3A'); a.da_fare.append((a.pos(), 'tag%d' % i, 'w', a.pos())); a.b(b'\x00\x00')  # move.l tagN(pc),d0
        a.b(b'\x56\xC0')                          # sne d0
        a.b(b'\x12\xC0')                          # move.b d0,(a1)+
    # post-codice: basi della tabella estesa e agganci dell'accordo
    a.b(b'\x20\x7A'); a.da_fare.append((a.pos(), 'expmem', 'w', a.pos())); a.b(b'\x00\x00')  # movea.l expmem(pc),a0
    a.b(b'\x4E\x90')                              # jsr (a0)
    a.b(b'\x4E\xAC').b(struct.pack('>h', R_FLUSHCACHE))
    a.b(b'\x4E\xF9').dato32(br.GIOCO)             # jmp $8100

    # ---- tastiera: sostituisce move.b $bfec01.l,d0 (d1 e' libero: il
    # gioco lo riscrive subito dopo con move.w d0,d1)
    a.eti('tastiera')
    a.b(b'\x10\x39\x00\xBF\xEC\x01')             # move.b $bfec01,d0
    a.b(b'\x2F\x00')                              # move.l d0,-(a7)
    a.b(b'\x46\x00')                              # not.b d0
    a.b(b'\xE2\x18')                              # ror.b #1,d0
    a.b(b'\xB0\x3A'); a.da_fare.append((a.pos(), 'keyexit', 'w', a.pos())); a.b(b'\x00\x00')  # cmp.b keyexit(pc),d0
    a.saltoW(b'\x67\x00', 'esci')                 # beq.w esci
    for _ in range(2):                            # almeno una riga intera: >= 64 us
        a.b(b'\x12\x39\x00\xDF\xF0\x06')         # move.b $dff006,d1
        n = 'r%d' % a.pos(); a.eti(n)
        a.b(b'\xB2\x39\x00\xDF\xF0\x06')         # cmp.b $dff006,d1
        a.salto(b'\x67', n)                        # beq.b n
    a.b(b'\x20\x1F')                              # move.l (a7)+,d0
    a.b(b'\x4E\x75')                              # rts
    a.eti('esci')
    a.b(b'\x2F\x3C').dato32(TDREASON_OK & 0xFFFFFFFF)   # move.l #TDREASON_OK,-(a7)
    a.b(b'\x20\x7A'); a.da_fare.append((a.pos(), 'resload', 'w', a.pos())); a.b(b'\x00\x00')  # movea.l resload(pc),a0
    a.b(b'\x4E\xE8').b(struct.pack('>h', R_ABORT))      # jmp resload_Abort(a0)

    while a.pos() % 4: a.b(b'\x4E\x71')
    a.eti('resload'); a.dc_l(0)
    a.eti('tag')
    for i, t in enumerate(CUSTOM_GET):
        a.dc_l(t); a.eti('tag%d' % i); a.dc_l(0)
    a.dc_l(0)                                     # TAG_DONE
    a.eti('config')
    a.stringa(';'.join('C%d:B:%s' % (i + 1, n) for i, n in enumerate(trucchi.NOMI)))
    a.eti('f_img'); a.stringa('rockstar.img')
    a.eti('f_ext'); a.stringa('rockstar.ext')
    a.eti('cartella'); a.stringa('data')
    a.eti('nome'); a.stringa('Rock Star Ate My Hamster (ITA)')
    a.eti('copia'); a.stringa('1989 Codemasters')
    a.eti('info'); a.stringa('Traduzione italiana: Lollo\n'
                             'Versione estesa, decrunchata\n'
                             'F10 per uscire')
    while a.pos() % 4: a.dc_b(0)    # chiudi() allinea a NOP: con lunghezza dispari non finirebbe
    corpo = a.chiudi(4)
    lw = len(corpo) // 4
    e = bytearray()
    for x in (0x3F3, 0, 1, 0, 0, lw, 0x3E9, lw): e += struct.pack('>I', x)
    e += corpo + struct.pack('>I', 0x3F2)
    return bytes(e)


NOME = 'RockStarAteMyHamsterIt'         # cartella e slave, stile Retroplay
VERSIONE = '1.0'
ARCHIVIO = f'RockStarAteMyHamster_v{VERSIONE}_It.lha'

README = f"""Rock Star Ate My Hamster - traduzione italiana
==============================================

Gioco originale: (c) 1989 Codemasters, di Colin Jones
Traduzione italiana: Lollo
Installazione WHDLoad v{VERSIONE}

ITALIANO
  - testo esteso, accordo di genere e numero, menu impaginati in italiano
  - il gioco gira decrunchato ai suoi indirizzi originali
  - pause uguali su 68000 e su 68020 o superiori (l'originale sulle CPU
    veloci faceva scorrere i testi troppo in fretta)
  - F10 per tornare al Workbench
  - trucchi nella finestra iniziale di WHDLoad, prima di premere Start:
    soldi infiniti, trucco originale (F7 F8 F9), sempre primi in classifica
  - richiede WHDLoad 17+ e 1MB di memoria, di cui 512K chip

ENGLISH
  Italian translation of Rock Star Ate My Hamster.
  Runs decrunched at its original addresses, extended text table,
  same timing on 68000 and faster CPUs. Quit key: F10.
  Requires WHDLoad 17+ and 1MB of memory (512K chip).

HISTORY
  v{VERSIONE} - prima versione / first release
"""


def installazione(imm, info=None):
    """i file dell'installazione: [(percorso con '/', byte)]. Le icone sono
    le nostre (icone.py)."""
    import icone
    info = {} if info is None else info
    img, ext = file_dati(imm, br.carica(os.path.join(QUI, 'rockstar_text_table_ESTESA.json')),
                         br.carica(os.path.join(QUI, 'rockstar_text_table_ITA.json')), info=info)
    return [
        (f'{NOME}.info', icone.cassetto()),
        (f'{NOME}/data/rockstar.ext', ext),
        (f'{NOME}/data/rockstar.img', img),
        (f'{NOME}/ReadMe', README.encode('latin1')),
        (f'{NOME}/ReadMe.info', icone.leggimi()),
        (f'{NOME}/{NOME}.info', icone.gioco(f'{NOME}.slave')),
        (f'{NOME}/{NOME}.slave', slave(info['flag_trucchi'])),
    ]


def main():
    import lha_amiga
    import percorsi
    out = sys.argv[1] if len(sys.argv) > 1 else os.path.join(percorsi.USCITE, 'WHDLoad_RockStar')
    voci = installazione(percorsi.immagine_ita())
    for p, dati in voci:                       # anche scompattato, per provarlo
        f = os.path.join(out, *p.split('/'))
        os.makedirs(os.path.dirname(f), exist_ok=True)
        open(f, 'wb').write(dati)
    arch = os.path.join(out, ARCHIVIO)
    for p, m, n in lha_amiga.scrivi_lha(arch, voci):
        print(f"  {m.decode()} {n:7d}  {p}")
    print(f"{ARCHIVIO}: {os.path.getsize(arch)} byte")


if __name__ == '__main__':
    main()
