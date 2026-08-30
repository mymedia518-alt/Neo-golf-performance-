(function () {
  "use strict";

  function revealActiveStage() {
    var navigation = document.querySelector("[data-stage-nav]");
    if (!navigation) return;
    var active = navigation.querySelector('[aria-current="page"]');
    if (!active || typeof active.scrollIntoView !== "function") return;
    active.scrollIntoView({ behavior: "auto", block: "nearest", inline: "center" });
  }

  function trackDeepDiveInterest(event) {
    var link = event.target.closest("[data-deep-dive-interest]");
    if (!link) return;
    window.dataLayer = window.dataLayer || [];
    window.dataLayer.push({
      event: "deep_dive_interest",
      tournament_id: link.dataset.tournamentId || undefined,
      tournament_slug: link.dataset.tournamentSlug || undefined,
      stage: link.dataset.stage || undefined,
      player_code: link.dataset.playerCode || undefined,
      cta_location: link.dataset.ctaLocation || undefined,
      deep_dive_id: link.dataset.deepDiveId || undefined,
      content_type: link.dataset.contentType || undefined
    });
  }

  function filterForecastRows(event) {
    var button = event.target.closest("[data-row-limit]");
    if (!button) return;
    var section = button.closest("[data-forecast-stage]");
    var table = section && section.querySelector("[data-forecast-table]");
    if (!table) return;
    var limit = button.dataset.rowLimit === "all" ? Infinity : Number(button.dataset.rowLimit);
    table.querySelectorAll("tbody tr").forEach(function (row, index) { row.hidden = index >= limit; });
    section.querySelectorAll("[data-row-limit]").forEach(function (item) {
      item.setAttribute("aria-pressed", item === button ? "true" : "false");
    });
  }

  document.addEventListener("DOMContentLoaded", function () {
    revealActiveStage();
    document.addEventListener("click", trackDeepDiveInterest);
    document.addEventListener("click", filterForecastRows);
  });
})();
