/* amiga_debug.c - registrazione e finestra di debug, solo con --debug o
 * AMIGA_DEBUG (e nelle prove senza finestra). Gli agganci del gioco alle
 * chiamate (g_debug_gioco.agganci) funzionano sempre. */
#include "amiga_debug.h"
#include "amiga_hw.h"
#include "genesis_runtime.h"
#include "font_debug.h"

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>

uint8_t g_debug_osservati[0x100000 / 8];

/* ------------------------------------------------------------ anelli */

#define N_CHIAMATE 8192
#define N_SCRITTURE 4096
#define N_MESSAGGI 256

typedef struct { uint64_t quadro; uint32_t ritorno, a7; } chiamata_t;
typedef struct { uint64_t quadro; uint32_t indirizzo, vecchio, nuovo, dove; uint8_t taglia; } scrittura_t;
typedef struct { uint64_t quadro; int numero; char testo[256]; } messaggio_t;

static chiamata_t s_ch[N_CHIAMATE];
static scrittura_t s_scr[N_SCRITTURE];
static messaggio_t s_msg[N_MESSAGGI];
static uint64_t s_n_ch, s_n_scr, s_n_msg, s_quadro;
static uint32_t s_ultima_chiamata;
static FILE *s_log_msg;
static int s_attivo;

/* ------------------------------------------------------------ nomi */

typedef struct { uint32_t a; char nome[64]; } nome_t;
static nome_t *s_nomi;
static int s_n_nomi;

static int cmp_nome(const void *x, const void *y) {
    uint32_t a = ((const nome_t *)x)->a, b = ((const nome_t *)y)->a;
    return a < b ? -1 : a > b;
}

static void carica_nomi(const char *csv) {
    FILE *f = csv ? fopen(csv, "r") : NULL;
    if (!f) return;
    char riga[512];
    int cap = 0;
    while (fgets(riga, sizeof riga, f)) {
        if (riga[0] == '#' || riga[0] == '\n') continue;
        char *v = strchr(riga, ',');
        if (!v) continue;
        *v++ = 0;
        char *fine = strchr(v, ',');
        if (fine) *fine = 0;
        if (s_n_nomi == cap) {
            cap = cap ? cap * 2 : 256;
            s_nomi = realloc(s_nomi, (size_t)cap * sizeof *s_nomi);
        }
        s_nomi[s_n_nomi].a = (uint32_t)strtoul(riga, NULL, 16);
        snprintf(s_nomi[s_n_nomi].nome, sizeof s_nomi[0].nome, "%s", v);
        s_n_nomi++;
    }
    fclose(f);
    qsort(s_nomi, (size_t)s_n_nomi, sizeof *s_nomi, cmp_nome);
}

/* "funzione+$off" della funzione che contiene a (l'ultima che inizia prima) */
static const char *dove(uint32_t a, char *buf, size_t n) {
    int lo = 0, hi = s_n_nomi - 1, k = -1;
    while (lo <= hi) {
        int m = (lo + hi) / 2;
        if (s_nomi[m].a <= a) { k = m; lo = m + 1; } else hi = m - 1;
    }
    if (k >= 0 && a - s_nomi[k].a < 0x1000) snprintf(buf, n, "%s+$%X", s_nomi[k].nome, a - s_nomi[k].a);
    else snprintf(buf, n, "$%06X", a);
    return buf;
}

/* ------------------------------------------------------------ registrazione */

void amiga_debug_chiamata(uint32_t ritorno, uint32_t a7) {
    chiamata_t *c = &s_ch[s_n_ch++ % N_CHIAMATE];
    c->quadro = s_quadro; c->ritorno = ritorno; c->a7 = a7;
    s_ultima_chiamata = ritorno;
    for (int i = 0; i < g_debug_gioco.n_agganci; i++)
        if (g_debug_gioco.agganci[i].ritorno == ritorno) g_debug_gioco.agganci[i].fn(ritorno);
}

void amiga_debug_scrittura(uint32_t indirizzo, int taglia, uint32_t vecchio, uint32_t nuovo) {
    if (vecchio == nuovo) return;
    scrittura_t *s = &s_scr[s_n_scr++ % N_SCRITTURE];
    s->quadro = s_quadro; s->indirizzo = indirizzo; s->taglia = (uint8_t)taglia;
    s->vecchio = vecchio; s->nuovo = nuovo; s->dove = s_ultima_chiamata;
}

void amiga_debug_messaggio(int numero, const char *testo) {
    messaggio_t *m = &s_msg[s_n_msg++ % N_MESSAGGI];
    m->quadro = s_quadro; m->numero = numero;
    snprintf(m->testo, sizeof m->testo, "%s", testo);
    if (s_log_msg) { fprintf(s_log_msg, "q%llu #%d: %s\n", (unsigned long long)s_quadro, numero, testo); fflush(s_log_msg); }
}

/* ------------------------------------------------------------ valori */

static void valore(const debug_var_t *v, char *buf, size_t n) {
    uint32_t a = v->indirizzo;
    switch (v->formato) {
    case DV_U8:    snprintf(buf, n, "%u", m68k_read8(a)); break;
    case DV_U16:   snprintf(buf, n, "%u", m68k_read16(a)); break;
    case DV_U32:   snprintf(buf, n, "%u", m68k_read32(a)); break;
    case DV_HEX8:  snprintf(buf, n, "$%02X", m68k_read8(a)); break;
    case DV_HEX16: snprintf(buf, n, "$%04X", m68k_read16(a)); break;
    case DV_CIFRE8: {
        char c[9]; int i = 0;
        for (; i < 8; i++) { uint8_t d = m68k_read8(a + (uint32_t)i); c[i] = (char)(d <= 9 ? '0' + d : '?'); }
        c[8] = 0;
        const char *p = c; while (*p == '0' && p[1]) p++;
        snprintf(buf, n, "%s", p);
        break;
    }
    }
}

/* ------------------------------------------------------------ finestra */

#define DW 960
#define DH 760
static SDL_Window *s_win;
static SDL_Renderer *s_ren;
static SDL_Texture *s_tex;
static uint32_t s_pix[DW * DH];
static int s_aperta;

static void testo(int x, int y, uint32_t col, const char *s) {
    for (; *s && x + FONT_DEBUG_L <= DW; s++, x += FONT_DEBUG_L) {
        unsigned c = (unsigned char)*s;
        if (c == 0xC2 && (unsigned char)s[1] == 0xA3) { c = 'L'; s++; }   /* sterlina in UTF-8 */
        else if (c < 32 || c > 126) c = '?';
        const uint8_t *g = font_debug[c - 32];
        for (int r = 0; r < FONT_DEBUG_A && y + r < DH; r++)
            for (int b = 0; b < 8; b++)
                if (g[r] & (0x80 >> b)) s_pix[(y + r) * DW + x + b] = col;
    }
}

static void apri(void) {
    if (s_win) { SDL_ShowWindow(s_win); s_aperta = 1; return; }
    s_win = SDL_CreateWindow("Debug", SDL_WINDOWPOS_UNDEFINED, SDL_WINDOWPOS_UNDEFINED, DW, DH, 0);
    s_ren = SDL_CreateRenderer(s_win, -1, 0);
    s_tex = SDL_CreateTexture(s_ren, SDL_PIXELFORMAT_ARGB8888, SDL_TEXTUREACCESS_STREAMING, DW, DH);
    s_aperta = 1;
}

static void disegna(void) {
    const uint32_t BIANCO = 0xFFE8E8E8, GIALLO = 0xFFFFC040, CIANO = 0xFF60D0FF, GRIGIO = 0xFF8090A0;
    char b[256], d[96];
    for (int i = 0; i < DW * DH; i++) s_pix[i] = 0xFF101820;
    int y = 6, L = FONT_DEBUG_A + 1;
    extern double g_amiga_fps;
    snprintf(b, sizeof b, "QUADRO %llu  %.2f fps   chiamate %llu   scritture %llu   messaggi %llu   (Shift+F11: dump)",
             (unsigned long long)s_quadro, g_amiga_fps, (unsigned long long)s_n_ch,
             (unsigned long long)s_n_scr, (unsigned long long)s_n_msg);
    testo(8, y, GIALLO, b); y += L + 4;

    testo(8, y, CIANO, "VARIABILI"); y += L;
    for (int i = 0; i < g_debug_gioco.n_var; i++) {
        char v[32];
        valore(&g_debug_gioco.var[i], v, sizeof v);
        snprintf(b, sizeof b, "%-26s %-12s $%05X", g_debug_gioco.var[i].nome, v, g_debug_gioco.var[i].indirizzo);
        testo(16 + (i % 2) * 470, y, BIANCO, b);
        if (i % 2) y += L;
    }
    if (g_debug_gioco.n_var % 2) y += L;
    y += 4;

    testo(8, y, CIANO, "ULTIMI MESSAGGI"); y += L;
    for (int i = 0; i < 6 && (uint64_t)i < s_n_msg; i++) {
        messaggio_t *m = &s_msg[(s_n_msg - 1 - (uint64_t)i) % N_MESSAGGI];
        snprintf(b, sizeof b, "q%-6llu #%-3d %.100s", (unsigned long long)m->quadro, m->numero, m->testo);
        testo(16, y, i ? GRIGIO : BIANCO, b); y += L;
    }
    y += 4;

    testo(8, y, CIANO, "ULTIME SCRITTURE SULLE VARIABILI"); y += L;
    for (int i = 0; i < 10 && (uint64_t)i < s_n_scr; i++) {
        scrittura_t *s = &s_scr[(s_n_scr - 1 - (uint64_t)i) % N_SCRITTURE];
        const char *nome = "";
        for (int k = 0; k < g_debug_gioco.n_var; k++)
            if (s->indirizzo >= g_debug_gioco.var[k].indirizzo &&
                s->indirizzo < g_debug_gioco.var[k].indirizzo + (g_debug_gioco.var[k].formato == DV_CIFRE8 ? 8u : 1u))
                nome = g_debug_gioco.var[k].nome;
        snprintf(b, sizeof b, "q%-6llu %-18s $%05X  %u -> %u   dopo %s", (unsigned long long)s->quadro, nome,
                 s->indirizzo, s->vecchio, s->nuovo, dove(s->dove, d, sizeof d));
        testo(16, y, i ? GRIGIO : BIANCO, b); y += L;
    }
    y += 4;

    testo(8, y, CIANO, "ULTIME CHIAMATE (chi chiama, dal punto di ritorno)"); y += L;
    for (int i = 0; y < DH - L && (uint64_t)i < s_n_ch; i++) {
        chiamata_t *c = &s_ch[(s_n_ch - 1 - (uint64_t)i) % N_CHIAMATE];
        snprintf(b, sizeof b, "q%-6llu %-48s A7=$%06X", (unsigned long long)c->quadro,
                 dove(c->ritorno, d, sizeof d), c->a7);
        testo(16, y, i ? GRIGIO : BIANCO, b); y += L;
    }
    SDL_UpdateTexture(s_tex, NULL, s_pix, DW * 4);
    SDL_RenderClear(s_ren);
    SDL_RenderCopy(s_ren, s_tex, NULL, NULL);
    SDL_RenderPresent(s_ren);
}

/* ------------------------------------------------------------ interfaccia */

void amiga_debug_init(int attivo, int apri_finestra) {
    s_attivo = attivo;
    if (!attivo) return;
    carica_nomi(g_debug_gioco.annotazioni);
    for (int i = 0; i < g_debug_gioco.n_var; i++) {
        uint32_t a = g_debug_gioco.var[i].indirizzo, n = 1;
        switch (g_debug_gioco.var[i].formato) {
        case DV_U16: case DV_HEX16: n = 2; break;
        case DV_U32: n = 4; break;
        case DV_CIFRE8: n = 8; break;
        default: break;
        }
        for (uint32_t k = 0; k < n && a + k < 0x100000u; k++)
            g_debug_osservati[(a + k) >> 3] |= (uint8_t)(1u << ((a + k) & 7));
    }
    s_log_msg = fopen("messaggi.log", "a");
    if (s_log_msg) fprintf(s_log_msg, "---- avvio %ld\n", (long)time(NULL));
    if (apri_finestra) apri();
}

void amiga_debug_quadro(uint64_t quadro) {
    s_quadro = quadro;
    if (s_aperta && quadro % 5 == 0) disegna();      /* 10 aggiornamenti al secondo */
}

int amiga_debug_evento(const SDL_Event *ev) {
    if (!s_attivo) return 0;
    if (ev->type == SDL_KEYDOWN && ev->key.keysym.sym == SDLK_F11 && !ev->key.repeat) {
        if (ev->key.keysym.mod & KMOD_SHIFT) {
            amiga_debug_dump("debug_dump.txt");
        } else if (s_aperta) {
            SDL_HideWindow(s_win); s_aperta = 0;
        } else apri();
        return 1;
    }
    if (ev->type == SDL_WINDOWEVENT && s_win && ev->window.windowID == SDL_GetWindowID(s_win)) {
        if (ev->window.event == SDL_WINDOWEVENT_CLOSE) { SDL_HideWindow(s_win); s_aperta = 0; }
        return 1;
    }
    return 0;
}

void amiga_debug_dump(const char *file) {
    FILE *f = fopen(file, "w");
    if (!f) return;
    char d[96], v[32];
    fprintf(f, "# debug dump al quadro %llu\n\n[variabili]\n", (unsigned long long)s_quadro);
    for (int i = 0; i < g_debug_gioco.n_var; i++) {
        valore(&g_debug_gioco.var[i], v, sizeof v);
        fprintf(f, "%-26s $%05X = %s\n", g_debug_gioco.var[i].nome, g_debug_gioco.var[i].indirizzo, v);
    }
    fprintf(f, "\n[cpu]\nD0-D7");
    for (int i = 0; i < 8; i++) fprintf(f, " %08X", g_cpu.D[i]);
    fprintf(f, "\nA0-A7");
    for (int i = 0; i < 8; i++) fprintf(f, " %08X", g_cpu.A[i]);
    fprintf(f, "\nSR %04X\n\n[messaggi] (dal piu' vecchio)\n", g_cpu.SR);
    uint64_t da = s_n_msg > N_MESSAGGI ? s_n_msg - N_MESSAGGI : 0;
    for (uint64_t i = da; i < s_n_msg; i++) {
        messaggio_t *m = &s_msg[i % N_MESSAGGI];
        fprintf(f, "q%llu #%d: %s\n", (unsigned long long)m->quadro, m->numero, m->testo);
    }
    fprintf(f, "\n[scritture] (dalla piu' vecchia)\n");
    da = s_n_scr > N_SCRITTURE ? s_n_scr - N_SCRITTURE : 0;
    for (uint64_t i = da; i < s_n_scr; i++) {
        scrittura_t *s = &s_scr[i % N_SCRITTURE];
        fprintf(f, "q%llu $%05X %u -> %u  dopo %s\n", (unsigned long long)s->quadro, s->indirizzo,
                s->vecchio, s->nuovo, dove(s->dove, d, sizeof d));
    }
    fprintf(f, "\n[chiamate] (dalla piu' vecchia)\n");
    da = s_n_ch > N_CHIAMATE ? s_n_ch - N_CHIAMATE : 0;
    for (uint64_t i = da; i < s_n_ch; i++) {
        chiamata_t *c = &s_ch[i % N_CHIAMATE];
        fprintf(f, "q%llu %s A7=$%06X\n", (unsigned long long)c->quadro, dove(c->ritorno, d, sizeof d), c->a7);
    }
    fclose(f);
    FILE *m = fopen("debug_memoria.bin", "wb");          /* tutta la memoria, per analisi */
    if (m) { fwrite(g_amiga_mem, 1, g_amiga_mem_size, m); fclose(m); }
}
