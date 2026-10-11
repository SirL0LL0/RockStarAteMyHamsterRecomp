/* amiga_disco.h - dal disco dell'utente (IPF o ADF) alla base del gioco. */
#ifndef AMIGA_DISCO_H
#define AMIGA_DISCO_H

#include <stddef.h>
#include <stdint.h>

uint32_t amiga_crc32(const uint8_t *p, size_t n);

/* disco riconosciuto dal CRC32 dell'intero file: 1 IPF originale, 2 ADF
 * "(1989)(Codemasters)", 0 sconosciuto */
int amiga_disco_tipo(uint32_t crc_file);
const char *amiga_disco_nome(int tipo);

/* legge il file, ricava la base canonica (lung byte, da mettere a $8100) e ne
 * verifica il CRC. 1 = fatto; 0 = errore, spiegato in errore. */
int amiga_disco_base(const char *file, uint8_t *base, size_t lung, uint32_t crc_atteso,
                     char *errore, size_t n_errore);

#endif
