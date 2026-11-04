#!/usr/bin/env python3
"""
Sandra konkursid — iganädalane konkursiotsing ilma tasulise tehisaruta.

Käik:
  1. Kogub kutsete lingid avalikest koondlehtedest (allikad allpool).
  2. Loeb iga kutse enda lehe läbi ja võtab välja: tähtaja, osalustasu,
     kunstnikutasu / kaetud kulud, residentuuri kestuse, piirangud
     (vanus, elukoht, tudengid), partneri nõude, liigi ja piirkonna.
  3. Annab punktid Sandra reeglite järgi. Kõva välistus: osalustasu,
     pikk residentuur, tähtaeg möödas / alla 7 päeva, piiratud sobivus.
  4. Kui Sandra on lehel staatusi märkinud, õpib neist (naiivne Bayes)
     ja liidab tõenäosuse punktidele.
  5. Kirjutab static/konkursid/data.json, mida loeb leht /konkursid/.

Ainult Pythoni standardteek — GitHub Actionsis pole vaja midagi paigaldada.
Käivitus:  python3 scripts/konkursid/konkursid.py
"""
from __future__ import annotations

import datetime as dt
import hashlib
import html
import json
import math
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from html.parser import HTMLParser
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "static" / "konkursid" / "data.json"
SEED = Path(__file__).with_name("seed.json")
UA = "Mozilla/5.0 (compatible; SandraKonkursid/1.0; +https://sandrajogeva.artcontainer.ee/)"
TODAY = dt.date.today()
MIN_DAYS = 7            # tähtaeg vähemalt nii kaugel
MAX_RES_DAYS = 24       # residentuur kuni ~3 nädalat (+ väike varu)
KEEP_SCORE = 2          # sellest alates tabelisse
SURE_SCORE = 5          # sellest alates ilma „Kontrolli üle“ sildita
MAX_DETAIL_FETCH = 300  # ühe jooksu jooksul loetavate lehtede ülempiir (koondleht + korraldaja leht)

LOG: list[str] = []


def log(*a):
    s = " ".join(str(x) for x in a)
    LOG.append(s)
    print(s, flush=True)


# ---------------------------------------------------------------- võrk
def fetch(url: str, timeout: int = 25) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept-Language": "en,et;q=0.8"})
    for attempt in range(2):
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                raw = r.read(3_000_000)
                cs = r.headers.get_content_charset() or "utf-8"
                return raw.decode(cs, errors="replace")
        except (urllib.error.URLError, TimeoutError, ConnectionError) as e:
            if attempt == 1:
                raise
            time.sleep(2)
    return ""


# ---------------------------------------------------------------- HTML -> tekst
class _Text(HTMLParser):
    SKIP = {"script", "style", "noscript", "svg", "nav", "footer", "header", "form", "aside", "iframe"}
    BLOCK = {"p", "div", "li", "br", "h1", "h2", "h3", "h4", "h5", "tr", "section", "article", "dd", "dt"}

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self.skip = 0
        self.title = ""
        self._in_title = False
        self.meta_desc = ""
        self.h1 = ""
        self._in_h1 = False

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag in self.SKIP:
            self.skip += 1
        if tag == "title":
            self._in_title = True
        if tag == "h1" and not self.h1:
            self._in_h1 = True
        if tag == "meta" and (a.get("name") == "description" or a.get("property") == "og:description"):
            self.meta_desc = self.meta_desc or (a.get("content") or "")
        if tag in self.BLOCK:
            self.parts.append("\n")

    def handle_endtag(self, tag):
        if tag in self.SKIP and self.skip:
            self.skip -= 1
        if tag == "title":
            self._in_title = False
        if tag == "h1":
            self._in_h1 = False
        if tag in self.BLOCK:
            self.parts.append("\n")

    def handle_data(self, data):
        if self._in_title:
            self.title += data
        if self._in_h1:
            self.h1 += data
        if not self.skip:
            self.parts.append(data)


def html_to_text(src: str) -> dict:
    # eelista <main> või <article> sisu, kui see on olemas
    m = re.search(r"<(main|article)\b.*?</\1>", src, re.S | re.I)
    body = m.group(0) if m and len(m.group(0)) > 1500 else src
    p = _Text()
    try:
        p.feed(body)
    except Exception:
        pass
    text = re.sub(r"[ \t\xa0]+", " ", "".join(p.parts))
    text = re.sub(r"\n\s*\n+", "\n", text).strip()
    meta = _Text()
    try:
        meta.feed(src[:60000])
    except Exception:
        pass
    return {"text": text, "title": (p.h1 or meta.h1 or meta.title).strip(), "desc": html.unescape(meta.meta_desc).strip()}


APPLY_TXT = re.compile(r"^\s*(?:apply(?: now| here)?|more info(?:rmation)?(?: (?:&|and) apply)?|full (?:call|details)|official (?:call|website)|kandideeri|lisainfo|vaata lähemalt)\b", re.I)


def apply_link(src: str, base: str) -> str | None:
    """Kutse enda leht: koondlehe „Apply“ / „More info & apply“ nupu siht."""
    host = urllib.parse.urlparse(base).netloc
    for m in re.finditer(r"<a\b[^>]*href=[\"']?([^\"' >]+)[\"']?[^>]*>(.*?)</a>", src, re.S | re.I):
        href, label = html.unescape(m.group(1)), strip_tags(m.group(2))
        if not APPLY_TXT.search(label):
            continue
        url = urllib.parse.urljoin(base, href)
        if url.startswith("http") and urllib.parse.urlparse(url).netloc != host and not re.search(r"facebook|twitter|instagram|linkedin|mailto", url):
            return url
    return None


def strip_tags(s: str) -> str:
    s = re.sub(r"<[^>]+>", " ", html.unescape(s))
    return re.sub(r"\s+", " ", s).strip()


# ---------------------------------------------------------------- kuupäevad
MONTHS = {
    "jan": 1, "january": 1, "jaan": 1, "jaanuar": 1, "tammikuu": 1,
    "feb": 2, "february": 2, "veebr": 2, "veebruar": 2, "helmikuu": 2,
    "mar": 3, "march": 3, "märts": 3, "maaliskuu": 3,
    "apr": 4, "april": 4, "aprill": 4, "huhtikuu": 4,
    "may": 5, "mai": 5, "toukokuu": 5,
    "jun": 6, "june": 6, "juuni": 6, "kesäkuu": 6,
    "jul": 7, "july": 7, "juuli": 7, "heinäkuu": 7,
    "aug": 8, "august": 8, "elokuu": 8,
    "sep": 9, "sept": 9, "september": 9, "syyskuu": 9,
    "oct": 10, "october": 10, "okt": 10, "oktoober": 10, "lokakuu": 10,
    "nov": 11, "november": 11, "marraskuu": 11,
    "dec": 12, "december": 12, "dets": 12, "detsember": 12, "joulukuu": 12,
}
MON_RE = "|".join(sorted(MONTHS, key=len, reverse=True))
DATE_PATTERNS = [
    # 30 October 2026 / 30. oktoober 2026 / 30th Oct, 2026
    re.compile(r"\b(\d{1,2})(?:st|nd|rd|th)?\.?\s+(" + MON_RE + r")\.?,?\s+(\d{4})\b", re.I),
    # October 30, 2026 / Oct. 30th 2026
    re.compile(r"\b(" + MON_RE + r")\.?\s+(\d{1,2})(?:st|nd|rd|th)?,?\s+(\d{4})\b", re.I),
    # 30.10.2026 / 30/10/2026
    re.compile(r"\b(\d{1,2})[./](\d{1,2})[./](\d{4})\b"),
    # 2026-10-30
    re.compile(r"\b(\d{4})-(\d{2})-(\d{2})\b"),
]


def _mk(y, m, d):
    try:
        return dt.date(int(y), int(m), int(d))
    except ValueError:
        return None


def find_dates(s: str) -> list[tuple[int, dt.date]]:
    out = []
    for i, pat in enumerate(DATE_PATTERNS):
        for m in pat.finditer(s):
            g = m.groups()
            if i == 0:
                d = _mk(g[2], MONTHS.get(g[1].lower().rstrip(".")), g[0])
            elif i == 1:
                d = _mk(g[2], MONTHS.get(g[0].lower().rstrip(".")), g[1])
            elif i == 2:
                d = _mk(g[2], g[1], g[0])
            else:
                d = _mk(g[0], g[1], g[2])
            if d:
                out.append((m.start(), d))
    return sorted(out)


DEADLINE_KW = re.compile(
    r"deadline|apply by|applications? (?:close|due|must be (?:received|submitted))|closing date|submission(?:s)? (?:close|due)|"
    r"due date|tähtaeg|hakuaika päättyy|viimeistään|sista ansökningsdag|ansökan senast|søknadsfrist|ansøgningsfrist|frist",
    re.I)


NOYEAR = [
    re.compile(r"\b(\d{1,2})(?:st|nd|rd|th)?\.?\s+(" + MON_RE + r")\b(?!\.?,?\s+\d{4})", re.I),
    re.compile(r"\b(" + MON_RE + r")\.?\s+(\d{1,2})(?:st|nd|rd|th)?\b(?!,?\s+\d{4})", re.I),
]


def _infer_year(mon: int, day: int) -> dt.date | None:
    for y in (TODAY.year, TODAY.year + 1):
        d = _mk(y, mon, day)
        if d and d >= TODAY - dt.timedelta(days=30):
            return d
    return None


def find_deadline(text: str) -> dt.date | None:
    dates = find_dates(text)
    best = None
    for m in DEADLINE_KW.finditer(text):
        window_end = m.end() + 140
        hit = None
        for pos, d in dates:
            if m.start() - 20 <= pos <= window_end:
                hit = d
                break
        if hit is None:  # „Deadline: November 15“ – aasta puudub
            win = text[m.end():window_end]
            for i, pat in enumerate(NOYEAR):
                mm = pat.search(win)
                if mm:
                    g = mm.groups()
                    mon = MONTHS.get((g[1] if i == 0 else g[0]).lower().rstrip("."))
                    day = int(g[0] if i == 0 else g[1])
                    if mon and 1 <= day <= 31:
                        hit = _infer_year(mon, day)
                        break
        if hit and (best is None or (hit >= TODAY and (best < TODAY or hit < best))):
            best = hit
    return best


# ---------------------------------------------------------------- väljavõtt
NUM_WORDS = {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7, "eight": 8,
             "nine": 9, "ten": 10, "twelve": 12, "a": 1, "üks": 1, "kaks": 2, "kolm": 3, "neli": 4}
DUR_RE = re.compile(r"\b(\d{1,3}|" + "|".join(NUM_WORDS) + r")[\s-]*(day|days|week|weeks|month|months|päev|päeva|nädal|nädalat|kuu|kuud)\b", re.I)
UNIT_DAYS = {"day": 1, "days": 1, "päev": 1, "päeva": 1, "week": 7, "weeks": 7, "nädal": 7, "nädalat": 7,
             "month": 30, "months": 30, "kuu": 30, "kuud": 30}
RES_CTX = re.compile(r"residen|stay|period|duration|lasts?|takes place over|programme runs|studio for|free studio|fellowship|residentuur|kestus", re.I)


def sentences(text: str) -> list[str]:
    return [s.strip() for s in re.split(r"(?<=[.!?])\s+|\n", text) if len(s.strip()) > 3]


def residency_days(text: str) -> int | None:
    vals = []
    for s in sentences(text):
        if not RES_CTX.search(s):
            continue
        if re.search(r"notif|announce|respon|result|within|after the deadline|before", s, re.I):
            continue
        for m in DUR_RE.finditer(s):
            n = m.group(1).lower()
            n = NUM_WORDS.get(n, None) if not n.isdigit() else int(n)
            if not n:
                continue
            vals.append(n * UNIT_DAYS[m.group(2).lower()])
    vals = [v for v in vals if 2 <= v <= 400]
    if not vals:
        return None
    return max(vals)


FEE_WORDS = r"(?:application|entry|submission|participation|registration|processing|admin(?:istration)?|jury(?:ing)?|handling|hanging)\s+fees?|osalustasu|registreerimistasu|ansökningsavgift|osallistumismaksu|hakemusmaksu"
FEE_RE = re.compile(FEE_WORDS, re.I)
NO_FEE_RE = re.compile(r"\b(no|free|without|waived|none|zero|not charge|isn't|is not|there is no|ei ole|puudub|tasuta|ingen|ei)\b", re.I)
MONEY_RE = re.compile(r"(?:€|eur|euro|\$|usd|£|gbp|sek|nok|dkk|chf)\s?\d[\d.,\s]*|\d[\d.,\s]*(?:€|eur\b|euros?\b|usd\b|\$|£|gbp\b|sek\b|nok\b|dkk\b|chf\b|kr\b)", re.I)

PAY_TO_SHOW = re.compile(
    r"(?:artists? (?:are|is|will be) (?:responsible for|expected to (?:cover|pay)|required to (?:cover|pay))|"
    r"(?:rental|hire|participation|exhibition) (?:fee|cost)s? (?:is|are|of)\s?(?:€|\$|£|\d)|"
    r"self[- ]funded|at (?:the|their) (?:own|artist'?s?) (?:cost|expense)|artists? (?:must|should) (?:cover|pay)|"
    r"residency (?:fee|cost)s? (?:is|are|of)|programme fee|program fee|tuition|the cost of the residency is|"
    r"(?:are|is) (?:covered|paid|borne) by the (?:artist|participant|resident)s?|per (?:\d+[- ])?night (?:term|stay)|"
    r"(?:jpy|usd|eur|€|\$|£)\s?[\d,.]+ per (?:week|month|night|term|person)|secure your (?:chosen )?(?:place|route|spot)|"
    r"confirm(?:ing)? your place|showcase (?:route|package)|exhibition package|participation package|wall (?:space )?rent|booth fee|"
    r"is there a (?:participation|submission|application) fee)"
    r"(?![^.]{0,40}(?:paid to|stipend|honorar))",
    re.I)
PAID_RE = {
    "kunstnikutasu": re.compile(r"artist'?s? fees?|artist honorari|honorari(?:um|a)|exhibition fee (?:of|for)|fee for (?:the )?artists?|paid (?:an? )?fee|kunstnikutasu|näitusetasu|utställningsersättning|utstillingshonorar|visningsvederlag|näyttelypalkkio|stipend|bursary|per diem|daily allowance|grant of|award of|prize of|commission fee", re.I),
    "tootmiseelarve": re.compile(r"production (?:budget|costs?|support|grant)|materials? budget|budget (?:of|for) (?:the )?(?:production|project)|tootmiseelarve", re.I),
    "sõit": re.compile(r"travel(?:ling)? (?:costs?|expenses|grant|allowance|support)? ?(?:are |is |will be )?(?:covered|paid|reimbursed|included|provided)|(?:covers?|reimburse[sd]?) (?:the )?travel|travel (?:grant|allowance|support)|flights? (?:covered|included|paid)", re.I),
    "majutus": re.compile(r"accommodation (?:is |are |will be )?(?:provided|covered|included|free)|(?:free|provided) accommodation|housing (?:is )?(?:provided|included)|studio and accommodation", re.I),
    "transport": re.compile(r"(?:shipping|transport(?:ation)?) of (?:the )?works? (?:is |are )?(?:covered|paid)|covers? (?:the )?(?:shipping|transport)", re.I),
}
RESTRICT = [
    (re.compile(r"\b(?:under|younger than|up to the age of|aged? (?:between )?\d{2}\s?(?:-|–|to|and)\s?)(\d{2})\b", re.I), "vanusepiirang"),
    (re.compile(r"\b(?:students? only|current(?:ly enrolled)? students|enrolled (?:in|at)|graduat(?:e|ing) students|bfa|mfa students|undergraduate)\b", re.I), "tudengitele"),
    (re.compile(r"\b(?:emerging artists? only|early[- ]career artists? only|recent (?:art school )?graduates|graduates? (?:of|from) (?:the )?(?:last|past) \w+ years|graduated (?:in|between|after) 20\d\d)\b", re.I), "alustavatele"),
    (re.compile(r"\b(?:be of|must be (?:of)?) [A-Z][a-z]+ (?:nationality|heritage|descent)|[A-Z][a-z]+ (?:nationality|heritage) (?:or|and) [A-Z][a-z]+ heritage|[A-Z][a-z]+(?:-born| heritage) artists only\b"), "kodakondsuspiirang"),
    (re.compile(r"\b(?:resident|based|living|residing) in (?:the )?(?:uk|united kingdom|england|scotland|wales|ireland|northern ireland|usa?|united states|canada|australia|new zealand|india|china|korea|japan|taiwan|singapore|indonesia|mexico|brazil|south africa|south america|latin america|africa|asia|new york|california|texas|london|berlin|paris|vienna|austria|germany|switzerland|norway|denmark|sweden|finland|iceland|netherlands|belgium|france|italy|spain|portugal|poland|latvia|lithuania|nrw)\b(?![^.]{0,40}(?:or|and) (?:internationally|abroad|elsewhere|europe|estonia|baltic))", re.I), "elukohapiirang"),
    (re.compile(r"\b(?:citizens? of|nationals? of|nationality of|passport holders? of)\b(?![^.]{0,60}(?:any|all|eu|european|estonia|baltic))", re.I), "kodakondsuspiirang"),
    (re.compile(r"\b(?:artists? from the arab (?:world|region)|arab artists|from the global south only|black artists only|indigenous artists only)\b", re.I), "sihtrühm"),
    (re.compile(r"\b(?:postdoctoral|post-doctoral|phd (?:students|candidates|holders) only|doctoral researchers|internship|interns?\b|trainee)", re.I), "teadlastele / praktikandile"),
    (re.compile(r"\bfor (?:palestinian|ukrainian|ukraine-based|african|asian|latin american|indigenous|black|south asian|southeast asia-based) (?:and [\w-]+ )?artists\b", re.I), "sihtrühm"),
]
OPEN_WIDE = re.compile(r"open to (?:all|artists) (?:from )?(?:all over the world|worldwide|internationally|of all nationalities|from any country|regardless of)|international (?:artists|applicants) (?:are )?(?:welcome|eligible)|anyone,? from anywhere|all nationalities|no (?:age|nationality) restriction|estonia|baltic|nordic and baltic|nordic-baltic|eu member state|creative europe countr", re.I)
PARTNER = re.compile(r"(?:collaborat(?:ing|ion|ive) partner|must (?:apply|work) (?:with|together with) (?:a |an )?(?:partner|collaborator|host)|duos?,? (?:or )?collectives? only|in pairs|teams? of (?:two|2|at least))", re.I)

TYPE_KW = {
    "Residentuur": re.compile(r"residen|artist[- ]in[- ]residence|\bair\b|residentuur", re.I),
    "Toetus": re.compile(r"\bgrant|fund(?:ing)?\b|stipend|scholarship|bursary|fellowship|mobility|stipendium|toetus|award|prize", re.I),
    "Näitus": re.compile(r"exhibition|show|biennial|biennale|triennial|festival|open call|gallery|kunsthall|konsthall|näitus|galerii|presentation|screening", re.I),
}
MEDIA_PLUS = re.compile(r"performance|live art|performative|painting|painter|installation|video art|moving image|photograph|multidisciplinary|interdisciplinary|contemporary art|visual art|feminis|gender|body|text[- ]based|spoken word|curator|curatorial", re.I)
MEDIA_MINUS = re.compile(r"\b(?:musicians?|composers?|orchestra|choir|singers?|dance companies|choreograph|theatre compan|playwright|novelists?|poets? only|writers? only|literary translat|architects?|architecture|urban plann|game designers?|fashion design|product design|ceramic(?:ist)?s? only|textile artists?|glass artists?|jewel(?:le)?ry|illustrators?|comics|filmmakers?|film festival|short films?|documentary films?|podcast|scientists|journalists|designers in residence)\b", re.I)
CALLISH = re.compile(r"open call|call for|apply|application|submission|konkurss|avatud kutse|taotl|haku|ansök|søknad", re.I)

COUNTRY_REGION = [
    ("Eesti", r"estonia|eesti|tallinn|tartu|narva|pärnu|saaremaa|kuressaare|viljandi"),
    ("Põhjamaad ja Baltikum", r"finland|helsinki|sweden|stockholm|gothenburg|malmö|norway|oslo|bergen|denmark|copenhagen|iceland|reykjavik|latvia|riga|lithuania|vilnius|nordic|baltic|åland|faroe|soome|rootsi|norra|taani|läti|leedu"),
    ("Euroopa", r"germany|berlin|france|paris|italy|spain|portugal|netherlands|belgium|austria|vienna|switzerland|poland|czech|slovakia|slovenia|croatia|serbia|hungary|romania|bulgaria|greece|cyprus|ireland|uk|united kingdom|england|scotland|wales|europe|european|ukraine|georgia|armenia|türkiye|turkey|malta|luxembourg"),
]


def guess_region(s: str) -> str:
    low = s.lower()
    for name, pat in COUNTRY_REGION:
        if re.search(r"\b(?:" + pat + r")\b", low):
            return name
    return "Maailm"


def region_for(title: str, text: str) -> str:
    """Kõigepealt pealkirja sulud „(Latvia)“, siis ArtRabbiti „Locations:“, alles siis tekst."""
    m = re.search(r"\(([^()]{3,60})\)\s*$", title)
    if m:
        return guess_region(m.group(1))
    m = re.search(r"Locations?:\s*([^\n]{3,80})", text)
    if m:
        loc = m.group(1)
        if re.search(r"international|worldwide|online|global", loc, re.I):
            return "Maailm"
        return guess_region(loc)
    return guess_region(title + " " + text[:2500])


def guess_type(title: str, text: str) -> str:
    head = title + " " + text[:600]
    for t in ("Residentuur", "Toetus", "Näitus"):
        if TYPE_KW[t].search(title):
            return t
    scores = {t: len(p.findall(head)) for t, p in TYPE_KW.items()}
    return max(scores, key=scores.get) if any(scores.values()) else "Näitus"


def fee_status(text: str) -> tuple[str, str]:
    """('ei', snippet) | ('jah', snippet) | ('?', '')"""
    found_yes, found_no = "", ""
    for m in FEE_RE.finditer(text):
        a, b = max(0, m.start() - 60), min(len(text), m.end() + 70)
        ctx = text[a:b]
        before = text[max(0, m.start() - 45):m.start()]
        after = text[m.end():m.end() + 45]
        if NO_FEE_RE.search(before) or re.search(r"^\W{0,3}(?:is |are )?(?:none|free|waived|not required|no\b|n/a|0\b|€?\s?0[.,]?0*\b)", after, re.I) or re.search(r"free of charge|no fee|without (?:a |any )?fee|fee[- ]free", ctx, re.I):
            found_no = found_no or ctx
        elif MONEY_RE.search(ctx) or re.search(r"(?:fee|tasu)\s*(?:is|of|:)", ctx, re.I):
            found_yes = found_yes or ctx
    if re.search(r"free (?:to apply|to enter|application|submission)|no (?:application|entry|submission) fee|application is free|free of charge to apply|tasuta osaleda|osalemine on tasuta", text, re.I):
        found_no = found_no or "free to apply"
    if found_yes and not found_no:
        return "jah", found_yes.strip()
    if found_no:
        return "ei", found_no.strip()
    return "?", ""


def money_snippets(text: str) -> list[str]:
    out = []
    for s in sentences(text):
        if MONEY_RE.search(s) and not FEE_RE.search(s) and len(s) < 260:
            if re.search(r"fee|honorar|stipend|grant|budget|award|prize|covered|allowance|per diem|tasu|toetus|eelarve|ersättning|honorar|palkkio|travel|accommodation", s, re.I):
                out.append(s)
    return out[:3]


def summarise(desc: str, text: str) -> str:
    desc = re.sub(r"^[\w &]+ \| Promoted:\s*", "", desc)
    base = desc if len(desc) > 80 else ""
    if not base:
        sents = [s for s in sentences(text) if 60 < len(s) < 400 and not re.search(r"cookie|subscribe|newsletter|share this|log in|menu", s, re.I)]
        base = " ".join(sents[:2])
    base = re.sub(r"\s+", " ", base).strip()
    return (base[:380].rsplit(" ", 1)[0] + "…") if len(base) > 390 else base


# ---------------------------------------------------------------- allikad
def src_onthemove() -> list[dict]:
    out = []
    try:
        x = fetch("https://on-the-move.org/news/deadlines")
    except Exception as e:
        log("On the Move: viga", e)
        return out
    keep = {"Project funding", "Presenting work", "Competitions & awards", "Residencies", "Fellowships"}
    for sec in re.split(r"<h2[^>]*>", x)[1:]:
        name = strip_tags(sec.split("</h2>", 1)[0])
        if name not in keep:
            continue
        for m in re.finditer(r'<a href="(/news/[^"]+)"[^>]*>(.*?)</a>.*?datetime="(\d{4}-\d{2}-\d{2})', sec, re.S):
            out.append({"url": "https://on-the-move.org" + m.group(1), "title": strip_tags(m.group(2)),
                        "deadline": m.group(3), "source": "On the Move", "section": name})
    # sama kutse võib olla mitme kuutähtajaga – jäta lähim tulevane
    best: dict[str, dict] = {}
    for it in out:
        d = dt.date.fromisoformat(it["deadline"])
        cur = best.get(it["url"])
        if d >= TODAY + dt.timedelta(days=MIN_DAYS) and (cur is None or d < dt.date.fromisoformat(cur["deadline"])):
            best[it["url"]] = it
    log("On the Move:", len(best))
    return list(best.values())


def src_artrabbit() -> list[dict]:
    out = []
    for page in ("https://www.artrabbit.com/artist-opportunities",
                 "https://www.artrabbit.com/artist-opportunities?type=Exhibition+Opportunity",
                 "https://www.artrabbit.com/artist-opportunities?type=Residency"):
        try:
            x = fetch(page)
        except Exception as e:
            log("ArtRabbit: viga", e)
            continue
        for m in re.finditer(r'href="(/artist-opportunities/\d{4}/[a-z]+/[^"/?#]+)"[^>]*>(.*?)</a>', x, re.S):
            t = strip_tags(m.group(2))
            if len(t) > 8:
                out.append({"url": "https://www.artrabbit.com" + m.group(1), "title": t, "source": "ArtRabbit"})
    uniq = {i["url"]: i for i in out}
    log("ArtRabbit:", len(uniq))
    return list(uniq.values())


def src_ekl() -> list[dict]:
    out = []
    try:
        x = fetch("https://eaa.ee/en/uritused/ekl-konkursid")
    except Exception as e:
        log("EKL: viga", e)
        return out
    main = re.search(r'<main\b.*?</main>', x, re.S)
    x = main.group(0) if main else x
    for m in re.finditer(r'href="(/en/[a-z0-9-]{15,})"[^>]*>(.*?)</a>', x, re.S):
        t = strip_tags(m.group(2))
        if len(t) > 15 and not t.lower().startswith(("show all", "read more")):
            out.append({"url": "https://eaa.ee" + m.group(1), "title": t, "source": "EKL"})
    uniq = {i["url"]: i for i in out}
    log("EKL:", len(uniq))
    return list(uniq.values())


def _rss(url: str, source: str) -> list[dict]:
    out = []
    try:
        x = fetch(url)
    except Exception as e:
        log(source + ": viga", e)
        return out
    for item in x.split("<item>")[1:]:
        link = re.search(r"<link>(.*?)</link>", item, re.S)
        title = re.search(r"<title>(.*?)</title>", item, re.S)
        content = re.search(r"<content:encoded>(.*?)</content:encoded>", item, re.S) or re.search(r"<description>(.*?)</description>", item, re.S)
        if not link:
            continue
        raw = (content.group(1) if content else "").replace("<![CDATA[", "").replace("]]>", "")
        out.append({"url": strip_tags(link.group(1)), "title": strip_tags(title.group(1) if title else ""),
                    "source": source, "rss_text": strip_tags(html.unescape(raw))})
    log(source + ":", len(out))
    return out


def src_contemporaryperformance() -> list[dict]:
    return _rss("https://contemporaryperformance.com/category/opportunities/festival-calls/feed/", "Contemporary Performance")


def src_frame() -> list[dict]:
    return _rss("https://frame-finland.fi/en/category/open-call/feed/", "Frame Finland")


SOURCES = [src_onthemove, src_ekl, src_frame, src_contemporaryperformance, src_artrabbit]


# ---------------------------------------------------------------- hindamine
def analyse(c: dict) -> dict:
    text = c.get("text", "")
    title = c.get("title", "")
    full = title + "\n" + text
    reasons, hard = [], []

    # tähtaeg
    dl = dt.date.fromisoformat(c["deadline"]) if c.get("deadline") else find_deadline(full)
    if dl is None:
        hard.append("tähtaeg leidmata")
    else:
        days = (dl - TODAY).days
        if days < MIN_DAYS:
            hard.append("tähtaeg möödas või liiga lähedal")

    # tasu
    fee, fee_ctx = fee_status(full)
    if fee == "jah":
        hard.append("osalustasu")
    elif fee == "ei":
        reasons.append(("osalustasu puudub", +2))
    if PAY_TO_SHOW.search(full):
        m = PAY_TO_SHOW.search(full)
        ctx = full[max(0, m.start() - 80):m.end() + 80]
        if not re.search(r"no (?:cost|fee)|free of charge|covered by (?:us|the organi|the host)|we cover", ctx, re.I):
            hard.append("kunstnik maksab kulud")

    paid = [k for k, p in PAID_RE.items() if p.search(full)]
    for k in paid:
        reasons.append((k, +3 if k in ("kunstnikutasu", "tootmiseelarve") else +2))
    if re.search(r"subject to (?:funding|confirmation)|if funding is (?:secured|granted)|depending on (?:funding|grants)|applying for (?:funding|grants)", full, re.I):
        reasons.append(("tasu sõltub rahastusest", -2))

    # liik ja kestus
    typ = guess_type(title, text)
    if c.get("section") == "Residencies":
        typ = "Residentuur"
    if c.get("section") in ("Project funding", "Fellowships"):
        typ = "Toetus"
    staylike = typ == "Residentuur" or re.search(r"residen|studio|fellowship", title + " " + text[:1500], re.I)
    days_res = residency_days(full) if staylike else None
    if staylike and not days_res and re.search(r"(?:stipend|fee|grant|allowance)[^.]{0,40}(?:per|a|/) ?month|monthly (?:stipend|allowance|fee)", full, re.I):
        days_res = 30
    if days_res:
        if days_res > MAX_RES_DAYS:
            hard.append(f"residentuur liiga pikk (~{days_res} p)")
        else:
            reasons.append((f"lühike residentuur (~{days_res} p)", +2))
    elif typ == "Residentuur":
        reasons.append(("kestus teadmata", -1))

    # sobivus
    for pat, label in RESTRICT:
        m = pat.search(full)
        if m:
            if label == "vanusepiirang":
                try:
                    if int(m.group(1)) >= 50:
                        continue
                except (ValueError, IndexError):
                    pass
            hard.append(label)
    if OPEN_WIDE.search(full):
        reasons.append(("avatud rahvusvaheliselt / Eestile", +1))

    partner = bool(PARTNER.search(full))

    # meedium
    plus = len(set(m.group(0).lower() for m in MEDIA_PLUS.finditer(full)))
    minus = len(set(m.group(0).lower() for m in MEDIA_MINUS.finditer(title + " " + text[:1500])))
    if plus:
        reasons.append(("meedium sobib", min(plus, 3)))
    if minus and minus >= plus:
        reasons.append(("teine valdkond", -3 * min(minus, 2)))
    if re.search(r"\bemerging\b|early[- ]career|young artists?|nuored|noor(?:te)? kunstnik", title, re.I):
        reasons.append(("alustavatele kunstnikele", -2))
    if re.search(r"kultuurkapital|kulka|venice biennale.*estonian pavilion|eesti paviljon", full, re.I):
        hard.append("Kulka / Veneetsia (Sandra teab ise)")
    if not CALLISH.search(full):
        reasons.append(("ei paista kutse", -3))

    score = sum(v for _, v in reasons)
    amount = "; ".join(money_snippets(full))
    if len(amount) > 170:
        amount = amount[:170].rsplit(" ", 1)[0] + "…"
    if not amount and paid:
        amount = "Kaetud: " + ", ".join(paid)
    return {
        "deadline": dl.isoformat() if dl else None,
        "type": typ,
        "region": region_for(title, text),
        "fee": fee,
        "paid": paid,
        "residencyDays": days_res,
        "needsPartner": partner,
        "reasons": [r for r, _ in reasons],
        "hard": hard,
        "score": score,
        "amount": amount,
        "summary": summarise(c.get("desc", ""), text),
    }


# ---------------------------------------------------------------- õppimine Sandra märgetest
TOK = re.compile(r"[a-zäöüõšž]{3,}", re.I)
STOP = set("the and for with that this from are will have has can their your you our not all any but its was were been into also more other which who they them about artists artist art call open".split())


def tokens(s: str) -> list[str]:
    return [t for t in (w.lower() for w in TOK.findall(s)) if t not in STOP]


class Bayes:
    def __init__(self):
        self.n = {0: 0, 1: 0}
        self.w = {0: {}, 1: {}}
        self.tot = {0: 0, 1: 0}

    def add(self, text, y):
        self.n[y] += 1
        for t in set(tokens(text)):
            self.w[y][t] = self.w[y].get(t, 0) + 1
            self.tot[y] += 1

    def ready(self):
        return self.n[0] >= 5 and self.n[1] >= 5

    def prob(self, text):
        vocab = len(set(self.w[0]) | set(self.w[1])) + 1
        lp = {y: math.log((self.n[y] + 1) / (self.n[0] + self.n[1] + 2)) for y in (0, 1)}
        for t in set(tokens(text)):
            for y in (0, 1):
                lp[y] += math.log((self.w[y].get(t, 0) + 1) / (self.tot[y] + vocab))
        d = max(-30, min(30, lp[0] - lp[1]))
        return 1 / (1 + math.exp(d))


def load_labels() -> dict[str, str]:
    """Staatused lehelt (Cloudflare KV kaudu, lugemine on avalik)."""
    url = os.environ.get("KONKURSID_API", "https://sandrajogeva.artcontainer.ee/api/konkursid")
    labels: dict[str, str] = {}
    if SEED.exists():
        for it in json.loads(SEED.read_text()).get("items", []):
            if it.get("status"):
                labels[it["id"]] = it["status"]
    if url:
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=20) as r:
                data = json.loads(r.read().decode())
            for k, v in (data.get("statuses") or {}).items():
                if isinstance(v, dict) and v.get("status"):
                    labels[k] = v["status"]
            log("Staatused lehelt:", len(data.get("statuses") or {}))
        except Exception as e:
            log("Staatusi ei saanud lugeda:", e)
    return labels


# ---------------------------------------------------------------- põhitsükkel
def make_id(url: str) -> str:
    p = urllib.parse.urlparse(url)
    slug = re.sub(r"[^a-z0-9]+", "-", (p.path.rstrip("/").rsplit("/", 1)[-1] or p.netloc).lower()).strip("-")[:60]
    return (slug or "kutse") + "-" + hashlib.sha1(url.encode()).hexdigest()[:6]


CACHE = Path(__file__).with_name("cache.json")
PRIORITY = {"käsitsi": 0, "On the Move": 1, "EKL": 2, "Frame Finland": 3, "Contemporary Performance": 4, "ArtRabbit": 5}


def org_name(c: dict) -> str:
    t = c.get("title", "")
    if c["source"] == "On the Move" and ":" in t:
        return t.split(":", 1)[0].strip()[:80]
    if c["source"] == "EKL":
        return "EKL"
    u = c.get("applyUrl") or c["url"]
    return urllib.parse.urlparse(u).netloc.replace("www.", "")


def _tset(t: str) -> set[str]:
    return {w for w in tokens(t) if not w.isdigit() and w not in {"2026", "2027", "2028", "residency", "competition", "programme", "program", "edition", "international"}}


def dedupe(items: list[dict]) -> list[dict]:
    """Sama kutse mitmest allikast: jäta üks (käsitsi > On the Move > …)."""
    items = sorted(items, key=lambda i: PRIORITY.get(i.get("source", ""), 9))
    kept: list[dict] = []
    for it in items:
        a = _tset(it.get("title", ""))
        dup = False
        for k in kept:
            b = _tset(k.get("title", ""))
            if not a or not b:
                continue
            j = len(a & b) / len(a | b)
            same_dl = it.get("deadline") and it.get("deadline") == k.get("deadline")
            hosts = lambda x: {urllib.parse.urlparse(u).netloc.replace("www.", "") for u in (x.get("url"), x.get("infoUrl")) if u}
            same_host = bool(hosts(it) & hosts(k) - {"on-the-move.org", "artrabbit.com", "eaa.ee", "contemporaryperformance.com", "frame-finland.fi"})
            if j >= 0.6 or (same_dl and (j >= 0.25 or same_host)):
                dup = True
                break
        if not dup:
            kept.append(it)
    return kept


def main() -> int:
    prev = {}
    if OUT.exists():
        try:
            prev = {i["id"]: i for i in json.loads(OUT.read_text()).get("items", [])}
        except Exception:
            prev = {}
    cache: dict = {}
    if CACHE.exists():
        try:
            cache = json.loads(CACHE.read_text())
        except Exception:
            cache = {}

    cands: list[dict] = []
    for src in SOURCES:
        try:
            cands += src()
        except Exception as e:
            log(src.__name__, "viga:", e)
    seen, uniq = set(), []
    for c in cands:
        u = c["url"].split("#")[0].rstrip("/")
        if u in seen:
            continue
        seen.add(u)
        c["url"] = u
        uniq.append(c)
    log("Kandidaate kokku:", len(uniq))

    labels = load_labels()
    model = Bayes()

    results, fetched = [], 0
    for c in uniq:
        cid = make_id(c["url"])
        hit = cache.get(cid)
        # varem loetud leht: ära loe uuesti (kutse tekst harva muutub)
        if hit and hit.get("text"):
            c["text"], c["desc"] = hit["text"], hit.get("desc", "")
            c["title"] = c.get("title") or hit.get("title", "")
            c["applyUrl"] = hit.get("applyUrl")
        elif c.get("rss_text") and len(c["rss_text"]) > 1500 and DEADLINE_KW.search(c["rss_text"]):
            c["text"], c["desc"] = c["rss_text"], ""
        else:
            if fetched >= MAX_DETAIL_FETCH:
                continue
            try:
                src = fetch(c["url"])
                page = html_to_text(src)
                fetched += 1
                time.sleep(0.6)
            except Exception as e:
                log("  ei saanud lugeda:", c["url"], e)
                continue
            text = page["text"][:12000]
            # loe ka korraldaja enda kutseleht (seal on tasud ja tingimused)
            ext = apply_link(src, c["url"])
            if ext:
                try:
                    extra = html_to_text(fetch(ext))
                    fetched += 1
                    text += "\n\n[KORRALDAJA LEHT]\n" + extra["text"][:12000]
                    c["applyUrl"] = ext
                    time.sleep(0.6)
                except Exception as e:
                    log("  korraldaja lehte ei saanud:", ext, e)
            if c.get("rss_text"):
                text = c["rss_text"][:6000] + "\n\n" + text
            c["text"], c["desc"] = text, page["desc"]
            c["title"] = c.get("title") or page["title"]
        cache[cid] = {"text": c["text"][:24000], "desc": c.get("desc", ""), "title": c.get("title", ""), "seen": TODAY.isoformat(), "applyUrl": c.get("applyUrl")}
        a = analyse(c)
        results.append((cid, c, a))

    # õppimine: märgitud kirjed
    for cid, c, a in results:
        st = labels.get(cid)
        if st in ("taotlen", "kaalun", "saadetud"):
            model.add(c["title"] + " " + c["text"][:3000], 1)
        elif st == "ei-sobi":
            model.add(c["title"] + " " + c["text"][:3000], 0)
    if model.ready():
        log("Õppija kasutusel:", model.n)

    items = []
    for cid, c, a in results:
        score = a["score"]
        if model.ready():
            p = model.prob(c["title"] + " " + c["text"][:3000])
            a["learned"] = round(p, 2)
            score += round((p - 0.5) * 6)  # -3 … +3
        keep = not a["hard"] and score >= KEEP_SCORE
        if cid in labels:  # märgitud kirjed jäävad alati alles
            keep = keep or labels[cid] in ("taotlen", "kaalun", "saadetud")
        if not keep:
            continue
        old = prev.get(cid, {})
        items.append({
            "id": cid,
            "title": c.get("title", "")[:200],
            "org": org_name(c),
            "source": c["source"],
            "type": a["type"],
            "region": a["region"],
            "deadline": a["deadline"],
            "summary": a["summary"],
            "amount": a["amount"],
            "url": c.get("applyUrl") or c["url"],
            "infoUrl": c["url"] if c.get("applyUrl") else None,
            "infoLabel": ("Kuulutus: " + c["source"]) if c.get("applyUrl") else None,
            "needsPartner": a["needsPartner"],
            "check": score < SURE_SCORE or a["deadline"] is None or a["fee"] == "?",
            "score": score,
            "reasons": a["reasons"],
            "added": old.get("added") or TODAY.isoformat(),
        })

    # käsitsi lisatud kirjed (seed.json) – säilivad, kuni tähtaeg möödub
    if SEED.exists():
        for it in json.loads(SEED.read_text()).get("items", []):
            if it.get("deadline") and dt.date.fromisoformat(it["deadline"]) < TODAY:
                continue
            if any(i["id"] == it["id"] for i in items) or it.get("status") == "ei-sobi":
                continue
            it = dict(it)
            it.pop("status", None)
            it.setdefault("source", "käsitsi")
            it.setdefault("check", False)
            items.append(it)

    items = dedupe(items)
    items.sort(key=lambda i: (i["deadline"] or "9999"))
    public = [{k: v for k, v in i.items() if v is not None} for i in items]
    # vahemälust välja kirjed, mida pole 120 päeva nähtud
    cutoff = (TODAY - dt.timedelta(days=120)).isoformat()
    cache = {k: v for k, v in cache.items() if v.get("seen", "") >= cutoff}
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps({
        "updated": TODAY.isoformat(),
        "candidates": len(uniq),
        "count": len(public),
        "items": public,
    }, ensure_ascii=False, indent=1))
    CACHE.write_text(json.dumps(cache, ensure_ascii=False))
    log(f"Valmis: {len(public)} kirjet tabelisse ({len(uniq)} kandidaadist, loetud {fetched} lehte).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
