/* amiga_video_gl.c - presentazione in OpenGL con filtro CRT "Commodore 1084S".
 *
 * Due modi, scelti a runtime con amiga_video_gl_modo():
 *   0 nitido   pixel netti, rapporto 5:4 del quadro 320x256
 *   1 1084S    il monitor dell'Amiga: leggera curvatura, scanline che si
 *              allargano sui colori chiari (il fascio), maschera RGB dei
 *              fosfori, un po' di bagliore, vignettatura, rapporto 4:3
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
static int s_modo;

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
    "void main() {\n"
    "    if (modo == 0) { gl_FragColor = texture2D(tex, uv); return; }\n"
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

void amiga_video_gl_modo(int modo) {
    s_modo = modo ? 1 : 0;
    glBindTexture(GL_TEXTURE_2D, s_tex);
    GLint f = s_modo ? GL_LINEAR : GL_NEAREST;   /* il 1084S filtra lui, il nitido no */
    glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, f);
    glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, f);
}

int amiga_video_gl_modo_attuale(void) { return s_modo; }

void amiga_video_gl_presenta(const uint32_t *pixel) {
    int w, h;
    SDL_GL_GetDrawableSize(s_win, &w, &h);
    /* rettangolo d'uscita: 4:3 per il monitor, 5:4 (pixel quadrati) per il nitido */
    double rapporto = s_modo ? 4.0 / 3.0 : (double)AMIGA_LARGHEZZA / AMIGA_ALTEZZA;
    int vw = w, vh = (int)(w / rapporto);
    if (vh > h) { vh = h; vw = (int)(h * rapporto); }
    glViewport(0, 0, w, h);
    glClearColor(0, 0, 0, 1);
    glClear(GL_COLOR_BUFFER_BIT);
    glViewport((w - vw) / 2, (h - vh) / 2, vw, vh);

    glBindTexture(GL_TEXTURE_2D, s_tex);
    glTexSubImage2D(GL_TEXTURE_2D, 0, 0, 0, AMIGA_LARGHEZZA, AMIGA_ALTEZZA, GL_BGRA, GL_UNSIGNED_BYTE, pixel);
    p_UseProgram(s_prog);
    p_Uniform1i(u_modo, s_modo);
    p_Uniform2f(u_src, (float)AMIGA_LARGHEZZA, (float)AMIGA_ALTEZZA);
    p_Uniform2f(u_out, (float)vw, (float)vh);
    static const float quad[8] = { -1, -1, 1, -1, -1, 1, 1, 1 };
    p_VertexAttribPointer(0, 2, GL_FLOAT, GL_FALSE, 0, quad);
    p_EnableVertexAttribArray(0);
    glDrawArrays(GL_TRIANGLE_STRIP, 0, 4);
    SDL_GL_SwapWindow(s_win);
}
