/* amiga_glue.c - l'ABI che il C generato da m68k-recomp-core si aspetta,
 * implementata per l'Amiga, e il ciclo principale del runner.
 *
 * Modello del tempo: il codice generato somma i cicli 68000 a
 * g_cycle_accumulator e chiama glue_check_vblank() quando superano
 * g_vblank_threshold (un quadro PAL). Li' finisce il quadro: copper e
 * bitplane, presentazione SDL, ingressi, 50 Hz; poi si consegnano gli
 * interrupt abilitati con lo stack frame del 68000. L'RTE del gestore toglie
 * SR e PC e mette g_rte_pending: lo consumiamo noi, che siamo il chiamante.
 *
 * Uso: <gioco>.exe [immagine.bin]
 *   AMIGA_QUADRI=n        senza finestra: n quadri, poi salva quadro.bmp ed esce
 *   AMIGA_INGRESSI=...    eventi finti per i test: "f:300" fuoco al quadro 300,
 *                         "k44:500" tasto raw $44 al quadro 500
 */
#define SDL_MAIN_HANDLED
#include <SDL.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include "genesis_runtime.h"
#include "game_spec.h"
#include "amiga_hw.h"
#include "amiga_debug.h"
#include "amiga_paula.h"
#include "amiga_video_gl.h"
#include "amiga_ingressi.h"
#include "amiga_disco.h"
#include "amiga_lingue.h"
#include "amiga_esporta.h"
#include "amiga_menu.h"

#if defined(RECOMP_LAUNCHER)
#include "recomp_launcher.h"
#include "launcher_profile.h"
#endif

M68KState g_cpu;
uint64_t  g_native_insn_count;
uint32_t  g_cycle_accumulator;
uint32_t  g_vblank_threshold = AMIGA_CICLI_QUADRO;
uint32_t  g_amiga_cpu_x = 1;

#define CPU_A4000 12u                        /* 68040 a 25 MHz contro 68000 a 7,09 */

/* la CPU scelta: 0 A500, 1 A4000. Si puo' cambiare anche a gioco avviato:
 * la posizione nel quadro resta la stessa */
static void imposta_cpu(int a4000) {
    uint32_t x = a4000 ? CPU_A4000 : 1u;
    g_cycle_accumulator = g_cycle_accumulator / g_amiga_cpu_x * x;
    g_amiga_cpu_x = x;
    g_vblank_threshold = AMIGA_CICLI_QUADRO * x;
}
uint32_t  g_audio_cycle_counter;
static int s_rte_pending;
int *g_rte_pending_ptr = &s_rte_pending;

static uint64_t s_quadri;
static long s_quadri_max;
static int s_senza_finestra;
static char s_ingressi_test[1024];
static SDL_Window *s_win;
static SDL_Renderer *s_ren;
static SDL_Texture *s_tex;
static uint64_t s_prossimo_quadro;   /* contatore ad alta risoluzione */
double g_amiga_fps;                  /* quadri al secondo misurati (debug) */
static int s_scala = 3;
static SDL_AudioDeviceID s_audio;
static FILE *s_wav;                  /* AMIGA_WAV=file: registra l'audio (test) */
static uint32_t s_wav_byte;

static void scarica_audio(void) {
    int16_t *c;
    int n = amiga_hw_audio(&c);
    if (s_wav && n) { fwrite(c, 4, (size_t)n, s_wav); s_wav_byte += (uint32_t)n * 4; }
    if (s_audio && n && SDL_GetQueuedAudioSize(s_audio) < 48000u * 4u / 5u)   /* al massimo ~200 ms in coda */
        SDL_QueueAudio(s_audio, c, (Uint32)n * 4);
}

static void chiudi_wav(void) {
    if (!s_wav) return;
    uint32_t h[11] = { 0x46464952, 36 + s_wav_byte, 0x45564157, 0x20746D66, 16, 0x00020001,
                       48000, 48000 * 4, 0x00100004, 0x61746164, s_wav_byte };
    fseek(s_wav, 0, SEEK_SET);
    fwrite(h, 4, 11, s_wav);
    fclose(s_wav);
    s_wav = NULL;
}
static int s_sensibilita = 100;      /* movimento del mouse, in percento */

/* impostazioni.ini accanto all'eseguibile: cio' che si sceglie nel launcher
 * (o a mano, senza launcher) e vale anche alla partenza successiva */
typedef struct {
    int scala, schermo_intero, filtro, volume, audio;
    int sensibilita_mouse, cattura_mouse, salta_launcher;
    int crt;                         /* modello di schermo: SCHERMO_* (amiga_video_gl.h) */
    int cpu;                         /* 0 A500 (68000), 1 A4000 (piu' fluido) */
    amiga_associazioni_t ass;        /* tasti e joypad (tasto0..., pad0...) */
    int sorgente;                    /* pagina Controller: 1 tastiera, 2 joypad */
    int lingua;                      /* LINGUA_ITALIANO / LINGUA_INGLESE */
    char disco[512];                 /* il disco scelto (IPF o ADF), "" = nessuno */
} impostazioni_t;

static impostazioni_t s_imp;
static int s_gl;                     /* presentazione OpenGL attiva */

static void leggi_impostazioni(impostazioni_t *s) {
    *s = (impostazioni_t){ 3, 0, 0, 80, 1, 100, 1, 0, 1 };
    amiga_ingressi_default(&s->ass);
    s->sorgente = 1;
    s->cpu = 1;
    FILE *f = fopen("impostazioni.ini", "r");
    if (!f) return;
    char riga[600]; int v, n;
    while (fgets(riga, sizeof riga, f)) {
        char *uguale = strchr(riga, '=');
        if (!uguale) continue;
        *uguale = 0;
        const char *k = riga, *val = uguale + 1;
        if (!strcmp(k, "disco")) {                  /* un percorso: fino a fine riga */
            snprintf(s->disco, sizeof s->disco, "%s", val);
            s->disco[strcspn(s->disco, "\r\n")] = 0;
            continue;
        }
        v = atoi(val);
        if (sscanf(k, "tasto%d", &n) == 1 && n >= 0 && n < AZ_NUMERO) { s->ass.tasto[n] = v; continue; }
        if (sscanf(k, "pad%d", &n) == 1 && n >= 0 && n < AZ_NUMERO) { s->ass.pad[n] = v; continue; }
        if (!strcmp(k, "scala")) s->scala = v;
        else if (!strcmp(k, "schermo_intero")) s->schermo_intero = v;
        else if (!strcmp(k, "filtro")) s->filtro = v;
        else if (!strcmp(k, "volume")) s->volume = v;
        else if (!strcmp(k, "audio")) s->audio = v;
        else if (!strcmp(k, "sensibilita_mouse")) s->sensibilita_mouse = v;
        else if (!strcmp(k, "cattura_mouse")) s->cattura_mouse = v;
        else if (!strcmp(k, "salta_launcher")) s->salta_launcher = v;
        else if (!strcmp(k, "crt")) s->crt = v >= 0 && v < AMIGA_SCHERMI ? v : 0;
        else if (!strcmp(k, "cpu")) s->cpu = v ? 1 : 0;
        else if (!strcmp(k, "sorgente")) s->sorgente = v == 2 ? 2 : 1;
        else if (!strcmp(k, "lingua")) s->lingua = v == LINGUA_INGLESE ? LINGUA_INGLESE : LINGUA_ITALIANO;
    }
    fclose(f);
    if (s->scala < 1) s->scala = 1;
    if (s->sensibilita_mouse < 25 || s->sensibilita_mouse > 400) s->sensibilita_mouse = 100;
}

static void scrivi_impostazioni(const impostazioni_t *s) {
    FILE *f = fopen("impostazioni.ini", "w");
    if (!f) return;
    fprintf(f, "scala=%d\nschermo_intero=%d\nfiltro=%d\nvolume=%d\naudio=%d\n"
               "sensibilita_mouse=%d\ncattura_mouse=%d\nsalta_launcher=%d\ncrt=%d\n",
            s->scala, s->schermo_intero, s->filtro, s->volume, s->audio,
            s->sensibilita_mouse, s->cattura_mouse, s->salta_launcher, s->crt);
    fprintf(f, "cpu=%d\nsorgente=%d\nlingua=%d\ndisco=%s\n", s->cpu, s->sorgente, s->lingua, s->disco);
    for (int i = 0; i < AZ_NUMERO; i++)
        fprintf(f, "tasto%d=%d\npad%d=%d\n", i, s->ass.tasto[i], i, s->ass.pad[i]);
    fclose(f);
}

/* ------------------------------------------------------------ memoria */

uint8_t m68k_read8(uint32_t a) {
    a &= 0xFFFFFFu;
    return a < g_amiga_mem_size ? g_amiga_mem[a] : amiga_hw_read8(a);
}
uint16_t m68k_read16(uint32_t a) {
    a &= 0xFFFFFFu;
    if (a + 1 < g_amiga_mem_size) return (uint16_t)(g_amiga_mem[a] << 8 | g_amiga_mem[a + 1]);
    return amiga_hw_read16(a);
}
uint32_t m68k_read32(uint32_t a) {
    return (uint32_t)m68k_read16(a) << 16 | m68k_read16(a + 2);
}
void m68k_write8(uint32_t a, uint8_t v) {
    a &= 0xFFFFFFu;
    if (a < g_amiga_mem_size) {
        if (amiga_debug_osservato(a)) amiga_debug_scrittura(a, 1, g_amiga_mem[a], v);
        g_amiga_mem[a] = v;
    } else amiga_hw_write8(a, v);
}
void m68k_write16(uint32_t a, uint16_t v) {
    a &= 0xFFFFFFu;
    if (a + 1 < g_amiga_mem_size) {
        if (amiga_debug_osservato(a) || amiga_debug_osservato(a + 1))
            amiga_debug_scrittura(a, 2, (uint32_t)(g_amiga_mem[a] << 8 | g_amiga_mem[a + 1]), v);
        g_amiga_mem[a] = (uint8_t)(v >> 8); g_amiga_mem[a + 1] = (uint8_t)v;
    }
    else amiga_hw_write16(a, v);
}
void m68k_write32(uint32_t a, uint32_t v) {
    m68k_write16(a, (uint16_t)(v >> 16));
    m68k_write16(a + 2, (uint16_t)v);
}

/* ------------------------------------------------------------ pila e salti */

/* profilo campionato (AMIGA_PROFILO_DA=quadro): conta gli indirizzi di ritorno
 * delle chiamate, cioe' chi chiama cosa, e li stampa alla fine del test */
static uint32_t *s_profilo;
static uint64_t s_profilo_da = ~0ull;
/* dove si trova il codice generato a ogni fine quadro (diagnostica) */
static void *s_dove[4096];
static int s_n_dove;

/* traccia (AMIGA_TRACCIA=indirizzo di ritorno esadecimale): registri a ogni
 * chiamata che tornera' li', nel file traccia.txt */
static uint32_t s_traccia_rit = 0xFFFFFFFFu;
static FILE *s_traccia;
static int s_traccia_tutte;
static uint64_t s_traccia_da, s_traccia_a;

void recomp_push_return(uint32_t ret_addr) {
    amiga_debug_chiamata(ret_addr & 0xFFFFFFu, g_cpu.A[7]);
    /* AMIGA_TRACCIA=tutte:DA:A  ogni chiamata fra i quadri DA e A */
    if (s_traccia_tutte && s_traccia && s_quadri >= s_traccia_da && s_quadri <= s_traccia_a)
        fprintf(s_traccia, "q%llu rit=%06X A7=%06X\n", (unsigned long long)s_quadri,
                ret_addr & 0xFFFFFFu, g_cpu.A[7]);
    if ((ret_addr & 0xFFFFFFu) == s_traccia_rit && s_traccia)
        fprintf(s_traccia, "q%llu D0=%08X D4=%08X D5=%08X D6=%08X A0=%06X A3=%06X A7=%06X\n",
                (unsigned long long)s_quadri, g_cpu.D[0], g_cpu.D[4], g_cpu.D[5], g_cpu.D[6],
                g_cpu.A[0], g_cpu.A[3], g_cpu.A[7]);
    if (s_profilo && s_quadri >= s_profilo_da && (ret_addr & 0xFFFFFFu) < 0x100000u)
        s_profilo[(ret_addr & 0xFFFFFu) >> 1]++;
    g_cpu.A[7] -= 4;
    m68k_write32(g_cpu.A[7], ret_addr & 0xFFFFFFu);
}

uint32_t recomp_resolve_ram_trampoline(uint32_t addr) { return addr & 0xFFFFFFu; }

/* Sull'Amiga tutto il codice sta in RAM ed e' stato tradotto: un salto a
 * codice non tradotto e' un errore di scoperta, non un caso da interpretare. */
int recomp_dispatch_ram_stub(uint32_t addr) { (void)addr; return 0; }

/* siti game_hook di game.toml: il C generato chiama questa prima dell'istruzione */
int genesis_game_instruction_hook(uint32_t pc) {
    return g_game_spec.instruction_hook ? g_game_spec.instruction_hook(pc) : 0;
}

void genesis_log_dispatch_miss(uint32_t addr) {
    FILE *f = fopen("dispatch_misses.toml", "w");
    if (f) {
        fprintf(f, "# salto a codice non tradotto (quadro %llu)\n[functions]\nextra = [0x%06X]\n",
                (unsigned long long)s_quadri, addr & 0xFFFFFFu);
        fclose(f);
    }
    fprintf(stderr, "[DISPATCH MISS] $%06X al quadro %llu: vedi dispatch_misses.toml\n",
            addr & 0xFFFFFFu, (unsigned long long)s_quadri);
    exit(2);
}

/* ------------------------------------------------------------ eccezioni */

static void eccezione(uint32_t vettore, int livello) {
    m68k_write32(g_cpu.A[7] -= 4, g_cpu.PC);
    m68k_write16(g_cpu.A[7] -= 2, g_cpu.SR);
    g_cpu.SR |= SR_S;
    if (livello > 0) g_cpu.SR = (uint16_t)((g_cpu.SR & ~0x0700u) | ((unsigned)livello << 8));
    call_by_address(m68k_read32(vettore));
    s_rte_pending = 0;               /* l'RTE del gestore torna qui */
}

void m68k_trap_vector(uint8_t vec) { eccezione((uint32_t)vec * 4u, 0); }

uint64_t g_amiga_irq[8];             /* interrupt consegnati per livello (debug) */

static void consegna_interrupt(void) {
    /* come il 68000: finito un gestore (RTE), se c'e' ancora un livello
     * pendente sopra la maschera parte subito. Consegnarne uno solo per volta
     * faceva morire di fame la tastiera (livello 2): il VBlank (livello 3)
     * arrivava insieme a lei a ogni quadro, vinceva sempre e non azzera il
     * bit PORTS. Il limite evita cicli se un gestore non pulisce INTREQ. */
    for (int giri = 0; giri < 8; giri++) {
        int l = amiga_hw_livello_interrupt();
        if (l <= (int)((g_cpu.SR >> 8) & 7)) break;
        g_amiga_irq[l]++;
        eccezione(0x60u + (uint32_t)l * 4u, l);
    }
}

/* ------------------------------------------------------------ quadro */

static int codice_amiga(SDL_Keycode k) {
    static const char r1[] = "1234567890", rq[] = "qwertyuiop", ra[] = "asdfghjkl", rz[] = "zxcvbnm";
    const char *p;
    if (k < 128 && k > 0) {
        if ((p = strchr(r1, (int)k)) != NULL) return 0x01 + (int)(p - r1);
        if ((p = strchr(rq, (int)k)) != NULL) return 0x10 + (int)(p - rq);
        if ((p = strchr(ra, (int)k)) != NULL) return 0x20 + (int)(p - ra);
        if ((p = strchr(rz, (int)k)) != NULL) return 0x31 + (int)(p - rz);
    }
    switch (k) {
    case SDLK_SPACE: return 0x40; case SDLK_BACKSPACE: return 0x41; case SDLK_RETURN: return 0x44;
    case SDLK_ESCAPE: return 0x45; case SDLK_DELETE: return 0x46;
    case SDLK_F1: return 0x50; case SDLK_F2: return 0x51; case SDLK_F3: return 0x52;
    case SDLK_F4: return 0x53; case SDLK_F5: return 0x54; case SDLK_F6: return 0x55;
    case SDLK_F7: return 0x56; case SDLK_F8: return 0x57; case SDLK_F9: return 0x58; case SDLK_F10: return 0x59;
    }
    return -1;
}

static void ingressi_sdl(void) {
    static int mouse_sx, mouse_dx, resto_x, resto_y;
    /* un clic deve durare almeno qualche quadro: se pressione e rilascio
     * arrivano fra due letture, il gioco vedrebbe solo il tasto su */
    static int tieni_sx, tieni_dx;
    int mdx = 0, mdy = 0;
    SDL_Event ev;
    while (SDL_PollEvent(&ev)) {
        if (ev.type == SDL_QUIT) exit(0);
        if (amiga_debug_evento(&ev)) continue;              /* F11, finestra di debug */
        if (ev.type == SDL_WINDOWEVENT && ev.window.event == SDL_WINDOWEVENT_CLOSE) exit(0);
        /* F1 o Start/Guide del joypad: menu in gioco */
        if ((ev.type == SDL_KEYDOWN && ev.key.keysym.sym == SDLK_F1 && !ev.key.repeat) ||
            (ev.type == SDL_CONTROLLERBUTTONDOWN && (ev.cbutton.button == SDL_CONTROLLER_BUTTON_START ||
                                                    ev.cbutton.button == SDL_CONTROLLER_BUTTON_GUIDE))) {
            amiga_menu_apri();
            continue;
        }
        /* tasti e joypad associati nel launcher (joystick, clic, Spazio...) */
        if (amiga_ingressi_evento(&ev)) continue;
        if (ev.type == SDL_KEYDOWN || ev.type == SDL_KEYUP) {
            /* gli altri tasti vanno alla tastiera Amiga */
            if (!ev.key.repeat) {
                int c = codice_amiga(ev.key.keysym.sym);
                if (c >= 0) amiga_hw_tasto((uint8_t)c, ev.type == SDL_KEYUP);
            }
        }
        if (ev.type == SDL_MOUSEBUTTONDOWN || ev.type == SDL_MOUSEBUTTONUP) {
            /* mouse libero: il clic che lo riprende serve solo a catturarlo e non
             * arriva al gioco (ne' la pressione ne' il rilascio), altrimenti
             * sceglierebbe l'opzione sotto il puntatore */
            static uint8_t ingoiato[8];
            int giu_ = ev.type == SDL_MOUSEBUTTONDOWN, b = ev.button.button & 7;
            if (ev.button.button == SDL_BUTTON_MIDDLE) {   /* centrale: sgancia / riaggancia */
                if (giu_) SDL_SetRelativeMouseMode(SDL_GetRelativeMouseMode() ? SDL_FALSE : SDL_TRUE);
                continue;
            }
            if (giu_ && !SDL_GetRelativeMouseMode()) {
                SDL_SetRelativeMouseMode(SDL_TRUE);
                ingoiato[b] = 1;
                continue;
            }
            if (!giu_ && ingoiato[b]) { ingoiato[b] = 0; continue; }
            if (ev.button.button == SDL_BUTTON_LEFT) { mouse_sx = giu_; if (giu_) tieni_sx = 4; }
            if (ev.button.button == SDL_BUTTON_RIGHT) { mouse_dx = giu_; if (giu_) tieni_dx = 4; }
        }
        if (ev.type == SDL_WINDOWEVENT && ev.window.event == SDL_WINDOWEVENT_FOCUS_LOST) {
            SDL_SetRelativeMouseMode(SDL_FALSE);            /* Alt+Tab: il mouse torna a Windows */
            mouse_sx = mouse_dx = 0;                        /* niente tasti rimasti giu' */
        }
        /* mouse catturato: il movimento in pixel della finestra diventa movimento
         * in pixel Amiga (diviso per la scala), il resto si porta avanti */
        if (ev.type == SDL_MOUSEMOTION && SDL_GetRelativeMouseMode()) {
            int div = s_scala * 100;                  /* sensibilita' in percento */
            resto_x += ev.motion.xrel * s_sensibilita; resto_y += ev.motion.yrel * s_sensibilita;
            mdx += resto_x / div; resto_x %= div;
            mdy += resto_y / div; resto_y %= div;
        }
        if (ev.type == SDL_KEYDOWN && ev.key.keysym.sym == SDLK_F12 && !ev.key.repeat) {
            if (ev.key.keysym.mod & KMOD_SHIFT) {          /* Shift+F12: il modello di schermo dopo */
                if (s_gl) {
                    s_imp.crt = (amiga_video_gl_modo_attuale() + 1) % AMIGA_SCHERMI;
                    amiga_video_gl_modo(s_imp.crt);
                    scrivi_impostazioni(&s_imp);
                }
            } else SDL_SetRelativeMouseMode(SDL_FALSE);   /* F12 libera il mouse */
        }
    }
    amiga_stato_ingressi_t st;
    amiga_ingressi_quadro(&st, s_sensibilita);
    amiga_hw_joystick(st.su, st.giu, st.sx, st.dx, st.fuoco);
    amiga_hw_mouse(mdx + st.mdx, mdy + st.mdy, mouse_sx || tieni_sx > 0 || st.mouse_sx,
                   mouse_dx || tieni_dx > 0 || st.mouse_dx);
    if (tieni_sx > 0) tieni_sx--;
    if (tieni_dx > 0) tieni_dx--;
}

static void ingressi_test(void) {
    const char *p = s_ingressi_test;
    int fuoco = 0, sinistro = 0;
    long q = (long)s_quadri;
    while (*p) {
        char tipo = *p++;
        int codice = 0;
        if (tipo == 'k') codice = (int)strtol(p, (char **)&p, 16);
        long quando = 0;
        if (*p == ':') quando = strtol(p + 1, (char **)&p, 10);
        if (tipo == 'f' && q >= quando && q < quando + 5) fuoco = 1;
        if (tipo == 'm' && q >= quando && q < quando + 5) sinistro = 1;   /* clic sinistro */
        if (tipo == 'k' && q == quando) amiga_hw_tasto((uint8_t)codice, 0);
        if (tipo == 'k' && q == quando + 3) amiga_hw_tasto((uint8_t)codice, 1);
        while (*p == ',') p++;
    }
    amiga_hw_joystick(0, 0, 0, 0, fuoco);
    amiga_hw_mouse(0, 0, sinistro, 0);
}

static void ciclo_menu(void);

static void salva_bmp(const char *nome) {
    SDL_Surface *s = SDL_CreateRGBSurfaceWithFormatFrom((void *)amiga_hw_framebuffer(), AMIGA_LARGHEZZA,
                                                        AMIGA_ALTEZZA, 32, AMIGA_LARGHEZZA * 4,
                                                        SDL_PIXELFORMAT_ARGB8888);
    SDL_SaveBMP(s, nome);
    SDL_FreeSurface(s);
}

static void fine_quadro(void) {
    s_quadri++;
    if (g_game_spec.on_frame_post) g_game_spec.on_frame_post(s_quadri);
    amiga_debug_quadro(s_quadri);
    amiga_hw_fine_quadro();
    scarica_audio();
    if (s_senza_finestra) {
        ingressi_test();
        if ((long)s_quadri >= s_quadri_max) {
            chiudi_wav();
            salva_bmp("quadro.bmp");
            FILE *m = fopen("memoria_fine.bin", "wb");     /* stato per confronti */
            if (m) { fwrite(g_amiga_mem, 1, g_amiga_mem_size, m); fclose(m); }
            printf("quadri %llu, salvati quadro.bmp e memoria_fine.bin\n", (unsigned long long)s_quadri);
            printf("interrupt consegnati: liv2 %llu  liv3 %llu  liv4 %llu\n", (unsigned long long)g_amiga_irq[2], (unsigned long long)g_amiga_irq[3], (unsigned long long)g_amiga_irq[4]);
            printf("INTENA %04X  INTREQ %04X  SR %04X\n", m68k_read16(0xDFF01C), m68k_read16(0xDFF01E), g_cpu.SR);
            printf("istruzioni %llu, letture VHPOSR %llu\n", (unsigned long long)g_native_insn_count,
                   (unsigned long long)g_amiga_letture_vhpos);
            if (s_profilo) {
                FILE *fd = fopen("dove.txt", "w");
                if (fd) {
                    for (int i = 0; i < s_n_dove; i++) fprintf(fd, "%lld\n", (long long)((char *)s_dove[i] - (char *)(void *)recomp_push_return));
                    fclose(fd);
                }
                for (int k = 0; k < 15; k++) {
                    uint32_t mi = 0, mv = 0;
                    for (uint32_t i = 0; i < 0x80000u; i++) if (s_profilo[i] > mv) { mv = s_profilo[i]; mi = i; }
                    if (!mv) break;
                    printf("  ritorno $%06X  %u chiamate\n", mi << 1, mv);
                    s_profilo[mi] = 0;
                }
            }
            exit(0);
        }
        return;
    }
    if (s_gl) amiga_video_gl_presenta(amiga_hw_framebuffer());
    else {
    SDL_UpdateTexture(s_tex, NULL, amiga_hw_framebuffer(), AMIGA_LARGHEZZA * 4);
    SDL_RenderClear(s_ren);
    SDL_RenderCopy(s_ren, s_tex, NULL, NULL);
    SDL_RenderPresent(s_ren);
    }
    ingressi_sdl();
    if (amiga_menu_aperto()) ciclo_menu();
    /* 50 Hz PAL veri (un quadro = 142.102 cicli a 7,09 MHz = 20,03 ms), con un
     * passo fisso che non si azzera: niente vsync, che a 60 Hz sommato alla
     * pausa faceva durare molti quadri 33 ms e rallentava gioco e musica */
    uint64_t freq = SDL_GetPerformanceFrequency();
    uint64_t periodo = freq * AMIGA_CICLI_QUADRO / 7093790u;
    uint64_t ora = SDL_GetPerformanceCounter();
    if (!s_prossimo_quadro || ora > s_prossimo_quadro + 5 * periodo) s_prossimo_quadro = ora;  /* ripartenza */
    s_prossimo_quadro += periodo;
    if (s_prossimo_quadro > ora) {
        uint64_t ms = (s_prossimo_quadro - ora) * 1000 / freq;
        if (ms > 1) SDL_Delay((Uint32)(ms - 1));
        while (SDL_GetPerformanceCounter() < s_prossimo_quadro) { }   /* l'ultimo millisecondo */
    }
    static uint64_t t0; static int n;
    if (!t0) t0 = ora;
    if (++n == 50) { g_amiga_fps = 50.0 * (double)freq / (double)(ora - t0); t0 = ora; n = 0; }
}

/* ------------------------------------------------------------ menu in gioco */

static void v_schermo(char *b, size_t n) {
    snprintf(b, n, "Schermo: %s  < >", amiga_video_gl_nome(s_imp.crt));
}
static void a_schermo(int verso) {
    s_imp.crt = (s_imp.crt + (verso < 0 ? AMIGA_SCHERMI - 1 : 1)) % AMIGA_SCHERMI;
    amiga_video_gl_modo(s_imp.crt);
    scrivi_impostazioni(&s_imp);
}
static int ok_schermo(void) { return s_gl; }
static void v_intero(char *b, size_t n) { snprintf(b, n, "Schermo intero: %s", s_imp.schermo_intero ? "si'" : "no"); }
static void a_intero(int verso) {
    (void)verso;
    s_imp.schermo_intero = !s_imp.schermo_intero;
    SDL_SetWindowFullscreen(s_win, s_imp.schermo_intero ? SDL_WINDOW_FULLSCREEN_DESKTOP : 0);
    scrivi_impostazioni(&s_imp);
}
static void v_volume(char *b, size_t n) { snprintf(b, n, "Volume: %d%%  < >", s_imp.audio ? s_imp.volume : 0); }
static void a_volume(int verso) {
    if (verso == 0) s_imp.audio = !s_imp.audio;
    else {
        s_imp.audio = 1;
        s_imp.volume += verso * 5;
        if (s_imp.volume < 0) s_imp.volume = 0;
        if (s_imp.volume > 100) s_imp.volume = 100;
    }
    amiga_paula_volume(s_imp.audio ? s_imp.volume : 0);
    scrivi_impostazioni(&s_imp);
}
static void v_cpu(char *b, size_t n) { snprintf(b, n, "Amiga: %s", s_imp.cpu ? "A4000 (fluido)" : "A500 (originale)"); }
static void a_cpu(int verso) {
    (void)verso;
    s_imp.cpu = !s_imp.cpu;
    imposta_cpu(s_imp.cpu);
    scrivi_impostazioni(&s_imp);
}
static void v_riprendi(char *b, size_t n) { snprintf(b, n, "Torna al gioco"); }
static void a_riprendi(int verso) { (void)verso; amiga_menu_chiudi(); }
static void v_esci(char *b, size_t n) { snprintf(b, n, "Esci"); }
static void a_esci(int verso) { if (verso == 0) exit(0); }

static const amiga_voce_menu_t s_voci_runner[] = {
    { v_schermo, a_schermo, ok_schermo },
    { v_intero, a_intero, NULL },
    { v_volume, a_volume, NULL },
    { v_cpu, a_cpu, NULL },
    { v_riprendi, a_riprendi, NULL },
    { v_esci, a_esci, NULL },
};

/* il gioco e' fermo dentro fine_quadro finche' il menu e' aperto: si
 * ridisegna l'ultimo quadro con il menu sopra, l'audio si svuota */
static int s_nel_menu;
static void ciclo_menu(void) {
    if (s_nel_menu) return;                     /* un'azione del menu che fa girare il gioco */
    s_nel_menu = 1;
    static uint32_t copia[AMIGA_LARGHEZZA * AMIGA_ALTEZZA];
    while (amiga_menu_aperto()) {
        SDL_Event ev;
        while (SDL_PollEvent(&ev)) {
            if (ev.type == SDL_QUIT) exit(0);
            if (ev.type == SDL_WINDOWEVENT && ev.window.event == SDL_WINDOWEVENT_CLOSE) exit(0);
            amiga_ingressi_evento(&ev);         /* joypad collegati/scollegati */
            amiga_menu_evento(&ev);
        }
        memcpy(copia, amiga_hw_framebuffer(), sizeof copia);
        amiga_menu_disegna(copia, AMIGA_LARGHEZZA, AMIGA_ALTEZZA);
        if (s_gl) amiga_video_gl_presenta(copia);
        else {
            SDL_UpdateTexture(s_tex, NULL, copia, AMIGA_LARGHEZZA * 4);
            SDL_RenderClear(s_ren);
            SDL_RenderCopy(s_ren, s_tex, NULL, NULL);
            SDL_RenderPresent(s_ren);
        }
        SDL_Delay(16);
    }
    s_prossimo_quadro = 0;                      /* il ritmo riparte da adesso */
    s_nel_menu = 0;
}

void glue_check_vblank(void) {
    if (s_profilo && s_quadri >= s_profilo_da && s_n_dove < 4096)
        s_dove[s_n_dove++] = __builtin_return_address(0);
    while (g_cycle_accumulator >= g_vblank_threshold) {
        g_cycle_accumulator -= g_vblank_threshold;
        fine_quadro();
    }
    consegna_interrupt();
}

void glue_yield_for_interrupt_poll(void) {
    if (g_cycle_accumulator >= g_vblank_threshold) glue_check_vblank();
}

/* ------------------------------------------------------------ avvio */

/* il gioco in memoria: dal disco dell'utente (IPF o ADF, nella lingua scelta)
 * oppure da un'immagine gia' pronta (rockstar_chipram*.bin, per lo sviluppo).
 * 1 = fatto; 0 = errore spiegato in err */
static int carica_gioco(const char *file, int lingua, char *err, size_t ne) {
    if (!file[0]) {
        snprintf(err, ne, "Nessun disco scelto: nel launcher, Sfoglia disco (Browse For DISK).\n"
                 "Servono Rock Star Ate My Hamster (Europe).ipf oppure "
                 "Rock Star Ate My Hamster (1989)(Codemasters).adf.");
        return 0;
    }
    FILE *f = fopen(file, "rb");
    if (!f) { snprintf(err, ne, "Non trovo %s.", file); return 0; }
    fseek(f, 0, SEEK_END);
    long n = ftell(f);
    fseek(f, 0, SEEK_SET);
    uint8_t *d = malloc(n > 0 ? (size_t)n : 1);
    int letto = n > 0 && fread(d, 1, (size_t)n, f) == (size_t)n;
    fclose(f);
    if (!letto) { free(d); snprintf(err, ne, "Non riesco a leggere %s.", file); return 0; }
    uint32_t crc = amiga_crc32(d, (size_t)n);
    g_amiga_mem = calloc(1, 0x100000 + 16);
    g_amiga_mem_size = 0x100000;
    if (amiga_disco_tipo(crc)) {
        free(d);
        size_t lb = amiga_lingue_lung_base();
        uint8_t *base = malloc(lb);
        int ok = amiga_disco_base(file, base, lb, amiga_lingue_crc_base(), err, ne) &&
                 amiga_lingue_immagine(base, lingua, g_amiga_mem, 0x100000, err, ne);
        free(base);
        return ok;
    }
    /* il C generato ha dentro costanti prese dall'immagine (indirizzi delle
     * tabelle, operandi patchati): con un'immagine diversa il gioco sbaglierebbe
     * in silenzio, quindi solo quelle di questa versione */
    if (n != 0x100000 || !amiga_lingue_crc_valido(crc)) {
        free(d);
        snprintf(err, ne, "%s non e' un disco supportato ne' un'immagine di questa versione (CRC %08X).\n"
                 "Servono Rock Star Ate My Hamster (Europe).ipf oppure "
                 "Rock Star Ate My Hamster (1989)(Codemasters).adf.", file, crc);
        return 0;
    }
    memcpy(g_amiga_mem, d, 0x100000);
    free(d);
    return 1;
}

/* le versioni Amiga in italiano (ADF e WHDLoad) dal disco scelto, in
 * "Amiga ITA" accanto all'eseguibile; poi apre la cartella */
static int esporta_amiga(const char *disco, char *msg, size_t n) {
    char dove[1024];
    char *qui = SDL_GetBasePath();
    snprintf(dove, sizeof dove, "%sAmiga ITA", qui ? qui : "");
    SDL_free(qui);
    if (!amiga_esporta(disco, dove, msg, n)) return 0;
    char url[1100];
    snprintf(url, sizeof url, "file:///%s", dove);
    for (char *c = url; *c; c++) if (*c == '\\') *c = '/';
    SDL_OpenURL(url);
    return 1;
}

int main(int argc, char **argv) {
    impostazioni_t imp;
    leggi_impostazioni(&imp);
    /* --esporta-amiga [disco [cartella]]: senza finestra, per le prove */
    for (int i = 1; i < argc; i++) {
        if (strcmp(argv[i], "--esporta-amiga")) continue;
        const char *d = i + 1 < argc ? argv[i + 1] : imp.disco;
        const char *c = i + 2 < argc ? argv[i + 2] : "Amiga ITA";
        char m[1200];
        int ok = amiga_esporta(d, c, m, sizeof m);
        printf("%s\n", m);
        return ok ? 0 : 1;
    }
    /* senza disco scelto: l'immagine di sviluppo, se c'e'; altrimenti nessun
     * file (il launcher chiede il disco) */
    FILE *sviluppo = fopen("rockstar_chipram.bin", "rb");
    if (sviluppo) fclose(sviluppo);
    const char *file = argc > 1 && argv[1][0] != '-' ? argv[1]
                     : imp.disco[0] ? imp.disco : sviluppo ? "rockstar_chipram.bin" : "";
    if (getenv("AMIGA_LINGUA")) imp.lingua = !strcmp(getenv("AMIGA_LINGUA"), "en") ? LINGUA_INGLESE : LINGUA_ITALIANO;
    const char *q = getenv("AMIGA_QUADRI");
    if (g_game_spec.on_post_reset) g_game_spec.on_post_reset();   /* preferenze del gioco (mods) */
#if defined(RECOMP_LAUNCHER)
    /* launcher recomp-ui (profilo "amiga"): scelta del file e impostazioni.
     * Saltato nei test senza finestra, con --senza-launcher, o se nel launcher
     * si e' scelto "Skip launcher on boot" (--launcher lo riapre). */
    static char scelto[512];
    int salta = q != NULL || imp.salta_launcher;
    for (int i = 1; i < argc; i++) {
        if (!strcmp(argv[i], "--senza-launcher")) salta = 1;
        if (!strcmp(argv[i], "--launcher")) salta = 0;
    }
    if (!salta) {
        RecompLauncherCSettings io;
        memset(&io, 0, sizeof io);
        io.window_scale = imp.scala; io.fullscreen = imp.schermo_intero;
        io.linear_filter = imp.filtro; io.enable_audio = imp.audio; io.audio_freq = 48000;
        io.volume = imp.volume; io.skip_launcher = imp.salta_launcher;
        io.pointer_sensitivity = imp.sensibilita_mouse; io.pointer_capture = imp.cattura_mouse;
        io.screen_kind = imp.crt;
        /* tasti e joypad: valori attuali e predefiniti (per "Restore defaults") */
        static RecompLauncherCSettings predef;
        amiga_associazioni_t def;
        amiga_ingressi_default(&def);
        io.player_src[0] = imp.sorgente;
        io.host_option[0] = imp.cpu;
        predef = io;
        predef.player_src[0] = 1;
        predef.host_option[0] = 1;                   /* A4000 */
        predef.screen_kind = 0;
        predef.linear_filter = 0;
        for (int i = 0; i < AZ_NUMERO; i++) {
            io.player_key_bind[0][i] = imp.ass.tasto[i];
            io.player_pad_bind[0][i] = imp.ass.pad[i];
            predef.player_key_bind[0][i] = def.tasto[i];
            predef.player_pad_bind[0][i] = def.pad[i];
        }
        RecompLauncherCGameInfo gi;
        memset(&gi, 0, sizeof gi);
        launcher_profile_apply("amiga", &gi);
        gi.default_settings = &predef;
        /* i due dischi supportati, riconosciuti dal CRC del file */
        static const uint32_t dischi[] = { 0x53EC7260u, 0xBB9DD80Bu };
        gi.expected_crc = dischi[0];
        gi.has_expected_crc = 1;
        gi.accepted_crcs = dischi;
        gi.num_accepted_crcs = 2;
        static const char *const lingue[] = { "Italiano", "English" };
        gi.language_labels = lingue;
        gi.num_languages = 2;
        io.language_index = imp.lingua;
        gi.name = g_game_spec.display_name ? g_game_spec.display_name : "Amiga";
        gi.mods = g_game_spec.mods ? g_game_spec.mods(NULL) : NULL;
        gi.tool_label = "Create Italian Amiga disks (ADF + WHDLoad)";
        gi.tool_note = "Builds the Italian floppy (ADF, any Amiga with 1 MB) and the WHDLoad install "
                       "from the selected disk, in the \"Amiga ITA\" folder next to the program.";
        gi.tool_run = esporta_amiga;
        /* il modello di Amiga (vedi imposta_cpu) */
        static const char *const modelli[] = { "A500 (original)", "A4000 (smooth)" };
        static const RecompLauncherCHostOption opzioni[] = { { "Amiga model", modelli, 2 } };
        gi.host_options_title = "AMIGA";
        gi.host_options = opzioni;
        gi.num_host_options = 1;
        /* i testi del launcher nella lingua scelta per il gioco */
        static const char *const codici[] = { "it", "en" };
        gi.ui_languages = codici;
        /* la copertina, quando il disco e' riconosciuto */
        gi.boxart_path = "assets/img/copertina.jpg";
        gi.boxart_only_verified = 1;
        int rc = recomp_launcher_run_window(gi.name, &io, &gi, ".", file, scelto, sizeof scelto);
        if (rc != 0) return 0;
        if (scelto[0]) file = scelto;
        if (file != imp.disco) snprintf(imp.disco, sizeof imp.disco, "%s", file);
        imp.lingua = io.language_index == LINGUA_INGLESE ? LINGUA_INGLESE : LINGUA_ITALIANO;
        imp.scala = io.window_scale > 0 ? io.window_scale : 3;
        imp.schermo_intero = io.fullscreen;
        imp.filtro = io.linear_filter;
        imp.volume = io.volume;
        imp.audio = io.enable_audio;
        imp.salta_launcher = io.skip_launcher;
        imp.sensibilita_mouse = io.pointer_sensitivity > 0 ? io.pointer_sensitivity : 100;
        imp.cattura_mouse = io.pointer_capture;
        imp.crt = io.screen_kind >= 0 && io.screen_kind < AMIGA_SCHERMI ? io.screen_kind : 0;
        imp.cpu = io.host_option[0] ? 1 : 0;
        imp.sorgente = io.player_src[0] == 2 ? 2 : 1;
        for (int i = 0; i < AZ_NUMERO; i++) {
            imp.ass.tasto[i] = io.player_key_bind[0][i];
            imp.ass.pad[i] = io.player_pad_bind[0][i];
        }
        scrivi_impostazioni(&imp);
    }
#endif
    s_imp = imp;
    if (getenv("AMIGA_CPU")) imp.cpu = s_imp.cpu = atoi(getenv("AMIGA_CPU")) ? 1 : 0;   /* per le prove */
    imposta_cpu(imp.cpu);
    int scala = imp.scala, schermo_intero = imp.schermo_intero, lineare = imp.filtro;
    s_sensibilita = imp.sensibilita_mouse;
    {
        char m[700];
        if (!carica_gioco(file, imp.lingua, m, sizeof m)) {
            fprintf(stderr, "%s\n", m);
            if (!q) SDL_ShowSimpleMessageBox(SDL_MESSAGEBOX_ERROR, "Rock Star Ate My Hamster", m, NULL);
            return 1;
        }
    }

    s_senza_finestra = q != NULL;
    s_quadri_max = q ? atol(q) : 0;
    if (getenv("AMIGA_TRACCIA")) {
        const char *t = getenv("AMIGA_TRACCIA");
        if (!strncmp(t, "tutte:", 6)) {
            char *fine;
            s_traccia_tutte = 1;
            s_traccia_da = strtoull(t + 6, &fine, 10);
            s_traccia_a = *fine == ':' ? strtoull(fine + 1, NULL, 10) : s_traccia_da;
        } else
            s_traccia_rit = (uint32_t)strtoul(t, NULL, 16);
        s_traccia = fopen("traccia.txt", "w");
    }
    if (getenv("AMIGA_PROFILO_DA")) {
        s_profilo = calloc(0x80000u, sizeof *s_profilo);
        s_profilo_da = (uint64_t)atoll(getenv("AMIGA_PROFILO_DA"));
    }
    if (getenv("AMIGA_INGRESSI")) snprintf(s_ingressi_test, sizeof s_ingressi_test, "%s", getenv("AMIGA_INGRESSI"));

    SDL_SetHint(SDL_HINT_MOUSE_FOCUS_CLICKTHROUGH, "1");   /* il primo clic arriva al gioco */
    SDL_Init(s_senza_finestra ? 0 : SDL_INIT_VIDEO | SDL_INIT_GAMECONTROLLER | (imp.audio ? SDL_INIT_AUDIO : 0));
    amiga_ingressi_imposta(&imp.ass);
    amiga_menu_registra(1, s_voci_runner, (int)(sizeof s_voci_runner / sizeof s_voci_runner[0]));
    amiga_hw_init();
    amiga_paula_volume(imp.audio ? imp.volume : 0);
    if (!s_senza_finestra && imp.audio) {
        SDL_AudioSpec voglio = { 0 }, ho;
        voglio.freq = 48000; voglio.format = AUDIO_S16SYS; voglio.channels = 2; voglio.samples = 1024;
        s_audio = SDL_OpenAudioDevice(NULL, 0, &voglio, &ho, 0);
        if (s_audio) SDL_PauseAudioDevice(s_audio, 0);
    }
    if (getenv("AMIGA_WAV")) {
        s_wav = fopen(getenv("AMIGA_WAV"), "wb");
        if (s_wav) fseek(s_wav, 44, SEEK_SET);
    }
    if (!s_senza_finestra) {
        const char *titolo = g_game_spec.display_name ? g_game_spec.display_name : "Amiga";
        s_win = SDL_CreateWindow(titolo, SDL_WINDOWPOS_CENTERED, SDL_WINDOWPOS_CENTERED,
                                 AMIGA_LARGHEZZA * scala, AMIGA_ALTEZZA * scala,
                                 SDL_WINDOW_RESIZABLE | SDL_WINDOW_OPENGL |
                                 (schermo_intero ? SDL_WINDOW_FULLSCREEN_DESKTOP : 0));
        if (lineare) SDL_SetHint(SDL_HINT_RENDER_SCALE_QUALITY, "1");
        s_scala = scala;
        SDL_RaiseWindow(s_win);                      /* dopo il launcher la finestra puo' nascere senza focus */
        if (imp.cattura_mouse)
            SDL_SetRelativeMouseMode(SDL_TRUE);      /* gioco a mouse: puntatore catturato */
        s_gl = amiga_video_gl_init(s_win, imp.crt);  /* filtro CRT; senza OpenGL, renderer SDL */
        if (s_gl) amiga_video_gl_filtro(lineare);
        if (!s_gl) {
            s_ren = SDL_CreateRenderer(s_win, -1, SDL_RENDERER_ACCELERATED);
            SDL_RenderSetLogicalSize(s_ren, AMIGA_LARGHEZZA, AMIGA_ALTEZZA);
            s_tex = SDL_CreateTexture(s_ren, SDL_PIXELFORMAT_ARGB8888, SDL_TEXTUREACCESS_STREAMING,
                                      AMIGA_LARGHEZZA, AMIGA_ALTEZZA);
        }
    }
    int debug = getenv("AMIGA_DEBUG") != NULL;
    for (int i = 1; i < argc; i++) if (!strcmp(argv[i], "--debug")) debug = 1;
    amiga_debug_init(debug || s_senza_finestra, debug && !s_senza_finestra);

    g_cpu.A[7] = m68k_read32(0);                      /* SSP dalla tabella dei vettori */
    g_cpu.SR = 0;                                     /* il gioco parte da AmigaDOS: utente */
    if (g_game_spec.call_entry_point) g_game_spec.call_entry_point();
    else call_by_address(m68k_read32(4));
    fprintf(stderr, "il gioco e' tornato dal punto di ingresso\n");
    return 1;
}
