/* amiga_console.c - la console di Windows.
 *
 * L'eseguibile e' un'applicazione grafica: aperto normalmente mostra solo il
 * launcher e il gioco, senza la finestra della shell. La console serve:
 *   - in modalita' debug (--debug o AMIGA_DEBUG): se ne apre una, o si usa
 *     quella da cui e' stato lanciato;
 *   - nelle prove senza finestra e con --esporta-amiga lanciati da una
 *     console: ci si aggancia a quella, per i messaggi.
 * Se l'uscita e' gia' rediretta (file o pipe, come fanno gli script di prova)
 * resta com'e'. */
#include "amiga_console.h"

#ifdef _WIN32
#include <windows.h>
#include <stdio.h>

void amiga_console_prepara(int debug) {
    DWORD tipo = GetFileType(GetStdHandle(STD_OUTPUT_HANDLE));
    if (tipo == FILE_TYPE_DISK || tipo == FILE_TYPE_PIPE) return;     /* gia' rediretta */
    int ok = AttachConsole(ATTACH_PARENT_PROCESS);
    if (!ok && debug) ok = AllocConsole();
    if (!ok) return;
    FILE *f;
    freopen_s(&f, "CONOUT$", "w", stdout);
    freopen_s(&f, "CONOUT$", "w", stderr);
    if (debug) SetConsoleTitleA("Rock Star Ate My Hamster - debug");
}
#else
void amiga_console_prepara(int debug) { (void)debug; }
#endif
