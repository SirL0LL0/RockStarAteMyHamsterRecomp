#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
rsamh_editor.py - Editor di traduzione per Rock Star Ate My Hamster (Amiga)

    python3 rsamh_editor.py

SERVE
    rockstar_base.bin (la base del gioco, fuori dal repository: percorsi.py)

Il testo inglese viene letto direttamente dall'immagine, quindi non serve
nessun altro file. La traduzione sta in rockstar_text_table_ITA.json, che
viene creato al primo salvataggio se non esiste.

COSA SI PUO' FARE
    - modificare tutte le 556 voci (165 gruppi mad-lib + 391 stringhe)
    - vedere le frasi composte a runtime, in inglese e in italiano affiancate
    - controllare in tempo reale i budget e i vincoli
    - generare l'eseguibile, compresso o non compresso

I VINCOLI, SPIEGATI
    I gruppi 0-163 devono occupare ESATTAMENTE 6020 byte. La base della
    tabella piatta e' cablata nel codice e dipende da quel totale: cambiarlo
    significa dover patchare il codice, cosa che rompe il trainer. Dentro quel
    blocco le singole stringhe sono libere, perche' il gioco le raggiunge
    contando i terminatori, non sommando offset.

    Il resto (gruppo 164 piu' le 391 stringhe) sta in 4771 byte.

    Alcune voci sono menu a colonne con spaziatura fissa: devono mantenere la
    lunghezza esatta dell'inglese, altrimenti le colonne si disallineano.

    Il primo item del gruppo 164 deve restare LIVE: il byte di conteggio del
    gruppo vale 0x43, la lettera C, e incollato a quell'item forma CLIVE, il
    nome dell'assistente, che il gioco usa 72 volte.

    Un messaggio composto non puo' superare 255 caratteri e va a capo da solo
    ogni 30.
"""

import base64
import json
import os
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

import build_ram
import script_rsamh as SCR
import accordo as ACC
from script_tab import SchedaScript, con_barre

# ---------------------------------------------------------------- costanti

import percorsi
TRADUZIONE = 'rockstar_text_table_ITA.json'      # compatta, dentro l'immagine
TRAD_ESTESA = 'rockstar_text_table_ESTESA.json'  # in RAM allocata

# La tabella estesa viaggia in un blocco chiesto al sistema e le sue basi
# vengono calcolate a runtime, quindi non ha il vincolo dei 6020 byte sui
# gruppi 0-163 ne' il tetto dei 10791. Il limite pratico e' la memoria che
# il gioco riesce a farsi dare: si tiene un margine ampio.
CAPIENZA_ESTESA = 24000

BASE       = 0x8100        # indirizzo a cui gira il gioco
TAB_INIZIO = 26967         # inizio tabella testi nell'immagine
TAB_FINE   = 37758         # oltre comincia la tabella a record fissi delle band
CAPIENZA   = TAB_FINE - TAB_INIZIO          # 10791
BLOCCO_A   = 6020          # gruppi 0-163: deve essere esatto
BLOCCO_B   = CAPIENZA - BLOCCO_A - 1        # 4770, piu' il byte di conteggio
SCRIPT     = 23664         # inizio della tabella degli script dei messaggi
RIEMPI     = 0xA0          # spazio con bit 7: stringa valida di un carattere

LARGHEZZA_RIGA = 30
MAX_MESSAGGIO  = 255

# Voci a colonne fisse: la lunghezza deve restare identica all'inglese.
STR_FISSE = {14, 92, 93, 96, 228, 229, 232, 233, 264,
             351, 352, 353, 354, 355, 359, 360, 361, 382}
GRUPPO_FISSO = {(164, 45)}

# Messaggi che il gioco usa come menu: se il testo italiano e' piu' lungo
# dell'inglese il menu non viene disegnato (e' successo con RELEASE ALBUM /
# RELEASE SINGLE, passato da 29 a 30 caratteri). Sono indici nella lista dei
# messaggi, che non cambia: i terminatori sono fissi.
# Numerazione del gioco. Ricavati dal disassemblato: sono i messaggi passati
# alla routine dei menu $9944 (piu' il SI/NO, 7), a cui si aggiungono 199 e
# 214 che hanno la stessa struttura a campi.
MENU_MSG = {7, 16, 18, 27, 32, 35, 38, 40, 45, 47, 50, 52, 68, 70, 171,
            190, 199, 214, 215, 218}

# Contesto di ogni messaggio, ricavato dal codice con tools/mappa_messaggi.py
# (routine che lo mostra, se e' un fumetto o un menu, cosa viene prima e
# dopo, token riscritti a runtime). Facoltativo: senza il file l'editor va.
FILE_CONTESTO = 'contesto_messaggi.json'

VERSIONI = ("rilocabile - 1MB di chip",
            "con loader - A500 512K chip + 512K")
try:
    CONTESTO = {int(k): v for k, v in
                json.load(open(FILE_CONTESTO, encoding='utf-8')).items()}
except Exception:
    CONTESTO = {}

# ------------------------------------------------- lettura tabella inglese

def leggi_tabella(img, inizio=TAB_INIZIO, fine=TAB_FINE):
    """Ricava le voci dall'immagine: FF apre un gruppo, il bit 7 chiude una
    stringa."""
    voci = []
    i = inizio
    while i < fine:
        if img[i] == 0xFF:
            n = img[i + 1] + 1
            i += 2
            items = []
            for _ in range(n):
                s = i
                while not (img[i] & 0x80):
                    i += 1
                items.append(''.join(chr(img[k] & 0x7F) for k in range(s, i + 1)))
                i += 1
            voci.append({'type': 'GROUP', 'items': items})
        else:
            s = i
            while not (img[i] & 0x80):
                i += 1
            voci.append({'type': 'STR',
                         'text': ''.join(chr(img[k] & 0x7F) for k in range(s, i + 1))})
            i += 1
    return voci


def codifica(s):
    b = bytearray()
    for i, c in enumerate(s):
        v = ord(c) & 0x7F
        if i == len(s) - 1:
            v |= 0x80
        b.append(v)
    return bytes(b)


def dimensione(v):
    if v['type'] == 'GROUP':
        return 2 + sum(len(x) for x in v['items'])
    return len(v['text'])


def costruisci(voci):
    out = bytearray()
    for v in voci:
        if v['type'] == 'GROUP':
            out.append(0xFF)
            out.append(len(v['items']) - 1)
            for it in v['items']:
                out += codifica(it.upper())
        else:
            out += codifica(v['text'].upper())
    return bytes(out)


# ------------------------------------------------------ frasi composte

def messaggi(img):
    """Lista dei messaggi, col modello verificato in script_rsamh."""
    return [m['token'] for m in SCR.messaggi_gioco(img)]


def rendi(voci, toks):
    """Compone la frase come il gioco. I gruppi sono estratti a caso a runtime:
    qui si mostra il primo item, tanto per far vedere la forma della frase."""
    gruppi = [v for v in voci if v['type'] == 'GROUP']
    piatte = list(gruppi[-1]['items']) + [v['text'] for v in voci if v['type'] == 'STR']
    s = ''
    for t in toks:
        k = SCR.tipo_token(t); v = SCR.valore_token(t)
        if k == 'STRINGA':
            if v == 0:
                s += 'C' + (piatte[0] if piatte else '')   # il byte di conteggio
            else:
                s += piatte[v] if v < len(piatte) else '<?>'
        elif k == 'GRUPPO':
            s += gruppi[v]['items'][0] if v < len(gruppi) else '<?>'
        elif k == 'RAM32':
            s += '<BAND>'
        else:
            s += '<DATO>'
    return s


def a_video(s):
    """Il testo come lo mostra il gioco: $D73E mangia lo spazio prima di
    ! , . ?  e l'a capo lascia cadere gli spazi in fondo."""
    out = []
    for c in s:
        if c in '!,.?' and out and out[-1] == ' ':
            out[-1] = c
        else:
            out.append(c)
    return ''.join(out).rstrip()


def righe(s, w=LARGHEZZA_RIGA):
    s = a_video(s)
    out, cur = [], ''
    for p in s.split(' '):
        if not cur: cur = p
        elif len(cur) + 1 + len(p) <= w: cur += ' ' + p
        else: out.append(cur); cur = p
    if cur: out.append(cur)
    return out


# ------------------------------------------------------------- controlli

def controlla(en, it, msgs, estesa=False):
    """Restituisce una lista di (grave, testo).

    grave=True  il gioco non funzionerebbe: la generazione si ferma
    grave=False qualcosa si vedra' male, ma il gioco parte
    """
    p = []
    if len(en) != len(it):
        return [(True, f"numero di voci diverso: {len(it)} invece di {len(en)}")]

    a = b = 0
    gi = 0
    for x, y in zip(en, it):
        if x['type'] == 'GROUP':
            if len(x['items']) != len(y['items']):
                p.append((True, f"gruppo {gi}: {len(y['items'])} items invece di "
                                f"{len(x['items'])} (il gioco li indicizza per posizione)"))
            if gi < 164: a += dimensione(y)
            else: b += dimensione(y)
            gi += 1
        else:
            b += dimensione(y)

    if estesa:
        tot = a + b
        if tot > CAPIENZA_ESTESA:
            p.append((True, f"la tabella occupa {tot} byte, il massimo e' "
                            f"{CAPIENZA_ESTESA} ({tot-CAPIENZA_ESTESA:+d})"))
    else:
        if a != BLOCCO_A:
            p.append((True, f"i gruppi 0-163 occupano {a} byte, devono essere esattamente "
                            f"{BLOCCO_A} ({a-BLOCCO_A:+d}): la base della tabella piatta "
                            f"e' cablata nel codice"))
        if b > BLOCCO_B + 1:
            p.append((True, f"il resto occupa {b} byte, il massimo e' {BLOCCO_B+1} "
                            f"({b-BLOCCO_B-1:+d})"))

    gi = si = 0
    for x, y in zip(en, it):
        if x['type'] == 'GROUP':
            for j, (e, i2) in enumerate(zip(x['items'], y['items'])):
                if (gi, j) in GRUPPO_FISSO and len(e) != len(i2):
                    p.append((False, f"gruppo {gi} item {j}: e' un menu a campi fissi, "
                                     f"servono esattamente {len(e)} caratteri, ne ha "
                                     f"{len(i2)}: le voci dopo slittano"))
                if not i2:
                    p.append((True, f"gruppo {gi} item {j}: stringa vuota, non ammessa"))
            if gi == 164 and y['items'] and y['items'][0].upper() != 'LIVE ':
                p.append((True, "il primo item del gruppo 164 deve restare 'LIVE ': "
                                "col byte di conteggio forma il nome CLIVE"))
            gi += 1
        else:
            if si in STR_FISSE and len(x['text']) != len(y['text']):
                p.append((False, f"stringa {si}: e' un menu a campi fissi, servono "
                                 f"esattamente {len(x['text'])} caratteri, ne ha "
                                 f"{len(y['text'])}: le voci dopo slittano"))
            if not y['text']:
                p.append((True, f"stringa {si}: vuota, non ammessa"))
            si += 1

    for v in it:
        for s2 in (v['items'] if v['type'] == 'GROUP' else [v['text']]):
            for c in s2:
                if ord(c) > 126 or ord(c) < 32:
                    p.append((True, f"carattere non ammesso {c!r} in {s2!r}"))
                    break
            if ACC.ha_marcatori(s2) or '}' in s2 or '|' in s2:
                if not estesa:
                    p.append((True, f"marcatori di genere/numero nella tabella compatta: "
                                    f"{s2!r} (li capisce solo la versione con la tabella "
                                    f"estesa; qui scrivi la forma maschile singolare)"))
                for err in ACC.errori_marcatori(s2):
                    p.append((True, f"marcatori: {err} in {s2!r}"))

    piatte = list([v for v in it if v['type'] == 'GROUP'][-1]['items']) + \
        [v['text'] for v in it if v['type'] == 'STR']
    if len(piatte) > SCR.RIEMPITIVO and piatte[SCR.RIEMPITIVO] != ' ':
        p.append((True, f"la stringa {SCR.RIEMPITIVO - 68} deve restare un solo spazio: "
                        f"e' il riempitivo che tappa i token tolti dagli script"))

    for n, toks in enumerate(msgs):
        e = rendi(en, toks); grezzo = rendi(it, toks)
        # il tetto dei 255 vale per il testo con i marcatori: il gioco tronca
        # mentre compone, il filtro arriva dopo
        if len(grezzo) > MAX_MESSAGGIO:
            p.append((False, f"#{n} messaggio di {len(grezzo)} caratteri (marcatori "
                             f"compresi), il tetto e' {MAX_MESSAGGIO}, viene troncato: "
                             f"{grezzo.strip()[:50]}..."))
        for i2 in varianti_messaggio(n, toks, grezzo):
            if n in MENU_FINESTRA:
                pr = problemi_menu(n, i2)
                if pr:
                    p.append((True, f"#{n} menu: {pr}"))
            elif n in MENU_MSG and len(i2) > len(e):
                p.append((True, f"#{n} menu di {len(i2)} caratteri contro {len(e)} "
                                f"dell'inglese: il gioco non lo disegna: {i2.strip()[:50]}"))
            if len(righe(i2)) > len(righe(e)):
                p.append((False, f"#{n} messaggio piu' alto di {len(righe(i2))-len(righe(e))} "
                                 f"riga/e rispetto all'inglese: {a_video(i2)[:60]}"))
    return p


def righe_finestra(s, larg):
    """Come $D48E dispone un testo in una finestra larga larg.

    Per ogni riga conta larg caratteri dal punto in cui e' (anche se e' uno
    spazio) e ricorda la posizione dell'ultimo spazio; se non ce n'e', o c'e'
    solo quello iniziale, prende la riga intera. Poi disegna saltando UNO
    spazio iniziale. Se il testo finisce mentre disegna, si ferma li'; se la
    riga si completa, scende di una riga, e quando arriva in fondo alla
    finestra la cancella e ricomincia dall'alto.

    Conseguenze viste in gioco: una riga che finisce con piu' spazi di quanti
    ne entrano fa disegnare alla successiva un carattere di troppo (la M di
    MANDA nel #171); un'ultima opzione che arriva esattamente al bordo fa
    scendere oltre la finestra, che viene cancellata (il menu dei giorni
    vuoto con "5 GIORNI " in 9 colonne).

    Restituisce ([(inizio, testo)], righe_scese)."""
    out, p, scese = [], 0, 0
    while p < len(s):
        k = ult = 0
        while k < larg and p + k < len(s):
            if s[p + k] == ' ': ult = k + 1
            k += 1
        q = p + 1 if s[p] == ' ' else p
        if p + k >= len(s) and k < larg:          # finisce prima del bordo
            out.append((q, s[q:])); break
        n = ult if ult > 1 else larg
        out.append((q, s[q:q + n]))
        if q + n > len(s):                        # finisce mentre disegna
            break
        p = q + n
        scese += 1
    return out, scese


# menu -> (larghezza della finestra, righe = opzioni), dalla tabella delle
# finestre a $11AF6 (la 5, giorni di prove, allargata a 10: FINESTRA_GIORNI)
MENU_FINESTRA = {7: (3, 2), 16: (13, 3), 18: (10, 6), 45: (10, 7), 190: (10, 7),
                 218: (12, 3), 27: (10, 5), 35: (14, 4), 215: (8, 3), 50: (16, 6),
                 32: (14, 5), 38: (13, 6), 40: (9, 7), 47: (19, 7), 52: (16, 2),
                 68: (30, 6), 70: (19, 4), 171: (21, 4)}


def problemi_menu(n, testo):
    """None se il menu viene giusto, altrimenti la descrizione."""
    larg, nr = MENU_FINESTRA[n]
    s = []                              # il buffer del gioco, spazi in fondo compresi:
    for c in testo:                     # si mangia solo lo spazio prima di ! , . ?
        if c in '!,.?' and s and s[-1] == ' ': s[-1] = c
        else: s.append(c)
    s = ''.join(s)
    r, a_capo = righe_finestra(s, larg)
    vis = [x.rstrip() for _, x in r]
    if a_capo >= nr:
        return (f"il testo riempie anche l'ultima riga ({vis[-1]!r} arriva al bordo, "
                f"largo {larg}): il gioco va a capo oltre la finestra, la cancella e "
                f"il menu resta vuoto. L'ultima opzione deve essere piu' corta della "
                f"finestra")
    if len(r) != nr:
        return f"viene su {len(r)} righe invece di {nr}, una per opzione: {vis}"
    for q, x in r[1:]:
        if q > 0 and s[q - 1] != ' ':
            return (f"una riga comincia a meta' parola ({x.strip()[:12]!r}): "
                    f"la riga prima ha piu' spazi di quanti ne entrano in {larg} "
                    f"colonne: {vis}")
    return None


def varianti_messaggio(n, toks, grezzo):
    """Le forme che il messaggio puo' prendere in gioco (una sola se non ha
    marcatori). Vedi accordo.py."""
    if not ACC.ha_marcatori(grezzo):
        return [grezzo]
    out = []
    for acc in ACC.soggetti_possibili(n, toks):
        r = ACC.risolvi(grezzo, acc)
        if r not in out:
            out.append(r)
    return out


def varianti_con_nome(n, toks, grezzo):
    if not ACC.ha_marcatori(grezzo):
        return [('', grezzo)]
    out, visti = [], set()
    for acc in ACC.soggetti_possibili(n, toks):
        r = ACC.risolvi(grezzo, acc)
        if r not in visti:
            visti.add(r); out.append((ACC.NOMI_ACC[acc], r))
    return out


def confronta(compatta, estesa):
    """Le due tabelle devono avere la stessa STRUTTURA: il gioco usa gli stessi
    indici per entrambe, quindi un gruppo con un numero diverso di items
    farebbe pescare la voce sbagliata a seconda della memoria disponibile."""
    p = []
    if len(compatta) != len(estesa):
        return [(True, f"le due tabelle hanno {len(compatta)} e {len(estesa)} voci: "
                       f"devono averne lo stesso numero")]
    gi = 0
    for c, e in zip(compatta, estesa):
        if c['type'] != e['type']:
            p.append((True, f"voce {gi}: tipo diverso fra compatta ed estesa"))
        elif c['type'] == 'GROUP':
            if len(c['items']) != len(e['items']):
                p.append((True, f"gruppo {gi}: {len(c['items'])} items nella compatta, "
                                f"{len(e['items'])} nell'estesa"))
            gi += 1
    return p


# ------------------------------------------------------- costruzione exe
#
# La costruzione vera sta in build_ram.costruisci_exe: mette la tabella
# compatta dentro l'immagine come piano B e quella estesa nel pacchetto
# che il gioco si copia in RAM. Qui non si duplica nulla.

# ------------------------------------------------------------------- GUI

class Editor(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Rock Star Ate My Hamster - editor traduzione")
        self.geometry("1180x760")

        if not os.path.isfile(percorsi.BASE):
            messagebox.showerror("File mancante",
                                 f"Serve {percorsi.BASE}: crealo con base_canonica.py "
                                 "dal disco originale.")
            self.destroy(); return

        self.img = percorsi.inglese()
        self.img_orig = self.img          # intatta: serve da riferimento inglese
        # calendario ed etichetta VENDITE: testi che non stanno nella tabella
        self.img = SCR.patch_fissi(self.img)
        # va creata prima di caricare: serve a scegliere quale file aprire
        self.estesa = tk.BooleanVar(value=False)
        self.en = leggi_tabella(self.img)
        self.it = self.carica_traduzione()
        self.msgs = messaggi(self.img)
        self.corrente = None
        self.in_commit = False      # evita il rientro: commit -> lista -> selezione
        self.punti = tk.BooleanVar(value=True)

        self.costruisci_ui()
        from script_tab import SALVATAGGIO
        if os.path.isfile(SALVATAGGIO):
            self.tab_scr.carica(SALVATAGGIO)
            self.tab_scr.applica()
        self.riempi_lista()
        self.aggiorna_budget()

    # -------------------------------------------------- dati

    def file_traduzione(self):
        return TRAD_ESTESA if self.estesa.get() else TRADUZIONE

    def cambia_tabella(self):
        self.commit()
        self.corrente = None
        self.it = self.carica_traduzione()
        self.riempi_lista(); self.aggiorna_budget()
        self.stato(f"ora stai modificando {self.file_traduzione()}")

    def carica_altra(self):
        """Le voci dell'altra tabella, letta dal disco. Serve alla verifica e
        alla generazione: l'eseguibile le contiene entrambe."""
        f = TRADUZIONE if self.estesa.get() else TRAD_ESTESA
        if not os.path.isfile(f):
            return None
        try:
            raw = json.load(open(f, encoding='utf-8'))
            if isinstance(raw, dict): raw = raw['entries']
            return raw if len(raw) == len(self.en) else None
        except Exception:
            return None

    def carica_traduzione(self):
        f = self.file_traduzione()
        if os.path.isfile(f):
            raw = json.load(open(f, encoding='utf-8'))
            if isinstance(raw, dict): raw = raw['entries']
            if len(raw) == len(self.en):
                return [dict(v) for v in raw]
            messagebox.showwarning(
                "Traduzione incompatibile",
                f"{f} ha {len(raw)} voci invece di {len(self.en)}: "
                "parto dall'inglese.")
        return [dict(v) for v in self.en]

    def salva_traduzione(self):
        self.commit()
        f = self.file_traduzione()
        json.dump(self.it, open(f, 'w', encoding='utf-8'),
                  ensure_ascii=False, indent=1)
        self.stato(f"salvato {f}")

    # -------------------------------------------------- interfaccia

    def costruisci_ui(self):
        barra = ttk.Frame(self); barra.pack(fill='x', padx=6, pady=4)
        ttk.Button(barra, text="Salva JSON", command=self.salva_traduzione).pack(side='left')
        ttk.Button(barra, text="Ricarica", command=self.ricarica).pack(side='left', padx=(4, 12))
        ttk.Button(barra, text="Verifica", command=self.mostra_verifica).pack(side='left')
        ttk.Button(barra, text="Crea eseguibile",
                   command=self.crea).pack(side='left', padx=(12, 0))
        self.versione = tk.StringVar(value=VERSIONI[1])
        ttk.Combobox(barra, textvariable=self.versione, values=VERSIONI,
                     state='readonly', width=34).pack(side='left', padx=4)
        ttk.Checkbutton(barra, text="tabella ESTESA (in RAM)",
                        variable=self.estesa,
                        command=self.cambia_tabella).pack(side='left', padx=(16, 0))
        ttk.Checkbutton(barra, text="mostra spazi finali come ·",
                        variable=self.punti,
                        command=self.mostra_voce).pack(side='right')

        mis = ttk.Frame(self); mis.pack(fill='x', padx=6)
        self.lbl_a = ttk.Label(mis, font=('TkFixedFont', 10)); self.lbl_a.pack(side='left')
        self.lbl_b = ttk.Label(mis, font=('TkFixedFont', 10)); self.lbl_b.pack(side='left', padx=20)
        self.lbl_t = ttk.Label(mis, font=('TkFixedFont', 10)); self.lbl_t.pack(side='left')

        corpo = ttk.PanedWindow(self, orient='horizontal')
        corpo.pack(fill='both', expand=True, padx=6, pady=6)

        sx = ttk.Frame(corpo); corpo.add(sx, weight=1)
        f = ttk.Frame(sx); f.pack(fill='x')
        self.cerca = tk.StringVar()
        self.cerca.trace_add('write', lambda *a: self.riempi_lista())
        ttk.Entry(f, textvariable=self.cerca).pack(side='left', fill='x', expand=True)
        self.filtro = tk.StringVar(value='tutti')
        ttk.Combobox(f, textvariable=self.filtro, width=10, state='readonly',
                     values=('tutti', 'gruppi', 'stringhe', 'modificate', 'fisse')
                     ).pack(side='left', padx=4)
        self.filtro.trace_add('write', lambda *a: self.riempi_lista())

        fl, self.lista = con_barre(sx, ttk.Treeview, columns=('t', 'n', 'x'),
                                   show='headings', height=30)
        for c, w, t in (('t', 60, 'tipo'), ('n', 60, 'byte'), ('x', 320, 'contenuto')):
            self.lista.heading(c, text=t); self.lista.column(c, width=w, anchor='w')
        fl.pack(fill='both', expand=True, pady=4)
        self.lista.bind('<<TreeviewSelect>>', self.seleziona)

        dx = ttk.Notebook(corpo); corpo.add(dx, weight=2)

        self.tab_voce = ttk.Frame(dx); dx.add(self.tab_voce, text='Voce')
        ttk.Label(self.tab_voce, text="inglese (sola lettura)").pack(anchor='w')
        fe, self.txt_en = con_barre(self.tab_voce, tk.Text, orizzontale=True,
                                    height=9, wrap='none',
                                    font=('TkFixedFont', 11), bg='#f0f0f0')
        fe.pack(fill='both', expand=True)
        self.lbl_nota = ttk.Label(self.tab_voce, text='', foreground='#a05000')
        self.lbl_nota.pack(anchor='w', pady=(6, 0))
        ttk.Label(self.tab_voce, text="italiano (una voce per riga)").pack(anchor='w')
        fi, self.txt_it = con_barre(self.tab_voce, tk.Text, orizzontale=True,
                                    height=9, wrap='none', font=('TkFixedFont', 11))
        fi.pack(fill='both', expand=True)
        self.txt_it.bind('<FocusOut>', lambda e: self.commit())
        ttk.Button(self.tab_voce, text="Applica", command=self.commit).pack(anchor='e', pady=4)

        self.tab_frasi = ttk.Frame(dx); dx.add(self.tab_frasi, text='Frasi composte')
        ff = ttk.Frame(self.tab_frasi); ff.pack(fill='x')
        ttk.Button(ff, text="Aggiorna", command=self.mostra_frasi).pack(side='left')
        ttk.Label(ff, text="  cerca").pack(side='left')
        self.cerca_frasi = tk.StringVar()
        self.cerca_frasi.trace_add('write', lambda *a: self.mostra_frasi())
        ttk.Entry(ff, textvariable=self.cerca_frasi).pack(side='left', fill='x',
                                                          expand=True, padx=4)
        ff2, self.txt_frasi = con_barre(self.tab_frasi, tk.Text, wrap='word',
                                        font=('TkFixedFont', 10))
        ff2.pack(fill='both', expand=True)
        self.txt_frasi.tag_config('en', foreground='#666666')
        self.txt_frasi.tag_config('ctx', foreground='#2060a0')
        self.txt_frasi.tag_config('bad', foreground='#bb0000')

        self.tab_scr = SchedaScript(dx, self); dx.add(self.tab_scr, text='Script')

        self.tab_ver = ttk.Frame(dx); dx.add(self.tab_ver, text='Verifica')
        vf = ttk.Frame(self.tab_ver); vf.pack(fill='x')
        ttk.Label(vf, text="cerca").pack(side='left')
        self.cerca_ver = tk.StringVar()
        self.cerca_ver.trace_add('write', lambda *a: self.mostra_verifica())
        ttk.Entry(vf, textvariable=self.cerca_ver).pack(side='left', fill='x',
                                                        expand=True, padx=4)
        fv, self.txt_ver = con_barre(self.tab_ver, tk.Text, wrap='word',
                                     font=('TkFixedFont', 10))
        fv.pack(fill='both', expand=True)
        self.txt_ver.tag_config('bad', foreground='#bb0000')

        self.barra_stato = ttk.Label(self, text='', anchor='w')
        self.barra_stato.pack(fill='x', padx=6, pady=(0, 4))

    def piatte(self, tab):
        g = [v for v in tab if v['type'] == 'GROUP']
        return list(g[-1]['items']) + [v['text'] for v in tab if v['type'] == 'STR']

    def stato(self, t):
        self.barra_stato.config(text=t)

    # -------------------------------------------------- lista

    def indici(self):
        q = self.cerca.get().lower()
        f = self.filtro.get()
        gi = si = 0
        for k, (e, i2) in enumerate(zip(self.en, self.it)):
            g, s = (gi, None) if e['type'] == 'GROUP' else (None, si)
            if e['type'] == 'GROUP': gi += 1
            else: si += 1
            if f == 'gruppi' and e['type'] != 'GROUP': continue
            if f == 'stringhe' and e['type'] != 'STR': continue
            if f == 'modificate' and e == i2: continue
            if f == 'fisse' and not (s in STR_FISSE or
                                     any((g, j) in GRUPPO_FISSO
                                         for j in range(len(e.get('items', []))))):
                continue
            if q:
                testo = ' '.join(i2['items']) if i2['type'] == 'GROUP' else i2['text']
                testo += ' ' + (' '.join(e['items']) if e['type'] == 'GROUP' else e['text'])
                if q not in testo.lower(): continue
            yield k, g, s

    def riempi_lista(self):
        self.lista.delete(*self.lista.get_children())
        for k, g, s in self.indici():
            v = self.it[k]
            et = f"G{g}" if g is not None else f"S{s}"
            cont = ' | '.join(v['items']) if v['type'] == 'GROUP' else v['text']
            self.lista.insert('', 'end', iid=str(k),
                              values=(et, dimensione(v), cont[:70]))

    def seleziona(self, _):
        if self.in_commit: return
        sel = self.lista.selection()
        if not sel: return
        self.commit()
        self.corrente = int(sel[0])
        self.mostra_voce()

    # -------------------------------------------------- editor voce

    def deco(self, s):
        return s.replace(' ', '·') if self.punti.get() and s.endswith(' ') else s

    def rideco(self, s):
        return s.replace('·', ' ')

    def mostra_voce(self):
        if self.corrente is None: return
        e, i2 = self.en[self.corrente], self.it[self.corrente]
        self.txt_en.config(state='normal'); self.txt_en.delete('1.0', 'end')
        self.txt_it.delete('1.0', 'end')
        if e['type'] == 'GROUP':
            self.txt_en.insert('end', '\n'.join(self.deco(x) for x in e['items']))
            self.txt_it.insert('end', '\n'.join(self.deco(x) for x in i2['items']))
        else:
            self.txt_en.insert('end', self.deco(e['text']))
            self.txt_it.insert('end', self.deco(i2['text']))
        self.txt_en.config(state='disabled')

        gi = si = 0
        for k in range(self.corrente):
            if self.en[k]['type'] == 'GROUP': gi += 1
            else: si += 1
        note = []
        if e['type'] == 'STR' and si in STR_FISSE:
            note.append(f"menu a colonne fisse: servono esattamente {len(e['text'])} caratteri")
        if e['type'] == 'GROUP':
            if gi < 164:
                note.append("gruppo 0-163: il blocco deve restare a 6020 byte in totale")
            if gi == 164:
                note.append("il primo item deve restare 'LIVE ' (forma CLIVE col byte di conteggio)")
            note.append("il numero di items non si puo' cambiare")
        self.lbl_nota.config(text='   '.join(note))

    def commit(self):
        if self.corrente is None or self.in_commit: return
        self.in_commit = True
        try:
            self._commit()
        finally:
            self.in_commit = False

    def _commit(self):
        righe_txt = self.txt_it.get('1.0', 'end-1c').split('\n')
        v = self.it[self.corrente]
        if v['type'] == 'GROUP':
            if len(righe_txt) != len(v['items']):
                self.stato(f"ATTENZIONE: servono {len(v['items'])} righe, ce ne sono "
                           f"{len(righe_txt)}: modifica ignorata")
                return
            nuovi = [self.rideco(r).upper() for r in righe_txt]
            if any(not r for r in nuovi):
                self.stato("ATTENZIONE: riga vuota, modifica ignorata"); return
            v['items'] = nuovi
        else:
            t = self.rideco(righe_txt[0]).upper()
            if not t:
                self.stato("ATTENZIONE: stringa vuota, modifica ignorata"); return
            v['text'] = t
        # aggiorna solo la riga toccata, non tutta la lista
        iid = str(self.corrente)
        if self.lista.exists(iid):
            cont = ' | '.join(v['items']) if v['type'] == 'GROUP' else v['text']
            et = self.lista.set(iid, 't')
            self.lista.item(iid, values=(et, dimensione(v), cont[:70]))
        self.aggiorna_budget()

    # -------------------------------------------------- budget

    def aggiorna_budget(self):
        a = b = 0; gi = 0
        for e, v in zip(self.en, self.it):
            if e['type'] == 'GROUP':
                if gi < 164: a += dimensione(v)
                else: b += dimensione(v)
                gi += 1
            else: b += dimensione(v)
        if self.estesa.get():
            tot = a + b
            ok = tot <= CAPIENZA_ESTESA
            self.lbl_a.config(text="TABELLA ESTESA: nessun vincolo sui gruppi",
                              foreground='#666666')
            self.lbl_b.config(text=f"gruppi 0-163: {a}   resto: {b}",
                              foreground='#666666')
            self.lbl_t.config(text=f"{'✓' if ok else '✗'} totale: {tot}/{CAPIENZA_ESTESA}",
                              foreground='#008000' if ok else '#bb0000')
        else:
            ok = '✓' if a == BLOCCO_A else '✗'
            self.lbl_a.config(text=f"{ok} gruppi 0-163: {a}/{BLOCCO_A} ({a-BLOCCO_A:+d})",
                              foreground='#008000' if a == BLOCCO_A else '#bb0000')
            ok2 = '✓' if b <= BLOCCO_B + 1 else '✗'
            self.lbl_b.config(text=f"{ok2} resto: {b}/{BLOCCO_B+1}",
                              foreground='#008000' if b <= BLOCCO_B + 1 else '#bb0000')
            self.lbl_t.config(text=f"totale: {a+b}/{CAPIENZA}",
                              foreground='#000000')

    # -------------------------------------------------- frasi e verifica

    def mostra_frasi(self):
        self.commit()
        self.txt_frasi.delete('1.0', 'end')
        q = self.cerca_frasi.get().lower() if hasattr(self, 'cerca_frasi') else ''
        for n, toks in enumerate(self.msgs):
            e = rendi(self.en, toks); i2 = rendi(self.it, toks)
            if not e.strip(): continue
            ctx = CONTESTO.get(n, [])
            if q and q not in e.lower() and q not in i2.lower() \
                    and q != f'#{n}' and not any(q in c.lower() for c in ctx):
                continue
            self.txt_frasi.insert('end', f'#{n}  ' + ('  |  '.join(ctx) if ctx else
                                  '(contesto non ricavato: composto dal codice)') + '\n', 'ctx')
            self.txt_frasi.insert('end', 'EN  ' + a_video(e).strip() + '\n', 'en')
            var = varianti_con_nome(n, toks, i2)
            for k, (nome, v) in enumerate(var):
                male = len(righe(v)) > len(righe(e)) or len(i2) > MAX_MESSAGGIO
                testa = 'IT  ' if not nome else f'IT {nome:>4} '
                self.txt_frasi.insert('end', testa + a_video(v).strip() + '\n',
                                      'bad' if male else '')
            self.txt_frasi.insert('end', '\n')
        self.stato(f"{len(self.msgs)} messaggi ricomposti")

    def mostra_verifica(self):
        self.commit()
        quale = 'ESTESA' if self.estesa.get() else 'compatta'
        p = controlla(self.en, self.it, self.msgs, self.estesa.get())
        # l'altra tabella serve comunque: la compatta e' il piano B, l'estesa
        # e' quella che si vede quando c'e' memoria. Vanno verificate insieme.
        altra = self.carica_altra()
        if altra is not None:
            p += [(g, f"[{'compatta' if self.estesa.get() else 'ESTESA'}] {t}")
                  for g, t in controlla(self.en, altra, self.msgs,
                                        not self.estesa.get())]
            comp = altra if self.estesa.get() else self.it
            est = self.it if self.estesa.get() else altra
            p += [(g, f"[struttura] {t}") for g, t in confronta(comp, est)]
        else:
            p.append((True, f"manca il file dell'altra tabella: serve anche quello "
                            f"per generare l'eseguibile"))

        q = self.cerca_ver.get().lower() if hasattr(self, 'cerca_ver') else ''
        mostrati = [(g, t) for g, t in p if not q or q in t.lower()]
        gravi = [t for g, t in p if g]
        lievi = [t for g, t in p if not g]

        self.txt_ver.delete('1.0', 'end')
        self.txt_ver.insert('end', f"stai modificando la tabella {quale}\n\n")
        if not p:
            self.txt_ver.insert('end', "Nessun problema: si puo' generare "
                                       "l'eseguibile.\n")
        else:
            self.txt_ver.insert('end',
                f"{len(gravi)} bloccanti, {len(lievi)} da guardare\n\n")
            for g, t in mostrati:
                self.txt_ver.insert('end', ('  BLOCCA  ' if g else '  guarda  ') + t + '\n',
                                    'bad' if g else '')
        self.stato(f"verifica: {len(gravi)} bloccanti, {len(lievi)} avvertimenti")
        return p

    # -------------------------------------------------- build

    def ricarica(self):
        self.corrente = None
        self.it = self.carica_traduzione()
        self.riempi_lista(); self.aggiorna_budget()
        self.stato("traduzione ricaricata dal disco")

    def crea(self, compresso=True):
        """Genera l'eseguibile completo: la tabella compatta va dentro
        l'immagine come piano B, quella estesa nel pacchetto che il gioco si
        copia in RAM. Servono quindi tutte e due."""
        p = self.mostra_verifica()
        gravi = [t for g, t in p if g]
        if gravi:
            messagebox.showerror(
                "Non posso generare",
                "Va sistemato prima:\n\n" + '\n\n'.join(gravi[:6])
                + ('\n\n(e altri...)' if len(gravi) > 6 else ''))
            return
        lievi = [t for g, t in p if not g]
        if lievi and not messagebox.askyesno(
                "Avvertimenti",
                f"Ci sono {len(lievi)} cose che si vedranno male (scheda Verifica), "
                "ma il gioco parte.\nGenero lo stesso?"):
            return

        altra = self.carica_altra()
        compatta = altra if self.estesa.get() else self.it
        estesa = self.it if self.estesa.get() else altra

        rilocabile = self.versione.get() == VERSIONI[0]
        f = filedialog.asksaveasfilename(
            defaultextension='',
            initialfile='rockstar_ita' if rilocabile else 'rockstar_ita_ram.bin')
        if not f: return
        if rilocabile:
            try:
                import build_riloc
                e, info = build_riloc.costruisci_riloc(self.img, estesa)
                open(f, 'wb').write(e)
            except Exception as ex:
                messagebox.showerror("Errore", str(ex)); return
            self.stato(f"scritto {os.path.basename(f)} — {info['eseguibile']} byte")
            messagebox.showinfo(
                "Fatto",
                f"{os.path.basename(f)}\n{info['eseguibile']} byte, "
                f"{info['rilocazioni']} rilocazioni\n\n"
                "Eseguibile AmigaDOS normale: niente compressione, niente\n"
                "loader. Serve 1MB di chip RAM.")
            return
        try:
            self.stato("compressione in corso...")
            self.update_idletasks()
            def avanti(x, y):
                self.stato(f"compressione {x*100//y}%")
                self.update_idletasks()
            e, note = build_ram.costruisci_exe(
                self.img, estesa, compatta, avanti)
            open(f, 'wb').write(e)
        except Exception as ex:
            messagebox.showerror("Errore", str(ex)); return
        self.stato(f"scritto {os.path.basename(f)} — {note['eseguibile']} byte")
        messagebox.showinfo(
            "Fatto",
            f"{os.path.basename(f)}\n{note['eseguibile']} byte\n\n"
            f"tabella compatta (piano B): {note['compatta']} byte\n"
            f"tabella estesa (in RAM):    {note['estesa']} byte\n\n"
            "Richiede 1MB di RAM. Nell'introduzione il testo esteso si\n"
            "riconosce dalla frase diversa.")


if __name__ == '__main__':
    Editor().mainloop()
