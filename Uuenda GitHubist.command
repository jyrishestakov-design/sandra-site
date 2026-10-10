#!/usr/bin/env bash
cd "$(dirname "$0")"
if bash scripts/uuenda.sh; then
  bash scripts/close-terminal.sh
else
  read -r -p "Vajuta Enter, et aken sulgeda..." _
fi
