#!/usr/bin/env bash
# Saadab kohalikud muudatused GitHubi. See käivitab Cloudflare'i
# automaatse ehituse — saidi uus versioon on üleval umbes minuti pärast.
#
# Käivita topeltklõpsuga failil "Salvesta muudatused.command" saidi
# kaustas, või käsurealt: bash scripts/salvesta.sh

set -euo pipefail
cd "$(dirname "$0")/.."

if [ -z "$(git status --porcelain)" ]; then
  echo "Midagi ei ole muutunud — pole vaja midagi saata."
  exit 0
fi

echo "==> Need failid saadetakse:"
git status --short | sed 's/^/    /'
echo

read -r -p "Lühike kirjeldus (Enter jätab automaatse): " MSG
if [ -z "$MSG" ]; then
  MSG="Kiirmuudatus $(date '+%Y-%m-%d %H:%M')"
fi

git add -A
git commit -q -m "$MSG"

echo "==> Tõmban GitHubist viimase seisu (kui vahepeal midagi muutus)"
git pull --rebase --autostash origin main

echo "==> Saadan GitHubi"
git push origin main

echo
echo "==> Valmis. Cloudflare ehitab uue versiooni ~1 minutiga."
echo "    Kontrolli: https://sandrajogeva.artcontainer.ee/"
echo
read -r -p "Vajuta Enter, et see aken sulgeda."
