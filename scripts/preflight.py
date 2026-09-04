#!/usr/bin/env python3
"""
preflight — nothing is handed over until this passes.

Four of these checks catch *silent* failures: the page looks fine on the screen
you built it on and is broken on the one you study from. Mojibake Thai, a
stylesheet Safari refused to load, a quiz whose engine never ran, a number
nobody computed. Each has already cost this workspace real time, which is why
they block rather than warn.

Two more are warnings: citations and the eyeball list. They make the output
better, they never make it broken, and at 23:00 the night before a test the
right behaviour is to hand over imperfect files rather than no files.

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

    # Options are shuffled on load, so prose that names a letter is now wrong.
    for m in re.finditer(r'data-(?:ok|no)="([^"]*)"', text):
        if re.search(r"(?:ตัวเลือก|choice|option)\s*[A-D]\b", m.group(1)):
            warn(name, "feedback names an option letter, but options are shuffled — "
                       'describe the option instead, or set data-shuffle="off"')
            break


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

    pages = sorted(
        list((root / "lessons").glob("*.html")) + list((root / "reference").glob("*.html"))
    )
    if not pages:
        print(f"error: no pages under {root}/lessons or {root}/reference")
        return 1

    for p in pages:
        text = p.read_text(encoding="utf-8", errors="replace")
        name = str(p.relative_to(root))
        check_charset(name, text)
        check_parent_refs(name, text)
        check_quiz(name, text)
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
        if "<svg" in text or "<img" in text:
            why.append("has a figure")
        if 'data-type="reveal"' in text:
            why.append("worked solutions")
        if re.search(r"\\\(|\\\[|<sub>|<sup>", text):
            why.append("formulas")
        if why:
            print(f"  · {p.relative_to(root)} — {', '.join(why)}")

    if BLOCK:
        print(f"\nBLOCKED: {len(BLOCK)} silent failure(s). Do not hand this over.")
        return 1
    print(f"\nOK to hand over. ({len(WARN)} warning(s))")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
