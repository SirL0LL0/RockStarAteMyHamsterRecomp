/* rockstar_menu.h - salvataggi e trucchi nel menu in gioco. */
#pragma once
#include <stdint.h>

void rockstar_menu_registra(void);              /* all'avvio */
void rockstar_menu_quadro(uint64_t quadro);     /* a ogni quadro: partita del gioco su file */
void rockstar_menu_principale(uint32_t ritorno); /* aggancio: chiamata al menu principale */
