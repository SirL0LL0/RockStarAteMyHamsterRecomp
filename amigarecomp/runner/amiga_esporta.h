/* amiga_esporta.h - le versioni Amiga in italiano costruite dal disco
 * dell'utente: floppy ADF e installazione WHDLoad (.lha). */
#ifndef AMIGA_ESPORTA_H
#define AMIGA_ESPORTA_H

#include <stddef.h>

/* disco: il disco originale (IPF o ADF). cartella: dove scrivere; la crea.
 * 1 = fatto, e msg dice cosa c'e' e dove; 0 = errore, spiegato in msg. */
int amiga_esporta(const char *disco, const char *cartella, char *msg, size_t n_msg);

#endif
