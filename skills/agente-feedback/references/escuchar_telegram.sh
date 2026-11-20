#!/usr/bin/env bash
# Espera mensajes nuevos del bot de Telegram con long polling.
# Uso: bash escuchar_telegram.sh <archivo_token> <offset> <segundos_max> <salida.json>
#   archivo_token: archivo con una línea TELEGRAM_BOT_TOKEN=<token> (no se imprime nunca)
#   offset:        ultimo_update_id + 1
#   segundos_max:  cuánto esperar como máximo (≤ 540 para que entre en una llamada de Bash)
# Sale con 0 y deja los updates en <salida.json> apenas llega al menos uno.
# Sale con 3 si pasó el tiempo sin mensajes. Sale con 1/2 ante un error (401 token, 409 conflicto).
set -u
TOKEN_FILE="$1"; OFFSET="$2"; MAX="$3"; OUT="$4"
T="$(grep -E '^TELEGRAM_BOT_TOKEN=' "$TOKEN_FILE" | head -1 | cut -d= -f2- | tr -d '[:space:]')"
[ -n "$T" ] || { echo "falta TELEGRAM_BOT_TOKEN"; exit 2; }
FIN=$(( $(date +%s) + MAX ))
while [ "$(date +%s)" -lt "$FIN" ]; do
  RESTA=$(( FIN - $(date +%s) )); W=$(( RESTA < 50 ? RESTA : 50 )); [ "$W" -lt 1 ] && break
  CODE=$(curl -s -o "$OUT.tmp" -w '%{http_code}' --max-time $(( W + 15 )) \
    "https://api.telegram.org/bot$T/getUpdates?offset=$OFFSET&timeout=$W")
  case "$CODE" in
    200) ;;
    401) echo "telegram 401: token inválido"; exit 1 ;;
    409) echo "telegram 409: otro programa lee el bot (webhook o versión local)"; exit 1 ;;
    *)   sleep 5; continue ;;
  esac
  N=$(python3 -I -c 'import json,sys; print(len(json.load(open(sys.argv[1])).get("result",[])))' "$OUT.tmp" 2>/dev/null || echo 0)
  if [ "$N" -gt 0 ]; then mv "$OUT.tmp" "$OUT"; echo "mensajes: $N"; exit 0; fi
done
rm -f "$OUT.tmp"; echo "sin mensajes en $MAX s"; exit 3
