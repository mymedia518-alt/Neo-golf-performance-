/* ==========================================================================
   NEO Golf Data — Player Intelligence page renderer
   Route: /player/{playerCode}   (fallback: /player.html?code={playerCode})
   Every section answers one question: "이 선수는 어떤 골프를 하는 선수인가?"
   ========================================================================== */

(function (global) {
  "use strict";

  const SERIES_OF = { Driver: 1, Iron: 2, Putting: 3, Recovery: 4, Pressure: 5 };
  const BETTER_LOWER = { Driver: false, Iron: true, Putting: true, Recovery: false, Pressure: true };

  function codeFromLocation() {
    const m = location.pathname.match(/\/player\/([^\/?#]+)/);
    if (m) return decodeURIComponent(m[1]);
    const q = new URLSearchParams(location.search).get("code");
    if (q) return q;
    return (location.hash || "").replace(/^#\/?/, "") || global.NEO.players[0].code;
  }

  const esc = (s) => String(s).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");

  /* ---------- SECTION 1 : Hero -------------------------------------------- */
  function hero(p) {
    const meta = [
      ["K-Ranking", "#" + p.kRank],
      ["NEO Ranking", "#" + p.neoRank],
      ["Recent Form", p.form],
      ["Tournament Entry", p.entry]
    ];
    return '<section class="card pi-hero" id="s-hero">' +
      '<span class="eyebrow">Player Intelligence</span>' +
      '<h1 class="pi-hero__name">' + esc(p.name) + "</h1>" +
      '<p class="pi-hero__tag">' + esc(p.tagline) + "</p>" +
      '<div class="pi-hero__meta">' +
        meta.map(function (m) {
          return '<div class="pi-meta"><div class="pi-meta__k">' + m[0] + '</div><div class="pi-meta__v">' + esc(m[1]) + "</div></div>";
        }).join("") +
      "</div></section>";
  }

  /* ---------- SECTION 2 : AI Insight -------------------------------------- */
  function insight(p) {
    return '<section class="card pi-insight" id="s-insight">' +
      '<div class="pi-insight__head"><span class="chip chip--accent">AI INSIGHT</span>' +
      '<span class="eyebrow">최근 5개 대회 기준</span></div>' +
      '<p class="pi-insight__body">' + p.insight.lead + "</p>" +
      '<p class="pi-insight__foot">' + esc(p.insight.body) + "</p>" +
      '<div class="pi-insight__tags">' +
        p.insight.tags.map(function (t) { return '<span class="chip">' + esc(t) + "</span>"; }).join("") +
      "</div></section>";
  }

  /* ---------- SECTION 3 : Player DNA -------------------------------------- */
  function dna(p) {
    return '<section class="card card--pad" id="s-dna">' +
      '<h2 class="section-title">Player DNA</h2>' +
      '<p class="section-sub">5개 축으로 본 경기 성향 · 0-100 (투어 상대값)</p>' +
      '<div class="dna-grid" style="margin-top:16px">' +
        p.dna.map(function (d, i) {
          return '<article class="dna-card" tabindex="0">' +
            '<div class="dna-card__k">' + esc(d.key) + "</div>" +
            '<div class="dna-card__v">' + d.value + "<small>/100</small></div>" +
            '<div class="dna-bar"><span style="width:' + d.value + "%;background:var(--series-" + ((i % 5) + 1) + ')"></span></div>' +
            '<div class="dna-card__rank">' + esc(d.rank) + "</div>" +
            '<div class="dna-card__note">' + esc(d.note) + "</div>" +
          "</article>";
        }).join("") +
      "</div></section>";
  }

  /* ---------- SECTION 4 : Shot DNA ---------------------------------------- */
  function shotDna(p) {
    return '<section class="card card--pad" id="s-shot">' +
      '<h2 class="section-title">Shot DNA</h2>' +
      '<p class="section-sub">샷 레벨 분포 · 프로토타입 더미 데이터 (DB 연결 시 동일 스키마로 교체)</p>' +
      '<div class="shot-grid" style="margin-top:16px">' +
        '<div class="shot-card"><h4>Driver Distribution</h4>' +
          '<p class="shot-card__sub">캐리 거리 ' + p.shot.driver.shots + "샷</p>" +
          '<div data-chart="driver"></div></div>' +
        '<div class="shot-card"><h4>Approach Distribution</h4>' +
          '<p class="shot-card__sub">거리 구간별 홀컵 근접도</p>' +
          '<div data-chart="approach"></div></div>' +
        '<div class="shot-card"><h4>Landing Distribution</h4>' +
          '<p class="shot-card__sub">티샷 낙하 지점 · 페어웨이 중앙 기준</p>' +
          '<div data-chart="landing"></div>' +
          '<div class="shot-legend">' +
            '<span><i style="background:var(--series-1)"></i>페어웨이</span>' +
            '<span><i style="background:var(--series-2)"></i>러프</span>' +
            '<span><i style="background:var(--series-3)"></i>벙커</span>' +
          "</div></div>" +
      "</div></section>";
  }

  /* ---------- SECTION 5 : Recent Evolution -------------------------------- */
  /* 화살표·부호 = 수치의 상승/하락, 색 = 경기력 개선/저하.
     Driver(거리)는 그 자체로 좋고 나쁨이 아니므로 중립으로 표시한다. */
  const NEUTRAL = { Driver: true };
  function trendOf(m) {
    const a = m.series[0], b = m.series[m.series.length - 1];
    const diff = b - a;
    const scale = Math.max(Math.abs(a), 1);
    const dirWord = diff > 0 ? "상승" : "하락";
    if (Math.abs(diff) / scale < 0.015) return { cls: "flat", arrow: "▬", text: "유지", diff: diff };
    if (NEUTRAL[m.key]) return { cls: "flat", arrow: diff > 0 ? "▲" : "▼", text: dirWord + " · 중립", diff: diff };
    const improved = BETTER_LOWER[m.key] ? diff < 0 : diff > 0;
    return {
      cls: improved ? "up" : "down",
      arrow: diff > 0 ? "▲" : "▼",
      text: dirWord + " · " + (improved ? "개선" : "저하"),
      diff: diff
    };
  }

  function evolution(p) {
    return '<section class="card card--pad" id="s-evo">' +
      '<h2 class="section-title">Recent Evolution</h2>' +
      '<p class="section-sub">최근 5개 대회 · 무엇이 달라졌는가 &nbsp;|&nbsp; 화살표 = 수치 상승/하락, 색 = 경기력 개선(초록)·저하(빨강)·중립(회색)</p>' +
      '<div class="evo-list" style="margin-top:16px">' +
        p.evolution.map(function (m, i) {
          const t = trendOf(m);
          const cur = m.series[m.series.length - 1];
          const sign = t.diff > 0 ? "+" : "";
          return '<div class="evo-row" data-evo="' + i + '">' +
            '<div class="evo-row__k"><i style="background:var(--series-' + SERIES_OF[m.key] + ')"></i>' + esc(m.key) + "</div>" +
            '<div class="evo-row__spark" data-spark="' + i + '"></div>' +
            '<div class="evo-row__val">' + cur + esc(m.unit) + "<small>" + esc(m.label) + "</small></div>" +
            '<div class="evo-row__delta"><span class="delta delta--' + t.cls + '">' + t.arrow + " " + sign +
              (Math.round(t.diff * 10) / 10) + esc(m.unit) + "</span><br>" +
              '<span class="delta delta--' + t.cls + '" style="font-weight:600">' + t.text + "</span></div>" +
            '<div class="evo-row__note">' + esc(m.note) + "</div>" +
          "</div>";
        }).join("") +
      "</div></section>";
  }

  /* ---------- SECTION 6 : Course Fit -------------------------------------- */
  function courseFit(p) {
    return '<section class="card card--pad" id="s-fit">' +
      '<h2 class="section-title">Course Fit</h2>' +
      '<p class="section-sub">' + esc(p.fit.course) + " · " + esc(p.fit.why) + "</p>" +
      '<div class="fit-wrap" style="margin-top:16px">' +
        '<div class="fit-score"><div><div class="fit-score__n">' + p.fit.score + "</div>" +
        '<div class="fit-score__l">Course Fit Score</div></div></div>' +
        '<div class="fit-cols">' +
          '<div class="fit-col fit-col--s"><h5>Strength</h5><ul>' +
            p.fit.strengths.map(function (s) {
              return "<li><span>+</span><span><b>" + esc(s.t) + "</b><br>" + esc(s.d) + "</span></li>";
            }).join("") +
          "</ul></div>" +
          '<div class="fit-col fit-col--w"><h5>Weakness</h5><ul>' +
            p.fit.weaknesses.map(function (s) {
              return "<li><span>−</span><span><b>" + esc(s.t) + "</b><br>" + esc(s.d) + "</span></li>";
            }).join("") +
          "</ul></div>" +
        "</div></div></section>";
  }

  /* ---------- SECTION 7 : Hole Library ------------------------------------ */
  function holeLibrary(p) {
    const qaCls = { GOOD: "good", OK: "ok", MISS: "bad" };
    return '<section class="card card--pad" id="s-holes">' +
      '<h2 class="section-title">Hole Library</h2>' +
      '<p class="section-sub">최근 샷 · 행을 클릭하면 홀 상세 분석으로 연결된다' +
      '<span class="hole-hint">좌우로 스크롤 →</span></p>' +
      '<div class="hole-scroll" style="margin-top:16px"><table class="neo-table">' +
        "<thead><tr><th>Round</th><th>Hole</th><th class=\"ta-r\">Carry</th><th class=\"ta-r\">Left Distance</th><th>Lie</th><th>QA</th></tr></thead><tbody>" +
        p.holes.map(function (h) {
          return '<tr class="hole-row" data-hole="' + h.id + '" tabindex="0" ' +
            'data-hole-href="/player/' + p.code + "/hole/" + h.id + '">' +
            '<td class="num">R' + h.round + "</td>" +
            "<td>" + h.hole + "번 <span style=\"color:var(--neo-ink-3)\">P" + h.par + "</span></td>" +
            '<td class="ta-r num">' + h.carry + "m</td>" +
            '<td class="ta-r num">' + h.left + "m</td>" +
            "<td>" + h.lie + "</td>" +
            '<td><span class="qa qa--' + qaCls[h.qa] + '">' + h.qa + "</span></td></tr>";
        }).join("") +
      "</tbody></table></div>" +
      '<div class="hole-detail" data-hole-detail>행을 선택하면 해당 홀의 샷 시퀀스 요약이 여기에 표시된다.</div>' +
      "</section>";
  }

  /* ---------- SECTION 8 : AI Summary -------------------------------------- */
  function summary(p) {
    return '<section class="card pi-summary" id="s-summary">' +
      '<div class="pi-insight__head"><span class="chip chip--accent">AI SUMMARY</span>' +
      '<span class="eyebrow">' + esc(p.name) + " · 3줄 요약</span></div><ol>" +
      p.summary.map(function (s) { return "<li><span>" + esc(s) + "</span></li>"; }).join("") +
      "</ol></section>";
  }

  /* ---------- Right panel : Player Snapshot ------------------------------- */
  function snapshot(p) {
    const s = p.snapshot;
    return '<aside class="card snap" id="s-snap">' +
      "<h3>Player Snapshot</h3>" +
      '<div class="snap__grid">' +
        '<div class="snap__tile"><b>' + s.avgRank + '</b><span>평균 순위</span></div>' +
        '<div class="snap__tile"><b>' + s.best + '</b><span>Best Finish</span></div>' +
        '<div class="snap__tile"><b>' + s.cut + '</b><span>최근 컷</span></div>' +
        '<div class="snap__tile"><b>#' + p.neoRank + '</b><span>NEO Rank</span></div>' +
      "</div>" +
      '<div class="snap__label">최근 5경기</div>' +
      '<ul class="snap__list">' +
        s.last5.map(function (r) { return "<li><span>" + esc(r.event) + "</span><b>" + esc(r.rank) + "</b></li>"; }).join("") +
      "</ul>" +
      '<div class="snap__label">최근 상승</div>' +
      '<div class="snap__mom">' + esc(s.momentum) + "</div>" +
    "</aside>";
  }

  /* ---------- Prev / Next pager ------------------------------------------- */
  function pager(p) {
    const n = global.NEO.neighbors(p.code);
    return '<nav class="pi-pager" aria-label="선수 이동">' +
      '<a class="pager-btn" href="' + global.NEO.href(n.prev.code) + '">' +
        '<span class="pager-arrow">←</span><span><span class="pager-btn__k">이전 선수</span>' +
        '<span class="pager-btn__n" style="display:block">' + esc(n.prev.name) + "</span>" +
        '<span class="pager-btn__t">' + esc(n.prev.tagline) + "</span></span></a>" +
      '<a class="pager-btn pager-btn--next" href="' + global.NEO.href(n.next.code) + '">' +
        '<span><span class="pager-btn__k">다음 선수</span>' +
        '<span class="pager-btn__n" style="display:block">' + esc(n.next.name) + "</span>" +
        '<span class="pager-btn__t">' + esc(n.next.tagline) + "</span></span>" +
        '<span class="pager-arrow">→</span></a>' +
    "</nav>";
  }

  /* ---------- mount -------------------------------------------------------- */
  function render(p) {
    document.title = p.name + " · Player Intelligence — NEO Golf Data";
    const main = document.querySelector("[data-pi-main]");
    const side = document.querySelector("[data-pi-side]");
    main.innerHTML = hero(p) + insight(p) + dna(p) + shotDna(p) + evolution(p) + courseFit(p) + holeLibrary(p) + summary(p);
    side.innerHTML = snapshot(p);
    document.querySelector("[data-pi-pager]").innerHTML = pager(p);

    NEOChart.responsive(main.querySelector('[data-chart="driver"]'), function (el, w) {
      NEOChart.driverDistribution(el, p.shot.driver, w);
    }, 240, 520);
    NEOChart.responsive(main.querySelector('[data-chart="approach"]'), function (el, w) {
      NEOChart.approachDistribution(el, p.shot.approach, w);
    }, 260, 560);
    NEOChart.responsive(main.querySelector('[data-chart="landing"]'), function (el, w) {
      NEOChart.landingDistribution(el, p.shot.landing, w);
    }, 240, 460);
    p.evolution.forEach(function (m, i) {
      NEOChart.responsive(main.querySelector('[data-spark="' + i + '"]'), function (el, w) {
        NEOChart.sparkline(el, m.series, SERIES_OF[m.key], w);
      }, 160, 420);
    });

    // Hole row → hole detail (route reserved: /player/{code}/hole/{holeId})
    const detail = main.querySelector("[data-hole-detail]");
    main.querySelectorAll(".hole-row").forEach(function (row) {
      const h = p.holes.filter(function (x) { return x.id === row.dataset.hole; })[0];
      function open() {
        detail.innerHTML = "<b>R" + h.round + " · " + h.hole + "번 홀 (Par " + h.par + ")</b><br>" +
          "캐리 " + h.carry + "m · 남은 거리 " + h.left + "m · 라이 " + h.lie + " · QA " + h.qa + "<br>" +
          esc(h.note) + '<br><span style="color:var(--neo-ink-3)">holeDetailRoute: ' + row.dataset.holeHref + "</span>";
      }
      row.addEventListener("click", open);
      row.addEventListener("keydown", function (e) { if (e.key === "Enter") open(); });
    });
  }

  document.addEventListener("DOMContentLoaded", function () {
    NEOUI.header("");
    const p = global.NEO.byCode(codeFromLocation()) || global.NEO.players[0];
    render(p);
  });
})(window);
