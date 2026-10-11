#!/usr/bin/env python3
"""tono_registrazione.py - frequenza dominante del primo suono di una registrazione.

    python tools/tono_registrazione.py file.wav [da_secondo]

Trova il primo istante con audio (dopo da_secondo), salta 30 ms e misura la
frequenza dominante su 250 ms (Goertzel, passo 0,5%).
"""
import math
import struct
import sys
import wave

f = sys.argv[1]
da = float(sys.argv[2]) if len(sys.argv) > 2 else 0.0
w = wave.open(f)
fr, n = w.getframerate(), w.getnframes()
d = struct.unpack('<%dh' % (n * 2), w.readframes(n))
k = int(fr * 0.005)
i0 = int(da * fr)
inizio = None
for i in range(i0, n - k, k):
    if sum(abs(d[2 * j]) for j in range(i, i + k)) / k > 150:
        inizio = i
        break
if inizio is None:
    sys.exit("nessun suono")
RATE = 12000
passo = fr / RATE
x = [d[2 * (inizio + int(0.03 * fr) + int(j * passo))] for j in range(int(0.25 * RATE))]
med = sum(x) / len(x)
x = [(v - med) * (0.5 - 0.5 * math.cos(2 * math.pi * j / (len(x) - 1))) for j, v in enumerate(x)]
migliore, fm, fq = 0, 0, 60.0
while fq < 2500:
    c = 2 * math.cos(2 * math.pi * fq / RATE)
    s1 = s2 = 0.0
    for v in x:
        s1, s2 = v + c * s1 - s2, s1
    p = s1 * s1 + s2 * s2 - c * s1 * s2
    if p > migliore:
        migliore, fm = p, fq
    fq *= 1.005
print("primo suono a %.2f s, frequenza dominante %.1f Hz" % (inizio / fr, fm))
