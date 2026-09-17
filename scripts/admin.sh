#!/usr/bin/env bash
# Avab kohaliku admini otse: tõmbab enne GitHubist viimase seisu ja
# käivitab Hugo serveri alati värskelt taustal (Terminali akna võib kohe
# sulgeda, server jääb siiski tööle) - nii on uued/muudetud failid kohe
# näha, mitte vana töötava serveri vahemälus kinni.
#
# Käivita topeltklõpsuga failil "Ava admin.command" saidi kaustas,
# või käsurealt: bash scripts/admin.sh

set -euo pipefail
cd "$(dirname "$0")/.."

PORT="${PORT:-1313}"

echo "==> Tõmban GitHubist viimase seisu"
git pull --rebase --autostash origin main || echo "    (ei õnnestunud, jätkan olemasoleva seisuga)"

existing_pid=$(lsof -ti "tcp:$PORT" 2>/dev/null || true)
if [ -n "$existing_pid" ]; then
  echo "==> Peatan vana Hugo serveri (et uued failid kindlasti kohe näha oleks)"
  kill "$existing_pid" 2>/dev/null || true
  sleep 1
fi

echo "==> Käivitan Hugo serveri taustal"
nohup hugo server -p "$PORT" --disableFastRender -b "http://localhost:$PORT/" \
  > /tmp/sandra-site-hugo.log 2>&1 &
disown
sleep 2

open "http://localhost:$PORT/admin/"
echo "==> Admin avatud: http://localhost:$PORT/admin/"
echo "    Sisselogimisel vali \"Work with Local Repository\" ja see kaust."
sleep 1
