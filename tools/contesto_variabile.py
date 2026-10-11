#!/usr/bin/env python3
"""contesto_variabile.py - dove il gioco usa un indirizzo e quali messaggi
mostrano le funzioni che lo toccano.

    python tools/contesto_variabile.py 128ce 128cd [--asm ../documentazione/rockstar.asm]

Per ogni funzione che nomina l'indirizzo (direttamente, o chiamando una
funzione che lo nomina) stampa le istruzioni coinvolte e i commenti
"; diretto #N: TESTO" dei messaggi composti nella stessa funzione.
"""
import json
import os
import re
import sys

args = [a for a in sys.argv[1:] if not a.startswith('--')]
asm = '../documentazione/rockstar.asm'
if '--asm' in sys.argv:
    asm = sys.argv[sys.argv.index('--asm') + 1]
    args = [a for a in args if a != asm]
nomi = {}
p = os.path.join(os.path.dirname(os.path.abspath(asm)), 'decomp', 'nomi.json')
if os.path.exists(p):
    nomi = {k: v['nome'] for k, v in json.load(open(p, encoding='utf-8')).items()}

righe = open(asm, encoding='utf-8', errors='replace').read().splitlines()
funz, corrente = {}, None
for l in righe:
    m = re.match(r'f_([0-9a-f]{5}):', l)
    if m:
        corrente = m.group(1); funz[corrente] = []
    elif corrente:
        funz[corrente].append(l)

for var in args:
    var = var.lower().lstrip('$').zfill(5)
    pat = re.compile(r'\$0*%s\b' % var.lstrip('0'))
    dirette = {f for f, ls in funz.items() if any(pat.search(x) for x in ls)}
    # chi chiama le funzioni dirette
    chiamanti = {f for f, ls in funz.items()
                 if any(re.search(r'bsr\.\w\s+f_(%s)\b' % '|'.join(dirette), x) for x in ls)} - dirette
    print('=' * 70)
    print('$%s: usato da %d funzioni, chiamate da altre %d' % (var, len(dirette), len(chiamanti)))
    for f in sorted(dirette) + sorted(chiamanti):
        ls = funz[f]
        uso = [x.strip() for x in ls if pat.search(x)]
        msg = sorted({re.sub(r'.*;\s*', '', x).strip() for x in ls if '; diretto #' in x or '; messaggio' in x})
        print('-- f_%s %s %s' % (f, nomi.get(f, ''), '(chiama una diretta)' if f in chiamanti else ''))
        for x in uso[:6]:
            print('     ', x)
        for x in msg[:8]:
            print('     msg:', x)
