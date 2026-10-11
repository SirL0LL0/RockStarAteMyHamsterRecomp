#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
disegna_copertina.py - la copertina che il launcher mostra a disco
riconosciuto: disegnata qui, con forme semplici e il font Lato (SIL Open Font
License, negli assets di recomp-ui). Nessuna immagine presa da altri.

    python tools/disegna_copertina.py [game/copertina.jpg]
"""
import math
import os
import sys

from PIL import Image, ImageDraw, ImageFilter, ImageFont

QUI = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(QUI)
FONT = os.path.join(REPO, 'external', 'recomp-ui', 'assets', 'common', 'fonts', 'LatoLatin-Bold.ttf')
L, A = 512, 532


def stella(cx, cy, r1, r2, punte=5, ruota=-90):
    p = []
    for k in range(punte * 2):
        a = math.radians(ruota + k * 180 / punte)
        r = r1 if k % 2 == 0 else r2
        p.append((cx + r * math.cos(a), cy + r * math.sin(a)))
    return p


def font(n):
    return ImageFont.truetype(FONT, n)


def testo_centrato(d, y, s, f, colore, ombra=None):
    w = d.textlength(s, font=f)
    if ombra:
        d.text(((L - w) / 2 + 4, y + 4), s, font=f, fill=ombra)
    d.text(((L - w) / 2, y), s, font=f, fill=colore)


def main():
    uscita = sys.argv[1] if len(sys.argv) > 1 else os.path.join(REPO, 'game', 'copertina.jpg')
    im = Image.new('RGB', (L, A))
    d = ImageDraw.Draw(im)
    for y in range(A):                                   # fondo: viola notte -> blu
        t = y / A
        d.line([(0, y), (L, y)], fill=(int(40 + 20 * t), int(16 + 20 * t), int(70 + 60 * t)))

    luce = Image.new('L', (L, A), 0)                     # fascio del riflettore
    dl = ImageDraw.Draw(luce)
    dl.polygon([(L / 2 - 30, 0), (L / 2 + 30, 0), (L - 40, A - 60), (40, A - 60)], fill=90)
    luce = luce.filter(ImageFilter.GaussianBlur(30))
    im.paste((255, 230, 150), (0, 0), luce)
    d = ImageDraw.Draw(im)

    d.ellipse([60, A - 120, L - 60, A - 40], fill=(30, 20, 40))       # palco
    d.polygon(stella(L / 2, 300, 150, 62), fill=(255, 196, 40), outline=(120, 60, 0))
    d.polygon(stella(L / 2, 300, 128, 52), fill=(255, 220, 90))

    # il criceto, sulla stella: corpo, testa, orecchie, occhi, guance, zampe
    c = (205, 140, 80)
    scuro = (120, 70, 35)
    d.ellipse([L / 2 - 70, 290, L / 2 + 70, 400], fill=c, outline=scuro, width=3)
    d.ellipse([L / 2 - 52, 225, L / 2 + 52, 320], fill=c, outline=scuro, width=3)
    for dx in (-38, 38):
        d.ellipse([L / 2 + dx - 18, 212, L / 2 + dx + 18, 246], fill=c, outline=scuro, width=3)
        d.ellipse([L / 2 + dx - 9, 220, L / 2 + dx + 9, 238], fill=(240, 160, 160))
    d.ellipse([L / 2 - 46, 250, L / 2 + 46, 318], fill=(245, 225, 190))
    for dx in (-20, 20):
        d.ellipse([L / 2 + dx - 7, 255, L / 2 + dx + 7, 271], fill=(20, 10, 10))
        d.ellipse([L / 2 + dx - 3, 258, L / 2 + dx + 1, 262], fill=(255, 255, 255))
        d.ellipse([L / 2 + dx * 1.6 - 11, 276, L / 2 + dx * 1.6 + 11, 294], fill=(245, 150, 140))
    d.polygon([(L / 2 - 6, 278), (L / 2 + 6, 278), (L / 2, 285)], fill=(200, 80, 90))
    for dx in (-48, 48):
        d.ellipse([L / 2 + dx - 14, 385, L / 2 + dx + 14, 405], fill=c, outline=scuro, width=2)

    # microfono in mano
    d.line([(L / 2 + 60, 330), (L / 2 + 105, 270)], fill=(60, 60, 70), width=9)
    d.ellipse([L / 2 + 92, 240, L / 2 + 128, 276], fill=(170, 170, 185), outline=(60, 60, 70), width=3)
    d.ellipse([L / 2 + 46, 318, L / 2 + 72, 344], fill=c, outline=scuro, width=2)

    for k, (x, y, r) in enumerate([(70, 170, 12), (440, 150, 9), (420, 420, 11), (90, 430, 8), (465, 300, 7)]):
        d.polygon(stella(x, y, r, r * 0.45, ruota=-90 + 20 * k), fill=(255, 255, 210))

    f1, f2 = font(64), font(46)
    testo_centrato(d, 22, 'ROCK STAR', f1, (255, 70, 90), ombra=(20, 0, 10))
    testo_centrato(d, 90, 'ATE MY HAMSTER', f2, (255, 255, 255), ombra=(20, 0, 10))
    d.rectangle([0, A - 46, L, A], fill=(255, 136, 0))
    testo_centrato(d, A - 40, 'TRADUZIONE ITALIANA  -  AMIGA', font(24), (25, 15, 5))
    im.save(uscita, quality=92)
    print(uscita, im.size)


if __name__ == '__main__':
    main()
