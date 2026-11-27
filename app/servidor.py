"""Servidor web del entrenador de feedback: sirve la página de práctica y expone la simulación."""
import hashlib
import hmac
import json
import os
import re
import uuid
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv

RAIZ = Path(__file__).resolve().parent.parent
load_dotenv(RAIZ / ".env")

import anthropic  # noqa: E402
from fastapi import FastAPI, File, HTTPException, Request, UploadFile  # noqa: E402
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse  # noqa: E402
from pydantic import BaseModel  # noqa: E402

from app import avatar, caso_propio, informes, lideres, simulador, voz  # noqa: E402

MAX_AUDIO = 15 * 1024 * 1024  # un turno hablado de varios minutos entra holgado

app = FastAPI(title="Entrenador de Feedback")
SESIONES: dict[str, dict] = {}
CARPETA_SESIONES = Path(os.getenv("DATOS_DIR") or RAIZ / "datos") / "sesiones"
MARCA_ERROR = "\n[[ERROR]] "
# Quién puede entrar, según el código que manda la página:
# - el código personal de un líder (se crean en el panel del gestor): practica a su nombre;
# - CODIGO_GESTOR: entra al panel y también puede practicar;
# - CODIGO_ACCESO: código compartido opcional, practica sin identificarse.
# Sin CODIGO_ACCESO ni CODIGO_GESTOR no hay control (uso en la propia PC).
CODIGO_ACCESO = (os.getenv("CODIGO_ACCESO") or "").strip()
CODIGO_GESTOR = (os.getenv("CODIGO_GESTOR") or "").strip()


def _igual(a: str, b: str) -> bool:
    return bool(a and b) and hmac.compare_digest(a.encode(), b.encode())


@app.middleware("http")
async def identificar(request: Request, call_next):
    ruta = request.url.path
    if not ruta.startswith("/api/"):
        return await call_next(request)
    codigo = request.headers.get("x-codigo", "").strip()
    rol, lider = None, None
    if _igual(codigo, CODIGO_GESTOR):
        rol = "gestor"
    elif codigo and (lider := lideres.por_codigo(codigo)):
        rol = "lider"
    elif _igual(codigo, CODIGO_ACCESO):
        rol = "invitado"
    elif not CODIGO_ACCESO and not CODIGO_GESTOR:
        rol = "local"
    if rol is None:
        return JSONResponse({"detail": "Código de acceso incorrecto."}, status_code=401)
    if ruta.startswith("/api/gestor/") and rol not in ("gestor", "local"):
        return JSONResponse({"detail": "Esta sección es solo para el gestor."}, status_code=403)
    request.state.rol, request.state.lider = rol, lider
    return await call_next(request)


def explicar_error(e: Exception) -> str:
    """Mensaje en lenguaje llano para mostrar en pantalla."""
    if isinstance(e, anthropic.AuthenticationError) or "api_key" in str(e) or "auth" in str(e).lower():
        return "Falta la clave de Anthropic o no es válida. Revisá ANTHROPIC_API_KEY en el archivo .env."
    if isinstance(e, anthropic.RateLimitError):
        return "Se alcanzó el límite de uso de la cuenta de Anthropic. Esperá un minuto y reintentá."
    if isinstance(e, anthropic.APIConnectionError):
        return "No se pudo conectar con Anthropic. Revisá la conexión a internet."
    if isinstance(e, anthropic.APIStatusError):
        return f"Anthropic devolvió un error ({e.status_code}): {e.message}"
    return str(e)


def guardar(sesion: dict) -> None:
    CARPETA_SESIONES.mkdir(parents=True, exist_ok=True)
    (CARPETA_SESIONES / f"{sesion['id']}.json").write_text(
        json.dumps(sesion, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def cargar(sesion_id: str) -> dict:
    if sesion_id not in SESIONES:
        # Tras un reinicio del servidor, la sesión se recupera del archivo guardado.
        ruta = CARPETA_SESIONES / f"{sesion_id}.json"
        if not re.fullmatch(r"[0-9a-f-]+", sesion_id) or not ruta.exists():
            raise HTTPException(404, "La sesión no existe. Empezá una nueva.")
        SESIONES[sesion_id] = json.loads(ruta.read_text(encoding="utf-8"))
    return SESIONES[sesion_id]


def buscar(sesion_id: str, request: Request) -> dict:
    """La sesión, solo si es de quien la pide: un líder no puede seguir la práctica de otro."""
    sesion = cargar(sesion_id)
    lider = request.state.lider
    if sesion.get("lider_id") and (not lider or lider["id"] != sesion["lider_id"]):
        if request.state.rol not in ("gestor", "local"):
            raise HTTPException(404, "La sesión no existe. Empezá una nueva.")
    return sesion


class NuevaSesion(BaseModel):
    colaborador_id: str = ""  # una carta de HR…
    caso: caso_propio.CasoPropio | None = None  # …o un caso propio
    idioma: str = "es"
    nombre: str = ""


class Mensaje(BaseModel):
    texto: str = ""
    por_voz: bool = False  # el líder habló por micrófono
    hablado: bool = False  # la voz del colaborador está activa: respuestas más cortas


class PedidoVoz(BaseModel):
    texto: str = ""  # una frase de la respuesta del colaborador; vacío = la última respuesta entera
    formato: str = "mp3"  # "pcm" cuando la voz va al avatar


class NuevoLider(BaseModel):
    nombre: str
    pais: str


class CambioLider(BaseModel):
    activo: bool | None = None
    nuevo_codigo: bool = False


# Que el navegador pida siempre la página actual: así, después de publicar un cambio, nadie ve la vieja.
SIN_CACHE = {"Cache-Control": "no-cache"}


@app.get("/")
def pagina():
    return FileResponse(RAIZ / "web" / "index.html", headers=SIN_CACHE)


@app.get("/gestor")
def pagina_gestor():
    return FileResponse(RAIZ / "web" / "gestor.html", headers=SIN_CACHE)


@app.get("/cartas/{archivo}")
def carta(archivo: str):
    """Las imágenes originales de las cartas (fNN frente, bNN dorso)."""
    if not re.fullmatch(r"[fb]\d{2}\.webp", archivo) or not (simulador.CARTAS / archivo).exists():
        raise HTTPException(404, "No existe esa carta.")
    return FileResponse(simulador.CARTAS / archivo, headers={"Cache-Control": "max-age=86400"})


@app.get("/api/config")
def config(request: Request):
    lider = request.state.lider
    return {
        "voz": voz.disponible(),
        "avatar": voz.disponible() and avatar.disponible(),
        "rol": request.state.rol,
        "lider": {"nombre": lider["nombre"], "pais": lider["pais"]} if lider else None,
    }


@app.get("/api/colaboradores")
def colaboradores():
    return [simulador.publico(c) for c in simulador.cargar_colaboradores().values()]


@app.get("/api/caso-propio")
def opciones_caso_propio():
    """Las opciones del formulario de caso propio."""
    return {
        "seniority": [{"id": k, "nombre": v[0], "nivel": v[1], "liderazgo": k in caso_propio.CON_LIDERAZGO}
                      for k, v in caso_propio.SENIORITY.items()],
        "aperturas": [{"id": k, "nombre": caso_propio.NOMBRES_APERTURA[k], "descripcion": v["tono"]}
                      for k, v in caso_propio.APERTURAS.items()],
        "competencias": caso_propio.COMPETENCIAS,
        "bandas": caso_propio.BANDAS,
        "max_objetivos": caso_propio.MAX_OBJETIVOS,
    }


@app.get("/api/competencias")
def competencias():
    return simulador.cargar_competencias()


@app.post("/api/sesiones")
def crear_sesion(datos: NuevaSesion, request: Request):
    if datos.idioma not in simulador.IDIOMAS:
        raise HTTPException(400, "Idioma inválido.")
    if datos.caso:
        if error := caso_propio.validar(datos.caso):
            raise HTTPException(400, error)
        ficha = caso_propio.armar_ficha(datos.caso, datos.idioma)
    else:
        fichas = simulador.cargar_colaboradores()
        if datos.colaborador_id not in fichas:
            raise HTTPException(400, "Colaborador inválido.")
        ficha = fichas[datos.colaborador_id]
    lider = request.state.lider
    sesion = {
        "id": datetime.now().strftime("%Y%m%d-%H%M%S-") + uuid.uuid4().hex[:6],
        "inicio": datetime.now().isoformat(timespec="seconds"),
        "lider_id": lider["id"] if lider else None,
        "lider": lider["nombre"] if lider else datos.nombre.strip(),
        "idioma": datos.idioma,
        "colaborador_id": ficha["id"],
        "ficha": ficha,  # copia de la ficha usada, por si después se edita
        "mensajes": [],
        "pistas": [],
        "evaluacion": None,
    }
    SESIONES[sesion["id"]] = sesion
    return {"id": sesion["id"], "colaborador": sesion["ficha"]["nombre"]}


@app.post("/api/sesiones/{sesion_id}/mensaje")
def mensaje(sesion_id: str, datos: Mensaje, request: Request):
    """Recibe lo que dijo el líder y devuelve la respuesta del colaborador a medida que se genera.
    Con la conversación vacía, el colaborador abre la reunión."""
    sesion = buscar(sesion_id, request)
    texto = datos.texto.strip()
    if not sesion["mensajes"]:
        # Si la apertura había fallado y el líder escribe igual, su texto va después de ella.
        texto = simulador.APERTURA + ("\n\n" + texto if texto else "")
    elif not texto:
        raise HTTPException(400, "El mensaje está vacío.")
    pendientes = sesion["mensajes"] + [{"role": "user", "content": texto}]
    if datos.por_voz:
        sesion["por_voz"] = True

    def generar():
        partes = []
        sesion["en_curso"] = ""
        try:
            for fragmento in simulador.responder(sesion["ficha"], sesion["idioma"], pendientes, datos.hablado):
                partes.append(fragmento)
                # Antes de mandar el fragmento, para que la página pueda pedir la voz de esa frase.
                sesion["en_curso"] = "".join(partes)
                yield fragmento
        except Exception as e:  # el error viaja dentro de la respuesta ya iniciada
            yield MARCA_ERROR + explicar_error(e)
            return
        finally:
            sesion.pop("en_curso", None)
        sesion["mensajes"] = pendientes + [{"role": "assistant", "content": "".join(partes)}]
        guardar(sesion)

    return StreamingResponse(generar(), media_type="text/plain; charset=utf-8")


def exigir_voz():
    if not voz.disponible():
        raise HTTPException(503, "La voz no está configurada: falta ELEVENLABS_API_KEY.")


@app.post("/api/sesiones/{sesion_id}/transcripcion")
def transcripcion(sesion_id: str, request: Request, audio: UploadFile = File(...)):
    """Convierte en texto lo que dijo el líder. No lo agrega a la conversación:
    la página lo muestra y lo envía como un mensaje más."""
    exigir_voz()
    sesion = buscar(sesion_id, request)
    datos = audio.file.read(MAX_AUDIO + 1)
    if len(datos) > MAX_AUDIO:
        raise HTTPException(413, "El audio es demasiado largo.")
    try:
        texto = voz.transcribir(datos, audio.filename or "audio.webm", audio.content_type, sesion["idioma"])
    except voz.ErrorVoz as e:
        raise HTTPException(502, str(e))
    return {"texto": texto}


@app.post("/api/sesiones/{sesion_id}/voz")
def voz_del_colaborador(sesion_id: str, request: Request, pedido: PedidoVoz | None = None):
    """Devuelve en audio una frase de la respuesta del colaborador, mientras se genera o ya terminada.
    Solo pone voz a lo que dijo el colaborador: no sirve para leer cualquier texto."""
    exigir_voz()
    sesion = buscar(sesion_id, request)
    ultimo = next((m["content"] for m in reversed(sesion["mensajes"]) if m["role"] == "assistant"), "")
    frase = (pedido.texto if pedido else "").strip()
    previo = ""
    if frase:
        for respuesta in (sesion.get("en_curso", ""), ultimo):
            posicion = respuesta.find(frase)
            if posicion >= 0:
                previo = respuesta[:posicion]
                break
        else:
            raise HTTPException(400, "Esa frase no es parte de la respuesta del colaborador.")
    else:
        frase = ultimo
    if not frase:
        raise HTTPException(400, "Todavía no hay respuesta del colaborador.")
    formato = pedido.formato if pedido else "mp3"
    if formato not in voz.FORMATOS:
        raise HTTPException(400, "Formato de audio inválido.")
    try:
        audio = voz.abrir_audio(frase, sesion["ficha"], sesion["idioma"], previo, formato)
    except voz.ErrorVoz as e:
        raise HTTPException(502, str(e))
    return StreamingResponse(audio, media_type="audio/mpeg" if formato == "mp3" else "application/octet-stream")


@app.post("/api/sesiones/{sesion_id}/avatar")
def avatar_del_colaborador(sesion_id: str, request: Request):
    """Permiso para que el navegador conecte el avatar con la cara de este colaborador."""
    if not avatar.disponible():
        raise HTTPException(503, "El avatar no está configurado: falta SIMLI_API_KEY.")
    sesion = buscar(sesion_id, request)
    try:
        return {"session_token": avatar.pedir_sesion(sesion["ficha"])}
    except avatar.ErrorAvatar as e:
        raise HTTPException(502, str(e))


@app.post("/api/sesiones/{sesion_id}/pista")
def pista(sesion_id: str, request: Request):
    """Una sugerencia del coach para el próximo turno. Queda registrada en la práctica."""
    sesion = buscar(sesion_id, request)
    try:
        texto = simulador.pista(sesion["ficha"], sesion["idioma"], sesion["mensajes"])
    except Exception as e:
        raise HTTPException(502, explicar_error(e))
    sesion.setdefault("pistas", []).append({"turno": len(sesion["mensajes"]), "texto": texto})
    guardar(sesion)
    return {"texto": texto}


@app.post("/api/sesiones/{sesion_id}/evaluacion")
def evaluacion(sesion_id: str, request: Request):
    sesion = buscar(sesion_id, request)
    if len(sesion["mensajes"]) < 4:
        raise HTTPException(400, "La conversación es muy corta para evaluarla.")
    try:
        sesion["evaluacion"] = simulador.evaluar(
            sesion["ficha"], sesion["idioma"], sesion["mensajes"], sesion.get("por_voz", False),
            len(sesion.get("pistas", []))
        )
    except Exception as e:
        raise HTTPException(502, explicar_error(e))
    guardar(sesion)
    return sesion["evaluacion"]


# ---------------------------------------------------------------- panel del gestor
@app.get("/api/gestor/resumen")
def gestor_resumen(dificultad: str | None = None):
    if dificultad and dificultad not in informes.NIVELES:
        raise HTTPException(400, "Complejidad inválida.")
    return informes.resumen(informes.leer_sesiones(CARPETA_SESIONES), lideres.listar(), dificultad or None)


@app.get("/api/gestor/sesiones/{sesion_id}")
def gestor_sesion(sesion_id: str):
    return informes.detalle(cargar(sesion_id))


@app.get("/api/gestor/lideres")
def gestor_lideres():
    return lideres.listar()


@app.post("/api/gestor/lideres")
def gestor_alta(datos: NuevoLider):
    if not datos.nombre.strip() or datos.pais not in ("ar", "br"):
        raise HTTPException(400, "Completá el nombre y elegí el país.")
    if any(c["nombre"].lower() == datos.nombre.strip().lower() for c in lideres.listar()):
        raise HTTPException(400, "Ya hay un líder con ese nombre.")
    return lideres.crear(datos.nombre, datos.pais)


@app.post("/api/gestor/lideres/{lider_id}")
def gestor_cambio(lider_id: str, datos: CambioLider):
    lider = lideres.actualizar(lider_id, activo=datos.activo, nuevo_codigo=datos.nuevo_codigo)
    if not lider:
        raise HTTPException(404, "Ese líder no existe.")
    return lider


# Resúmenes de puntos de mejora: se guardan para no volver a pagar la IA si no hay prácticas nuevas.
CARPETA_MEJORAS = Path(os.getenv("DATOS_DIR") or RAIZ / "datos") / "mejoras"


def _ruta_mejoras(clave: str) -> Path:
    return CARPETA_MEJORAS / (hashlib.sha1(clave.encode()).hexdigest()[:16] + ".json")


def _estado_mejoras(clave: str):
    sesiones = informes.leer_sesiones(CARPETA_SESIONES)
    _, objetivo = simulador.todos_los_criterios()
    ids, practicas = informes.insumos_mejoras(clave, sesiones, objetivo)
    ruta = _ruta_mejoras(clave)
    guardado = json.loads(ruta.read_text(encoding="utf-8")) if ruta.exists() else None
    return ids, practicas, guardado


@app.get("/api/gestor/mejoras")
def gestor_mejoras(clave: str):
    ids, _, guardado = _estado_mejoras(clave)
    if guardado:
        guardado["desactualizado"] = guardado["basado_en"] != ids
    return {"practicas_disponibles": len(ids), "resumen": guardado}


@app.post("/api/gestor/mejoras")
def gestor_resumir_mejoras(clave: str):
    ids, practicas, guardado = _estado_mejoras(clave)
    if not practicas:
        raise HTTPException(400, "Este líder todavía no tiene prácticas con devolución.")
    if guardado and guardado["basado_en"] == ids:
        return {"practicas_disponibles": len(ids), "resumen": {**guardado, "desactualizado": False}}
    nombre = next((p["nombre"] for p in informes.resumen(informes.leer_sesiones(CARPETA_SESIONES),
                   lideres.listar())["lideres"] if p["clave"] == clave), "el líder")
    try:
        resumen = simulador.resumir_mejoras(nombre, practicas)
    except Exception as e:
        raise HTTPException(502, explicar_error(e))
    guardado = {**resumen, "basado_en": ids, "fecha": datetime.now().isoformat(timespec="seconds")}
    CARPETA_MEJORAS.mkdir(parents=True, exist_ok=True)
    _ruta_mejoras(clave).write_text(json.dumps(guardado, ensure_ascii=False, indent=2), encoding="utf-8")
    return {"practicas_disponibles": len(ids), "resumen": {**guardado, "desactualizado": False}}
