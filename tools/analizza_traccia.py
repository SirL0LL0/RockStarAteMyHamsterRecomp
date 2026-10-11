#!/usr/bin/env python3
"""analizza_traccia.py - legge build/traccia.txt (AMIGA_TRACCIA=tutte:DA:A) e
mostra come cambia la base della pila 68000 fra un quadro e l'altro e le
chiamate attorno ai punti indicati.

    python tools/analizza_traccia.py [indirizzo_ritorno ...]
"""
import collections
import re
import sys

righe = []
for l in open('build/traccia.txt'):
    m = re.match(r'q(\d+) rit=([0-9A-F]+) A7=([0-9A-F]+)', l)
    if m:
        righe.append((int(m.group(1)), m.group(2), int(m.group(3), 16)))
print("chiamate registrate:", len(righe))
base = collections.OrderedDict()
for q, rit, a7 in righe:
    base[q] = max(base.get(q, 0), a7)
print("A7 massimo per quadro:", ' '.join('q%d=%06X' % kv for kv in base.items()))
cerca = set(x.upper().zfill(6) for x in sys.argv[1:])
for i, (q, rit, a7) in enumerate(righe):
    if rit in cerca:
        print('q%d rit=%s A7=%06X' % (q, rit, a7))
