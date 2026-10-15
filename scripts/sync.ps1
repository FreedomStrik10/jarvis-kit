<#
.SYNOPSIS
  Baja los AGENTS del Jarvis a un proyecto destino.

.DESCRIPTION
  En OpenCode V2 los skills y los commands llegan por la nube (catalogo HTTP y
  plugin desde GitHub). Los AGENTS son la excepcion: no aceptan URL, tienen que
  vivir en .opencode/agents/ de cada proyecto. Este script es ese puente.

  Por defecto NO pisa nada: si el archivo de destino existe y difiere, lo guarda
  como .bak y avisa. Usa -Forzar para sobrescribir sin guardar copia.

.EXAMPLE
  .\scripts\sync.ps1 -Destino "C:\Users\adria\Downloads\Trading With IA"

.EXAMPLE
  .\scripts\sync.ps1 -Destino "..\otro-proyecto" -DryRun
#>
[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$Destino,

    # Sobrescribir aunque el destino difiera, sin guardar copia .bak.
    [switch]$Forzar,

    # Solo decir qué haría, sin tocar nada.
    [switch]$DryRun
)

$ErrorActionPreference = "Stop"

$root       = Split-Path -Parent $PSScriptRoot
$agentsRoot = Join-Path $root ".opencode\agents"

if (-not (Test-Path $agentsRoot)) {
    throw "No se encuentra la carpeta de agents: $agentsRoot"
}

$destAbs = Resolve-Path -Path $Destino -ErrorAction Stop
$destDir = Join-Path $destAbs ".opencode\agents"

# Si el destino ya tiene .opencode/agents, lo respetamos; si no, lo creamos.
if (-not (Test-Path $destDir)) {
    if (-not $DryRun) {
        New-Item -ItemType Directory -Path $destDir -Force | Out-Null
    }
    Write-Host "Creando $destDir"
}

$actions = @()

foreach ($file in (Get-ChildItem $agentsRoot -File -Filter *.md | Sort-Object Name)) {

    $destFile = Join-Path $destDir $file.Name
    $status   = "nuevo"

    if (Test-Path $destFile) {
        $srcHash  = (Get-FileHash $file.FullName -Algorithm SHA256).Hash
        $destHash = (Get-FileHash $destFile     -Algorithm SHA256).Hash
        if ($srcHash -eq $destHash) { $status = "sin-cambios"; continue }
        $status = "difiere"
    }

    if ($DryRun) {
        $actions += [pscustomobject]@{ Archivo = $file.Name; Accion = $status; Destino = $destFile }
        continue
    }

    if ($status -eq "difiere") {
        if ($Forzar) {
            Copy-Item $file.FullName $destFile -Force
            $actions += [pscustomobject]@{ Archivo = $file.Name; Accion = "sobrescrito"; Destino = $destFile }
            continue
        }
        $bak = "$destFile.bak-$(Get-Date -Format yyyyMMdd-HHmmss)"
        Copy-Item $destFile $bak -Force
        Copy-Item $file.FullName $destFile -Force
        $actions += [pscustomobject]@{ Archivo = $file.Name; Accion = "actualizado (copia en $(Split-Path $bak -Leaf))"; Destino = $destFile }
        continue
    }

    Copy-Item $file.FullName $destFile -Force
    $actions += [pscustomobject]@{ Archivo = $file.Name; Accion = "creado"; Destino = $destFile }
}

if ($actions.Count -eq 0) {
    Write-Host "Nada que hacer: los agents del proyecto ya están al día."
} else {
    $actions | Format-Table -AutoSize
    if ($DryRun) {
        Write-Host "(DryRun — no se ha escrito nada)" -ForegroundColor Yellow
    }
}

Write-Host ""
Write-Host "Recordatorio: skills y commands NO se copian — llegan por la nube." -ForegroundColor Cyan
Write-Host "  skills  -> opencode.json(c):  `"skills`": [`"https://freedomstrik10.github.io/jarvis-kit/skills/`"]"
Write-Host "  plugin  -> `"plugins`": [`"github:FreedomStrik10/jarvis-kit`"]  (o: opencode plugin add github:FreedomStrik10/jarvis-kit)"
