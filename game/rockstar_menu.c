/* rockstar_menu.c - salvataggi e trucchi nel menu in gioco (amiga_menu.c).
 *
 * COME SALVA IL GIOCO
 * Nel menu principale l'opzione SALVATAGGI (SAVE/LOAD nell'originale; $8EEA)
 * chiede SALVA / CARICA /
 * ANNULLA. SALVA copia i 300 byte a $11D0B (classifiche) e i 3217 a $123CA
 * (soldi, band, canzoni, settimana: tutta la partita) in un buffer a $76E56 e
 * mette 1 in $8F86; CARICA li ricopia indietro e ridisegna il pannello
 * ($DBAC, $DC12). Sull'Amiga il buffer stava solo in memoria e spariva allo
 * spegnimento.
 *
 * QUI
 * - La partita salvata col gioco viene scritta anche in salvataggi/partita.sav
 *   e rimessa nel buffer alla partenza: SALVATAGGI -> CARICA funziona anche il
 *   giorno dopo.
 * - Quattro slot nel menu in gioco (F1): salvano e caricano gli stessi due
 *   blocchi. Si possono usare solo quando il gioco e' fermo nel menu
 *   principale (il momento in cui salva il gioco stesso: la partita e'
 *   completa e coerente). Lo si riconosce dalla chiamata al menu ($9944) dai
 *   tre punti del menu principale ($8E08, $8E66, $8E9C): finche' la pila resta
 *   sotto quella chiamata, il gioco e' li' dentro ad aspettare una scelta.
 * - I trucchi del launcher si accendono e spengono anche da qui.
 */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>
#ifdef _WIN32
#include <direct.h>
#define crea_cartella(p) _mkdir(p)
#else
#include <sys/stat.h>
#define crea_cartella(p) mkdir(p, 0755)
#endif

#include "amiga_menu.h"
#include "genesis_runtime.h"
#include "rockstar_decls.h"
#include "rockstar_mods.h"
#include "rockstar_menu.h"

#define CLASSIFICHE   0x11D0Bu
#define N_CLASSIFICHE 300u
#define PARTITA       0x123CAu
#define N_PARTITA     3217u
#define BUFFER        0x76E56u
#define FLAG_SALVATA  0x08F86u
#define TESTO         0x122C8u        /* buffer del compositore, fino a $123C9 */
#define TESTO_N       (PARTITA - TESTO)
#define N_BLOCCO      (N_CLASSIFICHE + N_PARTITA)
#define N_SLOT        4
#define CARTELLA      "salvataggi"
#define MAGIA         "RSAMH-SALVA1"

typedef struct {
    char magia[12];
    uint32_t quando;                 /* time(), per l'elenco */
    uint8_t dati[N_BLOCCO];
} salvataggio_t;

static int s_slot;                   /* 0..3 */
static uint32_t s_pila_menu;         /* A7 dentro la chiamata al menu principale */
static int s_nel_principale;

/* ------------------------------------------------------------ menu principale */

void rockstar_menu_principale(uint32_t ritorno) {
    (void)ritorno;
    s_pila_menu = g_cpu.A[7] - 4;    /* lo slot dell'indirizzo di ritorno */
    s_nel_principale = 1;
}

static int al_menu_principale(void) {
    if (s_nel_principale && g_cpu.A[7] > s_pila_menu) s_nel_principale = 0;  /* e' tornato */
    return s_nel_principale;
}

/* ------------------------------------------------------------ file */

static void percorso(char *b, size_t n, int slot) {
    if (slot < 0) snprintf(b, n, CARTELLA "/partita.sav");
    else snprintf(b, n, CARTELLA "/slot%d.sav", slot + 1);
}

static int leggi(int slot, salvataggio_t *s) {
    char p[64];
    percorso(p, sizeof p, slot);
    FILE *f = fopen(p, "rb");
    if (!f) return 0;
    int ok = fread(s, sizeof *s, 1, f) == 1 && !memcmp(s->magia, MAGIA, sizeof s->magia);
    fclose(f);
    return ok;
}

static int scrivi(int slot, const uint8_t *dati) {
    salvataggio_t s;
    memcpy(s.magia, MAGIA, sizeof s.magia);
    s.quando = (uint32_t)time(NULL);
    memcpy(s.dati, dati, N_BLOCCO);
    char p[64];
    crea_cartella(CARTELLA);
    percorso(p, sizeof p, slot);
    FILE *f = fopen(p, "wb");
    if (!f) return 0;
    int ok = fwrite(&s, sizeof s, 1, f) == 1;
    fclose(f);
    return ok;
}

static void leggi_memoria(uint32_t a, uint8_t *d, uint32_t n) { for (uint32_t i = 0; i < n; i++) d[i] = m68k_read8(a + i); }
static void scrivi_memoria(uint32_t a, const uint8_t *d, uint32_t n) { for (uint32_t i = 0; i < n; i++) m68k_write8(a + i, d[i]); }

/* ------------------------------------------------------------ partita del gioco */

static uint32_t s_somma_salvata;

static uint32_t somma(const uint8_t *d, uint32_t n) {
    uint32_t h = 2166136261u;
    for (uint32_t i = 0; i < n; i++) h = (h ^ d[i]) * 16777619u;
    return h;
}

static void a_salva(int verso);
static void a_carica(int verso);

/* AMIGA_PROVA_SLOT=N (prove senza finestra): al quadro N (0 = al primo menu
 * principale) salva nello slot 4, cambia i soldi, ricarica e controlla che
 * siano tornati e che i registri del gioco siano intatti */
static void prova_slot(uint64_t quadro) {
    static int fatta;
    const char *e = getenv("AMIGA_PROVA_SLOT");
    if (fatta || !e) return;
    uint64_t q = strtoull(e, NULL, 10);
    if (q ? quadro != q : (!s_nel_principale || g_cpu.A[7] > s_pila_menu)) return;
    fatta = 1;
    s_slot = 3;
    uint8_t prima[8], dopo[8];
    M68KState cpu = g_cpu;
    leggi_memoria(PARTITA, prima, 8);
    a_salva(0);
    for (uint32_t i = 0; i < 8; i++) m68k_write8(PARTITA + i, 7);
    a_carica(0);
    leggi_memoria(PARTITA, dopo, 8);
    printf("prova slot: soldi prima %d%d%d%d%d%d%d%d dopo %d%d%d%d%d%d%d%d -> %s, registri %s\n",
           prima[0], prima[1], prima[2], prima[3], prima[4], prima[5], prima[6], prima[7],
           dopo[0], dopo[1], dopo[2], dopo[3], dopo[4], dopo[5], dopo[6], dopo[7],
           memcmp(prima, dopo, 8) ? "SBAGLIATO" : "ok",
           memcmp(&cpu, &g_cpu, sizeof cpu) ? "CAMBIATI" : "intatti");
}

void rockstar_menu_quadro(uint64_t quadro) {
    uint8_t d[N_BLOCCO];
    prova_slot(quadro);
    if (quadro == 2) {                                   /* alla partenza: rimette la partita */
        salvataggio_t s;
        if (leggi(-1, &s)) {
            scrivi_memoria(BUFFER, s.dati, N_BLOCCO);
            m68k_write8(FLAG_SALVATA, 1);
            s_somma_salvata = somma(s.dati, N_BLOCCO);
        }
        return;
    }
    if (quadro % 25 || !m68k_read8(FLAG_SALVATA)) return;  /* due volte al secondo basta */
    leggi_memoria(BUFFER, d, N_BLOCCO);
    uint32_t h = somma(d, N_BLOCCO);
    if (h != s_somma_salvata && scrivi(-1, d)) s_somma_salvata = h;
}

/* ------------------------------------------------------------ voci */

static void soldi(const uint8_t *partita, char *b, size_t n) {
    /* 8 cifre decimali, una per byte */
    char c[16];
    int k = 0, inizio = 0;
    for (int i = 0; i < 8; i++) {
        if (!inizio && partita[i] == 0 && i < 7) continue;
        inizio = 1;
        c[k++] = (char)('0' + (partita[i] % 10));
    }
    c[k] = 0;
    snprintf(b, n, "%s st.", c);                 /* il font non ha la sterlina */
}

static void v_slot(char *b, size_t n) {
    salvataggio_t s;
    if (leggi(s_slot, &s)) {
        char m[24];
        soldi(s.dati + N_CLASSIFICHE, m, sizeof m);
        time_t t = (time_t)s.quando;
        struct tm *tm = localtime(&t);
        snprintf(b, n, "Slot %d < >  %s %02d/%02d %02d:%02d", s_slot + 1, m,
                 tm ? tm->tm_mday : 0, tm ? tm->tm_mon + 1 : 0, tm ? tm->tm_hour : 0, tm ? tm->tm_min : 0);
    } else
        snprintf(b, n, "Slot %d < >  vuoto", s_slot + 1);
}
static void a_slot(int verso) { s_slot = (s_slot + (verso ? verso : 1) + N_SLOT) % N_SLOT; }

static void v_salva(char *b, size_t n) {
    snprintf(b, n, al_menu_principale() ? "Salva la partita nello slot" : "Salva (solo nel menu principale)");
}
static void a_salva(int verso) {
    if (verso) return;
    uint8_t d[N_BLOCCO];
    leggi_memoria(CLASSIFICHE, d, N_CLASSIFICHE);
    leggi_memoria(PARTITA, d + N_CLASSIFICHE, N_PARTITA);
    char m[48];
    snprintf(m, sizeof m, scrivi(s_slot, d) ? "Salvata nello slot %d" : "Non riesco a scrivere lo slot %d", s_slot + 1);
    amiga_menu_avviso(m);
}

static void v_carica(char *b, size_t n) {
    snprintf(b, n, al_menu_principale() ? "Carica la partita dallo slot" : "Carica (solo nel menu principale)");
}
static int ok_carica(void) {
    salvataggio_t s;
    return al_menu_principale() && leggi(s_slot, &s);
}
static void a_carica(int verso) {
    salvataggio_t s;
    if (verso || !leggi(s_slot, &s)) return;
    scrivi_memoria(CLASSIFICHE, s.dati, N_CLASSIFICHE);
    scrivi_memoria(PARTITA, s.dati + N_CLASSIFICHE, N_PARTITA);
    /* come il gioco dopo CARICA: ridisegna il pannello. Il gioco e' fermo nel
     * menu: i suoi registri tornano com'erano */
    M68KState cpu = g_cpu;
    int rte = g_rte_pending;
    uint8_t testo[TESTO_N];                      /* il ridisegno usa il buffer dei testi */
    leggi_memoria(TESTO, testo, TESTO_N);
    recomp_push_return(0x08F46u);
    func_00DBAC();
    g_cpu = cpu;
    recomp_push_return(0x08F4Au);
    func_00DC12();
    g_cpu = cpu;
    g_rte_pending = rte;
    scrivi_memoria(TESTO, testo, TESTO_N);
    char m[48];
    snprintf(m, sizeof m, "Caricata dallo slot %d", s_slot + 1);
    amiga_menu_avviso(m);
}

static void v_trucco(int i, char *b, size_t n) {
    snprintf(b, n, "%s: %s", rockstar_mods_nome(i), rockstar_mods_attivo(i) ? "si'" : "no");
}
static void v_t0(char *b, size_t n) { v_trucco(0, b, n); }
static void v_t1(char *b, size_t n) { v_trucco(1, b, n); }
static void v_t2(char *b, size_t n) { v_trucco(2, b, n); }
static void a_t0(int v) { (void)v; rockstar_mods_cambia(0); }
static void a_t1(int v) { (void)v; rockstar_mods_cambia(1); }
static void a_t2(int v) { (void)v; rockstar_mods_cambia(2); }

static const amiga_voce_menu_t s_voci[] = {
    { v_slot, a_slot, NULL },
    { v_salva, a_salva, al_menu_principale },
    { v_carica, a_carica, ok_carica },
    { v_t0, a_t0, NULL },
    { v_t1, a_t1, NULL },
    { v_t2, a_t2, NULL },
};

void rockstar_menu_registra(void) {
    amiga_menu_registra(0, s_voci, (int)(sizeof s_voci / sizeof s_voci[0]));
}
