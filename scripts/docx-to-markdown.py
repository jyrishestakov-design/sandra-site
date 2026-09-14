#!/usr/bin/env python3
"""Teisendab .docx faili Sveltia admini "Sisu"/"Kirjeldus" väljale sobivaks
Markdowniks, säilitades Wordi lõikude vahed.

.docx on lihtsalt zip-fail, mis sisaldab word/document.xml — ei vaja
python-docx paketti, ainult Pythoni oma teeke.

Word eristab lõikude vahel:
  - tavaline lõigulõpp (uus lõik, tühi rida vahel) -> jääb Markdownis
    tühjaks reaks kahe lõigu vahele.
  - lõik, mille "vahe pärast" (space after) on 0pt -> Word näitab seda
    tihedalt järgmise reaga koos (nt pealkirjaplokk, autoriplokk,
    kontaktid) -> Markdownis kasutatakse kaldkriipsuga reamurdmist
    (rea lõpus "\\"), mis ei tekita CSS-i lõigumarginaali (vt main.css
    ".page-content p { margin-bottom: 1.5rem }" - kehtib ainult <p>
    elementide, mitte <br> vahel).

Rasvane ja kaldkiri säilivad (**rasvane**, *kaldkiri*).

Kasutus:
    python3 scripts/docx-to-markdown.py teade.docx
    python3 scripts/docx-to-markdown.py teade.docx | pbcopy
"""
import argparse
import subprocess
import sys
import zipfile
from xml.etree import ElementTree as ET

W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"


def load_paragraphs(docx_path):
    with zipfile.ZipFile(docx_path) as z:
        xml_bytes = z.read("word/document.xml")
    root = ET.fromstring(xml_bytes)
    body = root.find(f"{W}body")
    paragraphs = []
    for p in body.findall(f"{W}p"):
        paragraphs.append(parse_paragraph(p))
    return paragraphs


def parse_paragraph(p):
    ppr = p.find(f"{W}pPr")
    space_after = None
    if ppr is not None:
        spacing = ppr.find(f"{W}spacing")
        if spacing is not None:
            after = spacing.get(f"{W}after")
            if after is not None:
                space_after = int(after) / 20  # twips -> points

    # Koosta tekst, ühendades järjestikused ühesuguse vormindusega "run"id,
    # et vältida "****" tüüpi katkist Markdown-süntaksit.
    runs = []  # list of (text, bold, italic)
    for r in p.findall(f"{W}r"):
        text = "".join(t.text or "" for t in r.findall(f"{W}t"))
        if r.find(f"{W}tab") is not None:
            text += "\t"
        if not text:
            continue
        rpr = r.find(f"{W}rPr")
        bold = rpr is not None and rpr.find(f"{W}b") is not None
        italic = rpr is not None and rpr.find(f"{W}i") is not None
        if runs and runs[-1][1] == bold and runs[-1][2] == italic:
            runs[-1] = (runs[-1][0] + text, bold, italic)
        else:
            runs.append((text, bold, italic))

    parts = []
    for text, bold, italic in runs:
        stripped = text.strip()
        if not stripped:
            parts.append(text)
            continue
        lead = text[: len(text) - len(text.lstrip())]
        trail = text[len(text.rstrip()):]
        core = stripped
        if bold:
            core = f"**{core}**"
        if italic:
            core = f"*{core}*"
        parts.append(lead + core + trail)

    text = "".join(parts).strip()
    return text, space_after


def to_markdown(paragraphs):
    out = []
    n = len(paragraphs)
    for i, (text, space_after) in enumerate(paragraphs):
        if not text:
            continue  # tühjad lõigud (käsitsi tühjad read) jätame vahele
        out.append(text)
        is_last = i == n - 1
        next_is_empty_or_last = is_last or not paragraphs[i + 1][0]
        tight = space_after is not None and space_after < 4 and not next_is_empty_or_last
        out.append(" \\\n" if tight else "\n\n")
    return "".join(out).rstrip() + "\n"


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("docx", help="Sisend .docx fail")
    ap.add_argument("--copy", action="store_true", help="Kopeeri tulemus lõikelauale (pbcopy)")
    args = ap.parse_args()

    paragraphs = load_paragraphs(args.docx)
    markdown = to_markdown(paragraphs)

    if args.copy:
        subprocess.run(["pbcopy"], input=markdown.encode("utf-8"), check=True)
        print(f"Kopeeritud lõikelauale ({len(markdown)} tähemärki).", file=sys.stderr)
    else:
        sys.stdout.write(markdown)


if __name__ == "__main__":
    main()
