/* rockstar_mods.h - trucchi di Rock Star nel menu Mods del launcher. */
#pragma once

struct RecompLauncherCModProvider;

void rockstar_mods_carica(void);     /* legge mods.ini */
void rockstar_mods_quadro(void);     /* applica i trucchi attivi: a ogni quadro */
const struct RecompLauncherCModProvider *rockstar_mods_fornitore(const struct RecompLauncherCModProvider *base);
