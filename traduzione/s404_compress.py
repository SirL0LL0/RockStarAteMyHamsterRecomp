#!/usr/bin/env python3
"""
Compressore StoneCracker S404 (v4.10) in Python puro.

Ricostruito dal decompressore di amigadepacker (s404_dec.c).

FORMATO
  Header 16 byte:  'S404' + sLen(4) + oLen(4) + pLen(4)   [big-endian]
  Blob:            [Dk][Dk-1]...[D1][eff][init]
  Dopo il blob:    2 byte col numero di bit validi nella word iniziale
                   (il decoder li legge con & 0x0F, quindi deve stare in 1..15)

  Il bitstream si legge MSB-first dentro ogni word a 16 bit big-endian, e le
  word si consumano dagli indirizzi ALTI verso i BASSI. La decompressione
  procede all'indietro: il primo simbolo decodificato e' l'ultimo byte
  dell'output. Per questo si comprime il buffer rovesciato in avanti.

OPCODE (9 bit)
  0x000-0x0FF  literal, il valore e' il byte stesso
  0x100-0x11F  match lungo (23+), lunghezza a byte con catene 0xFF
  0x120-0x13D  match 8-22
  0x13E-0x13F  run di literal (non emesso da questo encoder)
  0x140-0x17F  match 4-7
  0x180-0x1FF  match 2-3

  In ogni famiglia la distanza ha tre codifiche: 1-32, 33-544, 545+.
  Il valore codificato e' distanza-1.
"""

import struct

EFF = 14                      # bit per le distanze grandi (come l'originale)
DIST_LARGE_MAX = 544 + (1 << EFF) - 1
MAX_DIST = DIST_LARGE_MAX + 1
MAX_MATCH = 277
MIN_MATCH = 2
CHAIN_LIMIT = 256


class _Bits:
    __slots__ = ('out',)

    def __init__(self):
        self.out = []

    def put(self, value, count):
        o = self.out
        for i in range(count - 1, -1, -1):
            o.append((value >> i) & 1)


def _emit_literal(bits, byte):
    bits.put(byte, 9)


def _emit_match(bits, n, dist):
    """n = lunghezza, dist = distanza reale (>=1). Codificata come dist-1."""
    w = dist - 1

    if n <= 3:
        op = 0x180 | (0x40 if n == 3 else 0)
        if w >= 544:
            v = w - 544
            bits.put(op | 0x20 | (v >> (EFF - 5)), 9)
            bits.put(v & ((1 << (EFF - 5)) - 1), EFF - 5)
        elif w < 32:
            bits.put(op | 0x10 | (w >> 1), 9)
            bits.put(w & 1, 1)
        else:
            v = w - 32
            bits.put(op | (v >> 5), 9)
            bits.put(v & 0x1F, 5)

    elif n <= 7:
        op = 0x140 | ((n - 4) << 4)
        if w >= 544:
            v = w - 544
            bits.put(op | 0x08 | (v >> (EFF - 3)), 9)
            bits.put(v & ((1 << (EFF - 3)) - 1), EFF - 3)
        elif w < 32:
            bits.put(op | 0x04 | (w >> 3), 9)
            bits.put(w & 0x07, 3)
        else:
            v = w - 32
            bits.put(op | (v >> 7), 9)
            bits.put(v & 0x7F, 7)

    elif n <= 22:
        op = 0x120 | ((n - 8) << 1)
        if w >= 544:
            bits.put(op | 1, 9)
            bits.put(w - 544, EFF)
        elif w < 32:
            bits.put(op, 9)
            bits.put(0x20 | w, 6)
        else:
            v = w - 32
            bits.put(op, 9)
            bits.put(v >> 4, 6)
            bits.put(v & 0x0F, 4)

    else:
        ln = n - 23                       # 0..254
        bits.put(0x100 | (ln >> 3), 9)
        bits.put(ln & 0x07, 3)
        if w >= 544:
            v = w - 544
            bits.put(0x40 | (v >> (EFF - 6)), 7)
            bits.put(v & ((1 << (EFF - 6)) - 1), EFF - 6)
        elif w < 32:
            bits.put(0x20 | w, 7)
        else:
            v = w - 32
            bits.put(v >> 4, 7)
            bits.put(v & 0x0F, 4)


def _cost(n, dist):
    """Bit necessari per codificare questo match."""
    w = dist - 1
    if w >= 544:
        extra = (EFF - 5, EFF - 3, EFF, EFF - 6)
    elif w < 32:
        extra = (1, 3, 6, 0)
    else:
        extra = (5, 7, 10, 4)
    if n <= 3:
        return 9 + extra[0]
    if n <= 7:
        return 9 + extra[1]
    if n <= 22:
        return 9 + extra[2]
    return 9 + 3 + 7 + extra[3]


def _pack_stream(bits_list):
    if len(bits_list) % 16 == 0:
        bits_list = bits_list + [0] * 8
    r = len(bits_list) % 16

    init = 0
    for b in bits_list[:r]:
        init = (init << 1) | b
    init <<= (16 - r)

    rest = bits_list[r:]
    nw = len(rest) // 16
    pad_words = 0
    if nw % 2:
        # il blob deve essere multiplo di 4 byte per l'allineamento dell'hunk
        # Amiga; la word in piu' finisce all'indirizzo piu' basso, cioe' in
        # fondo alla coda di lettura, e non viene mai consumata.
        pad_words = 1
    blob = bytearray((nw + pad_words) * 2 + 4)
    nw_tot = nw + pad_words
    for k in range(nw):
        w = 0
        base = k * 16
        for i in range(16):
            w = (w << 1) | rest[base + i]
        off = (nw_tot - 1 - k) * 2
        blob[off] = w >> 8
        blob[off + 1] = w & 0xFF
    struct.pack_into('>HH', blob, nw_tot * 2, EFF, init)
    return bytes(blob), r


def compress(data, progress=None):
    """Comprime in formato S404. Restituisce (file_s404, partial_bits)."""
    size = len(data)
    if size == 0:
        raise ValueError("dati vuoti")

    work = bytes(reversed(data))
    bits = _Bits()
    chains = {}
    pos = 0
    next_report = 0

    while pos < size:
        best_len = 0
        best_dist = 0

        if pos + 2 < size:
            h = (work[pos] << 16) | (work[pos + 1] << 8) | work[pos + 2]
            chain = chains.get(h)
            if chain:
                limit = min(size - pos, MAX_MATCH)
                steps = 0
                for cand in reversed(chain):
                    if steps >= CHAIN_LIMIT:
                        break
                    steps += 1
                    d = pos - cand
                    if d > MAX_DIST:
                        break
                    if best_len and work[cand + best_len] != work[pos + best_len]:
                        continue
                    ln = 0
                    while ln < limit and work[cand + ln] == work[pos + ln]:
                        ln += 1
                    if ln > best_len or (ln == best_len and d < best_dist):
                        if ln >= MIN_MATCH:
                            if ln > best_len or _cost(ln, d) < _cost(best_len, best_dist):
                                best_len = ln
                                best_dist = d
                                if ln >= limit:
                                    break

        if best_len >= MIN_MATCH and _cost(best_len, best_dist) < 9 * best_len:
            _emit_match(bits, best_len, best_dist)
            step = best_len
        else:
            _emit_literal(bits, work[pos])
            step = 1

        end = min(pos + step, size - 2)
        for i in range(pos, end):
            h = (work[i] << 16) | (work[i + 1] << 8) | work[i + 2]
            c = chains.get(h)
            if c is None:
                chains[h] = [i]
            else:
                c.append(i)

        pos += step

        if progress and pos >= next_report:
            progress(pos, size)
            next_report = pos + size // 20

    blob, partial = _pack_stream(bits.out)
    # sLen: margine di sicurezza per la decompressione in-place sull'Amiga.
    slen = max(0, len(blob) + 16 - size) + 80
    header = b'S404' + struct.pack('>III', slen, size, len(blob))
    return header + blob, partial
