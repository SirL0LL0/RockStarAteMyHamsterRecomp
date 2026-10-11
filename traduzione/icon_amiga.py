"""Minimal Amiga .info parser: read/replace DefaultTool and ToolTypes."""
import struct, sys


def _img_size(d, o):
    w, h, depth = struct.unpack_from('>hhh', d, o + 4)
    data = struct.unpack_from('>I', d, o + 10)[0]
    n = ((w + 15) // 16) * 2 * h * depth if data else 0
    return 20 + n


def _str(d, o):
    n = struct.unpack_from('>I', d, o)[0]
    return d[o + 4:o + 4 + n], o + 4 + n


def parse(d):
    r = {}
    flags = struct.unpack_from('>H', d, 16)[0]
    r['type'] = d[48]
    deftool, tt, dd, tw = (struct.unpack_from('>I', d, x)[0] for x in (50, 54, 66, 70))
    gr, sr = struct.unpack_from('>II', d, 22)
    o = 78
    if dd:
        o += 56
    if gr:
        o += _img_size(d, o)
    if sr:
        o += _img_size(d, o)
    r['pre_end'] = o
    r['deftool'] = None
    if deftool:
        r['deftool'], o = _str(d, o)
    r['tt'] = None
    if tt:
        cnt = struct.unpack_from('>I', d, o)[0] // 4 - 1
        o += 4
        r['tt'] = []
        for _ in range(cnt):
            s, o = _str(d, o)
            r['tt'].append(s.rstrip(b'\0'))
    r['post'] = o
    return r


def rebuild(d, deftool=None, tooltypes=None):
    r = parse(d)
    out = bytearray(d[:r['pre_end']])
    dt = deftool if deftool is not None else (r['deftool'].rstrip(b'\0') if r['deftool'] else None)
    tt = tooltypes if tooltypes is not None else r['tt']
    struct.pack_into('>I', out, 50, 0x12345678 if dt else 0)
    struct.pack_into('>I', out, 54, 0x12345678 if tt else 0)
    if dt:
        s = dt + b'\0'
        out += struct.pack('>I', len(s)) + s
    if tt:
        out += struct.pack('>I', (len(tt) + 1) * 4)
        for t in tt:
            s = t + b'\0'
            out += struct.pack('>I', len(s)) + s
    out += d[r['post']:]
    return bytes(out)


if __name__ == '__main__':
    for p in sys.argv[1:]:
        r = parse(open(p, 'rb').read())
        print(p, 'type', r['type'], 'deftool', r['deftool'], 'tt', r['tt'])
