/* amiga_video_gl.h - presentazione OpenGL: pixel netti o filtri CRT. */
#pragma once
#include <stdint.h>
#include <SDL.h>

/* modelli di schermo, nell'ordine del launcher (amiga_profile.h) */
enum { SCHERMO_NITIDO, SCHERMO_1084S, SCHERMO_EASYMODE, SCHERMO_APERTURE, SCHERMO_SCANLINE, AMIGA_SCHERMI };
const char *amiga_video_gl_nome(int modo);

int  amiga_video_gl_init(SDL_Window *win, int modo);   /* 0 = non disponibile: usare SDL_Renderer */
void amiga_video_gl_modo(int modo);                    /* SCHERMO_* */
int  amiga_video_gl_modo_attuale(void);
void amiga_video_gl_filtro(int lineare);               /* pixel netti ammorbiditi (filtro lineare) */
void amiga_video_gl_presenta(const uint32_t *pixel);   /* quadro 320x256 ARGB */
/* dove va il quadro (righe x 320) in una finestra w x h: scala intera, la
 * piu' grande possibile; pixel quadrati per il nitido, PAL 4:3 per i CRT */
void amiga_video_gl_rettangolo(int modo, int righe, int w, int h, int *vw, int *vh);
