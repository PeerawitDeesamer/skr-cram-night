/* ============================================================
   quiz.js — shared retrieval-practice widget for every SKR subject.

   One file, two APIs. The declarative one is what new lessons use;
   the imperative one exists so the older Biology pages keep working.

   ------------------------------------------------------------
   DECLARATIVE (preferred — Claude writes plain HTML, no JS array)
   ------------------------------------------------------------

   MULTIPLE CHOICE — options are shuffled on load, then re-lettered
   top-to-bottom, so position never leaks the answer. Never refer to
   an option by its letter in the feedback text.
     <div class="quiz" data-answer="B" data-tag="ตาราง ICE">
       <div class="qtext">…</div>
       <div class="opts">
         <button class="opt" data-k="A">…</button>
         <button class="opt" data-k="B">…</button>
       </div>
       <div class="fb" hidden data-ok="…ทำไมถูก…" data-no="…ทำไมผิด…"></div>
     </div>
   Add data-shuffle="off" to keep the authored order (rare — only when
   the options are a sequence, e.g. steps 1-4 or increasing values).

   FILL IN — numeric answers compare with 2% tolerance by default
     <div class="quiz" data-type="fib" data-answer="0.44" data-tol="0.02" data-unit="M">
   Accept several spellings with |  →  data-answer="ไปข้างหน้า|ขวา|forward"

   REVEAL — self-marked, never scored. This is the one used for the
   teacher's own แบบฝึกหัด: hint first, full solution second.
     <div class="quiz" data-type="reveal" data-hint="…นึกถึง Δn ก่อน…">
       <div class="qtext">แบบฝึกหัด 9.3 ข้อ 11</div>
       <div class="fb" hidden data-ok="…the worked solution…"></div>
     </div>
   data-hint is optional; when present the learner gets one nudge
   before the solution button appears.

   ------------------------------------------------------------
   IMPERATIVE (legacy — Biology lessons 0001-0006)
   ------------------------------------------------------------
     renderQuiz(el, [{ q, opts:[…], a:index, why, tag }])

   Both APIs report missed questions grouped BY TAG at the end, so a
   score turns into a study plan instead of just a number.
   ============================================================ */
(function (global) {
  'use strict';

  var LBL = { mc: 'เลือกคำตอบ', fib: 'เติมคำตอบ', reveal: 'ลองทำก่อนกดดู' };
  var total = 0, right = 0, done = 0, missed = [];

  function shuffled(n) {
    var idx = Array.from({ length: n }, function (_, i) { return i; });
    for (var i = n - 1; i > 0; i--) {
      var j = Math.floor(Math.random() * (i + 1));
      var t = idx[i]; idx[i] = idx[j]; idx[j] = t;
    }
    return idx;
  }

  /* --- normalise Thai/EN free text for comparison --- */
  function norm(s) {
    return String(s).trim().toLowerCase()
      .replace(/\s+/g, '')
      .replace(/[.,;:!?"'()\[\]]/g, '')
      .replace(/^ทาง/, '').replace(/^ด้าน/, '');
  }

  /* --- "3.7e-8", "3.7 x 10^-8", "3.7×10-8" → Number --- */
  function toNum(s) {
    var t = String(s).trim().replace(/,/g, '').replace(/\s/g, '');
    var m = t.match(/^([+-]?\d*\.?\d+)[x×*]10\^?([+-]?\d+)$/i);
    if (m) return parseFloat(m[1]) * Math.pow(10, parseInt(m[2], 10));
    var n = parseFloat(t);
    return isNaN(n) ? null : n;
  }

  function matches(given, key, tol) {
    var keys = key.split('|');
    for (var i = 0; i < keys.length; i++) {
      var k = keys[i].trim();
      var kn = toNum(k), gn = toNum(given);
      if (kn !== null && gn !== null) {
        if (kn === 0 ? Math.abs(gn) < 1e-12 : Math.abs(gn - kn) / Math.abs(kn) <= tol) return true;
      } else if (norm(given) === norm(k)) return true;
    }
    return false;
  }

  function showFB(fb, ok) {
    if (!fb) return;
    var msg = ok ? (fb.dataset.ok || '') : (fb.dataset.no || fb.dataset.ok || '');
    fb.className = 'fb ' + (ok ? 'ok' : 'no');
    fb.innerHTML = '<div class="verdict">' +
      (ok ? '✓ ถูกต้อง' : '✗ ยังไม่ใช่') + '</div>' + msg;
    fb.hidden = false;
  }

  /* A wrong answer should name the topic to revisit, not just cost a point. */
  function weakList(items) {
    var byTag = {};
    items.forEach(function (m) { (byTag[m.tag] = byTag[m.tag] || []).push(m.n); });
    var tags = Object.keys(byTag);
    if (!tags.length) return '';
    return '<div class="weak"><span class="weak-head">จุดที่ควรกลับไปทวน</span><ul>' +
      tags.map(function (t) {
        return '<li><strong>' + t + '</strong> — ข้อ ' + byTag[t].join(', ') + '</li>';
      }).join('') + '</ul></div>';
  }

  function tally(ok, tag, n) {
    done++; if (ok) right++;
    if (!ok) missed.push({ n: n, tag: tag || 'ไม่ได้ระบุหัวข้อ' });
    var s = document.querySelector('.score');
    if (!s) return;
    var txt = s.querySelector('.txt'), bar = s.querySelector('.bar > i');
    if (txt) txt.textContent = right + ' / ' + total;
    if (bar) bar.style.width = (done / total * 100) + '%';
    var note = s.querySelector('.note');
    if (note && done === total) {
      note.textContent = right === total ? 'เต็ม — ไปบทถัดไปได้'
        : right / total >= 0.7 ? 'ผ่าน — ทวนข้อที่ผิดอีกรอบ'
        : 'ยังไม่แน่น — อ่านหัวข้อด้านบนซ้ำแล้วรีเฟรชหน้า';
      if (missed.length) s.insertAdjacentHTML('beforeend', weakList(missed));
    }
  }

  function initMC(q, n) {
    var key = q.dataset.answer, fb = q.querySelector('.fb');
    var box = q.querySelector('.opts');
    var opts = [].slice.call(q.querySelectorAll('.opt'));

    // Freeze each button's authored key before touching the DOM order.
    opts.forEach(function (b, i) {
      if (!b.dataset.k) b.dataset.k = String.fromCharCode(65 + i);
    });
    if (box && q.dataset.shuffle !== 'off') {
      shuffled(opts.length).forEach(function (i) { box.appendChild(opts[i]); });
      opts = [].slice.call(q.querySelectorAll('.opt'));
    }
    // Re-letter by final position so the page still reads A, B, C, D downward.
    opts.forEach(function (b, i) {
      var mk = b.querySelector('.mk');
      if (!mk) {
        mk = document.createElement('span');
        mk.className = 'mk';
        b.insertBefore(mk, b.firstChild);
      }
      mk.textContent = String.fromCharCode(65 + i) + '.';
      b.addEventListener('click', function () {
        if (q.dataset.locked) return;
        q.dataset.locked = '1';
        var ok = b.dataset.k === key;
        opts.forEach(function (o) {
          o.disabled = true;
          if (o.dataset.k === key) o.classList.add('correct');
          else if (o === b) o.classList.add('wrong');
          else o.classList.add('dim');
        });
        showFB(fb, ok); tally(ok, q.dataset.tag, n);
      });
    });
  }

  function initFIB(q, n) {
    var key = q.dataset.answer, tol = parseFloat(q.dataset.tol || '0.02');
    var fb = q.querySelector('.fb');
    var row = document.createElement('div');
    row.className = 'fibrow';
    var inp = document.createElement('input');
    inp.type = 'text';
    inp.setAttribute('aria-label', 'คำตอบ');
    inp.placeholder = q.dataset.ph || 'พิมพ์คำตอบ';
    var btn = document.createElement('button');
    btn.className = 'btn'; btn.textContent = 'ตรวจ';
    row.appendChild(inp);
    if (q.dataset.unit) {
      var u = document.createElement('span');
      u.className = 'unit'; u.textContent = q.dataset.unit;
      row.appendChild(u);
    }
    row.appendChild(btn);
    q.insertBefore(row, fb || null);

    function check() {
      if (q.dataset.locked || !inp.value.trim()) return;
      q.dataset.locked = '1';
      var ok = matches(inp.value, key, tol);
      inp.classList.add(ok ? 'correct' : 'wrong');
      inp.disabled = true; btn.disabled = true; btn.style.display = 'none';
      if (!ok) {
        var a = document.createElement('span');
        a.className = 'unit';
        a.innerHTML = '→ เฉลย <strong>' + key.split('|')[0] + '</strong>';
        row.appendChild(a);
      }
      showFB(fb, ok); tally(ok, q.dataset.tag, n);
    }
    btn.addEventListener('click', check);
    inp.addEventListener('keydown', function (e) { if (e.key === 'Enter') check(); });
  }

  /* Reveal is deliberately unscored: it is where you are honest with
     yourself about the teacher's own exercises. A hint, if the lesson
     supplies one, always comes before the solution. */
  function initReveal(q) {
    var fb = q.querySelector('.fb');
    var row = document.createElement('div');
    row.className = 'fibrow';

    var hintBtn = null;
    if (q.dataset.hint) {
      hintBtn = document.createElement('button');
      hintBtn.className = 'btn ghost'; hintBtn.textContent = 'ขอใบ้';
      row.appendChild(hintBtn);
    }
    var sol = document.createElement('button');
    sol.className = 'btn'; sol.textContent = 'ทำแล้ว — ดูเฉลย';
    row.appendChild(sol);
    q.insertBefore(row, fb || null);

    if (hintBtn) {
      hintBtn.addEventListener('click', function () {
        hintBtn.disabled = true;
        var h = document.createElement('div');
        h.className = 'hint';
        h.innerHTML = '<span class="hint-head">ใบ้</span>' + q.dataset.hint;
        q.insertBefore(h, row);
      });
    }
    sol.addEventListener('click', function () {
      if (q.dataset.locked) return;
      q.dataset.locked = '1';
      row.style.display = 'none';
      showFB(fb, true);
      var v = fb && fb.querySelector('.verdict');
      if (v) v.textContent = '⟡ เฉลย';
    });
  }

  document.addEventListener('DOMContentLoaded', function () {
    // [data-quiz] marks a container the legacy renderQuiz() will fill in and
    // own; the declarative engine must not touch it or both will fight for
    // the same element.
    var qs = [].slice.call(document.querySelectorAll('.quiz:not([data-quiz])'));
    qs.forEach(function (q, i) {
      var t = q.dataset.type || 'mc';
      if (t !== 'reveal') total++;
      if (!q.querySelector('.qlbl')) {
        var l = document.createElement('div');
        l.className = 'qlbl';
        l.textContent = (LBL[t] || LBL.mc) + (q.dataset.tag ? ' · ' + q.dataset.tag : '');
        q.insertBefore(l, q.firstChild);
      }
      if (t === 'fib') initFIB(q, i + 1);
      else if (t === 'reveal') initReveal(q);
      else initMC(q, i + 1);
    });
    var s = document.querySelector('.score');
    if (s && total) {
      s.innerHTML = '<span class="note">ตอบให้ครบเพื่อดูผล</span>' +
        '<span class="bar"><i></i></span><span class="txt">0 / ' + total + '</span>';
    } else if (s) { s.remove(); }
  });

  /* ---------------------------------------------------------
     Legacy imperative API — one question at a time, shuffled.
     Kept verbatim in behaviour so Biology 0001-0006 are untouched.
     --------------------------------------------------------- */
  function renderQuiz(root, items, opts) {
    opts = opts || {};
    var label = opts.label || 'Retrieval practice';
    root.classList.add('q-legacy');
    var state;

    function reset() { state = { i: 0, correct: 0, missed: [] }; }

    function draw() {
      var item = items[state.i];
      root.innerHTML = '';

      var head = document.createElement('div');
      head.className = 'qhead';
      head.innerHTML = '<span>' + (item.tag || label) + '</span><span>' +
        (state.i + 1) + ' / ' + items.length + '</span>';
      root.appendChild(head);

      var q = document.createElement('div');
      q.className = 'qtext';
      q.innerHTML = item.q;
      root.appendChild(q);

      var wrap = document.createElement('div');
      wrap.className = 'opts';
      root.appendChild(wrap);

      var fb = document.createElement('div');
      fb.className = 'fb hidden';
      root.appendChild(fb);

      var buttons = [];
      shuffled(item.opts.length).forEach(function (origIndex) {
        var b = document.createElement('button');
        b.type = 'button';
        b.className = 'opt';
        b.innerHTML = item.opts[origIndex];
        b.addEventListener('click', function () { choose(origIndex); });
        wrap.appendChild(b);
        buttons.push({ btn: b, orig: origIndex });
      });

      function choose(picked) {
        var isRight = picked === item.a;
        if (isRight) state.correct++;
        else state.missed.push({ n: state.i + 1, tag: item.tag || label });

        buttons.forEach(function (o) {
          o.btn.disabled = true;
          if (o.orig === item.a) o.btn.classList.add('correct');
          else if (o.orig === picked) o.btn.classList.add('wrong');
          else o.btn.classList.add('dimmed');
        });

        fb.className = 'fb ' + (isRight ? 'ok' : 'no');
        fb.innerHTML = '<span class="verdict">' +
          (isRight ? '✓ ถูกต้อง' : '✗ ยังไม่ใช่') + '</span>' + item.why;

        var next = document.createElement('button');
        next.className = 'retry';
        next.textContent = state.i < items.length - 1 ? 'next →' : 'see score';
        next.addEventListener('click', function () {
          if (state.i < items.length - 1) { state.i++; draw(); } else { finish(); }
        });
        fb.appendChild(document.createElement('br'));
        fb.appendChild(next);
      }
    }

    function finish() {
      root.innerHTML = '';
      var pct = Math.round((state.correct / items.length) * 100);
      var s = document.createElement('div');
      s.className = 'score';
      var verdict = pct === 100 ? 'แม่นทุกข้อ — พร้อมสอบ'
        : pct >= 80 ? 'ดีมาก — ทวนเฉพาะจุดที่พลาด'
        : pct >= 60 ? 'พอใช้ — ยังมีจุดที่ต้องกลับไปอ่าน'
        : 'ยังไม่แน่น — กลับไปอ่านบทที่พลาดแล้วลองใหม่';
      s.innerHTML = 'คะแนน: <strong>' + state.correct + ' / ' + items.length +
        '</strong> (' + pct + '%) — ' + verdict + weakList(state.missed);

      var again = document.createElement('button');
      again.className = 'retry';
      again.textContent = 'try again';
      again.addEventListener('click', function () { reset(); draw(); });
      s.appendChild(again);
      root.appendChild(s);
    }

    reset();
    draw();
  }

  global.renderQuiz = renderQuiz;
})(window);
