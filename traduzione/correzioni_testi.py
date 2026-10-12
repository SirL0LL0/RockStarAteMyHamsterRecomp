#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
correzioni_testi.py - ritocchi alle tabelle dei testi, applicati sia alla
estesa (WHDLoad, port, eseguibile con memoria) sia alla compatta (piano B).

    python correzioni_testi.py          mostra cosa cambierebbe
    python correzioni_testi.py --scrivi  aggiorna i due json (copia .bak)

Vincoli (vedi build_ram.py e rsamh_editor.py):
  - compatta: il blocco dei gruppi 0-163 deve restare di 6021 byte (la base
    della tabella piatta e' cablata a $101DC) e il totale entro 10791;
  - menu dei temi del video (#73-#78): ogni combinazione entro 28 caratteri,
    altrimenti la riga del menu resta vuota.

Le voci sono indicate come nel json: gruppo n -> lista degli item,
stringa ('S', k) -> indice nella tabella piatta (voce 165 + k - 68).
"""
import json
import os
import shutil
import sys

QUI = os.path.dirname(os.path.abspath(__file__))

# (voce, item, vecchio, nuovo)   item None = stringa
CORREZIONI = [
    # temi del video, entro 28 caratteri e concordati (foto/pose/riprese: f. pl.)
    (58, 0, 'DEL TUTTO ', 'TROPPO '),            # TOTALLY  (#74, canzone 54)
    (61, 2, 'MACHI ', 'MACHO '),
    (63, 1, 'AD ALLENARSI ', 'ALLENANDOSI '),
    (66, 0, 'LUPI MANNARI ', 'LICANTROPI '),     # #77 superava i 28 caratteri
    (67, 3, 'FANTASMI ', 'SPETTRI '),
    (69, 0, 'DEPRIMENTI ', 'NOIOSE '),           # BORING
    (69, 1, 'TERMINALI ', 'MORTALI '),           # TERMINAL
    (69, 2, 'SFIANCANTI ', 'SOPORIFERE '),       # MIND-NUMBING
    # titoli delle canzoni
    (95, 0, 'OK', 'FELICE'),                     # ...MI FAI SENTIRE OK
    (('S', 451), None, 'FARE AFFARI CON IL ', 'PORTAMI '),   # TAKE ME TO THE (canzone 58)
    # accento
    (('S', 82), None, 'BAR      LOCALI  UNIVERSITA   SALE CONCERTI STADI   ',
                      "BAR      LOCALI  UNIVERSITA'  SALE CONCERTI STADI   "),
    (('S', 85), None, 'UNIVERSITA ', "UNIVERSITA' "),
    # esclamazioni (gruppo 5, sei messaggi): slang come l'originale
    (5, 0, 'TUTTO OK ', 'ALLA GRANDE '),         # HUNKY DORY
    (5, 2, 'GRANDE ', 'MITICO '),                # RIGHT ON
    # incisione e concerti: nomi maschili singolari (UN ALTRO / QUEL / QUESTO MINI ...)
    (46, 2, 'SUONO', 'TORMENTONE'),              # SOUND
    (46, 3, 'RUMORE', 'BRANO'),                  # NOISE
    (45, 1, 'PESANTE ', 'TOSTO '),               # HEAVY ("pezzo pesante" = noioso)
    (47, 1, 'IN CANNA', 'PRONTO'),               # IN THE CAN
    (47, 2, 'IMBUSTATO', 'PORTATO A CASA'),      # BAGGED
    (47, 3, 'PRESO', 'REGISTRATO'),              # CAPTURED
    (47, 5, 'NASTRATO', 'SU NASTRO'),            # TAPED
    (78, 3, 'RUMORE ', 'BEAT '),                 # titolo: MUOVI QUEL ... FUNKY
    # titoli delle canzoni
    (89, 0, 'MUTUO', 'MARCIO NASCENTE', 'estesa'),   # HOUSE OF THE RISING ROT
    (89, 1, 'MARCIO', 'UMIDO NASCENTE', 'estesa'),   # ... DAMP ("la casa del sole nascente")
    (89, 2, 'PRESTITO', 'MUTUO NASCENTE', 'estesa'), # ... MORTGAGE
    (89, 3, 'DOLORE', 'AFFITTO NASCENTE', 'estesa'), # ... RENT
    (131, 3, 'LE LACRIME', 'LA TRISTEZZA', 'estesa'),  # BALLANDO PASSA ... (singolare)
    (('S', 337), None, 'VIA ', 'PASSA '),        # [ballando] VIA [il crampo] -> PASSA
    (('S', 344), None, 'UN GRUMO ', 'UN NODO '), # LUMP IN MY THROAT
    (108, 2, 'PIU ALTO', "PIU' ALTO"),
    (124, 2, 'REATO ', 'CRIMINE '),              # anche: UNA VITA DI CRIMINE
    # "rock star" e' femminile anche per un uomo: la rock star, le rock star (#126)
    (('S', 417), None, 'REGALARE {AL NOSTRO|ALLA NOSTRA|AI NOSTRI|ALLE NOSTRE} ROCK STAR',
                       'REGALARE {ALLA NOSTRA|ALLE NOSTRE} ROCK STAR', 'estesa'),
    # titoli delle canzoni: la riga del menu di pubblicazione e' larga 30
    # (finestre $0D-$16); oltre, va a capo e si vede solo la fine
    (74, 4, 'SCATENANDOMI ', 'SCATENANDO ', 'estesa'),
    (84, 4, 'LA PUPA ', 'PUPA ', 'estesa'),
    (85, 0, 'HA UNA COTTA PER ', 'SBAVA PER ', 'estesa'),
    (85, 5, "E' IN GALERA CON ", 'EVADE CON ', 'estesa'),
    (86, 0, 'UNA CAMERIERA', 'UNA BARISTA', 'estesa'),
    (86, 2, 'UN CAMIONISTA', 'UN AUTISTA', 'estesa'),
    (86, 4, 'UNA BALLERINA', 'UNA VELINA', 'estesa'),
    (92, 1, 'DOO WAH ', 'DUWA ', 'estesa'),
    (92, 2, 'DINGLEDANGLE ', 'DINDON ', 'estesa'),
    (92, 3, 'SHOWADDY ', 'SHALA ', 'estesa'),
    (92, 4, 'LINGALANGA ', 'LALLA ', 'estesa'),
    (94, 1, 'BAMBOLA ', 'BIMBA ', 'estesa'),
    (95, 2, 'NAUSEATO', 'MALE', 'estesa'),
    (95, 3, 'A DISAGIO', 'STRANO', 'estesa'),
    (104, 3, 'POMELLO ', 'PERNO ', 'estesa'),
    (104, 2, 'SWITCH ', 'FILO ', 'estesa'),
    (35, 2, 'ZUCCAVUOTA ', 'BABBE{O|A|I} ', 'estesa'),
    (36, 3, 'PUTRESCENTE ', 'RIPUGNANTE ', 'estesa'),
    (('S', 212), None, 'MI FAI SENTIRE ', 'MI FAI STARE ', 'estesa'),
    (('S', 258), None, 'NUOVO DI ZECCA', 'NUOVO', 'estesa'),
    (('S', 454), None, 'SONO INNAMORATO ', 'SONO COTTO ', 'estesa'),
    (('S', 147), None, 'HO PERSO LA TESTA PER ', 'IMPAZZISCO PER ', 'estesa'),
    (('S', 345), None, "'S GREATEST HITS", ': IL MEGLIO', 'estesa'),
    (('S', 351), None, "DEGLI ANNI '60", "ANNI '60", 'estesa'),
    # sponsor: "JOKA" suona meglio in italiano (#158, manifesto)
    (('S', 296), None, '  BEVI UN JOKE', '  BEVI UNA JOKA', 'estesa'),
    # la star che molla la band (#211, #212, #213; EN IS QUITTING / YOU'RE NOT QUITTING)
    (('S', 394), None, 'IN FUGA ', 'SUL PIEDE DI PARTENZA ', 'estesa'),
    # menu principale: l'originale e' SAVE/LOAD; finestra larga 10 colonne
    (('S', 429), None, 'DISCO      ESCI', 'SALVATAGGI ESCI'),
    # giornale (#136 nel testo, finestra $2E da 10x6; #140 nel titolo): "MI HA
    # MANGIATO IL PESCE ROSSO! VEDI PAG 9!" faceva 7 righe, la finestra si
    # cancellava e restava solo "9!". Titolo al presente, col possessivo.
    (('S', 277), None, 'MI HA MANGIATO ', 'MANGIA ', 'estesa'),
    (119, 0, 'IL PESCE ROSSO', 'IL MIO PESCE ROSSO', 'estesa'),
    (119, 1, 'LA SALSICCIA', 'LA MIA SALSICCIA', 'estesa'),
    (119, 2, 'LA BARRETTA', 'LA MIA BARRETTA', 'estesa'),
    (123, 0, 'LA MOGLIE', 'MIA MOGLIE', 'estesa'),
    (123, 1, 'IL CANE', 'IL MIO CANE', 'estesa'),
    (123, 2, 'IL CRICETO', 'IL MIO CRICETO', 'estesa'),
    (123, 3, 'LA CASA', 'LA MIA CASA', 'estesa'),
]

# solo compatta: dove l'item differisce dall'estesa, o per bilanciare i byte
CORREZIONI_COMPATTA = {
    (63, 2): ('A CAZZEGGIARE ', 'A CAZZEGGIO '),
    # gli 11 byte tolti ai gruppi tornano dove l'estesa ha gia' la forma piena
    (70, 0): ('POSE PLETTRO ', 'POSE COL PLETTRO '),
    (70, 2): ('FOTO CONCERTO ', 'FOTO DAL CONCERTO '),
    (81, 1): ('I MIEI STIVALI', 'GLI STIVALI'),   # i 3 byte di ALLA GRANDE
    (131, 3): ('LE LACRIME', 'LA NOIA'),          # singolare e corto (PIU' e CRIMINE: +3)
    (('S', 296), None): ('  BEVI UN JOKE', ' BEVI UNA JOKA'),   # stessa lunghezza
    (('S', 394), None): ('IN FUGA ', 'IN PARTENZA '),           # +4: il posto che resta
    # #73 superava i 28 caratteri; i 9 byte tornano a "LA MIA VIRILITA'"
    (57, 0): ('SOTTO LA DOCCIA ', 'IN DOCCIA '),
    (57, 2): ('CON LE FRUSTE ', 'CON FRUSTE '),
    (83, 5): ("LA MIA VIRILITA'", "LA VIRILITA'"),
    # i 9 byte in piu' delle parole dell'incisione
    (47, 2): ('PORTATO A CASA', 'IN SCATOLA'),
    (69, 1): ('MORTALI ', 'LETALI '),
    (('S', 451), None): ('ENTRARE NEL ', 'PORTAMI '),
    # giornale: "MANGIA IL" + nomi maschili (prima IL SALSICCIA, IL MOGLIE...);
    # -2 -2 0 +4: il blocco dei gruppi resta della stessa lunghezza
    (119, 1): ('SALSICCIA', 'WURSTEL'),
    (119, 2): ('BARRETTA', 'GELATO'),
    (123, 0): ('MOGLIE', 'MARITO'),
    (123, 3): ('CASA', 'GIARDINO'),
    # giornale #135 "ALIENI RUBA IL FIGLIA": "ALIENO RUBA" e l'articolo dentro
    # ogni voce (LA FIGLIA, LA VOLVO...): +15 byte ai gruppi, ripresi da
    # SCHIFOSI (riempitivo, l'estesa non ce l'ha) e tre aggettivi piu' corti
    (('S', 273), None): ('ALIENI ', 'ALIENO '),
    (('S', 272), None): ('RUBA IL ', 'RUBA '),
    (118, 0): ('FIGLIO', 'LA FIGLIA'),
    (118, 1): ('CRICETO', 'IL CRICETO'),
    (118, 2): ('BOLIDE', 'LA VOLVO'),
    (118, 3): ('CERVELLO', 'IL CERVELLO'),
    (118, 4): ('NONNO', 'IL MARITO'),
    (11, 1): ('CAMPAGNA PER ESPERIMENTI SCHIFOSI SUGLI ANIMALI ', 'CAMPAGNA PER ESPERIMENTI SUGLI ANIMALI '),
    (4, 6): ('INCREDIBILE ', 'PAZZESCO '),
    (4, 3): ('STREPITOSO ', 'SPAZIALE '),
    (163, 1): ('FANTASTICO ', 'MAGNIFICO '),
    # #142 "ROCK STAR AGGREDITO": la rock star e' femminile
    (('S', 281), None): ('AGGREDITO ', 'AGGREDITA '),
}


def indice(voce):
    return 165 + voce[1] - 68 if isinstance(voce, tuple) else voce


def applica(tab, compatta):
    log = []
    for corr in CORREZIONI:
        voce, item, vecchio, nuovo = corr[:4]
        if compatta and len(corr) > 4 and corr[4] == 'estesa':
            continue                                 # nella compatta non c'e' posto
        e = tab[indice(voce)]
        if item is None:
            attuale = e['text']
            if attuale == nuovo: continue
            if attuale.rstrip() != vecchio.rstrip():
                log.append('  ! %r: trovato %r, atteso %r (salto)' % (voce, attuale, vecchio)); continue
            e['text'] = nuovo
        else:
            attuale = e['items'][item]
            if attuale == nuovo: continue
            if compatta and (voce, item) in CORREZIONI_COMPATTA:
                pass
            if attuale.rstrip() != vecchio.rstrip():
                log.append('  ! G%d[%d]: trovato %r, atteso %r (salto)' % (voce, item, attuale, vecchio)); continue
            e['items'][item] = nuovo
        log.append('  %r[%s]: %r -> %r' % (voce, item, vecchio, nuovo))
    if compatta:
        for (g, k), (vecchio, nuovo) in CORREZIONI_COMPATTA.items():
            e = tab[indice(g)]
            if k is None and e['text'] == vecchio:
                e['text'] = nuovo
            elif k is not None and e['items'][k] == vecchio:
                e['items'][k] = nuovo
            else:
                continue
            log.append('  (compatta) %r[%s]: %r -> %r' % (g, k, vecchio, nuovo))
    return log


def main():
    sys.path.insert(0, QUI)
    import build_ram as br
    scrivi = '--scrivi' in sys.argv
    for nome, compatta in (('rockstar_text_table_ESTESA.json', False),
                           ('rockstar_text_table_ITA.json', True)):
        p = os.path.join(QUI, nome)
        tab = br.carica(p)
        _, off0 = br.costruisci(tab)
        log = applica(tab, compatta)
        c, off = br.costruisci(tab)
        print(nome)
        print('\n'.join(log) or '  nessuna modifica')
        print('  gruppi %d byte (prima %d), totale %d' % (off, off0, len(c)))
        if compatta:
            atteso = 0x101DC - br.TAB_MEM
            if off != atteso:
                sys.exit('  compatta: il blocco dei gruppi deve restare di %d byte, ora %d' % (atteso, off))
            if len(c) > br.TAB_FINE - br.TAB_OFF:
                sys.exit('  compatta: %d byte di troppo' % (len(c) - (br.TAB_FINE - br.TAB_OFF)))
        if scrivi and log:
            shutil.copy(p, p + '.bak')
            json.dump(tab, open(p, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
            print('  scritto')


if __name__ == '__main__':
    main()
