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

#if defined(RECOMP_LAUNCHER)
#include "recomp_launcher.h"
#include "launcher_profile.h"
#endif

M68KState g_cpu;
uint64_t  g_native_insn_count;
uint32_t  g_cycle_accumulator;
uint32_t  g_vblank_threshold = AMIGA_CICLI_QUADRO;
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
static uint32_t s_t_quadro;
static int s_scala = 3;
static int s_sensibilita = 100;      /* movimento del mouse, in percento */

/* impostazioni.ini accanto all'eseguibile: cio' che si sceglie nel launcher
 * (o a mano, senza launcher) e vale anche alla partenza successiva */
typedef struct {
    int scala, schermo_intero, filtro, volume, audio;
    int sensibilita_mouse, cattura_mouse, salta_launcher;
} impostazioni_t;

static void leggi_impostazioni(impostazioni_t *s) {
    *s = (impostazioni_t){ 3, 0, 0, 80, 1, 100, 1, 0 };
    FILE *f = fopen("impostazioni.ini", "r");
    if (!f) return;
    char k[64]; int v;
    while (fscanf(f, " %63[^=]=%d", k, &v) == 2) {
        if (!strcmp(k, "scala")) s->scala = v;
        else if (!strcmp(k, "schermo_intero")) s->schermo_intero = v;
        else if (!strcmp(k, "filtro")) s->filtro = v;
        else if (!strcmp(k, "volume")) s->volume = v;
        else if (!strcmp(k, "audio")) s->audio = v;
        else if (!strcmp(k, "sensibilita_mouse")) s->sensibilita_mouse = v;
        else if (!strcmp(k, "cattura_mouse")) s->cattura_mouse = v;
        else if (!strcmp(k, "salta_launcher")) s->salta_launcher = v;
    }
    fclose(f);
    if (s->scala < 1) s->scala = 1;
    if (s->sensibilita_mouse < 25 || s->sensibilita_mouse > 400) s->sensibilita_mouse = 100;
}

static void scrivi_impostazioni(const impostazioni_t *s) {
    FILE *f = fopen("impostazioni.ini", "w");
    if (!f) return;
    fprintf(f, "scala=%d\nschermo_intero=%d\nfiltro=%d\nvolume=%d\naudio=%d\n"
               "sensibilita_mouse=%d\ncattura_mouse=%d\nsalta_launcher=%d\n",
            s->scala, s->schermo_intero, s->filtro, s->volume, s->audio,
            s->sensibilita_mouse, s->cattura_mouse, s->salta_launcher);
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

static void consegna_interrupt(void) {
    int l = amiga_hw_livello_interrupt();
    if (l > (int)((g_cpu.SR >> 8) & 7))
        eccezione(0x60u + (uint32_t)l * 4u, l);
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
    static int su, giu, sx, dx, fuoco, mouse_sx, mouse_dx, resto_x, resto_y;
    /* un clic deve durare almeno qualche quadro: se pressione e rilascio
     * arrivano fra due letture, il gioco vedrebbe solo il tasto su */
    static int tieni_sx, tieni_dx;
    int mdx = 0, mdy = 0;
    SDL_Event ev;
    while (SDL_PollEvent(&ev)) {
        if (ev.type == SDL_QUIT) exit(0);
        if (amiga_debug_evento(&ev)) continue;              /* F11, finestra di debug */
        if (ev.type == SDL_WINDOWEVENT && ev.window.event == SDL_WINDOWEVENT_CLOSE) exit(0);
        if (ev.type == SDL_KEYDOWN || ev.type == SDL_KEYUP) {
            int giu_ = ev.type == SDL_KEYDOWN;
            switch (ev.key.keysym.sym) {     /* joystick in porta 2: frecce + Ctrl */
            case SDLK_UP: su = giu_; break;
            case SDLK_DOWN: giu = giu_; break;
            case SDLK_LEFT: sx = giu_; break;
            case SDLK_RIGHT: dx = giu_; break;
            case SDLK_LCTRL: case SDLK_RCTRL: fuoco = giu_; break;
            default:
                if (!ev.key.repeat) {
                    int c = codice_amiga(ev.key.keysym.sym);
                    if (c >= 0) amiga_hw_tasto((uint8_t)c, !giu_);
                }
            }
        }
        if (ev.type == SDL_MOUSEBUTTONDOWN || ev.type == SDL_MOUSEBUTTONUP) {
            int giu_ = ev.type == SDL_MOUSEBUTTONDOWN;
            if (ev.button.button == SDL_BUTTON_LEFT) { mouse_sx = giu_; if (giu_) tieni_sx = 4; }
            if (ev.button.button == SDL_BUTTON_RIGHT) { mouse_dx = giu_; if (giu_) tieni_dx = 4; }
            if (ev.button.button == SDL_BUTTON_MIDDLE) {   /* centrale: sgancia / riaggancia */
                if (giu_) SDL_SetRelativeMouseMode(SDL_GetRelativeMouseMode() ? SDL_FALSE : SDL_TRUE);
            } else if (giu_ && !SDL_GetRelativeMouseMode())
                SDL_SetRelativeMouseMode(SDL_TRUE);         /* un clic nella finestra lo cattura */
        }
        if (ev.type == SDL_WINDOWEVENT && ev.window.event == SDL_WINDOWEVENT_FOCUS_LOST)
            SDL_SetRelativeMouseMode(SDL_FALSE);            /* Alt+Tab: il mouse torna a Windows */
        /* mouse catturato: il movimento in pixel della finestra diventa movimento
         * in pixel Amiga (diviso per la scala), il resto si porta avanti */
        if (ev.type == SDL_MOUSEMOTION && SDL_GetRelativeMouseMode()) {
            int div = s_scala * 100;                  /* sensibilita' in percento */
            resto_x += ev.motion.xrel * s_sensibilita; resto_y += ev.motion.yrel * s_sensibilita;
            mdx += resto_x / div; resto_x %= div;
            mdy += resto_y / div; resto_y %= div;
        }
        if (ev.type == SDL_KEYDOWN && ev.key.keysym.sym == SDLK_F12)    /* F12 libera il mouse */
            SDL_SetRelativeMouseMode(SDL_FALSE);
    }
    amiga_hw_joystick(su, giu, sx, dx, fuoco);
    amiga_hw_mouse(mdx, mdy, mouse_sx || tieni_sx > 0, mouse_dx || tieni_dx > 0);
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
    if (s_senza_finestra) {
        ingressi_test();
        if ((long)s_quadri >= s_quadri_max) {
            salva_bmp("quadro.bmp");
            FILE *m = fopen("memoria_fine.bin", "wb");     /* stato per confronti */
            if (m) { fwrite(g_amiga_mem, 1, g_amiga_mem_size, m); fclose(m); }
            printf("quadri %llu, salvati quadro.bmp e memoria_fine.bin\n", (unsigned long long)s_quadri);
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
    SDL_UpdateTexture(s_tex, NULL, amiga_hw_framebuffer(), AMIGA_LARGHEZZA * 4);
    SDL_RenderClear(s_ren);
    SDL_RenderCopy(s_ren, s_tex, NULL, NULL);
    SDL_RenderPresent(s_ren);
    ingressi_sdl();
    uint32_t ora = SDL_GetTicks();
    if (ora - s_t_quadro < 20) SDL_Delay(20 - (ora - s_t_quadro));
    s_t_quadro = SDL_GetTicks();
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

int main(int argc, char **argv) {
    const char *file = argc > 1 && argv[1][0] != '-' ? argv[1] : "rockstar_chipram.bin";
    impostazioni_t imp;
    leggi_impostazioni(&imp);
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
        RecompLauncherCGameInfo gi;
        memset(&gi, 0, sizeof gi);
        launcher_profile_apply("amiga", &gi);
        gi.name = g_game_spec.display_name ? g_game_spec.display_name : "Amiga";
        gi.mods = g_game_spec.mods ? g_game_spec.mods(NULL) : NULL;
        int rc = recomp_launcher_run_window(gi.name, &io, &gi, ".", file, scelto, sizeof scelto);
        if (rc != 0) return 0;
        if (scelto[0]) file = scelto;
        imp.scala = io.window_scale > 0 ? io.window_scale : 3;
        imp.schermo_intero = io.fullscreen;
        imp.filtro = io.linear_filter;
        imp.volume = io.volume;
        imp.audio = io.enable_audio;
        imp.salta_launcher = io.skip_launcher;
        imp.sensibilita_mouse = io.pointer_sensitivity > 0 ? io.pointer_sensitivity : 100;
        imp.cattura_mouse = io.pointer_capture;
        scrivi_impostazioni(&imp);
    }
#endif
    int scala = imp.scala, schermo_intero = imp.schermo_intero, lineare = imp.filtro;
    s_sensibilita = imp.sensibilita_mouse;
    FILE *f = fopen(file, "rb");
    if (!f) { fprintf(stderr, "immagine non trovata: %s\n", file); return 1; }
    fseek(f, 0, SEEK_END);
    long n = ftell(f);
    fseek(f, 0, SEEK_SET);
    g_amiga_mem = calloc(1, (size_t)n + 16);
    if (!g_amiga_mem || fread(g_amiga_mem, 1, (size_t)n, f) != (size_t)n) { fprintf(stderr, "lettura fallita\n"); return 1; }
    fclose(f);
    g_amiga_mem_size = (uint32_t)n;

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
    SDL_Init(s_senza_finestra ? 0 : SDL_INIT_VIDEO);
    if (!s_senza_finestra) {
        const char *titolo = g_game_spec.display_name ? g_game_spec.display_name : "Amiga";
        s_win = SDL_CreateWindow(titolo, SDL_WINDOWPOS_CENTERED, SDL_WINDOWPOS_CENTERED,
                                 AMIGA_LARGHEZZA * scala, AMIGA_ALTEZZA * scala,
                                 SDL_WINDOW_RESIZABLE | (schermo_intero ? SDL_WINDOW_FULLSCREEN_DESKTOP : 0));
        if (lineare) SDL_SetHint(SDL_HINT_RENDER_SCALE_QUALITY, "1");
        s_scala = scala;
        SDL_RaiseWindow(s_win);                      /* dopo il launcher la finestra puo' nascere senza focus */
        if (imp.cattura_mouse)
            SDL_SetRelativeMouseMode(SDL_TRUE);      /* gioco a mouse: puntatore catturato */
        s_ren = SDL_CreateRenderer(s_win, -1, SDL_RENDERER_PRESENTVSYNC);
        SDL_RenderSetLogicalSize(s_ren, AMIGA_LARGHEZZA, AMIGA_ALTEZZA);
        s_tex = SDL_CreateTexture(s_ren, SDL_PIXELFORMAT_ARGB8888, SDL_TEXTUREACCESS_STREAMING,
                                  AMIGA_LARGHEZZA, AMIGA_ALTEZZA);
        s_t_quadro = SDL_GetTicks();
    }
    int debug = getenv("AMIGA_DEBUG") != NULL;
    for (int i = 1; i < argc; i++) if (!strcmp(argv[i], "--debug")) debug = 1;
    amiga_debug_init(debug && !s_senza_finestra);

    g_cpu.A[7] = m68k_read32(0);                      /* SSP dalla tabella dei vettori */
    g_cpu.SR = 0;                                     /* il gioco parte da AmigaDOS: utente */
    if (g_game_spec.call_entry_point) g_game_spec.call_entry_point();
    else call_by_address(m68k_read32(4));
    fprintf(stderr, "il gioco e' tornato dal punto di ingresso\n");
    return 1;
}
