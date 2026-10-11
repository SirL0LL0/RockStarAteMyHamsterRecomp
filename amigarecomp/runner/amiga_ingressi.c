/* amiga_ingressi.c - tastiera e joypad del PC verso l'Amiga.
 *
 * Ogni azione (amiga_ingressi.h) ha un tasto e un pulsante/asse del joypad,
 * scelti nella pagina Controller del launcher. I tasti associati non arrivano
 * alla tastiera Amiga come tali (le frecce non diventano anche i tasti cursore);
 * quelli liberi si'. Lo stick analogico sinistro muove sempre il puntatore. */
#include <string.h>
#include "amiga_ingressi.h"
#include "amiga_hw.h"

/* codifica dei pulsanti del joypad come recomp_launcher.h */
#define PAD_BOTTONE(c)        (1 + (c))
#define PAD_E_BOTTONE(v)      ((v) > 0 && (v) < 100)
#define PAD_E_ASSE(v)         ((v) >= 100 && (v) < 1000)
#define PAD_CODICE_BOTTONE(v) ((v) - 1)
#define PAD_CODICE_ASSE(v)    (((v) - 100) / 2)
#define PAD_ASSE_POSITIVO(v)  (((v) - 100) & 1)

static amiga_associazioni_t s_ass;
static SDL_GameController *s_pad[4];
static int s_tasto_giu[AZ_NUMERO];
static int s_era_giu[AZ_NUMERO];
static int s_resto_x, s_resto_y;

/* codici tastiera Amiga per le azioni che sono tasti */
static const int s_codice_amiga[AZ_NUMERO] = {
    [AZ_SPAZIO] = 0x40, [AZ_INVIO] = 0x44, [AZ_BACKSPACE] = 0x41, [AZ_ESC] = 0x45,
};

void amiga_ingressi_default(amiga_associazioni_t *a) {
    static const int tasti[AZ_NUMERO] = {
        SDL_SCANCODE_UP, SDL_SCANCODE_DOWN, SDL_SCANCODE_LEFT, SDL_SCANCODE_RIGHT,
        SDL_SCANCODE_LCTRL, 0, 0,
        SDL_SCANCODE_SPACE, SDL_SCANCODE_RETURN, SDL_SCANCODE_BACKSPACE, SDL_SCANCODE_ESCAPE,
    };
    static const int pad[AZ_NUMERO] = {
        PAD_BOTTONE(SDL_CONTROLLER_BUTTON_DPAD_UP), PAD_BOTTONE(SDL_CONTROLLER_BUTTON_DPAD_DOWN),
        PAD_BOTTONE(SDL_CONTROLLER_BUTTON_DPAD_LEFT), PAD_BOTTONE(SDL_CONTROLLER_BUTTON_DPAD_RIGHT),
        PAD_BOTTONE(SDL_CONTROLLER_BUTTON_A),                /* fuoco: sceglie e salta i fumetti */
        PAD_BOTTONE(SDL_CONTROLLER_BUTTON_RIGHTSHOULDER),    /* clic sinistro, col puntatore sullo stick */
        PAD_BOTTONE(SDL_CONTROLLER_BUTTON_B),
        PAD_BOTTONE(SDL_CONTROLLER_BUTTON_X),                /* spazio: tenuto, ferma i testi */
        PAD_BOTTONE(SDL_CONTROLLER_BUTTON_Y),
        PAD_BOTTONE(SDL_CONTROLLER_BUTTON_LEFTSHOULDER),
        PAD_BOTTONE(SDL_CONTROLLER_BUTTON_BACK),
    };
    memcpy(a->tasto, tasti, sizeof tasti);
    memcpy(a->pad, pad, sizeof pad);
}

void amiga_ingressi_imposta(const amiga_associazioni_t *a) { s_ass = *a; }

static void apri_pad(int indice) {
    if (!SDL_IsGameController(indice)) return;
    for (int i = 0; i < 4; i++)
        if (!s_pad[i]) { s_pad[i] = SDL_GameControllerOpen(indice); return; }
}

int amiga_ingressi_evento(const SDL_Event *ev) {
    switch (ev->type) {
    case SDL_CONTROLLERDEVICEADDED:
        apri_pad(ev->cdevice.which);
        return 1;
    case SDL_CONTROLLERDEVICEREMOVED:
        for (int i = 0; i < 4; i++)
            if (s_pad[i] && SDL_JoystickInstanceID(SDL_GameControllerGetJoystick(s_pad[i])) == ev->cdevice.which) {
                SDL_GameControllerClose(s_pad[i]);
                s_pad[i] = NULL;
            }
        return 1;
    case SDL_KEYDOWN: case SDL_KEYUP: {
        int usato = 0;
        for (int i = 0; i < AZ_NUMERO; i++)
            if (s_ass.tasto[i] && s_ass.tasto[i] == (int)ev->key.keysym.scancode) {
                s_tasto_giu[i] = ev->type == SDL_KEYDOWN;
                usato = 1;
            }
        return usato;
    }
    }
    return 0;
}

static int pad_attivo(int v) {
    for (int i = 0; i < 4; i++) {
        if (!s_pad[i]) continue;
        if (PAD_E_BOTTONE(v) && SDL_GameControllerGetButton(s_pad[i], (SDL_GameControllerButton)PAD_CODICE_BOTTONE(v)))
            return 1;
        if (PAD_E_ASSE(v)) {
            int x = SDL_GameControllerGetAxis(s_pad[i], (SDL_GameControllerAxis)PAD_CODICE_ASSE(v));
            if (PAD_ASSE_POSITIVO(v) ? x > 16000 : x < -16000) return 1;
        }
    }
    return 0;
}

void amiga_ingressi_quadro(amiga_stato_ingressi_t *st, int sensibilita) {
    int giu[AZ_NUMERO];
    for (int i = 0; i < AZ_NUMERO; i++) {
        giu[i] = s_tasto_giu[i] || (s_ass.pad[i] && pad_attivo(s_ass.pad[i]));
        if (s_codice_amiga[i] && giu[i] != s_era_giu[i])
            amiga_hw_tasto((uint8_t)s_codice_amiga[i], !giu[i]);
        s_era_giu[i] = giu[i];
    }
    st->su = giu[AZ_SU]; st->giu = giu[AZ_GIU]; st->sx = giu[AZ_SINISTRA]; st->dx = giu[AZ_DESTRA];
    st->fuoco = giu[AZ_FUOCO];
    st->mouse_sx = giu[AZ_MOUSE_SX]; st->mouse_dx = giu[AZ_MOUSE_DX];
    /* stick sinistro -> puntatore: zona morta, poi fino a ~6 pixel per quadro
     * a sensibilita' 100 (risposta quadratica, per la precisione nei menu) */
    st->mdx = st->mdy = 0;
    for (int i = 0; i < 4; i++) {
        if (!s_pad[i]) continue;
        int ax = SDL_GameControllerGetAxis(s_pad[i], SDL_CONTROLLER_AXIS_LEFTX);
        int ay = SDL_GameControllerGetAxis(s_pad[i], SDL_CONTROLLER_AXIS_LEFTY);
        long vx = 0, vy = 0;
        if (ax > 6000 || ax < -6000) vx = (long)ax * (ax < 0 ? -ax : ax) / 32767;
        if (ay > 6000 || ay < -6000) vy = (long)ay * (ay < 0 ? -ay : ay) / 32767;
        /* unita': 1/100 di pixel per punto di sensibilita' */
        s_resto_x += (int)(vx * 6 * sensibilita / 32767);
        s_resto_y += (int)(vy * 6 * sensibilita / 32767);
        st->mdx += s_resto_x / 100; s_resto_x %= 100;
        st->mdy += s_resto_y / 100; s_resto_y %= 100;
        break;                                   /* il primo joypad muove il puntatore */
    }
}
