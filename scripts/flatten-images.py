#!/usr/bin/env python3
"""Ühekordne migratsioon (migrate-images.py vastand): content/portfolio/*.md
failides `images` väli objektinimekirjast

    images:
      - image: "faili.jpg"
        caption: ""
        alt: ""

(või Sveltia enda kirjutatud kujul, ilma jutumärkideta ja täieliku teega:

    images:
      - image: /images/faili.jpg
        caption: ''
        alt: ''
)

tagasi lihtsaks stringinimekirjaks

    images:
      - "faili.jpg"
      # või - /images/faili.jpg, olenevalt algsest kujust

Vaja, sest Sveltia CMS-i uus `widget: image, multiple: true` väli (mis
lubab mitu pilti korraga lohistada) salvestab ainult pilditeede
massiivi, mitte objekte.

Ohutu: kirjeid, millel on caption või alt täidetud, EI puudutata — need
jäävad objektikujule alles ja loetletakse hoiatusena, et andmeid ei
kaotataks vaikimisi.

Idempotentne: juba stringikujul kirjeid ei puutu (ei ole `key: value`
ega `{...}` kujul).

Kasutus: python3 scripts/flatten-images.py [--dry-run] [failid...]
"""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PORTFOLIO = ROOT / "content" / "portfolio"

ITEM_RE = re.compile(r"^(\s*)-\s*(.*?)\s*$")
KV_RE = re.compile(r"^\s*([a-zA-Z_]+):\s*(.*?)\s*$")


def unquote(value):
    if len(value) >= 2 and value[0] == value[-1] == '"':
        return value[1:-1].replace('\\"', '"')
    if len(value) >= 2 and value[0] == value[-1] == "'":
        return value[1:-1].replace("''", "'")
    return value


def quote(value):
    return '"' + value.replace("\\", "\\\\").replace('"', '\\"') + '"'


def flatten_frontmatter(head, path):
    """head = front matter, algusest kuni lõpetava `---`ni (kaasa arvatud)."""
    lines = head.split("\n")
    out, changed, skipped = [], 0, []
    i, n = 0, len(lines)
    while i < n:
        line = lines[i]
        if not re.match(r"^images\s*:\s*$", line):
            out.append(line)
            i += 1
            continue
        out.append(line)
        i += 1
        item_indent = None
        while i < n:
            item_m = ITEM_RE.match(lines[i])
            if not (item_m and lines[i].strip().startswith("-")):
                break
            indent = len(item_m.group(1))
            if item_indent is None:
                item_indent = indent
            if indent != item_indent:
                break
            value = item_m.group(2)
            if not (value.startswith("{") or re.match(r"^[a-zA-Z_]+\s*:", value)):
                out.append(lines[i])  # juba stringikujul
                i += 1
                continue
            # objektikirje: `- image: ...` + indenditud `caption:`/`alt:` read
            obj = {}
            kv = KV_RE.match(value)
            if kv:
                obj[kv.group(1)] = unquote(kv.group(2))
            i += 1
            while i < n:
                sub = lines[i]
                if sub.strip() == "" or len(sub) - len(sub.lstrip()) <= item_indent:
                    break
                sub_m = KV_RE.match(sub)
                if sub_m:
                    obj[sub_m.group(1)] = unquote(sub_m.group(2))
                i += 1
            caption = obj.get("caption", "")
            alt = obj.get("alt", "")
            img = obj.get("image", "")
            pad = " " * item_indent
            if caption or alt:
                out.append(f"{pad}- image: {quote(img)}")
                out.append(f"{pad}  caption: {quote(caption)}")
                out.append(f"{pad}  alt: {quote(alt)}")
                skipped.append((path, img, caption, alt))
            else:
                out.append(f"{pad}- {quote(img)}")
                changed += 1
    return "\n".join(out), changed, skipped


def flatten(text, path):
    if not text.startswith("---"):
        return text, 0, []
    end = text.find("\n---", 3)
    if end == -1:
        return text, 0, []
    head, rest = text[: end + 1], text[end + 1 :]
    new_head, changed, skipped = flatten_frontmatter(head, path)
    return new_head + rest, changed, skipped


def main(argv):
    dry = "--dry-run" in argv
    files = [Path(a) for a in argv if not a.startswith("--")] or sorted(PORTFOLIO.glob("*.md"))
    total_files = total_items = 0
    all_skipped = []
    for path in files:
        text = path.read_text(encoding="utf-8")
        new, n, skipped = flatten(text, path)
        all_skipped.extend(skipped)
        if n:
            total_files += 1
            total_items += n
            print(f"{path.relative_to(ROOT)}: {n} pilti")
            if not dry:
                path.write_text(new, encoding="utf-8")
    if all_skipped:
        print("\nHOIATUS — jäeti puutumata, sest caption või alt on täidetud:")
        for path, img, cap, alt in all_skipped:
            print(f"  {path.relative_to(ROOT)}: {img} (caption={cap!r}, alt={alt!r})")
    tail = f", {len(all_skipped)} jäeti puutumata" if all_skipped else ""
    print(f"\n{'(dry-run) ' if dry else ''}{total_files} faili, {total_items} pildikirjet lamestatud{tail}")


if __name__ == "__main__":
    main(sys.argv[1:])
