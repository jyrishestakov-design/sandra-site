#!/usr/bin/env bash
# Avab kohaliku admini otse: tõmbab enne GitHubist viimase seisu, ja kui
# Hugo server veel ei tööta, käivitab selle taustal (Terminali akna võib
# kohe sulgeda, server jääb siiski tööle).
#
# Käivita topeltklõpsuga failil "Ava admin.command" saidi kaustas,
# või käsurealt: bash scripts/admin.sh

set -euo pipefail
cd "$(dirname "$0")/.."

PORT="${PORT:-1313}"

echo "==> Tõmban GitHubist viimase seisu"
git pull --rebase --autostash origin main || echo "    (ei õnnestunud, jätkan olemasoleva seisuga)"

if ! lsof -ti "tcp:$PORT" >/dev/null 2>&1; then
  echo "==> Hugo server ei tööta, käivitan taustal"
  nohup hugo server -p "$PORT" --disableFastRender -b "http://localhost:$PORT/" \
    > /tmp/sandra-site-hugo.log 2>&1 &
  disown
  sleep 2
else
  echo "==> Hugo server juba töötab pordil $PORT"
fi

open "http://localhost:$PORT/admin/"
echo "==> Admin avatud: http://localhost:$PORT/admin/"
echo "    Sisselogimisel vali \"Work with Local Repository\" ja see kaust."
sleep 1
