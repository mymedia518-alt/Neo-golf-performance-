(() => {
  document.querySelectorAll('.mode').forEach((button) => button.addEventListener('click', () => {
    document.querySelectorAll('.mode').forEach((b) => { b.classList.remove('active'); b.setAttribute('aria-pressed', 'false'); });
    button.classList.add('active'); button.setAttribute('aria-pressed', 'true');
  }));
  const selected = new Set();
  document.querySelectorAll('.player-select').forEach((button) => button.addEventListener('click', () => {
    const id = button.dataset.playerId;
    if (selected.has(id)) selected.delete(id); else if (selected.size < 5) selected.add(id);
    document.querySelectorAll('.performance-card').forEach((card) => { card.hidden = selected.size > 0 && !selected.has(card.dataset.playerId); });
  }));
})();
