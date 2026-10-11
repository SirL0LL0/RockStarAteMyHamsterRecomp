# clic_finestra.ps1 - avvia il port, clicca in punti della finestra (coordinate
# dell'immagine catturata) e cattura il risultato. Per provare il launcher.
#   tools\clic_finestra.ps1 -clic "555,405" [-argomenti "--launcher"] [-uscita build\clic.png]
param([string]$clic = "", [string]$argomenti = "--launcher", [int]$attesa = 6,
      [string]$titolo = "Rock Star Ate My Hamster", [string]$uscita = "build\clic.png")
$repo = Split-Path $PSScriptRoot -Parent
$dir = Join-Path $repo "build\cmake"
Add-Type -AssemblyName System.Drawing
Add-Type @"
using System; using System.Text; using System.Runtime.InteropServices;
public class Clic {
  public delegate bool CB(IntPtr h, IntPtr l);
  [DllImport("user32.dll")] public static extern bool EnumWindows(CB cb, IntPtr l);
  [DllImport("user32.dll")] public static extern uint GetWindowThreadProcessId(IntPtr h, out uint pid);
  [DllImport("user32.dll")] public static extern bool IsWindowVisible(IntPtr h);
  [DllImport("user32.dll")] public static extern bool GetWindowRect(IntPtr h, out RECT r);
  [DllImport("user32.dll")] public static extern bool SetForegroundWindow(IntPtr h);
  [DllImport("user32.dll")] public static extern bool SetCursorPos(int x, int y);
  [DllImport("user32.dll")] public static extern void mouse_event(uint f, uint x, uint y, uint d, IntPtr e);
  [StructLayout(LayoutKind.Sequential)] public struct RECT { public int L, T, R, B; }
  public static IntPtr Trova(uint pid) {
    IntPtr trovata = IntPtr.Zero;
    EnumWindows((h, l) => { uint p; GetWindowThreadProcessId(h, out p);
      if (p == pid && IsWindowVisible(h)) { trovata = h; return false; } return true; }, IntPtr.Zero);
    return trovata;
  }
}
"@
$p = Start-Process -FilePath "$dir\RockStarAteMyHamsterRecomp.exe" -ArgumentList $argomenti -WorkingDirectory $dir -PassThru
Start-Sleep -Seconds $attesa
$h = [Clic]::Trova([uint32]$p.Id)
$r = New-Object Clic+RECT
[Clic]::GetWindowRect($h, [ref]$r) | Out-Null
[Clic]::SetForegroundWindow($h) | Out-Null
foreach ($c in ($clic -split ";" | Where-Object { $_ })) {
    $x, $y = $c -split ","
    [Clic]::SetCursorPos($r.L + [int]$x, $r.T + [int]$y) | Out-Null
    Start-Sleep -Milliseconds 200
    [Clic]::mouse_event(2, 0, 0, 0, [IntPtr]::Zero); Start-Sleep -Milliseconds 80
    [Clic]::mouse_event(4, 0, 0, 0, [IntPtr]::Zero); Start-Sleep -Milliseconds 800
}
$b = New-Object Drawing.Bitmap ($r.R - $r.L), ($r.B - $r.T)
$g = [Drawing.Graphics]::FromImage($b)
$g.CopyFromScreen($r.L, $r.T, 0, 0, $b.Size)
$b.Save((Join-Path $repo $uscita))
$p.Kill()
"catturata: $uscita"
