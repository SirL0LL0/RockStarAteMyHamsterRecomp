/* amiga_video_gl.h - presentazione OpenGL: pixel netti o filtri CRT. */
#pragma once
#include <stdint.h>
#include <SDL.h>

/* modelli di schermo, nell'ordine del launcher (amiga_profile.h) */
enum { SCHERMO_NITIDO, SCHERMO_1084S, SCHERMO_EASYMODE, SCHERMO_SCANLINE, AMIGA_SCHERMI };
const char *amiga_video_gl_nome(int modo);

int  amiga_video_gl_init(SDL_Window *win, int modo);   /* 0 = non disponibile: usare SDL_Renderer */
void amiga_video_gl_modo(int modo);                    /* SCHERMO_* */
int  amiga_video_gl_modo_attuale(void);
void amiga_video_gl_filtro(int lineare);               /* pixel netti ammorbiditi (filtro lineare) */
void amiga_video_gl_scala_intera(int si);              /* 1 pixel perfetti, 0 il piu' grande possibile */
/* forma del pixel, nell'ordine del launcher: PAL o NTSC (come su un monitor
 * 4:3 di quello standard) o quadrata */
enum { ASPETTO_PAL, ASPETTO_NTSC, ASPETTO_QUADRATI, AMIGA_ASPETTI };
double amiga_video_gl_par(int aspetto);                /* larghezza di un pixel / altezza */
void amiga_video_gl_aspetto(int aspetto);              /* ASPETTO_* */
void amiga_video_gl_presenta(const uint32_t *pixel);   /* quadro 320x256 ARGB */
/* dove va il quadro (righe x 320) in una finestra w x h con la forma del
 * pixel ASPETTO_*; con intera il fattore verticale e' intero (il piu'
 * grande possibile), senza riempie la finestra */
void amiga_video_gl_rettangolo(int modo, int righe, int intera, int aspetto, int w, int h, int *vw, int *vh);
