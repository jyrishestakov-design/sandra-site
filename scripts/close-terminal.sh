#!/usr/bin/env bash
# Sulgeb Terminali akna, kus see skript käivitati. Kasutamiseks .command
# failide kõige viimase reana, et aken ei jääks pärast valmimist lahtiseks
# rippuma. Ei puutu teisi lahtisi Terminali aknaid (leiab õige akna tty
# järgi, mitte lihtsalt "esimese akna").
#
# Ei sobi skriptidele, mis peavad jääma töösse (nt eelvaade.sh, mis
# käivitab Hugo serveri esiplaanil) - sulgemine katkestaks selle.

MY_TTY="$(tty 2>/dev/null || true)"
if [ -n "$MY_TTY" ]; then
  ( sleep 0.3
    osascript -e "tell application \"Terminal\" to close (first window whose tty is \"$MY_TTY\")" \
      >/dev/null 2>&1 ) &
  disown
fi
