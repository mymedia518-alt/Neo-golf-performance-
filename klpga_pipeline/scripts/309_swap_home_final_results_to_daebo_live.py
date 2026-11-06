"""Replace HOME's "최종 결과" section (the previous tournament's -- 제20회
S-OIL 챔피언십 -- full 68-player final results table) with a live,
auto-refreshing win-probability table for the current tournament
(대보 하우스디 챔피언십, 2026110001), per explicit operator instruction
(2026-11-06): "홈화면에 지난 대회 결과를 내리고 이번대회를 띄워줘"
("take down the previous tournament's results on the home screen and
bring up this tournament's instead").

This reuses the EXACT same fetch/render approach and column order
already verified on /tournaments/2026/2026110001/live/ (순위, 선수,
진행, R<current round>, TOP20, TOP10, TOP5, 우승확률 -- matching this
site's own established column order, not reinvented), fetching the
same DAEBO_2026110001_LIVE_PROBABILITY_LATEST.json from the
live/2026110001 branch, so the two pages can never drift out of sync
with each other.

SCOPE: the `<section id="home-fr-records">...</section>` block is
replaced, AND two separate <script> blocks further down the page that
target that same id by element query -- the auto-scroll-into-view-once
script and the continuous horizontal-ticker animation script (the same
32px/s ticker built earlier this session for this exact table) -- are
retargeted to the new section's id so that existing behavior keeps
working against the new content instead of silently finding nothing.
The patch script proves everything else in index.html is byte-
identical before/after (same hard-assert discipline as scripts/308's
featured-card swap).
"""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INDEX_PATH = ROOT.parent / "docs" / "index.html"

OLD_SECTION_OPEN = '<section class="home-section panel leaderboard-panel" id="home-fr-records">'

NEW_SECTION = '''<section class="home-section panel leaderboard-panel" id="home-live-results"><style>
#home-live-results .live-status{display:flex;flex-wrap:wrap;gap:10px 18px;align-items:center;margin:0 0 10px;font-size:13px;color:var(--muted)}
#home-live-results .live-status__badge{display:inline-flex;align-items:center;gap:6px;padding:3px 10px;border-radius:999px;background:var(--soft);font-weight:700}
#home-live-results .live-status__stale{display:none;background:#5a1f1f;color:#ffd6d6;border-radius:999px;padding:3px 10px;font-weight:700}
#home-live-results .live-status--is-stale .live-status__stale{display:inline-flex}
#home-live-results .live-status__upcoming{display:none;background:var(--soft);color:var(--muted);border-radius:999px;padding:3px 10px;font-weight:700}
#home-live-results .live-status--upcoming .live-status__upcoming{display:inline-flex}
#home-live-results .live-table td.rank{font-weight:800;color:var(--accent)}
#home-live-results .live-table td.holes{color:var(--muted);font-size:12px}
#home-live-results .live-table td.winpct{font-weight:900;color:var(--gold,#d8ab5c)}
#home-live-results .live-table tr.is-eliminated td,#home-live-results .live-table tr.is-eliminated th{color:var(--muted)}
#home-live-results .live-error{display:none;background:#5a1f1f;color:#ffd6d6;border-radius:8px;padding:10px 14px;margin:0 0 10px;font-size:13px}
#home-live-results .eyebrow-badge{display:inline-block;padding:2px 9px;border-radius:999px;border:1px solid var(--gold,#d8ab5c);color:var(--gold,#d8ab5c);font-size:11px;font-weight:700;margin-left:6px;vertical-align:middle}
</style><div class="leaderboard-head"><h2>실시간 우승확률<span class="eyebrow-badge">참고 예상</span> <small id="homeLiveFieldCount">—명</small></h2></div><p class='section-link-row'><a href='/tournaments/2026/2026110001/live/'>실시간 우승확률 전체 보기 →</a></p><div class="live-error" id="homeLiveError">실시간 데이터를 불러오지 못했습니다. 잠시 후 다시 시도합니다.</div><div class="live-status" id="homeLiveStatus"><span class="live-status__badge" id="homeLiveRoundBadge">라운드 —</span><span id="homeLiveUpdatedAt">최근 갱신: —</span><span class="live-status__stale" id="homeLiveStaleBadge">업데이트 지연</span><span class="live-status__upcoming" id="homeLiveUpcomingBadge">1라운드 시작과 동시에 업데이트</span></div><div class="table-wrap table-wrap--iceberg-r1"><table class="data leaderboard-table leaderboard-table--iceberg-r1 live-table" id="homeLiveTable"><thead><tr><th>순위</th><th>선수</th><th>진행</th><th id="homeLiveRoundScoreHeader">R1</th><th>TOP20</th><th>TOP10</th><th>TOP5</th><th>우승확률</th></tr></thead><tbody id="homeLiveTableBody"><tr><td colspan="8">불러오는 중…</td></tr></tbody></table></div><script>
(function () {
  "use strict";
  var DATA_URL = "https://raw.githubusercontent.com/mymedia518-alt/Neo-golf-performance-/live/2026110001/klpga_pipeline/content/website_v2/DAEBO_2026110001_LIVE_PROBABILITY_LATEST.json";
  var REFRESH_MS = 60000;
  var STALE_MS = 45 * 60 * 1000;
  var ROUND1_START_MS = new Date("2026-11-06T00:00:00+09:00").getTime();

  var statusEl = document.getElementById("homeLiveStatus");
  var roundBadge = document.getElementById("homeLiveRoundBadge");
  var updatedAtEl = document.getElementById("homeLiveUpdatedAt");
  var errorEl = document.getElementById("homeLiveError");
  var fieldCountEl = document.getElementById("homeLiveFieldCount");
  var tbody = document.getElementById("homeLiveTableBody");

  function fmtPct(value) { return (value * 100).toFixed(2) + "%"; }

  function fmtToPar(value) {
    if (value == null) return "—";
    if (value === 0) return "E";
    return value > 0 ? "+" + value : String(value);
  }

  function escapeHtml(s) {
    return String(s == null ? "" : s).replace(/[&<>"']/g, function (c) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c];
    });
  }

  function eliminationLabel(status) {
    var s = String(status || "").toUpperCase();
    if (s === "WD") return "기권";
    if (s === "DQ") return "실격";
    if (s === "CUT") return "컷 탈락";
    return "제외";
  }

  function render(doc) {
    roundBadge.textContent = "라운드 " + doc.current_round + " / " + doc.rounds_total;
    document.getElementById("homeLiveRoundScoreHeader").textContent = "R" + doc.current_round;
    var updated = new Date(doc.collected_at);
    updatedAtEl.textContent = "최근 갱신(실제 수집 시각): " + updated.toLocaleString("ko-KR", { hour12: false });

    var now = Date.now();
    var ageMs = now - updated.getTime();
    var isStale = !!doc.is_stale || ageMs > STALE_MS;
    var tournamentStarted = now >= ROUND1_START_MS;
    statusEl.classList.toggle("live-status--is-stale", isStale && tournamentStarted);
    statusEl.classList.toggle("live-status--upcoming", isStale && !tournamentStarted);

    var activeRows = doc.probabilities || [];
    var eliminatedRows = (doc.round_complete && doc.eliminated_players) ? doc.eliminated_players : [];
    fieldCountEl.textContent = (activeRows.length + eliminatedRows.length) + "명";

    var roundLabel = "R" + doc.current_round;
    if (!activeRows.length && !eliminatedRows.length) {
      tbody.innerHTML = "<tr><td colspan='8'>아직 집계된 선수가 없습니다.</td></tr>";
    } else {
      var rows = activeRows.map(function (p, idx) {
        var holes = p.holes_completed == null ? "—" : (p.holes_completed >= 18 ? "완료" : p.holes_completed + "H");
        return (
          "<tr><td class='rank' data-label='순위'>" + (idx + 1) + "</td>" +
          "<th scope='row' style='text-align:left;white-space:nowrap'>" + escapeHtml(p.player_name) + "</th>" +
          "<td class='holes' data-label='진행'>" + holes + "</td>" +
          "<td data-label='" + roundLabel + "'>" + fmtToPar(p.today_under_par) + "</td>" +
          "<td data-label='TOP20'>" + fmtPct(p.top20_probability) + "</td>" +
          "<td data-label='TOP10'>" + fmtPct(p.top10_probability) + "</td>" +
          "<td data-label='TOP5'>" + fmtPct(p.top5_probability) + "</td>" +
          "<td class='winpct' data-label='우승확률'>" + fmtPct(p.win_probability) + "</td></tr>"
        );
      });
      rows = rows.concat(eliminatedRows.map(function (p) {
        var label = eliminationLabel(p.status);
        return (
          "<tr class='is-eliminated'><td class='rank' data-label='순위'>—</td>" +
          "<th scope='row' style='text-align:left;white-space:nowrap'>" + escapeHtml(p.player_name) + "</th>" +
          "<td class='holes' data-label='진행'>" + label + "</td>" +
          "<td data-label='" + roundLabel + "'>—</td>" +
          "<td data-label='TOP20'>—</td>" +
          "<td data-label='TOP10'>—</td>" +
          "<td data-label='TOP5'>—</td>" +
          "<td class='winpct' data-label='우승확률'>—</td></tr>"
        );
      }));
      tbody.innerHTML = rows.join("");
    }

    errorEl.style.display = "none";
  }

  function load() {
    fetch(DATA_URL + "?_=" + Date.now(), { cache: "no-store" })
      .then(function (res) {
        if (!res.ok) throw new Error("HTTP " + res.status);
        return res.json();
      })
      .then(render)
      .catch(function () {
        errorEl.style.display = "block";
      });
  }

  load();
  setInterval(load, REFRESH_MS);
})();
</script></section>'''


def main() -> None:
    html = INDEX_PATH.read_text(encoding="utf-8")

    start = html.find(OLD_SECTION_OPEN)
    if start == -1:
        raise RuntimeError("could not find the home-fr-records section opening tag -- refusing to patch")
    if html.count(OLD_SECTION_OPEN) != 1:
        raise RuntimeError("expected exactly 1 occurrence of the section opening tag")

    end_tag = "</section>"
    end = html.find(end_tag, start)
    if end == -1:
        raise RuntimeError("could not find the matching </section> -- refusing to patch")
    end += len(end_tag)

    old_section = html[start:end]
    if old_section.count("<section") != 1 or old_section.count("</section>") != 1:
        raise RuntimeError("the located section contains nested <section> tags -- boundary detection unsafe, refusing to patch")

    patched = html[:start] + NEW_SECTION + html[end:]

    # Two scripts further down the page target the old section by id:
    # the one-shot auto-scroll-into-view and the continuous 32px/s
    # ticker animation (same ticker built earlier this session for this
    # exact table). Retarget both so they keep working against the new
    # section instead of silently finding nothing (getElementById/
    # querySelector returning null, an early `if(!target)return`).
    retargets = [
        ("getElementById('home-fr-records')", "getElementById('home-live-results')"),
        ("querySelector('#home-fr-records .table-wrap')", "querySelector('#home-live-results .table-wrap')"),
        ("#home-fr-records{scroll-margin-top:1rem}", "#home-live-results{scroll-margin-top:1rem}"),
        ("#home-fr-records .table-wrap{max-height:26rem;overflow-y:hidden}", "#home-live-results .table-wrap{max-height:26rem;overflow-y:hidden}"),
        ("#home-fr-records .table-wrap:after{content:none}", "#home-live-results .table-wrap:after{content:none}"),
    ]
    for old, new in retargets:
        if patched.count(old) != 1:
            raise RuntimeError(f"expected exactly 1 occurrence of {old!r} outside the replaced section, found {patched.count(old)}")
        patched = patched.replace(old, new)

    if "최근 종료 대회" not in patched:
        raise RuntimeError("the '최근 종료 대회' line disappeared -- refusing to write a patch that touched it")
    if "id=\"home-live-results\"" not in patched:
        raise RuntimeError("new section did not get inserted correctly")
    if "home-fr-records" in patched:
        raise RuntimeError("old section id still present -- replacement incomplete")

    before_minus_section = html[:start] + html[end:]
    after_reverted = patched.replace(NEW_SECTION, "")
    for old, new in retargets:
        after_reverted = after_reverted.replace(new, old)
    if before_minus_section != after_reverted:
        raise RuntimeError(
            "the patch changed something outside the replaced section and the two retargeted scripts -- "
            "refusing to write it. This is a hard assert: every other byte of the page must be identical."
        )

    INDEX_PATH.write_text(patched, encoding="utf-8")
    print(f"patched {INDEX_PATH}: replaced home-fr-records (S-OIL final results, {len(old_section)} bytes) "
          f"with home-live-results (Daebo live probability, {len(NEW_SECTION)} bytes)")
    print("verified: everything else in index.html is byte-identical (최근 종료 대회 line + featured card untouched)")


if __name__ == "__main__":
    main()
