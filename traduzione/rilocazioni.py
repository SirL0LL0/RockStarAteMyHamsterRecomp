# -*- coding: utf-8 -*-
"""
rilocazioni.py - trova nel codice ogni campo che contiene un indirizzo
della memoria del gioco ($400-$80000), per costruire HUNK_RELOC32.

Per ogni istruzione disassemblata guarda gli operandi con capstone (dettaglio
completo) e restituisce il byte esatto del campo a 32 bit nell'immagine.
"""
import sys
import capstone as cs
from capstone import m68k as M

sys.path.insert(0, __file__.rsplit('/', 1)[0])
from disasm_rsamh import analizza, carica, BASE

LO, HI = 0x400, 0x80000          # memoria del gioco: schermo, immagine, buffer, stack


def in_zona(v):
    return LO <= v <= HI


def campi(img, d):
    """Restituisce (sicuri, dubbi, corti):
    sicuri : offset (nell'immagine) di longword che sono indirizzi
    dubbi  : immediati a 32 bit nella zona ma non chiaramente indirizzi
    corti  : operandi assoluti a 16 bit nella zona (non rilocabili)"""
    md = cs.Cs(cs.CS_ARCH_M68K, cs.CS_MODE_BIG_ENDIAN | cs.CS_MODE_M68K_000)
    md.detail = True
    sicuri, dubbi, corti = [], [], []
    for a in sorted(d.ins):
        o = a - BASE
        i = next(md.disasm(img[o:o + 12], a))
        b = bytes(i.bytes)
        ops = i.operands
        # posizione dei campi di estensione: si cercano nei byte dell'istruzione
        for k, op in enumerate(ops):
            val = None; tipo = None
            if op.type == M.M68K_OP_IMM and i.op_str.split(',')[0].strip().startswith('#'):
                if k == 0 and (i.mnemonic.endswith('.l') or i.mnemonic in ('moveq',)):
                    if i.mnemonic == 'moveq': continue
                    val = op.imm & 0xFFFFFFFF; tipo = 'imm'
            elif op.type == M.M68K_OP_MEM:
                am = op.address_mode
                if am == M.M68K_AM_ABSOLUTE_DATA_LONG:
                    val = op.imm & 0xFFFFFFFF; tipo = 'abs.l'
                elif am == M.M68K_AM_ABSOLUTE_DATA_SHORT:
                    v = op.imm & 0xFFFF
                    if v >= 0x8000: v |= 0xFFFF0000
                    if in_zona(v & 0xFFFFFFFF): corti.append((a, i.mnemonic, i.op_str))
                    continue
            if val is None or not in_zona(val):
                continue
            pat = val.to_bytes(4, 'big')
            pos = [p for p in range(2, len(b) - 3, 2) if b[p:p + 4] == pat]
            if not pos:
                dubbi.append((a, i.mnemonic, i.op_str, 'campo non trovato')); continue
            campo = o + pos[0] if len(pos) == 1 or k == 0 else o + pos[-1]
            dest = i.op_str.split(',')[-1].strip()
            if tipo == 'abs.l' or i.mnemonic in ('lea.l', 'pea.l', 'movea.l', 'adda.l',
                                                 'suba.l', 'cmpa.l') \
               or dest.startswith('a') and len(dest) == 2 or '(' in dest or dest.startswith('$'):
                sicuri.append((campo, a, i.mnemonic, i.op_str))
            else:
                dubbi.append((campo, a, i.mnemonic, i.op_str))
    return sicuri, dubbi, corti


if __name__ == '__main__':
    img = carica(sys.argv[1] if len(sys.argv) > 1 else __import__('percorsi').BASE)
    d = analizza(img)
    s, du, c = campi(img, d)
    print(len(s), 'sicuri,', len(du), 'dubbi,', len(c), 'corti')
    for x in du: print('DUBBIO', hex(x[1]) if isinstance(x[0], int) and len(x) == 4 else x, x)
    for x in c: print('CORTO', hex(x[0]), x[1], x[2])
