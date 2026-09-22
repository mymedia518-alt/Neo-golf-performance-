/* ==========================================================================
   NEO Golf Data — shared shell (header, nav, list tables)
   Player names anywhere in the product link to /player/{playerCode}.
   ========================================================================== */

(function (global) {
  "use strict";

  const NAV = [
    { href: "/index.html", key: "home", label: "HOME" },
    { href: "/ranking.html", key: "ranking", label: "RANKING" },
    { href: "/tournament.html", key: "tournament", label: "TOURNAMENT" },
    { href: "/leaderboard.html", key: "leaderboard", label: "LEADERBOARD" }
  ];

  function header(active) {
    const mount = document.querySelector("[data-neo-header]");
    if (!mount) return;
    mount.className = "neo-header";
    mount.innerHTML =
      '<div class="wrap neo-header__inner">' +
        '<a class="neo-logo" href="/index.html">' +
          '<span class="neo-logo__mark">N</span>NEO<span class="neo-logo__sub">Golf Data</span>' +
        "</a>" +
        '<nav class="neo-nav">' +
          NAV.map(function (n) {
            return '<a href="' + n.href + '"' + (n.key === active ? ' aria-current="page"' : "") + ">" + n.label + "</a>";
          }).join("") +
        "</nav>" +
      "</div>";
  }

  /** Player name → Player Intelligence. The single entry point used by
   *  HOME / RANKING / TOURNAMENT / LEADERBOARD. */
  function playerLink(p, extraClass) {
    return '<a class="player-link ' + (extraClass || "") + '" href="' + global.NEO.href(p.code) +
      '" data-player-code="' + p.code + '">' + p.name + "</a>";
  }

  function leaderboardTable(mount, limit) {
    const rows = global.NEO.leaderboard.slice(0, limit || 99);
    mount.innerHTML =
      '<table class="neo-table"><thead><tr>' +
        "<th>순위</th><th>선수</th><th>스타일</th><th class=\"ta-r\">Today</th><th class=\"ta-r\">Total</th><th class=\"ta-r\">Thru</th>" +
      "</tr></thead><tbody>" +
      rows.map(function (r) {
        const p = global.NEO.byCode(r.code);
        return "<tr><td class=\"num\">" + r.pos + "</td>" +
          "<td>" + playerLink(p) + "</td>" +
          '<td style="color:var(--neo-ink-3)">' + p.tagline + "</td>" +
          '<td class="ta-r num">' + r.today + "</td>" +
          '<td class="ta-r num" style="color:var(--neo-ink);font-weight:700">' + r.total + "</td>" +
          '<td class="ta-r num">' + r.thru + "</td></tr>";
      }).join("") +
      "</tbody></table>";
  }

  function rankingTable(mount) {
    const ps = global.NEO.players.slice().sort(function (a, b) { return a.kRank - b.kRank; });
    mount.innerHTML =
      '<table class="neo-table"><thead><tr>' +
        "<th>K-Rank</th><th>NEO Rank</th><th>선수</th><th>NEO 한 줄 정의</th><th class=\"ta-r\">Form</th>" +
      "</tr></thead><tbody>" +
      ps.map(function (p) {
        return '<tr><td class="num">' + p.kRank + "</td>" +
          '<td class="num" style="color:var(--neo-accent);font-weight:700">' + p.neoRank + "</td>" +
          "<td>" + playerLink(p) + "</td>" +
          '<td style="color:var(--neo-ink-3)">' + p.tagline + "</td>" +
          '<td class="ta-r"><span class="chip">' + p.form + "</span></td></tr>";
      }).join("") +
      "</tbody></table>";
  }

  global.NEOUI = { header: header, playerLink: playerLink, leaderboardTable: leaderboardTable, rankingTable: rankingTable };
})(window);
