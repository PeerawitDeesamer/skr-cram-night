#!/usr/bin/env python3
"""
Inline the shared assets into every lesson / reference page.

Why this exists
---------------
`assets/lesson.css` and `assets/quiz.js` stay the single source of truth — edit
them, never the copies. But the pages live in `lessons/` and `reference/`, so a
plain <link href="../assets/..."> has to reach into a PARENT directory. Safari
refuses to load file:// subresources that way, so the pages render unstyled and
the quizzes never initialise. Chrome allows it, which is exactly why the bug
survives a "looks fine on my machine" check.

So: author against the shared assets, then run this to stamp their current
contents into each page between marker comments. The pages become fully
self-contained — they open correctly from any folder, in any browser, offline,
and even when emailed to yourself.

Usage
-----
    python3 build.py            # sync every page in this workspace
    python3 build.py --check    # report drift without writing

Re-run it after ANY edit to assets/lesson.css or assets/quiz.js.
"""

import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parent
ASSETS = ROOT / "assets"

CSS_BEGIN = "<!-- BEGIN inlined assets/lesson.css -->"
CSS_END = "<!-- END inlined assets/lesson.css -->"
JS_BEGIN = "<!-- BEGIN inlined assets/quiz.js -->"
JS_END = "<!-- END inlined assets/quiz.js -->"

# Both the current name and the pre-merge Chemistry name, with or without defer.
LINK_RE = re.compile(r'[ \t]*<link[^>]+href="\.\./assets/(?:lesson|style)\.css"[^>]*>\n?')
SCRIPT_RE = re.compile(r'[ \t]*<script[^>]*src="\.\./assets/quiz\.js"[^>]*></script>\n?')


def block(begin: str, end: str, tag: str, body: str) -> str:
    # An HTML parser ends a <script>/<style> block at the first matching close
    # tag in the raw text — even one sitting inside a JS comment or string.
    # quiz.js documents its own usage with a literal </script>, which would
    # truncate the inlined code and spill the remainder onto the page as text.
    # Escaping the slash keeps the JS/CSS identical to the parser but invisible.
    body = re.sub(rf"</\s*{tag}", rf"<\\/{tag}", body, flags=re.IGNORECASE)
    return f"{begin}\n<{tag}>\n{body.strip()}\n</{tag}>\n{end}\n"


def replace_between(text: str, begin: str, end: str, new: str) -> str:
    pattern = re.compile(re.escape(begin) + r".*?" + re.escape(end) + r"\n?", re.DOTALL)
    return pattern.sub(lambda _: new, text)


def sync(path: pathlib.Path, css: str, js: str) -> bool:
    """Return True if the file's content changed."""
    original = path.read_text(encoding="utf-8")
    text = original

    css_block = block(CSS_BEGIN, CSS_END, "style", css)
    js_block = block(JS_BEGIN, JS_END, "script", js)

    if CSS_BEGIN in text:
        text = replace_between(text, CSS_BEGIN, CSS_END, css_block)
    else:
        # A lambda keeps the replacement literal: re.sub() would otherwise read
        # the backslashes inside the engine's own regexes (/\s+/g) as escape
        # sequences and refuse to run.
        text, n = LINK_RE.subn(lambda _: css_block, text, count=1)
        if not n:
            print(f"  ! {path.name}: no stylesheet link or marker found")

    # quiz.js only belongs on pages that actually run a quiz
    if JS_BEGIN in text:
        text = replace_between(text, JS_BEGIN, JS_END, js_block)
    elif SCRIPT_RE.search(text):
        text = SCRIPT_RE.sub(lambda _: js_block, text, count=1)
    elif 'class="quiz"' in text:
        # A page with quizzes but no script tag would silently render dead
        # boxes; inline the engine right before </body> instead.
        if "</body>" in text:
            text = text.replace("</body>", js_block + "</body>", 1)
        else:
            text = text.rstrip() + "\n" + js_block
        print(f"  + {path.name}: quizzes found with no script tag — engine inlined")

    # Any other script the page pulls from ../assets (Chemistry's graph.js, and
    # whatever a future subject adds) hits the same Safari block, so inline it
    # the same way rather than leaving one working asset and one dead one.
    for m in list(re.finditer(r'[ \t]*<script[^>]*src="\.\./assets/([A-Za-z0-9_-]+)\.js"[^>]*></script>\n?', text)):
        stem = m.group(1)
        if stem == "quiz":
            continue
        extra = ASSETS / f"{stem}.js"
        if not extra.exists():
            print(f"  ! {path.name}: links ../assets/{stem}.js which is not in this workspace")
            continue
        begin = f"<!-- BEGIN inlined assets/{stem}.js -->"
        end = f"<!-- END inlined assets/{stem}.js -->"
        blk = block(begin, end, "script", extra.read_text(encoding="utf-8"))
        text = text.replace(m.group(0), blk, 1)

    for extra in sorted(ASSETS.glob("*.js")):
        if extra.stem == "quiz":
            continue
        begin = f"<!-- BEGIN inlined assets/{extra.stem}.js -->"
        end = f"<!-- END inlined assets/{extra.stem}.js -->"
        if begin in text and end in text:
            blk = block(begin, end, "script", extra.read_text(encoding="utf-8"))
            text = replace_between(text, begin, end, blk)

    if text != original:
        path.write_text(text, encoding="utf-8")
        return True
    return False


def main() -> int:
    check_only = "--check" in sys.argv

    css_path = ASSETS / "lesson.css"
    if not css_path.exists():
        legacy = ASSETS / "style.css"
        if legacy.exists():
            print(f"error: {ASSETS}/lesson.css not found (found style.css — run install.sh)")
        else:
            print(f"error: {css_path} not found")
        return 1

    css = css_path.read_text(encoding="utf-8")
    js_path = ASSETS / "quiz.js"
    js = js_path.read_text(encoding="utf-8") if js_path.exists() else ""

    pages = sorted(
        list((ROOT / "lessons").glob("*.html")) + list((ROOT / "reference").glob("*.html"))
    )
    if not pages:
        print("no pages found in lessons/ or reference/")
        return 1

    changed = []
    for page in pages:
        if check_only:
            before = page.read_text(encoding="utf-8")
            if sync(page, css, js):
                page.write_text(before, encoding="utf-8")  # restore
                changed.append(page)
        elif sync(page, css, js):
            changed.append(page)

    verb = "would update" if check_only else "updated"
    for page in changed:
        print(f"  {verb}  {page.relative_to(ROOT)}")
    print(f"{len(changed)} of {len(pages)} page(s) {verb}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
