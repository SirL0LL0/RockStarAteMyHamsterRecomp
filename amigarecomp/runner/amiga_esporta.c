/* amiga_esporta.c - le versioni Amiga in italiano, costruite dal disco
 * dell'utente come le costruisce la pipeline della traduzione:
 *
 *   RockStar_ITA_1MB.adf       floppy avviabile (OFS): s/startup-sequence e
 *                              l'eseguibile "rockstar" (build_ram.py)
 *   RockStarAteMyHamster_v1.0_It.lha   installazione WHDLoad (build_whdload.py),
 *                              compressa -lh5- come lha_amiga.py
 *
 * Il programma non contiene file del gioco: dalla base (amiga_disco.c) si
 * ricava l'immagine italiana con la patch del kit (build/amiga_kit.h, da
 * game/prepara_immagine.py); l'eseguibile Amiga e' testa + immagine compressa
 * + coda, e la compressione e' quella di s404_compress.py rifatta qui byte per
 * byte: il CRC dell'eseguibile deve essere quello del kit. */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>
#include <errno.h>
#ifdef _WIN32
#include <direct.h>
#define crea_cartella(p) _mkdir(p)
#else
#include <sys/stat.h>
#define crea_cartella(p) mkdir(p, 0755)
#endif
#include "amiga_esporta.h"
#include "amiga_disco.h"
#include "amiga_lingue.h"
#include "amiga_kit.h"

/* ------------------------------------------------------------ S404 */

#define EFF 14
#define MAX_DIST (544 + (1 << EFF))
#define MAX_MATCH 277
#define LIMITE_CATENA 256

typedef struct { uint8_t *b; size_t n, cap; } bit_t;

static void metti(bit_t *s, uint32_t v, int conta) {
    if (s->n + (size_t)conta > s->cap) {
        s->cap = (s->cap + (size_t)conta) * 2;
        s->b = realloc(s->b, s->cap);
    }
    for (int i = conta - 1; i >= 0; i--) s->b[s->n++] = (uint8_t)((v >> i) & 1);
}

static void emetti_match(bit_t *s, int n, int dist) {
    int w = dist - 1;
    if (n <= 3) {
        int op = 0x180 | (n == 3 ? 0x40 : 0);
        if (w >= 544) { int v = w - 544; metti(s, op | 0x20 | (v >> (EFF - 5)), 9); metti(s, v & ((1 << (EFF - 5)) - 1), EFF - 5); }
        else if (w < 32) { metti(s, op | 0x10 | (w >> 1), 9); metti(s, w & 1, 1); }
        else { int v = w - 32; metti(s, op | (v >> 5), 9); metti(s, v & 0x1F, 5); }
    } else if (n <= 7) {
        int op = 0x140 | ((n - 4) << 4);
        if (w >= 544) { int v = w - 544; metti(s, op | 0x08 | (v >> (EFF - 3)), 9); metti(s, v & ((1 << (EFF - 3)) - 1), EFF - 3); }
        else if (w < 32) { metti(s, op | 0x04 | (w >> 3), 9); metti(s, w & 7, 3); }
        else { int v = w - 32; metti(s, op | (v >> 7), 9); metti(s, v & 0x7F, 7); }
    } else if (n <= 22) {
        int op = 0x120 | ((n - 8) << 1);
        if (w >= 544) { metti(s, op | 1, 9); metti(s, w - 544, EFF); }
        else if (w < 32) { metti(s, op, 9); metti(s, 0x20 | w, 6); }
        else { int v = w - 32; metti(s, op, 9); metti(s, v >> 4, 6); metti(s, v & 0x0F, 4); }
    } else {
        int ln = n - 23;
        metti(s, 0x100 | (ln >> 3), 9);
        metti(s, ln & 7, 3);
        if (w >= 544) { int v = w - 544; metti(s, 0x40 | (v >> (EFF - 6)), 7); metti(s, v & ((1 << (EFF - 6)) - 1), EFF - 6); }
        else if (w < 32) metti(s, 0x20 | w, 7);
        else { int v = w - 32; metti(s, v >> 4, 7); metti(s, v & 0x0F, 4); }
    }
}

static int costo(int n, int dist) {
    int w = dist - 1;
    static const int grandi[4] = { EFF - 5, EFF - 3, EFF, EFF - 6 }, piccole[4] = { 1, 3, 6, 0 },
                     medie[4] = { 5, 7, 10, 4 };
    const int *e = w >= 544 ? grandi : w < 32 ? piccole : medie;
    if (n <= 3) return 9 + e[0];
    if (n <= 7) return 9 + e[1];
    if (n <= 22) return 9 + e[2];
    return 9 + 3 + 7 + e[3];
}

/* catene per chiave esatta di 3 byte: ultima posizione (tabella aperta) e
 * posizione precedente con la stessa chiave */
#define TAB_BIT 21
typedef struct { uint32_t *chiave; int32_t *ultima; int32_t *prec; } catene_t;

static int32_t *testa(catene_t *c, uint32_t k, int crea) {
    uint32_t h = (k * 2654435761u) >> (32 - TAB_BIT);
    for (;;) {
        if (c->chiave[h] == k + 1) return &c->ultima[h];
        if (!c->chiave[h]) {
            if (!crea) return NULL;
            c->chiave[h] = k + 1;
            c->ultima[h] = -1;
            return &c->ultima[h];
        }
        h = (h + 1) & ((1u << TAB_BIT) - 1);
    }
}

/* -> dati compressi (pLen byte: parole, efficienza, parola iniziale) e il
 * numero di bit della parola iniziale; NULL se manca memoria */
static uint8_t *s404_comprimi(const uint8_t *dati, int dim, size_t *plen, int *parz) {
    uint8_t *w = malloc((size_t)dim);
    catene_t c = { calloc(1u << TAB_BIT, 4), malloc((1u << TAB_BIT) * 4), malloc((size_t)dim * 4) };
    bit_t s = { 0 };
    if (!w || !c.chiave || !c.ultima || !c.prec) { free(w); free(c.chiave); free(c.ultima); free(c.prec); return NULL; }
    for (int i = 0; i < dim; i++) w[i] = dati[dim - 1 - i];
    int pos = 0;
    while (pos < dim) {
        int mig = 0, mig_d = 0;
        if (pos + 2 < dim) {
            int32_t *t = testa(&c, (uint32_t)w[pos] << 16 | w[pos + 1] << 8 | w[pos + 2], 0);
            int limite = dim - pos < MAX_MATCH ? dim - pos : MAX_MATCH, passi = 0;
            for (int32_t cand = t ? *t : -1; cand >= 0; cand = c.prec[cand]) {
                if (passi >= LIMITE_CATENA) break;
                passi++;
                int d = pos - cand;
                if (d > MAX_DIST) break;
                if (mig && w[cand + mig] != w[pos + mig]) continue;
                int ln = 0;
                while (ln < limite && w[cand + ln] == w[pos + ln]) ln++;
                if ((ln > mig || (ln == mig && d < mig_d)) && ln >= 2 &&
                    (ln > mig || costo(ln, d) < costo(mig, mig_d))) {
                    mig = ln; mig_d = d;
                    if (ln >= limite) break;
                }
            }
        }
        int passo;
        if (mig >= 2 && costo(mig, mig_d) < 9 * mig) { emetti_match(&s, mig, mig_d); passo = mig; }
        else { metti(&s, w[pos], 9); passo = 1; }
        int fine = pos + passo < dim - 2 ? pos + passo : dim - 2;
        for (int i = pos; i < fine; i++) {
            int32_t *t = testa(&c, (uint32_t)w[i] << 16 | w[i + 1] << 8 | w[i + 2], 1);
            c.prec[i] = *t;
            *t = i;
        }
        pos += passo;
    }
    free(w); free(c.chiave); free(c.ultima); free(c.prec);

    if (s.n % 16 == 0) metti(&s, 0, 8);
    int r = (int)(s.n % 16);
    uint32_t iniz = 0;
    for (int i = 0; i < r; i++) iniz = iniz << 1 | s.b[i];
    iniz <<= 16 - r;
    size_t nw = (s.n - (size_t)r) / 16, tot = nw + (nw % 2);   /* multiplo di 4 byte */
    uint8_t *blob = calloc(tot * 2 + 4, 1);
    for (size_t k = 0; k < nw; k++) {
        uint32_t v = 0;
        for (int i = 0; i < 16; i++) v = v << 1 | s.b[(size_t)r + k * 16 + (size_t)i];
        size_t o = (tot - 1 - k) * 2;
        blob[o] = (uint8_t)(v >> 8); blob[o + 1] = (uint8_t)v;
    }
    blob[tot * 2] = 0; blob[tot * 2 + 1] = EFF;
    blob[tot * 2 + 2] = (uint8_t)(iniz >> 8); blob[tot * 2 + 3] = (uint8_t)iniz;
    free(s.b);
    *plen = tot * 2 + 4;
    *parz = r;
    return blob;
}

/* ------------------------------------------------------------ file */

static int scrivi_file(const char *p, const uint8_t *d, size_t n) {
    FILE *f = fopen(p, "wb");
    if (!f) return 0;
    int ok = fwrite(d, 1, n, f) == n;
    return fclose(f) == 0 && ok;
}

static int cartella(const char *p) { return crea_cartella(p) == 0 || errno == EEXIST; }

static void be32w(uint8_t *p, uint32_t v) { p[0] = (uint8_t)(v >> 24); p[1] = (uint8_t)(v >> 16); p[2] = (uint8_t)(v >> 8); p[3] = (uint8_t)v; }
static uint32_t be32r(const uint8_t *p) { return (uint32_t)p[0] << 24 | p[1] << 16 | p[2] << 8 | p[3]; }

/* ------------------------------------------------------------ ADF (OFS) */

#define BLOCCHI 1760
#define RADICE 880
#define ST_ROOT 1
#define ST_DIR 2
#define ST_FILE 0xFFFFFFFDu

typedef struct { uint8_t *d; int libero; uint32_t giorni, minuti; } adf_t;

static uint8_t *blocco(adf_t *a, int b) { return a->d + (size_t)b * 512; }

static int hash_ofs(const char *s) {
    int h = (int)strlen(s);
    for (; *s; s++) h = (h * 13 + (*s >= 'a' && *s <= 'z' ? *s - 32 : *s)) & 0x7FF;
    return h % 72;
}

static void somma_testata(uint8_t *b) {                 /* blocchi con checksum a +20 */
    uint32_t s = 0;
    be32w(b + 20, 0);
    for (int i = 0; i < 128; i++) s += be32r(b + i * 4);
    be32w(b + 20, 0u - s);
}

static void nome_e_data(adf_t *a, uint8_t *b, const char *nome) {
    size_t l = strlen(nome);
    b[432] = (uint8_t)l;
    memcpy(b + 433, nome, l);
    be32w(b + 420, a->giorni); be32w(b + 424, a->minuti); be32w(b + 428, 0);
}

/* aggiunge la voce b (nome) alla cartella dir */
static void collega(adf_t *a, int dir, int b, const char *nome) {
    uint8_t *d = blocco(a, dir);
    int h = hash_ofs(nome);
    uint32_t prima = be32r(d + 24 + h * 4);
    be32w(blocco(a, b) + 496, prima);                    /* catena dell'hash */
    be32w(d + 24 + h * 4, (uint32_t)b);
}

static int nuova_cartella(adf_t *a, int padre, const char *nome) {
    int b = a->libero++;
    uint8_t *h = blocco(a, b);
    be32w(h, 2); be32w(h + 4, (uint32_t)b);
    nome_e_data(a, h, nome);
    be32w(h + 500, (uint32_t)padre);
    be32w(h + 508, ST_DIR);
    collega(a, padre, b, nome);
    return b;
}

static void nuovo_file(adf_t *a, int padre, const char *nome, const uint8_t *dati, size_t n) {
    int testata = a->libero++;
    size_t nd = (n + 487) / 488;
    int *dat = malloc((nd ? nd : 1) * sizeof *dat);
    int ext_prec = testata, k = 0;
    /* testata con i primi 72 blocchi, poi blocchi d'estensione da 72 */
    for (size_t i = 0; i < nd; i++) {
        if (i && i % 72 == 0) {
            int e = a->libero++;
            uint8_t *x = blocco(a, e);
            be32w(x, 16); be32w(x + 4, (uint32_t)e);
            be32w(x + 500, (uint32_t)testata); be32w(x + 508, ST_FILE);
            be32w(blocco(a, ext_prec) + 504, (uint32_t)e);
            ext_prec = e;
        }
        dat[i] = a->libero++;
        uint8_t *t = blocco(a, ext_prec);
        k = (int)(i % 72);
        be32w(t + 24 + (71 - k) * 4, (uint32_t)dat[i]);  /* al contrario */
        be32w(t + 8, (uint32_t)(k + 1));                  /* high_seq */
    }
    for (size_t i = 0; i < nd; i++) {
        uint8_t *x = blocco(a, dat[i]);
        size_t q = n - i * 488 < 488 ? n - i * 488 : 488;
        be32w(x, 8); be32w(x + 4, (uint32_t)testata); be32w(x + 8, (uint32_t)(i + 1));
        be32w(x + 12, (uint32_t)q);
        be32w(x + 16, i + 1 < nd ? (uint32_t)dat[i + 1] : 0);
        memcpy(x + 24, dati + i * 488, q);
        somma_testata(x);
    }
    uint8_t *h = blocco(a, testata);
    be32w(h, 2); be32w(h + 4, (uint32_t)testata);
    be32w(h + 16, nd ? (uint32_t)dat[0] : 0);
    be32w(h + 324, (uint32_t)n);
    nome_e_data(a, h, nome);
    be32w(h + 500, (uint32_t)padre);
    be32w(h + 508, ST_FILE);
    collega(a, padre, testata, nome);
    free(dat);
}

/* il bootblock: trova dos.library e restituisce il suo init (nostro) */
static const uint8_t s_avvio[] = {
    0x43, 0xFA, 0x00, 0x18,             /* lea dosname(pc),a1 */
    0x4E, 0xAE, 0xFF, 0xA0,             /* jsr FindResident(a6) */
    0x4A, 0x80, 0x67, 0x0A,             /* tst.l d0 ; beq.s errore */
    0x20, 0x40, 0x20, 0x68, 0x00, 0x16, /* movea.l d0,a0 ; movea.l 22(a0),a0 */
    0x70, 0x00, 0x4E, 0x75,             /* moveq #0,d0 ; rts */
    0x70, 0xFF, 0x4E, 0x75,             /* errore: moveq #-1,d0 ; rts */
    'd', 'o', 's', '.', 'l', 'i', 'b', 'r', 'a', 'r', 'y', 0,
};

static uint8_t *crea_adf(const uint8_t *exe, size_t n_exe) {
    adf_t a = { calloc(BLOCCHI, 512), RADICE + 2, 0, 0 };
    time_t t = time(NULL);
    long g = (long)(t / 86400) - 2922;                    /* giorni dal 1/1/1978 */
    a.giorni = g > 0 ? (uint32_t)g : 0;
    a.minuti = (uint32_t)((t % 86400) / 60);

    uint8_t *bb = a.d;                                     /* bootblock */
    memcpy(bb, "DOS\0", 4);
    be32w(bb + 8, RADICE);
    memcpy(bb + 12, s_avvio, sizeof s_avvio);
    uint32_t s = 0;
    for (int i = 0; i < 256; i++) {
        uint32_t v = be32r(bb + i * 4), p = s;
        s += v;
        if (s < p) s++;                                     /* con riporto */
    }
    be32w(bb + 4, ~s);

    uint8_t *r = blocco(&a, RADICE);                       /* radice */
    be32w(r, 2); be32w(r + 12, 72);
    be32w(r + 312, 0xFFFFFFFFu);                           /* bitmap valida */
    be32w(r + 316, RADICE + 1);
    nome_e_data(&a, r, "RockStar ITA");
    be32w(r + 472, a.giorni); be32w(r + 476, a.minuti);
    be32w(r + 484, a.giorni); be32w(r + 488, a.minuti);
    be32w(r + 508, ST_ROOT);

    int s_dir = nuova_cartella(&a, RADICE, "s");
    static const char avvio[] = "rockstar\n";              /* a capo Amiga: solo LF */
    nuovo_file(&a, s_dir, "startup-sequence", (const uint8_t *)avvio, sizeof avvio - 1);
    nuovo_file(&a, RADICE, "rockstar", exe, n_exe);
    somma_testata(blocco(&a, s_dir));
    /* le testate dei file e le estensioni: checksum dopo averle riempite */
    for (int b = RADICE + 2; b < a.libero; b++) {
        uint8_t *x = blocco(&a, b);
        if (be32r(x) == 2 || be32r(x) == 16) somma_testata(x);
    }
    somma_testata(r);

    uint8_t *bm = blocco(&a, RADICE + 1);                  /* bitmap: 1 = libero */
    for (int b = 2; b < BLOCCHI; b++) {
        int usato = b == RADICE || b == RADICE + 1 || (b >= RADICE + 2 && b < a.libero);
        if (!usato) bm[4 + (b - 2) / 32 * 4 + 3 - ((b - 2) % 32) / 8] |= (uint8_t)(1u << ((b - 2) % 8));
    }
    s = 0;
    for (int i = 1; i < 128; i++) s += be32r(bm + i * 4);
    be32w(bm, 0u - s);
    return a.d;
}

/* ------------------------------------------------------------ LhA */

static uint16_t crc16(const uint8_t *p, size_t n, uint16_t c) {
    while (n--) {
        c ^= *p++;
        for (int k = 0; k < 8; k++) c = (uint16_t)(c & 1 ? (c >> 1) ^ 0xA001 : c >> 1);
    }
    return c;
}

/* -lh5-, come lha_amiga.py: LZSS goloso (finestra 8K) e Huffman a blocchi */
enum { NC = 510, NT = 19, NP = 14, CBIT = 9, TBIT = 5, PBIT = 4, FINESTRA = 8192, MAXM = 256, MINM = 3 };

typedef struct { uint8_t *o; size_t n, cap; uint32_t acc; int nb; } bw_t;

static void bw_put(bw_t *b, int nbit, uint32_t v) {
    if (nbit <= 0) return;
    b->acc = (b->acc << nbit) | (v & ((1u << nbit) - 1));
    b->nb += nbit;
    while (b->nb >= 8) {
        b->nb -= 8;
        if (b->n == b->cap) { b->cap = b->cap * 2 + 4096; b->o = realloc(b->o, b->cap); }
        b->o[b->n++] = (uint8_t)(b->acc >> b->nb);
    }
    b->acc &= (1u << b->nb) - 1;
}

/* lunghezze di Huffman (0 = assente), al massimo 16 bit */
static void lunghezze(const uint32_t *freq, int n, uint8_t *lung) {
    uint32_t f[NC], peso[2 * NC];
    int padre[2 * NC], vivo[2 * NC];
    memcpy(f, freq, (size_t)n * 4);
    for (;;) {
        int k = 0, usati = 0;
        memset(lung, 0, (size_t)n);
        for (int i = 0; i < n; i++) if (f[i]) usati++;
        if (usati < 2) return;
        for (int i = 0; i < n; i++) { peso[i] = f[i]; vivo[i] = f[i] != 0; padre[i] = -1; }
        k = n;
        for (int giri = 0; giri < usati - 1; giri++) {
            int a = -1, b = -1;
            for (int i = 0; i < k; i++) {
                if (!vivo[i]) continue;
                if (a < 0 || peso[i] < peso[a]) { b = a; a = i; }
                else if (b < 0 || peso[i] < peso[b]) b = i;
            }
            peso[k] = peso[a] + peso[b]; vivo[k] = 1; padre[k] = -1;
            vivo[a] = vivo[b] = 0; padre[a] = padre[b] = k;
            k++;
        }
        int massimo = 0;
        for (int i = 0; i < n; i++) {
            if (!f[i]) continue;
            int l = 0;
            for (int x = i; padre[x] >= 0; x = padre[x]) l++;
            lung[i] = (uint8_t)l;
            if (l > massimo) massimo = l;
        }
        if (massimo <= 16) return;
        for (int i = 0; i < n; i++) f[i] = f[i] ? (f[i] + 1) / 2 : 0;   /* appiattisce e riprova */
    }
}

static void codici(const uint8_t *lung, int n, uint16_t *cod) {
    uint32_t c = 0;
    for (int l = 1; l <= 16; l++) {
        for (int s = 0; s < n; s++) if (lung[s] == l) cod[s] = (uint16_t)c++;
        c <<= 1;
    }
}

static void scrivi_pt(bw_t *b, const uint8_t *lung, int n, int nbit, int speciale) {
    while (n > 0 && !lung[n - 1]) n--;
    bw_put(b, nbit, (uint32_t)n);
    for (int i = 0; i < n;) {
        int k = lung[i++];
        if (k <= 6) bw_put(b, 3, (uint32_t)k);
        else bw_put(b, k - 3, (1u << (k - 3)) - 2);
        if (i == speciale) {
            int z = 0;
            while (i < 6 && i < n && !lung[i]) { i++; z++; }
            bw_put(b, 2, (uint32_t)z);
        }
    }
}

static int bit_len(uint32_t v) { int j = 0; while (v) { j++; v >>= 1; } return j; }

typedef struct { uint16_t l, d; } tok_t;                  /* l = 0: letterale d */

static void blocco_lh5(bw_t *b, const tok_t *t, int nt) {
    uint32_t cf[NC] = { 0 }, pf[NP] = { 0 }, tf[NT] = { 0 };
    uint8_t cl[NC], pl[NP], tl[NT];
    uint16_t cc[NC] = { 0 }, pc[NP] = { 0 }, tc[NT] = { 0 };
    for (int i = 0; i < nt; i++) {
        if (!t[i].l) cf[t[i].d]++;
        else { cf[t[i].l - MINM + 256]++; pf[bit_len(t[i].d - 1u)]++; }
    }
    bw_put(b, 16, (uint32_t)nt);
    lunghezze(cf, NC, cl);
    int usati = 0, unico = 0;
    for (int i = 0; i < NC; i++) if (cf[i]) { usati++; unico = i; }
    if (usati == 1) {
        bw_put(b, TBIT, 0); bw_put(b, TBIT, 0);
        bw_put(b, CBIT, 0); bw_put(b, CBIT, (uint32_t)unico);
        memset(cl, 0, sizeof cl);
    } else {
        int n = NC;
        while (n > 0 && !cl[n - 1]) n--;
        static uint8_t ss[NC * 2];                        /* sequenza: simbolo, extra */
        static uint16_t sx[NC * 2];
        int ns = 0;
        for (int i = 0; i < n;) {
            int k = cl[i++];
            if (!k) {
                int z = 1;
                while (i < n && !cl[i]) { i++; z++; }
                if (z <= 2) { while (z--) { ss[ns] = 0; sx[ns++] = 0; tf[0]++; } }
                else if (z <= 18) { ss[ns] = 1; sx[ns++] = (uint16_t)(z - 3); tf[1]++; }
                else if (z == 19) { ss[ns] = 0; sx[ns++] = 0; ss[ns] = 1; sx[ns++] = 15; tf[0]++; tf[1]++; }
                else { ss[ns] = 2; sx[ns++] = (uint16_t)(z - 20); tf[2]++; }
            } else { ss[ns] = (uint8_t)(k + 2); sx[ns++] = 0; tf[k + 2]++; }
        }
        lunghezze(tf, NT, tl);
        int ut = 0, unico_t = 0;
        for (int i = 0; i < NT; i++) if (tf[i]) { ut++; unico_t = i; }
        if (ut == 1) {
            bw_put(b, TBIT, 0); bw_put(b, TBIT, (uint32_t)unico_t);
            memset(tl, 0, sizeof tl);
        } else {
            scrivi_pt(b, tl, NT, TBIT, 3);
            codici(tl, NT, tc);
        }
        bw_put(b, CBIT, (uint32_t)n);
        for (int i = 0; i < ns; i++) {
            bw_put(b, tl[ss[i]], tc[ss[i]]);
            if (ss[i] == 1) bw_put(b, 4, sx[i]);
            else if (ss[i] == 2) bw_put(b, CBIT, sx[i]);
        }
        codici(cl, NC, cc);
    }
    lunghezze(pf, NP, pl);
    int up = 0, unico_p = 0;
    for (int i = 0; i < NP; i++) if (pf[i]) { up++; unico_p = i; }
    if (up <= 1) {
        bw_put(b, PBIT, 0); bw_put(b, PBIT, (uint32_t)unico_p);
        memset(pl, 0, sizeof pl);
    } else {
        scrivi_pt(b, pl, NP, PBIT, -1);
        codici(pl, NP, pc);
    }
    for (int i = 0; i < nt; i++) {
        if (!t[i].l) { bw_put(b, cl[t[i].d], cc[t[i].d]); continue; }
        int s = t[i].l - MINM + 256;
        bw_put(b, cl[s], cc[s]);
        uint32_t d = t[i].d - 1u;
        int j = bit_len(d);
        bw_put(b, pl[j], pc[j]);
        if (j > 1) bw_put(b, j - 1, d - (1u << (j - 1)));
    }
}

/* -> dati -lh5- (malloc), lunghezza in *nout */
static uint8_t *lh5(const uint8_t *d, size_t n, size_t *nout) {
    enum { HB = 15, PROF = 96 };
    int32_t *testa = malloc(sizeof(int32_t) << HB), *prec = malloc((n ? n : 1) * sizeof(int32_t));
    tok_t *t = malloc((n ? n : 1) * sizeof *t);
    for (int i = 0; i < 1 << HB; i++) testa[i] = -1;
    size_t nt = 0;
#define H3(p) ((((uint32_t)d[p] << 10) ^ ((uint32_t)d[(p) + 1] << 5) ^ d[(p) + 2]) & ((1u << HB) - 1))
#define INS(p) do { if ((p) + 2 < n) { uint32_t h_ = H3(p); prec[p] = testa[h_]; testa[h_] = (int32_t)(p); } } while (0)
    for (size_t i = 0; i < n;) {
        size_t mig = 0, mig_d = 0;
        if (i + 2 < n) {
            size_t lim = n - i < MAXM ? n - i : MAXM;
            int giri = 0;
            for (int32_t p = testa[H3(i)]; p >= 0 && i - (size_t)p < FINESTRA && giri < PROF; p = prec[p], giri++) {
                if (mig >= lim || d[(size_t)p + mig] != d[i + mig]) continue;
                size_t l = 0;
                while (l < lim && d[(size_t)p + l] == d[i + l]) l++;
                if (l > mig) { mig = l; mig_d = i - (size_t)p; if (l == lim) break; }
            }
        }
        if (mig >= MINM) {
            t[nt].l = (uint16_t)mig; t[nt++].d = (uint16_t)mig_d;
            for (size_t q = i; q < i + mig; q++) INS(q);
            i += mig;
        } else {
            t[nt].l = 0; t[nt++].d = d[i];
            INS(i);
            i++;
        }
    }
#undef INS
#undef H3
    bw_t b = { 0 };
    for (size_t k = 0; k < nt; k += 16384)
        blocco_lh5(&b, t + k, (int)(nt - k < 16384 ? nt - k : 16384));
    if (b.nb) bw_put(&b, 8 - b.nb, 0);                    /* ultimo byte */
    free(testa); free(prec); free(t);
    *nout = b.n;
    return b.o;
}

static void le16(uint8_t *p, uint32_t v) { p[0] = (uint8_t)v; p[1] = (uint8_t)(v >> 8); }
static void le32(uint8_t *p, uint32_t v) { le16(p, v); le16(p + 2, v >> 16); }

/* una voce come lha_amiga.py (livello 1, sistema 'A'): -lh5-, o -lh0- se
 * comprimere non conviene */
static size_t voce_lha(uint8_t *out, const char *percorso, const uint8_t *d, size_t n, uint32_t quando) {
    size_t nc = 0;
    uint8_t *comp = n ? lh5(d, n, &nc) : NULL;
    const char *metodo = "-lh5-";
    const uint8_t *dati = comp;
    if (!comp || nc >= n) { metodo = "-lh0-"; dati = d; nc = n; }
    const char *nome = strrchr(percorso, '/');
    nome = nome ? nome + 1 : percorso;
    size_t lc = (size_t)(nome - percorso), ln = strlen(nome);
    uint8_t est[300];
    size_t ne = 0, primo = 0;
    if (lc) {                                              /* cartella: separatori $FF */
        est[ne++] = 0x02;
        for (size_t i = 0; i < lc; i++) est[ne++] = percorso[i] == '/' ? 0xFF : (uint8_t)percorso[i];
        le16(est + ne, 5); ne += 2;
        est[ne++] = 0x00; est[ne++] = 0; est[ne++] = 0;   /* CRC dell'header, dopo */
        le16(est + ne, 0); ne += 2;
        primo = 1 + lc + 2;
    }
    uint8_t *h = out;
    size_t hs = 5 + 4 + 4 + 4 + 3 + ln + 2 + 1 + 2;
    uint8_t *b = h + 2;
    memcpy(b, metodo, 5);
    le32(b + 5, (uint32_t)(nc + ne));
    le32(b + 9, (uint32_t)n);
    le32(b + 13, quando);
    b[17] = 0x00; b[18] = 0x01; b[19] = (uint8_t)ln;
    memcpy(b + 20, nome, ln);
    le16(b + 20 + ln, crc16(d, n, 0));
    b[22 + ln] = 'A';
    le16(b + 23 + ln, (uint32_t)primo);
    h[0] = (uint8_t)hs;
    memcpy(h + 2 + hs, est, ne);
    unsigned sum = 0;
    for (size_t i = 0; i < hs; i++) sum += h[2 + i];
    h[1] = (uint8_t)sum;
    if (lc) le16(h + 2 + hs + primo + 1, crc16(h, 2 + hs + ne, 0));
    memcpy(h + 2 + hs + ne, dati, nc);
    free(comp);
    return 2 + hs + ne + nc;
}

static uint32_t ora_dos(void) {
    time_t t = time(NULL);
    struct tm *l = localtime(&t);
    return (uint32_t)(l->tm_year - 80) << 25 | (uint32_t)(l->tm_mon + 1) << 21 | (uint32_t)l->tm_mday << 16 |
           (uint32_t)l->tm_hour << 11 | (uint32_t)l->tm_min << 5 | (uint32_t)(l->tm_sec / 2);
}

/* ------------------------------------------------------------ insieme */

typedef struct { const char *nome; const uint8_t *d; size_t n; } voce_t;

#define VOCE(i) { KIT_WHD_NOME_##i, KIT_WHD_##i, KIT_WHD_##i##_LUNG }
static const voce_t s_whd[KIT_WHD_N] = { VOCE(0), VOCE(1), VOCE(2), VOCE(3), VOCE(4), VOCE(5), VOCE(6) };
_Static_assert(KIT_WHD_N == 7, "amiga_kit.h: cambiato il numero dei file di WHDLoad, aggiorna s_whd");

int amiga_esporta(const char *disco, const char *dove, char *msg, size_t nm) {
    size_t lb = amiga_lingue_lung_base();
    uint8_t *base = malloc(lb), *img = NULL, *blob = NULL, *exe = NULL, *adf = NULL, *lha = NULL;
    int ok = 0;
    char p[1024];
    if (!amiga_disco_base(disco, base, lb, amiga_lingue_crc_base(), msg, nm)) goto fine;

    /* immagine italiana: base + patch del kit */
    img = malloc(KIT_IMM_LUNG);
    memcpy(img, base, KIT_IMM_LUNG);
    for (int i = 0; i < KIT_PATCH_N; i++)
        memcpy(img + KIT_PATCH_tratti[i][0], KIT_PATCH_byte + KIT_PATCH_tratti[i][2], KIT_PATCH_tratti[i][1]);
    if (amiga_crc32(img, KIT_IMM_LUNG) != KIT_IMM_CRC) {
        snprintf(msg, nm, "L'immagine italiana non e' quella attesa (CRC %08X).", amiga_crc32(img, KIT_IMM_LUNG));
        goto fine;
    }

    /* eseguibile Amiga: testa + immagine compressa + coda */
    size_t plen = 0;
    int parz = 0;
    blob = s404_comprimi(img, KIT_IMM_LUNG, &plen, &parz);
    if (!blob) { snprintf(msg, nm, "Memoria insufficiente."); goto fine; }
    exe = malloc(KIT_EXE_LUNG);
    if (plen != KIT_BLOB_N || KIT_EXE_TESTA_LUNG + plen + KIT_EXE_CODA_LUNG != KIT_EXE_LUNG) {
        snprintf(msg, nm, "Compressione diversa da quella attesa (%u byte invece di %u).",
                 (unsigned)plen, (unsigned)KIT_BLOB_N);
        goto fine;
    }
    memcpy(exe, KIT_EXE_TESTA, KIT_EXE_TESTA_LUNG);
    memcpy(exe + KIT_EXE_TESTA_LUNG, blob, plen);
    memcpy(exe + KIT_EXE_TESTA_LUNG + plen, KIT_EXE_CODA, KIT_EXE_CODA_LUNG);
    if (amiga_crc32(exe, KIT_EXE_LUNG) != KIT_EXE_CRC) {
        snprintf(msg, nm, "L'eseguibile Amiga non e' quello atteso (CRC %08X).", amiga_crc32(exe, KIT_EXE_LUNG));
        goto fine;
    }

    if (!cartella(dove)) { snprintf(msg, nm, "Non riesco a creare la cartella %s.", dove); goto fine; }
    adf = crea_adf(exe, KIT_EXE_LUNG);
    snprintf(p, sizeof p, "%s/RockStar_ITA_1MB.adf", dove);
    if (!scrivi_file(p, adf, BLOCCHI * 512)) { snprintf(msg, nm, "Non riesco a scrivere %s.", p); goto fine; }

    /* WHDLoad: i file del kit, con l'immagine al suo posto, in un archivio */
    size_t cap = 1024;
    for (int i = 0; i < KIT_WHD_N; i++) cap += 600 + (i == (int)KIT_WHD_IMMAGINE ? KIT_IMM_LUNG : s_whd[i].n);
    lha = malloc(cap);
    size_t nl = 0;
    uint32_t quando = ora_dos();
    for (int i = 0; i < KIT_WHD_N; i++) {
        const uint8_t *d = i == (int)KIT_WHD_IMMAGINE ? img : s_whd[i].d;
        size_t n = i == (int)KIT_WHD_IMMAGINE ? KIT_IMM_LUNG : s_whd[i].n;
        nl += voce_lha(lha + nl, s_whd[i].nome, d, n, quando);
    }
    lha[nl++] = 0;
    snprintf(p, sizeof p, "%s/%s", dove, KIT_WHD_LHA);
    if (!scrivi_file(p, lha, nl)) { snprintf(msg, nm, "Non riesco a scrivere %s.", p); goto fine; }

    snprintf(msg, nm, "Fatto, in %s:\n"
             "  RockStar_ITA_1MB.adf  floppy avviabile (ogni Amiga con 1 MB)\n"
             "  %s  installazione WHDLoad", dove, KIT_WHD_LHA);
    ok = 1;
fine:
    free(base); free(img); free(blob); free(exe); free(adf); free(lha);
    return ok;
}
