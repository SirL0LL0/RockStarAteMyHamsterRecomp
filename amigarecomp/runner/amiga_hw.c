/* amiga_hw.c - chip custom, CIA-A e video di un A500 (OCS), quanto basta ai
 * giochi che prendono la macchina.
 *
 * Video: a fine quadro il copper (MOVE e WAIT) viene eseguito riga per riga
 * e i bitplane lowres producono 320x256 pixel nella finestra di
 * visualizzazione DIWSTRT/DIWSTOP. Niente blitter, niente sprite (per ora).
 * Tastiera: un codice per quadro nel registro seriale del CIA-A, come fa il
 * controller della tastiera dell'Amiga, con l'interrupt PORTS.
 */
#include "amiga_hw.h"
#include "amiga_paula.h"
#include <string.h>

#include "genesis_runtime.h"     /* g_cycle_accumulator: posizione del pennello */

uint8_t *g_amiga_mem;
uint32_t g_amiga_mem_size;
uint64_t g_amiga_letture_vhpos;     /* diagnostica: letture di VHPOSR */

static uint16_t s_custom[0x100];
static uint16_t s_dmacon, s_intena, s_intreq;
static uint32_t s_quadro[AMIGA_LARGHEZZA * AMIGA_ALTEZZA];
static unsigned long s_quadri;

static uint8_t s_cia_icr_mask, s_cia_icr_dati, s_cia_sdr, s_cia_pra = 0xFF;
static uint8_t s_tasti[64];
static int s_n_tasti;

static int s_fuoco1, s_fuoco2, s_su, s_giu, s_sx, s_dx, s_mx, s_my, s_destro;

static uint16_t leggi_mem16(uint32_t a) {
    a &= 0xFFFFFEu;
    return a + 1 < g_amiga_mem_size ? (uint16_t)(g_amiga_mem[a] << 8 | g_amiga_mem[a + 1]) : 0;
}

/* istante attuale in cicli CPU dall'avvio: quadri completati + posizione nel quadro */
static uint64_t adesso(void) {
    return (uint64_t)s_quadri * AMIGA_CICLI_QUADRO + g_cycle_accumulator / g_amiga_cpu_x;
}

static void scrivi_custom(uint32_t off, uint16_t v) {
    off &= 0x1FE;
    if (off >= 0x0A0 && off < 0x0E0) {                /* audio: prima si genera fin qui */
        amiga_paula_avanza(adesso());
        amiga_paula_registro(off, v);
    }
    switch (off) {
    case 0x096: {
        uint16_t prima = s_dmacon;
        s_dmacon = (v & 0x8000) ? (uint16_t)(s_dmacon | (v & 0x7FFF)) : (uint16_t)(s_dmacon & ~v);
        if ((prima ^ s_dmacon) & 0x020F) {
            amiga_paula_avanza(adesso());
            amiga_paula_dmacon(prima, s_dmacon);
        }
        return;
    }
    case 0x09A: s_intena = (v & 0x8000) ? (uint16_t)(s_intena | (v & 0x7FFF)) : (uint16_t)(s_intena & ~v); return;
    case 0x09C: s_intreq = (v & 0x8000) ? (uint16_t)(s_intreq | (v & 0x7FFF)) : (uint16_t)(s_intreq & ~v); return;
    case 0x088: return;                  /* COPJMP1: il copper riparte da COP1LC a ogni quadro */
    }
    s_custom[off / 2] = v;
}

static uint16_t joydat(int su, int giu, int sx, int dx) {
    int b1 = dx, b9 = sx, b0 = giu ^ dx, b8 = su ^ sx;
    return (uint16_t)(b9 << 9 | b8 << 8 | b1 << 1 | b0);
}

static uint16_t leggi_custom(uint32_t off) {
    off &= 0x1FE;
    uint32_t t = g_cycle_accumulator / g_amiga_cpu_x;      /* tempo dei chip, non della CPU */
    uint32_t riga = t / AMIGA_CICLI_RIGA, h = (t % AMIGA_CICLI_RIGA) / 2;
    switch (off) {
    case 0x002: return s_dmacon;
    case 0x004: return (uint16_t)((riga >> 8) & 1);
    case 0x006: g_amiga_letture_vhpos++; return (uint16_t)((riga & 0xFF) << 8 | (h & 0xFF));
    case 0x00A: return (uint16_t)((s_my & 0xFF) << 8 | (s_mx & 0xFF));
    case 0x00C: return joydat(s_su, s_giu, s_sx, s_dx);
    case 0x016: return (uint16_t)(0xFF00 & ~(s_destro ? 0x0400 : 0));   /* POTGOR: DATLY = destro porta 0 */
    case 0x01C: return s_intena;
    case 0x01E: return s_intreq;
    }
    return s_custom[off / 2];
}

uint8_t amiga_hw_read8(uint32_t a) {
    if (a >= 0xDFF000 && a < 0xDFF200) {
        uint16_t v = leggi_custom(a & ~1u);
        return (a & 1) ? (uint8_t)v : (uint8_t)(v >> 8);
    }
    if ((a & 0xFFF000) == 0xBFE000 && (a & 1)) {           /* CIA-A, registri dispari */
        switch ((a >> 8) & 15) {
        case 0x0: return (uint8_t)((s_cia_pra & 0x3F) | (s_fuoco1 ? 0 : 0x40) | (s_fuoco2 ? 0 : 0x80));
        case 0x8: return (uint8_t)s_quadri;                 /* TOD basso: contatore di quadri */
        case 0xC: return s_cia_sdr;
        case 0xD: { uint8_t r = s_cia_icr_dati; if (r) r |= 0x80; s_cia_icr_dati = 0; return r; }
        }
        return 0xFF;
    }
    return 0xFF;
}

uint16_t amiga_hw_read16(uint32_t a) {
    if (a >= 0xDFF000 && a < 0xDFF200) return leggi_custom(a);
    return (uint16_t)(amiga_hw_read8(a) << 8 | amiga_hw_read8(a + 1));
}

void amiga_hw_write8(uint32_t a, uint8_t v) {
    if (a >= 0xDFF000 && a < 0xDFF200) { scrivi_custom(a & ~1u, (uint16_t)(v << 8 | v)); return; }
    if ((a & 0xFFF000) == 0xBFE000 && (a & 1)) {
        switch ((a >> 8) & 15) {
        case 0x0: s_cia_pra = v; break;
        case 0xD: if (v & 0x80) s_cia_icr_mask |= v & 0x7F; else s_cia_icr_mask &= (uint8_t)~v; break;
        }
    }
}

void amiga_hw_write16(uint32_t a, uint16_t v) {
    if (a >= 0xDFF000 && a < 0xDFF200) { scrivi_custom(a, v); return; }
    amiga_hw_write8(a, (uint8_t)(v >> 8));
    amiga_hw_write8(a + 1, (uint8_t)v);
}

int amiga_hw_livello_interrupt(void) {
    if (!(s_intena & 0x4000)) return 0;
    uint16_t att = s_intena & s_intreq & 0x3FFF;
    if (att & 0x2000) return 6;
    if (att & 0x1800) return 5;
    if (att & 0x0780) return 4;
    if (att & 0x0070) return 3;
    if (att & 0x0008) return 2;
    if (att & 0x0007) return 1;
    return 0;
}

static uint32_t rgb(uint16_t c) {
    uint32_t r = (c >> 8) & 15, g = (c >> 4) & 15, b = c & 15;
    return 0xFF000000u | (r * 17) << 16 | (g * 17) << 8 | (b * 17);
}

static void disegna(void) {
    uint32_t pc = (uint32_t)s_custom[0x80 / 2] << 16 | s_custom[0x82 / 2];
    /* le righe fuori dalla finestra video restano nere (bordo) */
    for (int i = 0; i < AMIGA_LARGHEZZA * AMIGA_ALTEZZA; i++) s_quadro[i] = 0xFF000000u;
    int attesa = -1, fermo = 0;
    uint32_t pt[6] = {0};
    for (int riga = 0; riga < (int)AMIGA_RIGHE_QUADRO; riga++) {
        while (!fermo) {
            if (attesa >= 0) { if (riga < attesa) break; attesa = -1; }
            uint16_t i1 = leggi_mem16(pc), i2 = leggi_mem16(pc + 2);
            pc += 4;
            if (!(i1 & 1)) {                                   /* MOVE */
                uint32_t reg = i1 & 0x1FE;
                scrivi_custom(reg, i2);
                if (reg >= 0xE0 && reg < 0xF8) {
                    int p = (int)(reg - 0xE0) / 4;
                    pt[p] = (uint32_t)s_custom[(0xE0 + p * 4) / 2] << 16 | s_custom[(0xE2 + p * 4) / 2];
                }
            } else if (!(i2 & 1)) {                            /* WAIT */
                if (i1 == 0xFFFF && i2 == 0xFFFE) { fermo = 1; break; }
                int v = i1 >> 8;
                if (riga > 255 && v < 0x80) v += 256;
                attesa = v;
                if (riga < attesa) break;
                attesa = -1;
            }
        }
        uint16_t diw = s_custom[0x8E / 2], diwstop = s_custom[0x90 / 2];
        int v0 = diw >> 8, v1 = (diwstop >> 8) | ((diwstop & 0x8000) ? 0 : 0x100);
        if (riga < v0 || riga >= v1) continue;
        int y = riga - v0;
        int piani = (s_custom[0x100 / 2] >> 12) & 7;
        if (piani > 5) piani = 5;
        int16_t mod1 = (int16_t)s_custom[0x108 / 2], mod2 = (int16_t)s_custom[0x10A / 2];
        if (y < AMIGA_ALTEZZA) {
            uint32_t *out = &s_quadro[y * AMIGA_LARGHEZZA];
            for (int x = 0; x < AMIGA_LARGHEZZA; x++) {
                int col = 0;
                for (int p = 0; p < piani; p++) {
                    uint32_t a = pt[p] + (uint32_t)(x >> 3);
                    uint8_t b = a < g_amiga_mem_size ? g_amiga_mem[a] : 0;
                    col |= ((b >> (7 - (x & 7))) & 1) << p;
                }
                out[x] = rgb(s_custom[0x180 / 2 + col]);
            }
        }
        for (int p = 0; p < piani; p++) pt[p] += (uint32_t)(40 + ((p & 1) ? mod2 : mod1));
    }
}

/* Sprite hardware (8 canali, 16 pixel lowres, 3 colori + trasparente).
 * Ogni canale legge da SPRxPT: due parole di controllo (POS, CTL), poi una
 * coppia DATA/DATB per riga fino a VSTOP, poi altre parole di controllo
 * (riuso dello stesso canale piu' in basso) finche' POS e CTL sono 0.
 * Il puntatore del mouse dei giochi e' quasi sempre lo sprite 0. Gli sprite
 * stanno davanti ai bitplane (priorita' di default). Gli sprite "attaccati"
 * (15 colori) non sono ancora gestiti. */
static void disegna_sprite(void) {
    uint16_t diw = s_custom[0x8E / 2];
    int v0 = diw >> 8, h0 = diw & 0xFF;
    if (!(s_dmacon & 0x0200) || !(s_dmacon & 0x0020)) return;      /* DMAEN + SPREN */
    for (int n = 7; n >= 0; n--) {                                 /* lo 0 sopra tutti */
        uint32_t pt = (uint32_t)s_custom[(0x120 + n * 4) / 2] << 16 | s_custom[(0x122 + n * 4) / 2];
        for (int giro = 0; giro < 16; giro++) {
            uint16_t pos = leggi_mem16(pt), ctl = leggi_mem16(pt + 2);
            pt += 4;
            if (pos == 0 && ctl == 0) break;
            int vstart = (pos >> 8) | ((ctl & 4) << 6);
            int vstop  = (ctl >> 8) | ((ctl & 2) << 7);
            int hstart = ((pos & 0xFF) << 1) | (ctl & 1);
            int base_col = 17 + (n / 2) * 4;
            for (int riga = vstart; riga < vstop; riga++, pt += 4) {
                uint16_t a = leggi_mem16(pt), b = leggi_mem16(pt + 2);
                int y = riga - v0;
                if (y < 0 || y >= AMIGA_ALTEZZA) continue;
                for (int i = 0; i < 16; i++) {
                    int c = ((a >> (15 - i)) & 1) | (((b >> (15 - i)) & 1) << 1);
                    int x = hstart + i - h0;
                    if (c && x >= 0 && x < AMIGA_LARGHEZZA)
                        s_quadro[y * AMIGA_LARGHEZZA + x] = rgb(s_custom[0x180 / 2 + base_col - 1 + c]);
                }
            }
        }
    }
}

void amiga_hw_init(void) { amiga_paula_init(&s_intreq); }

int amiga_hw_audio(int16_t **campioni) { return amiga_paula_prendi(campioni); }

void amiga_hw_fine_quadro(void) {
    amiga_paula_avanza((uint64_t)(s_quadri + 1) * AMIGA_CICLI_QUADRO);   /* audio del quadro finito */
    s_quadri++;
    disegna();
    disegna_sprite();
    if (s_n_tasti && (s_cia_icr_mask & 0x08)) {      /* un codice tastiera per quadro */
        uint8_t k = s_tasti[0];
        memmove(s_tasti, s_tasti + 1, (size_t)--s_n_tasti);
        s_cia_sdr = (uint8_t)~((k << 1) | (k >> 7));
        s_cia_icr_dati |= 0x08;
        s_intreq |= 0x0008;
    }
    s_intreq |= 0x0020;                                /* vertical blank */
}

const uint32_t *amiga_hw_framebuffer(void) { return s_quadro; }

void amiga_hw_tasto(uint8_t raw, int rilasciato) {
    if (s_n_tasti < (int)sizeof s_tasti) s_tasti[s_n_tasti++] = (uint8_t)(raw | (rilasciato ? 0x80 : 0));
}

void amiga_hw_joystick(int su, int giu, int sx, int dx, int fuoco) {
    s_su = su; s_giu = giu; s_sx = sx; s_dx = dx; s_fuoco2 = fuoco;
}

void amiga_hw_mouse(int dx, int dy, int sinistro, int destro) {
    s_mx += dx; s_my += dy; s_fuoco1 = sinistro; s_destro = destro;
}
