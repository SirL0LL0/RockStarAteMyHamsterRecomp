# ricostruisci_tutto.ps1 - dopo ogni modifica ai testi o alle patch:
# eseguibile Amiga + ADF, WHDLoad (LHA), immagine del port e port nativo.
#   .\ricostruisci_tutto.ps1 [-senza_port]
# Servono rockstar_base.bin nella cartella dei dati (vedi percorsi.py) e
# amitools (pip install amitools) per l'ADF. Le versioni Amiga finiscono in
# uscite\ nella cartella dei dati, fuori dal repository.
param([switch]$senza_port)
$ErrorActionPreference = "Stop"
$qui = $PSScriptRoot
$repo = Split-Path $qui -Parent
Set-Location $qui
$uscite = python -c "import percorsi; percorsi.base(); print(percorsi.USCITE)"
if ($LASTEXITCODE) { throw "manca la base del gioco (vedi sopra)" }
New-Item -ItemType Directory -Force $uscite | Out-Null
# l'eseguibile Amiga e' un passaggio intermedio: va dentro l'ADF come
# "rockstar" (da li' si estrae, se serve), quindi sta nella cartella temporanea
$tmp = Join-Path $env:TEMP "rsamh_adf"
New-Item -ItemType Directory -Force $tmp | Out-Null
$exe = Join-Path $tmp "rockstar"
$py = @"
import percorsi, build_ram as br
e, n = br.costruisci_exe(percorsi.immagine_ita(), br.carica('rockstar_text_table_ESTESA.json'),
                         br.carica('rockstar_text_table_ITA.json'))
open(r'$exe', 'wb').write(e)
print('eseguibile Amiga:', n)
"@
$py | python -
if ($LASTEXITCODE) { throw "build_ram" }

$adf = Join-Path $uscite "RockStar_ITA_1MB.adf"
[IO.File]::WriteAllText("$tmp\startup-sequence", "rockstar`n")   # a capo Amiga: solo LF
if (Test-Path $adf) { Move-Item $adf "$tmp\RockStar_ITA_1MB.adf.vecchio" -Force }
python -m amitools.tools.xdftool $adf create + format "RockStar ITA" ofs + boot install + makedir s + write "$tmp\startup-sequence" s/startup-sequence + write $exe rockstar | Out-Null
if ($LASTEXITCODE) { throw "xdftool" }
Remove-Item -LiteralPath $exe
"ADF: $adf"

python build_whdload.py | Select-Object -Last 1
if ($LASTEXITCODE) { throw "build_whdload" }

if (-not $senza_port) {
    python "$repo\game\prepara_immagine.py"
    if ($LASTEXITCODE) { throw "prepara_immagine" }
    cmake --build "$repo\build\cmake" | Select-String "error|FAILED|immagine"
    if ($LASTEXITCODE) { throw "cmake (il gioco e' aperto?)" }
    # di nuovo, ora che il C generato viene da questa immagine: controlla che
    # l'inglese non cambi codice
    python "$repo\game\prepara_immagine.py" | Out-Null
    if ($LASTEXITCODE) { throw "controllo del codice dell'inglese" }
    "port: $repo\build\cmake\RockStarAteMyHamsterRecomp.exe"
}
