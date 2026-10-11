#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
prepara_immagine.py - le immagini della chip RAM (italiano e inglese) e i dati
con cui l'eseguibile le ricostruisce dal disco dell'utente.

    python game/prepara_immagine.py [--traduzione CARTELLA] [--uscita FILE]

Il repository non contiene file del gioco. Si parte dalla cartella della
traduzione (default: quella che contiene il repository), che deve avere
rockstar_base.bin (la base canonica: base_canonica.py dal disco IPF o ADF),
rockstar_ita_img.bin e le tabelle dei testi.

IMMAGINE ITALIANA (--uscita, default build/rockstar_chipram.bin)
    Come lo slave WHDLoad: immagine a $8100, blocco esteso (post-codice,
    tabella estesa, accordo) a $90000; il post-codice viene eseguito in
    Unicorn e collega tabella e agganci. In testa i vettori che il gioco
    installa da se', cosi' il ricompilatore sa da dove partire:
        $00 SSP    $04 ingresso $8100    $68 livello 2 (tastiera)
        $6C livello 3 (VBlank, player musicale)    $80 trap #0 ($810A)
    Da questa nasce il C ricompilato.

IMMAGINE INGLESE (accanto: rockstar_chipram_en.bin)
    Lo stesso codice (patch di velocita', agganci dell'accordo, operandi
    collegati alla tabella estesa): un solo eseguibile per le due lingue.
    I dati della traduzione tornano quelli del disco (messaggi, tabella
    compatta, modelli dei titoli, calendario, VENDITE, crediti, finestre) e la
    tabella estesa e' quella originale con un riempimento: la parte dei gruppi
    lunga quanto l'italiana (stessa base delle stringhe) e il totale uguale
    (l'accordo resta allo stesso indirizzo). L'accordo su un testo senza
    marcatori non cambia nulla.

DATI PER L'ESEGUIBILE (build/lingue_dati.h)
    Le differenze fra la base (a $8100 in 1 MB di zeri) e ciascuna immagine,
    a tratti; per l'inglese senza la tabella estesa, che l'eseguibile rifa'
    dalla tabella del disco dell'utente (amiga_lingue.c, stesso algoritmo di
    tabella_inglese() qui sotto). Dentro ci sono solo dati nostri: traduzione,
    patch e codice aggiunto. Piu' i CRC delle due immagini.
"""
import argparse
import os
import struct
import sys
import zlib

QUI = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(QUI)

DIMENSIONE = 0x100000
GIOCO = 0x8100
EXT = 0x90000
SSP = 0x7F000
SENTINELLA = 0xFFF0
VETTORI = {0x00: SSP, 0x04: GIOCO, 0x68: 0xB95A, 0x6C: 0x132EA, 0x80: 0x810A}
N_GRUPPI = 165
N_STRINGHE = 391
RIEMPITIVO = 0x00          # dentro i gruppi: nessuno ci arriva (si conta fino a $FF)


def crc(b):
    return zlib.crc32(b) & 0xFFFFFFFF


def leggi_tabella(img, inizio):
    """la tabella originale come la scrive costruisci(): 165 gruppi
    (FF, conteggio-1, item) e 391 stringhe. -> (lunghezza, off_str)"""
    p = inizio
    off_str = None
    for g in range(N_GRUPPI):
        if img[p] != 0xFF:
            raise ValueError('tabella: gruppo %d senza $FF a +%d' % (g, p - inizio))
        p += 1
        if g == N_GRUPPI - 1:
            off_str = p - inizio
        n = img[p] + 1
        p += 1
        for _ in range(n):
            while img[p] < 0x80:
                p += 1
            p += 1
    for _ in range(N_STRINGHE):
        while img[p] < 0x80:
            p += 1
        p += 1
    return p - inizio, off_str


def tabella_inglese(img, inizio, off_str_it, len_it):
    """la tabella del disco nella disposizione della tabella estesa italiana"""
    lung, off_str = leggi_tabella(img, inizio)
    orig = bytes(img[inizio:inizio + lung])
    extra = off_str_it - off_str
    if extra < 0 or lung + extra > len_it:
        raise ValueError('la tabella inglese non entra nella disposizione italiana')
    # il riempimento va prima del $FF del gruppo 164
    t = orig[:off_str - 1] + bytes([RIEMPITIVO]) * extra + orig[off_str - 1:]
    return t + bytes(len_it - len(t))


def zone(a, b, inizio=0):
    """tratti in cui a e b differiscono: [(da, a), ...] con a escluso"""
    out = []
    i, n = 0, min(len(a), len(b))
    while i < n:
        if a[i] != b[i]:
            j = i
            while j < n and a[j] != b[j]:
                j += 1
            out.append((inizio + i, inizio + j))
            i = j
        i += 1
    return out


def tratti(base, finale, escludi=()):
    """differenze per l'eseguibile: tratti uniti se separati da pochi byte
    uguali; [(indirizzo, byte)]"""
    zs = []
    for da, a in zone(base, finale):
        if any(da < e1 and a > e0 for e0, e1 in escludi):
            # taglia via le parti escluse
            pezzi = [(da, a)]
            for e0, e1 in escludi:
                nuovi = []
                for x, y in pezzi:
                    if y <= e0 or x >= e1:
                        nuovi.append((x, y))
                    else:
                        if x < e0: nuovi.append((x, e0))
                        if y > e1: nuovi.append((e1, y))
                pezzi = nuovi
            zs += pezzi
        else:
            zs.append((da, a))
    uniti = []
    for da, a in zs:
        if uniti and da - uniti[-1][1] <= 8 and not any(uniti[-1][1] < e1 and da > e0 for e0, e1 in escludi):
            uniti[-1] = (uniti[-1][0], a)
        else:
            uniti.append((da, a))
    return [(da, bytes(finale[da:a])) for da, a in uniti]


def scrivi_dati_c(percorso, voci):
    """voci: lista di (nome, valore) -- int o lista di tratti"""
    righe = ['/* generato da game/prepara_immagine.py: non modificare */',
             '#include <stdint.h>', '']
    for nome, v in voci:
        if isinstance(v, int):
            righe.append('#define %s 0x%Xu' % (nome, v))
            continue
        blob = bytearray()
        indice = []
        for ind, b in v:
            indice.append((ind, len(b), len(blob)))
            blob += b
        righe.append('static const uint8_t %s_byte[%d] = {' % (nome, max(len(blob), 1)))
        for k in range(0, len(blob), 24):
            righe.append('    ' + ','.join('%d' % x for x in blob[k:k + 24]) + ',')
        if not blob:
            righe.append('    0')
        righe.append('};')
        righe.append('static const uint32_t %s_tratti[%d][3] = {  /* indirizzo, lunghezza, posizione */'
                     % (nome, max(len(indice), 1)))
        for t in indice:
            righe.append('    { 0x%06Xu, %du, %du },' % t)
        if not indice:
            righe.append('    { 0, 0, 0 }')
        righe.append('};')
        righe.append('#define %s_N %d' % (nome, len(indice)))
        righe.append('')
    open(percorso, 'w', encoding='utf-8').write('\n'.join(righe) + '\n')


def esegui_post(m):
    from unicorn import Uc, UC_ARCH_M68K, UC_MODE_BIG_ENDIAN
    from unicorn.m68k_const import UC_M68K_REG_A7, UC_M68K_REG_PC, UC_CPU_M68K_M68000
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
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--traduzione", default=os.path.dirname(REPO))
    ap.add_argument("--uscita", default=os.path.join(REPO, "build", "rockstar_chipram.bin"))
    o = ap.parse_args()

    sys.path.insert(0, o.traduzione)
    import build_whdload as bw
    import build_ram as br
    import patch_finestre

    t = lambda n: os.path.join(o.traduzione, n)
    base = open(t('rockstar_base.bin'), 'rb').read()
    imm = open(t('rockstar_ita_img.bin'), 'rb').read()
    info = {}
    img, ext = bw.file_dati(imm, br.carica(t('rockstar_text_table_ESTESA.json')),
                            br.carica(t('rockstar_text_table_ITA.json')), info=info)
    m = bytearray(DIMENSIONE)
    m[GIOCO:GIOCO + len(img)] = img
    m[EXT:EXT + len(ext)] = ext
    it = esegui_post(m)

    # ---- inglese: dati del disco, codice dell'italiano
    en = bytearray(it)
    lb = len(imm)
    dati = zone(base[:lb], imm, GIOCO)                       # cio' che ha cambiato la traduzione
    dati.append((GIOCO + br.TAB_OFF, GIOCO + br.TAB_FINE))    # tabella compatta
    for n, orig, nuova in patch_finestre.FINESTRE:
        a = patch_finestre.TABELLA + 4 * n
        dati.append((a, a + 4))
    puntatori = (br.PTR_G, br.PTR_S + 4)                      # scritti dal post-codice: restano
    for da, a in dati:
        for k in range(da, a):
            if not (puntatori[0] <= k < puntatori[1]):
                en[k] = base[k - GIOCO]
    tab = EXT + info['off_tab']
    en[tab:tab + info['len_tab']] = tabella_inglese(base, br.TAB_OFF, info['off_str'], info['len_tab'])

    # il codice dev'essere identico: nessuna istruzione nelle zone cambiate
    cicli = os.path.join(REPO, 'build', 'cmake', 'generated', 'rockstar_cycles.c')
    if os.path.exists(cicli):
        import re
        istr = {int(x, 16) for x in re.findall(r'\{0x([0-9A-F]+)u,', open(cicli).read())}
        for da, a in zone(it, en):
            dentro = [x for x in istr if da <= x < a]
            if dentro:
                raise SystemExit('inglese: cambierebbe del codice a $%X (%d istruzioni)' % (da, len(dentro)))

    # ---- uscite
    os.makedirs(os.path.dirname(o.uscita), exist_ok=True)
    open(o.uscita, 'wb').write(it)
    p_en = os.path.join(os.path.dirname(o.uscita), 'rockstar_chipram_en.bin')
    open(p_en, 'wb').write(en)
    chip_base = bytearray(DIMENSIONE)
    chip_base[GIOCO:GIOCO + len(base)] = base
    t_it = tratti(chip_base, it)
    t_en = tratti(chip_base, en, escludi=[(tab, tab + info['len_tab'])])
    scrivi_dati_c(os.path.join(os.path.dirname(o.uscita), 'lingue_dati.h'), [
        ('LINGUE_CRC_BASE', crc(base)),
        ('LINGUE_LUNG_BASE', len(base)),
        ('LINGUE_CRC_IT', crc(it)),
        ('LINGUE_CRC_EN', crc(en)),
        ('LINGUE_TAB_DISCO', GIOCO + br.TAB_OFF),
        ('LINGUE_TAB_EXT', tab),
        ('LINGUE_TAB_LUNG', info['len_tab']),
        ('LINGUE_TAB_OFF_STR', info['off_str']),
        ('LINGUE_PATCH_IT', t_it),
        ('LINGUE_PATCH_EN', t_en),
    ])
    print("immagine: %s (%d byte), blocco esteso %d byte a $%X" % (o.uscita, len(it), len(ext), EXT))
    print("inglese:  %s, CRC IT %08X EN %08X" % (p_en, crc(it), crc(en)))
    print("patch: italiano %d tratti %d byte, inglese %d tratti %d byte" % (
        len(t_it), sum(len(b) for _, b in t_it), len(t_en), sum(len(b) for _, b in t_en)))


if __name__ == '__main__':
    main()
