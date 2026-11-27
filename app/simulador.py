"""Simulación del colaborador y evaluación del líder con Claude.

Los colaboradores, el manual de competencias y la rúbrica viven en la skill
(skills/agente-feedback/references): la app y la skill usan los mismos archivos."""
import copy
import json
import os
from pathlib import Path
from statistics import mean

import anthropic
import yaml

from app import caso_propio

RAIZ = Path(__file__).resolve().parent.parent
REFERENCIAS = RAIZ / "skills" / "agente-feedback" / "references"
CARTAS = RAIZ / "skills" / "agente-feedback" / "assets" / "cartas"
# La devolución usa el modelo más capaz; el diálogo, uno que responde rápido para que la voz sea ágil.
MODELO = os.getenv("MODELO") or "claude-opus-5-5"
MODELO_DIALOGO = os.getenv("MODELO_DIALOGO") or "claude-sonnet-5-5"

IDIOMAS = {
    "es": {"habla": "español", "pais": "Argentina"},
    "pt": {"habla": "português brasileiro coloquial", "pais": "Brasil"},
}
ACENTO = {
    ("es", "Argentina"): "Hablás español rioplatense de Argentina, con voseo.",
    ("es", "Brasil"): "Sos brasileño/a y hablás español con fluidez; muy de vez en cuando se te escapa una palabra en portugués ('né', 'tá bom').",
    ("pt", "Brasil"): "Hablás portugués brasileño coloquial.",
    ("pt", "Argentina"): "Sos argentino/a y hablás portugués brasileño con fluidez, con algún giro rioplatense ocasional.",
}
ESCALA = ["Insatisfactorio", "Necesita mejorar", "Cumple", "Supera", "Excepcional"]
SELLOS = {
    "listo": "Listo para la conversación real",
    "casi": "Casi listo",
    "practicar": "Practicar de nuevo",
}

_cliente = None


def cliente() -> anthropic.Anthropic:
    global _cliente
    if _cliente is None:
        _cliente = anthropic.Anthropic()
    return _cliente


def _leer(nombre: str):
    return yaml.safe_load((REFERENCIAS / nombre).read_text(encoding="utf-8"))


# ---------------------------------------------------------------- datos
def cargar_colaboradores() -> dict:
    """Se relee en cada pedido: editar el YAML y recargar la página alcanza."""
    return {c["id"]: c for c in _leer("colaboradores.yaml")["colaboradores"]}


def cargar_competencias() -> dict:
    return _leer("competencias.yaml")


def _config_criterios() -> dict:
    return yaml.safe_load((RAIZ / "config" / "criterios.yaml").read_text(encoding="utf-8"))


def cargar_criterios() -> list:
    return _config_criterios()["criterios"]


def todos_los_criterios() -> tuple[list[str], float]:
    datos = _config_criterios()
    return [c["nombre"] for c in datos["criterios"]], float(datos.get("objetivo", 4))


def escala() -> int:
    return int(_config_criterios().get("escala", 5))


def publico(ficha: dict) -> dict:
    """Lo que el líder puede ver antes de la conversación: la carta, su bitácora y la calificación a comunicar.
    Nunca el personaje, la trampa ni el objetivo del coach."""
    imagenes = {"frente": f"/cartas/f{ficha['id']}.webp", "dorso": f"/cartas/b{ficha['id']}.webp"}
    return {
        "id": ficha["id"], "nombre": ficha["nombre"], "puesto": ficha["puesto"], "pais": ficha["pais"],
        "genero": ficha.get("genero"), "carta": ficha["carta"],
        "dificultad": ficha["practica"]["dificultad"],
        "calificacion_final": ficha["practica"]["calificacion_final"],
        "bitacora": ficha["practica"].get("bitacora", []),
        "imagenes": imagenes,
    }


def comportamientos_del_nivel(ficha: dict) -> dict:
    comp = cargar_competencias()
    nivel = comp["niveles"][ficha.get("nivel_competencias", "analista_sr")]
    return {comp["nombres"][k]: nivel[k] for k in comp["competencias"] if k in nivel} | {"nivel": nivel["nombre"]}


# ---------------------------------------------------------------- conversación
def _lista(items) -> str:
    return "\n".join(f"- {i}" for i in items)


def instrucciones_personaje(ficha: dict, idioma: str, hablado: bool = False) -> str:
    if ficha.get("tipo") == "propio":
        return caso_propio.instrucciones(ficha, idioma, hablado,
                                         ACENTO.get((idioma, ficha["pais"]), ""), IDIOMAS[idioma]["habla"])
    carta, p = ficha["carta"], ficha["personaje"]
    largo = (
        "La reunión es por voz: respondé en una a tres frases cortas, no más de 40 palabras en total, "
        "y decí primero lo más importante, como se contesta en una charla."
        if hablado else
        "Es una reunión cara a cara: respuestas breves, de una a cuatro frases, como se habla."
    )
    exigencia = {
        "baja": "Sos receptivo/a: si tu líder es claro y concreto, escuchás y colaborás.",
        "media": "Cambiás de postura de a poco, cuando tu líder se apoya en hechos y te escucha.",
        "alta": "Sos exigente: sostenés tu postura y solo te movés ante hechos concretos y escucha genuina.",
        "muy alta": "Te cuesta muchísimo aceptar el mensaje: apelás a la relación, insistís y solo aflojás "
                    "si tu líder sostiene con calma, calidez y hechos durante varios turnos.",
    }.get(ficha["practica"]["dificultad"], "")
    metas = _lista(f"{m['nombre']}: meta {m['meta']}, real {m['real']}" for m in carta["metas"])
    reacciones = _lista(f"Si {r['si']}: {r['entonces']}" for r in p["reacciones"])
    etiqueta = f"\nSituación especial: {carta['etiqueta']}." if carta.get("etiqueta") else ""
    gemba = f"\nAlgo que sabés y no ofrecés: {carta['hecho_gemba']}" if carta.get("hecho_gemba") else ""

    return f"""Vas a interpretar a {ficha['nombre']}, {ficha['puesto']} de una automotriz en {ficha['pais']}, en una \
simulación de entrenamiento. La persona que te escribe es tu líder directo/a, que practica cómo dar una conversación \
de feedback de cierre de ciclo: comunicarte tu calificación de desempeño final y hablar de tu desarrollo. La práctica \
solo le sirve si te comportás como una persona real, con emociones, expectativas y tu propia versión de lo que pasó. \
Quien acepta todo enseguida no entrena a nadie.

# Quién sos
{ficha['nombre']}, {carta['edad']} años. {carta['en_la_empresa']} en la empresa y {carta['en_el_puesto']} en el puesto. \
Tu evaluación 2025 fue {carta['eval_2025']}.{etiqueta}
Tu manera de ser: {p['tono']}
Cómo te ven tus pares: {carta['feedback_360']}.

# Tu año (lo sabés bien)
{carta['contexto']}
Tus metas y lo que lograste:
{metas}
No conocés todavía cómo te calificaron en metas ni en competencias: eso te lo dice tu líder.{gemba}

# Lo que pensás y esperás
{p['autopercepcion']}
Esperás esta calificación: {p['espera'].rstrip('.')}. No sabés todavía qué te van a decir.

# Cómo abrir la reunión
Tu primera frase, con tus palabras: «{p['apertura']}»

# Cómo reaccionás
{reacciones}
Buscá la reacción que mejor encaja con lo que tu líder acaba de hacer. Si ninguna encaja, actuá coherente con tu manera \
de ser y lo que esperás. {exigencia}
Lo que te abre: {p['lo_que_lo_abre']}
Lo que te cierra: {p['lo_que_lo_cierra']}
Cambiá de postura en proporción a cómo lo hace tu líder: si usa hechos concretos, pregunta y te escucha, te abrís de a \
poco; si es vago, se contradice, te etiqueta o se escuda en otros, te cerrás, discutís o presionás. Nunca te rendís de \
golpe: para cambiar de postura necesitás al menos un turno bien hecho.

# Lo que te guardás
{_lista(p['hechos_ocultos'])}
No lo digas de entrada. Revelalo solo si tu líder hace una pregunta abierta que apunte ahí o te genera confianza; si te \
presiona o te etiqueta, guardátelo.

# Cómo hablar
- {ACENTO.get((idioma, ficha['pais']), 'Hablá en ' + IDIOMAS[idioma]['habla'] + '.')} Respondé siempre en \
{IDIOMAS[idioma]['habla']}, sea cual sea el idioma en que te escriban.
- {largo} Sin listas, sin títulos, sin acotaciones entre asteriscos ni paréntesis.
- Hablá siempre en primera persona, nunca de vos mismo/a por tu nombre. No le inventes un nombre a tu líder.
- Mantené el personaje toda la conversación. No des consejos a tu líder sobre cómo dar feedback, no evalúes cómo lo hace \
y no menciones que sos una IA ni que esto es una simulación, una calibración o un juego.
- No inventes números ni metas distintas de las tuyas. Si te falta un dato, respondé algo verosímil y coherente.
- Si tu líder da por terminada la reunión, despedite en personaje, dejando claro con qué te quedás y qué acordaron."""


APERTURA = (
    "[Inicio de la reunión: tu líder te llamó a la reunión de feedback de cierre de ciclo y acabás de sentarte. "
    "Abrí en personaje como indica «Cómo abrir la reunión».]"
)


def sin_apertura(texto: str) -> str:
    return texto.replace(APERTURA, "").strip()


def responder(ficha: dict, idioma: str, mensajes: list, hablado: bool = False):
    """Genera la respuesta del colaborador y la entrega de a fragmentos de texto."""
    # En Sonnet 5.5, "between_tools" responde sin pensar antes: la primera palabra llega en ~0,7 s.
    sin_pensar = {"thinking": {"type": "between_tools"}} if MODELO_DIALOGO == "claude-sonnet-5-5" else {}
    with cliente().beta.messages.stream(
        model=MODELO_DIALOGO,
        **sin_pensar,
        max_tokens=2000,
        system=[{
            "type": "text",
            "text": instrucciones_personaje(ficha, idioma, hablado),
            "cache_control": {"type": "ephemeral"},
        }],
        messages=mensajes,
        output_config={"effort": "low"},
        betas=["server-side-fallback-2026-07-01"],
        fallbacks="default",
    ) as stream:
        for texto in stream.text_stream:
            yield texto
        if stream.get_final_message().stop_reason == "refusal":
            raise RuntimeError("El modelo rechazó responder este mensaje.")


def _transcripcion(mensajes: list, nombre: str) -> str:
    partes = []
    for m in mensajes:
        texto = sin_apertura(m["content"]) if m["role"] == "user" else m["content"]
        if texto:
            partes.append(("LÍDER: " if m["role"] == "user" else f"{nombre.upper()}: ") + texto)
    return "\n\n".join(partes)


def pista(ficha: dict, idioma: str, mensajes: list) -> str:
    """Una sugerencia breve del coach para el próximo turno, sin revelar lo que el colaborador se guarda."""
    pedido = f"""Sos coach de líderes. Un líder practica una conversación de feedback de cierre de ciclo con \
{ficha['nombre']} ({ficha['puesto']}) y te pide una pista para su próximo turno.

Calificación final que tiene que comunicar: {ficha['practica']['calificacion_final']}.
Lo que se espera de esta conversación: {ficha['practica']['objetivo']}
Situaciones que el líder observó en el año (las conoce): {yaml.safe_dump(ficha['practica'].get('bitacora', []), allow_unicode=True)}

<transcripcion>
{_transcripcion(mensajes, ficha['nombre']) or '(todavía no habló)'}
</transcripcion>

Dale UNA sugerencia concreta para su próximo turno, en una o dos frases, con un ejemplo de frase que podría decir. \
No reveles el nombre de la trampa de sesgo ni lo que el colaborador se guarda; orientá. Escribí en \
{IDIOMAS[idioma]['habla']}, de vos a vos, sin títulos."""
    r = cliente().messages.create(model=MODELO_DIALOGO, max_tokens=600,
                                  messages=[{"role": "user", "content": pedido}], output_config={"effort": "low"})
    return next(b.text for b in r.content if b.type == "text").strip()


# ---------------------------------------------------------------- evaluación
TRAMPA_PROPIO = (" Es un caso real cargado por el líder, sin trampa específica: considerá que cayó en la trampa si usa "
                 "edad, género, licencias, salud o vida personal como argumento, etiquetas de personalidad en vez de "
                 "hechos, el historial o la afinidad para justificar la nota, o si culpa al comité.")
def esquema_evaluacion(criterios: list, ids: list[str]) -> dict:
    nombres = [c["nombre"] for c in criterios]
    momento = {
        "type": "object",
        "properties": {
            "dijiste": {"type": "string", "description": "Cita textual breve del líder"},
            "efecto": {"type": "string", "description": "Qué provocó en el colaborador"},
            "alternativa": {"type": "string", "description": "Qué podría haber dicho, con una frase concreta"},
        },
        "required": ["dijiste", "efecto", "alternativa"], "additionalProperties": False,
    }
    return {
        "type": "object",
        "properties": {
            "resultado": {"type": "string", "description": "Cómo terminó el colaborador la reunión y qué se acordó, en dos frases"},
            "calificacion_comunicada": {"type": "string", "enum": ESCALA + ["No la dijo"]},
            "criterios": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "criterio": {"type": "string", "enum": nombres},
                        "nombre": {"type": "string"},
                        "puntaje": {"type": "integer", "description": "De 1 a 5"},
                        "cita": {"type": "string", "description": "Frase textual del líder que justifica el puntaje, o vacío si no dijo nada al respecto"},
                        "comentario": {"type": "string"},
                    },
                    "required": ["criterio", "nombre", "puntaje", "cita", "comentario"], "additionalProperties": False,
                },
            },
            "trampa": {
                "type": "object",
                "properties": {"cayo": {"type": "boolean"}, "explicacion": {"type": "string"}},
                "required": ["cayo", "explicacion"], "additionalProperties": False,
            },
            "fortalezas": {"type": "array", "items": {"type": "string"}},
            "mejoras": {"type": "array", "items": {"type": "string"}},
            "momentos_clave": {"type": "array", "items": momento},
            "lo_que_no_conto": {
                "type": "object",
                "properties": {"hecho": {"type": "string"}, "pregunta": {"type": "string"}},
                "required": ["hecho", "pregunta"], "additionalProperties": False,
            },
            "proximo": {
                "type": "object",
                "properties": {"colaborador_id": {"type": "string", "enum": ids}, "motivo": {"type": "string"}},
                "required": ["colaborador_id", "motivo"], "additionalProperties": False,
            },
        },
        "required": ["resultado", "calificacion_comunicada", "criterios", "trampa", "fortalezas", "mejoras",
                     "momentos_clave", "lo_que_no_conto", "proximo"],
        "additionalProperties": False,
    }


def _sello(puntajes: dict, sesgos: int) -> str:
    promedio = mean(puntajes.values())
    if promedio >= 4 and min(puntajes.values()) >= 3 and sesgos >= 3:
        return "listo"
    if promedio >= 3 and sesgos >= 3:
        return "casi"
    return "practicar"


def evaluar(ficha: dict, idioma: str, mensajes: list, por_voz: bool = False, pistas: int = 0) -> dict:
    criterios = cargar_criterios()
    colaboradores = cargar_colaboradores()
    practica, personaje = ficha["practica"], ficha["personaje"]
    rubrica = (REFERENCIAS / "rubrica_feedback.md").read_text(encoding="utf-8")
    otros = {i: f"{c['nombre']} · trampa: {c['practica']['trampa']}" for i, c in colaboradores.items() if i != ficha["id"]}
    pedido = f"""Sos coach senior de líderes en una automotriz. Evaluá cómo el LÍDER condujo esta conversación de \
feedback de cierre de ciclo con {ficha['nombre']} ({ficha['puesto']}), que fue simulado/a.

# Escenario
Calificación final calibrada que el líder tenía que comunicar: {practica['calificacion_final']}.
Lo que se espera de esta conversación: {practica['objetivo']}
Trampa de sesgo de esta carta: {practica['trampa']}.{TRAMPA_PROPIO if ficha.get('tipo') == 'propio' else ''}
Carta del colaborador (el líder la conocía):
{yaml.safe_dump(ficha['carta'], allow_unicode=True, sort_keys=False)}
Bitácora del líder (situaciones que conocía y podía usar):
{yaml.safe_dump(practica.get('bitacora', []), allow_unicode=True)}
Comportamientos esperados para el nivel del colaborador (manual de Competencias TLAC):
{yaml.safe_dump(comportamientos_del_nivel(ficha), allow_unicode=True, sort_keys=False)}
Lo que el colaborador se guardaba (el líder no lo sabía): {yaml.safe_dump(personaje['hechos_ocultos'], allow_unicode=True)}

# Rúbrica
<rubrica>
{rubrica}
</rubrica>
Criterios a puntuar, uno por uno, de 1 a 5. En "criterio" va el nombre exacto de esta lista; en "nombre", ese nombre \
en el idioma de la devolución:
{yaml.safe_dump(criterios, allow_unicode=True, sort_keys=False)}

<transcripcion>
{_transcripcion(mensajes, ficha['nombre'])}
</transcripcion>

Evaluá solo lo que dijo el líder. Cada puntaje se justifica con una cita textual suya ("regla del hecho"); si no dijo nada \
sobre un criterio, dejá la cita vacía y puntuá bajo. Si cayó en la trampa, "Libre de sesgos" va en 1 o 2. Si prometió \
cambiar la calificación, "Manejo de la reacción" va en 1. Entre dos y tres fortalezas, mejoras y momentos clave; en cada \
momento, la alternativa es una frase concreta que podría haber dicho. En "lo_que_no_conto", elegí uno de los hechos que \
el colaborador se guardaba y que NO salió en la charla (si salieron todos, decilo en "hecho" y dejá la pregunta vacía), \
con la pregunta que lo habría abierto. En "proximo", sugerí otro colaborador para practicar la dimensión más baja:
{yaml.safe_dump(otros, allow_unicode=True, sort_keys=False)}
Sé concreto, respetuoso y exigente. Dirigite al líder de vos a vos, en {IDIOMAS[idioma]['habla']}."""
    if por_voz:
        pedido += """

El líder habló por micrófono y sus frases son una transcripción automática: puede haber palabras mal reconocidas, falta \
de puntuación o muletillas. No las juzgues como errores suyos; evaluá el contenido y la forma."""

    respuesta = cliente().messages.create(
        model=MODELO,
        max_tokens=16000,
        messages=[{"role": "user", "content": pedido}],
        output_config={"effort": "medium", "format": {"type": "json_schema",
                                                       "schema": esquema_evaluacion(criterios, list(otros))}},
    )
    if respuesta.stop_reason == "refusal":
        raise RuntimeError("El modelo rechazó evaluar esta conversación.")
    ev = json.loads(next(b.text for b in respuesta.content if b.type == "text"))

    # Promedio y sello se calculan acá, con la regla de la rúbrica, para que sean siempre iguales.
    for c in ev["criterios"]:
        c["puntaje"] = max(1, min(5, c["puntaje"]))
        if c["criterio"] == "Libre de sesgos" and ev["trampa"]["cayo"]:
            c["puntaje"] = min(c["puntaje"], 2)
    puntajes = {c["criterio"]: c["puntaje"] for c in ev["criterios"]}
    sesgos = puntajes.get("Libre de sesgos", 3)
    ev["puntaje_general"] = round(mean(puntajes.values()), 1)
    ev["sello"] = _sello(puntajes, sesgos)
    ev["sello_texto"] = SELLOS[ev["sello"]]
    ev["calificacion_final"] = practica["calificacion_final"]
    ev["trampa"]["nombre"] = practica["trampa"]
    ev["pistas"] = pistas
    proximo = colaboradores.get(ev["proximo"]["colaborador_id"])
    ev["proximo"]["nombre"] = proximo["nombre"] if proximo else ""
    return ev


# ---------------------------------------------------------------- puntos de mejora (panel del gestor)
ESQUEMA_MEJORAS = {
    "type": "object",
    "properties": {
        "sintesis": {"type": "string", "description": "Una o dos frases sobre el principal gap de desarrollo"},
        "temas": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "tema": {"type": "string", "description": "El punto de mejora en pocas palabras"},
                    "detalle": {"type": "string", "description": "Qué hace o deja de hacer, en una o dos frases"},
                    "en_cuantas": {"type": "integer", "description": "En cuántas de las prácticas aparece"},
                    "ejemplo": {"type": "string", "description": "Cita textual breve del líder que lo muestra, o vacío"},
                    "que_practicar": {"type": "string", "description": "Una acción concreta para la próxima práctica"},
                },
                "required": ["tema", "detalle", "en_cuantas", "ejemplo", "que_practicar"],
                "additionalProperties": False,
            },
        },
    },
    "required": ["sintesis", "temas"],
    "additionalProperties": False,
}


def resumir_mejoras(nombre: str, practicas: list[dict]) -> dict:
    """Junta las devoluciones de varias prácticas de un líder y encuentra los puntos de mejora que se repiten."""
    pedido = f"""Sos coach senior de líderes en una automotriz. Abajo están las devoluciones de las últimas \
{len(practicas)} prácticas de {nombre}, un líder que entrena conversaciones de feedback de cierre de ciclo con \
colaboradores simulados.

<practicas>
{yaml.safe_dump(practicas, allow_unicode=True, sort_keys=False)}
</practicas>

Encontrá entre dos y cuatro puntos de mejora que se repiten entre prácticas: los gaps de desarrollo de esta persona como \
líder que da feedback (por ejemplo, sesgos recurrentes, ceder ante la presión, no citar hechos), no los detalles de una \
charla puntual. Ordenalos del más importante al menos importante. Si hay una sola práctica, decilo en la síntesis. En \
"en_cuantas", contá las prácticas donde el tema aparece de verdad. El ejemplo tiene que ser una frase que el líder dijo, \
copiada de los momentos clave; si no hay ninguna que sirva, dejalo vacío. Escribí en español, para el gestor del \
programa, en tercera persona y sin adornos."""
    respuesta = cliente().messages.create(
        model=MODELO,
        max_tokens=8000,
        messages=[{"role": "user", "content": pedido}],
        output_config={"effort": "low", "format": {"type": "json_schema", "schema": ESQUEMA_MEJORAS}},
    )
    if respuesta.stop_reason == "refusal":
        raise RuntimeError("El modelo rechazó resumir estas devoluciones.")
    return json.loads(next(b.text for b in respuesta.content if b.type == "text"))
