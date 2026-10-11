#!/usr/bin/env python3
"""confronta_tempo.py - di quanto e' piu' veloce o lenta una registrazione
rispetto a un'altra (stessa musica, attacchi in istanti diversi).

    python tools/confronta_tempo.py riferimento.wav prova.wav

Inviluppo di energia a 10 ms per entrambe; cerca il fattore di scala del
tempo (0,70-1,40) e lo spostamento che massimizzano la correlazione.
Fattore 1,00 = stesso tempo; >1 = la prova e' piu' lenta.
"""
import struct
import sys
import wave


def inviluppo(f, passo=0.01):
    w = wave.open(f)
    fr, n = w.getframerate(), w.getnframes()
    d = struct.unpack('<%dh' % (n * 2), w.readframes(n))
    k = int(fr * passo)
    env = []
    for i in range(0, n - k, k):
        env.append(sum(abs(d[2 * j]) + abs(d[2 * j + 1]) for j in range(i, i + k, 4)) / (k / 4))
    # solo le variazioni (attacchi), normalizzate
    att = [max(0.0, env[i] - env[i - 1]) for i in range(1, len(env))]
    m = max(att) or 1
    return [a / m for a in att]


rif = inviluppo(sys.argv[1])
pro = inviluppo(sys.argv[2])
inizio_rif = next(i for i, v in enumerate(rif) if v > 0.2)
inizio_pro = next(i for i, v in enumerate(pro) if v > 0.2)
print("primo attacco: riferimento %.2f s, prova %.2f s" % (inizio_rif * 0.01, inizio_pro * 0.01))
lung = min(len(rif) - inizio_rif, 2500)
migliore = (0, 1, 0)
s = 0.70
while s <= 1.40:
    for off in range(-30, 31):
        tot = 0.0
        for i in range(0, lung):
            j = inizio_pro + off + int(i * s)
            if 0 <= j < len(pro):
                tot += rif[inizio_rif + i] * pro[j]
        if tot > migliore[0]:
            migliore = (tot, s, off)
    s += 0.01
print("fattore di tempo: %.2f  (1,00 = uguale, >1 = la prova e' piu' lenta)" % migliore[1])
