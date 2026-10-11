#!/usr/bin/env python3
"""cerca_automodifica.py - scritture ad indirizzi assoluti che cadono dentro
un'istruzione (codice automodificante): il C generato ne congela il valore.

    python tools/cerca_automodifica.py ../rockstar.asm
"""
import re
import sys

righe = open(sys.argv[1], encoding='utf-8', errors='replace').read().splitlines()
istr = []                      # (indirizzo, testo)
for r in righe:
    m = re.match(r'\s+([0-9a-f]{5,6})\s+(\S.*)$', r)
    if m:
        istr.append((int(m.group(1), 16), m.group(2).strip()))
istr.sort()
inizi = [a for a, _ in istr]
testo = dict(istr)


def dentro(t):
    """istruzione che contiene l'indirizzo t (non il suo primo byte)."""
    import bisect
    i = bisect.bisect_right(inizi, t) - 1
    if i < 0 or i + 1 >= len(inizi):
        return None
    a, b = inizi[i], inizi[i + 1]
    return a if a < t < b and b - a <= 10 else (a if t == a else None)


SCRIVE = re.compile(r'^(move|clr|add|sub|or|and|eor|not|neg|st|sf|bset|bclr|bchg|addq|subq)')
for a, t in istr:
    if not SCRIVE.match(t):
        continue
    ops = t.split(None, 1)[1] if ' ' in t else ''
    dest = ops.rsplit(',', 1)[-1].strip()
    m = re.fullmatch(r'\$([0-9a-f]+)(\.[lw])?', dest)
    if not m:
        continue
    bersaglio = int(m.group(1), 16)
    c = dentro(bersaglio)
    if c is not None:
        print('$%05x  %-34s -> $%05x dentro  $%05x  %s' % (a, t, bersaglio, c, testo[c]))
