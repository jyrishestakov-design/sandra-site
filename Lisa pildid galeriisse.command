#!/usr/bin/env bash
cd "$(dirname "$0")"
python3 scripts/lisa-pildid.py
bash scripts/close-terminal.sh
