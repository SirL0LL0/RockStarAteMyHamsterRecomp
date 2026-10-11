#!/usr/bin/env python3
"""attacchi_da.py - attacchi dopo il primo suono, per confrontare il ritmo.

    python tools/attacchi_da.py file.wav da_secondo [durata]
"""
import struct
import sys
import wave

f, da = sys.argv[1], float(sys.argv[2])
dur = float(sys.argv[3]) if len(sys.argv) > 3 else 8.0
w = wave.open(f)
fr, n = w.getframerate(), w.getnframes()
d = struct.unpack('<%dh' % (n * 2), w.readframes(n))
k = int(fr * 0.005)
env = []
for i in range(int(da * fr), min(n - k, int((da + 30) * fr)), k):
    env.append(sum(abs(d[2 * j]) for j in range(i, i + k, 2)) / (k / 2))
t0 = next(i for i, v in enumerate(env) if v > 150)
att = []
for i in range(t0 + 2, len(env)):
    if (i - t0) * 0.005 > dur:
        break
    if env[i] > 2.0 * max(env[i - 2], 40) and env[i] > 150:
        if not att or (i - t0) * 0.005 - att[-1] > 0.08:
            att.append((i - t0) * 0.005)
print(' '.join('%.2f' % a for a in att))
