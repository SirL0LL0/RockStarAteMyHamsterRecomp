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
 * Sempre primi in classifica: il singolo in uscita sta in $128C4 (posizione,
 * 0 = nessuno, 1-10 in classifica, 11 e oltre fuori), $1289C e' la posizione
 * migliore che puo' raggiungere (calcolata all'uscita da qualita' e pubblico,
 * $B1F6) e $128C6 le settimane di salita (bit 7 = in discesa). Ogni settimana
 * $B35A lo fa salire di qualche posto verso $1289C o scendere, e se e' fra i
 * primi 10 scrive il segno $FE (il nostro disco) nella top 10 a $1241A.
 * L'album fa lo stesso con $128C5 e la top 10 a $12438 ($B2A8). La mod, se un
 * disco e' uscito, lo tiene al primo posto e in salita.
 *
 * Star sempre contente: ogni star ha un byte di contentezza ($129B7, 4 byte;
 * 0 e $FF = posto vuoto). Prima di ogni serata di un tour ($0A630) il gioco
 * prende la piu' scontenta ($0A8A6): se e' a 9 o piu' la serata va liscia e
 * tutte perdono 1 punto; sotto 9 partono le richieste (go-go girls, Porsche)
 * o, con 2-3 dischi d'argento ($128AE, $128AF), la star se ne va. I regali
 * le alzano tutte (auto +12 ... cibo +8). La mod le tiene a 20.
 *
 * Stadio pieno a ogni prezzo: i biglietti venduti sono il minore fra
 * la capienza ($12175) e 10 x fattore del prezzo ($12161: 9 6 4 2 1 per
 * 2 5 10 15 20 sterline) x $128CE ($09832). Con $128CE al massimo (255) a 15
 * e 20 sterline non si va oltre 5.100 e 2.550 biglietti: lo stadio (10.000)
 * non si riempie mai. La mod mette i fattori 9 8 6 5 4: una band al top
 * riempie lo stadio a ogni prezzo (a 20 sterline con $128CE da 250), una
 * mediocre continua a non farcela. Spenta, la tabella torna quella originale.
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
#define SINGOLO_POS_ADDR  0x128C4u
#define ALBUM_POS_ADDR    0x128C5u
#define SINGOLO_SETT_ADDR 0x128C6u
#define SINGOLO_MAX_ADDR  0x1289Cu
#define CONTENTEZZA_ADDR  0x129B7u
#define FATTORI_ADDR      0x12161u
#define FILE_MODS         "mods.ini"
#define PACCHETTO         "rockstar-trucchi"

typedef struct {
    const char *id, *nome, *descrizione, *name, *description;   /* italiano, inglese */
    int scelto;      /* nel launcher, prima di PLAY */
    int attivo;      /* nella partita in corso */
} trucco_t;

static trucco_t s_trucchi[] = {
    { "soldi_infiniti", "Soldi infiniti",
      "I soldi restano sempre a 999.999 sterline: ingaggi, concerti e dischi "
      "senza mai finire in rosso.",
      "Infinite money",
      "Your money always stays at 999,999 pounds: bookings, gigs and records "
      "without ever going into the red.", 0, 0 },
    { "trucco_originale", "Trucco originale F7 F8 F9",
      "Sblocca il trucco nascosto nel gioco. In partita: F7 aggiunge 1.000.000 di "
      "sterline; F8 fa suonare la band al massimo (classifica, vendite dei dischi, "
      "occasioni di lavoro); F9 porta il pubblico al massimo. Senza questa mod il "
      "trucco si attiva digitando C O L B O P S durante la partita, poi F7, F8 o F9.",
      "Original cheat F7 F8 F9",
      "Unlocks the cheat hidden in the game. In play: F7 adds 1,000,000 pounds; F8 "
      "makes the band play at its best (charts, record sales, job offers); F9 gives "
      "the biggest audience. Without this mod the cheat is enabled by typing "
      "C O L B O P S during the game, then F7, F8 or F9.", 0, 0 },
    { "primi_in_classifica", "Sempre primi in classifica",
      "Il singolo e l'album che pubblichi vanno subito al primo posto della "
      "classifica e non scendono piu'.",
      "Always number one",
      "The singles and albums you release go straight to number one in the "
      "charts and never drop.", 0, 0 },
    { "star_contente", "Star sempre contente",
      "Le rock star restano sempre contente: niente go-go girls, niente ricatti della "
      "Porsche, nessuno se ne va durante i tour. Gli altri imprevisti restano.",
      "Always happy stars",
      "Your rock stars stay happy: no go-go girls, no Porsche blackmail, nobody quits "
      "during tours. Other surprises still happen.", 0, 0 },
    { "stadio_pieno", "Stadio pieno a ogni prezzo",
      "Nel gioco originale a 15 e 20 sterline lo stadio non si riempie mai, nemmeno con "
      "la band al massimo. Con questa mod una band al top lo riempie a ogni prezzo; "
      "una band mediocre no.",
      "Stadiums sell out at any price",
      "In the original game a stadium never sells out at 15 or 20 pounds, not even with "
      "the band at its best. With this mod a top band fills it at any price; an average "
      "band still can't.", 0, 0 },
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
    if (s_trucchi[2].attivo) {                                     /* sempre primi */
        if (m68k_read8(SINGOLO_POS_ADDR)) {
            m68k_write8(SINGOLO_POS_ADDR, 1);
            m68k_write8(SINGOLO_MAX_ADDR, 1);
            m68k_write8(SINGOLO_SETT_ADDR, 5);                     /* sempre in salita */
        }
        if (m68k_read8(ALBUM_POS_ADDR)) m68k_write8(ALBUM_POS_ADDR, 1);
    }
    if (s_trucchi[3].attivo) {                                     /* star contente */
        for (uint32_t i = 0; i < 4; i++) {
            uint8_t v = m68k_read8(CONTENTEZZA_ADDR + i);
            if (v != 0 && v != 0xFF && v < 20) m68k_write8(CONTENTEZZA_ADDR + i, 20);
        }
    }
    {                                                              /* fattori del prezzo */
        static const uint8_t originali[5] = { 9, 6, 4, 2, 1 }, nuovi[5] = { 9, 8, 6, 5, 4 };
        const uint8_t *f = s_trucchi[4].attivo ? nuovi : originali;
        for (uint32_t i = 0; i < 5; i++)
            if (m68k_read8(FATTORI_ADDR + i) != f[i]) m68k_write8(FATTORI_ADDR + i, f[i]);
    }
}

/* ------------------------------------------------------------ menu in gioco */

int rockstar_mods_numero(void) { return N_TRUCCHI; }
const char *rockstar_mods_nome(int i) { return i >= 0 && i < N_TRUCCHI ? s_trucchi[i].nome : ""; }
int rockstar_mods_attivo(int i) { return i >= 0 && i < N_TRUCCHI && s_trucchi[i].attivo; }

/* acceso/spento subito, e ricordato in mods.ini come dal launcher */
void rockstar_mods_cambia(int i) {
    if (i < 0 || i >= N_TRUCCHI) return;
    for (int k = 0; k < N_TRUCCHI; k++) s_trucchi[k].scelto = s_trucchi[k].attivo;
    s_trucchi[i].scelto = !s_trucchi[i].attivo;
    salva();
}

/* ------------------------------------------------------------ fornitore */

/* i testi del launcher seguono la lingua scelta (recomp-ui, launcher_i18n) */
#if defined(RECOMP_LAUNCHER)
const char *launcher_i18n_language(void);
static int inglese(void) { const char *l = launcher_i18n_language(); return l && !strncmp(l, "en", 2); }
#else
static int inglese(void) { return 0; }
#endif
#define T(it, en) (inglese() ? (en) : (it))

static int package_count(void *ctx) { (void)ctx; return 1; }

static int package_get(void *ctx, int i, RecompLauncherCModPackage *o) {
    (void)ctx;
    if (i != 0) return 0;
    memset(o, 0, sizeof *o);
    copia(o->id, sizeof o->id, PACCHETTO);
    copia(o->version, sizeof o->version, "1.2");
    copia(o->name, sizeof o->name, T("Trucchi", "Cheats"));
    copia(o->author, sizeof o->author, "Lollo");
    copia(o->description, sizeof o->description, T("Trucchi per Rock Star Ate My Hamster.",
                                                   "Cheats for Rock Star Ate My Hamster."));
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
    copia(o->package_version, sizeof o->package_version, "1.2");
    copia(o->package_name, sizeof o->package_name, T("Trucchi", "Cheats"));
    copia(o->name, sizeof o->name, T(s_trucchi[i].nome, s_trucchi[i].name));
    copia(o->author, sizeof o->author, "Lollo");
    copia(o->description, sizeof o->description, T(s_trucchi[i].descrizione, s_trucchi[i].description));
    copia(o->group, sizeof o->group, T("Trucchi", "Cheats"));
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
