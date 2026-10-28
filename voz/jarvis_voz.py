# /// script
# requires-python = ">=3.11"
# dependencies = [
#   "faster-whisper>=1.0",
#   "edge-tts>=6.1",
#   "sounddevice>=0.4",
#   "numpy>=1.26",
#   "openwakeword>=0.6",
#   "onnxruntime>=1.17",
# ]
# ///
"""
jarvis_voz.py - EL JARVIS DE TONY STARK, en voz.
===========================================================================
Bucle conversacional continuo:

    [openwakeword] escuchando "Jarvis" -> tono de confirmacion ->
    [sounddevice]  graba tu frase (VAD por energia, corta a los 0,7 s de
                   silencio) -> [faster-whisper] transcribe ->
    [opencode run --agent jarvis] piensa con TODAS las herramientas del
    Jarvis (sesion persistente = memoria de la charla) ->
    [edge-tts + ffplay] te contesta en voz alta -> vuelve a escuchar.

Modo repliegue (di "modo repliegue"): el cerebro recibe una instruccion
extra de responder en frases cortas. Se guarda en voz/estado-voz.json.

Degradacion elegante: si openwakeword no arranca (sin red la primera vez,
o dependencia rota), Jarvis pasa a modo BOTON: pulsa Intro y habla. El
resto del pipeline (whisper, cerebro, voz) es identico. Nunca se queda
sin arrancar en silencio.

Uso:
    uv run voz/jarvis_voz.py [--selftest]
"""

import glob
import json
import math
import os
import queue
import re
import shutil
import subprocess
import sys
import threading
import time
import wave
from pathlib import Path

# --------------------------------------------------------------------------
# Configuracion
# --------------------------------------------------------------------------

AQUI = Path(__file__).resolve().parent
CONFIG = AQUI / "config-voz.json"
ESTADO = AQUI / "estado-voz.json"

def cargar_json(p: Path, defecto: dict) -> dict:
    try:
        with open(p, "r", encoding="utf-8") as f:
            d = json.load(f)
        if isinstance(d, dict):
            return d
    except Exception:
        pass
    return dict(defecto)

def guardar_estado(d: dict) -> None:
    tmp = ESTADO.with_suffix(".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(d, f, ensure_ascii=True, indent=2)
    os.replace(tmp, ESTADO)

CFG_DEFECTO = {
    "voz_tts": "es-ES-AlvaroNeural",       # es-ES-ElviraNeural (femenina),
                                            # es-GB-RyanNeural (britanica classica)
    "modelo_whisper": "small",             # tiny/base/small/medium (mas grande = mejor y mas lento)
    "idioma_whisper": "es",
    "umbral_despertar": 0.5,               # sensibilidad de "hey jarvis" (0.3=muchos falsos, 0.8=muy estricto)
    "timeout_cerebro_s": 240,              # si el agente tarda mas, se corta y se avisa
    "carpeta_cerebro": "",                 # donde vive opencode.json con el agente jarvis (vacio = raiz del repo)
    "ruta_cli_opencode": "",               # vacio = autodescubrir
    "ruta_ffplay": "",                     # vacio = autodescubrir
}

CFG = cargar_json(CONFIG, CFG_DEFECTO)
EST = cargar_json(ESTADO, {"repliegue": False, "sesion": None})

# --------------------------------------------------------------------------
# Utilidades
# --------------------------------------------------------------------------

def log(msg: str) -> None:
    # ASCII en consola (cp1252); los acentos del codigo solo viven en el archivo.
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    print(f"[jarvis] {msg}", flush=True)

def descubrir_cli_opencode() -> str | None:
    if CFG.get("ruta_cli_opencode"):
        return CFG["ruta_cli_opencode"] if Path(CFG["ruta_cli_opencode"]).exists() else None
    base = Path(os.environ.get("LOCALAPPDATA", "")) / "Programs"
    directo = base / "ai.opencode.desktop" / "resources" / "opencode-cli.exe"
    if directo.exists():
        return str(directo)
    hitos = glob.glob(str(base / "*opencode*desktop" / "resources" / "opencode-cli.exe"))
    if hitos:
        return hitos[0]
    # Ultimo recurso: busqueda acotada (como en lanzar-sesion.ps1).
    try:
        for p in base.rglob("opencode-cli.exe"):
            return str(p)
    except Exception:
        pass
    return None

def descubrir_ffplay() -> str | None:
    if CFG.get("ruta_ffplay"):
        return CFG["ruta_ffplay"] if Path(CFG["ruta_ffplay"]).exists() else None
    en_path = shutil.which("ffplay")
    if en_path:
        return en_path
    winget = Path(os.environ.get("LOCALAPPDATA", "")) / "Microsoft" / "WinGet" / "Packages"
    try:
        for p in winget.glob("Gyan.FFmpeg*/ffmpeg-*/bin/ffplay.exe"):
            return str(p)
    except Exception:
        pass
    return None

def carpeta_cerebro() -> str:
    if CFG.get("carpeta_cerebro"):
        return CFG["carpeta_cerebro"]
    return str(AQUI.parent)   # la raiz del repo jarvis-kit (tiene opencode.json)

# --------------------------------------------------------------------------
# Boca: tonos + edge-tts + ffplay
# --------------------------------------------------------------------------

FFPLAY = descubrir_ffplay()

def _reproducir(ruta: str) -> None:
    if not FFPLAY:
        log("ffplay no encontrado; no hay audio de salida")
        return
    try:
        subprocess.run(
            [FFPLAY, "-nodisp", "-autoexit", "-loglevel", "quiet", ruta],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=120,
        )
    except Exception as e:
        log(f"error reproduciendo audio: {e}")

def _tono_wav(ruta: str, frecuencias_ms: list[tuple[float, int]], volumen: float = 0.22) -> None:
    rate = 22050
    muestras = []
    for hz, ms in frecuencias_ms:
        n = int(rate * ms / 1000)
        for i in range(n):
            env = min(1.0, i / (rate * 0.008)) * min(1.0, (n - i) / (rate * 0.02))
            muestras.append(int(volumen * 32767 * env * math.sin(2 * math.pi * hz * i / rate)))
    with wave.open(ruta, "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(rate)
        w.writeframes(b"".join(int(s).to_bytes(2, "little", signed=True) for s in muestras))

def tono(nombre: str, frecuencias_ms: list[tuple[float, int]]) -> None:
    ruta = str(AQUI / f"_tono_{nombre}_{os.getpid()}.wav")
    _tono_wav(ruta, frecuencias_ms)
    try:
        _reproducir(ruta)
    finally:
        try: os.remove(ruta)
        except OSError: pass

TONO_DESPERTO   = [(880, 90), (1320, 120)]     # "te oigo"
TONO_ERROR      = [(330, 220)]                 # "algo ha ido mal"
TONO_APAGADO    = [(1100, 90), (700, 140)]     # "hasta luego"

def limpiar_para_voz(texto: str) -> str:
    """Quita lo que suena mal al leerse en voz alta: codigo, markdown, listas."""
    t = re.sub(r"```.*?```", " ", texto, flags=re.S)
    t = re.sub(r"`[^`]*`", " ", t)
    t = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", t)      # [texto](url) -> texto
    t = re.sub(r"^#{1,6}\s*", "", t, flags=re.M)        # encabezados
    t = re.sub(r"^\s*[-*+]\s+", "", t, flags=re.M)      # viñetas
    t = re.sub(r"^\s*\d+\.\s+", "", t, flags=re.M)      # numeradas
    t = re.sub(r"[*_#>|]", " ", t)
    t = re.sub(r"\s+", " ", t).strip()
    return t

def decir(texto: str) -> None:
    limpio = limpiar_para_voz(texto)
    if not limpio:
        return
    mp3 = str(AQUI / f"_tts_{os.getpid()}.mp3")
    try:
        r = subprocess.run(
            [sys.executable, "-m", "edge_tts",
             "--voice", CFG["voz_tts"], "--rate=+4%", "--text", limpio, "--write-media", mp3],
            stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, timeout=60,
        )
        if r.returncode != 0 or not Path(mp3).exists():
            log(f"edge-tts fallo: {r.stderr.decode(errors='replace')[:200]}")
            return
        _reproducir(mp3)
    except Exception as e:
        log(f"error en decir(): {e}")
    finally:
        try: os.remove(mp3)
        except OSError: pass

# --------------------------------------------------------------------------
# Cerebro: opencode run --agent jarvis (sesion persistente)
# --------------------------------------------------------------------------

CLI = descubrir_cli_opencode()

PREFIJO_REPLIEGUE = ("[MODO REPLIEGUE del usuario: contesta en VOZ, en maximo 2 frases "
                     "cortas y naturales. Sin listas, sin markdown, sin emojis, sin codigo. ] ")
PREFIJO_NORMAL    = ("[CONTEXTO: te estan escuchando por VOZ. Contestas en voz alta: frases "
                     "naturales, sin markdown, sin listas, sin emojis, sin codigo. Un par de "
                     "frases salvo que te pidan detalle. ] ")

def preguntar_al_cerebro(mensaje: str) -> str:
    if not CLI:
        return "No encuentro el CLI de OpenCode, asi que no puedo pensar."
    prefijo = PREFIJO_REPLIEGUE if EST.get("repliegue") else PREFIJO_NORMAL
    cmd = [CLI, "run", "--agent", "jarvis", "--format", "json", "--auto"]
    if EST.get("sesion"):
        cmd += ["-s", str(EST["sesion"])]
    cmd.append(prefijo + mensaje)
    try:
        r = subprocess.run(
            cmd, cwd=carpeta_cerebro(), stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            timeout=int(CFG.get("timeout_cerebro_s", 240)), text=True, encoding="utf-8", errors="replace",
        )
    except subprocess.TimeoutExpired:
        return "He tardado demasiado en pensarlo y lo he cortado. Prueba a preguntarme otra vez."
    except Exception as e:
        return f"He tenido un problema al contactar con el cerebro: {e}"

    trozos = []
    for linea in (r.stdout or "").splitlines():
        linea = linea.strip()
        if not linea.startswith("{"):
            continue
        try:
            ev = json.loads(linea)
        except Exception:
            continue
        sid = ev.get("sessionID")
        if sid and not EST.get("sesion"):
            EST["sesion"] = sid
            guardar_estado(EST)
            log(f"sesion del cerebro: {sid}")
        if ev.get("type") == "text" and isinstance(ev.get("part"), dict):
            t = ev["part"].get("text")
            if t:
                trozos.append(t)
    if trozos:
        return " ".join(trozos).strip()
    if r.returncode != 0:
        err = (r.stderr or "").strip().splitlines()
        log(f"cerebro exit={r.returncode}: {err[-1] if err else 'sin detalle'}")
        return "El cerebro ha fallado. Mira la ventana de Jarvis para el detalle."
    return "No tengo respuesta del cerebro."

# --------------------------------------------------------------------------
# Oidos: microfono (sounddevice) + VAD por energia + whisper + wakeword
# --------------------------------------------------------------------------

SR = 16000          # whisper y openwakeword trabajan a 16 kHz
BLOQUE = 1280       # 80 ms: el trozo que espera openwakeword

import numpy as np
import sounddevice as sd

class Oidos:
    """Captura el micro a 16 kHz mono y la entrega por bloques de 80 ms."""

    def __init__(self):
        self.cola: "queue.Queue[np.ndarray]" = queue.Queue()
        self.activo = True
        self._stream = sd.InputStream(
            samplerate=SR, channels=1, dtype="int16", blocksize=BLOQUE,
            callback=self._cb,
        )

    def _cb(self, datos, frames, tiempo, estado):
        if self.activo:
            self.cola.put(datos[:, 0].copy())

    def __enter__(self):
        self._stream.start()
        return self

    def __exit__(self, *a):
        self._stream.stop(); self._stream.close()

    def vaciar(self):
        while not self.cola.empty():
            try: self.cola.get_nowait()
            except queue.Empty: break

    def escuchar_bloque(self, timeout=2.0) -> np.ndarray | None:
        try:
            return self.cola.get(timeout=timeout)
        except queue.Empty:
            return None

    def esperar_silencio_este_bloque(self) -> None:
        """Drenaje rapido: mientras Jarvis habla, NO queremos que se oiga a si mismo."""
        try:
            while not self.cola.empty():
                self.cola.get_nowait()
            self.cola.put(np.zeros(BLOQUE, dtype=np.int16))  # marca de sincronia
        except Exception:
            pass

def ruido_de_fondo(oidos: Oidos, ms: int = 400) -> float:
    muestras = []
    fin = time.time() + ms / 1000
    while time.time() < fin:
        b = oidos.escuchar_bloque(0.2)
        if b is not None:
            muestras.append(b)
    if not muestras:
        return 400.0
    x = np.concatenate(muestras).astype(np.float32)
    return float(np.sqrt(np.mean(x ** 2)))

def grabar_frase(oids: Oidos, umbral: float, silencio_s: float = 0.7,
                 max_s: float = 20.0, min_s: float = 0.4) -> np.ndarray | None:
    """Graba hasta que el usuario se calla `silencio_s` seg. Devuelve None si no hablo."""
    pcm: list[np.ndarray] = []
    silencio_seg = 0.0
    habla_seg = 0.0
    t0 = time.time()
    while time.time() - t0 < max_s:
        b = oids.escuchar_bloque(0.3)
        if b is None:
            continue
        pcm.append(b)
        rms = float(np.sqrt(np.mean(b.astype(np.float32) ** 2)))
        dur = len(b) / SR
        if rms >= umbral:
            habla_seg += dur
            silencio_seg = 0.0
        else:
            silencio_seg += dur
        if habla_seg >= min_s and silencio_seg >= silencio_s:
            break
    if habla_seg < min_s:
        return None
    return np.concatenate(pcm)

# --------------------------------------------------------------------------
# Transcripcion
# --------------------------------------------------------------------------

_WHISPER = None

def transcribir(audio: np.ndarray) -> str:
    global _WHISPER
    if _WHISPER is None:
        from faster_whisper import WhisperModel
        log(f"cargando whisper '{CFG['modelo_whisper']}' (primera vez: descarga)...")
        _WHISPER = WhisperModel(CFG["modelo_whisper"], device="cpu", compute_type="int8")
    segmentos, _ = _WHISPER.transcribe(
        audio.astype(np.float32) / 32768.0,
        language=CFG.get("idioma", CFG.get("idioma_whisper", "es")),
        vad_filter=True, beam_size=1,
    )
    return " ".join(s.text.strip() for s in segmentos).strip()

# --------------------------------------------------------------------------
# Despertar: openwakeword "hey jarvis"
# --------------------------------------------------------------------------

class Despertador:
    """Devuelve True cuando el modelo oye la palabra. Degradable a modo boton."""

    def __init__(self):
        self.modelo = None
        self.modo = "wakeword"
        try:
            from openwakeword.model import Model
            from openwakeword.utils import download_models
            try:
                download_models(["hey_jarvis"])
            except Exception:
                pass  # puede que ya esten descargados y el downloader queje por la red
            self.modelo = Model(wakeword_models=["hey_jarvis"], inference_framework="onnx")
            log("despertador 'hey jarvis' listo (onnx, local)")
        except Exception as e:
            self.modo = "boton"
            log(f"wakeword no disponible ({e}); MODO BOTON: pulsa Intro y habla")

    def escuchar(self, oidos: Oidos) -> None:
        """Bloquea hasta que se diga la palabra (o se pulse Intro en modo boton)."""
        if self.modo == "boton":
            try:
                input("    [Intro para hablar a Jarvis] ")
            except EOFError:
                time.sleep(1)
            return
        umbral = float(CFG.get("umbral_despertar", 0.5))
        consecutivos = 0
        while True:
            b = oidos.escuchar_bloque(1.0)
            if b is None:
                continue
            try:
                scores = self.modelo.predict(b)
            except Exception as e:
                log(f"error wakeword: {e}; paso a modo boton")
                self.modo = "boton"
                continue
            mejor = max(scores.values()) if scores else 0.0
            if mejor >= umbral:
                consecutivos += 1
                if consecutivos >= 2:      # 2 bloques = 160 ms: corta falsos de un frame
                    self.modelo.reset()
                    return
            else:
                consecutivos = 0

# --------------------------------------------------------------------------
# Bucle principal
# --------------------------------------------------------------------------

COMANDOS = [
    ("modo repliegue", "repliegue"),
    ("repliegue", "repliegue"),
    ("modo normal", "normal"),
    ("nueva conversacion", "nueva"),
    ("reinicia la conversacion", "nueva"),
    ("apagate", "apagar"),
    ("apágate", "apagar"),
]

def clasificar(texto: str) -> str | None:
    t = texto.lower()
    for fragmento, accion in COMANDOS:
        if fragmento in t:
            return accion
    return None

def atender(accion: str, texto: str) -> bool:
    """Gestiona los comandos de casa. Devuelve False si hay que apagarse."""
    if accion == "repliegue":
        EST["repliegue"] = True; guardar_estado(EST)
        log("modo repliegue ACTIVADO")
        decir("Modo repliegue activado. Contestare corto.")
        return True
    if accion == "normal":
        EST["repliegue"] = False; guardar_estado(EST)
        log("modo repliegue DESACTIVADO")
        decir("Modo normal. Vuelvo a contestarte con detalle.")
        return True
    if accion == "nueva":
        EST["sesion"] = None; guardar_estado(EST)
        log("nueva conversacion (sesion del cerebro reseteada)")
        decir("Entendido. Empezamos una conversacion nueva.")
        return True
    if accion == "apagar":
        tono("apagado", TONO_APAGADO)
        decir("Hasta luego.")
        return False
    # pregunta normal al cerebro
    respuesta = preguntar_al_cerebro(texto)
    log(f" -> {limpiar_para_voz(respuesta)[:160]}")
    decir(respuesta)
    return True

def bucle() -> int:
    if not CLI:
        log("ALERTA: sin CLI de OpenCode no hay cerebro. Instalalo o ajusta config-voz.json.")
    if not FFPLAY:
        log("ALERTA: sin ffplay no hay boca. Instala ffmpeg o ajusta config-voz.json.")
    log(f"cerebro en: {carpeta_cerebro()}")
    log(f"repliegue: {EST.get('repliegue', False)} | sesion: {EST.get('sesion') or 'nueva'}")

    despertador = Despertador()
    with Oidos() as oidos:
        log("midiendo el ruido de la habitacion...")
        base = ruido_de_fondo(oids)
        umbral_voz = max(base * 4.0, 500.0)
        log(f"ruido de fondo RMS={base:.0f}; umbral de voz={umbral_voz:.0f}")
        log("OK. Di 'Jarvis' cuando quieras. Ctrl+C para salir.")
        while True:
            despertador.escuchar(oids)
            log("despertado!")
            tono("despierto", TONO_DESPERTO)
            oidos.vaciar()
            audio = grabar_frase(oids, umbral_voz)
            if audio is None:
                log("no se ha oido nada; vuelvo a escuchar")
                continue
            texto = transcribir(audio)
            log(f"he oido: {texto!r}")
            if not texto:
                continue
            oidos.activo = False          # boca cerrada mientras Jarvis habla
            oidos.esperar_silencio_este_bloque()
            try:
                if not atender(clasificar(texto), texto):
                    break
            finally:
                oidos.activo = True
                oidos.vaciar()
    log("apagado. Adios.")
    return 0

# --------------------------------------------------------------------------
# Autochequeo (no necesita microfono): comprueba piezas una a una
# --------------------------------------------------------------------------

def selftest() -> int:
    fallos = 0

    def chk(nombre: str, ok: bool, detalle: str = "") -> None:
        nonlocal fallos
        log(f"  {nombre}: {'OK' if ok else 'FALLO'} {detalle}")
        if not ok:
            fallos += 1

    log("SELFTEST jarvis voz")
    chk("CLI opencode", CLI is not None, CLI or "-> no encontrado")
    chk("ffplay", FFPLAY is not None, FFPLAY or "-> no encontrado")
    chk("config", CONFIG.exists(), str(CONFIG) or "-> se usan los defectos")
    chk("estado", True, f"repliegue={EST.get('repliegue')}, sesion={'si' if EST.get('sesion') else 'no'} (se crea solo al primer cambio)")
    try:
        import sounddevice as sd
        devs = [d for d in sd.query_devices() if d["max_input_channels"] > 0]
        chk("microfonos", len(devs) > 0, f"{len(devs)} disponibles; por defecto: {sd.query_devices(kind='input')['name']}")
    except Exception as e:
        chk("sounddevice", False, str(e))
    try:
        import numpy  # noqa
        chk("numpy", True)
    except Exception as e:
        chk("numpy", False, str(e))
    try:
        from faster_whisper import WhisperModel  # noqa
        chk("faster-whisper (import)", True)
    except Exception as e:
        chk("faster-whisper (import)", False, str(e))
    try:
        import openwakeword  # noqa
        chk("openwakeword (import)", True)
    except Exception as e:
        chk("openwakeword (import)", False, f"{e} -> modo boton")
    try:
        import edge_tts  # noqa
        chk("edge-tts (import)", True)
    except Exception as e:
        chk("edge-tts (import)", False, str(e))

    if "--selftest-tts" in sys.argv:
        log("probando la voz (deberias oirme)...")
        decir("Hola. Soy Jarvis. Ya tengo voz.")

    log(f"selftest: {'TODO OK' if fallos == 0 else str(fallos) + ' fallo(s)'}")
    return 0 if fallos == 0 else 1

def prueba_despertar() -> int:
    """Prueba EN DIRECTO el oido y el despertador, sin llamar al cerebro.

    Dice 'jarvis' y comprueba si el modelo te oye. Sirve para calibrar el
    umbral y confirmar que el microfono capta tu voz antes de entrar al
    bucle completo.
    """
    despertador = Despertador()
    if despertador.modo == "boton":
        log("sin wakeword no hay prueba de despertar; usa el modo boton")
        return 1
    with Oidos() as oidos:
        base = ruido_de_fondo(oids)
        log(f"ruido de fondo RMS={base:.0f}. Di 'JARVIS' ahora (10 s)...")
        umbral = float(CFG.get("umbral_despertar", 0.5))
        t0 = time.time()
        while time.time() - t0 < 10:
            b = oidos.escuchar_bloque(0.5)
            if b is None:
                continue
            scores = despertador.modelo.predict(b)
            mejor = max(scores.values()) if scores else 0.0
            barra = "#" * int(mejor * 30)
            sys.stdout.write(f"    score={mejor:.2f} [{barra:<30}]\r")
            sys.stdout.flush()
            if mejor >= umbral:
                print()
                log("TE HE OIDO! el despertador funciona.")
                tono("despierto", TONO_DESPERTO)
                return 0
        print()
        log("no te he oido en 10 s. Baja el umbral_despertar en config-voz.json (ej. 0.35) o acercate al micro.")
        return 1

if __name__ == "__main__":
    if "--selftest" in sys.argv:
        sys.exit(selftest())
    if "--prueba-despertar" in sys.argv:
        sys.exit(prueba_despertar())
    try:
        sys.exit(bucle())
    except KeyboardInterrupt:
        log("interrumpido (Ctrl+C). Adios.")
        sys.exit(0)
