(function () {
  "use strict";

  function initNav() {
    var toggle = document.querySelector("[data-t-nav-toggle]");
    var nav = document.querySelector("[data-t-nav]");
    if (!toggle || !nav) return;
    toggle.addEventListener("click", function () {
      var open = nav.classList.toggle("is-open");
      toggle.setAttribute("aria-expanded", open ? "true" : "false");
    });
  }

  function rowsOf(root) {
    return root ? Array.from(root.querySelectorAll("[data-player-row]")) : [];
  }

  function initBoardFilter() {
    var search = document.querySelector("#t-search");
    var sort = document.querySelector("#t-sort");
    var countOut = document.querySelector("#t-visible-count");
    var boardBody = document.querySelector("[data-t-board-body]");
    var mobileList = document.querySelector("[data-t-mobile-list]");
    if (!search || !boardBody) return;

    function apply() {
      var query = search.value.trim().toLocaleLowerCase("ko");
      var mode = sort ? sort.value : "name";
      [boardBody, mobileList].forEach(function (root) {
        if (!root) return;
        var rows = rowsOf(root);
        rows.sort(function (a, b) {
          if (mode === "k-rank") {
            // Missing K-RANK (no data-k-rank attribute) is a distinct
            // missing-state, never a numeric value -- it always sorts
            // after every row that has a real official rank.
            var aHas = a.dataset.kRank !== undefined && a.dataset.kRank !== "";
            var bHas = b.dataset.kRank !== undefined && b.dataset.kRank !== "";
            if (aHas && bHas) {
              return Number(a.dataset.kRank) - Number(b.dataset.kRank) ||
                a.dataset.playerName.localeCompare(b.dataset.playerName, "ko");
            }
            if (aHas !== bHas) return aHas ? -1 : 1;
            return a.dataset.playerName.localeCompare(b.dataset.playerName, "ko");
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
        if (root === boardBody && countOut) countOut.value = visible;
      });
    }

    search.addEventListener("input", apply);
    if (sort) sort.addEventListener("change", apply);
  }

  // Player inspector: reads only the fields already present in the
  // clicked row's dataset (real player name, real or dash K-RANK) --
  // never invents a value the row itself does not already carry.
  function initInspector() {
    var inspector = document.querySelector("[data-t-inspector]");
    var scrim = document.querySelector("[data-t-scrim]");
    var closeBtn = document.querySelector("[data-t-inspector-close]");
    var nameEl = document.querySelector("[data-t-inspector-name]");
    var krankEl = document.querySelector("[data-t-inspector-krank]");
    if (!inspector || !scrim) return;

    function open(row) {
      if (nameEl) nameEl.textContent = row.dataset.playerDisplayName || "";
      if (krankEl) krankEl.textContent = row.dataset.kRankDisplay || "—";
      inspector.classList.add("is-open");
      scrim.classList.add("is-open");
      inspector.setAttribute("aria-hidden", "false");
      closeBtn && closeBtn.focus();
    }

    function close() {
      inspector.classList.remove("is-open");
      scrim.classList.remove("is-open");
      inspector.setAttribute("aria-hidden", "true");
    }

    document.addEventListener("click", function (event) {
      var row = event.target.closest("[data-player-row]");
      if (row) { open(row); return; }
      if (event.target.closest("[data-t-inspector-close]") || event.target === scrim) close();
    });

    document.addEventListener("keydown", function (event) {
      var row = event.target.closest("[data-player-row]");
      if (row && (event.key === "Enter" || event.key === " ")) {
        event.preventDefault();
        open(row);
        return;
      }
      if (event.key === "Escape") close();
    });
  }

  function initChartReadyMarkers() {
    document.querySelectorAll("[data-t-chart-svg]").forEach(function (svg) {
      svg.setAttribute("data-t-chart-ready", "true");
    });
  }

  document.addEventListener("DOMContentLoaded", function () {
    initNav();
    initBoardFilter();
    initInspector();
    initChartReadyMarkers();
  });
})();
