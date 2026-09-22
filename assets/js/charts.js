/* ==========================================================================
   NEO Golf Data — inline SVG chart components
   No external chart library. Each component takes (mountEl, data) and is
   re-renderable, so a real DB payload can replace the dummy one as-is.
   ========================================================================== */

(function (global) {
  "use strict";

  const NS = "http://www.w3.org/2000/svg";
  const el = (n, a) => { const e = document.createElementNS(NS, n); for (const k in a) e.setAttribute(k, a[k]); return e; };
  const S = (i) => "var(--series-" + i + ")";

  /* ---------- shared tooltip ---------------------------------------------- */
  let tip;
  function tipEl() {
    if (!tip) { tip = document.createElement("div"); tip.className = "neo-tip"; document.body.appendChild(tip); }
    return tip;
  }
  function bindTip(node, html) {
    node.addEventListener("mouseenter", function () { const t = tipEl(); t.innerHTML = html; t.classList.add("is-on"); node.classList.add("is-on"); });
    node.addEventListener("mousemove", function (e) { const t = tipEl(); t.style.left = e.clientX + "px"; t.style.top = e.clientY - 8 + "px"; });
    node.addEventListener("mouseleave", function () { tipEl().classList.remove("is-on"); node.classList.remove("is-on"); });
    node.setAttribute("tabindex", "0");
    node.addEventListener("focus", function () { const t = tipEl(); const r = node.getBoundingClientRect(); t.innerHTML = html; t.classList.add("is-on"); t.style.left = (r.left + r.width / 2) + "px"; t.style.top = r.top + "px"; });
    node.addEventListener("blur", function () { tipEl().classList.remove("is-on"); });
  }

  /* Charts are drawn at the container's real pixel width so type never scales.
     Re-renders (debounced) when the layout width changes. */
  function responsive(mount, draw, min, max) {
    if (!mount) return;
    let last = 0;
    function run() {
      const w = Math.max(min || 240, Math.min(max || 720, Math.round(mount.clientWidth || 320)));
      if (w === last) return;
      last = w;
      draw(mount, w);
    }
    run();
    let t;
    window.addEventListener("resize", function () { clearTimeout(t); t = setTimeout(run, 120); });
  }

  function svg(mount, w, h, label) {
    mount.innerHTML = "";
    const s = el("svg", {
      class: "chart", viewBox: "0 0 " + w + " " + h, width: w, height: h,
      role: "img", "aria-label": label, preserveAspectRatio: "xMidYMid meet"
    });
    mount.appendChild(s);
    return s;
  }

  /* ---------- 1. Driver carry distribution (histogram) -------------------- */
  function driverDistribution(mount, d, width) {
    const W = width || 320, H = 186, padL = 6, padR = 6, padT = 26, padB = 26;
    const s = svg(mount, W, H, "드라이버 캐리 거리 분포 히스토그램");
    let bins = d.bins;
    const first = bins.findIndex((b) => b.count > 0);
    let last = bins.length - 1;
    while (last > 0 && !bins[last].count) last--;
    bins = bins.slice(Math.max(0, first - 1), Math.min(bins.length, last + 2));
    const max = Math.max.apply(null, bins.map((b) => b.count)) || 1;
    const iw = W - padL - padR, bw = iw / bins.length;
    const x = (i) => padL + i * bw;
    const y = (v) => padT + (H - padT - padB) * (1 - v / max);

    s.appendChild(el("line", { class: "grid-line", x1: padL, x2: W - padR, y1: H - padB, y2: H - padB }));

    bins.forEach(function (b, i) {
      if (!b.count) return;
      const hgt = (H - padT - padB) - (y(b.count) - padT);
      const g = el("g", { class: "mark" });
      g.appendChild(el("rect", {
        x: x(i) + 1, y: y(b.count), width: Math.max(1, bw - 2), height: Math.max(2, hgt),
        rx: 4, fill: S(1), "fill-opacity": b.from <= d.median && d.median < b.to ? 1 : 0.72
      }));
      bindTip(g, "<b>" + b.from + "–" + b.to + "m</b><span>" + b.count + "샷 · 전체의 " + Math.round(b.count / d.shots * 100) + "%</span>");
      s.appendChild(g);
    });

    // median reference line — the one number the reader takes away
    const mi = (d.median - bins[0].from) / (bins[0].to - bins[0].from);
    const mx = padL + mi * bw;
    s.appendChild(el("line", { class: "ref-line", x1: mx, x2: mx, y1: padT - 12, y2: H - padB }));
    const lab = el("text", { class: "value-label", x: Math.min(mx + 6, W - 58), y: padT - 14, fill: "var(--neo-ink)" });
    lab.textContent = "중앙값 " + d.median + "m";
    s.appendChild(lab);

    [[bins[0].from, padL + 2, "start"], [bins[bins.length - 1].to, W - padR - 2, "end"]].forEach(function (t) {
      const n = el("text", { class: "axis-label", x: t[1], y: H - padB + 14, "text-anchor": t[2] });
      n.textContent = t[0] + "m"; s.appendChild(n);
    });
    const n2 = el("text", { class: "axis-label", x: W / 2, y: H - 4, "text-anchor": "middle" });
    n2.textContent = "10%–90% 구간 " + d.p10 + "–" + d.p90 + "m";
    s.appendChild(n2);
  }

  /* ---------- 2. Approach proximity by distance band ---------------------- */
  function approachDistribution(mount, rows, width) {
    const W = width || 320, rowH = 34, padT = 14, padL = 62, padR = 46, padB = 22;
    const H = padT + rows.length * rowH + padB;
    const s = svg(mount, W, H, "거리 구간별 그린 적중 근접도");
    const max = Math.max.apply(null, rows.map((r) => r.prox)) * 1.25;
    const iw = W - padL - padR;

    rows.forEach(function (r, i) {
      const y = padT + i * rowH;
      const t = el("text", { class: "axis-label", x: 0, y: y + 14, "text-anchor": "start" });
      t.textContent = r.band; s.appendChild(t);

      const g = el("g", { class: "mark" });
      g.appendChild(el("rect", { x: padL, y: y + 4, width: iw, height: 12, rx: 4, fill: "var(--neo-line)" }));
      g.appendChild(el("rect", { x: padL, y: y + 4, width: Math.max(4, iw * (r.prox / max)), height: 12, rx: 4, fill: S(2) }));
      const v = el("text", { class: "value-label", x: W - padR + 6, y: y + 14 });
      v.textContent = r.prox + "m"; g.appendChild(v);
      const sub = el("text", { class: "axis-label", x: padL, y: y + 28 });
      sub.textContent = r.shots + "샷 · GIR " + r.gir + "% · 3m 이내 " + r.inside3 + "%";
      g.appendChild(sub);
      bindTip(g, "<b>" + r.band + " · 평균 " + r.prox + "m</b><span>" + r.shots + "샷 · 그린 적중 " + r.gir + "% · 3m 이내 " + r.inside3 + "%</span>");
      s.appendChild(g);
    });

    const f = el("text", { class: "axis-label", x: 0, y: H - 6 });
    f.textContent = "막대 = 홀컵까지 평균 남은 거리 (짧을수록 좋음)";
    s.appendChild(f);
  }

  /* ---------- 3. Landing distribution (tee-shot dispersion) --------------- */
  function landingDistribution(mount, d, width) {
    const W = width || 320, H = Math.max(220, Math.min(320, Math.round(W * 0.68))), padT = 18, padB = 30, cx = W / 2;
    const s = svg(mount, W, H, "티샷 낙하 지점 분포");
    const pts = d.points;
    const ys = pts.map((p) => p.y), xs = pts.map((p) => Math.abs(p.x));
    const yMin = Math.min.apply(null, ys) - 6, yMax = Math.max.apply(null, ys) + 6;
    const span = Math.max(32, Math.max.apply(null, xs) + 6);
    const sx = (v) => cx + (v / span) * (W / 2 - 16);
    const sy = (v) => H - padB - ((v - yMin) / (yMax - yMin)) * (H - padT - padB);

    // fairway corridor
    const fwHalf = d.fairwayWidth / 2;
    s.appendChild(el("rect", {
      x: sx(-fwHalf), y: padT, width: sx(fwHalf) - sx(-fwHalf), height: H - padT - padB,
      rx: 8, fill: S(1), "fill-opacity": .09, stroke: S(1), "stroke-opacity": .28, "stroke-width": 1
    }));
    s.appendChild(el("line", { class: "ref-line", x1: cx, x2: cx, y1: padT, y2: H - padB }));

    const styleOf = {
      FAIRWAY: { fill: S(1), shape: "circle" },
      ROUGH: { fill: S(2), shape: "ring" },
      BUNKER: { fill: S(3), shape: "diamond" }
    };
    pts.forEach(function (p) {
      const st = styleOf[p.result], X = sx(p.x), Y = sy(p.y);
      const g = el("g", { class: "mark" });
      if (st.shape === "diamond") {
        g.appendChild(el("path", { d: "M" + X + " " + (Y - 5) + "L" + (X + 5) + " " + Y + "L" + X + " " + (Y + 5) + "L" + (X - 5) + " " + Y + "Z", fill: st.fill, stroke: "var(--neo-surface-2)", "stroke-width": 2 }));
      } else if (st.shape === "ring") {
        g.appendChild(el("circle", { cx: X, cy: Y, r: 4, fill: "none", stroke: st.fill, "stroke-width": 2 }));
      } else {
        g.appendChild(el("circle", { cx: X, cy: Y, r: 4.5, fill: st.fill, stroke: "var(--neo-surface-2)", "stroke-width": 2 }));
      }
      bindTip(g, "<b>" + p.y.toFixed(0) + "m · " + (p.x < 0 ? "좌 " : "우 ") + Math.abs(p.x).toFixed(1) + "m</b><span>" + p.result + " · " + p.hole + "번 홀</span>");
      s.appendChild(g);
    });

    [[Math.round(yMax - 6), padT + 4], [Math.round(yMin + 6), H - padB - 8]].forEach(function (t) {
      const n = el("text", { class: "axis-label", x: 4, y: t[1] });
      n.textContent = t[0] + "m"; s.appendChild(n);
    });

    [["좌", 4, "start"], ["우", W - 4, "end"]].forEach(function (t) {
      const n = el("text", { class: "axis-label", x: t[1], y: H - padB + 14, "text-anchor": t[2] });
      n.textContent = t[0]; s.appendChild(n);
    });
    const c = el("text", { class: "value-label", x: cx, y: H - padB + 14, "text-anchor": "middle", fill: "var(--neo-ink)" });
    c.textContent = "페어웨이 적중 " + d.fairwayHit + "%";
    s.appendChild(c);
    const bias = el("text", { class: "axis-label", x: cx, y: H - 6, "text-anchor": "middle" });
    bias.textContent = "미스 성향 " + (d.missBias < 0 ? "좌측" : "우측") + " 평균 " + Math.abs(d.missBias).toFixed(1) + "m";
    s.appendChild(bias);
  }

  /* ---------- 4. Evolution sparkline -------------------------------------- */
  function sparkline(mount, series, seriesIndex, width) {
    const W = width || 340, H = 46, pad = 6;
    const s = svg(mount, W, H, "최근 5경기 추이");
    const min = Math.min.apply(null, series), max = Math.max.apply(null, series);
    const rng = (max - min) || 1;
    const sx = (i) => pad + (i / (series.length - 1)) * (W - pad * 2);
    const sy = (v) => H - pad - ((v - min) / rng) * (H - pad * 2);
    const dAttr = series.map((v, i) => (i ? "L" : "M") + sx(i) + " " + sy(v)).join(" ");

    s.appendChild(el("path", {
      d: dAttr + "L" + sx(series.length - 1) + " " + (H - pad) + "L" + sx(0) + " " + (H - pad) + "Z",
      fill: S(seriesIndex), "fill-opacity": .12
    }));
    s.appendChild(el("path", { d: dAttr, fill: "none", stroke: S(seriesIndex), "stroke-width": 2, "stroke-linecap": "round", "stroke-linejoin": "round" }));
    series.forEach(function (v, i) {
      const g = el("g", { class: "mark" });
      const last = i === series.length - 1;
      g.appendChild(el("circle", {
        cx: sx(i), cy: sy(v), r: last ? 4.5 : 3.2,
        fill: last ? S(seriesIndex) : "var(--neo-surface-2)",
        stroke: S(seriesIndex), "stroke-width": 2
      }));
      bindTip(g, "<b>" + v + "</b><span>" + (series.length - i) + "경기 전</span>");
      s.appendChild(g);
    });
  }

  global.NEOChart = {
    responsive: responsive,
    driverDistribution: driverDistribution,
    approachDistribution: approachDistribution,
    landingDistribution: landingDistribution,
    sparkline: sparkline
  };
})(window);
