#!/usr/bin/env python3
"""
figure — get pictures out of the teacher's own slides and into the lesson.

Why this exists
---------------
A science lesson that is a wall of Thai prose is a lesson nobody reads at 01:00.
The diagram the teacher put on the slide is the one that will be on the test,
drawn the way the marker expects to see it drawn. Redrawing it from memory loses
that; screenshotting it by hand at cram-night speed is exactly the chore that
gets skipped. So this script makes lifting it a one-liner.

Ways to get a figure, cheapest first:

    list    what raster images are already embedded in the slide  → `pull`
    pull    save one of them at its native resolution (no reshoot loss)
    grid    render a page with a 0-100 ruler drawn on top, so a crop box can be
            read straight off the picture
    crop    cut that box out at print resolution
    fetch   download one off the web into the workspace, with its licence
    check   what every figure in a folder actually weighs and measures

`pull` beats `crop` whenever it works: the embedded original has no slide
background, no title text, no JPEG-of-a-JPEG. Try it first, fall back to crop
for anything the teacher assembled out of several pieces (labels + arrows).

Every write prints the path it actually used and the <img> line to paste. A PNG
over 1.2 MB is re-saved as JPEG, so that path is not always the one you asked
for — copy the one printed, not the one you typed.

Usage
-----
    python3 figure.py list  SLIDES.pdf --pages 4-9
    python3 figure.py pull  SLIDES.pdf --page 6 --index 0 --out lessons/fig/nephron.png
    python3 figure.py grid  SLIDES.pdf --pages 6 --out /tmp/grid
    python3 figure.py crop  SLIDES.pdf --page 6 --box 8,22,92,71 \
                            --out lessons/fig/nephron.png --trim
    python3 figure.py fetch URL --out lessons/fig/krebs.png --cite "Wikimedia Commons, CC BY-SA 4.0"
    python3 figure.py check lessons/fig

Boxes are percentages of the page: x0,y0,x1,y1 with 0,0 at the top-left corner
and 100,100 at the bottom-right — the same numbers printed on the `grid` ruler.
"""

import argparse
import pathlib
import re
import subprocess
import sys

try:
    import pymupdf
except ImportError:  # pragma: no cover - environment guard
    sys.exit("error: pymupdf missing — run install.sh")

# The lesson column is 38rem at 17px ≈ 646 CSS px. Twice that is sharp on a
# retina screen and on paper; past it the file just gets slower to open.
MAX_WIDTH = 1400
# Under this a diagram's own labels stop being readable once it is scaled to the
# column, and a blurry diagram teaches the wrong shape.
MIN_WIDTH = 520
# Anything fatter than this and a lesson folder stops fitting in a git checkout
# or an email to yourself.
FAT_BYTES = 1_200_000
UA = "Mozilla/5.0 (Macintosh) skr-figure/1.0 (cram-night lesson builder)"


def parse_pages(spec: str, n: int) -> list[int]:
    """'3', '4-9', '1,4,9-11' → zero-based page indices, clamped to the file."""
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


def parse_box(spec: str) -> tuple[float, float, float, float]:
    try:
        x0, y0, x1, y1 = (float(v) for v in spec.replace(" ", "").split(","))
    except ValueError:
        sys.exit("error: --box wants four percentages, e.g. --box 8,22,92,71")
    if not (x0 < x1 and y0 < y1):
        sys.exit(f"error: --box {spec} is inside-out (need x0<x1 and y0<y1)")
    return x0, y0, x1, y1


def save(pix, out: pathlib.Path) -> pathlib.Path:
    """Write the figure, and quietly switch a fat PNG to JPEG.

    A photographic diagram lifted off a slide is routinely 1.8 MB as PNG and
    190 KB as JPEG with no visible difference at the size the column shows it.
    Twelve of those is the gap between a lesson folder that syncs and one that
    does not, so the swap happens without being asked. Returns the path actually
    written — it is not always the one that was asked for.
    """
    out.parent.mkdir(parents=True, exist_ok=True)
    if pix.colorspace and pix.colorspace.n == 4:  # CMYK has no PNG/JPEG encoding
        pix = pymupdf.Pixmap(pymupdf.csRGB, pix)
    pix.save(out)
    if out.suffix.lower() == ".png" and not pix.alpha and out.stat().st_size > FAT_BYTES:
        jpg = out.with_suffix(".jpg")
        pix.save(jpg, jpg_quality=82)
        if jpg.stat().st_size < out.stat().st_size:
            out.unlink()
            return jpg
        jpg.unlink()
    return out


def report(out: pathlib.Path, pix) -> None:
    kb = out.stat().st_size / 1024
    note = ""
    if pix.width < MIN_WIDTH:
        note = f"  ← only {pix.width}px wide, its labels will be mush; raise --dpi"
    print(f"{out}  {pix.width}×{pix.height}px  {kb:.0f} KB{note}")
    print(f'  <img src="fig/{out.name}" alt="…">', file=sys.stderr)


# --------------------------------------------------------------------------
def cmd_list(path: pathlib.Path, pages: str) -> int:
    """Embedded rasters, with where they sit on the page as a ready-made box."""
    doc = pymupdf.open(path)
    total = 0
    for i in parse_pages(pages, doc.page_count):
        page = doc[i]
        pw, ph = page.rect.width, page.rect.height
        imgs = page.get_images(full=True)
        if not imgs:
            continue
        print(f"\n=== page {i + 1} ===")
        for k, info in enumerate(imgs):
            xref = info[0]
            w, h = info[2], info[3]
            try:
                rects = page.get_image_rects(xref)
            except Exception:
                rects = []
            where = ""
            if rects:
                r = rects[0]
                # A slide often places an image so it bleeds off the page edge,
                # which puts the raw box outside 0-100. Printed unclamped it is
                # an invalid --box that looks like a valid one.
                clamp = lambda v: max(0.0, min(100.0, v))
                where = ("  box %.0f,%.0f,%.0f,%.0f"
                         % (clamp(100 * r.x0 / pw), clamp(100 * r.y0 / ph),
                            clamp(100 * r.x1 / pw), clamp(100 * r.y1 / ph)))
            flag = "" if w >= MIN_WIDTH else "  (small — probably an icon or a bullet)"
            print(f"  --index {k}  {w}×{h}px{where}{flag}")
            total += 1
    if not total:
        print("no embedded rasters — the diagrams are vector or the page is a scan; "
              "use `grid` + `crop`")
    return 0


def cmd_pull(path: pathlib.Path, page_no: int, index: int, out: pathlib.Path) -> int:
    doc = pymupdf.open(path)
    if not 1 <= page_no <= doc.page_count:
        sys.exit(f"error: page {page_no} is outside {path.name} (1–{doc.page_count})")
    imgs = doc[page_no - 1].get_images(full=True)
    if not imgs:
        sys.exit(f"error: page {page_no} embeds no raster image — use `crop` instead")
    if not 0 <= index < len(imgs):
        sys.exit(f"error: --index {index} but page {page_no} has {len(imgs)} "
                 f"(0–{len(imgs) - 1}); run `list` first")
    pix = pymupdf.Pixmap(doc, imgs[index][0])
    if pix.colorspace and pix.colorspace.n == 4:  # CMYK has no PNG encoding
        pix = pymupdf.Pixmap(pymupdf.csRGB, pix)
    while pix.width > 2 * MAX_WIDTH:  # halving is lossless-ish and cheap
        pix.shrink(1)
    out = save(pix, out)
    report(out, pix)
    return 0


def cmd_grid(path: pathlib.Path, pages: str, out: pathlib.Path, dpi: int) -> int:
    """Render pages with a percentage ruler drawn on top.

    Eyeballing a crop box off a plain render is guesswork that costs a second
    render to correct. With the ruler on the page the box is read, not guessed.
    Nothing is saved back to the PDF — the drawing lives only in this pixmap.
    """
    doc = pymupdf.open(path)
    out.mkdir(parents=True, exist_ok=True)
    for i in parse_pages(pages, doc.page_count):
        page = doc[i]
        w, h = page.rect.width, page.rect.height
        for p in range(0, 101, 5):
            major = p % 10 == 0
            col = (0.85, 0.1, 0.1) if major else (0.45, 0.65, 0.95)
            width = 0.7 if major else 0.35
            x, y = w * p / 100, h * p / 100
            page.draw_line((x, 0), (x, h), color=col, width=width, overlay=True)
            page.draw_line((0, y), (w, y), color=col, width=width, overlay=True)
            if major:
                for tx, ty in ((x + 1.5, 9), (x + 1.5, h - 3)):
                    page.insert_text((tx, ty), str(p), fontsize=7,
                                     color=(0.85, 0.1, 0.1), overlay=True)
                for tx, ty in ((2, y - 1.5), (w - 14, y - 1.5)):
                    page.insert_text((tx, ty), str(p), fontsize=7,
                                     color=(0.85, 0.1, 0.1), overlay=True)
        f = out / f"grid-p{i + 1:03d}.png"
        page.get_pixmap(dpi=dpi).save(f)
        print(f)
    print("read the crop box off the red numbers: --box x0,y0,x1,y1", file=sys.stderr)
    return 0


def _trim(pix, tol: int = 12):
    """Shave uniform light margins so a hand-read box still looks deliberate.

    A box read off the ruler always carries a centimetre of slide background on
    some side. Left in, every figure on the page is misaligned by a different
    amount, which reads as sloppiness rather than as the slop it is.
    """
    if pix.n < 3:
        return pix
    n, w, h, s, stride = pix.n, pix.width, pix.height, pix.samples, pix.stride

    def light(x, y):
        o = y * stride + x * n  # rows are padded to `stride`, not to w*n
        return s[o] > 255 - tol and s[o + 1] > 255 - tol and s[o + 2] > 255 - tol

    step = max(1, min(w, h) // 200)  # sampling; a stray dark pixel is not an edge

    def row_blank(y):
        return all(light(x, y) for x in range(0, w, step))

    def col_blank(x):
        return all(light(x, y) for y in range(0, h, step))

    top, bot, left, right = 0, h - 1, 0, w - 1
    while top < bot and row_blank(top):
        top += 1
    while bot > top and row_blank(bot):
        bot -= 1
    while left < right and col_blank(left):
        left += 1
    while right > left and col_blank(right):
        right -= 1
    if (top, left) == (0, 0) and (bot, right) == (h - 1, w - 1):
        return pix
    pad = 6  # a hairline of white keeps the figure off its own border
    # A clipped render keeps its device origin, so these pixel offsets have to
    # be shifted by it — copy() works in the source's coordinates, not in the
    # 0-based ones the scan above counts in.
    ox, oy = pix.x, pix.y
    clip = pymupdf.IRect(ox + max(0, left - pad), oy + max(0, top - pad),
                         ox + min(w, right + 1 + pad), oy + min(h, bot + 1 + pad))
    if clip.width < 40 or clip.height < 40:  # trimmed to nothing — box was blank
        return pix
    cut = pymupdf.Pixmap(pix.colorspace, clip, pix.alpha)
    cut.copy(pix, clip)
    return cut


def cmd_crop(path: pathlib.Path, page_no: int, box: str,
             out: pathlib.Path, dpi: int, trim: bool) -> int:
    doc = pymupdf.open(path)
    if not 1 <= page_no <= doc.page_count:
        sys.exit(f"error: page {page_no} is outside {path.name} (1–{doc.page_count})")
    page = doc[page_no - 1]
    x0, y0, x1, y1 = parse_box(box)
    w, h = page.rect.width, page.rect.height
    clip = pymupdf.Rect(w * x0 / 100, h * y0 / 100, w * x1 / 100, h * y1 / 100)

    # Cap the dpi by the width we actually want rather than shrinking after the
    # fact: rendering straight to the target size keeps the text crisp.
    span_in = clip.width / 72
    if span_in > 0:
        dpi = min(dpi, max(72, int(MAX_WIDTH / span_in)))
    pix = page.get_pixmap(dpi=dpi, clip=clip)
    if trim:
        pix = _trim(pix)
    out = save(pix, out)
    report(out, pix)
    return 0


def cmd_fetch(url: str, out: pathlib.Path, cite: str) -> int:
    """Download a figure into the workspace. Never hotlink: the lesson is read
    offline from file://, and a URL that 404s in a month is a lesson with a hole
    in it. Provenance is written next to the file, not left in the chat."""
    out.parent.mkdir(parents=True, exist_ok=True)
    # curl, not urllib: the python.org build on this Mac ships no CA bundle, so
    # urllib fails every https fetch with CERTIFICATE_VERIFY_FAILED. curl uses
    # the system keychain and is on every Mac. The User-Agent is not optional —
    # Wikimedia, the best source of licensed diagrams, 400s a request without one.
    proc = subprocess.run(
        ["curl", "-fsSL", "--max-time", "45", "-A", UA,
         "-w", "%{content_type}", "-o", str(out), url],
        capture_output=True, text=True)
    if proc.returncode != 0:
        out.unlink(missing_ok=True)
        sys.exit(f"error: could not fetch {url} — {proc.stderr.strip() or proc.returncode}")
    # A server that says text/html is serving an error page or a cookie wall,
    # whatever the URL ends in. Only an absent content-type falls back to the
    # extension; a stated one is believed.
    ctype = proc.stdout.strip().split(";")[0]
    ok = ("image" in ctype) if ctype else \
         out.suffix.lower() in {".png", ".jpg", ".jpeg", ".svg", ".webp"}
    if not ok:
        out.unlink(missing_ok=True)
        sys.exit(f"error: {url} served {ctype or 'no content-type'}, not an image")

    if out.suffix.lower() != ".svg":
        try:  # re-encode through pymupdf so an oversized JPEG does not ship as-is
            pix = pymupdf.Pixmap(out)
            while pix.width > 2 * MAX_WIDTH:
                pix.shrink(1)
            written = save(pix, out.with_suffix(".png"))
            if out != written:
                out.unlink(missing_ok=True)
            out = written
            report(out, pix)
        except Exception:
            print(f"{out}  {out.stat().st_size / 1024:.0f} KB (kept as downloaded)")
    else:
        print(f"{out}  {out.stat().st_size / 1024:.0f} KB")

    src = out.parent / "SOURCES.md"
    if not src.exists():
        src.write_text("# ที่มาของรูปในโฟลเดอร์นี้\n\n"
                       "รูปที่ครอปจากชีท/สไลด์ของครูไม่ต้องลง — อ้างหน้าในแถบ .meta แทน\n"
                       "รูปที่โหลดจากเน็ตต้องมีบรรทัดของตัวเองที่นี่ทุกรูป\n\n",
                       encoding="utf-8")
    with src.open("a", encoding="utf-8") as f:
        f.write(f"- `{out.name}` — {cite or 'ไม่ระบุที่มา — ต้องเติม'}\n  {url}\n")
    if not cite:
        print("  ! no --cite given; SOURCES.md now has a hole in it", file=sys.stderr)
    return 0


def cmd_check(folder: pathlib.Path) -> int:
    """Every figure the lesson will ship, with the two numbers that matter."""
    if not folder.exists():
        sys.exit(f"error: {folder} not found")
    files = sorted(p for p in folder.rglob("*")
                   if p.suffix.lower() in {".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg"})
    if not files:
        print(f"{folder} holds no figures")
        return 0
    bad = 0
    for p in files:
        size = p.stat().st_size
        if p.suffix.lower() == ".svg":
            print(f"  {p.relative_to(folder)}  svg  {size / 1024:.0f} KB")
            continue
        try:
            pix = pymupdf.Pixmap(p)  # native pixels; get_pixmap() would re-render at 72dpi
            dims, w = f"{pix.width}×{pix.height}px", pix.width
        except Exception as e:
            print(f"  ✗ {p.relative_to(folder)} — unreadable: {e}")
            bad += 1
            continue
        notes = []
        if w < MIN_WIDTH:
            notes.append(f"too small (<{MIN_WIDTH}px) — labels will be mush")
        if size > FAT_BYTES:
            notes.append("very heavy — re-crop at a lower --dpi")
        mark = "!" if notes else " "
        print(f"  {mark} {p.relative_to(folder)}  {dims}  {size / 1024:.0f} KB"
              + (f"  — {'; '.join(notes)}" if notes else ""))
        bad += bool(notes)
    print(f"\n{len(files)} figure(s), {bad} worth a second look")
    return 0


# --------------------------------------------------------------------------
def main() -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("mode", choices=["list", "pull", "grid", "crop", "fetch", "check"])
    ap.add_argument("source", help="the PDF, the URL (fetch), or the folder (check)")
    ap.add_argument("--pages", default="", help="list/grid: e.g. 4-9 or 1,4,9-11 (1-based)")
    ap.add_argument("--page", type=int, default=1, help="pull/crop: which page (1-based)")
    ap.add_argument("--index", type=int, default=0, help="pull: which image, from `list`")
    ap.add_argument("--box", default="", help="crop: x0,y0,x1,y1 as percentages of the page")
    ap.add_argument("--out", type=pathlib.Path, help="output file, or folder for `grid`")
    ap.add_argument("--dpi", type=int, default=220, help="crop/grid render resolution")
    ap.add_argument("--trim", action="store_true", help="crop: shave uniform light margins")
    ap.add_argument("--cite", default="", help="fetch: source + licence, for SOURCES.md")
    a = ap.parse_args()

    if a.mode in {"list", "pull", "grid", "crop"}:
        pdf = pathlib.Path(a.source)
        if not pdf.exists():
            sys.exit(f"error: {pdf} not found")
        if a.mode == "list":
            return cmd_list(pdf, a.pages)
        if a.mode == "grid":
            return cmd_grid(pdf, a.pages or str(a.page),
                            a.out or pathlib.Path("grid"), a.dpi)
        if not a.out:
            sys.exit(f"error: {a.mode} needs --out lessons/fig/NAME.png")
        if a.mode == "pull":
            return cmd_pull(pdf, a.page, a.index, a.out)
        if not a.box:
            sys.exit("error: crop needs --box x0,y0,x1,y1 (run `grid` to read it off)")
        return cmd_crop(pdf, a.page, a.box, a.out, a.dpi, a.trim)

    if a.mode == "fetch":
        if not re.match(r"https?://", a.source):
            sys.exit("error: fetch wants a http(s) URL")
        if not a.out:
            sys.exit("error: fetch needs --out lessons/fig/NAME.png")
        return cmd_fetch(a.source, a.out, a.cite)

    return cmd_check(pathlib.Path(a.source))


if __name__ == "__main__":
    raise SystemExit(main())
