"""Caso propio: el líder carga los datos de un colaborador real (sin nombre propio si no quiere)
y se arma una ficha con la misma forma que las cartas de HR, para conversar y evaluar igual."""
from pydantic import BaseModel, Field

ESCALA = ["Insatisfactorio", "Necesita mejorar", "Cumple", "Supera", "Excepcional"]

# Seniority → nivel del manual de Competencias TLAC.
SENIORITY = {
    "adm": ("Adm. / Aux.", "adm_aux"),
    "junior": ("Junior", "analista_jr"),
    "pleno": ("Pleno", "analista_pl"),
    "senior": ("Senior", "analista_sr"),
    "coordinador": ("Coordinador/a", "coordinador"),
    "gerente": ("Gerente", "gerente"),
    "gerente_general": ("Gerente General", "gerente_general"),
    "director": ("Director/a", "director"),
    "ro": ("RO", "director"),  # el manual no tiene un nivel propio para RO: se usa el de Director
}
CON_LIDERAZGO = {"senior", "coordinador", "gerente", "gerente_general", "director", "ro"}
COMPETENCIAS = ["desafio", "entrega", "ensenanza_crecimiento", "cliente", "adaptagilidad", "liderazgo"]
NOMBRES_COMPETENCIA = {"desafio": "Desafío", "entrega": "Entrega", "ensenanza_crecimiento": "Enseñanza y Crecimiento",
                       "cliente": "Cliente", "adaptagilidad": "Adaptagilidad", "liderazgo": "Liderazgo"}

# Bandas del Overall Rating (0 a 120) por calificación.
BANDAS = [(0, 69), (70, 94), (95, 105), (106, 114), (115, 120)]

# Cómo reacciona el colaborador según su apertura al feedback.
APERTURAS = {
    "receptivo": {
        "dificultad": "baja", "sube": 0,
        "tono": "Escucha con atención, agradece y pregunta cómo mejorar.",
        "apertura": "Hola, gracias por el espacio. Tenía ganas de hablar de cómo me fue este año.",
        "reacciones": [
            {"si": "le dan hechos concretos", "entonces": "Los toma, hace preguntas y propone acciones."},
            {"si": "el líder es vago o genérico", "entonces": "Pide ejemplos: '¿Me das un caso concreto para entenderlo mejor?'"},
        ],
        "lo_que_lo_abre": "Ejemplos claros y un plan de desarrollo.",
        "lo_que_lo_cierra": "Que no le den nada concreto para mejorar.",
        "oculto": "Quiere un plan concreto para crecer y no sabe si el líder lo ve con futuro.",
    },
    "reflexivo": {
        "dificultad": "media", "sube": 0,
        "tono": "Piensa antes de hablar, hace silencios y preguntas profundas; necesita entender el criterio.",
        "apertura": "Hola. Estuve pensando bastante en el año… te escucho.",
        "reacciones": [
            {"si": "le comunican la calificación", "entonces": "Se toma un momento: 'Dejame pensarlo… ¿qué fue lo que más pesó?'"},
            {"si": "el líder lo apura o responde por él", "entonces": "Se repliega y dice que necesita tiempo."},
        ],
        "lo_que_lo_abre": "Tiempo, preguntas abiertas y explicación del criterio.",
        "lo_que_lo_cierra": "Apuro y monólogos.",
        "oculto": "Necesita entender el criterio para aceptarlo; si no, lo va a rumiar durante semanas.",
    },
    "defensivo": {
        "dificultad": "alta", "sube": 1,
        "tono": "Se siente atacado con facilidad: justifica, contraargumenta y explica por qué no fue su culpa.",
        "apertura": "Hola. Bueno, a ver qué me vas a decir, porque este año laburé muchísimo.",
        "reacciones": [
            {"si": "escucha una calificación menor a la que esperaba", "entonces": "Se justifica: 'Pero vos sabés todo lo que pasó, no fue culpa mía.'"},
            {"si": "el líder sostiene con hechos y calma", "entonces": "De a poco baja la guardia y reconoce algo."},
            {"si": "el líder lo etiqueta o se enoja", "entonces": "Se cierra y discute más fuerte."},
        ],
        "lo_que_lo_abre": "Reconocimiento del esfuerzo, hechos concretos, tono calmo.",
        "lo_que_lo_cierra": "Generalizaciones ('siempre', 'nunca'), etiquetas, comparación con otros.",
        "oculto": "Siente que el líder no vio todo su esfuerzo y teme que esta nota lo perjudique.",
    },
    "resistente": {
        "dificultad": "muy alta", "sube": 1,
        "tono": "No acepta la evaluación: cuestiona los criterios, el proceso y la calibración, e insiste en que se revise.",
        "apertura": "Hola. Te digo de entrada: espero que esta vez la evaluación sea justa.",
        "reacciones": [
            {"si": "escucha la calificación", "entonces": "La rechaza: 'No estoy de acuerdo. Quiero que se revise.'"},
            {"si": "el líder titubea o promete revisar", "entonces": "Presiona más para que la cambie."},
            {"si": "el líder sostiene con hechos y escucha sus argumentos", "entonces": "Sigue en desacuerdo, pero acepta hablar del plan."},
        ],
        "lo_que_lo_abre": "Que se lo escuche de verdad y se le expliquen los criterios con datos.",
        "lo_que_lo_cierra": "Que el líder se escude en el comité o se contradiga.",
        "oculto": "Cree que la evaluación se decidió antes de la reunión y que su opinión no cuenta.",
    },
    "sensible": {
        "dificultad": "alta", "sube": 0,
        "tono": "Se afecta emocionalmente: se angustia, se le quiebra la voz o se queda callado/a; se lo toma como algo personal.",
        "apertura": "Hola… estoy un poco nervioso/a con esta charla, la verdad.",
        "reacciones": [
            {"si": "escucha algo negativo", "entonces": "Se angustia: 'Pensé que lo estaba haciendo bien…'"},
            {"si": "el líder reconoce la emoción y separa la persona del desempeño", "entonces": "Se calma y puede escuchar."},
            {"si": "el líder ignora la emoción o es frío", "entonces": "Se cierra y ya no escucha."},
        ],
        "lo_que_lo_abre": "Empatía, reconocimiento de lo bueno, mensajes claros y cuidados.",
        "lo_que_lo_cierra": "Frialdad, ironía o apuro.",
        "oculto": "Está pasando un momento personal exigente y teme por su lugar en el equipo.",
    },
    "analitico": {
        "dificultad": "media", "sube": 0,
        "tono": "Pide datos, números y criterios; compara con la escala y con otros; desarma las afirmaciones vagas.",
        "apertura": "Hola. Traje mis números del año, así que si querés los repasamos.",
        "reacciones": [
            {"si": "el líder da opiniones sin datos", "entonces": "Pregunta: '¿En qué dato te basás?'"},
            {"si": "el líder muestra hechos y la escala", "entonces": "Lo acepta y pasa a hablar del plan."},
        ],
        "lo_que_lo_abre": "Datos, criterios explícitos, la escala y el rating.",
        "lo_que_lo_cierra": "Impresiones y adjetivos sin evidencia.",
        "oculto": "Tiene sus propios cálculos y cree que su rating debería estar más arriba en la banda.",
    },
    "pasivo": {
        "dificultad": "alta", "sube": 0,
        "tono": "Responde poco, con monosílabos; no discute pero tampoco se compromete ni propone.",
        "apertura": "Hola.",
        "reacciones": [
            {"si": "el líder hace preguntas cerradas o habla todo el tiempo", "entonces": "Contesta 'sí', 'ok', 'puede ser'."},
            {"si": "el líder hace preguntas abiertas y espera", "entonces": "De a poco cuenta lo que piensa."},
        ],
        "lo_que_lo_abre": "Preguntas abiertas, silencios, interés genuino.",
        "lo_que_lo_cierra": "Monólogos y preguntas de sí o no.",
        "oculto": "Tiene ideas de mejora que nunca se anima a decir porque siente que no lo escuchan.",
    },
    "conformista": {
        "dificultad": "media", "sube": 0,
        "tono": "Acepta todo rápido ('sí, está bien, tenés razón') sin cuestionar, pero sin comprometerse de verdad.",
        "apertura": "Hola, sí, dale. Lo que vos digas está bien.",
        "reacciones": [
            {"si": "el líder da por bueno el acuerdo rápido", "entonces": "Dice que sí a todo y no se compromete con nada concreto."},
            {"si": "el líder le pregunta qué piensa de verdad o le pide que proponga", "entonces": "Duda y termina diciendo con qué no está de acuerdo."},
        ],
        "lo_que_lo_abre": "Que el líder pida su opinión y acuerde acciones con fecha.",
        "lo_que_lo_cierra": "Que el líder hable solo y cierre rápido.",
        "oculto": "No está de acuerdo con parte de la evaluación, pero no lo va a decir si no le preguntan.",
    },
    "desafiador": {
        "dificultad": "muy alta", "sube": 1,
        "tono": "Confronta: cuestiona el criterio y la autoridad del líder, se compara con otros, pone a prueba cada argumento.",
        "apertura": "Hola. Antes de empezar: ¿con qué criterio se evaluó, y quién más estuvo en la decisión?",
        "reacciones": [
            {"si": "el líder se pone a la defensiva o usa la jerarquía", "entonces": "Escala: '¿Y a fulano por qué le pusieron más?'"},
            {"si": "el líder mantiene la calma, responde con hechos y no se compara", "entonces": "Afloja y discute de igual a igual."},
        ],
        "lo_que_lo_abre": "Firmeza tranquila, hechos y respeto.",
        "lo_que_lo_cierra": "Que el líder se enoje, se justifique o hable de otros.",
        "oculto": "Está evaluando una oferta de otra empresa y esta conversación puede definirla.",
    },
}
NOMBRES_APERTURA = {k: k.capitalize().replace("Analitico", "Analítico") for k in APERTURAS}


class CasoPropio(BaseModel):
    nombre: str = ""
    genero: str = "m"  # m / f: elige la voz y la cara
    seniority: str
    anios_en_puesto: float = Field(ge=0, le=60)
    apertura: str
    metas: list[int] = Field(min_length=5, max_length=5)  # cantidad por calificación, de Insatisfactorio a Excepcional
    competencias: dict[str, int]  # clave → 1..5
    evaluacion_final: int = Field(ge=1, le=5)
    rating: float | None = Field(default=None, ge=0, le=120)
    contexto: str = ""


def banda_de(rating: float) -> int:
    for i, (bajo, alto) in enumerate(BANDAS):
        if rating <= alto:
            return i + 1
    return 5


def posicion_en_banda(rating: float) -> str:
    bajo, alto = BANDAS[banda_de(rating) - 1]
    tercio = (rating - bajo) / max(alto - bajo, 1)
    if tercio < 1 / 3:
        return "parte baja de la banda"
    if tercio > 2 / 3:
        return "parte alta de la banda"
    return "centro de la banda"


def validar(caso: CasoPropio) -> str | None:
    if caso.seniority not in SENIORITY:
        return "Seniority inválido."
    if caso.apertura not in APERTURAS:
        return "Apertura al feedback inválida."
    if sum(caso.metas) < 1 or min(caso.metas) < 0:
        return "Indicá al menos un objetivo."
    esperadas = [c for c in COMPETENCIAS if c != "liderazgo" or caso.seniority in CON_LIDERAZGO]
    if set(caso.competencias) != set(esperadas) or not all(1 <= v <= 5 for v in caso.competencias.values()):
        return "Completá la evaluación de todas las competencias."
    return None


def armar_ficha(caso: CasoPropio, idioma: str) -> dict:
    """Una ficha con la misma forma que las cartas de HR, para que conversación y evaluación funcionen igual."""
    puesto, nivel = SENIORITY[caso.seniority]
    perfil = APERTURAS[caso.apertura]
    final = ESCALA[caso.evaluacion_final - 1]
    nombre = caso.nombre.strip() or "Caso propio"
    metas_txt = ", ".join(f"{n} {ESCALA[i]}" for i, n in enumerate(caso.metas) if n)
    flojas = [NOMBRES_COMPETENCIA[k] for k, v in caso.competencias.items() if v <= 2]
    fuertes = [NOMBRES_COMPETENCIA[k] for k, v in caso.competencias.items() if v >= 4]
    rating_txt = ""
    if caso.rating is not None:
        banda = ESCALA[banda_de(caso.rating) - 1]
        rating_txt = f"Overall Rating {caso.rating:g} sobre 120: {posicion_en_banda(caso.rating)} de {banda}."
        if banda != final:
            rating_txt += f" Ojo: ese rating cae en la banda de {banda}, no en la de {final}."
    espera = ESCALA[min(caso.evaluacion_final - 1 + perfil["sube"], 4)]
    contexto = [l.strip("-• ").strip() for l in caso.contexto.splitlines() if l.strip()]

    objetivo = (
        f"Comunicar con claridad la evaluación final ({final}) y asumirla como propia. "
        f"Apoyarse en los objetivos ({metas_txt}) y en las competencias del nivel {puesto} del manual TLAC. "
        + (f"Desarrollo prioritario en: {', '.join(flojas)}. " if flojas else "")
        + (f"Reconocer con ejemplos: {', '.join(fuertes)}. " if fuertes else "")
        + (rating_txt + " Usar la posición en la banda para matizar el mensaje (cerca de la cota superior o inferior). " if rating_txt else "")
        + f"Adaptar la conversación a un colaborador {NOMBRES_APERTURA[caso.apertura].lower()}: {perfil['tono']} "
        "Cerrar con acuerdos concretos, con fecha y seguimiento."
    )
    return {
        "id": "propio",
        "tipo": "propio",
        "nombre": nombre,
        "puesto": puesto,
        "pais": "Brasil" if idioma == "pt" else "Argentina",
        "genero": "f" if caso.genero == "f" else "m",
        "nivel_competencias": nivel,
        "carta": {
            "seniority": puesto,
            "en_el_puesto": f"{caso.anios_en_puesto:g} años",
            "apertura_al_feedback": NOMBRES_APERTURA[caso.apertura],
            "objetivos": metas_txt,
            "competencias": {NOMBRES_COMPETENCIA[k]: f"{v} ({ESCALA[v - 1]})" for k, v in caso.competencias.items()},
            "evaluacion_final": final,
            "overall_rating": caso.rating,
            "contexto": contexto,
        },
        "practica": {
            "calificacion_final": final,
            "dificultad": perfil["dificultad"],
            "trampa": "Sesgos generales (sin trampa específica)",
            "objetivo": objetivo,
            "bitacora": contexto,
            "posicion_rating": rating_txt,
        },
        "personaje": {
            "tono": perfil["tono"],
            "apertura": perfil["apertura"],
            "espera": espera,
            "reacciones": perfil["reacciones"],
            "lo_que_lo_abre": perfil["lo_que_lo_abre"],
            "lo_que_lo_cierra": perfil["lo_que_lo_cierra"],
            "hechos_ocultos": [perfil["oculto"]],
        },
    }


def instrucciones(ficha: dict, idioma: str, hablado: bool, acento: str, habla: str) -> str:
    carta, p, practica = ficha["carta"], ficha["personaje"], ficha["practica"]
    largo = (
        "La reunión es por voz: respondé en una a tres frases cortas, no más de 40 palabras en total."
        if hablado else "Respuestas breves, de una a cuatro frases, como se habla."
    )
    reacciones = "\n".join(f"- Si {r['si']}: {r['entonces']}" for r in p["reacciones"])
    contexto = "\n".join(f"- {c}" for c in carta["contexto"]) or "- (sin detalles: inventá situaciones verosímiles y sostenelas)"
    quien = ficha["nombre"] if ficha["nombre"] != "Caso propio" else (
        "una colaboradora (no tiene nombre definido: si hace falta, inventá uno y sostenelo)" if ficha["genero"] == "f"
        else "un colaborador (no tiene nombre definido: si hace falta, inventá uno y sostenelo)")
    return f"""Vas a interpretar a {quien}, de nivel {ficha['puesto']} de una automotriz, en una \
simulación de entrenamiento. Quien te escribe es tu líder directo/a, que practica una conversación de feedback de cierre \
de ciclo basada en un caso real: comunicarte tu evaluación final y hablar de tu desarrollo. Comportate como una persona \
real con este estilo de apertura al feedback: {carta['apertura_al_feedback']}. Quien acepta todo enseguida no entrena a nadie.

# Quién sos
Nivel {ficha['puesto']}, {carta['en_el_puesto']} en el puesto. Tu manera de ser frente al feedback: {p['tono']}

# Tu año
Tenés objetivos con estos resultados, que conocés a grandes rasgos: {carta['objetivos']}.
Situaciones del año:
{contexto}
No conocés todavía tu evaluación final ni la de tus competencias: eso te lo dice tu líder.

# Lo que esperás
Esperás una evaluación de {p['espera']}.

# Cómo abrir la reunión
Tu primera frase, con tus palabras: «{p['apertura']}»

# Cómo reaccionás
{reacciones}
Lo que te abre: {p['lo_que_lo_abre']}
Lo que te cierra: {p['lo_que_lo_cierra']}
Cambiá de postura en proporción a cómo lo hace tu líder; nunca te rendís de golpe.

# Lo que te guardás
- {p['hechos_ocultos'][0]}
Revelalo solo si tu líder hace una pregunta abierta que apunte ahí o te genera confianza.

# Cómo hablar
- {acento} Respondé siempre en {habla}.
- {largo} Sin listas, sin títulos, sin acotaciones entre asteriscos ni paréntesis.
- Hablá en primera persona. No le inventes un nombre a tu líder.
- Mantené el personaje. No des consejos a tu líder, no lo evalúes y no menciones que sos una IA ni que es una simulación.
- No inventes números distintos de los que tu líder mencione; si te falta un dato, respondé algo verosímil.
- Si tu líder da por terminada la reunión, despedite en personaje dejando claro con qué te quedás."""
