/* amiga_paula.h - audio Paula (4 canali DMA) per il runner. */
#pragma once
#include <stdint.h>

void amiga_paula_init(uint16_t *intreq);                 /* dove alzare gli interrupt audio */
void amiga_paula_volume(int percento);
void amiga_paula_avanza(uint64_t cicli_cpu);             /* genera fino a questo istante */
void amiga_paula_registro(uint32_t offset, uint16_t v);  /* AUDx* ($0A0-$0DA) */
void amiga_paula_dmacon(uint16_t prima, uint16_t dopo);
int  amiga_paula_prendi(int16_t **campioni);             /* campioni stereo pronti, poi azzera */
