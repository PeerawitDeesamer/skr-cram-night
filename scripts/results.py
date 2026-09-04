#!/usr/bin/env python3
"""
results — the one thing the system asks you for, and the only reason it can
ever answer "what should I study next".

You report topics, not scores: a score says you are weak, a topic says where.
It takes one line, once, when the graded paper comes back.

    python3 results.py add --subject chem --chapter "บทที่ 9 สมดุล" \
        --wrong "ICE table, Kp/Kc" --note "ทำไม่ทัน 3 ข้อ" --score 14/20

    python3 results.py weak --subject chem      # what the next build weights toward
    python3 results.py weak                     # across every subject

Two things are written, deliberately:
  * learning-records/NNNN-result-<date>.md — human-readable, in the same folder
    the `teach` convention already uses for "what is actually known"
  * results.jsonl — machine-readable, so the next lesson build can weight itself
    without anyone having to remember to ask
"""

import argparse
import datetime as dt
import json
import pathlib
import re
import sys
from collections import Counter

BASE = pathlib.Path.home() / "Documents" / "SKR"
SUBJECTS = {
    "chem": "Chemistry",
    "bio": "Biology",
    "physics": "Physics",
    "math": "Math",
}


def workspace(subject: str) -> pathlib.Path:
    key = subject.lower()
    if key not in SUBJECTS:
        sys.exit(f"error: unknown subject {subject!r} — one of {', '.join(SUBJECTS)}")
    return BASE / SUBJECTS[key]


def split_topics(raw: str) -> list[str]:
    return [t.strip() for t in re.split(r"[,;/]|、", raw) if t.strip()]


def next_record_number(records: pathlib.Path) -> int:
    n = 0
    for f in records.glob("[0-9][0-9][0-9][0-9]-*.md"):
        n = max(n, int(f.name[:4]))
    return n + 1


def cmd_add(a) -> int:
    ws = workspace(a.subject)
    if not ws.exists():
        sys.exit(f"error: {ws} does not exist yet — build a lesson set for it first")
    records = ws / "learning-records"
    records.mkdir(exist_ok=True)

    topics = split_topics(a.wrong)
    date = a.date or dt.date.today().isoformat()
    entry = {
        "date": date,
        "subject": a.subject.lower(),
        "chapter": a.chapter,
        "wrong": topics,
        "score": a.score,
        "note": a.note,
    }
    with (ws / "results.jsonl").open("a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")

    num = next_record_number(records)
    # Keep Thai in the slug — stripping it left every Thai chapter named "result".
    slug = re.sub(r"[^\w\u0e00-\u0e7f]+", "-", (a.chapter or "").lower()).strip("-")[:40]
    md = records / (f"{num:04d}-result-{slug}-{date}.md" if slug
                    else f"{num:04d}-result-{a.subject.lower()}-{date}.md")
    lines = [
        f"# ผลสอบจริง: {a.chapter or a.subject} ({date})",
        "",
        "รายงานจากกระดาษที่ตรวจแล้ว — นี่คือหลักฐานจริง ไม่ใช่ความรู้สึกหลังสอบ",
        "",
        f"**คะแนน:** {a.score or 'ไม่ได้ระบุ'}",
        "",
        "**หัวข้อที่ผิด:**",
        *[f"- {t}" for t in topics],
    ]
    if a.note:
        lines += ["", f"**หมายเหตุ:** {a.note}"]
    lines += [
        "",
        "**ผลต่อการสร้างบทเรียนครั้งหน้า:** หัวข้อข้างบนถูกถ่วงน้ำหนักอัตโนมัติ",
        "โดย `results.py weak` ตอนสร้างชุดถัดไปของวิชานี้ ไม่ต้องสั่งเพิ่ม",
        "",
    ]
    md.write_text("\n".join(lines), encoding="utf-8")

    print(f"บันทึกแล้ว → {md.relative_to(BASE)}")
    print(f"หัวข้อที่ผิด: {', '.join(topics)}")
    hits = Counter()
    for e in read_all(a.subject):
        hits.update(e["wrong"])
    repeats = [t for t, c in hits.items() if c > 1 and t in topics]
    if repeats:
        print(f"\n⚠ ผิดซ้ำ: {', '.join(repeats)} — เคยพลาดมาก่อนแล้ว")
    return 0


def read_all(subject: str | None) -> list[dict]:
    subs = [subject] if subject else list(SUBJECTS)
    out = []
    for s in subs:
        f = workspace(s) / "results.jsonl"
        if not f.exists():
            continue
        for line in f.read_text(encoding="utf-8").splitlines():
            if line.strip():
                out.append(json.loads(line))
    return out


def cmd_weak(a) -> int:
    entries = read_all(a.subject)
    if not entries:
        where = a.subject or "any subject"
        print(f"ยังไม่มีผลสอบที่บันทึกไว้สำหรับ {where}.")
        print("สร้างบทเรียนตามลำดับ high-yield ตามปกติ — ยังไม่มีหลักฐานให้ถ่วงน้ำหนัก")
        return 0

    hits = Counter()
    recent = {}
    for e in entries:
        for t in e["wrong"]:
            hits[t] += 1
            recent[t] = max(recent.get(t, ""), e["date"])

    print(f"จุดอ่อนจาก {len(entries)} ครั้งที่บันทึกไว้:")
    for topic, n in hits.most_common():
        flag = "  ← ผิดซ้ำ" if n > 1 else ""
        print(f"  {n}×  {topic}   (ล่าสุด {recent[topic]}){flag}")

    focus = [t for t, n in hits.most_common() if n > 1] or [t for t, _ in hits.most_common(3)]
    print("\nถ่วงน้ำหนักบทเรียนชุดหน้าไปที่: " + ", ".join(focus))
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("add", help="record a graded paper")
    p.add_argument("--subject", required=True)
    p.add_argument("--chapter", default="")
    p.add_argument("--wrong", required=True, help='comma separated, e.g. "ICE table, Kp/Kc"')
    p.add_argument("--score", default="")
    p.add_argument("--note", default="")
    p.add_argument("--date", default="")
    p.set_defaults(fn=cmd_add)

    p = sub.add_parser("weak", help="what the next build should weight toward")
    p.add_argument("--subject", default="")
    p.set_defaults(fn=cmd_weak)

    a = ap.parse_args()
    if getattr(a, "subject", "") == "":
        a.subject = None if a.cmd == "weak" else a.subject
    return a.fn(a)


if __name__ == "__main__":
    raise SystemExit(main())
