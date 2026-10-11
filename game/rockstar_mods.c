/* rockstar_mods.c - trucchi di Rock Star Ate My Hamster nel menu Mods del
 * launcher (recomp-ui), e il loro effetto sul gioco a ogni quadro.
 *
 * Soldi infiniti: i soldi sono 8 cifre decimali, una per byte, a $123CA
 * (buffer_bcd_soldi: li mostra disegna_valore_soldi_bcd, li toglie
 * sottrai_soldi_gestisci_underflow). A ogni quadro si riportano a 999.999 e
 * si azzera $128BD, il flag "saldo negativo" che il gioco alza quando i soldi
 * scendono sotto zero.
 *
 * La scelta si ricorda in mods.ini accanto all'eseguibile.
 */
#include <stdio.h>
#include <string.h>

#include "recomp_launcher.h"
#include "genesis_runtime.h"
#include "rockstar_mods.h"

#define SOLDI_ADDR        0x123CAu
#define SALDO_NEG_ADDR    0x128BDu
#define FILE_MODS         "mods.ini"

static int s_soldi_infiniti;          /* attivo nella partita in corso */
static int s_soldi_infiniti_scelto;   /* scelta nel launcher, prima di PLAY */
static char s_errore[128];

static void copia(char *dst, size_t n, const char *src) { snprintf(dst, n, "%s", src); }

void rockstar_mods_carica(void) {
    FILE *f = fopen(FILE_MODS, "r");
    char riga[128];
    s_soldi_infiniti = 0;
    if (f) {
        while (fgets(riga, sizeof riga, f))
            if (!strncmp(riga, "soldi_infiniti=", 15)) s_soldi_infiniti = riga[15] == '1';
        fclose(f);
    }
    s_soldi_infiniti_scelto = s_soldi_infiniti;
}

static int salva(void) {
    FILE *f = fopen(FILE_MODS, "w");
    if (!f) { copia(s_errore, sizeof s_errore, "non riesco a scrivere mods.ini"); return 0; }
    fprintf(f, "soldi_infiniti=%d\n", s_soldi_infiniti_scelto);
    fclose(f);
    s_soldi_infiniti = s_soldi_infiniti_scelto;
    return 1;
}

void rockstar_mods_quadro(void) {
    if (!s_soldi_infiniti) return;
    static const uint8_t pieno[8] = { 0, 0, 9, 9, 9, 9, 9, 9 };      /* 999.999 */
    for (uint32_t i = 0; i < 8; i++) m68k_write8(SOLDI_ADDR + i, pieno[i]);
    m68k_write8(SALDO_NEG_ADDR, 0);
}

/* ------------------------------------------------------------ fornitore */

static int package_count(void *ctx) { (void)ctx; return 1; }

static int package_get(void *ctx, int i, RecompLauncherCModPackage *o) {
    (void)ctx;
    if (i != 0) return 0;
    memset(o, 0, sizeof *o);
    copia(o->id, sizeof o->id, "rockstar-trucchi");
    copia(o->version, sizeof o->version, "1.0");
    copia(o->name, sizeof o->name, "Trucchi");
    copia(o->author, sizeof o->author, "Lollo");
    copia(o->description, sizeof o->description, "Trucchi per Rock Star Ate My Hamster.");
    copia(o->license, sizeof o->license, "PolyForm-Noncommercial-1.0.0");
    o->enabled = 1;
    return 1;
}

static int feature_count(void *ctx) { (void)ctx; return 1; }

static int feature_get(void *ctx, int i, RecompLauncherCModFeature *o) {
    (void)ctx;
    if (i != 0) return 0;
    memset(o, 0, sizeof *o);
    copia(o->id, sizeof o->id, "soldi_infiniti");
    copia(o->package_id, sizeof o->package_id, "rockstar-trucchi");
    copia(o->package_version, sizeof o->package_version, "1.0");
    copia(o->package_name, sizeof o->package_name, "Trucchi");
    copia(o->name, sizeof o->name, "Soldi infiniti");
    copia(o->author, sizeof o->author, "Lollo");
    copia(o->description, sizeof o->description,
          "I soldi restano sempre a 999.999 sterline: ingaggi, concerti e "
          "dischi senza mai finire in rosso.");
    copia(o->group, sizeof o->group, "Trucchi");
    o->enabled = s_soldi_infiniti_scelto;
    return 1;
}

static int feature_option_get(void *ctx, const char *p, const char *f, int i, RecompLauncherCModOption *o) {
    (void)ctx; (void)p; (void)f; (void)i; (void)o;
    return 0;                                    /* nessuna opzione */
}

static int feature_enable(void *ctx, const char *p, const char *f, int on) {
    (void)ctx; (void)p;
    if (strcmp(f, "soldi_infiniti")) { copia(s_errore, sizeof s_errore, "trucco sconosciuto"); return 0; }
    s_soldi_infiniti_scelto = on != 0;
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
