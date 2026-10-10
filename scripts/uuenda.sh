#!/usr/bin/env bash
# Toob GitHubist saidi viimase seisu sellesse arvutisse.
# Käivita topeltklõpsuga failil "Uuenda GitHubist.command".
set -uo pipefail
cd "$(dirname "$0")/.."
LOG="scripts/.uuenda.log"
{
echo "==> $(date '+%Y-%m-%d %H:%M') Uuendan GitHubist"
git config core.fileMode false
echo "--- Kohalikud muudatused enne:"
git status --short | head -40
git pull --rebase --autostash origin main
echo "--- Viimane versioon nüüd:"
git log -1 --format='%h %ci %s'
echo "--- Kohalikud muudatused pärast:"
git status --short | head -40
} 2>&1 | tee "$LOG"
echo
echo "==> Valmis. (Aken sulgub mõne sekundi pärast.)"
sleep 4
