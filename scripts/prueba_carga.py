"""Prueba de carga: simula N líderes practicando a la vez y mide cuánto tarda cada paso.

Uso (contra un servidor con MODO_CARGA=1, para no gastar en los proveedores):
    python scripts/prueba_carga.py --url http://localhost:8010 --lideres 10 25 50 --turnos 6 [--codigo XXXX]

Cada líder simulado: abre la práctica, el colaborador saluda, y en cada turno el líder "habla"
(transcripción), recibe la respuesta en streaming y pide la voz de dos frases; al final pide la
devolución. Mide el tiempo hasta la primera palabra del colaborador, que es lo que el líder siente
como "espera", y cuenta los errores.
"""
import argparse
import asyncio
import random
import statistics
import time

import httpx


async def un_lider(cliente, url, codigo, turnos, pausa, medidas, errores):
    h = {"X-Codigo": codigo} if codigo else {}
    try:
        r = await cliente.post(f"{url}/api/sesiones", headers=h,
                               json={"colaborador_id": f"{random.randint(1, 10):02d}", "idioma": "es"})
        r.raise_for_status()
        sid = r.json()["id"]
        for turno in range(turnos + 1):
            texto = ""
            if turno:
                await asyncio.sleep(pausa * random.uniform(0.7, 1.3))  # el líder piensa y habla
                t0 = time.perf_counter()
                r = await cliente.post(f"{url}/api/sesiones/{sid}/transcripcion", headers=h,
                                       files={"audio": ("turno.webm", b"\0" * 20000, "audio/webm")})
                r.raise_for_status()
                medidas["transcripcion"].append(time.perf_counter() - t0)
                texto = r.json()["texto"]
            t0 = time.perf_counter()
            primera, todo = None, ""
            async with cliente.stream("POST", f"{url}/api/sesiones/{sid}/mensaje", headers=h,
                                      json={"texto": texto, "hablado": True, "por_voz": bool(turno)}) as resp:
                resp.raise_for_status()
                async for trozo in resp.aiter_text():
                    if primera is None:
                        primera = time.perf_counter() - t0
                    todo += trozo
            if "[[ERROR]]" in todo:
                raise RuntimeError(todo.split("[[ERROR]]", 1)[1].strip())
            medidas["primera_palabra"].append(primera)
            medidas["respuesta_completa"].append(time.perf_counter() - t0)
            frases = [f.strip() + "." for f in todo.split(".") if f.strip()][:2]
            for frase in frases:
                t0 = time.perf_counter()
                async with cliente.stream("POST", f"{url}/api/sesiones/{sid}/voz", headers=h,
                                          json={"texto": frase.rstrip("."), "formato": "pcm"}) as resp:
                    resp.raise_for_status()
                    async for _ in resp.aiter_bytes():
                        pass
                medidas["voz_frase"].append(time.perf_counter() - t0)
        t0 = time.perf_counter()
        r = await cliente.post(f"{url}/api/sesiones/{sid}/evaluacion", headers=h)
        r.raise_for_status()
        medidas["devolucion"].append(time.perf_counter() - t0)
    except Exception as e:  # cada error cuenta, pero no frena a los demás líderes
        errores.append(f"{type(e).__name__}: {str(e)[:120]}")


def resumen(nombre, valores):
    if not valores:
        return f"  {nombre:20s} sin datos"
    v = sorted(valores)
    p95 = v[min(len(v) - 1, int(len(v) * 0.95))]
    return f"  {nombre:20s} mediana {statistics.median(v):6.2f} s · p95 {p95:6.2f} s · máx {v[-1]:6.2f} s  (n={len(v)})"


async def ronda(url, codigo, n, turnos, pausa):
    medidas = {k: [] for k in ("transcripcion", "primera_palabra", "respuesta_completa", "voz_frase", "devolucion")}
    errores = []
    limites = httpx.Limits(max_connections=n * 3, max_keepalive_connections=n * 3)
    async with httpx.AsyncClient(timeout=httpx.Timeout(180.0), limits=limites) as cliente:
        t0 = time.perf_counter()
        # Llegan escalonados en los primeros segundos, como pasaría en la realidad.
        await asyncio.gather(*[asyncio.sleep(random.uniform(0, 3)) for _ in range(0)])
        tareas = []
        for _ in range(n):
            tareas.append(asyncio.create_task(un_lider(cliente, url, codigo, turnos, pausa, medidas, errores)))
            await asyncio.sleep(random.uniform(0, 3 / max(n, 1)))
        await asyncio.gather(*tareas)
        total = time.perf_counter() - t0
    print(f"\n== {n} líderes en paralelo · {turnos} turnos · {total:.0f} s ==")
    for k, v in medidas.items():
        print(resumen(k, v))
    print(f"  errores: {len(errores)} de {n} líderes" + (f" → {errores[:3]}" if errores else ""))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", default="http://localhost:8010")
    ap.add_argument("--codigo", default="")
    ap.add_argument("--lideres", type=int, nargs="+", default=[5, 10, 25])
    ap.add_argument("--turnos", type=int, default=6)
    ap.add_argument("--pausa", type=float, default=4.0, help="segundos que el líder tarda en hablar entre turnos")
    a = ap.parse_args()
    for n in a.lideres:
        asyncio.run(ronda(a.url.rstrip("/"), a.codigo, n, a.turnos, a.pausa))


if __name__ == "__main__":
    main()
