# -*- coding: utf-8 -*-
"""
disasm_rsamh.py - disassemblatore ricorsivo di Rock Star Ate My Hamster.

    python3 disasm_rsamh.py rockstar_base.bin rockstar.asm

Parte dall'ingresso $8100 e segue tutti i salti, le chiamate e i vettori che
il codice installa. Quello che non viene raggiunto e' marcato come dati.
Oltre al listato produce `analisi` (un dizionario) con funzioni, chiamate e
riferimenti, che gli altri strumenti usano.
"""
import re
import struct
import sys
import capstone as cs

BASE = 0x8100

TERMINALI = {'rts', 'rte', 'rtr', 'jmp', 'bra', 'bra.b', 'bra.w', 'bra.s', 'illegal'}
RE_IND = re.compile(r'\$([0-9a-f]+)')


def carica(p):
    return open(p, 'rb').read()


class Disasm:
    def __init__(self, img):
        self.img = img
        self.fine = BASE + len(img)
        self.md = cs.Cs(cs.CS_ARCH_M68K, cs.CS_MODE_BIG_ENDIAN | cs.CS_MODE_M68K_000)
        self.ins = {}            # addr -> (size, mnem, ops)
        self.funzioni = set()    # destinazioni di bsr/jsr
        self.etichette = set()   # destinazioni di salti
        self.chiamate = []       # (da, a)
        self.rif = {}            # indirizzo dati -> [da]
        self.vettori = set()

    def dentro(self, a):
        return BASE <= a < self.fine

    def una(self, a):
        o = a - BASE
        for i in self.md.disasm(self.img[o:o + 12], a):
            return i
        return None

    def esplora(self, partenze):
        coda = list(partenze)
        while coda:
            a = coda.pop()
            while self.dentro(a) and a not in self.ins:
                i = self.una(a)
                if i is None:
                    break
                m, ops = i.mnemonic, i.op_str
                self.ins[a] = (i.size, m, ops)
                dest = self.destinazione(m, ops)
                if dest is not None and self.dentro(dest):
                    if m.startswith(('bsr', 'jsr')):
                        self.funzioni.add(dest); self.chiamate.append((a, dest))
                    else:
                        self.etichette.add(dest)
                    coda.append(dest)
                # vettori installati: lea xxx(pc),a0 ; move.l a0,$yy.w
                self.riferimenti(a, m, ops)
                if m in TERMINALI or m.startswith(('bra', 'jmp')):
                    break
                a += i.size

    def destinazione(self, m, ops):
        if m.startswith(('b', 'jsr', 'jmp', 'db')) and not m.startswith(('btst', 'bset', 'bclr', 'bchg')):
            if '(' in ops and 'pc' not in ops and not re.search(r'\$[0-9a-f]+\.[lw]$', ops):
                # jmp (a0) ecc.: indiretto
                if re.fullmatch(r'\$[0-9a-f]+(\.[lw])?', ops.split(',')[-1].strip()) is None:
                    return None
            t = RE_IND.findall(ops.split(',')[-1])
            if t:
                return int(t[-1], 16)
        return None

    def riferimenti(self, a, m, ops):
        for t in RE_IND.findall(ops):
            v = int(t, 16)
            if self.dentro(v) and not m.startswith(('b', 'db', 'jsr', 'jmp')) or \
               (self.dentro(v) and m.startswith(('btst', 'bset', 'bclr', 'bchg'))):
                self.rif.setdefault(v, []).append(a)

    def vettori_installati(self):
        """lea X(pc),a0 / lea X.l,a0 seguito da move.l a0,$NN.w (vettori
        d'eccezione e interrupt) -> X e' codice."""
        nuovi = set()
        prec = None
        for a in sorted(self.ins):
            s, m, ops = self.ins[a]
            if prec and m.startswith('move.l') and re.search(r'a0, \$[0-9a-f]+\.w$', ops):
                nuovi.add(prec)
            prec = None
            mm = re.match(r'\$([0-9a-f]+)(\(pc\)|\.l)?, a0$', ops)
            if m == 'lea.l' and mm:
                prec = int(mm.group(1), 16)
            if m.startswith('move.l') and re.match(r'#\$([0-9a-f]+), \$[0-9a-f]+\.w$', ops):
                v = int(re.match(r'#\$([0-9a-f]+)', ops).group(1), 16)
                if self.dentro(v): nuovi.add(v)
        return {x for x in nuovi if self.dentro(x) and x not in self.ins}

    def completa(self):
        self.esplora([BASE])
        for _ in range(5):
            v = self.vettori_installati()
            if not v: break
            self.vettori |= v
            self.funzioni |= v
            self.esplora(v)

    # ------------------------------------------------------------ listato
    def nome(self, a):
        if a in self.funzioni: return f"f_{a:05x}"
        if a in self.etichette: return f"l_{a:05x}"
        return None

    def listato(self, commenti=None):
        commenti = commenti or {}
        righe = []
        a = BASE
        chiamanti = {}
        for da, x in self.chiamate:
            chiamanti.setdefault(x, []).append(da)
        while a < self.fine:
            if a in self.ins:
                s, m, ops = self.ins[a]
                n = self.nome(a)
                if a in self.funzioni:
                    righe.append('')
                    cl = chiamanti.get(a, [])
                    righe.append(f"; ---- funzione ${a:05x}   chiamata da {len(cl)} punti"
                                 + (': ' + ' '.join(f'${c:05x}' for c in cl[:8]) if cl else ''))
                if n: righe.append(f"{n}:")
                ops2 = re.sub(r'\$([0-9a-f]{4,5})\b',
                              lambda mo: self.nome(int(mo.group(1), 16)) or mo.group(0), ops)
                c = commenti.get(a, '')
                righe.append(f"    {a:05x}  {m:<8} {ops2}" + (f"    ; {c}" if c else ''))
                a += s
            else:
                inizio = a
                while a < self.fine and a not in self.ins:
                    a += 1
                blocco = self.img[inizio - BASE:a - BASE]
                righe.append(f"    ; dati ${inizio:05x}-${a:05x} ({a-inizio} byte)"
                             + (f"  \"{self.testo(blocco)}\"" if len(blocco) < 4000 else ''))
        return '\n'.join(righe) + '\n'

    @staticmethod
    def testo(b):
        t = ''.join(chr(c & 0x7F) if 32 <= (c & 0x7F) < 127 else '.' for c in b[:60])
        return t + ('...' if len(b) > 60 else '')


def analizza(img):
    d = Disasm(img)
    d.completa()
    return d


if __name__ == '__main__':
    img = carica(sys.argv[1])
    d = analizza(img)
    codice = sum(s for s, _, _ in d.ins.values())
    print(f"istruzioni {len(d.ins)}, byte di codice {codice}, funzioni {len(d.funzioni)}, "
          f"vettori {sorted(hex(v) for v in d.vettori)}")
    if len(sys.argv) > 2:
        # con i commenti dei messaggi, se c'e' lo strumento accanto
        try:
            import os
            sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            from mappa_messaggi import commenti_listato
            c, d = commenti_listato(img)
        except Exception as ex:
            print('senza commenti:', ex); c = {}
        open(sys.argv[2], 'w').write(d.listato(c))
