/* amiga_lingue.c - dalla base del disco all'immagine della chip RAM.
 *
 * Italiano: base a $8100 in 1 MB di zeri, piu' la patch (traduzione, codice
 * aggiunto, collegamenti fatti dal post-codice, vettori).
 * Inglese: base piu' la patch delle sole parti di codice, piu' la tabella
 * dei testi del disco ricopiata nella disposizione della tabella estesa
 * italiana (stesso algoritmo di tabella_inglese() in prepara_immagine.py):
 * cosi' gli indirizzi cablati nel C ricompilato valgono per tutte e due.
 * Alla fine il CRC deve essere quello dell'immagine preparata in build. */
#include <stdio.h>
#include <string.h>
#include "amiga_lingue.h"
#include "amiga_disco.h"
#include "lingue_dati.h"
#include "immagine_crc.h"

/* il C ricompilato e i dati delle lingue devono venire dalla stessa immagine */
_Static_assert(LINGUE_CRC_IT == AMIGA_IMMAGINE_CRC,
               "lingue_dati.h e il C generato vengono da immagini diverse: rifai game/prepara_immagine.py");

#define GIOCO 0x8100u
#define N_GRUPPI 165
#define N_STRINGHE 391

size_t   amiga_lingue_lung_base(void) { return LINGUE_LUNG_BASE; }
uint32_t amiga_lingue_crc_base(void) { return LINGUE_CRC_BASE; }
int      amiga_lingue_crc_valido(uint32_t crc) { return crc == LINGUE_CRC_IT || crc == LINGUE_CRC_EN; }

static void applica(uint8_t *chip, const uint8_t *byte, const uint32_t (*tratti)[3], int n) {
    for (int i = 0; i < n; i++) memcpy(chip + tratti[i][0], byte + tratti[i][2], tratti[i][1]);
}

/* la tabella del disco: 165 gruppi ($FF, conteggio-1, item) e 391 stringhe;
 * ogni item/stringa finisce col bit 7. 0 se la forma non torna. */
static int leggi_tabella(const uint8_t *t, size_t max, size_t *lung, size_t *off_str) {
    size_t p = 0;
    for (int g = 0; g < N_GRUPPI; g++) {
        if (p >= max || t[p] != 0xFF) return 0;
        p++;
        if (g == N_GRUPPI - 1) *off_str = p;
        int n = t[p++] + 1;
        while (n--) { while (p < max && t[p] < 0x80) p++; p++; }
    }
    for (int s = 0; s < N_STRINGHE; s++) { while (p < max && t[p] < 0x80) p++; p++; }
    if (p > max) return 0;
    *lung = p;
    return 1;
}

int amiga_lingue_immagine(const uint8_t *base, int lingua, uint8_t *chip, size_t n_chip,
                          char *err, size_t ne) {
    if (n_chip < 0x100000) { snprintf(err, ne, "memoria insufficiente"); return 0; }
    memset(chip, 0, n_chip);
    memcpy(chip + GIOCO, base, LINGUE_LUNG_BASE);
    uint32_t atteso;
    if (lingua == LINGUA_INGLESE) {
        applica(chip, LINGUE_PATCH_EN_byte, LINGUE_PATCH_EN_tratti, LINGUE_PATCH_EN_N);
        const uint8_t *t = base + (LINGUE_TAB_DISCO - GIOCO);
        size_t lung, off_str;
        if (!leggi_tabella(t, LINGUE_LUNG_BASE - (LINGUE_TAB_DISCO - GIOCO), &lung, &off_str) ||
            off_str > LINGUE_TAB_OFF_STR || lung + (LINGUE_TAB_OFF_STR - off_str) > LINGUE_TAB_LUNG) {
            snprintf(err, ne, "la tabella dei testi del disco non ha la forma attesa");
            return 0;
        }
        uint8_t *dst = chip + LINGUE_TAB_EXT;
        size_t extra = LINGUE_TAB_OFF_STR - off_str;
        memset(dst, 0, LINGUE_TAB_LUNG);
        memcpy(dst, t, off_str - 1);                         /* gruppi 0-163 */
        /* riempimento prima del $FF del gruppo 164 (nessuno lo legge) */
        memcpy(dst + off_str - 1 + extra, t + off_str - 1, lung - (off_str - 1));
        atteso = LINGUE_CRC_EN;
    } else {
        applica(chip, LINGUE_PATCH_IT_byte, LINGUE_PATCH_IT_tratti, LINGUE_PATCH_IT_N);
        atteso = LINGUE_CRC_IT;
    }
    uint32_t c = amiga_crc32(chip, 0x100000);
    if (c != atteso) {
        snprintf(err, ne, "l'immagine %s non e' quella attesa (CRC %08X invece di %08X)",
                 lingua == LINGUA_INGLESE ? "inglese" : "italiana", c, atteso);
        return 0;
    }
    return 1;
}
