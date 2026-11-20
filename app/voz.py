"""Voz con ElevenLabs: transcribe lo que dice el líder y pone voz al colaborador."""
import os
from pathlib import Path

import httpx
import yaml

RAIZ = Path(__file__).resolve().parent.parent
API = "https://api.elevenlabs.io/v1"
PAISES = {"Argentina": "ar", "Brasil": "br"}


class ErrorVoz(Exception):
    pass


def _clave() -> str:
    return (os.getenv("ELEVENLABS_API_KEY") or "").strip()


def disponible() -> bool:
    return bool(_clave())


def _config() -> dict:
    return yaml.safe_load((RAIZ / "config" / "voces.yaml").read_text(encoding="utf-8"))


def _explicar(r: httpx.Response) -> str:
    try:
        detalle = r.json().get("detail")
        if isinstance(detalle, dict):
            detalle = detalle.get("message") or detalle.get("status")
        elif isinstance(detalle, list):
            detalle = "; ".join(str(d.get("msg", d)) for d in detalle)
    except Exception:
        detalle = r.text[:300]
    if r.status_code == 401:
        return "La clave de ElevenLabs falta o no es válida. Revisá ELEVENLABS_API_KEY."
    if r.status_code == 429:
        return "ElevenLabs está saturado o se alcanzó el límite del plan. Probá en un momento."
    return f"ElevenLabs devolvió un error ({r.status_code}): {detalle}"


def voz_para(ficha: dict) -> str:
    """La voz sale del país y el género del colaborador; una ficha puede traer la suya en `voz`."""
    if ficha.get("voz"):
        return ficha["voz"]
    genero = "mujer" if ficha.get("genero") == "f" else "hombre"
    return _config()[PAISES.get(ficha.get("pais"), "ar")][genero]


FORMATOS = {
    "mp3": "mp3_44100_64",
    "pcm": "pcm_16000",  # PCM de 16 bits, 16 kHz, mono: lo que recibe el avatar de Simli
}


def abrir_audio(texto: str, ficha: dict, idioma: str, previo: str = "", formato: str = "mp3"):
    """Pide la voz del colaborador a ElevenLabs. Devuelve un iterador de bytes de audio, o falla antes de empezar.
    `previo` es lo que el colaborador ya dijo en esta respuesta: mantiene la entonación entre frases."""
    cuerpo = {
        "text": texto,
        "model_id": _config()["modelo_voz"],
        "language_code": idioma,
        "apply_text_normalization": "on",  # que lea bien montos, porcentajes y fechas
    }
    if previo.strip():
        cuerpo["previous_text"] = previo.strip()[-1000:]
    cliente = httpx.Client(timeout=httpx.Timeout(30.0, connect=10.0))
    pedido = cliente.build_request(
        "POST",
        f"{API}/text-to-speech/{voz_para(ficha)}/stream",
        params={"output_format": FORMATOS[formato]},
        headers={"xi-api-key": _clave()},
        json=cuerpo,
    )
    try:
        respuesta = cliente.send(pedido, stream=True)
        if respuesta.status_code in (400, 404) and ficha.get("voz"):
            # La voz propia del colaborador no está en la cuenta: se usa la del país y el género.
            respuesta.read()
            respuesta.close()
            genero = "mujer" if ficha.get("genero") == "f" else "hombre"
            defecto = _config()[PAISES.get(ficha.get("pais"), "ar")][genero]
            pedido = cliente.build_request("POST", f"{API}/text-to-speech/{defecto}/stream",
                                           params={"output_format": FORMATOS[formato]},
                                           headers={"xi-api-key": _clave()}, json=cuerpo)
            respuesta = cliente.send(pedido, stream=True)
    except httpx.HTTPError as e:
        cliente.close()
        raise ErrorVoz(f"No se pudo conectar con ElevenLabs: {e}")
    if respuesta.status_code != 200:
        respuesta.read()
        mensaje = _explicar(respuesta)
        respuesta.close()
        cliente.close()
        raise ErrorVoz(mensaje)

    def bytes_de_audio():
        try:
            yield from respuesta.iter_bytes()
        finally:
            respuesta.close()
            cliente.close()

    return bytes_de_audio()


def transcribir(audio: bytes, nombre: str, tipo: str, idioma: str) -> str:
    try:
        r = httpx.post(
            f"{API}/speech-to-text",
            headers={"xi-api-key": _clave()},
            data={
                "model_id": _config()["modelo_transcripcion"],
                "language_code": idioma,
                "tag_audio_events": "false",
            },
            files={"file": (nombre, audio, tipo or "application/octet-stream")},
            timeout=httpx.Timeout(60.0, connect=10.0),
        )
    except httpx.HTTPError as e:
        raise ErrorVoz(f"No se pudo conectar con ElevenLabs: {e}")
    if r.status_code != 200:
        raise ErrorVoz(_explicar(r))
    return (r.json().get("text") or "").strip()
