#!/usr/bin/env python3
"""Teisendab PDF-i (nt Google Docsist eksporditud CV) Hugo lehe markdowniks.

Säilitab reavahetused, tühjad read ja rasvase kirja (pealkirjad). Murtud read
liidetakse tagasi üheks reaks, et veebis toimuks murdmine ekraani laiuse järgi.

Vajab poppleri `pdftohtml` käsku (tuleb kaasa `brew install poppler`).

Kasutus:
    python3 scripts/pdf-to-markdown.py CV.pdf > content/pages/cv.md
    python3 scripts/pdf-to-markdown.py CV.pdf --title "CV" --slug cv -o content/pages/cv.md
"""
import argparse
import html
import re
import subprocess
import sys
import tempfile
from pathlib import Path

TEXT_RE = re.compile(
    r'<text top="(\d+)" left="(\d+)" width="(\d+)" height="\d+" font="(\d+)">(.*?)</text>'
)
LINK_RE = re.compile(r'<a href="([^"]+)">(.*?)</a>')
# Uue kirje algus: aastaarv, mis ei ole vahemiku teine pool (nii jääb murtud
# rea järg nagu "1963-1987, kuraatorinäitus ..." eelmise rea külge), või
# jutumärgiga algav pealkiri.
NEW_ENTRY_RE = re.compile(r"^\s*(?:(?:19|20)\d\d(?![-\u2013\u2014]\d)|[\"\u201c\u201e\u00ab\u2019\u2018])")


def pdf_to_xml(pdf_path):
    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp) / "doc"
        subprocess.run(
            ["pdftohtml", "-xml", "-i", "-enc", "UTF-8", str(pdf_path), str(out)],
            check=True,
            capture_output=True,
        )
        return (out.with_suffix(".xml")).read_text(encoding="utf-8")


def span_to_markdown(raw):
    """Üks <text> element markdowniks (rasvane, lingid, HTML-entiteedid)."""
    bold = "<b>" in raw
    text = LINK_RE.sub(lambda m: f"[{strip_tags(m.group(2))}]({m.group(1)})", raw)
    text = strip_tags(text)
    text = html.unescape(text).replace("\xa0", " ")
    if bold:
        stripped = text.strip()
        if stripped:
            text = text.replace(stripped, f"**{stripped}**", 1)
    return text


def strip_tags(s):
    return re.sub(r"<[^>]+>", "", s)


def parse_lines(xml):
    """Tagastab [(tekst, rea_laius)] dokumendi järjekorras, lehtede kaupa."""
    lines = []
    for page in xml.split("<page ")[1:]:
        by_top = {}
        for top, left, width, _font, raw in TEXT_RE.findall(page):
            by_top.setdefault(int(top), []).append((int(left), int(width), raw))
        for top in sorted(by_top):
            spans = sorted(by_top[top])
            text = "".join(span_to_markdown(raw) for _, _, raw in spans).rstrip()
            right = max(left + width for left, width, _ in spans)
            lines.append((text, right))
    return lines


def to_markdown(lines, wrap_threshold=0.85):
    widest = max((r for _, r in lines), default=0)
    limit = widest * wrap_threshold
    out = []
    prev_wrapped = False
    for text, right in lines:
        if not text.strip():
            prev_wrapped = False
            if out and out[-1] != "":
                out.append("")
            continue
        # Murtud rea järg: eelmine rida ulatus peaaegu servani ja see rida ei
        # alusta uut kirjet (aastaarv, jutumärk) ega ole pealkiri.
        cont = prev_wrapped and not NEW_ENTRY_RE.match(text) and not text.startswith("**")
        if cont and out:
            out[-1] = out[-1].rstrip() + " " + text.strip()
        else:
            out.append(text.rstrip())
        prev_wrapped = right >= limit
    while out and out[-1] == "":
        out.pop()
    return "\n".join(out)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("pdf")
    ap.add_argument("--title", default=None, help="Lehe pealkiri front-matteris")
    ap.add_argument("--slug", default=None, help="Lehe slug")
    ap.add_argument("--style", default="cv", help="text_style väärtus (cv või tavaline)")
    ap.add_argument("-o", "--output", default=None)
    ap.add_argument("--no-frontmatter", action="store_true")
    args = ap.parse_args()

    body = to_markdown(parse_lines(pdf_to_xml(args.pdf)))

    if args.no_frontmatter:
        doc = body + "\n"
    else:
        title = args.title or Path(args.pdf).stem
        slug = args.slug or re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")
        doc = (
            "---\n"
            f'title: "{title}"\n'
            f'slug: "{slug}"\n'
            "type: page\n"
            "draft: false\n"
            f'text_style: "{args.style}"\n'
            "---\n\n" + body + "\n"
        )

    if args.output:
        Path(args.output).write_text(doc, encoding="utf-8")
        print(f"Kirjutatud: {args.output} ({len(body.splitlines())} rida)", file=sys.stderr)
    else:
        sys.stdout.write(doc)


if __name__ == "__main__":
    main()
