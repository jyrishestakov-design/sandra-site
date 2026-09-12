#!/usr/bin/env bash
# Avaldab saidi Cloudflare Pages'is käsitsi.
#
# NB (2026-09-12): Cloudflare Pages on nüüd ühendatud GitHubi repoga ja
# ehitab/avaldab saidi ISE iga main-i push'i peale (paar minutit pärast
# admini salvestust). Seda skripti ei ole enam vaja tavapäraseks
# avaldamiseks — kasulik ainult kohaliku ehituse kontrolliks või kui
# tahad avaldada kohe, ootamata Cloudflare'i automaatset ehitust.
#
#   bash scripts/avalda.sh
#
# Skript tõmbab GitHubist viimase seisu, ehitab saidi ja laeb selle üles.

set -euo pipefail

cd "$(dirname "$0")/.."

export CLOUDFLARE_ACCOUNT_ID="${CLOUDFLARE_ACCOUNT_ID:-131e128ab0bc17121b276c1b3312a071}"
PROJECT="${PROJECT:-sandra-jogeva}"

echo "==> Tõmban GitHubist viimase seisu"
if [ -n "$(git status --porcelain)" ]; then
  echo "    HOIATUS: töökaustas on salvestamata muudatusi:"
  git status --short | sed 's/^/      /'
fi
git pull --rebase --autostash origin main

echo "==> Ehitan saidi"
rm -rf public
hugo --gc --minify

files=$(find public -type f | wc -l | tr -d ' ')
echo "    valmis: $files faili"

echo "==> Laen Cloudflare Pages'i"
npx --yes wrangler@latest pages deploy public \
  --project-name "$PROJECT" \
  --branch main \
  --commit-dirty=true

echo
echo "==> Valmis. Kontrolli: https://sandrajogeva.artcontainer.ee/"
