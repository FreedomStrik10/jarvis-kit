# Jarvis — cerebro unificador para OpenCode

Capa que mantiene coherentes tus proyectos: **lee** el estado de todos ellos,
lo resume en un solo parte y **avisa** cuando algo se desvía.

Hoy enlaza:

| id | Proyecto | Estado que lee |
|---|---|---|
| `trading` | Trading With IA | `trading/estado.json`, `guardian-estado.json`, `parametros.json` |
| `hogar` | Nuestro Hogar | notas de entrega del boceto + plan de rodaje |

## Qué obtienes

| Comando / herramienta | Qué hace |
|---|---|
| `/jarvis` | Parte de estado unificado de todos los proyectos (solo lectura) |
| `jarvis_estado` | La herramienta que lo alimenta — acepta `proyecto` para filtrar |
| `/alerta <texto>` → `jarvis_alerta` | Envía un aviso a Telegram (`info` · `aviso` · `critico`) |
| Agente `jarvis` | Orquestador primario, permisos de solo lectura |
| Skill `jarvis` | Qué lee de cada proyecto y qué señales obligan a `⚠️` |

## Estado

Todo está **probado y funcionando** en local con OpenCode **v2.0.26**:

- ✅ Plugin carga desde directorio y registra `jarvis.estado` / `jarvis.alerta`
- ✅ Agente `jarvis` descubierto (`default_agent` activo)
- ✅ Skill `jarvis` descubierto
- ✅ `jarvis_estado` devuelve datos en vivo de los dos proyectos
- ✅ Catálogo HTTP de skills generado (`docs/skills/`)
- ✅ `sync.ps1 -DryRun` resuelve bien el destino
- ✅ **Publicado**: <https://github.com/FreedomStrik10/jarvis-kit> (rama `main`)
- ✅ **Pages activo**: `https://freedomstrik10.github.io/jarvis-kit/skills/` → HTTP 200 (`.md` incluido, con `.nojekyll`)
- ✅ **Trading With IA enlazado** — plugin por `github:`, skill por Pages, agente sincronizado, `jarvis_estado` probado en vivo (régimen BAJISTA, 0 posiciones)
- ✅ **Nuestro Hogar enlazado** — mismo camino, `opencode.json` creado desde cero, filtro `proyecto: "hogar"` probado
- ✅ **Telegram activo** — `jarvis.alerta` enviado y entregado al chat del bot de Trading
- ⬜ **Pendiente**: permisos `jarvis.*` para el agente `qa` de Trading (el bot de Telegram, hoy en `* deny`)

## Estructura

```
opencode.json               → default_agent: jarvis + carga del plugin
package.json                → paquete instalable desde git
src/index.ts                → EL PLUGIN: herramientas + comandos
.opencode/agents/jarvis.md  → agente orquestador (puente local, ver docs/CLOUD.md)
.opencode/skills/jarvis/    → skill (fuente de verdad)
jarvis.projects.json        → registro de proyectos  ⚠ NO se sube (gitignored)
jarvis.projects.example.json→ plantilla del registro
config/                     → fragmentos copiables a otros proyectos
scripts/build-catalog.ps1   → genera docs/skills/ (catálogo HTTP)
scripts/sync.ps1            → baja los agents a otro proyecto
docs/                       → guías + catálogo servido por GitHub Pages
```

## Arranque rápido

```powershell
# 1. El registro de proyectos (una sola vez, no se sube a git)
Copy-Item jarvis.projects.example.json jarvis.projects.json
#    → ajusta las rutas a tu máquina

# 2. Abrir OpenCode aquí y preguntar
/jarvis
```

## Documentación

- **[docs/CLOUD.md](docs/CLOUD.md)** — qué vive en la nube, qué no, y **por qué** (tu pregunta original)
- **[docs/INSTALACION.md](docs/INSTALACION.md)** — cómo consumir el Jarvis desde otro proyecto
- **[docs/GITHUB.md](docs/GITHUB.md)** — autenticar y hacer push (esta máquina aún no está conectada)
- **[docs/TELEGRAM.md](docs/TELEGRAM.md)** — configurar las alertas

## Licencia

MIT
