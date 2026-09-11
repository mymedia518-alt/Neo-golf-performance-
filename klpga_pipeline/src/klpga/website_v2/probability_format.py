"""ONE shared public probability display formatter (FINAL HOTFIX BEFORE
DEPLOYMENT, base fb4f165).

Display-only, render-boundary transform -- the raw stored probability
value (win_pct/top5_pct/top10_pct/top20_pct, already on a 0-100 scale,
see klpga.neo_win.round_update_r2) is never touched, never resimulated,
never rounded/clamped/rewritten in any artifact. This module only
decides what STRING a real number becomes when it reaches a public
page.

Used identically by every renderer's desktop AND mobile output -- there
is only ever one call site per cell (klpga.neo_win.r2_real_page's
leaderboard table is the same markup for both; CSS alone reflows it for
narrow viewports), so "PC and mobile use exactly the same formatter" is
true by construction, not by convention.

CONTRACT:
    p == 0       -> "0%"     a real, exact zero -- not "0.0%", which
                              elsewhere in this codebase's convention
                              reads as "rounds to zero", ambiguous with
                              the near-zero case below.
    0 < p < 0.1  -> "<0.1%"  a real, non-zero probability that would
                              otherwise round away to "0.0%" at one
                              decimal place -- silently displaying that
                              would misrepresent a genuine non-zero
                              chance as exactly impossible. Contains no
                              whitespace, so it can never wrap onto two
                              lines under normal (non break-all) CSS
                              text flow.
    p >= 0.1     -> one decimal place, e.g. "0.2%", "8.8%", "53.1%".
"""
from __future__ import annotations


def format_public_probability(p: float) -> str:
    p = float(p)
    if p == 0:
        return "0%"
    if p < 0.1:
        return "<0.1%"
    return f"{p:.1f}%"
