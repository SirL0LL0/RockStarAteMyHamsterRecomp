# cattura_finestra.ps1 - avvia il port con la finestra, aspetta e cattura una finestra.
#   tools\cattura_finestra.ps1 [-argomenti "--senza-launcher"] [-attesa 20]
#                              [-titolo "Rock Star Ate My Hamster"] [-uscita build\finestra.png]
param([string]$argomenti = "--senza-launcher", [int]$attesa = 20,
      [string]$titolo = "Rock Star Ate My Hamster", [string]$uscita = "build\finestra.png")
$repo = Split-Path $PSScriptRoot -Parent
$dir = Join-Path $repo "build\cmake"
Add-Type -AssemblyName System.Drawing
Add-Type @"
using System; using System.Text; using System.Runtime.InteropServices;
public class Cattura {
  public delegate bool CB(IntPtr h, IntPtr l);
  [DllImport("user32.dll")] public static extern bool EnumWindows(CB cb, IntPtr l);
  [DllImport("user32.dll")] public static extern uint GetWindowThreadProcessId(IntPtr h, out uint pid);
  [DllImport("user32.dll", CharSet=CharSet.Unicode)] public static extern int GetWindowText(IntPtr h, StringBuilder s, int n);
  [DllImport("user32.dll")] public static extern bool GetWindowRect(IntPtr h, out R r);
  [DllImport("user32.dll")] public static extern bool PrintWindow(IntPtr h, IntPtr dc, uint f);
  public struct R { public int L, T, Rr, B; }
  public static IntPtr Trova(uint pid, string t) {
    IntPtr x = IntPtr.Zero;
    EnumWindows((h,l)=>{ uint p; GetWindowThreadProcessId(h,out p); var s=new StringBuilder(256);
      GetWindowText(h,s,256); if(p==pid && s.ToString()==t){ x=h; return false; } return true; }, IntPtr.Zero);
    return x; }
}
"@ -ErrorAction SilentlyContinue
$p = Start-Process -FilePath "$dir\RockStarAteMyHamsterRecomp.exe" -ArgumentList $argomenti.Split(' ') -WorkingDirectory $dir -PassThru
Start-Sleep -Seconds $attesa
$h = [Cattura]::Trova([uint32]$p.Id, $titolo)
if ($h -eq [IntPtr]::Zero) { "finestra '$titolo' non trovata"; Stop-Process -Id $p.Id -Force; exit 1 }
$r = New-Object Cattura+R; [Cattura]::GetWindowRect($h, [ref]$r) | Out-Null
$b = New-Object Drawing.Bitmap ($r.Rr - $r.L), ($r.B - $r.T)
$g = [Drawing.Graphics]::FromImage($b); $dc = $g.GetHdc()
[Cattura]::PrintWindow($h, $dc, 2) | Out-Null; $g.ReleaseHdc($dc)
$b.Save((Join-Path $repo $uscita)); $b.Dispose()
Stop-Process -Id $p.Id -Force
"catturata: $uscita"
