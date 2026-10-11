# -*- coding: utf-8 -*-
"""
asm68k.py - mini assemblatore con etichette.

Serve a non calcolare piu' a mano gli spostamenti dei salti: sono gia' stati
tre gli errori di quel tipo, e sono invisibili alla lettura del disassemblato
(un "beq.b $3e" sembra giusto anche quando $3e e' il salto indietro del ciclo
da cui doveva uscire).

Uso:
    a = Asm()
    a.eti('ciclo')
    a.b(b'\\x20\\x11')                  # move.l (a1),d0
    a.salto('\\x67', 'fine')            # beq.b fine   (corto)
    a.saltoW('\\x60\\x00', 'ciclo')     # bra.w ciclo  (lungo)
    a.eti('fine')
    dati = a.chiudi()

chiudi() verifica anche che ogni salto corto stia nei -128..127 e che nessuna
etichetta sia rimasta irrisolta.

Estensione per slave WHDLoad:
    a.dc_w(1234)                        # dc.w 1234
    a.dc_l(0x12345678)                  # dc.l $12345678
    a.dc_b(0x42)                       # dc.b $42
    a.stringa('testo')                  # stringa con terminatore 0
    a.stringa('testo', termina=False)   # stringa senza terminatore
    a.jsr_resload(8)                    # jsr 8(a4) - chiamata resload
    a.jmp_ind(0)                        # jmp (a0) - salto indiretto
    a.lea_pc(1, 'etichetta')            # lea etichetta(pc), a1
"""

import struct


class Asm:
    def __init__(self):
        self.buf = bytearray()
        self.etichette = {}
        self.da_fare = []      # (posizione, etichetta, 'b'|'w'|'l', base)
        self.rilocare = []     # posizioni dei puntatori assoluti (HUNK_RELOC32)

    def puntatore(self, nome):
        """dc.l etichetta, assoluto: vale l'offset nel blocco e va nella lista
        da rilocare (l'eseguibile aggiunge HUNK_RELOC32, AmigaDOS somma
        l'indirizzo di caricamento). Il blocco deve stare in testa all'hunk."""
        self.rilocare.append(len(self.buf))
        self.da_fare.append((len(self.buf), nome, 'l', 0))
        self.buf.extend(b'\x00\x00\x00\x00')
        return self

    def b(self, dati):
        self.buf.extend(dati)
        return self

    def eti(self, nome):
        if nome in self.etichette:
            raise ValueError(f"etichetta doppia: {nome}")
        self.etichette[nome] = len(self.buf)
        return self

    def salto(self, opcode, nome):
        """Salto corto: opcode di un byte piu' spostamento di un byte."""
        self.buf.extend(opcode if isinstance(opcode, bytes) else opcode.encode('latin1'))
        # Nel 68000 lo spostamento di un salto corto si conta dall'indirizzo
        # dell'istruzione piu' due, cioe' dal byte DOPO lo spostamento stesso.
        self.da_fare.append((len(self.buf), nome, 'b', len(self.buf) + 1))
        self.buf.append(0)
        return self

    def saltoW(self, opcode, nome):
        """Salto lungo: opcode piu' spostamento di due byte."""
        self.buf.extend(opcode if isinstance(opcode, bytes) else opcode.encode('latin1'))
        self.da_fare.append((len(self.buf), nome, 'w', len(self.buf)))
        self.buf.extend(b'\x00\x00')
        return self

    def dato32(self, valore):
        self.buf.extend(struct.pack('>I', valore))
        return self

    def rif32(self, nome, base):
        """Longword che vale (etichetta - base), per gli adda.l dopo lea 0(pc)."""
        self.da_fare.append((len(self.buf), nome, 'l', base))
        self.buf.extend(b'\x00\x00\x00\x00')
        return self

    def pos(self):
        return len(self.buf)

    def lunghezza(self, allinea=2):
        """Lunghezza definitiva, senza risolvere le etichette: serve quando una
        di esse punta a qualcosa che viene dopo il blocco stesso."""
        n = len(self.buf)
        while n % allinea: n += 2
        return n

    def chiudi(self, allinea=2):
        while len(self.buf) % allinea:
            self.buf.extend(b'\x4E\x71')
        for posizione, nome, tipo, base in self.da_fare:
            if nome not in self.etichette:
                raise ValueError(f"etichetta mai definita: {nome}")
            dest = self.etichette[nome]
            if tipo == 'l':
                # puo' essere negativo: il blocco a cui ci si riferisce puo'
                # trovarsi prima del codice che lo raggiunge
                struct.pack_into('>i', self.buf, posizione, dest - base)
                continue
            d = dest - base
            if tipo == 'b':
                if not -128 <= d <= 127:
                    raise ValueError(f"salto corto fuori portata verso {nome}: {d}")
                if d == 0:
                    raise ValueError(f"salto corto a spostamento zero verso {nome}")
                struct.pack_into('>b', self.buf, posizione, d)
            else:
                if not -32768 <= d <= 32767:
                    raise ValueError(f"salto lungo fuori portata verso {nome}: {d}")
                struct.pack_into('>h', self.buf, posizione, d)
        return bytes(self.buf)

    # === Estensione per slave WHDLoad ===

    def dc_w(self, valore):
        """Scrive un word (16 bit) big-endian. Accetta int o stringa (etichetta)."""
        if isinstance(valore, str):
            self.da_fare.append((len(self.buf), valore, 'w', 0))
            self.buf.extend(b'\x00\x00')
        else:
            self.buf.extend(struct.pack('>H', valore & 0xFFFF))
        return self

    def dc_l(self, valore):
        """Scrive un longword (32 bit) big-endian. Accetta int o stringa (etichetta)."""
        if isinstance(valore, str):
            self.da_fare.append((len(self.buf), valore, 'l', 0))
            self.buf.extend(b'\x00\x00\x00\x00')
        else:
            self.buf.extend(struct.pack('>I', valore & 0xFFFFFFFF))
        return self

    def dc_b(self, valore):
        """Scrive un byte o una sequenza di byte."""
        if isinstance(valore, int):
            self.buf.append(valore & 0xFF)
        else:
            self.buf.extend(valore if isinstance(valore, bytes) else valore.encode('latin1'))
        return self

    def stringa(self, s, termina=True):
        """Scrive una stringa ASCII, opzionariamente con terminatore 0."""
        if isinstance(s, str):
            s = s.encode('latin1')
        self.buf.extend(s)
        if termina:
            self.buf.append(0)
        return self

    def jsr_resload(self, offset):
        """JSR a una funzione resload: jsr offset(a4)."""
        self.buf.extend(b'\x4E\xA4')
        self.buf.extend(struct.pack('>h', offset))
        return self

    def jmp_ind(self, registro):
        """JMP (An) - salto indiretto."""
        self.buf.extend(bytes([0x4E, 0xE0 | registro]))
        return self

    def lea_pc(self, registro, etichetta):
        """LEA (d16,PC), An con riferimento a etichetta."""
        opcode = 0x41F8 | registro
        self.buf.extend(struct.pack('>H', opcode))
        self.da_fare.append((len(self.buf), etichetta, 'w', len(self.buf)))
        self.buf.extend(b'\x00\x00')
        return self

    def move_l_imm(self, registro, valore):
        """MOVE.L #imm, Dn."""
        self.buf.extend(bytes([0x20 | (registro << 1) | 0x00]))
        self.buf.extend(struct.pack('>I', valore))
        return self

    def move_l_ind(self, registro, addr):
        """MOVE.L Dn, (An) o MOVE.L (An), Dn."""
        # Placeholder per istruzioni piu' complesse
        pass
