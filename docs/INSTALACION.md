# Instalar el Jarvis en otro proyecto

Guía paso a paso para que `Trading With IA`, `Nuestro Hogar` u otro proyecto
consuman el Jarvis. Los pasos 1–2 son de una sola vez; el resto es por proyecto.

---

## 1. Autenticar GitHub (una sola vez)

Esta máquina **aún no está conectada a GitHub** y no tiene `gh`. Instrucciones
completas en **[GITHUB.md](GITHUB.md)**. Resumen:

```powershell
winget install GitHub.cli          # o crear un PAT en github.com/settings/tokens
gh auth login --web                # solo si instalaste gh
git config --global user.name  "Tu Nombre"
git config --global user.email "tu@email"
```

## 2. Publicar el repo (una sola vez)

```powershell
cd "C:\Users\adria\Downloads\Posible Jarvis"
git init
git add -A
git commit -m "jarvis: cerebro unificador v0.1"
# crear el repo en github.com y luego:
git remote add origin https://github.com/FreedomStrik10/jarvis-kit.git
git push -u origin main
```

Verifica que `jarvis.projects.json` y `.env` **no** se suben:

```powershell
git status --ignored      # ambos deben aparecer como ignorados
```

## 3. Activar GitHub Pages (para el skill)

1. Repo → *Settings* → *Pages*
2. *Source*: **Deploy from a branch** → rama `main`, carpeta **`/docs`**
3. Guardar

Comprueba que responde:

```
https://freedomstrik10.github.io/jarvis-kit/skills/index.json
```

> ⚠️ **Obligatorio: `docs/.nojekyll`** (fichero vacío, ya incluido en el repo).
> Sin él, GitHub Pages procesa los `.md` con **Jekyll** y los sirve convertidos a
> `.html`: el `index.json` funciona, pero OpenCode recibe **404** al bajar
> `skills/jarvis/jarvis.md` y el skill no se instala. Con `.nojekyll`, Pages
> sirve los ficheros tal cual.
>
> Verificación rápida — esto tiene que dar 200, no 404:
> ```
> https://freedomstrik10.github.io/jarvis-kit/skills/jarvis/jarvis.md
> ```

Si cambias un skill, regenera y sube:

```powershell
npm run catalogo          # = scripts/build-catalog.ps1
git add docs/skills && git commit -m "skill: actualizar catálogo" && git push
```

> El campo `version` del `index.json` es un hash del contenido: OpenCode solo
> refresca su caché cuando cambia. Por eso se regenera en cada edición.

## 4. Por proyecto consumidor

### a) El plugin (commands + herramientas)

```powershell
opencode plugin add github:FreedomStrik10/jarvis-kit
```

Eso lo instala en el **config global** (`~/.config/opencode/opencode.json`), así
que vale para todos los proyectos. Verifica con `opencode plugin list`.

> Si prefieres activarlo **solo** en un proyecto, añádelo al array `plugins` de
> su `opencode.json(c)`. Ver `config/opencode.snippet.jsonc`.

### b) El skill (catálogo HTTP)

Añade al `opencode.json(c)` del proyecto:

```jsonc
{
  "skills": ["https://freedomstrik10.github.io/jarvis-kit/skills/"]
}
```

### c) El agent (puente local — obligatorio)

```powershell
.\scripts\sync.ps1 -Destino "C:\Users\adria\Downloads\Trading With IA"
.\scripts\sync.ps1 -Destino "C:\Users\adria\Documents\Proyecto predeterminado"
```

Usa `-DryRun` para ver qué haría sin tocar nada. Si el destino ya tiene un
`jarvis.md` distinto, lo guarda como `.bak-<fecha>` antes de sobrescribir.

> Alternativa: define el agente *inline* con `config/agents.snippet.jsonc`.

### d) El registro de proyectos

En la **raíz del proyecto consumidor** crea `jarvis.projects.json` (copia
`jarvis.projects.example.json`), **o** pásalo directamente en la config — que es
lo que permite versionarlo junto al resto:

```jsonc
"plugins": [
  {
    "package": "github:FreedomStrik10/jarvis-kit",
    "options": {
      "projects": [
        { "id": "trading", "name": "Trading With IA",
          "path": "C:\\Users\\adria\\Downloads\\Trading With IA",
          "files": ["trading/estado.json", "trading/guardian-estado.json"],
          "keys": ["fase", "mercado_abierto", "sesion_actual", "posiciones_abiertas"] },
        { "id": "hogar", "name": "Nuestro Hogar",
          "path": "C:\\Users\\adria\\Documents\\Proyecto predeterminado\\nuestro-hogar",
          "files": ["08-boceto/NOTAS-DE-ENTREGA-BOCETO.md"], "lines": 45 }
      ]
    }
  }
]
```

Orden de resolución: `options.projects` → `JARVIS_PROJECTS` (env) →
`jarvis.projects.json` junto al plugin → raíz del proyecto → `.opencode/`.

## 5. Verificar

```powershell
opencode-cli reload
opencode-cli debug agents       # debe aparecer "jarvis"
```

Y dentro de OpenCode:

```
/jarvis
```

Si responde con un informe de ambos proyectos, está listo. Si dice *"no tiene
proyectos enlazados"*, revisa el paso **d**.

---

## Problemas conocidos

| Síntoma | Causa → arreglo |
|---|---|
| `configured plugin path must be a directory` | La ruta del plugin apunta a un `.ts`. Usa el **directorio** (`"./src"` o la raíz del paquete). |
| Las herramientas aparecen como `estado`/`alerta` sin prefijo | Falta `options: { namespace: "jarvis" }` en cada `editor.add()`. |
| Error de sintaxis rarísimo en un `.ps1` con acentos | Falta el **BOM UTF-8**. PowerShell 5.1 lo lee como ANSI y un `—` se vuelve comilla rizada. |
| `plugin list` sale vacío | Solo lista plugins **globales** instalados con `plugin add`; los de ruta en la config no aparecen. |
| El skill no se actualiza en otra máquina | Sube el catálogo (`npm run catalogo`) — `version` es un hash del contenido. |
| `failed to download skill file … 404` en el log | Falta `docs/.nojekyll`. Jekyll convierte los `.md` a `.html` y el skill 404. |
| `index.json` sirve pero el skill no instala | Mismo motivo: comprueba que `<base>/<nombre>/<nombre>.md` da 200. |
| `No tool named "jarvis.estado" is currently available` | **Ruido de Code Mode, no es un fallo.** El modelo intenta primero llamarlo por nombre directo; al llamarlo dentro de `execute` (`return await tools.jarvis.estado({…})`) funciona. Verás 1–2 intentos fallidos antes. No hay que tocar nada. |
| El `.env` tiene las claves pero `credentials()` da `undefined` | Revisa el formato: `clave=` y el valor en **la misma línea**. En PowerShell, `"texto" + $x,` dentro de `@(...)` separa los elementos (la coma prima sobre `+`). Usa `("texto" + $x)`. |
