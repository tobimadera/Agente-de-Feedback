# Agente de Feedback

Entrenador de conversaciones de feedback para líderes. Usa la misma arquitectura que el **Agente de Gastos**: una skill que corre en la nube, una carpeta en Google Drive, un bot de Telegram por la API HTTP y una planilla de Google Sheets como registro.

El líder elige a uno de los 10 colaboradores de las cartas de calibración ("El Comité") y practica la conversación de cierre de ciclo: tiene que comunicar la calificación final calibrada y dar feedback por competencia. El agente interpreta al colaborador, que reacciona como lo haría esa persona. Al escribir `FIN`, el coach devuelve un puntaje en 7 dimensiones. Cada puntaje cita una frase del líder y se compara con el manual **Competencias TLAC por nivel**.

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

La calificación a comunicar es la **referencia** del juego de calibración. Respeta el techo de 2 Supera y 1 Excepcional. Los datos de metas, competencias y contexto son los de las cartas. La *bitácora* del líder y lo que cada personaje se guarda son situaciones creadas para la práctica, coherentes con cada carta, y están marcadas así en el YAML.

## Estructura

```
skills/agente-feedback/
├── SKILL.md                         ← instrucciones del agente
├── references/
│   ├── colaboradores.yaml           ← las 10 cartas + escenario + personaje
│   ├── competencias.yaml            ← manual TLAC, 8 niveles × 6 competencias
│   ├── rubrica_feedback.md          ← 7 dimensiones, trampas, sello
│   ├── formato_respuestas.md        ← textos de menú, ficha, pista, devolución
│   ├── lideres.yaml                 ← ejemplo de líderes habilitados
│   ├── registro_encabezado.csv      ← columnas de la planilla
│   └── escuchar_telegram.sh         ← long polling para el modo en vivo
└── assets/cartas/                   ← imágenes originales (fNN frente, bNN dorso)
dist/agente-feedback.zip             ← la skill empaquetada para subir a claude.ai
```

## Puesta en marcha

1. **Instalar la skill**: en claude.ai → Configuración → Capacidades → Skills, subí `dist/agente-feedback.zip`. Hacelo igual que con `agente-gastos`.
2. **Probar en el chat** (no necesita nada más): *"Quiero practicar la conversación de feedback con Sergio"*.
3. **Telegram** (opcional):
   1. Creá un bot con @BotFather.
   2. En Google Drive (Mi unidad), creá la carpeta `Agente de feedback` con:
      - `config/telegram.env` → `TELEGRAM_BOT_TOKEN=<token>`
      - `config/lideres.yaml` → los líderes habilitados (ver `references/lideres.yaml`)
      - `config/estado.json` → `{"ultimo_update_id": 0}`
   3. En el entorno cloud, permití el host `api.telegram.org`.
   4. Creá una tarea programada con: *"Usá la skill agente-feedback y hacé una pasada de Telegram en modo en vivo. Al terminar, dejá el resumen."* Cada pasada se queda escuchando mientras haya prácticas abiertas, así que la conversación fluye casi en tiempo real.
4. La planilla `registro/practicas` y las transcripciones se crean solas en la primera práctica.

## Comandos

`MENU` · `PRACTICAR 08` · `FICHA` · `COMPETENCIAS` · `PISTA` · `FIN` · `SALIR`
