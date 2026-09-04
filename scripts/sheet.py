#!/usr/bin/env python3
"""
Read a teacher's sheet (PDF) the cheap way first.

Some sheets carry a real text layer (the Chemistry ones do) and can be read in
milliseconds. Others are photocopies scanned to image (the Biology one is) and
have to be rendered to PNG and looked at. Guessing wrong wastes the one thing
cram night has none of: time. So always run `probe` first.

Usage
-----
    python3 sheet.py probe  FILE.pdf
    python3 sheet.py text   FILE.pdf [--pages 20-30]
    python3 sheet.py render FILE.pdf --pages 1-6 --out DIR [--dpi 150]

`text` prints each page with a === page N === banner so a quotation can always
be traced back to the page it came from — the citation rule depends on it.
"""

import argparse
import pathlib
import sys

try:
    import pymupdf
except ImportError:  # pragma: no cover - environment guard
    sys.exit("error: pymupdf missing — run install.sh")

# Below this many characters a page is a picture of text, not text.
TEXT_FLOOR = 120


def parse_pages(spec: str, n: int) -> list[int]:
    """'3', '20-30', '1,4,9-11' → zero-based page indices, clamped to the file."""
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


def probe(path: pathlib.Path) -> int:
    doc = pymupdf.open(path)
    scanned = []
    chars = 0
    for i, page in enumerate(doc):
        c = len(page.get_text().strip())
        chars += c
        if c < TEXT_FLOOR:
            scanned.append(i + 1)

    print(f"file   : {path.name}")
    print(f"pages  : {doc.page_count}")
    print(f"text   : {chars} chars")
    if not scanned:
        print("kind   : TEXT — read it with `sheet.py text` (fast)")
    elif len(scanned) == doc.page_count:
        print("kind   : SCAN — no text layer at all; `sheet.py render` then read the images")
    else:
        print(f"kind   : MIXED — pages with no text: {scanned}")
        print("         use `text` for the rest, `render` for those")
    return 0


def dump_text(path: pathlib.Path, pages: str) -> int:
    doc = pymupdf.open(path)
    for i in parse_pages(pages, doc.page_count):
        body = doc[i].get_text().strip()
        print(f"\n=== page {i + 1} ===")
        print(body if body else "[no text layer on this page — render it instead]")
    return 0


def render(path: pathlib.Path, pages: str, out: pathlib.Path, dpi: int) -> int:
    doc = pymupdf.open(path)
    out.mkdir(parents=True, exist_ok=True)
    written = []
    for i in parse_pages(pages, doc.page_count):
        pix = doc[i].get_pixmap(dpi=dpi)
        f = out / f"p{i + 1:03d}.png"
        pix.save(f)
        written.append(f)
    for f in written:
        print(f)
    print(f"{len(written)} page(s) rendered at {dpi} dpi", file=sys.stderr)
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("mode", choices=["probe", "text", "render"])
    ap.add_argument("pdf", type=pathlib.Path)
    ap.add_argument("--pages", default="", help="e.g. 20-30 or 1,4,9-11 (1-based)")
    ap.add_argument("--out", type=pathlib.Path, default=pathlib.Path("pages"))
    ap.add_argument("--dpi", type=int, default=150)
    a = ap.parse_args()

    if not a.pdf.exists():
        sys.exit(f"error: {a.pdf} not found")
    if a.mode == "probe":
        return probe(a.pdf)
    if a.mode == "text":
        return dump_text(a.pdf, a.pages)
    return render(a.pdf, a.pages, a.out, a.dpi)


if __name__ == "__main__":
    raise SystemExit(main())
