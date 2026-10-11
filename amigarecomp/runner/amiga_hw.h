/* amiga_hw.h - l'hardware Amiga (OCS) visto dal runner.
 *
 * Il runner non conosce il gioco: memoria, chip custom, CIA e video sono
 * quelli dell'A500. Cio' che e' del gioco arriva da g_game_spec.
 */
#pragma once
#include <stdint.h>

#define AMIGA_CICLI_RIGA    454u                 /* 68000 a 7,09 MHz, riga PAL */
#define AMIGA_RIGHE_QUADRO  313u
#define AMIGA_CICLI_QUADRO  (AMIGA_CICLI_RIGA * AMIGA_RIGHE_QUADRO)
#define AMIGA_LARGHEZZA     320
#define AMIGA_ALTEZZA       256

extern uint8_t *g_amiga_mem;          /* immagine della chip RAM (e oltre) */
extern uint32_t g_amiga_mem_size;

/* registri e periferiche */
uint8_t  amiga_hw_read8(uint32_t addr);
uint16_t amiga_hw_read16(uint32_t addr);
void     amiga_hw_write8(uint32_t addr, uint8_t val);
void     amiga_hw_write16(uint32_t addr, uint16_t val);

/* interrupt in attesa e abilitati: livello 1-7, 0 = nessuno */
int      amiga_hw_livello_interrupt(void);

/* fine quadro: copper + bitplane nel framebuffer, tastiera, VBlank */
void     amiga_hw_fine_quadro(void);
const uint32_t *amiga_hw_framebuffer(void);

/* ingressi dall'host */
void     amiga_hw_tasto(uint8_t codice_raw, int rilasciato);
void     amiga_hw_joystick(int su, int giu, int sx, int dx, int fuoco);
void     amiga_hw_mouse(int dx, int dy, int sinistro);
