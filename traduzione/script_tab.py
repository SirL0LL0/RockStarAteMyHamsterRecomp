# -*- coding: utf-8 -*-
"""Scheda dell'editor per riordinare i token dei messaggi."""
import json
import os
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import script_rsamh as S

SALVATAGGIO = 'rockstar_script_ITA.json'


def con_barre(padre, cls, orizzontale=False, **kw):
    """Crea un widget scorrevole: restituisce (cornice, widget). La cornice va
    impaginata al posto del widget."""
    f = ttk.Frame(padre)
    w = cls(f, **kw)
    sy = ttk.Scrollbar(f, orient='vertical', command=w.yview)
    w.configure(yscrollcommand=sy.set)
    sy.pack(side='right', fill='y')
    if orizzontale:
        sx = ttk.Scrollbar(f, orient='horizontal', command=w.xview)
        w.configure(xscrollcommand=sx.set)
        sx.pack(side='bottom', fill='x')
    w.pack(side='left', fill='both', expand=True)
    return f, w


class SchedaScript(ttk.Frame):
    def __init__(self, padre, app):
        super().__init__(padre)
        self.app = app
        self.voci = {}          # blocco -> lista di voci modificabile
        for a, b in S.blocchi(app.img) + S.blocchi_modelli():
            self.voci[(a, b)] = S.leggi_blocco(app.img, a, b)
        self.msg = None
        self._ui()
        self._riempi()

    # ---------------------------------------------------------- interfaccia
    def _ui(self):
        top = ttk.Frame(self); top.pack(fill='x')
        ttk.Button(top, text="Applica al binario", command=self.applica).pack(side='left')
        ttk.Button(top, text="Salva", command=self.salva).pack(side='left', padx=(8, 2))
        ttk.Button(top, text="Carica", command=self.carica).pack(side='left')
        ttk.Button(top, text="Ripristina messaggio",
                   command=self.ripristina).pack(side='left', padx=8)
        self.lbl = ttk.Label(top, text=''); self.lbl.pack(side='right')

        f = ttk.Frame(self); f.pack(fill='x', pady=2)
        ttk.Label(f, text="cerca").pack(side='left')
        self.cerca = tk.StringVar()
        self.cerca.trace_add('write', lambda *a: self._riempi())
        ttk.Entry(f, textvariable=self.cerca).pack(side='left', fill='x', expand=True, padx=4)

        p = ttk.PanedWindow(self, orient='horizontal')
        p.pack(fill='both', expand=True, pady=4)

        sx = ttk.Frame(p); p.add(sx, weight=1)
        fl, self.lista = con_barre(sx, ttk.Treeview, columns=('o', 'n', 't'),
                                   show='headings')
        for c, w, t in (('o', 110, 'messaggio'), ('n', 50, 'token'), ('t', 300, 'frase')):
            self.lista.heading(c, text=t); self.lista.column(c, width=w)
        fl.pack(fill='both', expand=True)
        self.lista.bind('<<TreeviewSelect>>', self.scegli)

        dx = ttk.Frame(p); p.add(dx, weight=1)
        ttk.Label(dx, text="token del messaggio (l'ordine e' quello della frase)").pack(anchor='w')
        ft, self.tok = con_barre(dx, ttk.Treeview, columns=('k', 'v', 'x'),
                                 show='headings', height=12)
        for c, w, t in (('k', 80, 'tipo'), ('v', 50, 'valore'), ('x', 260, 'testo')):
            self.tok.heading(c, text=t); self.tok.column(c, width=w)
        ft.pack(fill='both', expand=True)

        b = ttk.Frame(dx); b.pack(fill='x', pady=3)
        ttk.Button(b, text="▲ su", command=lambda: self.sposta(-1)).pack(side='left')
        ttk.Button(b, text="▼ giu", command=lambda: self.sposta(1)).pack(side='left', padx=3)
        ttk.Button(b, text="elimina", command=self.elimina).pack(side='left', padx=3)
        ttk.Button(b, text="duplica", command=self.duplica).pack(side='left')
        ttk.Button(b, text="+ aggiungi...", command=self.aggiungi).pack(side='left', padx=3)
        ttk.Label(dx, foreground='#666666', wraplength=420, justify='left',
                  text="I token tolti vengono rimpiazzati da soli con riempitivi di "
                       "uno spazio, messi in coda a una frase che finisce con ! ? . "
                       "cosi' non si vedono; se aggiungi token, i riempitivi del "
                       "blocco vengono consumati per primi.").pack(anchor='w')
        ttk.Label(dx, text="anteprima (i gruppi mostrano il primo item; "
                           "in gioco ne esce uno a caso)").pack(anchor='w', pady=(6, 0))
        fp, self.prev = con_barre(dx, tk.Text, height=6, wrap='word',
                                  font=('TkFixedFont', 10))
        fp.pack(fill='x')
        self.prev.tag_config('en', foreground='#666666')
        self.prev.tag_config('bad', foreground='#bb0000')
        self.prev.tag_config('ctx', foreground='#2060a0')

    # ------------------------------------------------------------- utilita'
    def testo(self, t, tab):
        k = S.tipo_token(t); v = S.valore_token(t)
        if t == S.RIEMPITIVO:
            return ' '
        if k == 'STRINGA':
            p = self.app.piatte(tab)
            return p[v] if v < len(p) else f'<stringa {v}?>'
        if k == 'GRUPPO':
            g = [x for x in tab if x['type'] == 'GROUP']
            return g[v]['items'][0] if v < len(g) else f'<gruppo {v}?>'
        return f'<{k} {v}>'

    def rendi(self, toks, tab):
        return ''.join(self.testo(t, tab) for t in toks)

    def _riempi(self):
        self.lista.delete(*self.lista.get_children())
        self.indice = []
        self.numero = {}
        ngioco = 0          # conta i terminatori: e' il numero del messaggio nel gioco
        seguito = False     # il pezzo continua un messaggio del blocco prima
        for (a, b), voci in sorted(self.voci.items()):
            off = a
            modello = S.MODELLI.get((a, b))
            nmod = 0
            for k, (tipo, dato) in enumerate(voci):
                if tipo in ('FF', 'RAW'):
                    if tipo == 'FF' and not modello:
                        ngioco += 1; seguito = False
                    off += 1; continue
                testo = self.rendi(dato, self.app.it).strip()
                if modello:
                    etichetta = f"{modello[0]} {nmod}"; nmod += 1
                else:
                    etichetta = f"#{ngioco}" + (" (seguito)" if seguito else "")
                    seguito = True
                self.numero[((a, b), k)] = None if modello else ngioco
                q = self.cerca.get().lower() if hasattr(self, 'cerca') else ''
                orig = S.leggi_blocco(self.app.img_orig, a, b)
                inglese = self.rendi(orig[k][1], self.app.en).strip() \
                    if q and k < len(orig) and orig[k][0] == 'MSG' else ''
                if q == 'titoli' and modello:
                    q2 = ''
                else:
                    q2 = q
                if (len(testo) > 4 or modello) and (not q2 or q2 in testo.lower()
                                                    or q2 in inglese.lower()
                                                    or q2 == str(etichetta).split()[0].lower()):
                    iid = str(len(self.indice))
                    self.indice.append(((a, b), k))
                    self.lista.insert('', 'end', iid=iid,
                                      values=(etichetta, len(dato), testo[:70]))
                off += len(dato) * 2
        self.lbl.config(text=f"{len(self.indice)} messaggi")

    def corrente(self):
        s = self.lista.selection()
        return self.indice[int(s[0])] if s else None

    def scegli(self, _=None):
        c = self.corrente()
        if not c: return
        blocco, k = c
        self.msg = c
        toks = self.voci[blocco][k][1]
        self.tok.delete(*self.tok.get_children())
        for j, t in enumerate(toks):
            self.tok.insert('', 'end', iid=str(j),
                            values=(S.tipo_token(t), S.valore_token(t),
                                    repr(self.testo(t, self.app.it))))
        self.anteprima()

    def anteprima(self):
        if not self.msg: return
        blocco, k = self.msg
        toks = self.voci[blocco][k][1]
        orig = S.leggi_blocco(self.app.img_orig, *blocco)[k][1]
        self.prev.delete('1.0', 'end')
        from rsamh_editor import a_video
        self.prev.insert('end', 'EN  ' + a_video(self.rendi(orig, self.app.en)).strip() + '\n', 'en')
        it = a_video(self.rendi(toks, self.app.it)).strip()
        male = len(it) > 255
        self.prev.insert('end', 'IT  ' + it + '\n', 'bad' if male else '')
        from rsamh_editor import CONTESTO
        n = getattr(self, 'numero', {}).get(self.msg)
        if n is not None:
            for c in CONTESTO.get(n, ['contesto non ricavato: composto dal codice']):
                self.prev.insert('end', '    ' + c + '\n', 'ctx')
        a, b = blocco
        if blocco in S.MODELLI:
            nome, quanti, maxt = S.MODELLI[blocco]
            n = len([x for x in toks if x != S.RIEMPITIVO])
            voci = [(t, [x for x in d if x != S.RIEMPITIVO]) if t == 'MSG' else (t, d)
                    for t, d in self.voci[blocco]]
            liberi = (b - a) - S._dim([(t, d) for t, d in voci
                                       if not (t == 'FF')]) - quanti
            self.prev.insert('end', f'\nmodello di {nome}: {n}/{maxt} token'
                                    + ('   TROPPI' if n > maxt else '')
                                    + f'   - spazio libero nella tabella: {liberi // 2} token',
                             'bad' if n > maxt or liberi < 0 else '')
            return
        voci = [(t, [x for x in d if x != S.RIEMPITIVO]) if t == 'MSG' else (t, d)
                for t, d in self.voci[blocco]]
        usati = S._dim(voci)
        liberi = (b - a) - usati
        if liberi < 0:
            self.prev.insert('end', f'\nblocco {a}-{b}: SFORA di {-liberi} byte: '
                                    f'togli {(-liberi + 1) // 2} token in questo blocco', 'bad')
        else:
            self.prev.insert('end', f'\nblocco {a}-{b}: {liberi // 2} riempitivi '
                                    f'(= token che puoi ancora aggiungere)')

    # ------------------------------------------------------------ modifiche
    def _sel(self):
        s = self.tok.selection()
        return int(s[0]) if s else None

    def sposta(self, d):
        j = self._sel()
        if j is None or not self.msg: return
        blocco, k = self.msg
        toks = self.voci[blocco][k][1]
        n = j + d
        if not 0 <= n < len(toks): return
        toks[j], toks[n] = toks[n], toks[j]
        self.scegli(); self.tok.selection_set(str(n)); self._riempi_riga()

    def elimina(self):
        j = self._sel()
        if j is None or not self.msg: return
        blocco, k = self.msg
        toks = self.voci[blocco][k][1]
        if len(toks) <= 1:
            messagebox.showwarning("No", "Un messaggio non puo' restare senza token.")
            return
        del toks[j]; self.scegli(); self._riempi_riga()

    def duplica(self):
        j = self._sel()
        if j is None or not self.msg: return
        blocco, k = self.msg
        toks = self.voci[blocco][k][1]
        toks.insert(j, toks[j]); self.scegli(); self._riempi_riga()

    def aggiungi(self):
        """Inserisce un token qualsiasi (stringa o gruppo) dopo quello
        selezionato, o in fondo se non c'e' selezione."""
        if not self.msg:
            messagebox.showinfo("Aggiungi", "Scegli prima un messaggio."); return
        w = tk.Toplevel(self); w.title("Aggiungi token"); w.geometry("560x520")
        q = tk.StringVar()
        e = ttk.Entry(w, textvariable=q); e.pack(fill='x', padx=6, pady=6); e.focus()
        fl, lst = con_barre(w, ttk.Treeview, columns=('c', 'x', 'en'), show='headings')
        for c, wd, t in (('c', 70, 'token'), ('x', 230, 'italiano'), ('en', 230, 'inglese')):
            lst.heading(c, text=t); lst.column(c, width=wd)
        fl.pack(fill='both', expand=True, padx=6)
        voci = []
        piatte_it = self.app.piatte(self.app.it)
        piatte_en = self.app.piatte(self.app.en)
        for i, (x, y) in enumerate(zip(piatte_it, piatte_en)):
            if i == S.RIEMPITIVO: continue
            voci.append((S.crea_token('STRINGA', i), f"S{i}", x, y))
        gi = [v for v in self.app.it if v['type'] == 'GROUP']
        ge = [v for v in self.app.en if v['type'] == 'GROUP']
        for i, (x, y) in enumerate(zip(gi, ge)):
            voci.append((S.crea_token('GRUPPO', i), f"G{i}",
                         ' | '.join(x['items']), ' | '.join(y['items'])))

        def filtra(*_):
            lst.delete(*lst.get_children())
            f = q.get().lower()
            for k, (t, c, x, y) in enumerate(voci):
                if not f or f in x.lower() or f in y.lower() or f == c.lower():
                    lst.insert('', 'end', iid=str(k), values=(c, repr(x), y))
        q.trace_add('write', filtra); filtra()

        def ok(*_):
            s = lst.selection()
            if not s: return
            t = voci[int(s[0])][0]
            blocco, k = self.msg
            toks = self.voci[blocco][k][1]
            j = self._sel()
            pos = len(toks) if j is None else j + 1
            toks.insert(pos, t)
            self.scegli(); self.tok.selection_set(str(pos)); self._riempi_riga()
            w.destroy()
        lst.bind('<Double-1>', ok)
        ttk.Button(w, text="Inserisci dopo il token selezionato", command=ok).pack(pady=6)

    def _riempi_riga(self):
        c = self.corrente()
        if not c: return
        blocco, k = c
        toks = self.voci[blocco][k][1]
        s = self.lista.selection()
        if s:
            off = self.lista.set(s[0], 'o')
            self.lista.item(s[0], values=(off, len(toks),
                                          self.rendi(toks, self.app.it).strip()[:70]))

    def ripristina(self):
        if not self.msg: return
        blocco, k = self.msg
        self.voci[blocco][k] = S.leggi_blocco(self.app.img_orig, *blocco)[k]
        self.scegli(); self._riempi_riga()

    # -------------------------------------------------------------- scrittura
    def finale(self, toks):
        # si guarda l'inglese: i segni di punteggiatura sono gli stessi token
        # in tutte le tabelle, e cosi' il risultato non dipende da quale
        # tabella e' aperta
        t = self.rendi([x for x in toks if x != S.RIEMPITIVO], self.app.en)
        return t.endswith(('! ', '? ', '. '))

    def applica(self):
        try:
            nuova = bytearray(self.app.img)
            for (a, b), voci in self.voci.items():
                orig = S.leggi_blocco(self.app.img_orig, a, b)
                if (a, b) in S.MODELLI:
                    pieno = S.bilancia_modelli(voci, orig, a, b)
                    nuova[a:b] = S.serializza_modelli(pieno, self.app.img_orig, a, b)
                    continue
                try:
                    pieno = S.bilancia(voci, orig, self.finale)
                except ValueError as ex:
                    raise ValueError(f"blocco {a}-{b}: {ex}")
                nuova[a:b] = S.serializza(pieno, self.app.img_orig, a, b)
        except ValueError as ex:
            messagebox.showerror("Non posso applicare", str(ex)); return
        self.app.img = bytes(nuova)
        # i messaggi sono cambiati: vanno riletti, o la scheda Frasi composte e
        # la verifica continuerebbero a ragionare su quelli di prima
        import rsamh_editor
        self.app.msgs = rsamh_editor.messaggi(self.app.img)
        self.app.stato("script applicati: ora genera l'eseguibile dalla barra in alto")
        return True

    # ------------------------------------------------- salvataggio su file
    def salva(self):
        f = filedialog.asksaveasfilename(defaultextension='.json',
                                         initialfile=SALVATAGGIO)
        if not f: return
        dati = {f"{a}-{b}": [[t, d if t == 'MSG' else (d if t == 'RAW' else None)]
                             for t, d in voci]
                for (a, b), voci in self.voci.items()}
        json.dump(dati, open(f, 'w'), indent=1)
        self.app.stato(f"riordini salvati in {os.path.basename(f)}")

    def carica(self, percorso=None):
        f = percorso or filedialog.askopenfilename(filetypes=[('JSON', '*.json')])
        if not f or not os.path.isfile(f): return
        dati = json.load(open(f))
        saltati = []
        for chiave, voci in dati.items():
            a, b = (int(x) for x in chiave.split('-'))
            if (a, b) not in self.voci:
                # file salvato con la vecchia divisione in blocchi (c'era
                # un'ancora sbagliata a 24003): quei riordini vanno rifatti
                saltati.append(chiave); continue
            self.voci[(a, b)] = [(t, d) for t, d in voci]
        if saltati:
            messagebox.showwarning(
                "Blocchi ignorati",
                "Questi blocchi vengono da una versione precedente e non "
                "corrispondono piu': " + ', '.join(saltati) +
                ". I messaggi che contengono restano come nell'originale.")
        self._riempi()
        self.app.stato(f"riordini caricati da {os.path.basename(f)}")
