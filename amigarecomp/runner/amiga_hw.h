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
extern uint64_t g_amiga_letture_vhpos;

/* velocita' della CPU rispetto al 68000 a 7,09 MHz (1 = A500, 12 = A4000/040):
 * il C generato conta cicli 68000, e in un quadro la CPU ne fa
 * AMIGA_CICLI_QUADRO * g_amiga_cpu_x (g_vblank_threshold); pennello, audio e
 * tempo dei chip custom restano quelli veri (cicli / g_amiga_cpu_x) */
extern uint32_t g_amiga_cpu_x;

void     amiga_hw_init(void);
int      amiga_hw_audio(int16_t **campioni);   /* campioni stereo a 48 kHz del quadro, poi azzera */

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
void     amiga_hw_mouse(int dx, int dy, int sinistro, int destro);   /* porta 0 */
