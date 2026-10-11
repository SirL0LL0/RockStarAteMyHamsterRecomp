#!/usr/bin/env python3
"""genera_font.py - font bitmap per la finestra di debug del runner.

    python tools/genera_font.py [font.ttf]   ->  amigarecomp/runner/font_debug.h

ASCII 32-126, celle 8x14, un byte per riga (bit 7 = pixel a sinistra).
Il file generato si versiona: il runner non dipende da nessun font esterno.
"""
import os
import sys
from PIL import Image, ImageDraw, ImageFont

W, H = 8, 14
ttf = sys.argv[1] if len(sys.argv) > 1 else r'C:\Windows\Fonts\consola.ttf'
f = ImageFont.truetype(ttf, 13)
righe = ['/* font_debug.h - GENERATO da tools/genera_font.py (%s, 8x14). */' % os.path.basename(ttf),
         '#pragma once', '#include <stdint.h>', '#define FONT_DEBUG_L 8', '#define FONT_DEBUG_A 14',
         'static const uint8_t font_debug[95][14] = {']
for c in range(32, 127):
    im = Image.new('L', (W, H), 0)
    ImageDraw.Draw(im).text((0, -1), chr(c), font=f, fill=255)
    byte = []
    for y in range(H):
        b = 0
        for x in range(W):
            if im.getpixel((x, y)) > 110:
                b |= 0x80 >> x
        byte.append(b)
    righe.append('    {%s}, /* %r */' % (','.join('0x%02x' % b for b in byte), chr(c)))
righe.append('};')
out = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'amigarecomp', 'runner', 'font_debug.h')
open(out, 'w', encoding='utf-8', newline='\n').write('\n'.join(righe) + '\n')
print('scritto', os.path.normpath(out))
