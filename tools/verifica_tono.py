#!/usr/bin/env python3
"""verifica_tono.py - l'altezza prodotta da Paula e' quella giusta?

    python tools/verifica_tono.py build/audio.wav build/memoria_fine.bin CICLI CANALE INDIRIZZO LUNGH PERIODO

Prende il campione grezzo dalla memoria (INDIRIZZO, LUNGH parole), che deve
suonare a 3.546.895/PERIODO byte al secondo, e confronta la sua frequenza
dominante con quella del WAV del runner nello stesso istante (canali 0/3 a
sinistra, 1/2 a destra). Python puro (Goertzel su una griglia di frequenze).
"""
import math
import struct
import sys
import wave

wavf, memf = sys.argv[1], sys.argv[2]
cicli, canale, ind, lung, per = (int(x, 0) for x in sys.argv[3:8])
m = open(memf, 'rb').read()
campione = [b - 256 if b > 127 else b for b in m[ind:ind + 2 * lung]]
freq_byte = 3546895.0 / per
finestra = min(len(campione) / freq_byte, 0.25)


def ricampiona(x, da, a):
    n = int(len(x) * a / da)
    return [x[min(int(i * da / a), len(x) - 1)] for i in range(n)]


def picco(x, rate):
    media = sum(x) / len(x)
    x = [(v - media) * (0.5 - 0.5 * math.cos(2 * math.pi * i / (len(x) - 1))) for i, v in enumerate(x)]
    migliore, fm = 0, 0
    f = 60.0
    while f < 2500:
        k = 2 * math.cos(2 * math.pi * f / rate)
        s1 = s2 = 0.0
        for v in x:
            s0 = v + k * s1 - s2
            s2, s1 = s1, s0
        p = s1 * s1 + s2 * s2 - k * s1 * s2
        if p > migliore:
            migliore, fm = p, f
        f *= 1.01                       # passo dell'1%
    return fm


RATE = 12000
atteso = picco(ricampiona(campione[:int(finestra * freq_byte)], freq_byte, RATE), RATE)
w = wave.open(wavf)
fr = w.getframerate()
w.setpos(int(cicli / 7093790.0 * fr) + int(0.005 * fr))
n = int(finestra * fr)
d = struct.unpack('<%dh' % (n * 2), w.readframes(n))
lato = 0 if canale in (0, 3) else 1
uscita = ricampiona([d[2 * i + lato] for i in range(n)], fr, RATE)
misurato = picco(uscita, RATE)
print("campione: %d byte a %.0f Hz" % (len(campione), freq_byte))
print("frequenza dominante attesa:  %.1f Hz" % atteso)
print("frequenza dominante nel WAV: %.1f Hz   rapporto %.3f" % (misurato, misurato / atteso))
