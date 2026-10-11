/* amiga_video_gl.h - presentazione OpenGL con filtro CRT Commodore 1084S. */
#pragma once
#include <stdint.h>
#include <SDL.h>

int  amiga_video_gl_init(SDL_Window *win, int modo);   /* 0 = non disponibile: usare SDL_Renderer */
void amiga_video_gl_modo(int modo);                    /* 0 nitido, 1 Commodore 1084S */
int  amiga_video_gl_modo_attuale(void);
void amiga_video_gl_presenta(const uint32_t *pixel);   /* quadro 320x256 ARGB */
