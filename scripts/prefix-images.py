#!/usr/bin/env python3
"""Lisab content/portfolio ja content/pages failide `images` nimekirja
kirjetele ja `cover` väljale "/images/" ette, kui see puudub.

Miks: vanad (algse impordi) kirjed hoiavad ainult paljast failinime
(nt "foto.jpg"), samas kui Sveltia CMS-i pildividin ise vajab
avaliku kausta (public_folder "/images") suhtes täielikku teed
(nt "/images/foto.jpg"), et osata admini poolel pisipilti näidata.
Hugo mall (image-item.html) juba lisab "/images/" ette kuvamisel,
seega avalik veebileht ei muutu - ainult admini pisipildid hakkavad
tööle vanade kirjete jaoks ka.

Ohutu: puudutab ainult stringikirjeid, mis EI alga juba "/" või
"http"-ga; objektikujul kirjeid (`- image: ...`) ei puutu.

Kasutus: python3 scripts/prefix-images.py [--dry-run]
"""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TARGETS = sorted((ROOT / "content" / "portfolio").glob("*.md")) + sorted(
    (ROOT / "content" / "pages").glob("*.md")
)

ITEM_RE = re.compile(r"^(\s*-\s*)(.*?)\s*$")


def unquote(value):
    if len(value) >= 2 and value[0] == value[-1] == '"':
        return value[1:-1]
    if len(value) >= 2 and value[0] == value[-1] == "'":
        return value[1:-1]
    return value


def needs_prefix(value):
    return bool(value) and not value.startswith("/") and not value.startswith("http")


def fix_images(lines):
    out, changed, in_field = [], 0, False
    for line in lines:
        if re.match(r"^images\s*:\s*$", line):
            out.append(line)
            in_field = True
            continue
        if in_field:
            m = ITEM_RE.match(line)
            if m and line.strip().startswith("-"):
                prefix, val = m.groups()
                unquoted = unquote(val)
                if unquoted.startswith("{") or re.match(r"^[a-zA-Z_]+\s*:", unquoted):
                    out.append(line)  # objektikujul kirje, ei puutu
                    continue
                if needs_prefix(unquoted):
                    out.append(f'{prefix}"/images/{unquoted}"')
                    changed += 1
                else:
                    out.append(line)
                continue
            in_field = False
        out.append(line)
    return out, changed


def fix_cover(lines):
    out, changed = [], 0
    for line in lines:
        m = re.match(r"^cover\s*:\s*(.*?)\s*$", line)
        if m:
            val = unquote(m.group(1))
            if needs_prefix(val):
                out.append(f"cover: /images/{val}")
                changed += 1
                continue
        out.append(line)
    return out, changed


def process(path, dry):
    text = path.read_text(encoding="utf-8")
    if not text.startswith("---"):
        return 0
    end = text.find("\n---", 3)
    if end == -1:
        return 0
    head, rest = text[: end + 1], text[end + 1 :]
    lines = head.split("\n")
    lines, c1 = fix_images(lines)
    lines, c2 = fix_cover(lines)
    total = c1 + c2
    if total and not dry:
        path.write_text("\n".join(lines) + rest, encoding="utf-8")
    return total


def main(argv):
    dry = "--dry-run" in argv
    grand_total = files_changed = 0
    for path in TARGETS:
        n = process(path, dry)
        if n:
            print(f"{path.relative_to(ROOT)}: {n}")
            grand_total += n
            files_changed += 1
    print(f"\n{'(dry-run) ' if dry else ''}{files_changed} faili, {grand_total} teed parandatud")


if __name__ == "__main__":
    main(sys.argv[1:])
