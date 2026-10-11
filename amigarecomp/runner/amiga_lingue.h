/* amiga_lingue.h - dalla base del disco all'immagine della chip RAM, in
 * italiano o in inglese (game/prepara_immagine.py genera i dati). */
#ifndef AMIGA_LINGUE_H
#define AMIGA_LINGUE_H

#include <stddef.h>
#include <stdint.h>

enum { LINGUA_ITALIANO = 0, LINGUA_INGLESE = 1 };

size_t   amiga_lingue_lung_base(void);
uint32_t amiga_lingue_crc_base(void);
/* l'immagine e' riconosciuta (italiana o inglese di questa versione)? */
int      amiga_lingue_crc_valido(uint32_t crc);
/* chip: 1 MB. 1 = fatto e verificato; 0 = errore spiegato in errore */
int      amiga_lingue_immagine(const uint8_t *base, int lingua, uint8_t *chip, size_t n_chip,
                               char *errore, size_t n_errore);

#endif
