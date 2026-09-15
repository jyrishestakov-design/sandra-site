#!/usr/bin/env python3
"""Ühekordne parandus: content/portfolio/*.en.md failidel puudus `date`
ja `weight` - Hugo näitas kuupäeva "0001" ja inglise galerii järjekord
oli juhuslik, kuna need väljad mõjutavad Hugo enda sisemist
lehtede sortimist otse, mitte malli kaudu (erinevalt kaanepildist/
piltidest, mille jaoks on juba olemas malli-tasandi fallback).

Loeb iga X.md failist `weight:` ja `date:` väärtused ja lisab need
vastavasse X.en.md faili (pealkirja järele), kui neid seal veel pole.

Kasutus: python3 scripts/fix-en-dates.py [--dry-run]
"""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PORTFOLIO = ROOT / "content" / "portfolio"


def main(argv):
    dry = "--dry-run" in argv
    fixed = 0
    for en_path in sorted(PORTFOLIO.glob("*.en.md")):
        et_path = PORTFOLIO / en_path.name.replace(".en.md", ".md")
        if not et_path.exists():
            print(f"HOIATUS: {en_path.name} jaoks pole eestikeelset faili")
            continue

        et_text = et_path.read_text(encoding="utf-8")
        weight_m = re.search(r"^weight:\s*(.*)$", et_text, re.MULTILINE)
        date_m = re.search(r"^date:\s*(.*)$", et_text, re.MULTILINE)

        en_text = en_path.read_text(encoding="utf-8")
        if re.search(r"^date:\s*", en_text, re.MULTILINE):
            continue  # juba olemas, ei puutu

        lines_to_add = []
        if weight_m:
            lines_to_add.append(f"weight: {weight_m.group(1)}")
        if date_m:
            lines_to_add.append(f"date: {date_m.group(1)}")
        if not lines_to_add:
            continue

        new_text = en_text.replace(
            "title:",
            "title:",  # anchor kept for clarity; actual insert below
            1,
        )
        # Sisesta title-rea JÄREL
        new_lines = en_text.split("\n")
        out = []
        inserted = False
        for line in new_lines:
            out.append(line)
            if not inserted and line.startswith("title:"):
                out.extend(lines_to_add)
                inserted = True
        new_text = "\n".join(out)

        print(f"{en_path.relative_to(ROOT)}: +{', '.join(lines_to_add)}")
        if not dry:
            en_path.write_text(new_text, encoding="utf-8")
        fixed += 1

    print(f"\n{'(dry-run) ' if dry else ''}{fixed} faili parandatud")


if __name__ == "__main__":
    main(sys.argv[1:])
