/* amiga_menu.c - il menu in gioco, disegnato sopra l'immagine dell'Amiga con
 * il font della finestra di debug (8x14: 40 colonne, 18 righe a 320x256).
 *
 * Comandi: frecce su/giu' o croce del joypad o mouse in verticale per
 * scegliere; Invio, A o clic sinistro per confermare; sinistra/destra per
 * cambiare un valore; Esc, F1, B, Start o clic destro per tornare al gioco. */
#include <stdio.h>
#include <string.h>
#include "amiga_menu.h"
#include "font_debug.h"

#define MAX_VOCI 32

static const amiga_voce_menu_t *s_voci[MAX_VOCI];
static int s_gruppo[MAX_VOCI];
static int s_n;
static int s_aperto, s_scelta, s_mouse_y;
static char s_avviso[64];
static uint32_t s_avviso_fino;

void amiga_menu_registra(int gruppo, const amiga_voce_menu_t *voci, int n) {
    for (int i = 0; i < n && s_n < MAX_VOCI; i++) {
        /* il gruppo 0 sta prima di tutto il gruppo 1 */
        int pos = s_n;
        if (gruppo == 0)
            while (pos > 0 && s_gruppo[pos - 1] == 1) pos--;
        memmove(&s_voci[pos + 1], &s_voci[pos], (size_t)(s_n - pos) * sizeof s_voci[0]);
        memmove(&s_gruppo[pos + 1], &s_gruppo[pos], (size_t)(s_n - pos) * sizeof s_gruppo[0]);
        s_voci[pos] = &voci[i];
        s_gruppo[pos] = gruppo;
        s_n++;
    }
}

static int attiva(int i) {
    return s_voci[i]->azione && (!s_voci[i]->attiva || s_voci[i]->attiva());
}

static void sposta(int verso) {
    for (int giri = 0; giri < s_n; giri++) {
        s_scelta = (s_scelta + verso + s_n) % s_n;
        if (attiva(s_scelta)) return;
    }
}

int  amiga_menu_aperto(void) { return s_aperto; }

void amiga_menu_apri(void) {
    s_aperto = 1;
    s_mouse_y = 0;
    if (s_scelta >= s_n || !attiva(s_scelta)) { s_scelta = s_n - 1; sposta(1); }
}

void amiga_menu_chiudi(void) { s_aperto = 0; }

void amiga_menu_avviso(const char *testo) {
    snprintf(s_avviso, sizeof s_avviso, "%s", testo);
    s_avviso_fino = SDL_GetTicks() + 4000;
}

static void conferma(int verso) {
    if (s_scelta < s_n && attiva(s_scelta)) s_voci[s_scelta]->azione(verso);
}

int amiga_menu_evento(const SDL_Event *ev) {
    if (!s_aperto) return 0;
    switch (ev->type) {
    case SDL_KEYDOWN:
        switch (ev->key.keysym.sym) {
        case SDLK_UP: sposta(-1); break;
        case SDLK_DOWN: sposta(1); break;
        case SDLK_LEFT: conferma(-1); break;
        case SDLK_RIGHT: conferma(1); break;
        case SDLK_RETURN: case SDLK_KP_ENTER: case SDLK_SPACE: if (!ev->key.repeat) conferma(0); break;
        case SDLK_ESCAPE: case SDLK_F1: if (!ev->key.repeat) amiga_menu_chiudi(); break;
        default: break;
        }
        return 1;
    case SDL_CONTROLLERBUTTONDOWN:
        switch (ev->cbutton.button) {
        case SDL_CONTROLLER_BUTTON_DPAD_UP: sposta(-1); break;
        case SDL_CONTROLLER_BUTTON_DPAD_DOWN: sposta(1); break;
        case SDL_CONTROLLER_BUTTON_DPAD_LEFT: conferma(-1); break;
        case SDL_CONTROLLER_BUTTON_DPAD_RIGHT: conferma(1); break;
        case SDL_CONTROLLER_BUTTON_A: conferma(0); break;
        case SDL_CONTROLLER_BUTTON_B: case SDL_CONTROLLER_BUTTON_START:
        case SDL_CONTROLLER_BUTTON_GUIDE: amiga_menu_chiudi(); break;
        default: break;
        }
        return 1;
    case SDL_MOUSEMOTION:                       /* il mouse e' catturato: movimenti relativi */
        s_mouse_y += ev->motion.yrel;
        while (s_mouse_y >= 40) { sposta(1); s_mouse_y -= 40; }
        while (s_mouse_y <= -40) { sposta(-1); s_mouse_y += 40; }
        return 1;
    case SDL_MOUSEWHEEL:
        sposta(ev->wheel.y > 0 ? -1 : 1);
        return 1;
    case SDL_MOUSEBUTTONDOWN:
        if (ev->button.button == SDL_BUTTON_LEFT) conferma(0);
        else if (ev->button.button == SDL_BUTTON_RIGHT) amiga_menu_chiudi();
        return 1;
    case SDL_KEYUP: case SDL_MOUSEBUTTONUP: case SDL_CONTROLLERBUTTONUP: case SDL_CONTROLLERAXISMOTION:
        return 1;
    }
    return 0;
}

/* ------------------------------------------------------------ disegno */

static void testo(uint32_t *q, int L, int A, int x, int y, uint32_t col, const char *s) {
    for (; *s && x + FONT_DEBUG_L <= L; s++, x += FONT_DEBUG_L) {
        unsigned char c = (unsigned char)*s;
        if (c < 32 || c > 126) c = '?';
        const uint8_t *g = font_debug[c - 32];
        for (int r = 0; r < FONT_DEBUG_A && y + r < A; r++)
            for (int b = 0; b < 8; b++)
                if (g[r] & (0x80 >> b)) q[(y + r) * L + x + b] = col;
    }
}

static void rettangolo(uint32_t *q, int L, int A, int x0, int y0, int x1, int y1, uint32_t col, int scurisci) {
    for (int y = y0 < 0 ? 0 : y0; y < y1 && y < A; y++)
        for (int x = x0 < 0 ? 0 : x0; x < x1 && x < L; x++) {
            uint32_t *p = &q[y * L + x];
            *p = scurisci ? (0xFF000000u | ((*p >> 2) & 0x3F3F3Fu)) : col;
        }
}

void amiga_menu_disegna(uint32_t *q, int L, int A) {
    const uint32_t bianco = 0xFFFFFFFFu, grigio = 0xFF707888u, arancio = 0xFFFF8800u,
                   blu = 0xFF0055AAu, giallo = 0xFFFFDD55u;
    const int riga = FONT_DEBUG_A + 1;
    /* posizione di ogni voce nella lista (i gruppi separati da mezza riga) */
    static int pos[64];
    int lista = 0;
    for (int i = 0; i < s_n && i < 64; i++) {
        if (i > 0 && s_gruppo[i] != s_gruppo[i - 1]) lista += riga / 2;
        pos[i] = lista;
        lista += riga;
    }
    /* il riquadro sta nelle righe che si vedono (200 per Rock Star): se la
     * lista e' piu' lunga scorre, con la voce scelta sempre in vista */
    const int testa = riga + 8, piede = riga + 6;          /* titolo; riga dell'avviso */
    int spazio = A - 8 - testa - piede;
    if (spazio > lista) spazio = lista;
    int h = testa + spazio + piede, y0 = (A - h) / 2;
    if (y0 < 0) y0 = 0;
    int scorri = 0;
    if (lista > spazio && s_scelta >= 0 && s_scelta < s_n) {
        scorri = pos[s_scelta] + riga / 2 - spazio / 2;
        if (scorri > lista - spazio) scorri = lista - spazio;
        if (scorri < 0) scorri = 0;
    }
    rettangolo(q, L, A, 0, 0, L, A, 0, 1);                          /* il gioco in penombra */
    rettangolo(q, L, A, 16, y0, L - 16, y0 + h, blu, 0);            /* colori del Workbench 1.3 */
    rettangolo(q, L, A, 16, y0, L - 16, y0 + riga + 2, arancio, 0);
    testo(q, L, A, 24, y0 + 2, bianco, "ROCK STAR ATE MY HAMSTER - PAUSA");
    int alto = y0 + testa, basso = alto + spazio;
    for (int i = 0; i < s_n; i++) {
        int y = alto + pos[i] - scorri;
        if (y < alto || y + riga > basso + 1) continue;             /* fuori dalla finestra della lista */
        char t[64] = "";
        s_voci[i]->etichetta(t, sizeof t);
        int on = attiva(i);
        if (i == s_scelta && on) rettangolo(q, L, A, 20, y - 1, L - 20, y + riga - 1, 0xFF002244u, 0);
        testo(q, L, A, 28, y, !s_voci[i]->azione ? giallo : on ? (i == s_scelta ? arancio : bianco) : grigio, t);
    }
    if (scorri > 0) testo(q, L, A, L - 32, alto, giallo, "^");      /* altre voci sopra / sotto */
    if (scorri < lista - spazio) testo(q, L, A, L - 32, basso - riga, giallo, "v");
    if (s_avviso[0] && SDL_GetTicks() < s_avviso_fino)
        testo(q, L, A, 28, basso + 4, giallo, s_avviso);
}
