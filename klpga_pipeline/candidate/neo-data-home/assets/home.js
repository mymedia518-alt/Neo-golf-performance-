(function () {
  "use strict";
  function rankOrMissingLast(v) {
    // An absent/empty data-k-rank attribute means no real official rank
    // was ever joined for this player -- Infinity always sorts it after
    // every real (finite) rank, without a fabricated numeric stand-in
    // ever appearing in the page's own markup.
    return v === "" || v === undefined ? Infinity : Number(v);
  }
  function refresh() {
    var query = document.querySelector("#player-search").value.trim().toLocaleLowerCase("ko");
    var select = document.querySelector("#home-sort").value;
    var tbody = document.querySelector("[data-player-row]").parentNode;
    var rows = Array.from(tbody.querySelectorAll("[data-player-row]"));
    rows.sort(function (a, b) {
      if (select === "k-rank") return rankOrMissingLast(a.dataset.kRank) - rankOrMissingLast(b.dataset.kRank) || a.dataset.playerName.localeCompare(b.dataset.playerName, "ko");
      return a.dataset.playerName.localeCompare(b.dataset.playerName, "ko");
    });
    var visible = 0;
    rows.forEach(function (row) { var show = !query || row.dataset.playerName.indexOf(query) !== -1; row.hidden = !show; if (show) visible += 1; tbody.appendChild(row); });
    document.querySelector("#home-count").value = visible + "명";
  }
  document.addEventListener("DOMContentLoaded", function () {
    document.querySelector("#player-search").addEventListener("input", refresh);
    document.querySelector("#home-sort").addEventListener("change", refresh);
  });
})();
