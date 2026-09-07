(function () {
  "use strict";

  function initNav() {
    var toggle = document.querySelector("[data-v3-nav-toggle]");
    var nav = document.querySelector("[data-v3-nav]");
    if (!toggle || !nav) return;
    toggle.addEventListener("click", function () {
      var open = nav.classList.toggle("is-open");
      toggle.setAttribute("aria-expanded", open ? "true" : "false");
    });
  }

  function initRankingFilter() {
    var search = document.querySelector("#v3-player-search");
    var sort = document.querySelector("#v3-sort");
    var countOut = document.querySelector("#v3-visible-count");
    var tableBody = document.querySelector("[data-v3-rank-body]");
    var cardsRoot = document.querySelector("[data-v3-rank-cards]");
    if (!search || !tableBody) return;

    function rowsOf(root) {
      return root ? Array.from(root.querySelectorAll("[data-player-row]")) : [];
    }

    function apply() {
      var query = search.value.trim().toLocaleLowerCase("ko");
      var mode = sort ? sort.value : "neo";
      [tableBody, cardsRoot].forEach(function (root) {
        if (!root) return;
        var rows = rowsOf(root);
        rows.sort(function (a, b) {
          if (mode === "k-rank") {
            return Number(a.dataset.kRank) - Number(b.dataset.kRank) ||
              a.dataset.playerName.localeCompare(b.dataset.playerName, "ko");
          }
          if (mode === "recent-sg") {
            return Number(b.dataset.recentSg || -999) - Number(a.dataset.recentSg || -999) ||
              a.dataset.playerName.localeCompare(b.dataset.playerName, "ko");
          }
          return a.dataset.playerName.localeCompare(b.dataset.playerName, "ko");
        });
        var visible = 0;
        rows.forEach(function (row) {
          var show = !query || row.dataset.playerName.indexOf(query) !== -1;
          row.hidden = !show;
          if (show) visible += 1;
          root.appendChild(row);
        });
        if (root === tableBody && countOut) countOut.value = visible + "명";
      });
    }

    search.addEventListener("input", apply);
    if (sort) sort.addEventListener("change", apply);
  }

  // NEO Performance Race: purely decorative, non-data-bearing animation
  // (a slow pulse on the "awaiting validated data" empty-state marker).
  // Respects prefers-reduced-motion via CSS (.v3-race-pulse has an
  // @media (prefers-reduced-motion: reduce) override) -- this script
  // never draws or invents a single data point; the shell is structural
  // only, ready for a real series renderer to attach to
  // [data-v3-race-series] once validated data exists.
  function initRaceShell() {
    var svg = document.querySelector("[data-v3-race-svg]");
    if (!svg) return;
    svg.setAttribute("data-v3-race-ready", "true");
  }

  document.addEventListener("DOMContentLoaded", function () {
    initNav();
    initRankingFilter();
    initRaceShell();
  });
})();
