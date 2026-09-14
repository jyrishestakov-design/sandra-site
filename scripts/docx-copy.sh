#!/usr/bin/env bash
# Küsib .docx faili, teisendab selle Markdowniks (säilitades Wordi
# lõikude tiheda/tavalise vahe) ja kopeerib tulemuse lõikelauale.
#
# Käivita topeltklõpsuga failil "Muuda DOCX Markdowniks.command".

set -euo pipefail
cd "$(dirname "$0")/.."

FILE=$(osascript -e 'POSIX path of (choose file with prompt "Vali .docx fail:")' 2>/dev/null) || {
  echo "Tühistatud."
  exit 0
}

case "$FILE" in
  *.docx|*.DOCX) ;;
  *)
    osascript -e 'display alert "See ei ole .docx fail" message "Vali Wordi dokument (.docx laiendiga)." as warning'
    exit 1
    ;;
esac

python3 scripts/docx-to-markdown.py "$FILE" --copy

osascript -e 'display notification "Kleebi admini väljal Raw/Markdown vaates (M↓ nupp)." with title "Kopeeritud lõikelauale"'
