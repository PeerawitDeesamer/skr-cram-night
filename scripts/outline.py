#!/usr/bin/env python3
"""
outline — find out what order the sheet is REALLY in, before teaching from it.

Why this exists
---------------
A teacher's deck is built to be talked over, not read alone. The same topic
gets split across pages that are nowhere near each other, a term is used ten
pages before it is defined, and two unrelated classifications sit back to back
because that is the order they were lectured in. Teaching in page order copies
all of that into the lesson, and the reader hits a word they were never given.

So: map the deck first, see where a topic is scattered, then decide the order
deliberately. This script does the mechanical half — which page mentions what,
and which topics come in more than one piece. **Deciding the teaching order is
not mechanical and this script will not do it**: that is a judgement about what
has to be understood before what, and it belongs to whoever is teaching.

Thai in these PDFs extracts with its vowels mangled, so only the English
technical vocabulary is used here. For this subject that is enough — the terms
that carry the structure (essential amino acid, gastrovascular cavity, gizzard)
are English in every Thai biology deck.

Usage
-----
    python3 outline.py map     SHEET.pdf [--pages 1-20] [--md]
    python3 outline.py scatter SHEET.pdf [--min-gap 2]

`map` prints page → the terms that page introduces. `--md` prints it as the
markdown table that belongs in the workspace's NOTES.md, so the next night does
not have to work it out again.

`scatter` prints only the terms that appear in more than one place, with the gap
between them — the topics the deck teaches in pieces.
"""

import argparse
import pathlib
import re
import sys
from collections import defaultdict

try:
    import pymupdf
except ImportError:  # pragma: no cover - environment guard
    sys.exit("error: pymupdf missing — run install.sh")

TEXT_FLOOR = 120  # below this a page is a picture of text, not text

# Words that are English but carry no structure. Everything else on a Thai
# biology slide that is written in English is there because it is a term.
STOP = {
    "and", "the", "for", "with", "from", "that", "this", "these", "those",
    "are", "was", "were", "has", "have", "had", "not", "but", "all", "any",
    "can", "will", "into", "out", "off", "than", "then", "when", "where",
    "which", "what", "who", "how", "why", "its", "their", "they", "them",
    "some", "such", "also", "more", "most", "less", "each", "other", "others",
    "one", "two", "three", "four", "five", "six", "seven", "eight", "nine",
    "ten", "first", "second", "third", "example", "figure", "page", "chapter",
    "type", "types", "kind", "kinds", "part", "parts", "system",
    # Slide furniture, not content: embedded video links and their captions.
    "http", "https", "www", "youtube", "youtu", "com", "watch", "video",
    "click", "here", "link", "source", "credit", "copyright",
}
TOKEN = re.compile(r"[A-Za-z][A-Za-z-]{2,}")


def parse_pages(spec: str, n: int) -> list[int]:
    if not spec:
        return list(range(n))
    out: list[int] = []
    for part in spec.split(","):
        part = part.strip()
        if "-" in part:
            a, b = part.split("-", 1)
            out.extend(range(int(a) - 1, int(b)))
        else:
            out.append(int(part) - 1)
    return [p for p in out if 0 <= p < n]


def terms_on(text: str) -> list[str]:
    """English terms on one page, longest phrases first.

    Consecutive English tokens are kept together: "essential amino acid" is one
    idea, and splitting it into three words loses exactly the thing being
    looked for. Thai between them ends a phrase, which is what separates
    "gastrovascular cavity" from the sentence around it.
    """
    # A line holding a URL is a link to a video, not a term the sheet teaches.
    text = "\n".join(l for l in text.splitlines() if "http" not in l.lower())
    phrases: list[str] = []
    for run in re.findall(r"[A-Za-z][A-Za-z \-]*[A-Za-z]", text):
        words = [w for w in TOKEN.findall(run)]
        keep = [w for w in words if w.lower() not in STOP and len(w) > 3]
        if not keep:
            continue
        # A run of 2-4 kept words reads as one term; longer is a sentence.
        phrase = " ".join(keep[:4]).lower()
        if 3 < len(phrase) < 60:
            phrases.append(phrase)
    seen, out = set(), []
    for p in phrases:
        if p not in seen:
            seen.add(p)
            out.append(p)
    return out


def load(path: pathlib.Path, pages: str):
    doc = pymupdf.open(path)
    idx = parse_pages(pages, doc.page_count)
    per_page, scanned = {}, []
    for i in idx:
        raw = doc[i].get_text().strip()
        if len(raw) < TEXT_FLOOR:
            scanned.append(i + 1)
        per_page[i + 1] = (raw, terms_on(raw))
    return per_page, scanned, doc.page_count


def heading(raw: str) -> str:
    """The line most likely to be this page's title: the first line carrying a
    section number, else the first line with English in it."""
    def trim(l: str) -> str:
        # The Thai tail extracts with its vowels stripped (see SHEETS.md), so it
        # is noise in a map. Cut where the Thai starts; if the line STARTS in
        # Thai, drop the Thai instead and keep whatever English it carries.
        head = re.split(r"[^\x20-\x7e]", l, maxsplit=1)[0].strip()
        if len(re.findall(r"[A-Za-z]", head)) < 4:
            head = re.sub(r"\s+", " ", re.sub(r"[^\x20-\x7e]", "", l)).strip()
        return head[:70]

    lines = [l.strip() for l in raw.splitlines()
             if l.strip() and "http" not in l.lower()]  # a pasted video link is not a title
    for l in lines[:6]:
        if re.match(r"^\d+(\.\d+)*[\.\)]?\s", l) and TOKEN.search(l):
            return trim(l)
    for l in lines[:4]:
        if TOKEN.search(l):
            return trim(l)
    return ""


# --------------------------------------------------------------------------
def cmd_map(path: pathlib.Path, pages: str, md: bool) -> int:
    per_page, scanned, total = load(path, pages)
    if not per_page:
        sys.exit(f"error: --pages matched no page (this file has {total})")

    # Terms seen earlier stop being news; a page's own contribution is what it
    # adds, which is what an ordering decision actually turns on.
    seen: set[str] = set()
    rows = []
    for pno in sorted(per_page):
        raw, terms = per_page[pno]
        fresh = [t for t in terms if t not in seen][:6]
        seen.update(terms)
        rows.append((pno, heading(raw), fresh))

    if md:
        print("| หน้า | หัวข้อ | ศัพท์ที่โผล่ครั้งแรก |")
        print("|---|---|---|")
        for pno, head, fresh in rows:
            mark = " *(สแกน)*" if pno in scanned else ""
            print(f"| {pno} | {head or '—'}{mark} | {', '.join(fresh) or '—'} |")
    else:
        for pno, head, fresh in rows:
            mark = "  [SCAN — render it and read the picture]" if pno in scanned else ""
            print(f"\n=== page {pno} ==={mark}")
            if head:
                print(f"  heading: {head}")
            if fresh:
                print(f"  new    : {', '.join(fresh)}")

    if scanned:
        print(f"\n{len(scanned)} page(s) have no text layer: {scanned}", file=sys.stderr)
        print("their terms are invisible here — render and read them before "
              "trusting this map", file=sys.stderr)
    return 0


def cmd_scatter(path: pathlib.Path, pages: str, min_gap: int) -> int:
    per_page, scanned, _ = load(path, pages)
    if not per_page:
        sys.exit("error: --pages matched no page in this file")
    # Saying "order looks fine" about pages it never read is the worst thing
    # this script could do: it is an all-clear built out of nothing, and it
    # would be believed at 01:00.
    if len(scanned) >= len(per_page) / 2:
        print(f"{len(scanned)} of {len(per_page)} page(s) have no text layer — "
              "this script can tell you NOTHING about this deck's order.")
        print(f"  scanned: {scanned}")
        print("\nRender them and read the order yourself:")
        print(f'  python3 sheet.py render "{path.name}" --pages 1-6 --out pages')
        return 0

    where: dict[str, list[int]] = defaultdict(list)
    for pno in sorted(per_page):
        for t in per_page[pno][1]:
            where[t].append(pno)

    split = []
    for term, pgs in where.items():
        if len(pgs) < 2:
            continue
        gaps = [(b - a) for a, b in zip(pgs, pgs[1:]) if b - a > min_gap]
        if gaps:
            split.append((max(gaps), term, pgs))

    if not split:
        print(f"no term repeats more than {min_gap} pages apart in the "
              f"{len(per_page) - len(scanned)} page(s) with a text layer — "
              "the deck's own order is probably usable")
        if scanned:
            print(f"  (but {len(scanned)} scanned page(s) were invisible here: {scanned})")
        return 0

    print("taught in more than one place (biggest gap first):\n")
    for gap, term, pgs in sorted(split, reverse=True)[:25]:
        print(f"  {gap:>3} pages apart · {term}")
        print(f"      pages {', '.join(map(str, pgs))}")
    print("\nEach of these is a decision: pull the pieces into one lesson, or keep")
    print("them apart on purpose. Say which you chose and why — do not just")
    print("follow the deck.")
    if scanned:
        print(f"\n{len(scanned)} scanned page(s) contributed nothing: {scanned}",
              file=sys.stderr)
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("mode", choices=["map", "scatter"])
    ap.add_argument("pdf", type=pathlib.Path)
    ap.add_argument("--pages", default="", help="e.g. 1-20 or 3,7,10-12 (1-based)")
    ap.add_argument("--md", action="store_true", help="map: print a NOTES.md table")
    ap.add_argument("--min-gap", type=int, default=2,
                    help="scatter: how many pages apart counts as 'elsewhere'")
    a = ap.parse_args()

    if not a.pdf.exists():
        sys.exit(f"error: {a.pdf} not found")
    if a.mode == "map":
        return cmd_map(a.pdf, a.pages, a.md)
    return cmd_scatter(a.pdf, a.pages, a.min_gap)


if __name__ == "__main__":
    raise SystemExit(main())
