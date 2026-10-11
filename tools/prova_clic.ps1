# prova_clic.ps1 - prova il mouse per la strada vera: avvia il port con la
# finestra, aspetta il titolo, manda un clic sinistro di Windows (SendInput)
# alla finestra e confronta lo schermo prima e dopo.
#   tools\prova_clic.ps1 [-attesa 8] [-durata_ms 60]
param([int]$attesa = 8, [int]$durata_ms = 60)
$repo = Split-Path $PSScriptRoot -Parent
$dir = Join-Path $repo "build\cmake"
Add-Type -AssemblyName System.Drawing
Add-Type @"
using System; using System.Runtime.InteropServices;
public class Clic {
  [DllImport("user32.dll")] public static extern bool GetWindowRect(IntPtr h, out R r);
  [DllImport("user32.dll")] public static extern bool PrintWindow(IntPtr h, IntPtr dc, uint f);
  [DllImport("user32.dll")] public static extern bool SetForegroundWindow(IntPtr h);
  [DllImport("user32.dll")] public static extern bool SetCursorPos(int x, int y);
  [DllImport("user32.dll")] public static extern void mouse_event(uint f, uint x, uint y, uint d, IntPtr e);
  public struct R { public int L, T, Rr, B; }
}
"@ -ErrorAction SilentlyContinue
function Cattura($h, $nome) {
    $r = New-Object Clic+R; [Clic]::GetWindowRect($h, [ref]$r) | Out-Null
    $b = New-Object Drawing.Bitmap ($r.Rr - $r.L), ($r.B - $r.T)
    $g = [Drawing.Graphics]::FromImage($b); $dc = $g.GetHdc()
    [Clic]::PrintWindow($h, $dc, 2) | Out-Null; $g.ReleaseHdc($dc)
    $b.Save((Join-Path $repo "build\$nome.png")); $b.Dispose()
    return $r
}
$p = Start-Process -FilePath "$dir\RockStarAteMyHamsterRecomp.exe" -ArgumentList "rockstar_chipram.bin --senza-launcher" `
    -WorkingDirectory $dir -PassThru
Start-Sleep -Seconds $attesa
$p.Refresh(); $h = $p.MainWindowHandle
$r = Cattura $h "clic_prima"
[Clic]::SetForegroundWindow($h) | Out-Null
[Clic]::SetCursorPos([int](($r.L + $r.Rr) / 2), [int](($r.T + $r.B) / 2)) | Out-Null
Start-Sleep -Milliseconds 300
[Clic]::mouse_event(0x0002, 0, 0, 0, [IntPtr]::Zero)      # sinistro giu'
Start-Sleep -Milliseconds $durata_ms
[Clic]::mouse_event(0x0004, 0, 0, 0, [IntPtr]::Zero)      # sinistro su
Start-Sleep -Seconds 4
Cattura $h "clic_dopo" | Out-Null
Stop-Process -Id $p.Id -Force
"catturati build\clic_prima.png e build\clic_dopo.png"
