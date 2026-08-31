(() => {
  const style = document.createElement('style');
  style.textContent = '.probability-chart{display:block;width:100%;height:auto;margin-top:18px}.probability-chart .line{fill:none;stroke:#126b5b;stroke-width:3}.probability-chart circle{fill:#126b5b;stroke:#fff;stroke-width:2}.probability-chart .point-label{font-weight:700}.table-wrap{position:relative}.table-wrap::after{content:"↔";position:absolute;right:8px;top:8px;padding:2px 6px;border-radius:10px;background:#18212b;color:#fff;font-size:12px;pointer-events:none}';
  document.head.appendChild(style);
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
