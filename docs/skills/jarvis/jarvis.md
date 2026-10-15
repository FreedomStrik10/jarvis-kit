---
name: Jarvis
description: Cómo el Jarvis orquesta los proyectos enlazados — qué archivos lee, qué puede y qué no, y cómo añadir un proyecto nuevo. Usar cuando el usuario pregunte por el estado de los proyectos, por qué hay un desajuste, o quiera enlazar/desenlazar un proyecto.
---

# Skill: Jarvis

El Jarvis no tiene estado propio: **lee el estado de los demás**. Su única fuente de
verdad es el registro de proyectos enlazados más los archivos de estado de cada uno.

## Registro de proyectos

`jarvis.projects.json` en la raíz del proyecto (está en `.gitignore`; la plantilla
es `jarvis.projects.example.json`).

```jsonc
{
  "projects": [
    {
      "id": "trading",                     // id corto, para filtrar
      "name": "Trading With IA",           // nombre en el informe
      "path": "C:\\…\\Trading With IA",    // raíz del proyecto
      "files": ["trading/estado.json"],     // archivos de estado, en prioridad
      "keys": ["fase", "mercado_abierto"],  // claves a extraer (solo JSON)
      "lines": 30                           // líneas a mostrar (solo Markdown)
    }
  ]
}
```

Orden de resolución: `options.projects` del plugin → `JARVIS_PROJECTS` (env) →
`jarvis.projects.json` junto al plugin → en la raíz del proyecto → en `.opencode/`.

Si ninguno existe, `jarvis_estado` lo dice explícitamente. **No inventes un estado.**

## Qué lee de cada proyecto

### `trading` — Trading With IA

| Archivo | Aporta |
|---|---|
| `trading/estado.json` | `fase`, `mercado_abierto`, `sesion_actual` (régimen, ciclos, P/L del día), `posiciones_abiertas`, `tareas_pendientes`, `incidencias`, `equity_referencia`, `optimizacion` |
| `trading/guardian-estado.json` | `resumen` del último ciclo del guardián + `ultima_ejecucion` |
| `trading/parametros.json` | `version` vigente de la estrategia (fuente única de verdad) |

Señales que obligan a **`⚠️`** en la respuesta:

- `guardian-estado.json` con `ultima_ejecucion` de hace >15 min **con el mercado
  abierto** → el guardián no está corriendo.
- `mercado_abierto: true` y `posiciones_abiertas` con alguna entrada sin stop.
- Existe `trading/halt-<fecha>.flag` → circuit breaker disparado, día cerrado.
- `fase` distinta de `operando` con el mercado abierto.

### `hogar` — Nuestro Hogar

| Archivo | Aporta |
|---|---|
| `08-boceto/NOTAS-DE-ENTREGA-BOCETO.md` | Estado de la entrega: duración, formatos, verificación, material del cliente |
| `99-doc/PLAN-DE-RODAJE-Y-MONTAJE.md` | Plan por bloques, problemas de guion pendientes, decisiones abiertas |

Señales que obligan a **`⚠️`**: el plan marca opciones sin decidir (A/B/C), o las
notas de entrega tienen >5 días sin tocar mientras hay tareas abiertas en el plan.

## Límites

- **`jarvis_estado` solo lee.** No hay herramienta de escritura en el Jarvis a
  propósito: escribir en un proyecto lo hace su propio agente, con sus propias reglas.
- **`jarvis_alerta` es la única que tiene efecto externo** (Telegram). Nunca
  envíes claves ni el contenido de `.env` por ella.
- El Jarvis **no ejecuta** órdenes de trading ni renders. Si el usuario pide eso,
  dígelo y sugiere abrir el proyecto correspondiente.

## Añadir un proyecto nuevo

1. Copia una entrada en `jarvis.projects.json` y ajusta `id`, `name`, `path`.
2. Elige `files`: el archivo que mejor resuma "¿cómo va?" (JSON preferible, con
   `keys` para reducir el volumen; Markdown con `lines` si no existe JSON).
3. Prueba con `jarvis_estado` y `proyecto: "<id>"`.
4. Añade una fila a la tabla de arriba y sus señales de `⚠️`.
