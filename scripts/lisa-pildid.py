#!/usr/bin/env python3
"""Lisab pilte otse portfoolio töö galeriisse, mööda minnes Sveltia
admini "Pildid" väljast, mis vahel ei salvesta lisatud pilti (fail
jõuab static/images kausta, aga kirjet frontmatterisse ei teki).

Käib nii:
  1. Küsib (macOS dialoog), millisele tööle pilte lisada.
  2. Küsib, milliseid pildifaile lisada (võib valida mitu korraga).
  3. Kopeerib failid static/images kausta (kui neid seal juba pole).
  4. Lisab need otse töö .md faili `images:` väljale, samas stiilis,
     mis failis juba kasutusel (stringinimekiri või objektikirjed).
  5. Kui `cover` on tühi, pannakse esimene lisatud pilt kaaneks.

Ei sõltu admini brauseriseansist ega Sveltia enda salvestuslogikast —
kirjutab faili otse kettale, samamoodi nagu käsitsi redigeerides.

Kasutus: python3 scripts/lisa-pildid.py
"""
import re
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PORTFOLIO = ROOT / "content" / "portfolio"
IMAGES = ROOT / "static" / "images"

TITLE_RE = re.compile(r"^title:\s*(.*?)\s*$")
COVER_RE = re.compile(r"^cover:\s*(.*?)\s*$")
IMAGES_KEY_RE = re.compile(r"^images\s*:\s*$")
ITEM_RE = re.compile(r"^(\s*)-\s*(.*?)\s*$")


def osascript(script):
    result = subprocess.run(["osascript", "-e", script], capture_output=True, text=True)
    if result.returncode != 0:
        return None
    return result.stdout.strip()


def list_entries():
    entries = []
    for path in sorted(PORTFOLIO.glob("*.md")):
        title = path.stem
        for line in path.read_text(encoding="utf-8").split("\n"):
            if line.strip() == "---" and title != path.stem:
                break
            m = TITLE_RE.match(line)
            if m:
                title = m.group(1).strip("'\"") or path.stem
                break
        entries.append((path, title))
    return entries


def pick_entry(entries):
    choices = [f"{title}  ({path.stem})" for path, title in entries]
    applescript_list = "{" + ", ".join('"' + c.replace('"', '\\"') + '"' for c in choices) + "}"
    script = f'''
    set theChoice to choose from list {applescript_list} with prompt "Millisele tööle pilte lisada?" with title "Lisa pildid galeriisse"
    if theChoice is false then
        return "CANCELLED"
    end if
    return item 1 of theChoice
    '''
    result = osascript(script)
    if result is None or result == "CANCELLED":
        return None
    idx = choices.index(result)
    return entries[idx]


def pick_images():
    script = '''
    set theFiles to choose file with prompt "Vali pildifailid:" with multiple selections allowed
    set thePaths to {}
    repeat with f in theFiles
        set end of thePaths to POSIX path of f
    end repeat
    set AppleScript's text item delimiters to linefeed
    return thePaths as text
    '''
    result = osascript(script)
    if not result:
        return []
    return [Path(p) for p in result.split("\n") if p.strip()]


def copy_into_media(src_paths):
    added = []
    for src in src_paths:
        dest = IMAGES / src.name
        if not dest.exists():
            shutil.copy2(src, dest)
        added.append(f"/images/{src.name}")
    return added


def quote(value):
    return "'" + value.replace("'", "''") + "'"


def append_images(path, new_refs):
    text = path.read_text(encoding="utf-8")
    if not text.startswith("---"):
        raise ValueError("faili ei alga frontmatteriga")
    end = text.find("\n---", 3)
    head, rest = text[: end + 1], text[end + 1 :]
    lines = head.split("\n")

    # Leia olemasoleva `images:` bloki stiil (kui plokk on olemas) ja
    # tema viimane rida, kuhu uued kirjed järgi lisada.
    images_line_idx = None
    for i, line in enumerate(lines):
        if IMAGES_KEY_RE.match(line):
            images_line_idx = i
            break

    is_object_style = False
    insert_at = None
    item_indent = "  "

    if images_line_idx is not None:
        i = images_line_idx + 1
        first_item_seen = False
        while i < len(lines):
            m = ITEM_RE.match(lines[i])
            if not (m and lines[i].strip().startswith("-")):
                break
            if not first_item_seen:
                item_indent = m.group(1)
                value = m.group(2)
                is_object_style = value.startswith("{") or re.match(r"^[a-zA-Z_]+\s*:", value)
                first_item_seen = True
            i += 1
            if is_object_style:
                while i < len(lines) and lines[i].strip() != "" and len(lines[i]) - len(lines[i].lstrip()) > len(item_indent):
                    i += 1
        insert_at = i
    else:
        lines.insert(len(lines) - 1, "images:")
        images_line_idx = len(lines) - 2
        insert_at = images_line_idx + 1

    new_lines = []
    for ref in new_refs:
        if is_object_style:
            new_lines.append(f"{item_indent}- image: {ref}")
            new_lines.append(f"{item_indent}  caption: ''")
            new_lines.append(f"{item_indent}  alt: ''")
        else:
            new_lines.append(f"{item_indent}- {ref}")

    lines[insert_at:insert_at] = new_lines

    # Kui cover on tühi, pane esimene uus pilt kaaneks.
    for i, line in enumerate(lines):
        m = COVER_RE.match(line)
        if m and not m.group(1).strip("'\""):
            lines[i] = f"cover: {new_refs[0]}"
            break

    new_head = "\n".join(lines)
    path.write_text(new_head + rest, encoding="utf-8")


def main():
    entries = list_entries()
    if not entries:
        osascript('display alert "Ühtegi portfoolio tööd ei leitud" as warning')
        return 1

    chosen = pick_entry(entries)
    if chosen is None:
        print("Tühistatud.")
        return 0
    path, title = chosen

    images = pick_images()
    if not images:
        print("Tühistatud.")
        return 0

    refs = copy_into_media(images)
    append_images(path, refs)

    names = ", ".join(r.split("/")[-1] for r in refs)
    osascript(
        f'display notification "{title}: {len(refs)} pilti lisatud ({names})" '
        'with title "Pildid lisatud"'
    )
    print(f"{path.relative_to(ROOT)}: lisatud {len(refs)} pilti.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
