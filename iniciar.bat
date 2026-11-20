@echo off
rem Inicia el Entrenador de Feedback en http://localhost:8011
rem La primera vez crea el entorno de Python e instala lo necesario (tarda un par de minutos).
cd /d "%~dp0"

rem Windows suele ocultar la extension: un ".env" guardado desde el Bloc de notas queda como ".env.txt".
if not exist ".env" if exist ".env.txt" ren ".env.txt" ".env"

if not exist ".env" (
  echo No encontre el archivo .env con las claves en esta carpeta:
  echo   %~dp0
  echo.
  echo Se va a abrir el Bloc de notas con un .env nuevo. Pega ahi tus claves
  echo ^(las mismas del .env del Entrenador de Ventas^), guarda ^(Ctrl+S o Ctrl+G^) y cerra el Bloc de notas.
  pause
  copy /y ".env.ejemplo" ".env" >nul
  notepad ".env"
)

findstr /r /c:"^ANTHROPIC_API_KEY *= *[a-zA-Z0-9]" ".env" >nul || (
  echo El .env no tiene ANTHROPIC_API_KEY completa. Abrilo, pega la clave y volve a abrir este archivo.
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

echo.
echo Iniciando el Entrenador de Feedback. El navegador se abre en unos segundos.
echo No cierres esta ventana mientras uses el entrenador.
echo.
start "" /min cmd /c "timeout /t 6 /nobreak >nul & start http://localhost:8011"
".venv\Scripts\python.exe" -m uvicorn app.servidor:app --port 8011
pause
