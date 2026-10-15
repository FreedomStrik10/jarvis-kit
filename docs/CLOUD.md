# Qué vive en la nube y qué no

Tu pregunta original: *¿se puede subir plugins, MCP y agents a la nube para que
no ocupen sitio local y se mantengan online?*

Respuesta corta: **casi todo sí. Hay una excepción y dos matizes.**

## Tabla de verdad (OpenCode V2.0.26)

| Pieza | ¿En la nube? | Mecanismo | Ocupa sitio local |
|---|---|---|---|
| **Skill** | ✅ Sí, 100 % | Catálogo HTTP (`skills[]` con URL) — GitHub Pages | Caché descargada (~KB) |
| **Command** | ✅ Sí, 100 % | Lo registra el plugin al cargarse | El plugin (instalado una vez) |
| **Plugin** | ✅ Sí | `github:user/repo` / npm | **Sí** — código instalado y cacheado |
| **MCP remoto** | ✅ Sí, 100 % | `{"type":"remote","url":"https://…"}` | **No** (solo la config) |
| **MCP local** | ⚠️ Híbrido | `uvx` / `bunx` lo instala bajo demanda | Caché del runtime |
| **Agent** | ❌ **No** | Ver abajo | Sí, pero son ~2 KB de Markdown |
| **Referencias** | ✅ Sí | `references` con `repository` de Git | Caché |

### La excepción: los agents

En V2, `AgentEditor` **no expone `add()`** — solo `list/get/update/remove/default`.
Un plugin puede *modificar* agentes existentes pero **no crearlos**. Y la config
`skills`/`instructions` acepta URLs, pero **no existe un equivalente para agents**.

Por eso este repo tiene `scripts/sync.ps1`: es el puente. Copia
`.opencode/agents/jarvis.md` a cada proyecto que lo consuma.

> **Alternativa sin archivo local**: define el agente *inline* en el
> `opencode.json(c)` del proyecto con el campo `agents`
> (fragmento listo en `config/agents.snippet.jsonc`). Sigue siendo un archivo
> local, pero al menos va en la config que ya tienes versionada.

### Matiz 1: "en la nube" ≠ "sin nada en disco"

OpenCode corre **en tu máquina**. Todo lo que se ejecuta tiene que acabar en
algún lado. Lo que consigues es:

- la **fuente de verdad** vive en GitHub, versionada y sincronizada;
- OpenCode **lo trae bajo demanda** (instala el plugin, descarga el skill);
- tú **no mantienes copias** clonadas ni las sincronizas a mano.

Un plugin desde GitHub se instala igualmente en la caché de paquetes. La
diferencia es que *tú* no lo custodias.

### Matiz 2: los secretos nunca

`.env`, tokens y claves **no se suben**. Se referencian:

```jsonc
"headers": { "Authorization": "Bearer {env:POLLINATIONS_API_KEY}" }
```

En este repo: `.gitignore` bloquea `.env` y `jarvis.projects.json`.

## Cómo está montado aquí

```jsonc
// opencode.json del proyecto que consuma el Jarvis
{
  "skills": ["https://USUARIO.github.io/REPO/skills/"],   // ← nube
  "plugins": [{ "package": "github:USUARIO/REPO", "options": { ... } }]  // ← nube
}
```

```powershell
.\scripts\sync.ps1 -Destino "C:\ruta\del\proyecto"   // ← solo el agent
```

Detalle: los **rutas absolutas** de tus proyectos van en `options.projects`
(o en `jarvis.projects.json`). Eso es inevitablemente local — es config de
máquina, igual que lo es la ruta de tu disco.

## Reglas de este repo que descubrí probando

Documentadas porque costaron de encontrar:

1. **La ruta del plugin debe ser un directorio.** `"./src/index.ts"` falla con
   `configured plugin path must be a directory`. Usa `"./src"`.
2. **`editor.namespace()` no basta.** Cada herramienta necesita
   `options: { namespace: "jarvis" }` o termina con el nombre pelón (`estado`)
   — lo que además rompe los permisos del agente.
3. **Un `.ps1` con acentos necesita BOM UTF-8.** PowerShell 5.1 lo lee como
   ANSI y un `—` se convierte en comilla rizada, que PowerShell **acepta como
   delimitador** y tritura todo el parser.
4. **`opencode plugin list` solo muestra plugins de paquete globales** (los de
   `plugin add`). Los de ruta en la config no aparecen ahí.
