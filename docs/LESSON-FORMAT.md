# LESSON-FORMAT — โครงหน้า HTML

## โครงเปล่า

```html
<!doctype html>
<html lang="th"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>บทที่ 4 — ตาราง ICE</title>
<link rel="stylesheet" href="../assets/lesson.css">
<script src="../assets/quiz.js" defer></script>
</head><body><div class="wrap">

<div class="eyebrow">สมดุลเคมี · บทเรียนที่ 4</div>
<h1>ตาราง ICE</h1>
<p class="deck">หนึ่งประโยคว่าบทนี้ปลดล็อกอะไร</p>
<div class="meta">
  <span class="tag">ชีทหน้า 10–12</span><span class="tag">ตย. 9.17–9.19</span>
  <span class="tag">~18 นาที</span>
</div>

<div class="copy"><span class="copy-head">คัดลงสมุด</span>
  … 5–8 บรรทัดที่คุ้มค่าที่สุด …
</div>

… คำอธิบาย ตัวอย่างที่ทำให้ดู ควิซ …

<div class="nav"><a href="0003-k-algebra.html">← บทก่อน</a>
                 <a href="0005-kp-kc.html">บทถัดไป →</a></div>
</div></body></html>
```

`build.py` จะเปลี่ยน `<link>`/`<script>` เป็นบล็อกที่ฝังไว้ให้เอง — เขียนแบบข้างบนได้เลย
**ห้ามแก้ `<style>`/`<script>` ที่ถูกฝังในหน้าโดยตรง** จะโดนเขียนทับ

## บล็อก "คัดลงสมุด" (บังคับทุกบท)

ผู้เรียนลอกลง GoodNotes ด้วยมือแล้วไม่กลับมาเปิด HTML อีก บล็อกนี้คือสิ่งเดียว
ที่จะอยู่กับเขาในห้องสอบ ใส่เฉพาะ:
- สูตรหรือขั้นตอนที่ต้องใช้จริง
- กับดักของบทนี้ พูดเป็นประโยคเดียว
- ตัวเลข/เงื่อนไขที่ลืมแล้วทำไม่ได้

ห้ามใส่: นิยามยาว ๆ · ที่มาของสูตร · อะไรที่ค้นได้ตอนอ่านทวน

## คลาสที่มีให้ใช้

| คลาส | ใช้เมื่อ |
|---|---|
| `.copy` `.copy-head` | บล็อกคัดลงสมุด |
| `.bigidea` | ไอเดียแกนกลางของบท กล่องเดียวต่อบท |
| `.worked` `.step` | ตัวอย่างที่ทำให้ดูทีละขั้น |
| `.ice` | ตาราง ICE |
| `.formula` `.frac` `.eq` | สูตรและเศษส่วน |
| `.callout` | ข้อควรระวัง / กับดัก |
| `.meta` `.tag` | แถบอ้างอิงหน้าในชีท |
| `.ask` | คำถามให้คิดต่อ ท้ายบท |
| `.score` | แถบคะแนนรวมของหน้า (ใส่หนึ่งอันท้ายหน้าที่มีควิซ) |

## ควิซสามแบบ

```html
<!-- เลือกตอบ — ตัวเลือกถูกสลับตอนโหลด ห้ามอ้างถึง "ตัวเลือก A" ในคำอธิบาย -->
<div class="quiz" data-answer="B" data-tag="ตาราง ICE">
  <div class="qtext">…</div>
  <div class="opts">
    <button class="opt" data-k="A">…</button>
    <button class="opt" data-k="B">…</button>
  </div>
  <div class="fb" hidden data-ok="ทำไมถูก" data-no="ทำไมผิด — อธิบายวิธีคิด ไม่ใช่บอกเฉลย"></div>
</div>

<!-- เติมคำตอบ — ตัวเลขเทียบด้วย tolerance 2% -->
<div class="quiz" data-type="fib" data-answer="0.44" data-unit="M" data-tag="ICE">…</div>

<!-- แบบฝึกหัดของครู — ใบ้ก่อน เฉลยทีหลัง ไม่นับคะแนน -->
<div class="quiz" data-type="reveal" data-hint="เริ่มจากนับ Δn ก่อน"
     data-tag="Kp-Kc">
  <div class="qtext">แบบฝึกหัด 9.3 ข้อ 11</div>
  <div class="fb" hidden data-ok="… วิธีทำครบทุกขั้น …"></div>
</div>
```

`data-tag` ทำให้ข้อที่ผิดถูกจัดกลุ่มตอนจบหน้า — คะแนนกลายเป็นแผนอ่านหนังสือ
ใส่ทุกข้อ

`data-shuffle="off"` เมื่อตัวเลือกเป็นลำดับจริง ๆ (ขั้นที่ 1–4, ค่าเรียงจากน้อยไปมาก)
