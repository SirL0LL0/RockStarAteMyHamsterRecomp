/* amiga_video_gl.c - presentazione in OpenGL: pixel netti o filtri CRT.
 *
 * Modelli di schermo, scelti a runtime con amiga_video_gl_modo():
 *   nitido     pixel netti, rapporto 5:4 del quadro 320x256; col filtro
 *              lineare (amiga_video_gl_filtro) ammorbiditi
 *   1084S      il monitor dell'Amiga: leggera curvatura, scanline che si
 *              allargano sui colori chiari (il fascio), maschera RGB dei
 *              fosfori, un po' di bagliore, vignettatura, rapporto 4:3
 *   Easymode   CRT piatto alla maniera di crt-easymode: pixel ricostruiti in
 *              orizzontale con un filtro di Lanczos, fascio gaussiano che si
 *              allarga sui colori chiari, maschera a punti leggera, piu' luce
 *   Aperture   tubo Trinitron: griglia di apertura (strisce RGB verticali)
 *              piena, scanline sottili, bagliore
 *   Scanline   pixel netti con le righe vuote fra una riga e l'altra
 * Si mostrano solo le righe che il gioco usa (la finestra video,
 * amiga_hw_altezza_visibile: 200 su 256 per Rock Star), il piu' grandi
 * possibile: pixel quadrati per il nitido, la forma del pixel PAL su un 4:3
 * (AMIGA_PAR) per i CRT. Con la scala intera (predefinita) il fattore e'
 * intero, in verticale per i CRT, cosi' pixel e scanline restano tutti
 * uguali; senza, l'immagine riempie la finestra.
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
static int s_intera = 1;

void amiga_video_gl_scala_intera(int si) { s_intera = si != 0; }

const char *amiga_video_gl_nome(int modo) {
    static const char *const nomi[AMIGA_SCHERMI] = { "nitido", "Commodore 1084S", "CRT Easymode",
                                                     "CRT Aperture", "Scanline" };
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
    "uniform vec2 src;\n"       /* 320x256 */
    "uniform vec2 dst;\n"       /* pixel del rettangolo d'uscita */
    "varying vec2 uv;\n"
    "vec3 lin(vec3 c) { return pow(c, vec3(2.2)); }\n"
    "vec3 riga(vec2 u) {\n"     /* colore della riga, un po' morbido in orizzontale come il fascio */
    "    float y = (floor(u.y * src.y) + 0.5) / src.y;\n"
    "    float dx = 0.6 / src.x;\n"
    "    return lin(texture2D(tex, vec2(u.x, y)).rgb) * 0.5\n"
    "         + lin(texture2D(tex, vec2(u.x - dx, y)).rgb) * 0.25\n"
    "         + lin(texture2D(tex, vec2(u.x + dx, y)).rgb) * 0.25;\n"
    "}\n"
    /* Easymode: una riga (centro yc, in texel) ricostruita in x con Lanczos a 4 punti */
    "float lanczos(float x) {\n"
    "    x = abs(x);\n"
    "    if (x < 0.0001) return 1.0;\n"
    "    if (x >= 2.0) return 0.0;\n"
    "    float p = 3.14159265 * x;\n"
    "    return 2.0 * sin(p) * sin(p * 0.5) / (p * p);\n"
    "}\n"
    "vec3 riga_lanczos(float yc, float x) {\n"
    "    float xc = floor(x - 0.5) + 0.5, f = x - xc;\n"
    "    vec3 s = vec3(0.0); float w = 0.0;\n"
    "    for (int k = -1; k <= 2; k++) {\n"
    "        float wk = lanczos(f - float(k));\n"
    "        s += wk * pow(texture2D(tex, vec2(xc + float(k), yc) / src).rgb, vec3(2.4));\n"
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
    "void main() {\n"
    "    if (modo == 0) { gl_FragColor = texture2D(tex, uv); return; }\n"
    "    vec2 p = uv * src;\n"
    "    if (modo == 2 || modo == 3) {\n"
    "        float y0 = floor(p.y - 0.5) + 0.5, fy = p.y - y0;\n"       /* fra la riga y0 e la successiva */
    "        vec3 a, b;\n"
    "        if (modo == 2) { a = riga_lanczos(y0, p.x); b = riga_lanczos(y0 + 1.0, p.x); }\n"
    "        else {\n"
    "            a = pow(texture2D(tex, vec2(p.x, y0) / src).rgb, vec3(2.4));\n"
    "            b = pow(texture2D(tex, vec2(p.x, y0 + 1.0) / src).rgb, vec3(2.4));\n"
    "        }\n"
    "        vec3 col;\n"
    "        if (modo == 2) {\n"
    "            col = a * fascio(fy, a, 0.27, 0.40) + b * fascio(1.0 - fy, b, 0.27, 0.40);\n"
    "            col *= maschera(0.30) * 1.40;\n"
    "        } else {\n"
    "            col = a * fascio(fy, a, 0.22, 0.32) + b * fascio(1.0 - fy, b, 0.22, 0.32);\n"
    "            vec3 glow = pow(texture2D(tex, uv + vec2(2.0, 0.0) / src).rgb, vec3(2.4))\n"
    "                      + pow(texture2D(tex, uv - vec2(2.0, 0.0) / src).rgb, vec3(2.4));\n"
    "            col += glow * 0.05;\n"
    "            col *= maschera(0.75) * 2.1;\n"
    "        }\n"
    "        gl_FragColor = vec4(pow(col, vec3(1.0 / 2.2)), 1.0);\n"
    "        return;\n"
    "    }\n"
    "    if (modo == 4) {\n"                                       /* pixel netti, righe vuote in mezzo */
    "        vec3 c = texture2D(tex, (floor(p) + 0.5) / src).rgb;\n"
    "        float f = fract(p.y);\n"
    "        float w = 1.0 - 0.6 * smoothstep(0.55, 0.9, f);\n"
    "        gl_FragColor = vec4(c * w * 1.12, 1.0);\n"
    "        return;\n"
    "    }\n"
    "    vec2 c = uv * 2.0 - 1.0;\n"                         /* curvatura del tubo */
    "    c *= 1.0 + 0.035 * dot(c.yx, c.yx);\n"
    "    vec2 u = c * 0.5 + 0.5;\n"
    "    if (u.x < 0.0 || u.x > 1.0 || u.y < 0.0 || u.y > 1.0) { gl_FragColor = vec4(0.0, 0.0, 0.0, 1.0); return; }\n"
    "    float y = u.y * src.y;\n"
    "    float d = fract(y) - 0.5;\n"                        /* distanza dal centro della riga */
    "    vec3 a = riga(u);\n"
    "    vec3 b = riga(u + vec2(0.0, (d > 0.0 ? 1.0 : -1.0) / src.y));\n"
    "    float la = dot(a, vec3(0.3, 0.6, 0.1)), lb = dot(b, vec3(0.3, 0.6, 0.1));\n"
    "    float wa = exp(-d * d / (0.05 + 0.07 * la));\n"    /* le righe chiare sono piu' larghe */
    "    float e = 1.0 - abs(d);\n"
    "    float wb = exp(-e * e / (0.05 + 0.07 * lb)) * 0.6;\n"
    "    vec3 col = a * wa + b * wb;\n"
    "    vec3 glow = riga(u + vec2(1.5 / src.x, 0.0)) + riga(u - vec2(1.5 / src.x, 0.0));\n"
    "    col += glow * 0.06;\n"
    "    float m = mod(floor(gl_FragCoord.x), 3.0);\n"       /* maschera dei fosfori RGB */
    "    vec3 mask = vec3(0.78);\n"
    "    if (m < 1.0) mask.r = 1.0; else if (m < 2.0) mask.g = 1.0; else mask.b = 1.0;\n"
    "    col *= mask * 1.45;\n"
    "    float v = length(c * vec2(0.9, 1.0));\n"            /* vignettatura */
    "    col *= 1.0 - 0.22 * pow(v, 3.0);\n"
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
void amiga_video_gl_rettangolo(int modo, int righe, int intera, int w, int h, int *vw, int *vh) {
    double par = modo != SCHERMO_NITIDO ? AMIGA_PAR : 1.0;     /* larghezza di un pixel / altezza */
    double rapporto = AMIGA_LARGHEZZA * par / righe;
    int k = intera ? h / righe : 0;                             /* fattore intero in verticale */
    if (modo == SCHERMO_NITIDO && w / AMIGA_LARGHEZZA < k) k = w / AMIGA_LARGHEZZA;
    while (k >= 1 && (int)(righe * k * rapporto + 0.5) > w) k--;
    if (k >= 1) {
        *vh = righe * k;
        *vw = modo == SCHERMO_NITIDO ? AMIGA_LARGHEZZA * k : (int)(*vh * rapporto + 0.5);
    } else {                                    /* senza scala intera, o finestra piu' piccola */
        *vw = w; *vh = (int)(w / rapporto);
        if (*vh > h) { *vh = h; *vw = (int)(h * rapporto); }
    }
}

void amiga_video_gl_presenta(const uint32_t *pixel) {
    int w, h, vw, vh;
    SDL_GL_GetDrawableSize(s_win, &w, &h);
    int righe = amiga_hw_altezza_visibile();
    amiga_video_gl_rettangolo(s_modo, righe, s_intera, w, h, &vw, &vh);
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
