/* amiga_menu.h - il menu in gioco (F1 o Start del joypad): il gioco si ferma,
 * sopra l'immagine compare un elenco di voci. Le voci le registrano il runner
 * (schermo, volume, uscita) e il gioco (salvataggi, trucchi). */
#ifndef AMIGA_MENU_H
#define AMIGA_MENU_H

#include <stddef.h>
#include <stdint.h>
#include <SDL.h>

typedef struct {
    /* testo della voce, col valore attuale ("Volume: 80%") */
    void (*etichetta)(char *buf, size_t n);
    /* 0 = Invio/clic, -1/+1 = sinistra/destra. NULL = solo testo */
    void (*azione)(int verso);
    /* 0 = voce spenta (grigia, non si sceglie). NULL = sempre attiva */
    int  (*attiva)(void);
} amiga_voce_menu_t;

/* gruppo 0 = in alto (gioco), 1 = in basso (runner) */
void amiga_menu_registra(int gruppo, const amiga_voce_menu_t *voci, int n);

int  amiga_menu_aperto(void);
void amiga_menu_apri(void);
void amiga_menu_chiudi(void);
/* una riga di stato in fondo, per qualche secondo */
void amiga_menu_avviso(const char *testo);
/* con il menu aperto ogni evento passa da qui; 1 = usato */
int  amiga_menu_evento(const SDL_Event *ev);
/* disegna il menu sopra una copia del quadro (larghezza x altezza, ARGB) */
void amiga_menu_disegna(uint32_t *quadro, int larghezza, int altezza);

#endif
