# Jarvis Voz — el Jarvis de Tony Stark

Asistente por voz que escucha su nombre, piensa con el agente `jarvis` de
OpenCode y contesta en voz alta. Bucle conversacional continuo: dices
"Jarvis", te oye, responde y vuelve a escucharte. Todo local y gratis.

    oídos      -> faster-whisper (transcripcion a texto, en local)
    despertar  -> openwakeword, modelo "hey_jarvis" (solo reacciona a tu palabra)
    cerebro    -> opencode run --agent jarvis (sesion persistente = memoria)
    boca       -> edge-tts (voz neural gratis) + ffplay

## Requisitos

- Windows con altavoces y microfono (ya los tienes).
- `uv` (lo tienes en `C:\Users\adria\.local\bin\uv.exe`).
- `ffplay` de ffmpeg (ya instalado).
- OpenCode CLI (ya instalado).

## Arranque

    powershell -NoProfile -ExecutionPolicy Bypass -File voz\iniciar-jarvis.ps1

La primera vez descarga los modelos (whisper + wakeword), tarda un poco.
Luego di **"Jarvis"** y espera el tono: habla con normalidad. Al callarte
unos 0,7 s, procesa y te contesta.

### Probar que te oye (sin meterse en el bucle)

    powershell -NoProfile -ExecutionPolicy Bypass -File voz\iniciar-jarvis.ps1 -PruebaDespertar

Mide el ruido de la habitacion y te muestra en pantalla, en directo, la
puntuacion del despertador mientras dices "Jarvis" (10 s). Si no llega al
umbral, baja `umbral_despertar` en `config-voz.json` (prueba 0.35).

### Autochequeo (no usa microfono ni manda a Telegram)

    powershell -NoProfile -ExecutionPolicy Bypass -File voz\iniciar-jarvis.ps1 -SelfTest

## Modo repliegue (estilo Stark)

Di **"modo repliegue"** para que hable poco (frases curtas). Di **"modo
normal"** para volver a respuestas completas. El estado vive en
`voz/estado-voz.json`.

## Salir

Di **"jarvis, apagate"** o pulsa Ctrl+C en su ventana.

## Limits conocidos

- La transcripcion y el despertar corren en CPU: en maquinas justas hay un
  segundo de latencia. Es normal.
- `openwakeword` necesita red la PRIMERA vez (descarga el modelo). Luego es
  100% local.
- Si el microfono no va, Jarvis no oye: revisa el dispositivo de entrada.
