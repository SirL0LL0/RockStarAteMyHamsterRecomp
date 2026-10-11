/*
 * rom_parser.c - immagine Amiga per il frontend m68k-recomp-core.
 *
 * Sull'Amiga non c'e' cartuccia: il codice gira in chip RAM. Il frontend pero'
 * ragiona su un'"immagine" con la tabella dei vettori 68000 a $000000, quindi
 * l'immagine che si passa al ricompilatore e' una fotografia della memoria
 * (chip RAM e oltre) presa quando il gioco sta per partire, con in testa i
 * vettori che il gioco installera': $0 SSP, $4 ingresso, $64-$7C autovettori
 * degli interrupt, $80-$BC trap. La prepara lo strumento del gioco
 * (game/prepara_immagine.py); il motore non sa nulla del gioco.
 *
 * Restiamo compatibili con l'interfaccia GenesisRom del frontend: i campi di
 * intestazione Genesis (checksum, nomi, regione) non hanno senso qui e
 * restano vuoti.
 */
#include "rom_parser.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#define AMIGA_IMAGE_MAX 0x01000000u     /* tutto lo spazio a 24 bit */

bool rom_parse(const char *path, GenesisRom *out) {
    memset(out, 0, sizeof(*out));
    FILE *f = fopen(path, "rb");
    if (!f) { fprintf(stderr, "[AmigaRecomp] non riesco ad aprire %s\n", path); return false; }
    fseek(f, 0, SEEK_END);
    long size = ftell(f);
    fseek(f, 0, SEEK_SET);
    if (size < 0x400 || (unsigned long)size > AMIGA_IMAGE_MAX) {
        fprintf(stderr, "[AmigaRecomp] dimensione dell'immagine non valida: %ld\n", size);
        fclose(f);
        return false;
    }
    out->rom_data = (uint8_t *)malloc((size_t)size);
    if (!out->rom_data || fread(out->rom_data, 1, (size_t)size, f) != (size_t)size) {
        fprintf(stderr, "[AmigaRecomp] lettura di %s fallita\n", path);
        fclose(f);
        free(out->rom_data);
        out->rom_data = NULL;
        return false;
    }
    fclose(f);
    out->rom_size = (uint32_t)size;
    out->initial_sp = rom_read32(out, 0);
    out->initial_pc = rom_read32(out, 4);
    snprintf(out->domestic_name, sizeof out->domestic_name, "AMIGA CHIP RAM IMAGE");
    snprintf(out->overseas_name, sizeof out->overseas_name, "AMIGA CHIP RAM IMAGE");
    if (out->initial_pc == 0 || out->initial_pc >= out->rom_size) {
        fprintf(stderr, "[AmigaRecomp] il vettore di ingresso ($4) non punta nell'immagine\n");
        return false;
    }
    return true;
}

void rom_free(GenesisRom *rom) {
    free(rom->rom_data);
    rom->rom_data = NULL;
    rom->rom_size = 0;
}

uint8_t rom_read8(const GenesisRom *rom, uint32_t addr) {
    if (rom->read8_override) return rom->read8_override(addr, rom->read8_user);
    addr &= 0xFFFFFFu;
    return addr < rom->rom_size ? rom->rom_data[addr] : 0xFF;
}

uint16_t rom_read16(const GenesisRom *rom, uint32_t addr) {
    return (uint16_t)(rom_read8(rom, addr) << 8 | rom_read8(rom, addr + 1));
}

uint32_t rom_read32(const GenesisRom *rom, uint32_t addr) {
    return (uint32_t)rom_read16(rom, addr) << 16 | rom_read16(rom, addr + 2);
}
