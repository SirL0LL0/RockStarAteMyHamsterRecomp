/* amiga_disco.c - dal disco dell'utente alla base del gioco, senza file del
 * gioco nel programma. Stessi passi di base_canonica.py, ipf_leggi.py e
 * adf_depack.py della pipeline della traduzione.
 *
 *   53EC7260  Rock Star Ate My Hamster (Europe).ipf
 *             disco originale in formato CAPS/SPS: si ricostruiscono le tracce
 *             MFM, si decodificano i settori AmigaDOS e si legge RSTAR, che e'
 *             gia' il gioco decompresso da mettere a $8100.
 *   BB9DD80B  Rock Star Ate My Hamster (1989)(Codemasters).adf
 *             versione su file: RockStarAteMyHamster e' compresso (due stadi,
 *             bit a ritroso + RLE) ed e' la versione craccata; quattro testi
 *             tornano quelli dell'originale.
 *
 * In entrambi i casi la base (430848 byte) deve avere il CRC atteso. */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "amiga_disco.h"

#define CRC_IPF 0x53EC7260u
#define CRC_ADF 0xBB9DD80Bu
#define ADF_BYTE (1760 * 512)

uint32_t amiga_crc32(const uint8_t *p, size_t n) {
    uint32_t c = 0xFFFFFFFFu;
    while (n--) {
        c ^= *p++;
        for (int k = 0; k < 8; k++) c = (c >> 1) ^ (0xEDB88320u & (0u - (c & 1u)));
    }
    return ~c;
}

int amiga_disco_tipo(uint32_t crc) { return crc == CRC_IPF ? 1 : crc == CRC_ADF ? 2 : 0; }

const char *amiga_disco_nome(int tipo) {
    return tipo == 1 ? "Rock Star Ate My Hamster (Europe) - IPF originale"
         : tipo == 2 ? "Rock Star Ate My Hamster (1989)(Codemasters) - ADF"
         : "disco non riconosciuto";
}

static uint32_t be32(const uint8_t *p) { return (uint32_t)p[0] << 24 | p[1] << 16 | p[2] << 8 | p[3]; }

/* ------------------------------------------------------------ IPF */

typedef struct { uint8_t *b; size_t n, cap; int prec; } mfm_t;

static void mfm_metti(mfm_t *m, uint8_t v) {
    if (m->n == m->cap) { m->cap = m->cap ? m->cap * 2 : 16384; m->b = realloc(m->b, m->cap); }
    m->b[m->n++] = v;
}

/* byte di dati -> parola MFM (clock a 1 solo fra due zeri) */
static void mfm_codifica(mfm_t *m, uint8_t v) {
    uint16_t w = 0;
    for (int k = 7; k >= 0; k--) {
        int d = (v >> k) & 1, c = (m->prec == 0 && d == 0);
        w = (uint16_t)((w << 2) | (c << 1) | d);
        m->prec = d;
    }
    mfm_metti(m, (uint8_t)(w >> 8));
    mfm_metti(m, (uint8_t)w);
}

/* un blocco di flusso: elementi (tipo nei 5 bit bassi, larghezza del conteggio
 * nei 3 alti) fino al tipo 0. 1 sync e 4 grezzo: MFM gia' pronto; 2 dati da
 * codificare; 3 gap e 5 casuali: zeri codificati. */
static int ipf_traccia(const uint8_t *extra, size_t n_extra, uint32_t nblocchi, mfm_t *m) {
    for (uint32_t b = 0; b < nblocchi; b++) {
        if ((size_t)(b + 1) * 32 > n_extra) return 0;
        const uint8_t *d = extra + b * 32;
        uint32_t bflag = be32(d + 20), p = be32(d + 28);
        for (;;) {
            if (p >= n_extra) return 0;
            uint8_t testa = extra[p++];
            int tipo = testa & 0x1F, nb = testa >> 5;
            if (tipo == 0) break;
            uint32_t conta = 0;
            for (int i = 0; i < nb; i++) conta = conta << 8 | extra[p++];
            if (bflag & 2) conta = (conta + 7) / 8;              /* conteggio in bit */
            if (p + conta > n_extra) return 0;
            for (uint32_t i = 0; i < conta; i++) {
                uint8_t v = extra[p + i];
                if (tipo == 2) mfm_codifica(m, v);
                else if (tipo == 1 || tipo == 4) { mfm_metti(m, v); m->prec = v & 1; }
                else mfm_codifica(m, 0);
            }
            p += conta;
        }
    }
    return 1;
}

/* settori trackdisk: sync $4489 $4489, poi dispari/pari */
static int settori_amiga(const uint8_t *mfm, size_t n, uint8_t *traccia /* 11*512 */) {
    size_t tot = n + 1200;
    uint8_t *m = malloc(tot);
    memcpy(m, mfm, n);
    memcpy(m + n, mfm, n < 1200 ? n : 1200);                   /* la traccia e' circolare */
    if (n < 1200) memset(m + 2 * n, 0, 1200 - n);
    int trovati = 0, visto[11] = { 0 };
    for (size_t i = 0; i + 4 + 1080 <= tot; i++) {
        if (m[i] != 0x44 || m[i + 1] != 0x89 || m[i + 2] != 0x44 || m[i + 3] != 0x89) continue;
        const uint8_t *s = m + i + 4;
        uint32_t info = ((be32(s) & 0x55555555u) << 1) | (be32(s + 4) & 0x55555555u);
        int fmt = info >> 24, sec = (info >> 8) & 0xFF;
        if (fmt != 0xFF || sec >= 11 || visto[sec]) continue;
        uint8_t *dst = traccia + sec * 512;
        for (int k = 0; k < 512; k += 4) {
            uint32_t v = ((be32(s + 56 + k) & 0x55555555u) << 1) | (be32(s + 56 + 512 + k) & 0x55555555u);
            dst[k] = (uint8_t)(v >> 24); dst[k + 1] = (uint8_t)(v >> 16);
            dst[k + 2] = (uint8_t)(v >> 8); dst[k + 3] = (uint8_t)v;
        }
        visto[sec] = 1;
        trovati++;
    }
    free(m);
    return trovati;
}

static int adf_da_ipf(const uint8_t *d, size_t n, uint8_t *adf, char *err, size_t ne) {
    /* prima passata: dove sono i DATA, per chiave */
    enum { MAXC = 256 };
    const uint8_t *dati[MAXC] = { 0 };
    size_t n_dati[MAXC] = { 0 };
    for (size_t p = 0; p + 12 <= n;) {
        uint32_t lung = be32(d + p + 4);
        if (lung < 12 || p + lung > n) break;
        if (!memcmp(d + p, "DATA", 4)) {
            uint32_t ne_ = be32(d + p + 12), chiave = be32(d + p + 24);
            if (chiave < MAXC && p + lung + ne_ <= n) { dati[chiave] = d + p + lung; n_dati[chiave] = ne_; }
            p += lung + ne_;
        } else p += lung;
    }
    int tracce = 0;
    for (size_t p = 0; p + 12 <= n;) {
        uint32_t lung = be32(d + p + 4);
        if (lung < 12 || p + lung > n) break;
        if (!memcmp(d + p, "IMGE", 4)) {
            const uint8_t *im = d + p + 12;
            uint32_t cil = be32(im), testa = be32(im + 4), nblocchi = be32(im + 40), chiave = be32(im + 52);
            if (cil < 80 && testa < 2 && chiave < MAXC && dati[chiave]) {
                mfm_t m = { 0 };
                uint8_t traccia[11 * 512];
                if (!ipf_traccia(dati[chiave], n_dati[chiave], nblocchi, &m) ||
                    settori_amiga(m.b, m.n, traccia) != 11) {
                    snprintf(err, ne, "IPF: la traccia %u non si legge", cil * 2 + testa);
                    free(m.b);
                    return 0;
                }
                memcpy(adf + (cil * 2 + testa) * 11 * 512, traccia, sizeof traccia);
                free(m.b);
                tracce++;
            }
        }
        p += lung;
        if (!memcmp(d + p - lung, "DATA", 4)) p += be32(d + p - lung + 12);
    }
    if (tracce != 160) { snprintf(err, ne, "IPF: %d tracce su 160", tracce); return 0; }
    return 1;
}

/* ------------------------------------------------------------ AmigaDOS OFS */

static int hash_nome(const char *s) {
    int h = (int)strlen(s);
    for (; *s; s++) {
        int c = *s >= 'a' && *s <= 'z' ? *s - 32 : *s;
        h = (h * 13 + c) & 0x7FF;
    }
    return h % 72;
}

static uint8_t *leggi_file_ofs(const uint8_t *adf, const char *nome, size_t *lung) {
    uint32_t b = be32(adf + 880 * 512 + 24 + hash_nome(nome) * 4);
    for (int giri = 0; b && b < 1760 && giri < 100; giri++) {
        const uint8_t *h = adf + b * 512;
        int l = h[432];
        if (l == (int)strlen(nome)) {
            int uguale = 1;
            for (int i = 0; i < l; i++) {
                int a = h[433 + i], c = nome[i];
                if (a >= 'a' && a <= 'z') a -= 32;
                if (c >= 'a' && c <= 'z') c -= 32;
                if (a != c) uguale = 0;
            }
            if (uguale) {
                uint32_t dim = be32(h + 324), d = be32(h + 16);
                uint8_t *out = malloc(dim ? dim : 1);
                size_t n = 0;
                while (d && d < 1760 && n < dim) {
                    const uint8_t *bd = adf + d * 512;
                    uint32_t k = be32(bd + 12);
                    if (k > 488 || n + k > dim) break;
                    memcpy(out + n, bd + 24, k);
                    n += k;
                    d = be32(bd + 16);
                }
                if (n != dim) { free(out); return NULL; }
                *lung = dim;
                return out;
            }
        }
        b = be32(h + 496);                                   /* catena dell'hash */
    }
    return NULL;
}

/* ------------------------------------------------------------ ADF: depacker */

typedef struct { const uint8_t *m; uint32_t a0, d0; } bit_t;

static int bit(bit_t *s) {
    int c = (int)(s->d0 & 1);
    s->d0 >>= 1;
    if (!s->d0) {                                       /* ricarica: X=1 entra da sinistra */
        s->a0 -= 4;
        s->d0 = be32(s->m + s->a0);
        c = (int)(s->d0 & 1);
        s->d0 = (s->d0 >> 1) | 0x80000000u;
    }
    return c;
}

static uint32_t bits(bit_t *s, int n) {
    uint32_t v = 0;
    while (n--) v = (v << 1) | (uint32_t)bit(s);
    return v;
}

/* exe: il file RockStarAteMyHamster. Vedi adf_depack.py per lo schema. */
static int depack_adf(const uint8_t *exe, size_t n_exe, uint8_t *out, size_t cap, size_t *n_out) {
    enum { DEPACKER = 0x72, DATI = 0x2F8, LUNG_DATI = 0x398DC, TABELLA = 0x186,
           INIZIO1 = 0x1A7A4, FINE2 = 0x71000, GIOCO = 0x8100 };
    /* hunk: HEADER, nessun nome, tabella, poi il CODE */
    if (n_exe < 64 || be32(exe) != 0x3F3) return 0;
    size_t p = 4;
    while (be32(exe + p)) p += 4;                       /* nomi delle librerie (nessuno) */
    p += 4;
    uint32_t primo = be32(exe + p + 4), ultimo = be32(exe + p + 8);
    p += 12 + (ultimo - primo + 1) * 4;
    if ((be32(exe + p) & 0x3FFFFFFFu) != 0x3E9) return 0;
    uint32_t nlong = be32(exe + p + 4);
    const uint8_t *h = exe + p + 8;
    if (p + 8 + (size_t)nlong * 4 > n_exe || (size_t)nlong * 4 < DATI + LUNG_DATI) return 0;
    const uint8_t *tab = h + DEPACKER + TABELLA;

    uint8_t *mem = calloc(1, 0x80000);
    memcpy(mem + GIOCO, h + DATI, LUNG_DATI);
    bit_t s = { mem, GIOCO + LUNG_DATI, 0 };
    uint32_t a1 = INIZIO1;
    s.a0 -= 4; uint32_t a2 = a1 + be32(mem + s.a0);
    s.a0 -= 4; s.d0 = be32(mem + s.a0);
    if (a2 > FINE2) { free(mem); return 0; }
    for (;;) {
        uint32_t k = bits(&s, 3);
        if (k) {
            if (k == 7) {
                if (!bit(&s)) k = bits(&s, 2) + 7;
                else if ((k = bits(&s, 8)) != 0) k += 10;
                else if ((k = bits(&s, 12)) != 0) k += 0x109;
                else k = bits(&s, 15) + 0x110B;
            }
            while (k--) {                                   /* letterali dalla tabella */
                int d5, d1;
                if (!bit(&s)) { d5 = 8; d1 = 6; }
                else if (!bit(&s)) { d5 = 0; d1 = 3; }
                else if (!bit(&s)) { d5 = 0x48; d1 = 6; }
                else { d5 = 0x88; d1 = 7; }
                uint32_t i = bits(&s, d1) + (uint32_t)d5;
                if (a2 <= a1) break;
                mem[--a2] = i < 256 ? tab[i] : 0;
            }
        }
        if (a1 >= a2) break;
        uint32_t conta;                                     /* copia all'indietro */
        if (!bit(&s)) conta = bit(&s) ? 1 : 2;
        else {
            uint32_t c = bits(&s, 2);
            conta = c == 0 ? 3 : c == 3 ? bits(&s, 8) + 14 : c == 1 ? 4 + bits(&s, 1) : 6 + bits(&s, 3);
        }
        uint32_t dist = bits(&s, 9);
        for (uint32_t i = 0; i <= conta && a2 > a1; i++) {
            uint32_t sorg = a2 - 1 + dist;
            a2--;
            mem[a2] = mem[sorg];
        }
        if (a1 >= a2) break;
        if (s.a0 < GIOCO) { free(mem); return 0; }
    }
    size_t n = 0;                                           /* stadio 2: RLE */
    for (uint32_t i = INIZIO1; i < FINE2;) {
        uint8_t b = mem[i++];
        if (b == 0x6D && mem[i]) {
            uint32_t r = mem[i] + 3u;
            uint8_t v = mem[i + 1];
            i += 2;
            if (n + r > cap) { free(mem); return 0; }
            memset(out + n, v, r);
            n += r;
            continue;
        }
        if (b == 0x6D) i++;                                 /* "$6D, 0" = un $6D */
        if (n >= cap) { free(mem); return 0; }
        out[n++] = b;
    }
    free(mem);
    *n_out = n;
    return 1;
}

/* versione su file -> originale */
static const struct { uint32_t ind; const char *testo; size_t n; } s_ripristini[] = {
    { 0x112EA, "RELEASED THROUGH CODEMASTERS\xa0", 29 },
    { 0x11401, "THANKS TO THE MANAGERS OF NEW ORDER, HAPPY MONDAYS", 50 },
    { 0x1149C, "BIMBO ", 6 },
    { 0x117A8, "ANNIE SMALLPOX\xa0", 15 },
};

/* ------------------------------------------------------------ insieme */

int amiga_disco_base(const char *file, uint8_t *base, size_t lung, uint32_t crc_atteso,
                     char *err, size_t ne) {
    FILE *f = fopen(file, "rb");
    if (!f) { snprintf(err, ne, "non trovo %s", file); return 0; }
    fseek(f, 0, SEEK_END);
    long n = ftell(f);
    fseek(f, 0, SEEK_SET);
    uint8_t *d = malloc(n > 0 ? (size_t)n : 1);
    if (n <= 0 || fread(d, 1, (size_t)n, f) != (size_t)n) { fclose(f); free(d); snprintf(err, ne, "non riesco a leggere %s", file); return 0; }
    fclose(f);
    int tipo = amiga_disco_tipo(amiga_crc32(d, (size_t)n));
    if (!tipo) {
        snprintf(err, ne, "%s non e' un disco supportato: servono Rock Star Ate My Hamster (Europe).ipf "
                 "o Rock Star Ate My Hamster (1989)(Codemasters).adf", file);
        free(d);
        return 0;
    }
    memset(base, 0, lung);
    int ok = 0;
    if (tipo == 1) {
        uint8_t *adf = calloc(1, ADF_BYTE);
        size_t ln = 0;
        uint8_t *r = NULL;
        if (adf_da_ipf(d, (size_t)n, adf, err, ne)) {
            r = leggi_file_ofs(adf, "RSTAR", &ln);
            if (!r) snprintf(err, ne, "IPF: manca il file RSTAR");
        }
        if (r) { memcpy(base, r, ln < lung ? ln : lung); ok = 1; }
        free(r);
        free(adf);
    } else {
        size_t ln = 0, lo = 0;
        uint8_t *exe = (size_t)n == ADF_BYTE ? leggi_file_ofs(d, "RockStarAteMyHamster", &ln) : NULL;
        if (!exe) snprintf(err, ne, "ADF: manca il file RockStarAteMyHamster");
        else if (!depack_adf(exe, ln, base, lung, &lo)) snprintf(err, ne, "ADF: decompressione fallita");
        else {
            for (size_t i = 0; i < sizeof s_ripristini / sizeof s_ripristini[0]; i++)
                memcpy(base + s_ripristini[i].ind - 0x8100, s_ripristini[i].testo, s_ripristini[i].n);
            ok = 1;
        }
        free(exe);
    }
    free(d);
    if (ok && amiga_crc32(base, lung) != crc_atteso) {
        snprintf(err, ne, "la base ricavata dal disco non e' quella attesa (CRC %08X)", amiga_crc32(base, lung));
        ok = 0;
    }
    return ok;
}
