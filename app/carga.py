"""Modo de prueba de carga (MODO_CARGA=1): reemplaza a Claude, ElevenLabs y Simli por respuestas
simuladas con demoras parecidas a las reales. Sirve para medir cuántas conversaciones en paralelo
aguanta el servidor sin gastar en los proveedores. Nunca activarlo en el servicio que usan los líderes."""
import os
import time

# Demoras simuladas (segundos), ajustables por variable de entorno.
PRIMERA_PALABRA = float(os.getenv("CARGA_PRIMERA_PALABRA", "0.8"))   # Claude Sonnet: hasta el primer fragmento
FRAGMENTO = float(os.getenv("CARGA_FRAGMENTO", "0.05"))              # entre fragmentos del texto
VOZ = float(os.getenv("CARGA_VOZ", "1.5"))                           # ElevenLabs: audio de una frase
TRANSCRIPCION = float(os.getenv("CARGA_TRANSCRIPCION", "1.0"))       # ElevenLabs: pasar audio a texto
EVALUACION = float(os.getenv("CARGA_EVALUACION", "15"))              # Claude Opus: devolución completa

RESPUESTA = ("Mirá, la verdad que este año trabajé muchísimo y esperaba otra cosa. "
             "¿Me podés explicar qué fue lo que más pesó? Quiero entenderlo bien.")


def activo() -> bool:
    return os.getenv("MODO_CARGA") == "1"


def activar(simulador, voz, avatar) -> None:
    def responder(ficha, idioma, mensajes, hablado=False):
        time.sleep(PRIMERA_PALABRA)
        for palabra in RESPUESTA.split(" "):
            time.sleep(FRAGMENTO)
            yield palabra + " "

    def pista(ficha, idioma, mensajes):
        time.sleep(2)
        return "Pista simulada: preguntale qué fue lo que más le costó del año."

    def evaluar(ficha, idioma, mensajes, por_voz=False, pistas=0):
        time.sleep(EVALUACION)
        criterios = [{"criterio": c["nombre"], "nombre": c["nombre"], "puntaje": 3, "cita": "", "comentario": "Simulado."}
                     for c in simulador.cargar_criterios()]
        return {"resultado": "Simulado.", "calificacion_comunicada": "Cumple", "criterios": criterios,
                "trampa": {"cayo": False, "explicacion": "Simulado.", "nombre": "Simulada"},
                "fortalezas": [], "mejoras": [], "momentos_clave": [],
                "lo_que_no_conto": {"hecho": "", "pregunta": ""}, "proximo": {"colaborador_id": "01", "motivo": "", "nombre": ""},
                "puntaje_general": 3.0, "sello": "casi", "sello_texto": "Casi listo",
                "calificacion_final": ficha["practica"]["calificacion_final"], "pistas": pistas}

    def abrir_audio(texto, ficha, idioma, previo="", formato="mp3"):
        time.sleep(VOZ / 3)  # hasta el primer byte

        def trozos():
            for _ in range(10):
                time.sleep(VOZ * 2 / 30)
                yield b"\0" * 3200
        return trozos()

    def transcribir(audio, nombre, tipo, idioma):
        time.sleep(TRANSCRIPCION)
        return "Te quería contar cómo fue tu evaluación de este año."

    simulador.responder, simulador.pista, simulador.evaluar = responder, pista, evaluar
    voz.abrir_audio, voz.transcribir, voz.disponible = abrir_audio, transcribir, (lambda: True)
    avatar.pedir_sesion, avatar.disponible = (lambda ficha: "token-simulado"), (lambda: True)
