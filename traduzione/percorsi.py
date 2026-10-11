# -*- coding: utf-8 -*-
"""
percorsi.py - dove stanno i file del gioco e come si ricava l'immagine
italiana di partenza.

Il repository non contiene file del gioco. Quelli che servono alla
costruzione stanno nella cartella DATI, fuori dal repository: di norma quella
che lo contiene (o quella indicata dalla variabile RSAMH_DATI).

    DATI/rockstar_base.bin   la base canonica del gioco, 430848 byte, CRC
                             5BF4600A: la crea base_canonica.py dal disco
                             originale (IPF o ADF), una volta sola
    DATI/uscite/             ADF, eseguibile Amiga e WHDLoad costruiti

L'immagine italiana di partenza (la base con le modifiche fatte negli anni
con l'editor: script dei messaggi, testi dentro il codice) non e' un file:
e' la base con rockstar_ita_img.patch, che contiene solo i byte cambiati.
"""
import os
import zlib

QUI = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(QUI)
DATI = os.environ.get('RSAMH_DATI') or os.path.dirname(REPO)
USCITE = os.path.join(DATI, 'uscite')

BASE = os.path.join(DATI, 'rockstar_base.bin')
CRC_BASE = 0x5BF4600A
LUNG_BASE = 430848
LUNG_IMM = 429824                 # l'immagine del gioco: $8100-$71000
PATCH_IMM = os.path.join(QUI, 'rockstar_ita_img.patch')


def testo(nome):
    """un file della traduzione (testi, script, generi)"""
    return os.path.join(QUI, nome)


def base():
    if not os.path.isfile(BASE):
        raise SystemExit("manca %s\n  crealo dal disco originale:  python %s <disco.ipf|disco.adf> %s"
                         % (BASE, os.path.join(QUI, 'base_canonica.py'), BASE))
    b = open(BASE, 'rb').read()
    if len(b) != LUNG_BASE or zlib.crc32(b) & 0xFFFFFFFF != CRC_BASE:
        raise SystemExit("%s non e' la base attesa (CRC %08X)" % (BASE, zlib.crc32(b) & 0xFFFFFFFF))
    return b


def inglese():
    """il gioco originale, lungo quanto l'immagine (per editor e strumenti)"""
    return base()[:LUNG_IMM]


def leggi_patch(p=PATCH_IMM):
    tratti = []
    for riga in open(p, encoding='ascii'):
        riga = riga.strip()
        if riga and not riga.startswith('#'):
            ind, esa = riga.split()
            tratti.append((int(ind, 16), bytes.fromhex(esa)))
    return tratti


def immagine_ita():
    imm = bytearray(inglese())
    for ind, b in leggi_patch():
        imm[ind:ind + len(b)] = b
    return bytes(imm)


def scrivi_patch(orig, nuova, p=PATCH_IMM, per_riga=32):
    """i byte di nuova diversi da orig, a righe 'offset esadecimale'"""
    righe = ['# rockstar_ita_img.patch - modifiche alla base del gioco (percorsi.py)',
             '# offset nell\'immagine (0 = $8100), byte nuovi']
    i, n = 0, len(nuova)
    while i < n:
        if orig[i] == nuova[i]:
            i += 1
            continue
        j = i
        while j < n and (nuova[j] != orig[j] or any(nuova[k] != orig[k] for k in range(j, min(j + 4, n)))):
            j += 1
        for k in range(i, j, per_riga):
            righe.append('%05X %s' % (k, nuova[k:min(j, k + per_riga)].hex().upper()))
        i = j
    open(p, 'w', encoding='ascii', newline='\n').write('\n'.join(righe) + '\n')
