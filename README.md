# skr — a cram-night lesson builder

A [Claude Code](https://claude.com/claude-code) skill for Thai high-school students.
Point it at the PDF sheet (ชีท) your teacher handed out, and it produces a set of
self-contained HTML lessons plus hint-then-solution walkthroughs of **the sheet's own
exercises** — the ones that will actually be on the test.

Built for Chemistry, Biology, Physics and Mathematics at ม.4–ม.6 level, in Thai with
English technical terms.

## Why it works the way it does

Most study tools are built for the student you wish you were: the one who reviews on a
schedule, reports their quiz scores, and starts three days before the exam.

This one is built for the student who starts the night before, because that is when
people actually show up. So it has **no reminders, no calendar integration, no spaced
repetition scheduler, and no separate review command.** It is designed to be excellent
in the four hours that really happen, and to ask exactly one thing of you afterwards:
one line naming the topics you got wrong, once the graded paper comes back.

## What a run looks like

```
คุณ:   สอบเคมีวันศุกร์ บทที่ 9 หน้า 1-19
skr:  [asks 3 questions, locks the spec, says it back to you]
      [reads the sheet, orders lessons high-yield first]
      [computes every number in Python before writing a word]
      [writes the pages, inlines the assets, runs preflight]
→ ~20 minutes later: lessons you can open, and the teacher's own
   แบบฝึกหัด unlocked with a hint first and a full solution second
```

Every lesson opens with a **"คัดลงสมุด"** block — the five to eight lines worth copying
into your notebook by hand, marked out so you don't have to read a whole page to find
them.

## The rules it will not break

1. Lock the spec and say it back before writing anything — never guess silently
2. Order by high-yield, never by page number, so stopping early still leaves something usable
3. **Chem/Physics/Math: every number is computed in Python and checked against the
   sheet's answer before it is written.** Biology: every claim cites a page.
   A confidently wrong worked solution is worse than none — it teaches a method that
   gets reproduced under exam pressure
4. Never invent new problems; the teacher's exercises are the ones that count
5. Every lesson carries a "copy this down" block
6. Nothing ships until `preflight.py` passes
7. Past mistakes automatically weight the next build
8. Thai explanations, English technical terms
9. **Highlight the words that decide the answer, and nothing else.** Five colours with
   five jobs (main point / must-memorise / exam trap / number / term being defined),
   capped at ~10% of a page. A page painted end to end reads exactly like a page with
   no highlighting at all. Highlighting inside a quiz's options is a blocking error —
   the eye picks the coloured choice before the reader has thought

## Install

Requires Python 3 and [Claude Code](https://claude.com/claude-code).

```bash
git clone https://github.com/PeerawitDeesamer/skr-cram-night.git ~/.claude/skills/skr
bash ~/.claude/skills/skr/install.sh
```

`install.sh` installs `pymupdf` (reading teacher PDFs) and `sympy` (verifying numbers),
creates `~/Documents/SKR/<Subject>/` for each subject, and copies the shared assets in.
Run it with `--check` to see what's missing without changing anything.

## Layout

```
SKILL.md              the rules and the workflow
docs/
  WORKFLOW.md         one night, start to finish
  LESSON-FORMAT.md    HTML skeleton, CSS classes, the three quiz types
  HIGHLIGHT.md        the five highlight kinds, the budget, where it gives the answer away
  VERIFY.md           how to write verify.py; the Biology citation rule
  SHEETS.md           reading PDFs, including scanned ones
  RESULTS.md          recording a graded paper
  TROUBLESHOOTING.md  the file:// traps, in detail
scripts/
  sheet.py            probe / extract text / render scanned pages
  verify_lib.py       sympy ICE solver, Kp↔Kc, a PASS/COMPUTED/FAIL ledger
  preflight.py        the silent failures block; everything else warns
  results.py          record wrong topics; weight the next build
assets/               one lesson.css, one quiz.js, one build.py, graph.js
```

## Things learned the hard way

Pages are opened from `file://`, not a web server, and that breaks two things silently:

* **No HTTP header means no encoding**, so a page without `<meta charset="utf-8">` first
  turns every Thai character into `à¸ªà¸£à¹‰à¸²à¸‡`
* **Safari refuses `file://` subresources that reach into a parent directory**, so
  `<link href="../assets/lesson.css">` loads a completely unstyled page — while Chrome
  loads it fine, which is exactly why the bug survives testing

`build.py` inlines the shared assets into every page to sidestep both, and `preflight.py`
blocks on either one rather than warning, because both look fine until you rely on them.

There is a third: an HTML parser closes a `<script>` at the first `</script>` in the raw
text, **even one inside a JavaScript comment.** `quiz.js` documents its own usage with a
literal `</script>`, so the build escapes it on the way in.

## License

MIT — see [LICENSE](LICENSE).
