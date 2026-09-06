#!/usr/bin/env python3
"""Ühekordne migratsioon: content/portfolio/*.md frontmatteri `images` väli
stringinimekirjast objektinimekirjaks.

Enne:
    images:
      - SandraLaudKana-046.jpg

Pärast:
    images:
      - image: SandraLaudKana-046.jpg
        caption: ""
        alt: ""

Idempotentne: juba objektikujul kirjeid (`- image:` või `- {`) ei puututa.
Muid frontmatteri välju ega sisu ei muudeta – töödeldakse ainult `images:` plokki.

Kasutus:  python3 scripts/migrate-images.py [--dry-run] [failid...]
"""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PORTFOLIO = ROOT / "content" / "portfolio"

ITEM_RE = re.compile(r"^(\s*)-\s*(.*?)\s*$")


def unquote(value: str) -> str:
    if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
        inner = value[1:-1]
        return inner.replace('\\"', '"') if value[0] == '"' else inner.replace("''", "'")
    return value


def quote(value: str) -> str:
    return '"' + value.replace("\\", "\\\\").replace('"', '\\"') + '"'


def migrate_text(text: str):
    """Tagastab (uus_tekst, teisendatud_kirjete_arv)."""
    if not text.startswith("---"):
        return text, 0
    end = text.find("\n---", 3)
    if end == -1:
        return text, 0
    head, rest = text[: end + 1], text[end + 1 :]
    lines = head.split("\n")
    out, changed, in_images, item_indent = [], 0, False, None

    for line in lines:
        if in_images:
            m = ITEM_RE.match(line)
            if m and line.strip().startswith("-") and (item_indent is None or len(m.group(1)) == item_indent):
                item_indent = len(m.group(1))
                value = m.group(2)
                if value.startswith("{") or re.match(r"^[A-Za-z_]+\s*:", value):
                    out.append(line)  # juba objekt
                    continue
                pad = " " * item_indent
                out.append(f"{pad}- image: {quote(unquote(value))}")
                out.append(f"{pad}  caption: \"\"")
                out.append(f"{pad}  alt: \"\"")
                changed += 1
                continue
            if line.strip() == "" or (item_indent is not None and len(line) - len(line.lstrip()) > item_indent):
                out.append(line)  # objektikirje alamvõti või tühi rida
                continue
            in_images = False  # järgmine tipptaseme võti
        if re.match(r"^images\s*:\s*$", line):
            in_images, item_indent = True, None
        out.append(line)

    return "\n".join(out) + rest, changed


def main(argv):
    dry = "--dry-run" in argv
    files = [Path(a) for a in argv if not a.startswith("--")] or sorted(PORTFOLIO.glob("*.md"))
    total_files = total_items = 0
    for path in files:
        text = path.read_text(encoding="utf-8")
        new, n = migrate_text(text)
        if n:
            total_files += 1
            total_items += n
            print(f"{path.relative_to(ROOT)}: {n} pilti")
            if not dry:
                path.write_text(new, encoding="utf-8")
    print(f"{'(dry-run) ' if dry else ''}{total_files} faili, {total_items} pildikirjet teisendatud")


if __name__ == "__main__":
    main(sys.argv[1:])
