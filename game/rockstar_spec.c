/* rockstar_spec.c - cio' che il runner Amiga deve sapere di Rock Star Ate My
 * Hamster. Il resto (ingresso, vettori) sta nell'immagine. */
#include "game_spec.h"
#include "genesis_runtime.h"
#include "rockstar_mods.h"
#include "rockstar_menu.h"

static void a_ogni_quadro(uint64_t quadro) {
    rockstar_mods_quadro();
    rockstar_menu_quadro(quadro);
}

static void dopo_avvio(void) {
    rockstar_mods_carica();
    rockstar_menu_registra();
}

/* Codice automodificante del player musicale. f_133c6 avanza la riga quando
 * il contatore $13CEE vale "cmpi.l #6,$13cee" ($133CC), ma l'effetto F della
 * canzone (e $13AAA all'avvio) riscrive la velocita' nell'immediato con
 * "move.b d0,$133d1". Il C generato ha congelato il 6: la musica a velocita'
 * 4 andava 1,5 volte piu' lenta. Prima del bne a $133D6 rifacciamo il
 * confronto con l'immediato com'e' in memoria (game.toml, game_hook). */
static int prima_istruzione(uint32_t pc) {
    if (pc == 0x0133D6u) {
        uint32_t velocita = m68k_read32(0x0133CEu);
        if (m68k_read32(0x013CEEu) == velocita) g_cpu.SR |= 1u << 2;
        else g_cpu.SR &= ~(1u << 2);
    }
    return 0;
}

const GameSpec g_game_spec = {
    .display_name     = "Rock Star Ate My Hamster",
    .short_name       = "RockStar",
    .mods             = rockstar_mods_fornitore,
    .on_post_reset    = dopo_avvio,
    .on_frame_post    = a_ogni_quadro,
    .instruction_hook = prima_istruzione,
};
