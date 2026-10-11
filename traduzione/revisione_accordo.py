# -*- coding: utf-8 -*-
"""
revisione_accordo.py - la revisione di genere e numero (ottobre 2026).

Applica ai tre file della traduzione le modifiche che usano i marcatori
{..} di accordo.py. Si puo' rilanciare: ogni modifica controlla prima che il
testo sia quello di partenza e salta se e' gia' stata fatta.

    python3 tools/revisione_accordo.py            # mostra cosa farebbe
    python3 tools/revisione_accordo.py scrivi     # scrive i file
"""
import json
import os
import sys

QUI = os.path.dirname(os.path.abspath(__file__))
sys.path[:0] = [QUI]
import percorsi

# Promemoria: due alternative = singolare|plurale; per maschile|femminile ne
# servono tre (m|f|plurale) anche dove il plurale non capita mai.
#
# tabella ESTESA: (tipo, indice, prima, dopo). Per i gruppi prima/dopo sono
# liste di item. S = stringa piatta (indice come nei token).
ESTESA = [
    # band: singolare/plurale, maschile/femminile
    ('S', 339, "E' ", "{E'|SONO} "),                                   # 30 (e 21, 211, 213)
    ('G', 40, ['PERFETTO ', 'AFFIATATO ', 'IMPECCABILE '],
              ['PERFETT{O|A|I|E} ', 'AFFIATAT{O|A|I|E} ', 'IMPECCABIL{E|E|I|I} ']),
    ('S', 143, 'SUONATE ', 'SUONA{|TE} '),                              # 36
    ('G', 41, ['VAI ', 'ESCI '], ['{VAI|ANDATE} ', '{ESCI|USCITE} ']),  # 41
    ('G', 42, ['STENDILI', 'FALLI NERI', 'CONQUISTALI'],
              ['STEND{ILI|ETELI}', '{FALLI|FATELI} NERI', 'CONQUISTA{LI|TELI}']),
    ('S', 106, 'DACCI DENTRO ', '{DACCI|DATECI} DENTRO '),
    ('G', 44, ['INCIDI ', 'REGISTRA ', 'SFORNA ', 'SUONA ', 'FISSA ', 'METTI SU NASTRO '],
              ['INCID{I|ETE} ', 'REGISTRA{|TE} ', 'SFORNA{|TE} ', 'SUONA{|TE} ',
               'FISSA{|TE} ', '{METTI|METTETE} SU NASTRO ']),               # 48
    ('S', 144, "RIUSCIRA' A ", "{RIUSCIRA'|RIUSCIRANNO} A "),           # 54
    ('S', 417, 'REGALARE ',
     'REGALARE {AL NOSTRO|ALLA NOSTRA|AI NOSTRI|ALLE NOSTRE} ROCK STAR'),  # 126
    # una star sola: maschile/femminile
    ('S', 426, 'PRENDERE ', 'PRENDER{LO|LA|LI}'),                          # 21
    ('S', 385, "SE N'E' ANDATA A ", "SE N'E' ANDAT{O|A|I} A "),           # 208
    ('S', 392, 'FALLITO ', 'FALLIT{O|A|I} '),                             # 210
    ('G', 35, ['BELLO ', 'TESTONE ', 'ZUCCAVUOTA ', 'PAPERO ', 'TACCHINO ', 'PEZZENTE '],
              ['BELL{O|A|I} ', 'TESTON{E|A|I} ', 'ZUCCAVUOTA ', 'PAPER{O|A|I} ',
               'TACCHIN{O|A|I} ', 'PEZZENTE ']),                          # 25, 210, 212
    ('S', 374, 'SEI LICENZIATO ', 'SEI LICENZIAT{O|A|I} '),               # 201, 212
    # CREPA PURE: all'ente benefico (plurale), al discografico, a Clive, alla star
    ('G', 6, ['CREPA PURE ', 'MANGIA MERDA ', 'SPARISCI ', 'CHIUDI IL BECCO ', 'VAI A CAGARE '],
             ['CREPA{|TE} PURE ', 'MANGIA{|TE} MERDA ', 'SPAR{ISCI|ITE} ',
              'CHIUD{I|ETE} IL BECCO ', '{VAI|ANDATE} A CAGARE ']),
    # CREPATE PURE, BRANCO DI CIALTRONI!  ("YOU GROUP OF SCUMBAGS"): il gruppo 15
    # lo usano solo il #9 e il #10, la virgola qui non disturba nessuno (nel
    # gruppo 6 finirebbe nel titolo di canzone "CREPA PURE!")
    ('G', 15, ['CIALTRONE ', 'FANNULLONE ', 'SCROCCONE '],
              [', BRANCO DI CIALTRONI ', ', BANDA DI FANNULLONI ', ', MASNADA DI SCROCCONI ']),
    # "rock star" e' femminile
    ('S', 100, 'QUANTI ', 'QUANT{I|E|I} '),                             # 23 (F), 39 (M)
    ('S', 411, 'GLI STESSI ', 'LE STESSE '),                            # 33
    # 3 ottobre, sera
    ('G', 43, ['GUAI ', 'ARIA BRUTTA ', 'ARIA PESANTE '], ['GUAI ', 'BRUTTA ARIA ', 'ARIA PESANTE ']),
    # menu dei giorni (#27): celle da 9 caratteri, la finestra 5 ora e' larga 9
    ('S', 73, 'G.   ', 'GIORNO '),
    ('S', 74, 'GG.  ', 'GIORNI '),
    # #46 "INCIDIAMO UN ALBUM"; la stessa stringa e' la voce INCIDI del menu #45
    # (soggetti fissi: 45 M, 46 P)
    ('S', 114, 'INCIDI ', 'INCIDI{|AMO} '),
    # #54 "<BAND> RIUSCIRA' A ESSERE PRIMO/A/I/E"; nel #25 parliamo noi
    ('G', 38, ['SFONDARE ', 'FARCELA ', 'ESSERE PRIMI '],
              ['SFONDARE ', 'FARCELA ', 'ESSERE PRIM{O|A|I|E} ']),
    ('S', 58, 'STIAMO PER ', 'STIAMO PER {=P}'),
    # menu #171: la prima riga deve fare esattamente 21 (vedi FORMATO, menu)
    ('S', 208, 'NON FARE ', 'NON FAR '),
]

# tabella compatta: solo cambi della stessa lunghezza (e' piena al byte)
COMPATTA = [
    ('S', 426, 'PRENDERE ', 'PRENDERLO'),
    ('G', 43, ['GUAI ', 'ARIA BRUTTA ', 'ARIA PESANTE '], ['GUAI ', 'BRUTTA ARIA ', 'ARIA PESANTE ']),
    # i giorni per intero (+4 byte), presi da due frasi che non cambiano senso
    ('S', 73, 'G.   ', 'GIORNO '),
    ('S', 74, 'GG.  ', 'GIORNI '),
    ('S', 22, "C'E' UN TIPO AL TELEFONO ", "C'E' UNO AL TELEFONO "),
    ('S', 25, 'NON VOGLIAMO AVERE A CHE FARE CON ', 'NON VOGLIAMO AVER A CHE FARE CON '),
    ('S', 208, 'NON FARE ', 'NON FAR '),
]

# script: (messaggio, token prima, token dopo)
G = lambda i: 0x8000 | i
SCRIPT = [
    # DA URLO CAPO! <STAR>CHIEDE `<DATO>A SETTIMANA! VOGLIAMO PRENDERLO?
    (21, [G(4), G(0), 6, 134, 339, 0x404B, 7, 403, 0x2000, 404, 6, G(34), 426,
          134, 274, 276, G(4), 9],
         [G(4), G(0), 6, 0x404B, 403, 0x2000, 404, 6, G(34), 426, 9]),
]


def _piatte(voci):
    """indice token -> (voce, item) per le stringhe piatte"""
    gr = [v for v in voci if v['type'] == 'GROUP']
    out = [(gr[-1], k) for k in range(len(gr[-1]['items']))]
    out += [(v, None) for v in voci if v['type'] == 'STR']
    return gr, out


def applica_tabella(voci, modifiche, nome, log):
    gr, pi = _piatte(voci)
    for tipo, i, prima, dopo in modifiche:
        if tipo == 'G':
            v = gr[i]
            if v['items'] == dopo:
                continue
            if v['items'] != prima:
                log.append(f"  {nome} G{i}: testo diverso dall'atteso, lasciato com'e': {v['items']}")
                continue
            if len(dopo) != len(prima):
                raise ValueError(f"G{i}: il numero di item non puo' cambiare")
            v['items'] = list(dopo)
            log.append(f"  {nome} G{i}: {prima} -> {dopo}")
        else:
            v, k = pi[i]
            att = v['items'][k] if k is not None else v['text']
            if att == dopo:
                continue
            if att != prima:
                log.append(f"  {nome} S{i}: testo diverso dall'atteso, lasciato com'e': {att!r}")
                continue
            if k is not None: v['items'][k] = dopo
            else: v['text'] = dopo
            log.append(f"  {nome} S{i}: {prima!r} -> {dopo!r}")


def applica_script(script, orig, log):
    import script_rsamh as S
    import rsamh_editor as R
    en = R.leggi_tabella(orig)
    fin = lambda t: R.rendi(en, [x for x in t if x != S.RIEMPITIVO]).endswith(('! ', '? ', '. '))
    toccati = set()
    n = 0
    for k, voci in script.items():
        a, b = map(int, k.split('-'))
        if (a, b) in S.MODELLI:
            continue
        for j, (t, d) in enumerate(voci):
            if t == 'FF':
                n += 1; continue
            for m, prima, dopo in SCRIPT:
                if m != n: continue
                senza = [x for x in d if x != S.RIEMPITIVO]
                if senza == dopo:
                    continue
                if senza != prima:
                    log.append(f"  script #{m}: token diversi dall'atteso, lasciato com'e'")
                    continue
                voci[j] = ['MSG', list(dopo)]
                toccati.add(k)
                log.append(f"  script #{m}: {len(prima)} -> {len(dopo)} token")
    for k in toccati:
        a, b = map(int, k.split('-'))
        o = S.leggi_blocco(orig, a, b)
        bil = S.bilancia([(t, d) for t, d in script[k]], o, fin)
        S.serializza(bil, orig, a, b)          # verifica dimensione e ancore
        script[k] = [[t, d] for t, d in bil]


def carica(p):
    r = json.load(open(p, encoding='utf-8'))
    return r, (r['entries'] if isinstance(r, dict) else r)


def main():
    scrivi = len(sys.argv) > 1 and sys.argv[1] == 'scrivi'
    orig = percorsi.inglese()
    log = []
    fe, est = carica(os.path.join(QUI, 'rockstar_text_table_ESTESA.json'))
    fc, comp = carica(os.path.join(QUI, 'rockstar_text_table_ITA.json'))
    sc = json.load(open(os.path.join(QUI, 'rockstar_script_ITA.json'), encoding='utf-8'))
    applica_tabella(est, ESTESA, 'estesa', log)
    applica_tabella(comp, COMPATTA, 'compatta', log)
    applica_script(sc, orig, log)
    print('\n'.join(log) if log else 'niente da fare')
    if scrivi:
        json.dump(fe, open(os.path.join(QUI, 'rockstar_text_table_ESTESA.json'), 'w', encoding='utf-8'),
                  indent=1, ensure_ascii=False)
        json.dump(fc, open(os.path.join(QUI, 'rockstar_text_table_ITA.json'), 'w', encoding='utf-8'),
                  indent=1, ensure_ascii=False)
        json.dump(sc, open(os.path.join(QUI, 'rockstar_script_ITA.json'), 'w'), indent=1)
        print('scritto')


if __name__ == '__main__':
    main()
