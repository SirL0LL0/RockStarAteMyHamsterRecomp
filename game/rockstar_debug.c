/* rockstar_debug.c - cosa osserva la modalita' debug in Rock Star Ate My
 * Hamster: le variabili della partita e i messaggi composti.
 *
 * Messaggi: il compositore (processa_e_visualizza_testo_formattato, $D638)
 * chiama l'aggancio "ingresso" a $D63A con il numero del messaggio in D4
 * (ritorno $D640); poi il filtro dell'accordo ($D586) risolve i marcatori
 * {..|..} e la stampa ($D48E, ritorno $D73A) trova il testo definitivo nel
 * buffer $122C8, chiuso da $FF. Il carattere ` del font del gioco e' la sterlina.
 */
#include <stdio.h>

#include "amiga_debug.h"
#include "genesis_runtime.h"

#define BUFFER_TESTO 0x122C8u

static const debug_var_t s_var[] = {
    { 0x123CA, DV_CIFRE8, "soldi (sterline)" },
    { 0x128BD, DV_U8,     "saldo negativo" },
    { 0x128CE, DV_U8,     "qualita' esibizione band" },
    { 0x128CD, DV_U8,     "pubblico band" },
    { 0x0BB8D, DV_U8,     "trucco: tasti giusti (7=on)" },
    { 0x0BB64, DV_U8,     "pausa (spazio premuto)" },
    { 0x12866, DV_HEX8,   "ultimo tasto (ASCII)" },
    { 0x1285C, DV_U8,     "lunghezza testo / valore" },
};

static int s_numero = -1;

static void inizio_messaggio(uint32_t ritorno) {
    (void)ritorno;
    s_numero = (int)(g_cpu.D[4] & 0xFFFF);
}

static void fine_messaggio(uint32_t ritorno) {
    (void)ritorno;
    char t[256];
    int n = 0;
    for (uint32_t a = BUFFER_TESTO; n < (int)sizeof t - 1 && a < BUFFER_TESTO + 320; a++) {
        uint8_t c = m68k_read8(a);
        if (c == 0xFF) break;
        if (c == '`' && n < (int)sizeof t - 3) { t[n++] = (char)0xC2; t[n++] = (char)0xA3; }  /* sterlina */
        else if (c >= 32 && c < 127) t[n++] = (char)c;
        else if (c == 0x1E || c == 0x1F) t[n++] = c == 0x1E ? '<' : '>';    /* segni attorno ai nomi */
        else t[n++] = '|';
    }
    t[n] = 0;
    amiga_debug_messaggio(s_numero, t);
}

static const debug_aggancio_t s_agganci[] = {
    { 0x00D640, inizio_messaggio },
    { 0x00D73A, fine_messaggio },
};

const debug_gioco_t g_debug_gioco = {
    s_var, (int)(sizeof s_var / sizeof s_var[0]),
    s_agganci, (int)(sizeof s_agganci / sizeof s_agganci[0]),
    "rockstar_annotations.csv",
};
