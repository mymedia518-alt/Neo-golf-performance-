/* NEO GOLF PREDICTIONS — client-side search/filter/expand only.
 * No probability, ranking, or feature value is computed here. Search
 * and filter never re-sort or remove rows from the DOM: every row
 * renders once, in the archive's own rank order, at build time
 * (see src/klpga/site/templates.py); this script only toggles a
 * "row-hidden" class, so the underlying row ORDER can never change
 * at runtime, no matter what a viewer types or clicks. */
(function () {
  "use strict";

  function initPredictionsRoot(root) {
    var table = root.querySelector("#predictions-table");
    if (!table) return;

    var searchInput = root.querySelector("#player-search");
    var filterButtons = root.querySelectorAll(".filter-pill");
    var rows = Array.prototype.slice.call(table.querySelectorAll(".pred-row"));

    // "top10" matches the server-rendered default (see
    // DEFAULT_VISIBLE_RANK_COUNT / _entrant_row_html in templates.py) —
    // this only keeps client-side state in sync with what's already on
    // the page; it doesn't itself hide/show anything until a
    // search/filter interaction happens.
    var state = { query: "", filter: "top10" };

    function matchesSearch(row) {
      if (!state.query) return true;
      var haystack = row.getAttribute("data-search") || "";
      return haystack.indexOf(state.query) !== -1;
    }

    function matchesFilter(row) {
      // An active search query overrides the rank filter — every one
      // of the 120 entrants must stay reachable by name/code, even
      // while the "TOP 10" pill is still showing as active. Without
      // this, searching for a player ranked outside the current pill
      // would silently return zero results.
      if (state.query) return true;
      if (state.filter === "all") return true;
      var rank = parseInt(row.getAttribute("data-rank"), 10);
      if (state.filter === "top10") return rank <= 10;
      if (state.filter === "top20") return rank <= 20;
      return true;
    }

    function detailRowOf(row) {
      var next = row.nextElementSibling;
      return next && next.classList.contains("pred-detail") ? next : null;
    }

    function applyVisibility() {
      rows.forEach(function (row) {
        var visible = matchesSearch(row) && matchesFilter(row);
        row.classList.toggle("row-hidden", !visible);
        var detail = detailRowOf(row);
        if (detail) {
          if (!visible) {
            detail.classList.add("row-hidden");
            detail.hidden = true;
            row.setAttribute("aria-expanded", "false");
          } else {
            detail.classList.remove("row-hidden");
          }
        }
      });
    }

    function toggleDetail(row) {
      var detail = detailRowOf(row);
      if (!detail) return;
      var expanded = row.getAttribute("aria-expanded") === "true";
      detail.hidden = expanded;
      row.setAttribute("aria-expanded", expanded ? "false" : "true");
    }

    if (searchInput) {
      searchInput.addEventListener("input", function () {
        state.query = searchInput.value.trim().toLowerCase();
        applyVisibility();
      });
    }

    Array.prototype.forEach.call(filterButtons, function (btn) {
      btn.addEventListener("click", function () {
        Array.prototype.forEach.call(filterButtons, function (b) {
          b.classList.remove("active");
          b.setAttribute("aria-pressed", "false");
        });
        btn.classList.add("active");
        btn.setAttribute("aria-pressed", "true");
        state.filter = btn.getAttribute("data-filter");
        applyVisibility();
      });
    });

    rows.forEach(function (row) {
      row.addEventListener("click", function () {
        toggleDetail(row);
      });
      row.addEventListener("keydown", function (event) {
        if (event.key === "Enter" || event.key === " ") {
          event.preventDefault();
          toggleDetail(row);
        }
      });
    });
  }

  document.addEventListener("DOMContentLoaded", function () {
    var roots = document.querySelectorAll("[data-neo-predictions-root]");
    Array.prototype.forEach.call(roots, initPredictionsRoot);
  });
})();
