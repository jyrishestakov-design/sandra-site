#!/usr/bin/env bash
# Käivitab kohaliku Hugo eelvaate ja avab brauseris saidi + admini.
#
# Kasuta seda, et kontrollida muudatusi ENNE salvestamist ja avaldamist:
# admin (vali sisselogimisel "Work with Local Repository" ja see kaust)
# kirjutab failid otse siia, Hugo server näitab neid kohe päris
# kujundusega, ja midagi ei jõua GitHubi ega Cloudflare'i enne, kui
# käivitad "Salvesta muudatused".
#
# Käivita topeltklõpsuga failil "Ava eelvaade.command" saidi kaustas,
# või käsurealt: bash scripts/eelvaade.sh

set -euo pipefail
cd "$(dirname "$0")/.."

PORT="${PORT:-1313}"

echo "==> Tõmban GitHubist viimase seisu"
git pull --rebase --autostash origin main || echo "    (ei õnnestunud, jätkan olemasoleva seisuga)"

existing_pid=$(lsof -ti "tcp:$PORT" 2>/dev/null || true)
if [ -n "$existing_pid" ]; then
  echo "==> Port $PORT on juba kasutusel (eelmine eelvaade?), peatan selle"
  kill "$existing_pid" 2>/dev/null || true
  sleep 1
fi

echo "==> Käivitan Hugo serveri pordil $PORT"
hugo server -p "$PORT" --disableFastRender -b "http://localhost:$PORT/" &
HUGO_PID=$!
trap 'kill $HUGO_PID 2>/dev/null' EXIT

sleep 2
open "http://localhost:$PORT/admin/" 2>/dev/null || true
open "http://localhost:$PORT/" 2>/dev/null || true

echo
echo "==> Admin: http://localhost:$PORT/admin/"
echo "    Sisselogimisel vali \"Work with Local Repository\" ja see kaust."
echo "==> Sait:  http://localhost:$PORT/"
echo
echo "Kui muudatused on kontrollitud, käivita \"Salvesta muudatused.command\"."
echo "Selle akna võib sulgeda või vajutada Ctrl+C, kui eelvaadet enam ei vaja."
echo

wait $HUGO_PID
