#!/usr/bin/env python3
"""attacchi.py - attacchi forti di una registrazione, in secondi dal primo.

    python tools/attacchi.py file.wav [quanti] [soglia]
"""
import struct
import sys
import wave

f = sys.argv[1]
quanti = int(sys.argv[2]) if len(sys.argv) > 2 else 25
soglia = float(sys.argv[3]) if len(sys.argv) > 3 else 0.35
w = wave.open(f)
fr, n = w.getframerate(), w.getnframes()
d = struct.unpack('<%dh' % (n * 2), w.readframes(n))
k = int(fr * 0.005)
env = [sum(abs(d[2 * j]) + abs(d[2 * j + 1]) for j in range(i, i + k, 2)) / (k / 2) for i in range(0, n - k, k)]
att = [max(0.0, env[i] - env[i - 3]) for i in range(3, len(env))]
m = max(att)
t = []
for i, a in enumerate(att):
    if a > soglia * m and (not t or (i + 3) * 0.005 - t[-1] > 0.06):
        t.append((i + 3) * 0.005)
t0 = t[0]
print("primo attacco a %.2f s" % t0)
print(' '.join('%.2f' % (x - t0) for x in t[:quanti]))
