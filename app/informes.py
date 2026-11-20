"""Datos del panel del gestor: cuántos entrenamientos hizo cada líder y cómo evoluciona."""
import json
from pathlib import Path
from statistics import mean

from app import simulador


def leer_sesiones(carpeta: Path) -> list[dict]:
    if not carpeta.exists():
        return []
    sesiones = []
    for ruta in carpeta.glob("*.json"):
        try:
            sesiones.append(json.loads(ruta.read_text(encoding="utf-8")))
        except (OSError, ValueError):
            continue  # un archivo a medio escribir no frena el panel
    return sorted(sesiones, key=lambda s: s.get("inicio", ""))


def turnos(sesion: dict) -> int:
    """Cuántas veces habló el líder (sin contar la apertura automática)."""
    mensajes = sesion.get("mensajes", [])
    hablo = sum(1 for m in mensajes if m["role"] == "user") - 1
    if mensajes and simulador.sin_apertura(mensajes[0]["content"]):
        hablo += 1  # escribió algo junto con la apertura
    return max(hablo, 0)


def clave_de(sesion: dict) -> str:
    if sesion.get("lider_id"):
        return sesion["lider_id"]
    return "sin-codigo:" + (sesion.get("lider") or "").strip().lower()


def progreso(puntajes: list[float]) -> float | None:
    """Promedio de las últimas prácticas evaluadas menos el de las primeras (hasta 3 de cada lado)."""
    if len(puntajes) < 2:
        return None
    k = min(3, len(puntajes) // 2)
    return round(mean(puntajes[-k:]) - mean(puntajes[:k]), 1)


NIVELES = ["baja", "media", "alta", "muy alta"]


def dificultad_de(sesion: dict) -> str:
    return ((sesion.get("ficha") or {}).get("practica") or {}).get("dificultad", "")


def resumen(sesiones: list[dict], lista_lideres: list[dict], dificultad: str | None = None) -> dict:
    """Con `dificultad`, todos los números salen solo de las prácticas de ese nivel: así se
    compara a los líderes entre conversaciones de la misma exigencia."""
    existentes = {dificultad_de(s) for s in sesiones} | {f["practica"]["dificultad"] for f in simulador.cargar_colaboradores().values()}
    dificultades = [n for n in NIVELES if n in existentes]
    if dificultad:
        sesiones = [s for s in sesiones if dificultad_de(s) == dificultad]
    filas = []
    for s in sesiones:
        n = turnos(s)
        if n == 0:
            continue  # abrió la reunión y no dijo nada: no cuenta como entrenamiento
        evaluacion = s.get("evaluacion") or {}
        ficha = s.get("ficha", {})
        filas.append({
            "id": s["id"],
            "clave": clave_de(s),
            "fecha": s.get("inicio", ""),
            "colaborador": ficha.get("nombre", s.get("colaborador_id", "")),
            "puesto": ficha.get("puesto", ""),
            "dificultad": dificultad_de(s),
            "idioma": s.get("idioma", ""),
            "sello": evaluacion.get("sello"),
            "cayo_en_trampa": (evaluacion.get("trampa") or {}).get("cayo"),
            "pistas": len(s.get("pistas", [])),
            "por_voz": bool(s.get("por_voz")),
            "turnos": n,
            "puntaje": evaluacion.get("puntaje_general"),
            "criterios": {
                c.get("criterio") or c.get("nombre"): c.get("puntaje")
                for c in evaluacion.get("criterios", [])
            },
        })

    personas = {c["id"]: {"clave": c["id"], "nombre": c["nombre"], "pais": c["pais"],
                          "activo": c.get("activo", True), "con_codigo": True}
                for c in lista_lideres}
    for f in filas:
        if f["clave"] not in personas:
            nombre = f["clave"].removeprefix("sin-codigo:")
            original = next((s.get("lider") for s in sesiones if clave_de(s) == f["clave"]), "")
            personas[f["clave"]] = {"clave": f["clave"], "nombre": original or "Sin nombre", "pais": "",
                                    "activo": True, "con_codigo": False}

    for p in personas.values():
        propias = [f for f in filas if f["clave"] == p["clave"]]
        puntajes = [f["puntaje"] for f in propias if f["puntaje"] is not None]
        p.update({
            "entrenamientos": len(propias),
            "evaluados": len(puntajes),
            "ultimo": propias[-1]["fecha"] if propias else None,
            "promedio": round(mean(puntajes), 1) if puntajes else None,
            "progreso": progreso(puntajes),
        })

    orden = sorted(personas.values(), key=lambda p: (not p["con_codigo"], -p["entrenamientos"], p["nombre"]))
    criterios, objetivo = simulador.todos_los_criterios()
    return {"lideres": orden, "sesiones": filas, "criterios": criterios, "objetivo": objetivo,
            "escala": simulador.escala(), "dificultades": dificultades, "dificultad": dificultad}


MAX_PRACTICAS_MEJORAS = 8


def insumos_mejoras(clave: str, sesiones: list[dict], objetivo: float) -> tuple[list[str], list[dict]]:
    """Lo que necesita la IA para encontrar los puntos de mejora que se repiten: las devoluciones
    de las últimas prácticas evaluadas del líder. Devuelve también sus ids, para saber si
    un resumen ya hecho sigue al día."""
    propias = [s for s in sesiones if clave_de(s) == clave and (s.get("evaluacion") or {}).get("puntaje_general")]
    propias = propias[-MAX_PRACTICAS_MEJORAS:]
    practicas = []
    for s in propias:
        ev = s["evaluacion"]
        practicas.append({
            "fecha": s.get("inicio", "")[:10],
            "colaborador": s.get("ficha", {}).get("nombre", ""),
            "trampa": (ev.get("trampa") or {}).get("nombre", ""),
            "cayo_en_trampa": (ev.get("trampa") or {}).get("cayo"),
            "puntaje": ev["puntaje_general"],
            "a_mejorar": ev.get("mejoras", []),
            "criterios_bajo_objetivo": [
                {"criterio": c.get("criterio") or c.get("nombre"), "puntaje": c["puntaje"], "comentario": c.get("comentario", "")}
                for c in ev.get("criterios", []) if c.get("puntaje", 10) < objetivo
            ],
            "momentos_clave": ev.get("momentos_clave", []),
        })
    return [s["id"] for s in propias], practicas


def detalle(sesion: dict) -> dict:
    """La práctica completa para leerla: conversación sin la indicación de apertura, pistas y devolución."""
    mensajes = []
    for i, m in enumerate(sesion.get("mensajes", [])):
        texto = m["content"]
        if i == 0:
            texto = simulador.sin_apertura(texto)
            if not texto:
                continue
        mensajes.append({"quien": "lider" if m["role"] == "user" else "colaborador", "texto": texto})
    ficha = sesion.get("ficha", {})
    return {
        "id": sesion["id"],
        "fecha": sesion.get("inicio", ""),
        "lider": sesion.get("lider") or "Sin nombre",
        "idioma": sesion.get("idioma", ""),
        "colaborador": ficha.get("nombre", ""),
        "puesto": ficha.get("puesto", ""),
        "calificacion_final": (ficha.get("practica") or {}).get("calificacion_final", ""),
        "trampa": (ficha.get("practica") or {}).get("trampa", ""),
        "por_voz": bool(sesion.get("por_voz")),
        "mensajes": mensajes,
        "pistas": sesion.get("pistas", []),
        "evaluacion": sesion.get("evaluacion"),
    }
