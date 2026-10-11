/* rockstar_spec.c - cio' che il runner Amiga deve sapere di Rock Star Ate My
 * Hamster. Il resto (ingresso, vettori) sta nell'immagine. */
#include "game_spec.h"
#include "rockstar_mods.h"

static void a_ogni_quadro(uint64_t quadro) {
    (void)quadro;
    rockstar_mods_quadro();
}

static void dopo_avvio(void) { rockstar_mods_carica(); }

const GameSpec g_game_spec = {
    .display_name  = "Rock Star Ate My Hamster",
    .short_name    = "RockStar",
    .mods          = rockstar_mods_fornitore,
    .on_post_reset = dopo_avvio,
    .on_frame_post = a_ogni_quadro,
};
