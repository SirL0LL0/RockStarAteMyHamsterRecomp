#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Decompressore StoneCracker S404 (v4.10) in Python puro.

Porting fedele di s404_dec.c di Jouni 'Mr.Spiv' Korhonen (2006),
verificato contro amigadepacker e contro il manuale originale
StoneCracker 4.10.3 (stc.doc, sez. 5.2 "Decrunch info header & decrunching"):
header 16 byte S404/sLen/oLen/pLen, due control word in coda ai dati
(LastWord + Efficiency dentro pLen) e BitCounter subito dopo;
decompressione all'indietro con vincolo di overlap (Security length).

Layout su disco (tutto big-endian):
  offset 0   : 'S404' (4 byte)
  offset 4   : sLen (4 byte) - margine sicurezza, ignorato qui
  offset 8   : oLen (4 byte) - lunghezza output
  offset 12  : pLen (4 byte) - lunghezza packed (INCLUDE EFF+init, ESCLUDE counter)
  offset 16  : dati packed (pLen byte), coda = [..dati..][EFF(2)][init(2)]
  offset16+pLen : bit counter (2 byte, si usa solo il nibble basso & 0x0F)

La decompressione procede ALL'INDIETRO:
  dst parte da olen e scende; i match copiano da dst[w+1] (già scritto).
"""

import struct


def _getb_factory(blob, counter, eff, init_word):
    """Replica initGetb+getb del C. Ritorna (getb, info)."""
    left = counter & 0x0F  # il C NON mappa 0->16, lo teniamo così
    word = init_word & 0xFFFF
    # puntatore (in byte, offset nel blob) alla prossima word da caricare
    # dopo init: EFF sta a plen-4, quindi il prossimo è a plen-6
    src_pos = len(blob) - 6
    state = {'word': word, 'left': left, 'src_pos': src_pos, 'refills': 0}

    def getb(nbits):
        w = state['word'] & 0xFFFF  # bs->word &= 0xffff (inizio getb)
        left = state['left']
        src_pos = state['src_pos']
        if left < nbits:
            w = (w << left) & 0xFFFFFFFF  # uint32 wrap come nel C
            if src_pos < 0:
                raise ValueError(
                    f"Blob terminato: servono {nbits} bit, ne restano {left}, "
                    f"src_pos={src_pos}")
            w |= struct.unpack_from('>H', blob, src_pos)[0]
            src_pos -= 2
            nbits -= left
            left = 16
            state['refills'] += 1
        left -= nbits
        w = (w << nbits) & 0xFFFFFFFF
        state['word'] = w
        state['left'] = left
        state['src_pos'] = src_pos
        return (w >> 16) & 0xFFFF

    return getb, state


def decompress(data):
    """Decomprime header+blob S404. Ritorna bytes di lunghezza oLen."""
    idx = data.find(b'S404')
    if idx == -1:
        raise ValueError("Magic S404 non trovato")
    if len(data) < idx + 16:
        raise ValueError("Dati troppo corti per header S404")
    slen, olen, plen = struct.unpack_from('>III', data, idx + 4)
    base = idx + 16
    if len(data) < base + plen + 2:
        raise ValueError(
            f"File troncato: servono {plen}+2 byte dopo header, "
            f"disponibili {len(data) - base}")
    blob = bytes(data[base:base + plen])
    eff = struct.unpack_from('>H', blob, plen - 4)[0]
    init_word = struct.unpack_from('>H', blob, plen - 2)[0]
    counter = struct.unpack_from('>H', data, base + plen)[0]

    getb, dbg = _getb_factory(blob, counter, eff, init_word)

    out = bytearray(olen)
    dst = olen
    oleft = olen

    while oleft > 0:
        w = getb(9)
        if w < 0x100:
            dst -= 1
            oleft -= 1
            if dst < 0:
                raise ValueError("Literal oltre inizio buffer")
            out[dst] = w
        elif w == 0x13E or w == 0x13F:
            w = ((w << 4) | getb(4)) & 0xFFFF
            n = (w & 0x1F) + 14
            oleft -= n
            if oleft < 0:
                raise ValueError(f"Run oltre inizio buffer: n={n} oleft={oleft+n}")
            # porting letterale del while(n-->0){ *--dst = getb(8); }
            for _ in range(n):
                dst -= 1
                out[dst] = getb(8)
        else:
            if w >= 0x180:
                n = 3 if (w & 0x40) else 2
                if w & 0x20:
                    w = ((w & 0x1F) << (eff - 5)) & 0xFFFF
                    w |= getb(eff - 5)
                    w += 544
                elif w & 0x30:
                    w = ((w & 0x0F) << 1) & 0xFFFF
                    w |= getb(1)
                else:
                    w = ((w & 0x0F) << 5) & 0xFFFF
                    w |= getb(5)
                    w += 32
            elif w >= 0x140:
                n = ((w & 0x30) >> 4) + 4
                if w & 0x08:
                    w = ((w & 0x07) << (eff - 3)) & 0xFFFF
                    w |= getb(eff - 3)
                    w += 544
                elif w & 0x0C:
                    w = ((w & 0x03) << 3) & 0xFFFF
                    w |= getb(3)
                else:
                    w = ((w & 0x03) << 7) & 0xFFFF
                    w |= getb(7)
                    w += 32
            elif w >= 0x120:
                n = ((w & 0x1E) >> 1) + 8
                if w & 0x01:
                    w = getb(eff) + 544
                else:
                    w = getb(6)
                    if w & 0x20:
                        w &= 0x1F
                    else:
                        w = ((w << 4) | getb(4)) & 0xFFFF
                        w += 32
            else:
                w = (((w & 0x1F) << 3) | getb(3)) & 0xFFFF
                n = 23
                while w == 0xFF:
                    n += w
                    w = getb(8)
                n += w
                w = getb(7)
                if w & 0x40:
                    w = ((w & 0x3F) << (eff - 6)) & 0xFFFF
                    w |= getb(eff - 6)
                    w += 544
                elif w & 0x20:
                    w &= 0x1F
                else:
                    w = ((w << 4) | getb(4)) & 0xFFFF
                    w += 32
            oleft -= n
            if oleft < 0:
                raise ValueError(f"Match n={n} oltre inizio buffer")
            # while(n-->0){ dst--; *dst = dst[w+1]; }
            for _ in range(n):
                dst -= 1
                if dst < 0:
                    raise ValueError("dst sotto zero nel match")
                src_idx = dst + w + 1
                if src_idx >= olen:
                    raise ValueError(
                        f"Match fuori buffer: dst={dst} w={w} "
                        f"src={src_idx} olen={olen}")
                out[dst] = out[src_idx]
    return bytes(out)


def decompress_file(path):
    with open(path, 'rb') as f:
        data = f.read()
    return decompress(data)


if __name__ == '__main__':
    import sys
    input_path = sys.argv[1]
    output_path = sys.argv[2] if len(sys.argv) > 2 else input_path + '.bin'
    print(f"Decomprimendo {input_path}...")
    output = decompress_file(input_path)
    print(f"Output: {len(output)} bytes, primi 4: {output[:4].hex()}")
    with open(output_path, 'wb') as f:
        f.write(output)
    print(f"Scritto: {output_path}")
