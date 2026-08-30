(function () {
  "use strict";

  function revealActiveStage() {
    var navigation = document.querySelector("[data-stage-nav]");
    if (!navigation) return;
    var active = navigation.querySelector('[aria-current="page"]');
    if (!active || typeof active.scrollIntoView !== "function") return;
    active.scrollIntoView({ behavior: "auto", block: "nearest", inline: "center" });
  }

  document.addEventListener("DOMContentLoaded", revealActiveStage);
})();
