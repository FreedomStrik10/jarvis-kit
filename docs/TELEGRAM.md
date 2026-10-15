# Telegram — alertas del Jarvis

`jarvis_alerta` envía mensajes a Telegram por la **API HTTPS directa**
(`api.telegram.org/bot<token>/sendMessage`), no por scripts. Eso evita de golpe
todos los dolores de cabeza de escapado en PowerShell (el clásico bug del `$`).

## 1. Crear el bot

1. Habla con **@BotFather** en Telegram → `/newbot`
2. Elige nombre y usuario (`@…_bot`)
3. Copia el **token** (`123456789:AA…`)

> Si ya tienes el bot del proyecto *Trading With IA*, **reutilízalo**: mismo
> token, mismo canal, un solo chat para todo.

## 2. Obtener el `chat_id`

1. Manda un mensaje cualquiera a tu bot (o `@userinfobot`)
2. Abre:
   ```
   https://api.telegram.org/bot<TOKEN>/getUpdates
   ```
3. Busca `"chat":{"id": 123456789}` → ese es el `chat_id`
   (los de grupo suelen ir en negativo, `-100…`)

## 3. Configurar las credenciales

El plugin las busca, **en este orden**:

1. `process.env` → `TELEGRAM_BOT_TOKEN` / `TELEGRAM_CHAT_ID`
   (o los prefijados `JARVIS_TELEGRAM_*`)
2. Un `.env` cuya ruta pases en `options.envFile` (o `JARVIS_ENV_FILE`)
3. `.env` junto al plugin
4. `.env` en la **raíz del proyecto que lo consuma**

En la práctica: crea un `.env` en la raíz del proyecto (o reutiliza el del
proyecto Trading, ya funcionando):

```dotenv
TELEGRAM_BOT_TOKEN=123456789:AA...
TELEGRAM_CHAT_ID=123456789
```

`.env` está en `.gitignore` — **nunca se sube**. Copia la referencia:

```powershell
Copy-Item .env.example .env
```

## 4. Probar

Dentro de OpenCode:

```
/alerta prueba desde el Jarvis
```

o directamente la herramienta `jarvis_alerta` con
`{ "mensaje": "prueba", "nivel": "info" }`.

Si no está configurado, la herramienta lo dice explícitamente y **no envía nada**
(no falla en silencio).

## Niveles

| Nivel | Emoji | Cuándo |
|---|---|---|
| `info` | ℹ️ | Día a día — resúmenes, "sin novedad" |
| `aviso` | ⚠️ | Algo se desvía — régimen raro, fichero parado, plan sin decidir |
| `critico` | 🚨 | **Riesgo real** — posición sin stop, guardián caído con mercado abierto, pérdida de dinero/datos |

> **Formato**: el texto se envía con `parse_mode: MarkdownV2` y se escapan los
> caracteres especiales. Por eso la instrucción de no usar `$` en los importes:
> escribe `55,80 USD`, no `$55.80`.
