/* rockstar_mods.c - trucchi di Rock Star Ate My Hamster nel menu Mods del
 * launcher (recomp-ui), e il loro effetto sul gioco a ogni quadro.
 *
 * Soldi infiniti: i soldi sono 8 cifre decimali, una per byte, a $123CA
 * (buffer_bcd_soldi: li mostra disegna_valore_soldi_bcd, li toglie
 * sottrai_soldi_gestisci_underflow). A ogni quadro si riportano a 999.999 e
 * si azzera $128BD, il flag "saldo negativo" che il gioco alza quando i soldi
 * scendono sotto zero.
 *
 * Trucco originale: il gestore della tastiera del gioco (irq_livello2, $BA7A)
 * confronta i tasti premuti con la sequenza a $BB86 (codici tasto Amiga
 * $33 $18 $28 $35 $18 $19 $21: C O L B O P S) e conta quelli giusti in $BB8D;
 * un tasto sbagliato azzera il conto. A 7, F7 mette 1 nella cifra dei milioni
 * dei soldi ($123CB, +1.000.000), F8 porta $128CE a 255, F9 porta $128CD a
 * 255. La mod tiene il conto a 7, cioe' il trucco sempre sbloccato.
 *
 * Le guide del gioco chiamano F8 "Band plays their best" e F9 "Biggest
 * audience", e F7 "Extra 100,000": in questa versione F7 aggiunge invece
 * 1.000.000 (la cifra dei milioni, misurato: da 50.000 a 1.050.000).
 *
 * $128CE, qualita' dell'esibizione:
 * media del byte 20 dei record delle 4 star (2-30) piu' $1285C
 * ($8B5C-$8B7C). Decide la posizione in classifica (10 soglie a $121D7,
 * $B252), entra nei ricavi delle vendite (*256, $9850), sceglie la fascia
 * delle occasioni nel menu (<$46 <$6E <$A0 <$FA, $8F88) e a 200 o piu' fa
 * scattare l'evento dei dischi piratati ($D264, messaggio #170).
 * $128CD, pubblico: media del byte 22 dei record delle 4 star (1-15,
 * $8B46-$8B5A); deve superare $3B per le occasioni del menu ($8F88).
 * (Record delle star: 30 byte a $1147E, nome nei primi 20.)
 *
 * Le scelte si ricordano in mods.ini accanto all'eseguibile.
 */
#include <stdio.h>
#include <string.h>

#include "recomp_launcher.h"
#include "genesis_runtime.h"
#include "rockstar_mods.h"

#define SOLDI_ADDR        0x123CAu
#define SALDO_NEG_ADDR    0x128BDu
#define CONTO_TRUCCO_ADDR 0x0BB8Du
#define FILE_MODS         "mods.ini"
#define PACCHETTO         "rockstar-trucchi"

typedef struct {
    const char *id, *nome, *descrizione;
    int scelto;      /* nel launcher, prima di PLAY */
    int attivo;      /* nella partita in corso */
} trucco_t;

static trucco_t s_trucchi[] = {
    { "soldi_infiniti", "Soldi infiniti",
      "I soldi restano sempre a 999.999 sterline: ingaggi, concerti e dischi "
      "senza mai finire in rosso.", 0, 0 },
    { "trucco_originale", "Trucco originale (F7 / F8 / F9)",
      "Sblocca il trucco nascosto nel gioco. In partita: F7 aggiunge 1.000.000 di "
      "sterline; F8 fa suonare la band al massimo (classifica, vendite dei dischi, "
      "occasioni di lavoro); F9 porta il pubblico al massimo. Senza questa mod il "
      "trucco si attiva digitando C O L B O P S durante la partita, poi F7, F8 o F9.", 0, 0 },
};
#define N_TRUCCHI ((int)(sizeof s_trucchi / sizeof s_trucchi[0]))

static char s_errore[128];

static void copia(char *dst, size_t n, const char *src) { snprintf(dst, n, "%s", src); }

static trucco_t *trova(const char *id) {
    for (int i = 0; i < N_TRUCCHI; i++)
        if (!strcmp(s_trucchi[i].id, id)) return &s_trucchi[i];
    return NULL;
}

void rockstar_mods_carica(void) {
    FILE *f = fopen(FILE_MODS, "r");
    char riga[128];
    for (int i = 0; i < N_TRUCCHI; i++) s_trucchi[i].attivo = 0;
    if (f) {
        while (fgets(riga, sizeof riga, f)) {
            char *uguale = strchr(riga, '=');
            if (!uguale) continue;
            *uguale = 0;
            trucco_t *t = trova(riga);
            if (t) t->attivo = uguale[1] == '1';
        }
        fclose(f);
    }
    for (int i = 0; i < N_TRUCCHI; i++) s_trucchi[i].scelto = s_trucchi[i].attivo;
}

static int salva(void) {
    FILE *f = fopen(FILE_MODS, "w");
    if (!f) { copia(s_errore, sizeof s_errore, "non riesco a scrivere mods.ini"); return 0; }
    for (int i = 0; i < N_TRUCCHI; i++) {
        fprintf(f, "%s=%d\n", s_trucchi[i].id, s_trucchi[i].scelto);
        s_trucchi[i].attivo = s_trucchi[i].scelto;
    }
    fclose(f);
    return 1;
}

void rockstar_mods_quadro(void) {
    if (s_trucchi[0].attivo) {                                     /* soldi infiniti */
        static const uint8_t pieno[8] = { 0, 0, 9, 9, 9, 9, 9, 9 };  /* 999.999 */
        for (uint32_t i = 0; i < 8; i++) m68k_write8(SOLDI_ADDR + i, pieno[i]);
        m68k_write8(SALDO_NEG_ADDR, 0);
    }
    if (s_trucchi[1].attivo)                                       /* trucco originale */
        m68k_write8(CONTO_TRUCCO_ADDR, 7);
}

/* ------------------------------------------------------------ fornitore */

static int package_count(void *ctx) { (void)ctx; return 1; }

static int package_get(void *ctx, int i, RecompLauncherCModPackage *o) {
    (void)ctx;
    if (i != 0) return 0;
    memset(o, 0, sizeof *o);
    copia(o->id, sizeof o->id, PACCHETTO);
    copia(o->version, sizeof o->version, "1.1");
    copia(o->name, sizeof o->name, "Trucchi");
    copia(o->author, sizeof o->author, "Lollo");
    copia(o->description, sizeof o->description, "Trucchi per Rock Star Ate My Hamster.");
    copia(o->license, sizeof o->license, "PolyForm-Noncommercial-1.0.0");
    o->enabled = 1;
    return 1;
}

static int feature_count(void *ctx) { (void)ctx; return N_TRUCCHI; }

static int feature_get(void *ctx, int i, RecompLauncherCModFeature *o) {
    (void)ctx;
    if (i < 0 || i >= N_TRUCCHI) return 0;
    memset(o, 0, sizeof *o);
    copia(o->id, sizeof o->id, s_trucchi[i].id);
    copia(o->package_id, sizeof o->package_id, PACCHETTO);
    copia(o->package_version, sizeof o->package_version, "1.1");
    copia(o->package_name, sizeof o->package_name, "Trucchi");
    copia(o->name, sizeof o->name, s_trucchi[i].nome);
    copia(o->author, sizeof o->author, "Lollo");
    copia(o->description, sizeof o->description, s_trucchi[i].descrizione);
    copia(o->group, sizeof o->group, "Trucchi");
    o->enabled = s_trucchi[i].scelto;
    return 1;
}

static int feature_option_get(void *ctx, const char *p, const char *f, int i, RecompLauncherCModOption *o) {
    (void)ctx; (void)p; (void)f; (void)i; (void)o;
    return 0;                                    /* nessuna opzione */
}

static int feature_enable(void *ctx, const char *p, const char *f, int on) {
    (void)ctx; (void)p;
    trucco_t *t = trova(f);
    if (!t) { copia(s_errore, sizeof s_errore, "trucco sconosciuto"); return 0; }
    t->scelto = on != 0;
    return 1;
}

static int feature_set_option(void *ctx, const char *p, const char *f, const char *o, const char *v) {
    (void)ctx; (void)p; (void)f; (void)o; (void)v;
    copia(s_errore, sizeof s_errore, "questo trucco non ha opzioni");
    return 0;
}

static int set_enabled(void *ctx, const char *p, int on) { (void)ctx; (void)p; (void)on; return 1; }
static int commit(void *ctx, const char *immagine) { (void)ctx; (void)immagine; return salva(); }
static const char *last_error(void *ctx) { (void)ctx; return s_errore; }

static RecompLauncherCModProvider s_fornitore;

const struct RecompLauncherCModProvider *rockstar_mods_fornitore(const struct RecompLauncherCModProvider *base) {
    (void)base;
    s_fornitore.package_count = package_count;
    s_fornitore.package_get = package_get;
    s_fornitore.set_enabled = set_enabled;
    s_fornitore.commit = commit;
    s_fornitore.last_error = last_error;
    s_fornitore.feature_count = feature_count;
    s_fornitore.feature_get = feature_get;
    s_fornitore.feature_option_get = feature_option_get;
    s_fornitore.feature_enable = feature_enable;
    s_fornitore.feature_set_option = feature_set_option;
    return &s_fornitore;
}
