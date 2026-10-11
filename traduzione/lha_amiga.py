#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
lha_amiga.py - crea archivi LhA come quelli Amiga (stile Retroplay).

    scrivi_lha('Gioco_v1.0.lha', [('Gioco.info', dati), ('Gioco/data/file', dati), ...])

Formato, ricavato dagli archivi Retroplay:
    - header di livello 1, sistema operativo 'A' (Amiga)
    - i file in sottocartelle hanno l'header esteso 0x02 (cartella, separatori
      0xFF) seguito dall'header esteso 0x00 con il CRC dell'header
    - compressione -lh5- (LZSS con finestra 8K + Huffman a blocchi); se non
      conviene il file e' memorizzato -lh0-
"""
import struct
import time

# ------------------------------------------------------------------ CRC-16 (ARC)

_TAB = []
for _i in range(256):
    _c = _i
    for _ in range(8):
        _c = (_c >> 1) ^ 0xA001 if _c & 1 else _c >> 1
    _TAB.append(_c)


def crc16(dati, crc=0):
    for b in dati:
        crc = (crc >> 8) ^ _TAB[(crc ^ b) & 0xFF]
    return crc


# ------------------------------------------------------------------ bit

class Bit:
    def __init__(self):
        self.out = bytearray(); self.acc = 0; self.n = 0

    def put(self, nbit, val):
        if nbit == 0:
            return
        self.acc = (self.acc << nbit) | (val & ((1 << nbit) - 1)); self.n += nbit
        while self.n >= 8:
            self.n -= 8
            self.out.append((self.acc >> self.n) & 0xFF)
        self.acc &= (1 << self.n) - 1

    def fine(self):
        if self.n:
            self.out.append((self.acc << (8 - self.n)) & 0xFF)
            self.n = 0; self.acc = 0
        return bytes(self.out)


# ------------------------------------------------------------------ Huffman

def lunghezze(freq, limite=16):
    """Lunghezze di Huffman (0 = simbolo assente), al massimo `limite` bit."""
    import heapq
    f = list(freq)
    while True:
        usati = [i for i, x in enumerate(f) if x]
        lung = [0] * len(f)
        if len(usati) < 2:
            return lung
        h = [(f[i], i, (i,)) for i in usati]
        heapq.heapify(h); k = len(f)
        while len(h) > 1:
            a = heapq.heappop(h); b = heapq.heappop(h)
            for s in a[2] + b[2]:
                lung[s] += 1
            heapq.heappush(h, (a[0] + b[0], k, a[2] + b[2])); k += 1
        if max(lung) <= limite:
            return lung
        f = [(x + 1) // 2 if x else 0 for x in f]     # appiattisce e riprova


def codici(lung):
    """Codici canonici come make_table di LhA: per lunghezza, poi per simbolo."""
    cod = [0] * len(lung); c = 0
    for L in range(1, 17):
        for s, l in enumerate(lung):
            if l == L:
                cod[s] = c; c += 1
        c <<= 1
    return cod


# ------------------------------------------------------------------ -lh5-

NC, NT, NP = 510, 19, 14
CBIT, TBIT, PBIT = 9, 5, 4
FINESTRA, MAXM, MINM = 8192, 256, 3


def _token(dati, profondita=96):
    """LZSS goloso con catene di hash: lista di int (letterale) o (lung, dist)."""
    n = len(dati); out = []; testa = {}; prec = [-1] * n
    i = 0
    def inserisci(p):
        if p + 2 < n:
            k = dati[p:p + 3]
            prec[p] = testa.get(k, -1); testa[k] = p
    while i < n:
        mig_l = 0; mig_d = 0
        if i + 2 < n:
            p = testa.get(dati[i:i + 3], -1); giri = 0; lim = min(MAXM, n - i)
            while p >= 0 and i - p < FINESTRA and giri < profondita:
                if dati[p + mig_l] == dati[i + mig_l] if mig_l < lim else False:
                    l = 0
                    while l < lim and dati[p + l] == dati[i + l]:
                        l += 1
                    if l > mig_l:
                        mig_l, mig_d = l, i - p
                        if l == lim:
                            break
                p = prec[p]; giri += 1
        if mig_l >= MINM:
            out.append((mig_l, mig_d))
            for q in range(i, i + mig_l):
                inserisci(q)
            i += mig_l
        else:
            out.append(dati[i]); inserisci(i); i += 1
    return out


def _scrivi_pt(bw, lung, nbit, speciale):
    n = len(lung)
    while n > 0 and lung[n - 1] == 0:
        n -= 1
    bw.put(nbit, n)
    i = 0
    while i < n:
        k = lung[i]; i += 1
        if k <= 6:
            bw.put(3, k)
        else:
            bw.put(k - 3, (1 << (k - 3)) - 2)
        if i == speciale:
            z = 0
            while i < 6 and i < n and lung[i] == 0:
                i += 1; z += 1
            bw.put(2, z)


def _blocco(bw, tok):
    cf = [0] * NC; pf = [0] * NP
    for t in tok:
        if isinstance(t, int):
            cf[t] += 1
        else:
            l, d = t; cf[l - MINM + 256] += 1
            pf[(d - 1).bit_length()] += 1
    bw.put(16, len(tok))
    cl = lunghezze(cf)
    usati_c = [i for i, x in enumerate(cf) if x]
    if len(usati_c) == 1:
        # un solo simbolo: tabella vuota, il simbolo non costa bit
        bw.put(TBIT, 0); bw.put(TBIT, 0)
        bw.put(CBIT, 0); bw.put(CBIT, usati_c[0])
        cc = [0] * NC
    else:
        n = NC
        while n > 0 and cl[n - 1] == 0:
            n -= 1
        # frequenze della tabella T (lunghezze dei codici C, zeri a gruppi)
        tf = [0] * NT; seq = []; i = 0
        while i < n:
            k = cl[i]; i += 1
            if k == 0:
                z = 1
                while i < n and cl[i] == 0:
                    i += 1; z += 1
                if z <= 2:
                    seq += [(0, None)] * z; tf[0] += z
                elif z <= 18:
                    seq.append((1, z - 3)); tf[1] += 1
                elif z == 19:
                    seq += [(0, None), (1, 15)]; tf[0] += 1; tf[1] += 1
                else:
                    seq.append((2, z - 20)); tf[2] += 1
            else:
                seq.append((k + 2, None)); tf[k + 2] += 1
        tl = lunghezze(tf)
        usati_t = [i for i, x in enumerate(tf) if x]
        if len(usati_t) == 1:
            bw.put(TBIT, 0); bw.put(TBIT, usati_t[0]); tc = [0] * NT; tl = [0] * NT
        else:
            _scrivi_pt(bw, tl, TBIT, 3); tc = codici(tl)
        bw.put(CBIT, n)
        for s, extra in seq:
            bw.put(tl[s], tc[s])
            if s == 1:
                bw.put(4, extra)
            elif s == 2:
                bw.put(CBIT, extra)
        cc = codici(cl)
    pl = lunghezze(pf)
    usati_p = [i for i, x in enumerate(pf) if x]
    if len(usati_p) <= 1:
        bw.put(PBIT, 0); bw.put(PBIT, usati_p[0] if usati_p else 0)
        pc = [0] * NP; pl = [0] * NP
    else:
        _scrivi_pt(bw, pl, PBIT, -1); pc = codici(pl)
    for t in tok:
        if isinstance(t, int):
            bw.put(cl[t], cc[t])
        else:
            l, d = t; s = l - MINM + 256
            bw.put(cl[s], cc[s])
            d -= 1; j = d.bit_length()
            bw.put(pl[j], pc[j])
            if j > 1:
                bw.put(j - 1, d - (1 << (j - 1)))


def lh5(dati, per_blocco=16384):
    tok = _token(bytes(dati))
    bw = Bit()
    for k in range(0, len(tok), per_blocco):
        _blocco(bw, tok[k:k + per_blocco])
    return bw.fine()


# ------------------------------------------------------------------ archivio

def _dos_time(t):
    t = time.localtime(t)
    return ((t.tm_year - 1980) << 25 | t.tm_mon << 21 | t.tm_mday << 16 |
            t.tm_hour << 11 | t.tm_min << 5 | t.tm_sec // 2)


def _voce(percorso, dati, quando):
    parti = percorso.split('/')
    nome = parti[-1].encode('latin1'); cartella = parti[:-1]
    comp = lh5(dati) if dati else b''
    if dati and len(comp) < len(dati):
        metodo = b'-lh5-'
    else:
        metodo, comp = b'-lh0-', bytes(dati)
    est = bytearray()
    if cartella:
        d = b''.join(p.encode('latin1') + b'\xff' for p in cartella)
        est += bytes([0x02]) + d
        est += struct.pack('<H', 5)               # dimensione del prossimo (CRC)
        est += bytes([0x00]) + b'\x00\x00'        # CRC dell'header, dopo
        est += struct.pack('<H', 0)
        primo = 1 + len(d) + 2
    else:
        primo = 0
    base = bytearray()
    base += metodo
    base += struct.pack('<II', len(comp) + len(est), len(dati))
    base += struct.pack('<I', _dos_time(quando))
    base += bytes([0x00, 0x01, len(nome)]) + nome
    base += struct.pack('<H', crc16(dati)) + b'A'
    base += struct.pack('<H', primo)
    hs = len(base)
    h = bytearray([hs, 0]) + base + est
    h[1] = sum(h[2:2 + hs]) & 0xFF          # prima il checksum: il CRC lo include
    if cartella:
        pos_crc = 2 + hs + primo + 1
        struct.pack_into('<H', h, pos_crc, crc16(h))
    return bytes(h) + comp, metodo


def scrivi_lha(uscita, voci, quando=None):
    """voci: lista di (percorso con '/', bytes). Restituisce i metodi usati."""
    quando = quando or time.time()
    out = bytearray(); metodi = []
    for percorso, dati in voci:
        v, m = _voce(percorso, dati, quando)
        out += v; metodi.append((percorso, m, len(dati)))
    out.append(0)
    open(uscita, 'wb').write(out)
    return metodi
