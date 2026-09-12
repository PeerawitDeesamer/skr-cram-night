#!/usr/bin/env python3
"""
preflight — nothing is handed over until this passes.

These checks catch *silent* failures: the page looks fine on the screen you
built it on and is broken on the one you study from. Mojibake Thai, a stylesheet
Safari refused to load, a quiz whose engine never ran, a figure whose file is
not there, a number nobody computed. Each has already cost this workspace real
time, which is why they block rather than warn.

A hand-drawn <svg> blocks too, for a different reason: a diagram invented
here was never checked against the sheet, and a confident wrong picture is
studied just as hard as a right one. Figures come from the slides or from a
trusted source.

The rest are warnings: the figure quota, citations, alt text, the eyeball list.
They make the output better, they never make it broken, and at 23:00 the night
before a test the right behaviour is to hand over imperfect files rather than
no files.

Usage
-----
    python3 preflight.py                 # check the workspace you are in
    python3 preflight.py --subject chem  # also require verified numbers

Exit code 0 = safe to hand over. 1 = blocking failure, fix it first.
"""

import argparse
import json
import pathlib
import re
import sys

MATHY = {"chem", "physics", "math"}

BLOCK, WARN = [], []


def block(page, msg):
    BLOCK.append(f"{page}: {msg}")


def warn(page, msg):
    WARN.append(f"{page}: {msg}")


# --------------------------------------------------------------------------
def check_charset(name, text):
    """No HTTP header exists on file://, so the browser guesses the encoding.
    Guess wrong and every Thai character becomes à¸ªà¸£à¹‰à¸²à¸‡."""
    head = text[:1024].lower()
    if 'charset="utf-8"' not in head and "charset=utf-8" not in head:
        block(name, "no <meta charset=\"utf-8\"> in the first 1KB — Thai will render as mojibake")


def check_parent_refs(name, text):
    """Safari refuses file:// subresources that reach into a parent directory."""
    for m in re.finditer(r'(?:href|src)="(\.\./[^"]+)"', text):
        ref = m.group(1)
        if ref.endswith((".css", ".js")):
            block(name, f'still links {ref} — run build.py, Safari will not load it')


def check_quiz(name, text):
    """A quiz that does not initialise looks like a quiz until you click it."""
    # [data-quiz] containers are filled in by the legacy renderQuiz() from a JS
    # array; they carry no data-answer by design and are not a defect.
    quizzes = [q for q in re.findall(r'<div class="quiz"[^>]*>', text) if "data-quiz" not in q]
    if not quizzes:
        return
    has_engine = "renderQuiz" in text or "querySelectorAll('.quiz')" in text
    if not has_engine:
        block(name, f"{len(quizzes)} quiz block(s) but the engine is not on the page")
    # The inlined block legitimately ends with one </script>; a SECOND one means
    # an unescaped close tag inside the code, which truncates the engine silently.
    for begin, end, what in [
        ("<!-- BEGIN inlined assets/quiz.js -->", "<!-- END inlined assets/quiz.js -->", "engine"),
    ]:
        if begin in text and end in text:
            region = text.split(begin, 1)[1].split(end, 1)[0]
            if region.count("</script>") > 1:
                block(name, f"an unescaped </script> inside the inlined {what} — it will be cut off")

    for tag in quizzes:
        kind = (re.search(r'data-type="([^"]+)"', tag) or [None, "mc"])[1]
        if kind in ("mc", "fib") and "data-answer=" not in tag:
            block(name, f"a {kind} quiz has no data-answer — it can never be right")

    # quiz.js reads dataset.shuffle off the .quiz container. Put it on .opts and
    # nothing errors — the attribute is simply never seen, and the ordered
    # options the author was protecting get scrambled anyway.
    if re.search(r'<div class="opts"[^>]*data-shuffle', text):
        warn(name, 'data-shuffle is on <div class="opts"> where the engine never '
                   'reads it — move it onto the <div class="quiz"> tag')

    # Options are shuffled on load, so prose that names a letter is now wrong.
    for m in re.finditer(r'data-(?:ok|no)="([^"]*)"', text):
        if re.search(r"(?:ตัวเลือก|choice|option)\s*[A-D]\b", m.group(1)):
            warn(name, "feedback names an option letter, but options are shuffled — "
                       'describe the option instead, or set data-shuffle="off"')
            break


# Bio and Chem lessons are read off a screen at 01:00; the pages made of prose
# alone are the ones that get scrolled past. See docs/FIGURES.md for the quota.
FIG_QUOTA = {"bio": 4, "chem": 3, "physics": 3, "math": 2}

IMG_RE = re.compile(r'<img\b[^>]*>')
SRC_RE = re.compile(r'\bsrc="([^"]+)"')


SCRIPTY_RE = re.compile(r"<(script|style)\b.*?</\1>", re.DOTALL | re.IGNORECASE)
FIGURE_RE = re.compile(r"<figure\b.*?</figure>", re.DOTALL | re.IGNORECASE)


def count_figures(text):
    """How many pictures the reader actually sees.

    The inlined engines are stripped first — graph.js builds its SVG out of
    string literals, and counting those would credit every page with a dozen
    figures it does not have. A <figure> counts once whether it holds an <img>
    or is an empty .cgraph shell that graph.js plots into at load."""
    body = SCRIPTY_RE.sub("", text)
    body, figures = FIGURE_RE.subn("", body)
    return figures + len(IMG_RE.findall(body))


def check_images(path, name, text):
    """A figure that does not load is worse than one that was never added: the
    page still promises a diagram, and the caption still refers to it."""
    text = SCRIPTY_RE.sub("", text)  # the inlined engines are code, not markup
    for tag in IMG_RE.findall(text):
        m = SRC_RE.search(tag)
        if not m:
            block(name, "an <img> with no src")
            continue
        src = m.group(1)
        if src.startswith("data:"):
            continue
        if re.match(r"https?://", src):
            block(name, f"hotlinks {src[:60]} — the page is read offline from "
                        "file://; use figure.py fetch to bring it into fig/")
            continue
        if src.startswith("../"):
            block(name, f'<img src="{src}"> reaches into a parent folder — '
                        "Safari will not load it; move the file into lessons/fig/")
            continue
        target = (path.parent / src).resolve()
        if not target.exists():
            block(name, f"<img src=\"{src}\"> points at nothing")
        if 'alt="' not in tag or re.search(r'alt="\s*"', tag):
            warn(name, f"an <img> has no useful alt text ({src})")

    # Where a figure came from is the only way to check it later: a slide page
    # number, or the licence line figure.py fetch wrote into fig/SOURCES.md.
    for fig in FIGURE_RE.findall(text):
        if "<img" in fig and "figsrc" not in fig:
            warn(name, "a figure has no .figsrc line — say which slide page it "
                       "came from, or which source it was fetched from")

    # A diagram drawn here by hand is a diagram nobody checked against the
    # sheet: it looks authoritative and can be wrong in exactly the way the
    # marker is testing. Figures come from the teacher's own slide, or from a
    # trusted source via `figure.py fetch` — never from this script's
    # imagination. graph.js is the one exception, and it writes its <svg> at
    # load time out of data-series, so nothing literal shows up here.
    if re.search(r"<svg\b", text):
        block(name, "an inline <svg> is drawn by hand — pull the figure from the "
                    "slides (figure.py pull/crop) or fetch one from a trusted "
                    "source; a plot of the sheet's own numbers goes in "
                    '<figure class="cgraph" data-series=…>')


def check_figure_quota(name, text, subject):
    want = FIG_QUOTA.get(subject)
    if not want:
        return
    got = count_figures(text)
    if got < want:
        warn(name, f"{got} figure(s), {subject} wants {want} — "
                   "a science lesson made of prose is one nobody finishes (docs/FIGURES.md)")


WHERE_RE = re.compile(r'<div class="where".*?</div>', re.DOTALL)


def check_where(name, text, subject):
    """Biology only: a process the reader cannot place is a process they cannot
    answer about. The Thai school paper asks "เกิดที่ใด" more often than it asks
    how the mechanism works, and location scattered through prose reads fine and
    tests badly."""
    if subject != "bio":
        return
    body = SCRIPTY_RE.sub("", text)
    blocks = WHERE_RE.findall(body)
    # A page with no "คัดลงสมุด" block is not a lesson (กฎเหล็ก 5 makes that block
    # mandatory in one) — it is a mock exam or a reference sheet. An exam must
    # not carry a .where: that block exists to TELL the reader where things
    # happen, which is exactly what the exam is asking them.
    teaches = 'class="copy"' in body
    if teaches and not blocks:
        warn(name, 'no <div class="where"> — every process must say which organ, '
                   "which part, made-where vs acts-where (docs/WHERE.md)")
    for b in blocks:
        if len(re.findall(r"<dt\b", b)) < 2:
            warn(name, "a .where block has fewer than 2 slots filled — "
                       "อวัยวะ and ส่วน/เซลล์ are the minimum")

    if 'class="quiz"' in body and not re.search(r'data-tag="ตำแหน่ง-', body):
        warn(name, 'no quiz tagged data-tag="ตำแหน่ง-…" — the location question is '
                   "the one the reader thinks they can answer until asked")


HL_CLASSES = {"key", "trap", "num", "def"}
MARK_RE = re.compile(r"<mark\b([^>]*)>(.*?)</mark>", re.DOTALL | re.IGNORECASE)
OPTS_RE = re.compile(r'<div class="opts".*?</div>', re.DOTALL)
HEAD_RE = re.compile(r"<h[123]\b[^>]*>.*?</h[123]>", re.DOTALL | re.IGNORECASE)
TAG_RE = re.compile(r"<[^>]+>")


def check_highlight(name, text):
    """Highlighting is a budget, not a decoration (docs/HIGHLIGHT.md).

    Every extra mark makes the rest cheaper, and a page painted end to end reads
    exactly like a page with no marks at all — except it took longer to write.
    The one blocking case is a mark inside the options of a quiz: the eye lands
    on the coloured choice before the reader has thought, they get it right, and
    they walk away believing they know the topic."""
    body = SCRIPTY_RE.sub("", text)

    for opts in OPTS_RE.findall(body):
        if MARK_RE.search(opts):
            block(name, "a <mark> inside <div class=\"opts\"> — the highlighted "
                        "option is answered by eye, not by thinking (docs/HIGHLIGHT.md)")
            break

    marks = MARK_RE.findall(body)
    if not marks:
        # A glossary or a mock exam is not a lesson; only a teaching page (กฎเหล็ก 5
        # makes .copy mandatory in one) is expected to guide the eye.
        if 'class="copy"' in body:
            warn(name, "nothing is highlighted — a page of even grey text is one "
                       "that gets scrolled past at 01:00 (docs/HIGHLIGHT.md)")
        return

    marked, seen, said = 0, set(), set()
    for attrs, inner in marks:
        cls = re.search(r"""class=["']([^"']*)["']""", attrs)
        for c in (cls.group(1).split() if cls else []):
            if c not in HL_CLASSES and c not in seen:
                seen.add(c)
                warn(name, f'<mark class="{c}"> is not a highlight kind — '
                           f"use {' / '.join(sorted(HL_CLASSES))}, or plain <mark>")
        plain = TAG_RE.sub("", inner).strip()
        marked += len(plain)
        # One line per kind: a page that got this wrong got it wrong everywhere,
        # and twenty identical warnings bury the four that differ.
        if re.search(r"<(p|li|div|table|h[123])\b", inner, re.IGNORECASE):
            if "blockwrap" not in said:
                said.add("blockwrap")
                warn(name, "a <mark> wraps a whole block element — highlight the "
                           "words that carry the claim, not the container")
        elif len(plain) > 100 and "toolong" not in said:
            said.add("toolong")
            warn(name, f'a <mark> covers {len(plain)} characters ("{plain[:32]}…") — '
                       "past a phrase the eye has nowhere to land")

    for h in HEAD_RE.findall(body):
        if MARK_RE.search(h):
            warn(name, "a <mark> inside a heading — headings already stand out")
            break

    # Share of the visible prose that is painted. Ten percent is roughly one
    # phrase per paragraph, which is what a reader can still act on.
    # Short pages make the ratio jumpy — a formula sheet with three marks is
    # not over-painted — so the budget only applies once there is prose to budget.
    visible = len(TAG_RE.sub("", body).strip())
    if visible > 1200 and len(marks) >= 5 and marked / visible > 0.10:
        warn(name, f"{marked * 100 // visible}% of the text is highlighted "
                   f"({len(marks)} marks) — if everything matters, nothing does")


HEAD_ALL_RE = re.compile(r"<(h[1-6])\b([^>]*)>(.*?)</\1>", re.DOTALL | re.IGNORECASE)
COLOR_RE = re.compile(r"(?:style=[\"'][^\"']*\bcolor\s*:|<font\b[^>]*\bcolor=)", re.IGNORECASE)


def check_headings(name, text):
    """Heading colour belongs to the stylesheet, not to the page.

    แดง = หัวเรื่อง (h1/h2), น้ำเงิน = หัวเรื่องย่อย (h3 ลงไป) — สีผูกกับระดับของ
    หัวข้อ ไม่ใช่ความสำคัญ (กฎเหล็ก 12). A page that paints its own headings looks
    right the day it is written and stops matching every other page the next time
    lesson.css moves, which is exactly the sort of drift nobody notices at 01:00."""
    body = SCRIPTY_RE.sub("", text)
    said = False
    for tag, attrs, inner in HEAD_ALL_RE.findall(body):
        if said:
            break
        if COLOR_RE.search(attrs) or COLOR_RE.search(inner):
            said = True
            warn(name, f"<{tag.lower()}> sets its own colour — แดง = หัวเรื่อง, "
                       "น้ำเงิน = หัวเรื่องย่อย มาจาก lesson.css แล้ว (กฎเหล็ก 12)")


def check_citation(name, text):
    """Every lesson should be traceable back to the teacher's own sheet."""
    if re.search(r"(หน้า\s*\d+|ตย\.\s*\d|ตัวอย่าง\s*\d|แบบฝึกหัด|p\.\s*\d+)", text):
        return
    warn(name, "cites no page / ตัวอย่าง / แบบฝึกหัด from the sheet")


def check_numbers(root, subject):
    """Math-y subjects may not ship numbers that Python never produced."""
    if subject not in MATHY:
        return
    vo = root / "verify_out.json"
    if not vo.exists():
        block("workspace", "no verify_out.json — numbers were never computed (กฎเหล็ก 3)")
        return
    try:
        data = json.loads(vo.read_text())
    except json.JSONDecodeError as e:
        block("verify_out.json", f"unreadable: {e}")
        return
    counts = data.get("counts", {})
    if counts.get("fail"):
        block("verify_out.json", f"{counts['fail']} value(s) disagree with the sheet")
    if not (counts.get("pass", 0) + counts.get("computed", 0)):
        block("verify_out.json", "contains no checked values at all")


# --------------------------------------------------------------------------
def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--subject", default="", help="chem | bio | physics | math")
    ap.add_argument("--root", type=pathlib.Path, default=pathlib.Path.cwd())
    a = ap.parse_args()
    root = a.root.resolve()

    # lessons/ and reference/ sit either at the workspace root, or one level
    # down inside a per-topic folder (Biology/Digestion/lessons, ...) once a
    # subject grows past a single topic. Scan both shapes.
    pages = sorted(
        set(root.glob("lessons/*.html"))
        | set(root.glob("reference/*.html"))
        | set(root.glob("*/lessons/*.html"))
        | set(root.glob("*/reference/*.html"))
    )
    if not pages:
        print(f"error: no pages under {root}/lessons or {root}/reference "
              f"(nor {root}/*/lessons)")
        return 1

    for p in pages:
        text = p.read_text(encoding="utf-8", errors="replace")
        name = str(p.relative_to(root))
        check_charset(name, text)
        check_parent_refs(name, text)
        check_quiz(name, text)
        check_images(p, name, text)
        # A glossary or a formula sheet is a lookup table; the quota is for lessons.
        if "/lessons/" in f"/{name}":
            check_figure_quota(name, text, a.subject.lower())
        if "/lessons/" in f"/{name}":
            check_where(name, text, a.subject.lower())
        if "/lessons/" in f"/{name}":
            check_highlight(name, text)
        check_headings(name, text)
        check_citation(name, text)

    check_numbers(root, a.subject.lower())

    print(f"preflight · {len(pages)} page(s) · {root.name}")
    for line in BLOCK:
        print(f"  ✗ {line}")
    for line in WARN:
        print(f"  ! {line}")

    # Nothing automated can tell you whether a diagram is right or an
    # explanation lands. Name what a human still has to look at.
    print("\nlook at these yourself before you rely on them:")
    for p in pages:
        text = p.read_text(encoding="utf-8", errors="replace")
        why = []
        n_fig = count_figures(text)
        if n_fig:
            # No script can tell a crop of the right diagram from a crop of the
            # one next to it, so every figure is on the human's list.
            why.append(f"{n_fig} figure(s)")
        if 'data-type="reveal"' in text:
            why.append("worked solutions")
        if re.search(r"\\\(|\\\[|<sub>|<sup>", text):
            why.append("formulas")
        if WHERE_RE.search(SCRIPTY_RE.sub("", text)):
            why.append("location claims")
        if why:
            print(f"  · {p.relative_to(root)} — {', '.join(why)}")

    if BLOCK:
        print(f"\nBLOCKED: {len(BLOCK)} silent failure(s). Do not hand this over.")
        return 1
    print(f"\nOK to hand over. ({len(WARN)} warning(s))")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
