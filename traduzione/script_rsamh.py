# -*- coding: utf-8 -*-
"""
script_rsamh.py - il formato degli script dei messaggi, ricavato dal codice.

COME IL GIOCO COMPONE UNA FRASE

Il compositore principale sta a $D638. Legge dallo script token da DUE byte e
li smista guardando tre bit, in quest'ordine:

    bit 13   indice in una tabella di record da 9 byte in RAM ($1286C).
             Sono dati della partita, non testo fisso.
    bit 14   indice in una tabella di record in RAM: da 32 byte a $129DA se
             l'indice e' sotto 12, altrimenti da 20 byte a $12B5A. Il record
             contiene a sua volta una lista di token, che viene espansa dal
             sottocompositore a $8842 (dove i token sono da TRE byte).
             E' cosi' che vengono inseriti i nomi delle band, che il gioco
             genera e memorizza come liste di token.
    bit 15   gruppo mad-lib. ATTENZIONE: nello script NON c'e' l'indice
             dell'item. Il gioco legge il byte di conteggio del gruppo e poi
             chiama $D440, che estrae un item A CASO ($B882 legge il timer
             CIA a $BFE801) tenendo una cronologia di 64 voci per non
             ripetersi.
    nessuno  indice nella tabella piatta delle stringhe.

Il messaggio finisce con 0xFF.

ACCODAMENTO ($D73E)
    Il testo si accumula in un buffer a $122C8, con un contatore a un byte a
    $1285C: oltre 255 caratteri il messaggio viene troncato.
    I byte sotto 0x0A diventano cifre (viene sommato 0x30): e' cosi' che il
    gioco infila i numeri dentro le frasi.
    Se il carattere e' ! , . oppure ? e prima c'e' uno spazio, lo spazio viene
    mangiato.

ANDATA A CAPO ($88A8)
    Le righe vengono spezzate ogni 30 caratteri sull'ultimo spazio utile.

VINCOLI PER CHI RIORDINA
    - i token sono tutti da 2 byte, quindi spostarli e' semplice
    - dodici byte vengono riscritti dal gioco a runtime (vedi ANCORE):
      il token che li contiene deve restare al suo indirizzo esatto
    - fra un'ancora e l'altra si puo' riorganizzare liberamente, purche' il
      blocco mantenga la stessa dimensione e lo stesso numero di messaggi
"""

# I tre ingressi a 23648/23654/23658 sono letti da routine diverse ($A47C,
# $A4BE, $A528) che non usano questo formato: decodificati come token danno
# indici impossibili. La regione dei messaggi comincia a 23664, l'ingresso
# usato dal compositore $D638.
SCRIPT_INIZIO = 23664
SCRIPT_FINE   = 26967

# Byte che il codice riscrive a runtime: intoccabili, con il loro token.
# Verificate sul disassemblato: ognuna e' il byte BASSO di un token, scritto da
# un'istruzione "move.b d6,(a0)" preceduta da "lea $xxxx,a0". Nella prima
# versione c'era anche 24003, che nessuna istruzione scrive: tagliava a meta'
# un token del messaggio 21 e lo faceva leggere storto.
ANCORE = [23969, 24271, 24364, 25609, 25638,
          25681, 26055, 26709, 26738, 26804, 26864]

# Indirizzi da cui il codice entra a leggere: inizio di blocco.
INGRESSI = [23664]

TIPI = ('STRINGA', 'GRUPPO', 'RAM9', 'RAM32')


def tipo_token(t):
    if t & 0x2000: return 'RAM9'
    if t & 0x4000: return 'RAM32'
    if t & 0x8000: return 'GRUPPO'
    return 'STRINGA'


def valore_token(t):
    k = tipo_token(t)
    if k == 'GRUPPO': return t & 0x7FF
    if k == 'STRINGA': return t
    return t & 0xFF


def crea_token(kind, val):
    if kind == 'STRINGA': return val & 0x7FFF
    if kind == 'GRUPPO':  return 0x8000 | (val & 0x7FF)
    if kind == 'RAM9':    return 0x2000 | (val & 0xFF)
    if kind == 'RAM32':   return 0x4000 | (val & 0xFF)
    raise ValueError(kind)


def blocchi(img):
    """Divide la regione script nei tratti manovrabili fra le ancore."""
    tagli = sorted(set(INGRESSI + [a - 1 for a in ANCORE] + [SCRIPT_FINE]))
    out = []
    for i, a in enumerate(tagli[:-1]):
        b = tagli[i + 1]
        if b - a < 2: continue
        out.append((a, b))
    return out


def leggi_blocco(img, a, b):
    """Legge un blocco conservandone la struttura esatta: una sequenza di voci
    che sono messaggi (liste di token) oppure terminatori isolati. Cosi' la
    riscrittura puo' riprodurre il blocco byte per byte."""
    voci = []
    i = a
    while i < b:
        if img[i] == 0xFF:
            voci.append(('FF', None)); i += 1; continue
        toks = []
        spaiato = None
        while i < b and img[i] != 0xFF:
            if i + 1 >= b:
                spaiato = img[i]; i += 1; break      # byte finale dispari
            toks.append((img[i] << 8) | img[i + 1]); i += 2
        if toks: voci.append(('MSG', toks))
        if spaiato is not None: voci.append(('RAW', spaiato))
    return voci


def messaggi_gioco(img):
    """I messaggi come li numera il gioco: $D5CA salta d4 terminatori a
    partire da SCRIPT_INIZIO. E' la numerazione che usa il codice (registro
    d4), quindi quella da usare per ragionare sul contesto."""
    out = []
    i = SCRIPT_INIZIO
    while i < SCRIPT_FINE:
        st = i; t = []
        while i < SCRIPT_FINE and img[i] != 0xFF:
            t.append((img[i] << 8) | img[i + 1]); i += 2
        out.append({'offset': st, 'fine': i, 'token': t})
        i += 1
    return out


def leggi_messaggi(img):
    """Lista piatta dei messaggi con la loro posizione, per l'editor."""
    msgs = []
    for a, b in blocchi(img):
        off = a
        for tipo, toks in leggi_blocco(img, a, b):
            if tipo == 'FF':
                off += 1
            elif tipo == 'RAW':
                off += 1
            else:
                msgs.append({'blocco': (a, b), 'offset': off, 'token': toks})
                off += len(toks) * 2
    return msgs


def ancore_nel_blocco(a, b):
    return [x for x in ANCORE if a <= x < b]


def serializza(voci, img, a, b):
    """Riscrive un blocco dalla sua sequenza di voci, verificando dimensione,
    numero di terminatori e ancore."""
    out = bytearray()
    for tipo, toks in voci:
        if tipo == 'FF':
            out.append(0xFF)
        elif tipo == 'RAW':
            out.append(toks)
        else:
            for t in toks:
                out += bytes(((t >> 8) & 0xFF, t & 0xFF))
    orig = img[a:b]
    if len(out) > len(orig):
        raise ValueError(f"il blocco {a}-{b} sfora di {len(out)-len(orig)} byte")
    # il riempimento e' fatto di terminatori: messaggi vuoti, innocui
    out += b'\xFF' * (len(orig) - len(out))
    if out.count(0xFF) != orig.count(0xFF):
        raise ValueError(
            f"il blocco {a}-{b} ha {out.count(0xFF)} terminatori invece di "
            f"{orig.count(0xFF)}: il gioco conta i messaggi, non si puo' cambiare")
    for x in ancore_nel_blocco(a, b):
        if out[x - a] != orig[x - a]:
            raise ValueError(
                f"l'ancora a {x} e' stata spostata: quel byte il gioco lo "
                f"riscrive a runtime e deve restare dov'e'")
    return bytes(out)


# ------------------------------------------------------------ riempitivi
#
# Il gioco trova il messaggio N contando i terminatori dall'inizio, e dodici
# byte vengono riscritti a indirizzi fissi: per questo ogni blocco deve
# restare della stessa dimensione e con lo stesso numero di 0xFF. Togliere un
# token lascerebbe un buco di due byte: lo si tappa con un token che punta a
# una stringa di un solo spazio che nessun messaggio usa (S338). Non esiste un
# token che non stampi nulla: il compositore stampa sempre almeno un
# carattere, lo si e' verificato nel codice di $D73E.

RIEMPITIVO = 406            # tabella piatta: 68 item del gruppo 164 + S338


def _dim(voci):
    return sum(len(d) * 2 if t == 'MSG' else 1 for t, d in voci)


def bilancia(voci, orig, finale=None):
    """Rende il blocco della stessa dimensione dell'originale.

    Prima toglie tutti i riempitivi presenti (cosi' si possono aggiungere
    token finche' ce ne sono), poi ne rimette quanti ne servono. Vanno in coda
    a un messaggio che finisce una frase (! ? .), dove un paio di spazi in piu'
    non si vedono; se il messaggio accorciato non chiude una frase (per
    esempio "OK CAPO, " che il gioco fa seguire da un altro pezzo) finiscono
    nel messaggio piu' vicino che la chiude.

    Solleva ValueError se il blocco, anche senza riempitivi, e' troppo lungo."""
    nuove = []
    for t, d in voci:
        if t == 'MSG':
            d = [x for x in d if x != RIEMPITIVO] or [RIEMPITIVO]
            nuove.append((t, list(d)))
        else:
            nuove.append((t, d))
    manca = _dim(orig) - _dim(nuove)
    if manca < 0:
        raise ValueError(f"{-manca} byte di troppo: togli {(-manca + 1) // 2} "
                         f"token da un messaggio dello stesso blocco")
    if manca % 2:
        raise ValueError("dimensione dispari: la struttura del blocco e' cambiata")
    n = manca // 2
    if not n:
        return nuove
    msg = [k for k, (t, _) in enumerate(nuove) if t == 'MSG']
    buoni = [k for k in msg if finale is None or finale(nuove[k][1])]
    # chi ha perso token, in ordine
    debito = []
    for k in msg:
        o = orig[k][1] if k < len(orig) and orig[k][0] == 'MSG' else []
        d = len(o) - len(nuove[k][1])
        if d > 0: debito.append((k, d))
    if not debito:
        debito = [(msg[-1], n)]
    for k, d in debito:
        if not n: break
        q = min(d, n)
        if k in buoni or not buoni:
            dove = k
        else:
            dopo = [j for j in buoni if j > k]
            dove = dopo[0] if dopo else buoni[-1]
        nuove[dove][1].extend([RIEMPITIVO] * q)
        n -= q
    if n:
        dove = buoni[-1] if buoni else msg[-1]
        nuove[dove][1].extend([RIEMPITIVO] * n)
    return nuove


# ------------------------------------------------------ titoli e nomi band
#
# Titoli delle canzoni e nomi delle band non sono messaggi: il gioco li genera
# da due tabelle di modelli, liste di token nello stesso formato a 2 byte
# separate da 0xFF. Il generatore ($8918 per le band, $A900 per le canzoni)
# sceglie il modello N contando i terminatori e copia ogni token in un record
# in RAM (1 byte + 3 byte per token): per i gruppi estrae subito l'item a
# caso e lo memorizza, cosi' il titolo resta lo stesso per tutta la partita.
#
#   canzoni  $11E37 (40247-40710)  61 modelli, record da 20 byte: max 6 token
#            gli indici arrivano da una tabella a $B43E e sono tutti < 61:
#            eventuali terminatori in piu' in fondo non vengono mai usati
#   band     $120E2 (40930-40992)   8 modelli, record da 32 byte: max 10 token
#
# Le due tabelle stanno a indirizzi assoluti e sono seguite da altri dati:
# la dimensione non puo' cambiare, il numero di modelli si'... solo in piu'.

MODELLI = {
    (40247, 40710): ('canzone', 61, 6),
    (40930, 40992): ('band', 8, 10),
}


def blocchi_modelli():
    return list(MODELLI)


def bilancia_modelli(voci, orig, a, b):
    """Toglie i riempitivi e tappa lo spazio avanzato con terminatori in
    fondo, cioe' modelli vuoti che il gioco non sceglie mai."""
    nome, quanti, maxt = MODELLI[(a, b)]
    nuove = []
    for t, d in voci:
        if t == 'MSG':
            d = [x for x in d if x != RIEMPITIVO]
            if d: nuove.append((t, list(d)))
        elif t == 'FF':
            nuove.append((t, d))
    # la struttura e': modello FF modello FF ... tolgo gli FF finali in eccesso
    while len(nuove) > 1 and nuove[-1][0] == 'FF' and nuove[-2][0] == 'FF':
        nuove.pop()
    n = sum(1 for t, _ in nuove if t == 'FF')
    if n < quanti:
        raise ValueError(f"{nome}: servono {quanti} modelli, ce ne sono {n}")
    for t, d in nuove:
        if t == 'MSG' and len(d) > maxt:
            raise ValueError(f"{nome}: un modello ha {len(d)} token, il massimo e' {maxt} "
                             f"(il record in RAM non ne contiene di piu')")
    manca = _dim(orig) - _dim(nuove)
    if manca < 0:
        raise ValueError(f"{nome}: {-manca} byte di troppo, togli {(-manca+1)//2} token")
    nuove += [('FF', None)] * manca
    return nuove


def serializza_modelli(voci, img, a, b):
    out = bytearray()
    for tipo, toks in voci:
        if tipo == 'FF':
            out.append(0xFF)
        else:
            for t in toks:
                out += bytes(((t >> 8) & 0xFF, t & 0xFF))
    if len(out) != b - a:
        raise ValueError(f"modelli {a}-{b}: {len(out)} byte invece di {b-a}")
    return bytes(out)


# ------------------------------------------------ testi fuori dalla tabella
#
# Calendario: giorni (4 caratteri l'uno) e mesi (3 caratteri, dicembre
# ripetuto) stanno in chiaro a 40839 e 40867.
# Etichetta SALES: e' disegnata nel pannello in basso, un'immagine grezza a
# 320 pixel e 4 bitplane interlacciati a parole (8 byte ogni 16 pixel) che
# comincia a 345610. L'etichetta occupa x 268-307, y 95-101.

CALENDARIO = [(40839, b"MON TUESWEDSTHURFRI SAT SUN ", b"LUN MAR MER GIO VEN SAB DOM "),
              (40867, b"JANFEBMARAPRMAYJUNJULAUGSEPOCTNOVDECDEC",
                      b"GENFEBMARAPRMAGGIULUGAGOSETOTTNOVDICDIC")]

PANNELLO = 345610
ETICHETTA = "VENDITE"
_GLIFI = {
    'V': ["##.##", "##.##", "##.##", "##.##", "#####", ".###.", "..#.."],
    'E': [".####", "#####", "##...", "####.", "##...", "#####", ".####"],
    'N': ["##..##", "###.##", "######", "##.###", "##..##", "##..##", "##..##"],
    'D': ["####.", "#####", "##.##", "##.##", "##.##", "#####", "####."],
    'I': ["##"] * 7,
    'T': ["######", "######", "..##..", "..##..", "..##..", "..##..", "..##.."],
}


def _pixel(img, x, y, c):
    wc, bit = divmod(x, 16)
    bit = 15 - bit
    for p in range(4):
        o = PANNELLO + y * 160 + wc * 8 + p * 2 + (0 if bit >= 8 else 1)
        m = 1 << (bit % 8)
        if (c >> p) & 1: img[o] |= m
        else: img[o] &= ~m & 0xFF


def _leggi_pixel(img, x, y):
    wc, bit = divmod(x, 16)
    bit = 15 - bit
    c = 0
    for p in range(4):
        o = PANNELLO + y * 160 + wc * 8 + p * 2 + (0 if bit >= 8 else 1)
        c |= ((img[o] >> (bit % 8)) & 1) << p
    return c



# ------------------------------------------------ crediti nell'introduzione
#
# La prima delle quattro immagini dell'introduzione (quella dell'astronauta
# sulla bombola) e' compressa RLE a 241238 ($42F56 nel gioco); la successiva
# comincia a 253375 ($45EBF), quindi la nuova codifica deve stare in 12137
# byte. La scompatta $DCAC: byte n < $80 = copia n+1 byte, n > $80 = ripeti
# il byte seguente 257-n volte, $80 = niente; si ferma quando ha scritto piu'
# di $7D00 byte. Il risultato e' 320x200 a 4 piani interlacciati per riga
# (160 byte a riga: 40 del piano 0, 40 del piano 1...).
#
# Sulla bombola c'e' "SUPPLIED / BY / BRI", ruotato di 90 gradi in senso
# antiorario (si legge dal basso in alto, la prima riga e' a sinistra), in
# lettere alte 6 pixel. Il colore di ogni lettera e' quello della fascia di
# sfumatura della bombola in quella riga, scurito: F->9, B->7, 9->5, 7->3, 5->3.

INTRO = 0x42F56 - 0x8100
INTRO_FINE = 0x45EBF - 0x8100
CREDITI = [("TRADOTTO", 284), ("DA", 293), ("LOLLO", 302)]   # (testo, x della cima)
CREDITI_CENTRO = 140          # riga di centro della bombola
_SCURO = {0xF: 0x9, 0xB: 0x7, 0x9: 0x5, 0x7: 0x3, 0x5: 0x3}
_GLIFI_V = {    # 6 righe (dall'alto), larghezza 2-3
    'T': ["###", ".#.", ".#.", ".#.", ".#.", ".#."],
    'R': ["##.", "#.#", "#.#", "##.", "#.#", "#.#"],
    'A': [".#.", "#.#", "#.#", "###", "#.#", "#.#"],
    'D': ["##.", "#.#", "#.#", "#.#", "#.#", "##."],
    'O': [".#.", "#.#", "#.#", "#.#", "#.#", ".#."],
    'L': ["#.", "#.", "#.", "#.", "#.", "##"],
}
# la S di SUPPLIED, in basso a sinistra: se c'e' l'immagine e' ancora inglese
_FIRMA_EN = [(284, 153, 0x3), (285, 153, 0x3), (286, 153, 0x3), (287, 153, 0x7),
             (284, 152, 0x5), (285, 152, 0x9), (286, 152, 0x5)]


def rle_scompatta(d, i):
    """Come $DCAC. Restituisce (dati, byte consumati)."""
    out = bytearray(); s = i
    while len(out) <= 0x7D00:
        n = d[i]; i += 1
        if n == 0x80:
            continue
        if n < 0x80:
            out += d[i:i + n + 1]; i += n + 1
        else:
            out += bytes([d[i]]) * (257 - n); i += 1
    return bytes(out), i - s


def rle_compatta(b):
    """PackBits alla lunghezza minima (programmazione dinamica)."""
    n = len(b)
    INF = 1 << 30
    costo = [INF] * (n + 1); da = [None] * (n + 1)
    costo[n] = 0
    for i in range(n - 1, -1, -1):
        # ripetizione
        k = 1
        while i + k < n and k < 128 and b[i + k] == b[i]:
            k += 1
        for L in range(2, k + 1):
            c = 2 + costo[i + L]
            if c < costo[i]: costo[i] = c; da[i] = ('r', L)
        # copia letterale
        for L in range(1, min(128, n - i) + 1):
            c = 1 + L + costo[i + L]
            if c < costo[i]: costo[i] = c; da[i] = ('c', L)
    out = bytearray(); i = 0
    while i < n:
        t, L = da[i]
        if t == 'r': out += bytes([257 - L, b[i]])
        else: out += bytes([L - 1]) + b[i:i + L]
        i += L
    return bytes(out)


def _px_intro(buf, x, y, c=None):
    o = y * 160 + x // 8; m = 0x80 >> (x % 8)
    if c is None:
        return sum(((buf[o + p * 40] & m) != 0) << p for p in range(4))
    for p in range(4):
        if (c >> p) & 1: buf[o + p * 40] |= m
        else: buf[o + p * 40] &= ~m & 0xFF


def patch_crediti(img):
    img = bytearray(img)
    buf, usati = rle_scompatta(img, INTRO)
    buf = bytearray(buf)
    if any(_px_intro(buf, x, y) != c for x, y, c in _FIRMA_EN):
        return bytes(img)                       # gia' fatto, o immagine diversa
    fascia = {y: _px_intro(buf, 276, y) for y in range(125, 157)}
    for y in range(125, 157):                   # cancella la scritta inglese
        for x in range(280, 310):
            _px_intro(buf, x, y, fascia[y])
    for testo, x0 in CREDITI:
        larg = sum(len(_GLIFI_V[ch][0]) for ch in testo) + len(testo) - 1
        y = CREDITI_CENTRO + larg // 2          # si scrive dal basso in alto
        for ch in testo:
            g = _GLIFI_V[ch]
            for c in range(len(g[0])):
                for r in range(6):
                    if g[r][c] == '#':
                        _px_intro(buf, x0 + r, y, _SCURO[fascia[y]])
                y -= 1
            y -= 1
    nuovo = rle_compatta(bytes(buf))
    if len(nuovo) > INTRO_FINE - INTRO:
        raise ValueError(f"crediti dell'introduzione: {len(nuovo)} byte, "
                         f"ne stanno {INTRO_FINE - INTRO}")
    img[INTRO:INTRO + len(nuovo)] = nuovo
    return bytes(img)


# Menu dei giorni di prove (#27): usa la finestra 5 della tabella a $11AF6
# (4 byte: riga e colonna dell'angolo in alto a sinistra, riga e colonna di
# quello in basso a destra). Il gioco riempie una riga fino alla larghezza
# della finestra e la tronca all'ultimo spazio, e ogni riga e' un'opzione:
# con 8 colonne ci stava "1 DAY. ". "1 GIORNO " e' di 9, ma in 9 colonne
# l'ultima opzione arriva al bordo e il gioco scende oltre la finestra e la
# cancella (menu vuoto): servono 10. La finestra 5 la usa solo questo menu
# (le altre routine con d6=5 non sono finestre).
FINESTRA_GIORNI = 0x11AF6 - 0x8100 + 5 * 4
FINESTRA_GIORNI_EN = bytes([14, 16, 19, 24])
FINESTRA_GIORNI_IT = bytes([14, 16, 19, 26])


def patch_fissi(img):
    """Traduce i testi che non stanno nella tabella. Controlla prima che i
    byte siano quelli inglesi: se non lo sono, non tocca nulla."""
    img = bytearray(img)
    for off, en, it in CALENDARIO:
        if img[off:off + len(en)] == en:
            img[off:off + len(it)] = it
    # etichetta: sfondo 2, lettere 0xA in alto, retino A/E, ultima riga E
    if _leggi_pixel(img, 268, 96) == 0xA and _leggi_pixel(img, 267, 95) == 1:
        for y in range(95, 102):
            for x in range(268, 308):
                _pixel(img, x, y, 2)
        x0 = 268
        larg = sum(len(_GLIFI[ch][0]) for ch in ETICHETTA) + len(ETICHETTA) - 1
        x0 += (40 - larg) // 2
        for ch in ETICHETTA:
            g = _GLIFI[ch]
            for r, riga in enumerate(g):
                y = 95 + r
                for k, v in enumerate(riga):
                    if v != '#': continue
                    x = x0 + k
                    if r <= 3: c = 0xA
                    elif r == 6: c = 0xE
                    else: c = 0xE if (x + y) % 2 == 0 else 0xA
                    _pixel(img, x, y, c)
            x0 += len(g[0]) + 1
    if img[FINESTRA_GIORNI:FINESTRA_GIORNI + 4] == FINESTRA_GIORNI_EN:
        img[FINESTRA_GIORNI:FINESTRA_GIORNI + 4] = FINESTRA_GIORNI_IT
    return patch_crediti(bytes(img))
