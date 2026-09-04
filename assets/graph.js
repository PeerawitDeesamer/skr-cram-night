/* ============================================================
   graph.js — concentration–time plots for สมดุลเคมี lessons
   Renders an inline SVG (theme-safe, print-safe, no library).

   <figure class="cgraph"
           data-series='[{"label":"A","from":1.0,"to":0.40},
                         {"label":"B","from":0,"to":0.60}]'
           data-teq="0.55"            <!-- fraction of x-axis where eq is reached -->
           data-ymax="1.2"
           data-ylab="ความเข้มข้น (M)"
           data-xlab="เวลา">
     <figcaption>…</figcaption>
   </figure>

   Optional per-series: "flat":true  (draws a horizontal line — solids)
                        "dash":true
   ============================================================ */
(function () {
  'use strict';
  var COLORS = ['#8a2f1e', '#1f6f5c', '#2b5c8a', '#a8621c', '#6b4d8f'];
  var NS = 'http://www.w3.org/2000/svg';

  function el(n, a) {
    var e = document.createElementNS(NS, n);
    for (var k in a) if (a[k] != null) e.setAttribute(k, a[k]);
    return e;
  }

  function draw(fig) {
    var series;
    try { series = JSON.parse(fig.dataset.series); }
    catch (err) { return; }
    if (!series || !series.length) return;

    var W = 560, H = 300, P = { t: 18, r: 74, b: 46, l: 52 };
    var iw = W - P.l - P.r, ih = H - P.t - P.b;
    var teq = parseFloat(fig.dataset.teq || '0.55');
    var ymax = parseFloat(fig.dataset.ymax ||
      String(Math.max.apply(null, series.map(function (s) {
        return Math.max(s.from, s.to);
      })) * 1.25));

    var X = function (f) { return P.l + f * iw; };
    var Y = function (v) { return P.t + ih - (v / ymax) * ih; };

    var svg = el('svg', {
      viewBox: '0 0 ' + W + ' ' + H, width: '100%',
      role: 'img', 'aria-label': fig.dataset.alt || 'กราฟความเข้มข้นกับเวลา'
    });

    /* y gridlines */
    for (var i = 0; i <= 4; i++) {
      var v = ymax * i / 4;
      svg.appendChild(el('line', {
        x1: P.l, x2: P.l + iw, y1: Y(v), y2: Y(v),
        stroke: '#e0dcd2', 'stroke-width': 1
      }));
      var tk = el('text', {
        x: P.l - 8, y: Y(v) + 4, 'text-anchor': 'end',
        'font-size': 11, fill: '#8a8680', 'font-family': 'IBM Plex Mono, monospace'
      });
      tk.textContent = v.toFixed(ymax < 2 ? 1 : 0);
      svg.appendChild(tk);
    }

    /* equilibrium marker */
    svg.appendChild(el('line', {
      x1: X(teq), x2: X(teq), y1: P.t, y2: P.t + ih,
      stroke: '#8a8680', 'stroke-width': 1, 'stroke-dasharray': '3 3'
    }));
    var eqt = el('text', {
      x: X(teq), y: P.t + ih + 30, 'text-anchor': 'middle',
      'font-size': 11, fill: '#8a8680', 'font-family': 'Sarabun, sans-serif'
    });
    eqt.textContent = 'เข้าสมดุล';
    svg.appendChild(eqt);

    /* axes */
    svg.appendChild(el('line', { x1: P.l, x2: P.l, y1: P.t, y2: P.t + ih, stroke: '#1a1a18', 'stroke-width': 1.5 }));
    svg.appendChild(el('line', { x1: P.l, x2: P.l + iw, y1: P.t + ih, y2: P.t + ih, stroke: '#1a1a18', 'stroke-width': 1.5 }));

    /* curves: exponential approach, flat after teq */
    series.forEach(function (s, si) {
      var col = s.color || COLORS[si % COLORS.length];
      var d = '', N = 90;
      for (var j = 0; j <= N; j++) {
        var f = j / N, val;
        if (s.flat) val = s.from;
        else if (f >= teq) val = s.to;
        else val = s.to + (s.from - s.to) * Math.exp(-4.6 * (f / teq));
        d += (j ? 'L' : 'M') + X(f).toFixed(1) + ' ' + Y(val).toFixed(1) + ' ';
      }
      svg.appendChild(el('path', {
        d: d, fill: 'none', stroke: col, 'stroke-width': 2.4,
        'stroke-linecap': 'round', 'stroke-linejoin': 'round',
        'stroke-dasharray': s.dash ? '6 4' : null
      }));
      var yEnd = Y(s.flat ? s.from : s.to);
      var lab = el('text', {
        x: P.l + iw + 8, y: yEnd + 4, 'font-size': 12.5, fill: col,
        'font-weight': 600, 'font-family': 'IBM Plex Mono, monospace'
      });
      lab.textContent = s.label;
      svg.appendChild(lab);
    });

    /* axis labels */
    var xl = el('text', {
      x: P.l + iw / 2, y: H - 6, 'text-anchor': 'middle',
      'font-size': 12, fill: '#55524c', 'font-family': 'Sarabun, sans-serif'
    });
    xl.textContent = fig.dataset.xlab || 'เวลา';
    svg.appendChild(xl);
    var yl = el('text', {
      x: 14, y: P.t + ih / 2, 'text-anchor': 'middle',
      'font-size': 12, fill: '#55524c', 'font-family': 'Sarabun, sans-serif',
      transform: 'rotate(-90 14 ' + (P.t + ih / 2) + ')'
    });
    yl.textContent = fig.dataset.ylab || 'ความเข้มข้น (M)';
    svg.appendChild(yl);

    fig.insertBefore(svg, fig.firstChild);
  }

  document.addEventListener('DOMContentLoaded', function () {
    [].slice.call(document.querySelectorAll('.cgraph')).forEach(draw);
  });
})();
