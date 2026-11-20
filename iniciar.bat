@echo off
rem Inicia el Entrenador de Feedback en http://localhost:8011
rem La primera vez crea el entorno de Python e instala lo necesario (tarda un par de minutos).
cd /d "%~dp0"

if not exist ".env" (
  echo Falta el archivo .env con las claves.
  echo Copia el .env de la carpeta del Entrenador de Ventas a esta carpeta y volve a abrir este archivo.
  pause
  exit /b 1
)

if not exist ".venv\Scripts\python.exe" (
  echo Preparando el entorno de Python por primera vez...
  py -m venv .venv || python -m venv .venv
  if not exist ".venv\Scripts\python.exe" (
    echo No se encontro Python. Instalalo desde https://www.python.org/downloads/ y volve a intentar.
    pause
    exit /b 1
  )
  ".venv\Scripts\python.exe" -m pip install -r requirements.txt
)

start "" http://localhost:8011
".venv\Scripts\python.exe" -m uvicorn app.servidor:app --port 8011
pause
