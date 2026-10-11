#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
esporta_annotazioni.py - decomp/nomi.json (lavoro di decompilazione) ->
game/rockstar_annotations.csv (formato m68k-recomp-core: addr,nome,note).

    python game/esporta_annotazioni.py [percorso/nomi.json]

I nomi finiscono nei commenti del C generato e nei nomi delle funzioni.
"""
import json
import os
import sys

QUI = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(QUI)


def main():
    src = sys.argv[1] if len(sys.argv) > 1 else os.path.join(os.path.dirname(REPO), 'decomp', 'nomi.json')
    nomi = json.load(open(src, encoding='utf-8'))
    righe = ["# Rock Star Ate My Hamster - nomi delle funzioni (da decomp/nomi.json)",
             "# rigenerare con: python game/esporta_annotazioni.py"]
    for a in sorted(nomi, key=lambda k: int(k, 16)):
        v = nomi[a]
        note = (v.get('desc') or '').replace('"', "'").replace(',', ';')[:250]
        righe.append('%06x,%s,"%s"' % (int(a, 16), v['nome'], note))
    out = os.path.join(QUI, 'rockstar_annotations.csv')
    open(out, 'w', encoding='utf-8', newline='\n').write('\n'.join(righe) + '\n')
    print("%d annotazioni -> %s" % (len(nomi), out))


if __name__ == '__main__':
    main()
