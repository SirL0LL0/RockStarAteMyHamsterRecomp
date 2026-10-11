#!/usr/bin/env python3
"""tempo_audio.py - quanto distano gli attacchi delle note in un WAV.

    python tools/tempo_audio.py build/audio.wav [da_secondo] [a_secondo]

Inviluppo di energia a finestre di 5 ms, attacchi dove l'energia sale di
colpo; stampa gli intervalli e il passo di griglia piu' probabile.
Un player a 6 tick per riga da' 120 ms in PAL (50 Hz) e 100 ms in NTSC.
"""
import struct
import sys
import wave

f = sys.argv[1] if len(sys.argv) > 1 else 'build/audio.wav'
da = float(sys.argv[2]) if len(sys.argv) > 2 else 0
a = float(sys.argv[3]) if len(sys.argv) > 3 else 1e9
w = wave.open(f)
fr = w.getframerate()
n = w.getnframes()
d = struct.unpack('<%dh' % (n * 2), w.readframes(n))
fin = int(fr * 0.005)
env = []
for i in range(0, n - fin, fin):
    s = 0
    for k in range(i, i + fin):
        s += abs(d[2 * k]) + abs(d[2 * k + 1])
    env.append(s / fin)
attacchi = []
for i in range(2, len(env)):
    t = i * 0.005
    if da <= t <= a and env[i] > 1.8 * max(env[i - 2], 50) and env[i] > 300:
        if not attacchi or t - attacchi[-1] > 0.04:
            attacchi.append(t)
iv = [round((b - x) * 1000) for x, b in zip(attacchi, attacchi[1:])]
print("attacchi:", len(attacchi))
print("intervalli (ms):", iv[:40])
# passo di griglia: il valore fra 80 e 160 ms che spiega meglio gli intervalli
migliore = min(range(80, 161), key=lambda p: sum(min(x % p, p - x % p) for x in iv if x > 40))
print("passo piu' probabile: %d ms (PAL 6 tick = 120, NTSC 6 tick = 100)" % migliore)
