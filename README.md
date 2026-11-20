# Entrenador de Feedback

Simulador de conversaciones para entrenar a los líderes en la **conversación de feedback de cierre de ciclo**.
El líder elige a uno de los 10 colaboradores de las cartas de calibración ("El Comité"). El agente interpreta
a esa persona, con su carta, su forma de ser y lo que se guarda. El líder le comunica la calificación final
calibrada y le da feedback por competencia. Al terminar, recibe una devolución con puntaje de 1 a 5 en
7 criterios, la trampa de sesgo de la carta y qué decir distinto.

Es el mismo modelo que el **Entrenador de Ventas** (`tobimadera/Entrenamiento-Comercial`): FastAPI + Claude,
voz con ElevenLabs, cara con Simli, panel del gestor y códigos de acceso por líder. Usa **las mismas variables
de entorno**, así que se puede copiar el mismo `.env`.

## Los 10 escenarios

| # | Colaborador | Líder dijo | Calificación a comunicar | Trampa | Dificultad |
|---|---|---|---|---|---|
| 01 | Felipe · Ing. de Procesos | Excepcional | **Supera** | Tres cartas fuertes, un solo lugar | media |
| 02 | Marina · Planificación | Excepcional | **Excepcional** | ¿Reputación o resultado? | baja |
| 03 | Rafael · Compras | Excepcional | **Cumple** | El año pasado, otro puesto | alta |
| 04 | Bruno · Logística | Excepcional | **Cumple** | La evaluación del año pasado | alta |
| 05 | Martín · Logística | Cumple | **Supera** | Edad y "recién promovido" | media |
| 06 | Paula · Calidad de Proveedores | Necesita mejorar | **Cumple** | Penalizar la licencia | media |
| 07 | Ana · Mantenimiento | Necesita mejorar | **Cumple** | Sesgo de género | alta |
| 08 | Sergio · Producción | Supera | **Necesita mejorar** | Afinidad y recencia | muy alta |
| 09 | Laura · Control de Calidad | Necesita mejorar | **Cumple** | Desempeño × potencial | media |
| 10 | Marcos · Logística de Salida | Cumple | **Necesita mejorar** | Zona de confort y culpa externa | alta |

La calificación a comunicar es la **referencia** del juego de calibración (techo: 2 Supera, 1 Excepcional).
Metas, competencias y contexto salen de las cartas. La *bitácora* del líder y lo que cada personaje se
guarda son situaciones creadas para la práctica, coherentes con cada carta.

## Cómo usarlo

1. Copiar `.env.ejemplo` como `.env` y completar `ANTHROPIC_API_KEY` (y, para voz y cara,
   `ELEVENLABS_API_KEY` y `SIMLI_API_KEY`). Son las mismas claves del Entrenador de Ventas.
2. Primera vez: `py -m venv .venv` y `.venv\Scripts\python.exe -m pip install -r requirements.txt`.
3. Iniciar el servidor desde esta carpeta:

   ```
   .venv\Scripts\python.exe -m uvicorn app.servidor:app --port 8011
   ```

4. Abrir http://localhost:8011. El panel del gestor está en http://localhost:8011/gestor.

## La práctica

- **Elegir**: idioma de la conversación (español o portugués) y una carta. Se ve la carta (tocándola se da
  vuelta), la calificación a comunicar, la bitácora del líder y lo que el manual TLAC espera en su nivel.
- **Conversar** por texto o por voz. **Pista** pide una sugerencia al coach para el próximo turno (queda
  registrada). **Ver ficha** muestra la carta durante la charla.
- **Terminar y evaluar**: sello (*Listo para la conversación real*, *Casi listo*, *Practicar de nuevo*),
  puntaje de 1 a 5, la calificación que comunicó contra la que correspondía, si cayó en la trampa, momentos
  clave con una frase alternativa, cada criterio con la cita que lo justifica, lo que el colaborador no
  contó y con quién practicar después.

## Cómo "entrenar" al agente

No se reentrena ningún modelo: se editan archivos de texto (se leen al recargar la página).

- **Colaboradores**: `skills/agente-feedback/references/colaboradores.yaml`. Por colaborador: la carta, la
  práctica (calificación final, trampa, objetivo, bitácora) y el personaje (tono, apertura, reacciones,
  hechos ocultos). También `voz` (ElevenLabs) y opcionalmente `cara` (Simli).
- **Manual de competencias**: `skills/agente-feedback/references/competencias.yaml` (8 niveles × 6 competencias).
- **Rúbrica**: `skills/agente-feedback/references/rubrica_feedback.md` y los criterios en `config/criterios.yaml`
  (escala 1–5, `objetivo: 4`).
- **Voces y caras por defecto**: `config/voces.yaml`. Cada colaborador ya tiene su voz propia; si una voz no
  está disponible en la cuenta de ElevenLabs, se usa la del país y género.
- **Conversaciones hechas**: `datos/sesiones/` (transcripción, pistas y devolución).

## Voz y avatar

Igual que en el Entrenador de Ventas: con `ELEVENLABS_API_KEY`, botones **Hablar** y **Voz: sí/no**; con
`SIMLI_API_KEY` además, la cara del colaborador hablando. La voz habla en el idioma elegido con el acento del
colaborador (un brasileño que habla español suena brasileño). La sesión de Simli se cierra al terminar, al
apagar la voz o tras 3 minutos sin hablar.

## Panel del gestor

Por líder: entrenamientos, promedio y progreso; mapa de brechas por criterio contra el objetivo; porcentaje
de prácticas que cayeron en la trampa de sesgo; principales puntos de mejora (y resumen con IA); detalle de
cada práctica con conversación, pistas y devolución; códigos de acceso personales. Se entra con `CODIGO_GESTOR`.

## Publicarlo (Railway)

Igual que el Entrenador de Ventas: repositorio en GitHub → Railway (**Deploy from GitHub repo**), variables
`ANTHROPIC_API_KEY`, `CODIGO_GESTOR`, `CODIGO_ACCESO` (opcional), `DATOS_DIR=/data`, `ELEVENLABS_API_KEY`,
`SIMLI_API_KEY`; un **Volume** en `/data` y **Generate Domain**.

## También como skill de Claude (chat y Telegram)

`skills/agente-feedback/` es la misma práctica como skill de Claude, sin servidor: se practica en el chat de
Claude o con un bot de Telegram, con el registro en Google Sheets. Ver `skills/agente-feedback/SKILL.md`.
`dist/agente-feedback.zip` es la skill empaquetada para subir a claude.ai.

## Estructura

- `app/simulador.py`: instrucciones del colaborador, pista del coach y evaluación con la rúbrica.
- `app/servidor.py`: servidor web, sesiones, cartas y códigos.
- `app/voz.py`, `app/avatar.py`: ElevenLabs y Simli.
- `app/lideres.py`: líderes y sus códigos personales.
- `app/informes.py`: datos del panel del gestor.
- `web/index.html`, `web/gestor.html`: pantalla de práctica y panel del gestor.
- `skills/agente-feedback/`: datos compartidos (colaboradores, manual, rúbrica) y la skill.
