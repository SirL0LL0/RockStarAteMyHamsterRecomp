/* amiga_video_gl.c - presentazione in OpenGL: pixel netti o filtri CRT.
 *
 * Modelli di schermo, scelti a runtime con amiga_video_gl_modo():
 *   nitido     pixel netti; col filtro lineare (amiga_video_gl_filtro)
 *              ammorbiditi
 *   1084S      il monitor dell'Amiga: pixel ricostruiti in orizzontale
 *              (Lanczos), fascio gaussiano che si allarga sui colori chiari,
 *              maschera a fessure (slot mask) dei fosfori, un po' di alone,
 *              leggera curvatura e vignettatura
 *   Easymode   CRT piatto alla maniera di crt-easymode: Lanczos, fascio
 *              gaussiano, maschera a punti leggera, piu' luce
 *   Scanline   pixel netti con le righe vuote fra una riga e l'altra
 * Si mostrano solo le righe che il gioco usa (la finestra video,
 * amiga_hw_altezza_visibile: 200 su 256 per Rock Star), il piu' grandi
 * possibile, con la forma del pixel scelta (amiga_video_gl_aspetto): PAL,
 * cioe' come su un monitor 4:3 (AMIGA_PAR), o quadrata. Con la scala intera
 * (predefinita) il fattore verticale e' intero, cosi' pixel e scanline
 * restano tutti uguali; senza, l'immagine riempie la finestra.
 * OpenGL 2.1 / GLSL 1.20: le funzioni degli shader si caricano con
 * SDL_GL_GetProcAddress, cosi' basta opengl32 senza altre librerie.
 * Se qualcosa non va, amiga_video_gl_init() restituisce 0 e il runner usa il
 * renderer SDL normale.
 */
#include "amiga_video_gl.h"
#include "amiga_hw.h"
#include <SDL_opengl.h>
#include <stdio.h>

static PFNGLCREATESHADERPROC          p_CreateShader;
static PFNGLSHADERSOURCEPROC          p_ShaderSource;
static PFNGLCOMPILESHADERPROC         p_CompileShader;
static PFNGLGETSHADERIVPROC           p_GetShaderiv;
static PFNGLGETSHADERINFOLOGPROC      p_GetShaderInfoLog;
static PFNGLCREATEPROGRAMPROC         p_CreateProgram;
static PFNGLATTACHSHADERPROC          p_AttachShader;
static PFNGLBINDATTRIBLOCATIONPROC    p_BindAttribLocation;
static PFNGLLINKPROGRAMPROC           p_LinkProgram;
static PFNGLGETPROGRAMIVPROC          p_GetProgramiv;
static PFNGLUSEPROGRAMPROC            p_UseProgram;
static PFNGLGETUNIFORMLOCATIONPROC    p_GetUniformLocation;
static PFNGLUNIFORM1IPROC             p_Uniform1i;
static PFNGLUNIFORM2FPROC             p_Uniform2f;
static PFNGLVERTEXATTRIBPOINTERPROC   p_VertexAttribPointer;
static PFNGLENABLEVERTEXATTRIBARRAYPROC p_EnableVertexAttribArray;

static SDL_Window *s_win;
static SDL_GLContext s_ctx;
static GLuint s_tex, s_prog;
static GLint u_modo, u_src, u_out;
static int s_modo, s_lineare;
static int s_righe = AMIGA_ALTEZZA;          /* righe della texture */
static int s_intera = 1, s_pal = 1;

void amiga_video_gl_scala_intera(int si) { s_intera = si != 0; }
void amiga_video_gl_aspetto(int pal) { s_pal = pal != 0; }

const char *amiga_video_gl_nome(int modo) {
    static const char *const nomi[AMIGA_SCHERMI] = { "nitido", "Commodore 1084S", "CRT Easymode",
                                                     "Scanline" };
    return modo >= 0 && modo < AMIGA_SCHERMI ? nomi[modo] : nomi[0];
}

static const char *VS =
    "#version 120\n"
    "attribute vec2 pos;\n"
    "varying vec2 uv;\n"
    "void main() { uv = vec2(pos.x * 0.5 + 0.5, 0.5 - pos.y * 0.5); gl_Position = vec4(pos, 0.0, 1.0); }\n";

static const char *FS =
    "#version 120\n"
    "uniform sampler2D tex;\n"
    "uniform int modo;\n"
    "uniform vec2 src;\n"       /* 320 x righe usate */
    "uniform vec2 dst;\n"       /* pixel del rettangolo d'uscita */
    "varying vec2 uv;\n"
    "vec3 lin(vec3 c) { return pow(c, vec3(2.4)); }\n"
    /* una riga (centro yc, in texel) ricostruita in x con Lanczos a 4 punti */
    "float lanczos(float x) {\n"
    "    x = abs(x);\n"
    "    if (x < 0.0001) return 1.0;\n"
    "    if (x >= 2.0) return 0.0;\n"
    "    float p = 3.14159265 * x;\n"
    "    return 2.0 * sin(p) * sin(p * 0.5) / (p * p);\n"
    "}\n"
    "vec3 riga_lanczos(float yc, float x) {\n"
    "    yc = clamp(yc, 0.5, src.y - 0.5);\n"
    "    float xc = floor(x - 0.5) + 0.5, f = x - xc;\n"
    "    vec3 s = vec3(0.0); float w = 0.0;\n"
    "    for (int k = -1; k <= 2; k++) {\n"
    "        float wk = lanczos(f - float(k));\n"
    "        s += wk * lin(texture2D(tex, vec2(xc + float(k), yc) / src).rgb);\n"
    "        w += wk;\n"
    "    }\n"
    "    return max(s / w, vec3(0.0));\n"
    "}\n"
    "float fascio(float d, vec3 c, float stretto, float largo) {\n"   /* gaussiana, piu' larga sul chiaro */
    "    float l = max(max(c.r, c.g), c.b);\n"
    "    float s = mix(stretto, largo, l);\n"
    "    return exp(-0.5 * d * d / (s * s));\n"
    "}\n"
    "vec3 maschera(float forza) {\n"                                 /* 3 pixel: R, G, B */
    "    float m = mod(floor(gl_FragCoord.x), 3.0);\n"
    "    vec3 k = vec3(1.0 - forza);\n"
    "    if (m < 1.0) k.r = 1.0; else if (m < 2.0) k.g = 1.0; else k.b = 1.0;\n"
    "    return k;\n"
    "}\n"
    "vec3 fessure(float forza) {\n"                                  /* slot mask: triadi RGB sfalsate */
    "    float t = floor(gl_FragCoord.x / 3.0);\n"
    "    float r = mod(floor(gl_FragCoord.y) + mod(t, 2.0) * 2.0, 4.0);\n"
    "    return maschera(forza) * (r < 1.0 ? 0.80 : 1.0);\n"
    "}\n"
    "vec3 crt(vec2 p, float stretto, float largo) {\n"               /* le due righe vicine, col fascio */
    "    float y0 = floor(p.y - 0.5) + 0.5, fy = p.y - y0;\n"
    "    vec3 a = riga_lanczos(y0, p.x), b = riga_lanczos(y0 + 1.0, p.x);\n"
    "    return a * fascio(fy, a, stretto, largo) + b * fascio(1.0 - fy, b, stretto, largo);\n"
    "}\n"
    "void main() {\n"
    "    if (modo == 0) { gl_FragColor = texture2D(tex, uv); return; }\n"
    "    if (modo == 3) {\n"                                       /* pixel netti, righe vuote in mezzo */
    "        vec2 p = uv * src;\n"
    "        vec3 c = texture2D(tex, (floor(p) + 0.5) / src).rgb;\n"
    "        float w = 1.0 - 0.6 * smoothstep(0.55, 0.9, fract(p.y));\n"
    "        gl_FragColor = vec4(c * w * 1.12, 1.0);\n"
    "        return;\n"
    "    }\n"
    "    if (modo == 2) {\n"                                       /* Easymode */
    "        vec3 col = crt(uv * src, 0.27, 0.40) * maschera(0.30) * 1.40;\n"
    "        gl_FragColor = vec4(pow(col, vec3(1.0 / 2.2)), 1.0);\n"
    "        return;\n"
    "    }\n"
    /* Commodore 1084S */
    "    vec2 c = uv * 2.0 - 1.0;\n"                         /* curvatura leggera del tubo */
    "    c *= 1.0 + 0.018 * dot(c.yx, c.yx);\n"
    "    vec2 u = c * 0.5 + 0.5;\n"
    "    if (u.x < 0.0 || u.x > 1.0 || u.y < 0.0 || u.y > 1.0) { gl_FragColor = vec4(0.0, 0.0, 0.0, 1.0); return; }\n"
    "    vec2 p = u * src;\n"
    "    vec3 col = crt(p, 0.30, 0.44);\n"
    "    vec3 alone = crt(p + vec2(1.5, 0.0), 0.5, 0.6) + crt(p - vec2(1.5, 0.0), 0.5, 0.6)\n"
    "               + crt(p + vec2(0.0, 1.0), 0.5, 0.6) + crt(p - vec2(0.0, 1.0), 0.5, 0.6);\n"
    "    col = col + alone * 0.035;\n"
    "    col *= fessure(0.35) * 1.45;\n"
    "    vec2 bordo = smoothstep(vec2(0.0), vec2(0.012, 0.016), u) * smoothstep(vec2(0.0), vec2(0.012, 0.016), 1.0 - u);\n"
    "    col *= bordo.x * bordo.y;\n"                         /* angoli arrotondati dal vetro */
    "    col *= 1.0 - 0.12 * pow(length(c * vec2(0.8, 1.0)), 3.0);\n"   /* vignettatura */
    "    gl_FragColor = vec4(pow(col, vec3(1.0 / 2.2)), 1.0);\n"
    "}\n";

static GLuint compila(GLenum tipo, const char *sorgente) {
    GLuint s = p_CreateShader(tipo);
    p_ShaderSource(s, 1, &sorgente, NULL);
    p_CompileShader(s);
    GLint ok = 0;
    p_GetShaderiv(s, GL_COMPILE_STATUS, &ok);
    if (!ok) {
        char log[1024];
        p_GetShaderInfoLog(s, sizeof log, NULL, log);
        fprintf(stderr, "[video] shader non compilato: %s\n", log);
        return 0;
    }
    return s;
}

#define CARICA(v, nome) if (!(v = (void *)SDL_GL_GetProcAddress(nome))) return 0

int amiga_video_gl_init(SDL_Window *win, int modo) {
    s_win = win;
    s_ctx = SDL_GL_CreateContext(win);
    if (!s_ctx) return 0;
    SDL_GL_SetSwapInterval(0);                    /* il ritmo lo da' il runner, 50 Hz */
    CARICA(p_CreateShader, "glCreateShader");
    CARICA(p_ShaderSource, "glShaderSource");
    CARICA(p_CompileShader, "glCompileShader");
    CARICA(p_GetShaderiv, "glGetShaderiv");
    CARICA(p_GetShaderInfoLog, "glGetShaderInfoLog");
    CARICA(p_CreateProgram, "glCreateProgram");
    CARICA(p_AttachShader, "glAttachShader");
    CARICA(p_BindAttribLocation, "glBindAttribLocation");
    CARICA(p_LinkProgram, "glLinkProgram");
    CARICA(p_GetProgramiv, "glGetProgramiv");
    CARICA(p_UseProgram, "glUseProgram");
    CARICA(p_GetUniformLocation, "glGetUniformLocation");
    CARICA(p_Uniform1i, "glUniform1i");
    CARICA(p_Uniform2f, "glUniform2f");
    CARICA(p_VertexAttribPointer, "glVertexAttribPointer");
    CARICA(p_EnableVertexAttribArray, "glEnableVertexAttribArray");

    GLuint vs = compila(GL_VERTEX_SHADER, VS), fs = compila(GL_FRAGMENT_SHADER, FS);
    if (!vs || !fs) return 0;
    s_prog = p_CreateProgram();
    p_AttachShader(s_prog, vs);
    p_AttachShader(s_prog, fs);
    p_BindAttribLocation(s_prog, 0, "pos");
    p_LinkProgram(s_prog);
    GLint ok = 0;
    p_GetProgramiv(s_prog, GL_LINK_STATUS, &ok);
    if (!ok) return 0;
    u_modo = p_GetUniformLocation(s_prog, "modo");
    u_src = p_GetUniformLocation(s_prog, "src");
    u_out = p_GetUniformLocation(s_prog, "dst");

    glGenTextures(1, &s_tex);
    glBindTexture(GL_TEXTURE_2D, s_tex);
    glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_S, GL_CLAMP_TO_EDGE);
    glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_T, GL_CLAMP_TO_EDGE);
    glTexImage2D(GL_TEXTURE_2D, 0, GL_RGBA8, AMIGA_LARGHEZZA, AMIGA_ALTEZZA, 0, GL_BGRA, GL_UNSIGNED_BYTE, NULL);
    amiga_video_gl_modo(modo);
    return 1;
}

/* i CRT campionano fra un texel e l'altro (lineare); il nitido solo se si
 * vuole il filtro lineare */
static void filtro_texture(void) {
    glBindTexture(GL_TEXTURE_2D, s_tex);
    GLint f = (s_modo != SCHERMO_NITIDO || s_lineare) ? GL_LINEAR : GL_NEAREST;
    glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, f);
    glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, f);
}

void amiga_video_gl_modo(int modo) {
    s_modo = modo >= 0 && modo < AMIGA_SCHERMI ? modo : SCHERMO_NITIDO;
    filtro_texture();
}

void amiga_video_gl_filtro(int lineare) {
    s_lineare = lineare != 0;
    filtro_texture();
}

int amiga_video_gl_modo_attuale(void) { return s_modo; }

/* il rettangolo d'uscita per righe x 320 pixel in una finestra w x h */
void amiga_video_gl_rettangolo(int modo, int righe, int intera, int pal, int w, int h, int *vw, int *vh) {
    double par = pal ? AMIGA_PAR : 1.0;                         /* larghezza di un pixel / altezza */
    (void)modo;
    double rapporto = AMIGA_LARGHEZZA * par / righe;
    int k = intera ? h / righe : 0;                             /* fattore intero in verticale */
    if (!pal && w / AMIGA_LARGHEZZA < k) k = w / AMIGA_LARGHEZZA;
    while (k >= 1 && (int)(righe * k * rapporto + 0.5) > w) k--;
    if (k >= 1) {
        *vh = righe * k;
        *vw = !pal ? AMIGA_LARGHEZZA * k : (int)(*vh * rapporto + 0.5);
    } else {                                    /* senza scala intera, o finestra piu' piccola */
        *vw = w; *vh = (int)(w / rapporto);
        if (*vh > h) { *vh = h; *vw = (int)(h * rapporto); }
    }
}

void amiga_video_gl_presenta(const uint32_t *pixel) {
    int w, h, vw, vh;
    SDL_GL_GetDrawableSize(s_win, &w, &h);
    int righe = amiga_hw_altezza_visibile();
    amiga_video_gl_rettangolo(s_modo, righe, s_intera, s_pal, w, h, &vw, &vh);
    glViewport(0, 0, w, h);
    glClearColor(0, 0, 0, 1);
    glClear(GL_COLOR_BUFFER_BIT);
    glViewport((w - vw) / 2, (h - vh) / 2, vw, vh);

    glBindTexture(GL_TEXTURE_2D, s_tex);
    if (righe != s_righe) {                       /* la texture e' grande quanto le righe usate */
        glTexImage2D(GL_TEXTURE_2D, 0, GL_RGBA8, AMIGA_LARGHEZZA, righe, 0, GL_BGRA, GL_UNSIGNED_BYTE, NULL);
        s_righe = righe;
    }
    glTexSubImage2D(GL_TEXTURE_2D, 0, 0, 0, AMIGA_LARGHEZZA, righe, GL_BGRA, GL_UNSIGNED_BYTE, pixel);
    p_UseProgram(s_prog);
    p_Uniform1i(u_modo, s_modo);
    p_Uniform2f(u_src, (float)AMIGA_LARGHEZZA, (float)righe);
    p_Uniform2f(u_out, (float)vw, (float)vh);
    static const float quad[8] = { -1, -1, 1, -1, -1, 1, 1, 1 };
    p_VertexAttribPointer(0, 2, GL_FLOAT, GL_FALSE, 0, quad);
    p_EnableVertexAttribArray(0);
    glDrawArrays(GL_TRIANGLE_STRIP, 0, 4);
    SDL_GL_SwapWindow(s_win);
}
