# -*- coding: utf-8 -*-
"""
mappa_messaggi.py - chi mostra quale messaggio, e come.

    python3 mappa_messaggi.py [rockstar_base.bin] [mappa.json]

Dal disassemblato ricorsivo cerca le chiamate alle routine che mostrano i
messaggi e ricostruisce il numero di messaggio (registro d4, numerazione del
gioco) e il modo:

    $D5F4  fumetto      box in alto, parla Clive o chi per lui
    $D348  fumetto      come sopra, poi aspetta un po' o il pulsante
    $9944  menu         finestra di scelta: d4 = opzioni, d6 = quante
    $993C  menu SI/NO   il messaggio 7, dopo una domanda
    $D816  finestra     testo in una finestra (introduzione, fine partita)
    $C4F4  riga         testo in un punto fisso dello schermo (classifiche)
    $D638  diretto      composizione senza cornice

Le ancore (byte scritti a runtime dentro i messaggi) sono ricavate dalle
istruzioni "lea $indirizzo,a0 / move.b d6,(a0)" che puntano nella regione.
"""
import json
import re
import sys
from collections import defaultdict

sys.path.insert(0, __file__.rsplit('/', 1)[0])
from disasm_rsamh import analizza, carica, BASE

MODI = {0xD5F4: 'fumetto', 0xD348: 'fumetto+pausa', 0x9944: 'menu',
        0x993C: 'menu SI/NO', 0xD816: 'finestra', 0xC4F4: 'riga', 0xD638: 'diretto'}
INTERNE = {0xD5F4, 0xD348, 0x9944, 0x993C, 0xD816, 0xC4F4, 0xD638, 0xD5CA}


def _imm(ops, reg):
    mm = re.match(r'#(\$?)([0-9a-f]+), ' + reg + r'$', ops)
    if not mm: return None
    return int(mm.group(2), 16 if mm.group(1) else 10)


def valore_reg(d, lista, pos, reg):
    k = pos - 1; agg = 0; passi = 0
    while k >= 0 and passi < 30:
        a = lista[k]
        s, m, ops = d.ins[a]
        if m.startswith(('bsr', 'jsr', 'rts', 'bra', 'jmp')):
            return None, 'dopo una chiamata o un salto'
        v = _imm(ops, reg)
        if v is not None:
            if m.startswith('move') or m == 'moveq': return v + agg, ''
            if m.startswith(('addq', 'addi')): agg += v
            elif m.startswith(('subq', 'subi')): agg -= v
            else: return None, f'{m} {ops}'
        elif ops.endswith(', ' + reg):
            return None, f'{m} {ops}'
        k -= 1; passi += 1
    return None, 'non trovato'


def analisi(img):
    d = analizza(img)
    lista = sorted(d.ins)
    pos = {a: i for i, a in enumerate(lista)}
    fun = sorted(d.funzioni | {BASE})

    def funz(a):
        return max((x for x in fun if x <= a), default=BASE)

    usi = []
    for da, a in sorted(d.chiamate):
        if a not in MODI: continue
        f = funz(da)
        if f in INTERNE: continue
        if a == 0x993C:
            usi.append({'msg': 7, 'modo': MODI[a], 'sito': da, 'funzione': f}); continue
        v, perche = valore_reg(d, lista, pos[da], 'd4')
        u = {'msg': v, 'modo': MODI[a], 'sito': da, 'funzione': f}
        if v is None: u['calcolato'] = perche
        if a == 0x9944:
            n, _ = valore_reg(d, lista, pos[da], 'd6'); u['opzioni'] = n
        usi.append(u)

    # ancore: lea $X,a0 (o a1) seguito da move.b d6,(a0)
    ancore = []
    for i, a in enumerate(lista[:-1]):
        s, m, ops = d.ins[a]
        mm = re.match(r'\$([0-9a-f]+)(?:\(pc\)|\.l)?, (a[01])$', ops)
        if m == 'lea.l' and mm:
            x = int(mm.group(1), 16)
            if 0xDD70 <= x < 0xEA57:
                for j in (1, 2):
                    s2, m2, o2 = d.ins[lista[i + j]]
                    if m2 == 'move.b' and o2.endswith('(%s)' % mm.group(2)):
                        ancore.append({'offset': x - BASE, 'sito': a, 'funzione': funz(a)})
                        break
    # sequenza dei messaggi dentro ogni funzione, nell'ordine del codice
    seq = defaultdict(list)
    for u in usi:
        seq[u['funzione']].append(u)
    chiamanti = defaultdict(set)
    for da, a in d.chiamate:
        chiamanti[a].add(funz(da))
    return {'usi': usi, 'ancore': ancore, 'sequenze': seq,
            'chiamanti': chiamanti, 'disasm': d}


def per_messaggio(an):
    """messaggio -> lista di stringhe di contesto, pronte per l'editor."""
    out = defaultdict(list)
    seq = an['sequenze']
    for f, lista in seq.items():
        for k, u in enumerate(lista):
            if u['msg'] is None: continue
            prima = [x for x in lista[:k] if x['msg'] is not None][-1:]
            dopo = [x for x in lista[k + 1:] if x['msg'] is not None][:1]
            t = f"{u['modo']} (${u['sito']:05x}, routine ${f:05x})"
            if u['modo'] == 'menu' and u.get('opzioni'):
                t += f", {u['opzioni']} opzioni"
            if dopo and dopo[0]['modo'].startswith('menu'):
                t += f"; poi il menu #{dopo[0]['msg']}"
            if u['modo'].startswith('menu') and prima:
                t += f"; risponde al #{prima[0]['msg']}"
            out[u['msg']].append(t)
    for a in an['ancore']:
        out.setdefault(('ancora', a['offset']), []).append(f"${a['sito']:05x}")
    return out


NOMI = {
    0x08100: 'ciclo principale', 0x08466: 'introduzione', 0x085c6: 'concerto benefico',
    0x086ec: 'cassa', 0x089aa: 'nome della band', 0x08d28: 'acquisto strumenti',
    0x08dec: 'menu principale', 0x08ecc: 'uscita dal gioco', 0x08eea: 'salva/carica',
    0x08f88: 'contratto discografico', 0x091e0: 'prove', 0x092ce: 'bancarotta',
    0x092f6: 'fine partita', 0x0931e: 'fine per vecchiaia', 0x09338: 'disco di platino',
    0x09356: 'cattive notizie', 0x09440: 'sala proiezioni (scelta delle rock star)',
    0x0977a: 'regali', 0x099bc: 'tour', 0x09c92: 'stipendi', 0x09fa4: 'titolo del pezzo',
    0x0a0ea: 'registrazione album', 0x0a2e0: 'causa per plagio', 0x0a346: 'irruzione della polizia',
    0x0a396: 'uscita album/singolo e video', 0x0a5a2: 'nastro rubato', 0x0a630: 'capricci in tour',
    0x0ac94: 'classifica', 0x0c202: 'trovata pubblicitaria', 0x0c326: 'titoli di giornale',
    0x0c37e: 'titoli di giornale', 0x0c428: 'giornale', 0x0c71c: 'manifesto del concerto',
    0x0d138: 'sponsor', 0x0d24c: 'pirati coreani', 0x0c120: 'pulizia del fumetto',
}
ANCORE_DESCR = {
    23969: 'nome della casa discografica', 24271: 'tipo di locale (bar, locale, ...)',
    24364: 'nome di una rock star', 25609: 'nome di un membro della band',
    25638: 'nome di un membro della band', 25681: "' ' oppure 'S ' (plurale inglese)",
    26055: 'nome dello sponsor', 26709: 'nome di una rock star', 26738: 'nome di una rock star',
    26804: 'nome di una rock star', 26864: 'nome di una rock star',
}


def contesto(img):
    """{numero messaggio: [righe]} per l'editor."""
    import script_rsamh as S
    an = analisi(img)
    out = defaultdict(list)
    for f, lista in an['sequenze'].items():
        nome = NOMI.get(f, f'routine ${f:05x}')
        for k, u in enumerate(lista):
            if u['msg'] is None: continue
            prec = [x for x in lista[:k] if x['msg'] is not None][-1:]
            succ = [x for x in lista[k + 1:] if x['msg'] is not None][:1]
            t = f"{nome}: {u['modo']}"
            if u['modo'] == 'menu' and u.get('opzioni'):
                t += f" con {u['opzioni']} opzioni"
            if prec: t += f"; dopo il #{prec[0]['msg']}"
            if succ: t += f"; poi il #{succ[0]['msg']}"
            if t not in out[u['msg']]:
                out[u['msg']].append(t)
    mg = S.messaggi_gioco(img)
    for a in an['ancore']:
        for g, m in enumerate(mg):
            if m['offset'] <= a['offset'] < m['fine']:
                d = ANCORE_DESCR.get(a['offset'], 'dato di gioco')
                t = f"il gioco riscrive un token: qui compare {d}"
                if t not in out[g]: out[g].append(t)
    return dict(out)


def documento(img_orig, img_it, tab_it):
    """Testo leggibile: il flusso dei dialoghi routine per routine, con
    l'inglese e l'italiano. Serve a tradurre sapendo chi parla e quando."""
    import script_rsamh as S
    import rsamh_editor as r
    an = analisi(img_orig)
    en = r.leggi_tabella(img_orig)
    mo = S.messaggi_gioco(img_orig)
    mi = S.messaggi_gioco(img_it)
    righe = ["FLUSSO DEI DIALOGHI - ricavato dal codice del gioco",
             "numeri = messaggi come li numera il gioco (#n nell'editor)", ""]
    for f in sorted(an['sequenze']):
        ch = sorted(an['chiamanti'].get(f, []))
        righe.append(f"== {NOMI.get(f, 'routine')}  (${f:05x}, chiamata da "
                     + ', '.join(NOMI.get(c, f'${c:05x}') for c in ch[:5]) + ")")
        for u in an['sequenze'][f]:
            if u['msg'] is None:
                righe.append(f"   {u['modo']:<14} (numero calcolato a runtime)")
                continue
            e = r.a_video(r.rendi(en, mo[u['msg']]['token']))
            i = r.a_video(r.rendi(tab_it, mi[u['msg']]['token']))
            righe.append(f"   {u['modo']:<14} #{u['msg']}")
            righe.append(f"        EN {e}")
            righe.append(f"        IT {i}")
        righe.append('')
    return '\n'.join(righe) + '\n'


def commenti_listato(img):
    """Commenti per il listato: numero e testo del messaggio a ogni chiamata."""
    import script_rsamh as S
    import rsamh_editor as r
    an = analisi(img)
    en = r.leggi_tabella(img)
    mg = S.messaggi_gioco(img)
    c = {}
    for u in an['usi']:
        if u['msg'] is None:
            c[u['sito']] = f"{u['modo']}: messaggio calcolato ({u.get('calcolato')})"
        else:
            c[u['sito']] = f"{u['modo']} #{u['msg']}: " + r.a_video(r.rendi(en, mg[u['msg']]['token']))[:60]
    for a in an['ancore']:
        c[a['sito']] = f"ancora: riscrive il byte {a['offset']} (" + ANCORE_DESCR.get(a['offset'], '') + ")"
    for f, n in NOMI.items():
        c.setdefault(f, 'ROUTINE: ' + n)
    return c, an['disasm']


def immagine_italiana(orig, cartella='.'):
    """Immagine con testi fissi e riordini applicati, come la costruisce
    l'editor (serve solo al documento con l'italiano)."""
    import json, os
    import script_rsamh as S
    import rsamh_editor as r
    img = bytearray(S.patch_fissi(orig))
    p = os.path.join(cartella, 'rockstar_script_ITA.json')
    if not os.path.isfile(p):
        return bytes(img)
    en = r.leggi_tabella(orig)
    fin = lambda t: r.rendi(en, [x for x in t if x != S.RIEMPITIVO]).endswith(('! ', '? ', '. '))
    for k, v in json.load(open(p)).items():
        a, b = map(int, k.split('-'))
        vs = [(x, y) for x, y in v]
        o = S.leggi_blocco(orig, a, b)
        if (a, b) in S.MODELLI:
            img[a:b] = S.serializza_modelli(S.bilancia_modelli(vs, o, a, b), orig, a, b)
        elif (a, b) in [tuple(x) for x in S.blocchi(orig)]:
            img[a:b] = S.serializza(S.bilancia(vs, o, fin), orig, a, b)
    return bytes(img)


if __name__ == '__main__':
    import json, os
    radice = os.path.dirname(os.path.abspath(__file__))
    sys.path.insert(0, radice)
    import rsamh_editor as r
    orig = carica(sys.argv[1] if len(sys.argv) > 1 else __import__('percorsi').BASE)
    json.dump({str(k): v for k, v in sorted(contesto(orig).items())},
              open(os.path.join(radice, 'contesto_messaggi.json'), 'w', encoding='utf-8'),
              indent=1, ensure_ascii=False)
    pt = os.path.join(radice, 'rockstar_text_table_ESTESA.json')
    tab = json.load(open(pt, encoding='utf-8')) if os.path.isfile(pt) else r.leggi_tabella(orig)
    open(os.path.join(__import__('percorsi').DATI, 'mappa_messaggi.txt'), 'w')  # testi inglesi: fuori dal repository.write(
        documento(orig, immagine_italiana(orig, radice), tab))
    print("scritti contesto_messaggi.json e mappa_messaggi.txt")
