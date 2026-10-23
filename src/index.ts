import { Plugin } from "@opencode/plugin"
import { existsSync, readFileSync, statSync } from "node:fs"
import { dirname, resolve } from "node:path"
import { fileURLToPath } from "node:url"

const HERE = dirname(fileURLToPath(import.meta.url))

/** Un proyecto enlazado: dónde vive y qué archivos cuentan su estado. */
export interface ProjectDef {
  /** Identificador corto, usado como filtro (`proyecto: "trading"`). */
  id: string
  /** Nombre legible para el informe. */
  name: string
  /** Ruta absoluta (o relativa al config) de la raíz del proyecto. */
  path: string
  /** Archivos de estado relativos a `path`, en orden de prioridad. */
  files: string[]
  /** Edad máxima "sana" en minutos para los archivos de este proyecto (por defecto 240). */
  maxAgeMinutes?: number
  /** Claves a extraer si el archivo primario es JSON. Si se omite, las 15 primeras. */
  keys?: string[]
  /** Líneas a mostrar si el archivo es Markdown. */
  lines?: number
}

interface JarvisOptions {
  /** Lista de proyectos. Tiene prioridad sobre cualquier archivo. */
  projects?: ProjectDef[]
  /** Ruta a un .env con TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID. */
  envFile?: string
}

const MAX_STR = 400
const MAX_ARR = 6
const MAX_DEPTH = 3

/** Recorta estructuras para que el informe no desborde el contexto. */
function compact(value: unknown, depth = 0): unknown {
  if (typeof value === "string") {
    return value.length > MAX_STR
      ? `${value.slice(0, MAX_STR)} …(+${value.length - MAX_STR} car.)`
      : value
  }
  if (Array.isArray(value)) {
    if (depth >= MAX_DEPTH) return `[${value.length} elementos]`
    const head = value.slice(0, MAX_ARR).map((item) => compact(item, depth + 1))
    if (value.length > MAX_ARR) head.push(`…(+${value.length - MAX_ARR} más)`)
    return head
  }
  if (value && typeof value === "object") {
    if (depth >= MAX_DEPTH) return "{…}"
    const out: Record<string, unknown> = {}
    for (const [key, item] of Object.entries(value as Record<string, unknown>)) {
      out[key] = compact(item, depth + 1)
    }
    return out
  }
  return value
}

function parseJsonFile(file: string): unknown {
  try {
    if (!existsSync(file)) return undefined
    return JSON.parse(readFileSync(file, "utf8"))
  } catch {
    return undefined
  }
}

/** Acepta `ProjectDef[]` o `{ projects: [...] }` y descarta entradas incompletas. */
function normaliseProjects(raw: unknown): ProjectDef[] {
  if (!raw) return []
  const list = Array.isArray(raw) ? raw : (raw as { projects?: unknown }).projects
  if (!Array.isArray(list)) return []
  return list.filter(
    (item): item is ProjectDef =>
      !!item &&
      typeof item === "object" &&
      typeof (item as ProjectDef).id === "string" &&
      typeof (item as ProjectDef).path === "string" &&
      Array.isArray((item as ProjectDef).files),
  )
}

function readEnvFile(file: string): Record<string, string> {
  const out: Record<string, string> = {}
  if (!existsSync(file)) return out
  for (const line of readFileSync(file, "utf8").split(/\r?\n/)) {
    const match = line.match(/^\s*([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.*?)\s*$/)
    if (!match) continue
    let value = match[2]
    if (
      (value.startsWith('"') && value.endsWith('"') && value.length > 1) ||
      (value.startsWith("'") && value.endsWith("'") && value.length > 1)
    ) {
      value = value.slice(1, -1)
    }
    out[match[1]] = value
  }
  return out
}

const LEVEL_BADGE: Record<string, string> = {
  info: "ℹ️",
  aviso: "⚠️",
  critico: "🚨",
}

export default Plugin.define({
  id: "jarvis",
  async setup(ctx) {
    const options = (ctx.options ?? {}) as JarvisOptions
    const locationDir = ctx.location?.directory ?? process.cwd()

    /** Orden de resolución del registro de proyectos. */
    const registry = (): ProjectDef[] => {
      const fromOptions = normaliseProjects(options.projects)
      if (fromOptions.length) return fromOptions

      const candidates = [
        process.env.JARVIS_PROJECTS,
        resolve(HERE, "..", "jarvis.projects.json"),
        resolve(locationDir, "jarvis.projects.json"),
        resolve(locationDir, ".opencode", "jarvis.projects.json"),
      ].filter((candidate): candidate is string => !!candidate)

      for (const candidate of candidates) {
        const found = normaliseProjects(parseJsonFile(candidate))
        if (found.length) return found
      }
      return []
    }

    /** Filtra proyectos por id o nombre parcial; error legible si no hay coincidencias. */
    const seleccionar = (
      projects: ProjectDef[],
      proyecto?: string,
    ): { selected: ProjectDef[]; error?: string } => {
      if (!proyecto) return { selected: projects }
      const selected = projects.filter(
        (project) =>
          project.id === proyecto ||
          project.name.toLowerCase().includes(proyecto.toLowerCase()),
      )
      return selected.length
        ? { selected }
        : {
            selected: [],
            error: `Proyecto "${proyecto}" no está enlazado. Enlazados: ${projects
              .map((project) => project.id)
              .join(", ")}`,
          }
    }

    /** Rutas en las que el plugin busca el .env con las credenciales de Telegram. */
    const envFileCandidates = (): string[] =>
      [
        options.envFile,
        process.env.JARVIS_ENV_FILE,
        resolve(HERE, "..", ".env"),
        resolve(locationDir, ".env"),
      ].filter((file): file is string => !!file)

    const credentials = (): { token: string; chat: string } | undefined => {
      const fileEnv = envFileCandidates()
        .map(readEnvFile)
        .reduce((merged, next) => ({ ...merged, ...next }), {} as Record<string, string>)

      const token =
        process.env.TELEGRAM_BOT_TOKEN || process.env.JARVIS_TELEGRAM_BOT_TOKEN || fileEnv.TELEGRAM_BOT_TOKEN
      const chat =
        process.env.TELEGRAM_CHAT_ID || process.env.JARVIS_TELEGRAM_CHAT_ID || fileEnv.TELEGRAM_CHAT_ID

      return token && chat ? { token, chat } : undefined
    }

    /** Diagnóstico para el error de "Telegram no configurado": qué se miró y qué había. */
    const envDiagnostics = (): string => {
      const paths = envFileCandidates().map((file) => {
        const exists = existsSync(file)
        const keys = exists ? Object.keys(readEnvFile(file)).length : 0
        return `  ${exists ? "existe    " : "no existe "} (${keys} claves): ${file}`
      })
      return [
        "Rutas de .env comprobadas:",
        ...paths,
        `process.env: TELEGRAM_BOT_TOKEN=${process.env.TELEGRAM_BOT_TOKEN ? "si" : "no"}, ` +
          `TELEGRAM_CHAT_ID=${process.env.TELEGRAM_CHAT_ID ? "si" : "no"}`,
        `locationDir: ${locationDir}`,
        `HERE (plugin): ${HERE}`,
      ].join("\n")
    }

    // ── Herramientas ────────────────────────────────────────────────────────
    await ctx.tool.transform((editor) => {
      editor.namespace({
        name: "jarvis",
        description: "Orquestación entre los proyectos enlazados con el Jarvis.",
      })

      editor.add({
        name: "estado",
        description:
          "Lee el estado de TODOS los proyectos enlazados con el Jarvis (Trading With IA, Nuestro Hogar, …) y " +
          "devuelve un informe unificado de solo lectura: fase, mercado, posiciones, guardián, tareas pendientes " +
          "y última entrega. Úsala para responder a /jarvis o cuando el usuario pregunte cómo van los proyectos.",
        input: {
          type: "object",
          properties: {
            proyecto: {
              type: "string",
              description: "Filtro opcional: id o nombre parcial de un proyecto (p. ej. \"trading\").",
            },
          },
          additionalProperties: false,
        },
        options: { namespace: "jarvis" },
        execute: async (input, context) => {
          const { proyecto } = input as { proyecto?: string }
          const projects = registry()

          if (!projects.length) {
            return {
              content:
                "El Jarvis no tiene proyectos enlazados.\n\n" +
                "Copia `jarvis.projects.example.json` a `jarvis.projects.json` en la raíz de este proyecto " +
                "(o pásalos como `options.projects` en opencode.json(c)) y ajusta las rutas.\n" +
                "Guía: docs/INSTALACION.md",
            }
          }

          const { selected, error } = seleccionar(projects, proyecto)
          if (error) return { content: error }

          await context.progress({ status: `Leyendo ${selected.length} proyecto(s)` })

          const out: string[] = [
            "# Estado unificado — Jarvis",
            "",
            `_Generado: ${new Date().toISOString()}_`,
            "",
          ]

          for (const project of selected) {
            out.push(`## ${project.name}  ·  \`${project.id}\``, "")

            if (!existsSync(project.path)) {
              out.push(`- ⚠️ Ruta no encontrada: \`${project.path}\``, "")
              continue
            }

            for (const relative of project.files) {
              const absolute = resolve(project.path, relative)

              if (!existsSync(absolute)) {
                out.push(`- \`${relative}\` — no existe`)
                continue
              }

              const stats = statSync(absolute)
              const age = Math.round((Date.now() - stats.mtimeMs) / 60000)
              const stale = age > 240 ? " ⏳" : ""
              out.push(`- \`${relative}\` — modificado hace ${age} min${stale}`)

              const raw = readFileSync(absolute, "utf8")

              if (absolute.toLowerCase().endsWith(".json")) {
                try {
                  const parsed = JSON.parse(raw) as Record<string, unknown>
                  const keys = project.keys ?? Object.keys(parsed).slice(0, 15)
                  const picked: Record<string, unknown> = {}
                  for (const key of keys) if (key in parsed) picked[key] = parsed[key]
                  out.push("```json", JSON.stringify(compact(picked), null, 2), "```")
                } catch {
                  out.push("```json", raw.slice(0, 1200), "```")
                }
              } else {
                const limit = project.lines ?? 40
                const body = raw.split(/\r?\n/).slice(0, limit).join("\n")
                out.push("```markdown", body, "```")
              }
            }
            out.push("")
          }

          return { content: out.join("\n") }
        },
      })

      editor.add({
        name: "salud",
        description:
          "Comprueba la SALUD de los proyectos enlazados (solo existencia y frescura de sus archivos de estado) y " +
          "devuelve un diagnóstico compacto: ✅ sano / ⏳ obsoleto (archivo con más de maxAgeMinutes, por defecto 240) / " +
          "🚨 caído (ruta o archivo ausente), con tabla resumen arriba y detalle debajo. Úsala para /jarvis-salud o " +
          "cuando pidan un diagnóstico rápido del sistema.",
        input: {
          type: "object",
          properties: {
            proyecto: {
              type: "string",
              description: "Filtro opcional: id o nombre parcial de un proyecto (p. ej. \"trading\").",
            },
          },
          additionalProperties: false,
        },
        options: { namespace: "jarvis" },
        execute: async (input, context) => {
          const { proyecto } = input as { proyecto?: string }
          const projects = registry()

          if (!projects.length) {
            return {
              content:
                "El Jarvis no tiene proyectos enlazados: nada que comprobar.\n\n" +
                "Copia `jarvis.projects.example.json` a `jarvis.projects.json` en la raíz de este proyecto " +
                "y ajusta las rutas. Guía: docs/INSTALACION.md",
            }
          }

          const { selected, error } = seleccionar(projects, proyecto)
          if (error) return { content: error }

          await context.progress({ status: `Comprobando salud de ${selected.length} proyecto(s)` })

          const tabla: string[] = []
          const detalle: string[] = []
          let sanos = 0
          let obsoletos = 0
          let caidos = 0

          for (const project of selected) {
            if (!existsSync(project.path)) {
              caidos++
              tabla.push(`| ${project.name} | 🚨 | ruta ausente |`)
              detalle.push(`### ${project.name} — 🚨`, "", `- Ruta no encontrada: \`${project.path}\``, "")
              continue
            }

            const maxAge = project.maxAgeMinutes ?? 240
            const motivos: string[] = []
            let veredicto: "✅" | "⏳" | "🚨" = "✅"
            const lineas: string[] = []

            for (const relative of project.files) {
              const absolute = resolve(project.path, relative)
              if (!existsSync(absolute)) {
                veredicto = "🚨"
                motivos.push(`falta ${relative}`)
                lineas.push(`- \`${relative}\` — 🚨 no existe`)
                continue
              }
              const age = Math.round((Date.now() - statSync(absolute).mtimeMs) / 60000)
              if (age > maxAge) {
                if (veredicto !== "🚨") veredicto = "⏳"
                motivos.push(`${relative}: hace ${age} min (> ${maxAge})`)
                lineas.push(`- \`${relative}\` — ⏳ hace ${age} min (máx ${maxAge})`)
              } else {
                lineas.push(`- \`${relative}\` — ✅ hace ${age} min (máx ${maxAge})`)
              }
            }

            if (veredicto === "✅") sanos++
            else if (veredicto === "⏳") obsoletos++
            else caidos++
            tabla.push(
              `| ${project.name} | ${veredicto} | ${motivos.length ? motivos.join("; ") : `${project.files.length}/${project.files.length} sanos`} |`,
            )
            detalle.push(`### ${project.name} — ${veredicto}`, "", ...lineas, "")
          }

          const global = caidos > 0 ? "🚨" : obsoletos > 0 ? "⏳" : "✅"
          const out = [
            "# Salud — Jarvis",
            "",
            `_Generado: ${new Date().toISOString()}_`,
            "",
            "| Proyecto | Veredicto | Detalle |",
            "|---|---|---|",
            ...tabla,
            "",
            ...detalle,
            `**Veredicto global: ${global}** — sanos ${sanos} · obsoletos ${obsoletos} · caídos ${caidos}`,
            "",
            caidos > 0
              ? "Hay proyectos caídos: si quieres avisar por Telegram, pídelo con `/alerta <texto>` (no se envía solo)."
              : obsoletos > 0
                ? "Archivos obsoletos no son incidencia crítica: pueden esperar al siguiente ciclo del proyecto."
                : "Todo sano: los proyectos enlazados se actualizan dentro de su cadencia esperada.",
          ]
          return { content: out.join("\n") }
        },
      })

      editor.add({
        name: "alerta",
        description:
          "Envía una alerta corta a Telegram. Úsala cuando el usuario pida avisar de algo, o cuando detectes " +
          "una incidencia en un proyecto enlazado (posición sin stop, render caído, tarea pendiente urgente).",
        input: {
          type: "object",
          properties: {
            mensaje: { type: "string", description: "Texto del aviso. Nunca incluyas el signo $; escribe los importes como 55,80 USD." },
            nivel: { type: "string", enum: ["info", "aviso", "critico"], description: "Gravedad. Por defecto info." },
          },
          required: ["mensaje"],
          additionalProperties: false,
        },
        options: { namespace: "jarvis" },
        execute: async (input) => {
          const { mensaje, nivel = "info" } = input as { mensaje: string; nivel?: string }
          const cred = credentials()

          if (!cred) {
            return {
              content:
                "Telegram no está configurado. Faltan TELEGRAM_BOT_TOKEN y TELEGRAM_CHAT_ID " +
                "(en process.env o en un .env — ver docs/TELEGRAM.md). El mensaje NO se ha enviado.\n\n" +
                envDiagnostics(),
            }
          }

          const badge = LEVEL_BADGE[nivel] ?? LEVEL_BADGE.info
          const text = `${badge} *Jarvis*\n${mensaje.replace(/([_*[\]()~`>#+\-=|{}.!\\])/g, "\\$1")}`

          try {
            const response = await fetch(`https://api.telegram.org/bot${cred.token}/sendMessage`, {
              method: "POST",
              headers: { "content-type": "application/json" },
              body: JSON.stringify({
                chat_id: cred.chat,
                text,
                parse_mode: "MarkdownV2",
                disable_web_page_preview: true,
              }),
            })
            const body = (await response.json()) as { ok?: boolean; description?: string }
            if (!response.ok || !body.ok) {
              return { content: `Telegram rechazó el envío (${response.status}): ${body.description ?? "sin detalle"}` }
            }
            return { content: `Alerta enviada a Telegram (${nivel}).` }
          } catch (error) {
            return { content: `No se pudo enviar la alerta: ${(error as Error).message}` }
          }
        },
      })
    })

    // ── Comandos ────────────────────────────────────────────────────────────
    await ctx.command.transform((editor) => {
      editor.add({
        name: "jarvis",
        description: "Parte de estado unificado de todos los proyectos enlazados con el Jarvis",
        execute: async ({ sessionID, prompt, delivery }) => {
          await ctx.session.prompt({
            ...prompt,
            sessionID,
            delivery,
            text: [
              "Muestra el **parte de estado unificado** usando la herramienta `jarvis_estado`.",
              "",
              "Reglas:",
              "- **Solo lectura**: no modifiques, crees ni borres nada en ningún proyecto.",
              "- Estructura de la respuesta: (1) una línea por proyecto con su estado actual,",
              "  (2) alertas o desajustes detectados, (3) qué harías a continuación.",
              "- Si un archivo está desactualizado (>4 h) o falta, dilo explícitamente.",
              "",
              "--- Petición original del usuario ---",
              prompt.text || "(sin texto adicional)",
            ].join("\n"),
          })
        },
      })

      editor.add({
        name: "jarvis-salud",
        description: "Diagnóstico rápido de salud de todos los proyectos enlazados (solo lectura)",
        execute: async ({ sessionID, prompt, delivery }) => {
          await ctx.session.prompt({
            ...prompt,
            sessionID,
            delivery,
            text: [
              "Comprueba la salud de TODOS los proyectos enlazados con la herramienta `jarvis_salud` (sin filtro).",
              "",
              "Reglas:",
              "- **Solo lectura**: no modifiques, crees ni borres nada; la herramienta solo lee archivos de estado.",
              "- Estructura de la respuesta: (1) tabla resumen proyecto → veredicto (✅ sano / ⏳ obsoleto / 🚨 caído),",
              "  (2) detalle de lo que falla y por qué (ruta ausente, archivo con más de su maxAgeMinutes),",
              "  (3) si hay 🚨, sugiere `/alerta <texto>` pero NO envíes la alerta sin que el usuario lo pida.",
              "- Un archivo obsoleto NO es incidencia crítica si su proyecto puede estar fuera de su horario;",
              "  dilo con calma y no asumas fallo.",
              "",
              "--- Petición original del usuario ---",
              prompt.text || "(sin texto adicional)",
            ].join("\n"),
          })
        },
      })

      editor.add({
        name: "alerta",
        description: "Envía una alerta a Telegram — uso: /alerta <mensaje>",
        execute: async ({ sessionID, prompt, delivery }) => {
          await ctx.session.prompt({
            ...prompt,
            sessionID,
            delivery,
            text: [
              "Envía a Telegram el mensaje indicado por el usuario con la herramienta `jarvis_alerta`.",
              "Si el usuario no indicó texto, pídeselo antes de enviar nada.",
              "Usa nivel `critico` solo si hay riesgo real (dinero, seguridad, pérdida de datos).",
              "",
              "--- Petición original del usuario ---",
              prompt.text || "(sin texto adicional)",
            ].join("\n"),
          })
        },
      })
    })
  },
})
