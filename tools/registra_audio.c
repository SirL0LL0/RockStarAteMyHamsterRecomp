/* registra_audio.c - registra l'audio che esce dal PC (WASAPI in loopback)
 * per confrontare il port con un emulatore di riferimento.
 *
 *   clang -O2 tools/registra_audio.c -lole32 -o build/registra_audio.exe
 *   build\registra_audio.exe uscita.wav SECONDI
 *
 * Salva in PCM 16 bit stereo alla frequenza del dispositivo.
 */
#define COBJMACROS
#include <windows.h>
#include <initguid.h>
#include <mmdeviceapi.h>
#include <audioclient.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>

static void scrivi_intestazione(FILE *f, uint32_t freq, uint32_t byte) {
    uint32_t h[11] = { 0x46464952, 36 + byte, 0x45564157, 0x20746D66, 16, 0x00020001,
                       freq, freq * 4, 0x00100004, 0x61746164, byte };
    fseek(f, 0, SEEK_SET);
    fwrite(h, 4, 11, f);
}

int main(int argc, char **argv) {
    if (argc < 3) { fprintf(stderr, "uso: registra_audio uscita.wav secondi\n"); return 1; }
    double secondi = atof(argv[2]);
    CoInitializeEx(NULL, COINIT_MULTITHREADED);
    IMMDeviceEnumerator *en = NULL;
    IMMDevice *dev = NULL;
    IAudioClient *cl = NULL;
    IAudioCaptureClient *cap = NULL;
    WAVEFORMATEX *fmt = NULL;
    if (FAILED(CoCreateInstance(&CLSID_MMDeviceEnumerator, NULL, CLSCTX_ALL, &IID_IMMDeviceEnumerator, (void **)&en)) ||
        FAILED(IMMDeviceEnumerator_GetDefaultAudioEndpoint(en, eRender, eConsole, &dev)) ||
        FAILED(IMMDevice_Activate(dev, &IID_IAudioClient, CLSCTX_ALL, NULL, (void **)&cl)) ||
        FAILED(IAudioClient_GetMixFormat(cl, &fmt)) ||
        FAILED(IAudioClient_Initialize(cl, AUDCLNT_SHAREMODE_SHARED, AUDCLNT_STREAMFLAGS_LOOPBACK, 10000000, 0, fmt, NULL)) ||
        FAILED(IAudioClient_GetService(cl, &IID_IAudioCaptureClient, (void **)&cap))) {
        fprintf(stderr, "WASAPI non disponibile\n");
        return 1;
    }
    /* il formato condiviso e' quasi sempre float 32 bit: lo convertiamo in 16 bit */
    int canali = fmt->nChannels, flt = fmt->wBitsPerSample == 32;
    uint32_t freq = fmt->nSamplesPerSec, byte = 0;
    FILE *f = fopen(argv[1], "wb");
    if (!f) return 1;
    fseek(f, 44, SEEK_SET);
    IAudioClient_Start(cl);
    DWORD inizio = GetTickCount();
    while (GetTickCount() - inizio < (DWORD)(secondi * 1000)) {
        Sleep(10);
        UINT32 n;
        while (SUCCEEDED(IAudioCaptureClient_GetNextPacketSize(cap, &n)) && n) {
            BYTE *dati; UINT32 fotogrammi; DWORD flag;
            IAudioCaptureClient_GetBuffer(cap, &dati, &fotogrammi, &flag, NULL, NULL);
            for (UINT32 i = 0; i < fotogrammi; i++) {
                short s[2];
                for (int c = 0; c < 2; c++) {
                    int k = c < canali ? c : 0;
                    float v = (flag & AUDCLNT_BUFFERFLAGS_SILENT) ? 0.0f
                            : flt ? ((float *)dati)[i * canali + k] : ((short *)dati)[i * canali + k] / 32768.0f;
                    if (v > 1) v = 1; if (v < -1) v = -1;
                    s[c] = (short)(v * 32767);
                }
                fwrite(s, 2, 2, f);
                byte += 4;
            }
            IAudioCaptureClient_ReleaseBuffer(cap, fotogrammi);
        }
    }
    IAudioClient_Stop(cl);
    scrivi_intestazione(f, freq, byte);
    fclose(f);
    printf("registrati %.1f s a %u Hz in %s\n", byte / 4.0 / freq, freq, argv[1]);
    return 0;
}
