<#
  iniciar-jarvis.ps1 - ARRANQUE DEL JARVIS DE VOZ
  ---------------------------------------------------------------------------
  Lanza voz/jarvis_voz.py con uv (que resuelve solo las dependencias:
  whisper, wakeword, edge-tts, sounddevice). Primera vez: descarga modelos
  (puede tardar unos minutos). Despues: di "Jarvis".

  Uso:
    powershell -NoProfile -ExecutionPolicy Bypass -File voz\iniciar-jarvis.ps1
    powershell -NoProfile -ExecutionPolicy Bypass -File voz\iniciar-jarvis.ps1 [-SelfTest] [-PruebaDespertar]

  Nota: si la consola escribe acentos raros, es solo estetica (cp1252);
  el script interno fuerza UTF-8.
#>
param(
  [switch]$SelfTest,
  [switch]$PruebaDespertar
)

$ErrorActionPreference = "Stop"
$Here = Split-Path -Parent $MyInvocation.MyCommand.Definition
$Py   = Join-Path $Here "jarvis_voz.py"

# uv: el instalador que ya hay en esta maquina (o el del PATH).
$uv = "C:\Users\adria\.local\bin\uv.exe"
if (-not (Test-Path -LiteralPath $uv)) {
  $enPath = Get-Command uv -ErrorAction SilentlyContinue
  if ($enPath) { $uv = $enPath.Source }
  else {
    Write-Output "No encuentro uv. Instalalo: winget install astral-sh.uv"
    exit 1
  }
}

$argList = @("run", "--python", "3.12", $Py)
if ($SelfTest) { $argList += "--selftest" }
if ($PruebaDespertar) { $argList += "--prueba-despertar" }

Write-Output ("Arrancando Jarvis voz con: " + $uv + " " + ($argList -join " "))
& $uv @argList
exit $LASTEXITCODE
