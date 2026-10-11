/* amiga_ingressi.h - tastiera e joypad del PC verso joystick, mouse e tasti
 * dell'Amiga, secondo le associazioni scelte nel launcher. */
#ifndef AMIGA_INGRESSI_H
#define AMIGA_INGRESSI_H

#include <SDL.h>

/* stesso ordine dei pulsanti del profilo "amiga" di recomp-ui
 * (consoles/amiga/amiga_profile.h, kAmigaPadButtons) */
enum {
    AZ_SU, AZ_GIU, AZ_SINISTRA, AZ_DESTRA, AZ_FUOCO,
    AZ_MOUSE_SX, AZ_MOUSE_DX,
    AZ_SPAZIO, AZ_INVIO, AZ_BACKSPACE, AZ_ESC,
    AZ_NUMERO
};

typedef struct {
    int tasto[AZ_NUMERO];    /* scancode SDL, 0 = nessuno */
    int pad[AZ_NUMERO];      /* codifica RECOMP_LAUNCHER_PAD_*, 0 = nessuno */
} amiga_associazioni_t;

typedef struct {
    int su, giu, sx, dx, fuoco;     /* joystick in porta 2 */
    int mouse_sx, mouse_dx;         /* pulsanti tenuti giu' da tasti o pad */
    int mdx, mdy;                   /* movimento del puntatore dallo stick, in pixel Amiga */
} amiga_stato_ingressi_t;

void amiga_ingressi_default(amiga_associazioni_t *a);
void amiga_ingressi_imposta(const amiga_associazioni_t *a);
/* 1 se l'evento e' stato usato (tasto associato, joypad): non va oltre */
int  amiga_ingressi_evento(const SDL_Event *ev);
/* stato del quadro; i tasti Amiga associati (Spazio, Invio...) vengono
 * inviati alla tastiera emulata quando cambiano */
void amiga_ingressi_quadro(amiga_stato_ingressi_t *st, int sensibilita);

#endif
