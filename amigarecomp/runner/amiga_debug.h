/* amiga_debug.h - modalita' debug del runner: registrazione sempre attiva e
 * finestra di ispezione mentre si gioca.
 *
 * Sempre attivi (costano poco, girano anche senza finestra):
 *   - anello delle chiamate: ogni JSR/BSR con quadro, indirizzo di ritorno, A7
 *   - anello delle scritture sulle variabili osservate: vecchio e nuovo valore
 *     e la chiamata piu' recente (dove stava il gioco)
 *   - anello dei messaggi, che il gioco segnala con amiga_debug_messaggio()
 *     (finiscono anche in messaggi.log)
 * F11 apre/chiude la finestra, Shift+F11 salva tutto in debug_dump.txt.
 *
 * Il motore non conosce il gioco: variabili e agganci li dichiara il gioco
 * in g_debug_gioco (game/<gioco>_debug.c).
 */
#pragma once
#include <stdint.h>
#include <SDL.h>

typedef enum { DV_U8, DV_U16, DV_U32, DV_HEX8, DV_HEX16, DV_CIFRE8 } debug_formato_t;

typedef struct {
    uint32_t indirizzo;
    debug_formato_t formato;     /* DV_CIFRE8: 8 cifre decimali, una per byte */
    const char *nome;
} debug_var_t;

/* chiamata a una funzione che tornera' a 'ritorno': il gioco ci appende
 * le sue osservazioni (per esempio "messaggio composto") */
typedef struct {
    uint32_t ritorno;
    void (*fn)(uint32_t ritorno);
} debug_aggancio_t;

typedef struct {
    const debug_var_t *var;
    int n_var;
    const debug_aggancio_t *agganci;
    int n_agganci;
    const char *annotazioni;     /* CSV indirizzo,nome,note per i nomi delle funzioni */
} debug_gioco_t;

extern const debug_gioco_t g_debug_gioco;

void amiga_debug_init(int apri_finestra);
void amiga_debug_chiamata(uint32_t ritorno, uint32_t a7);
void amiga_debug_scrittura(uint32_t indirizzo, int taglia, uint32_t vecchio, uint32_t nuovo);
void amiga_debug_messaggio(int numero, const char *testo);
void amiga_debug_quadro(uint64_t quadro);
int  amiga_debug_evento(const SDL_Event *ev);    /* 1 = consumato */
void amiga_debug_dump(const char *file);

/* bitmap delle variabili osservate: test veloce dentro m68k_write* */
extern uint8_t g_debug_osservati[0x100000 / 8];
static inline int amiga_debug_osservato(uint32_t a) {
    return a < 0x100000u && (g_debug_osservati[a >> 3] >> (a & 7) & 1);
}
