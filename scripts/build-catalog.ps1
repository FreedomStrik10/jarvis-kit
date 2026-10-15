<#
.SYNOPSIS
  Genera el catalogo HTTP de skills para GitHub Pages a partir de .opencode/skills/.

.DESCRIPTION
  Un catalogo HTTP es un index.json con una entrada por skill; OpenCode descarga
  <base-url>/<id>/<archivo> desde esa base. Esta rutina:
    1. Lee cada carpeta de .opencode/skills/
    2. Copia su SKILL.md como <id>/<id>.md (forma preferida por OpenCode)
    3. Copia los archivos de apoyo preservando rutas relativas
    4. Escribe docs/skills/index.json con un `version` derivado del contenido,
       para que OpenCode refresque la cache solo cuando algo cambia

  Base URL tras activar GitHub Pages (carpeta /docs):
      https://USUARIO.github.io/REPO/skills/

.EXAMPLE
  .\scripts\build-catalog.ps1
#>
[CmdletBinding()]
param()

$ErrorActionPreference = "Stop"

$root     = Split-Path -Parent $PSScriptRoot
$srcRoot  = Join-Path $root ".opencode\skills"
$dstRoot  = Join-Path $root "docs\skills"

if (-not (Test-Path $srcRoot)) {
    throw "No se encuentra la carpeta de skills: $srcRoot"
}

if (Test-Path $dstRoot) {
    Remove-Item $dstRoot -Recurse -Force
}
New-Item -ItemType Directory -Path $dstRoot -Force | Out-Null

$entries = @()
$hasher  = [System.Security.Cryptography.SHA256]::Create()

foreach ($skillDir in (Get-ChildItem $srcRoot -Directory | Sort-Object Name)) {

    $id       = $skillDir.Name
    $primary  = Join-Path $skillDir.FullName "SKILL.md"
    if (-not (Test-Path $primary)) {
        $alternate = Join-Path $skillDir.FullName "$id.md"
        if (Test-Path $alternate) { $primary = $alternate }
        else {
            Write-Warning "Skill '$id' sin SKILL.md ni $id.md — se omite."
            continue
        }
    }

    $target = Join-Path $dstRoot $id
    New-Item -ItemType Directory -Path $target -Force | Out-Null

    $relativeFiles = @()
    foreach ($file in (Get-ChildItem $skillDir.FullName -Recurse -File)) {

        $rel = $file.FullName.Substring($skillDir.FullName.Length).TrimStart('\', '/')
        $relUnix = $rel -replace '\\', '/'

        if ($file.FullName -eq $primary) {
            $relUnix = "$id.md"
        }

        $destPath = Join-Path $target ($relUnix -replace '/', '\')
        $destDir  = Split-Path -Parent $destPath
        if (-not (Test-Path $destDir)) {
            New-Item -ItemType Directory -Path $destDir -Force | Out-Null
        }
        Copy-Item $file.FullName $destPath -Force
        $relativeFiles += $relUnix
    }

    $relativeFiles = @($relativeFiles | Sort-Object -Unique)

    # Version determinista: cambia exactamente cuando cambia el contenido.
    $combined = ""
    foreach ($rel in $relativeFiles) {
        $combined += $rel + "`n" + [System.IO.File]::ReadAllText((Join-Path $target ($rel -replace '/', '\'))) + "`n"
    }
    $bytes  = [System.Text.Encoding]::UTF8.GetBytes($combined)
    $digest = [System.BitConverter]::ToString($hasher.ComputeHash($bytes)).Replace('-', '').Substring(0, 12).ToLower()

    $entries += [ordered]@{
        name    = $id
        version = $digest
        files   = $relativeFiles
    }

    Write-Host ("  skill '{0}' -> {1} archivo(s), version {2}" -f $id, $relativeFiles.Count, $digest)
}

$index = [ordered]@{
    skills = $entries
}

$indexPath = Join-Path $dstRoot "index.json"
$index | ConvertTo-Json -Depth 6 | Set-Content -Path $indexPath -Encoding UTF8

$hasher.Dispose()

Write-Host ""
Write-Host ("Catalogo escrito: {0} ({1} skill(s))" -f $indexPath, $entries.Count)
Write-Host "Base URL esperada: https://USUARIO.github.io/REPO/skills/"
