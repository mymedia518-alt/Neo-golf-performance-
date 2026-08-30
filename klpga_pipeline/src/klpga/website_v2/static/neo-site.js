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

  document.addEventListener("DOMContentLoaded", function () {
    revealActiveStage();
    document.addEventListener("click", trackDeepDiveInterest);
  });
})();
