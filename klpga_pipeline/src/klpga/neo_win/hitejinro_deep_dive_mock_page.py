"""HITE JINRO (game_code 2026100005) Course Deep Dive -- UI LAYOUT
MOCKUP, explicit operator instruction (2026-10-01): "Deep Dive HTML
레이아웃만 구현한다. 실제 데이터 연결은 하지 않는다. 더미 데이터로
UI를 만든다." (build the Deep Dive HTML layout only; do not connect
real data; build the UI with dummy data.)

EVERY per-hole performance number on this page -- hole difficulty stars,
average relative score, birdie/par/bogey-plus rates, tee-shot
distribution, distance, the TOP5 lists, the 18-hole matrix, the "한 줄
분석"/"NEO 코스 분석" sentences, the Course DNA radar -- is a hand-built,
internally-consistent MOCK dataset (_MOCK_HOLES below), never a real
KLPGA measurement. All of it is computed FROM _MOCK_HOLES (not
independently typed), so it can never numerically contradict the
per-hole table even though none of it is real.

V2 EXCEPTION (operator-supplied evidence, 2026-10-01): the East Hole 6
"cinematic" section IS real. The operator uploaded a saved copy of
Blue Heron's own official course page
(https://blueheron.co.kr/swp/course/east/hole06) -- _HOLE6_REAL below
is transcribed verbatim from that page: Par/Hdcp/tee yardages, the
Pro Tip paragraph, and the embedded YouTube video id. These real facts
are rendered in their own clearly-tagged cards, kept visually and
textually separate from this module's mock performance stats (which
are tagged "더미 성적 데이터") so the two tiers are never conflated.

The real pipeline this page is a placeholder for:
klpga.neo_win.final_course_deep_dive.connect_course_deep_dive() (real
artifact existence check) + the real Reader collectors for
course_statistics.json / playerInfo / shotGroupList -- none of which
this module calls. A future commit wires this same layout to that real
data; nothing here should be mistaken for it in the meantime (see
STAGE_NOT_READY_META, and the small on-page preview badge in section ①).
"""
from __future__ import annotations

import math
from html import escape as _esc

from klpga.website_v2.global_navigation import inject_global_navigation
from klpga.website_v2.shell import breadcrumb_html

STAGE_NOT_READY_META = '<meta name="neo-stage-publication-ready" content="false"><meta name="neo-mock-data" content="true">'

# ---------------------------------------------------------------------------
# MOCK dataset -- see module docstring. hole/par/stars(1-5)/distance are
# the only "assigned" fields; birdie/par/bogey_plus always sum to 100,
# the five tee-shot fields always sum to 100, and the hardest-hole
# ranking by avg_rel is 18 > 2 > 11 > 8 > 16 (matches the operator's own
# example). distance (yards) is assigned per par class (par3 150-175,
# par4 380-440, par5 495-540) and sums to a plausible 6,710-yard course.
# ---------------------------------------------------------------------------
_MOCK_HOLES = [
    {"hole": 1, "par": 4, "stars": 2, "avg_rel": -0.05, "birdie": 18, "par_pct": 70, "bogey_plus": 12, "distance": 385,
     "tee": {"fairway": 62, "left_rough": 14, "right_rough": 12, "bunker": 7, "other": 5},
     "note": "오프닝홀, 버디 18%로 시작 부담이 적다"},
    {"hole": 2, "par": 3, "stars": 5, "avg_rel": 0.58, "birdie": 6, "par_pct": 58, "bogey_plus": 36, "distance": 175,
     "tee": {"fairway": 40, "left_rough": 22, "right_rough": 20, "bunker": 12, "other": 6},
     "note": "짧지만 그린이 좁아 보기 이상이 36%에 달한다"},
    {"hole": 3, "par": 4, "stars": 3, "avg_rel": 0.18, "birdie": 11, "par_pct": 63, "bogey_plus": 26, "distance": 400,
     "tee": {"fairway": 55, "left_rough": 16, "right_rough": 15, "bunker": 8, "other": 6},
     "note": "평이한 파4, 세컨샷 정확도가 스코어를 가른다"},
    {"hole": 4, "par": 5, "stars": 1, "avg_rel": -0.22, "birdie": 34, "par_pct": 58, "bogey_plus": 8, "distance": 510,
     "tee": {"fairway": 64, "left_rough": 13, "right_rough": 11, "bunker": 7, "other": 5},
     "note": "투온이 가능한 파5, 버디 기회가 34%"},
    {"hole": 5, "par": 4, "stars": 3, "avg_rel": 0.20, "birdie": 10, "par_pct": 64, "bogey_plus": 26, "distance": 395,
     "tee": {"fairway": 56, "left_rough": 15, "right_rough": 14, "bunker": 9, "other": 6},
     "note": "중간 난이도의 파4, 페어웨이 적중률 56%가 관건"},
    {"hole": 6, "par": 4, "stars": 2, "avg_rel": 0.02, "birdie": 14, "par_pct": 68, "bogey_plus": 18, "distance": 380,
     "tee": {"fairway": 60, "left_rough": 14, "right_rough": 13, "bunker": 8, "other": 5},
     "note": "보기 이상이 18%에 그치는 안정적인 홀"},
    {"hole": 7, "par": 3, "stars": 3, "avg_rel": 0.24, "birdie": 9, "par_pct": 62, "bogey_plus": 29, "distance": 160,
     "tee": {"fairway": 45, "left_rough": 20, "right_rough": 18, "bunker": 11, "other": 6},
     "note": "바람의 영향이 큰 쇼트홀"},
    {"hole": 8, "par": 4, "stars": 4, "avg_rel": 0.51, "birdie": 6, "par_pct": 55, "bogey_plus": 39, "distance": 410,
     "tee": {"fairway": 42, "left_rough": 20, "right_rough": 19, "bunker": 13, "other": 6},
     "note": "페어웨이가 좁아 벙커 비율이 13%로 가장 높다"},
    {"hole": 9, "par": 5, "stars": 2, "avg_rel": -0.10, "birdie": 28, "par_pct": 62, "bogey_plus": 10, "distance": 505,
     "tee": {"fairway": 61, "left_rough": 15, "right_rough": 12, "bunker": 7, "other": 5},
     "note": "전반 마무리 파5, 버디 기회가 28%"},
    {"hole": 10, "par": 4, "stars": 3, "avg_rel": 0.19, "birdie": 10, "par_pct": 65, "bogey_plus": 25, "distance": 390,
     "tee": {"fairway": 57, "left_rough": 15, "right_rough": 13, "bunker": 9, "other": 6},
     "note": "후반 시작홀, 평이한 파4"},
    {"hole": 11, "par": 3, "stars": 4, "avg_rel": 0.55, "birdie": 5, "par_pct": 54, "bogey_plus": 41, "distance": 150,
     "tee": {"fairway": 38, "left_rough": 22, "right_rough": 21, "bunker": 13, "other": 6},
     "note": "가장 짧은 파3이지만 보기 이상이 41%"},
    {"hole": 12, "par": 4, "stars": 3, "avg_rel": 0.15, "birdie": 12, "par_pct": 66, "bogey_plus": 22, "distance": 405,
     "tee": {"fairway": 58, "left_rough": 15, "right_rough": 14, "bunker": 8, "other": 5},
     "note": "중간 난이도의 파4"},
    {"hole": 13, "par": 5, "stars": 1, "avg_rel": -0.25, "birdie": 36, "par_pct": 57, "bogey_plus": 7, "distance": 495,
     "tee": {"fairway": 65, "left_rough": 13, "right_rough": 10, "bunker": 7, "other": 5},
     "note": "버디 기회 36%로 코스에서 가장 쉬운 홀"},
    {"hole": 14, "par": 4, "stars": 4, "avg_rel": 0.27, "birdie": 9, "par_pct": 61, "bogey_plus": 30, "distance": 415,
     "tee": {"fairway": 50, "left_rough": 18, "right_rough": 16, "bunker": 10, "other": 6},
     "note": "좁은 그린으로 보기 이상이 30%"},
    {"hole": 15, "par": 3, "stars": 2, "avg_rel": 0.01, "birdie": 15, "par_pct": 70, "bogey_plus": 15, "distance": 165,
     "tee": {"fairway": 48, "left_rough": 18, "right_rough": 17, "bunker": 11, "other": 6},
     "note": "짧은 파3, 보기 이상 15%의 평이한 홀"},
    {"hole": 16, "par": 4, "stars": 4, "avg_rel": 0.49, "birdie": 7, "par_pct": 56, "bogey_plus": 37, "distance": 420,
     "tee": {"fairway": 44, "left_rough": 19, "right_rough": 18, "bunker": 13, "other": 6},
     "note": "좁은 페어웨이로 보기 이상이 37%"},
    {"hole": 17, "par": 5, "stars": 2, "avg_rel": -0.08, "birdie": 27, "par_pct": 63, "bogey_plus": 10, "distance": 520,
     "tee": {"fairway": 62, "left_rough": 14, "right_rough": 12, "bunker": 7, "other": 5},
     "note": "버디 기회 27%의 공격 가능한 파5"},
    {"hole": 18, "par": 4, "stars": 5, "avg_rel": 0.62, "birdie": 4, "par_pct": 53, "bogey_plus": 43, "distance": 430,
     "tee": {"fairway": 39, "left_rough": 21, "right_rough": 21, "bunker": 13, "other": 6},
     "note": "이번 코스 최대 승부홀, 보기 이상이 버디의 11배"},
]

_DIFFICULTY_TIER = {1: ("쉬움", "easy"), 2: ("쉬움", "easy"), 3: ("보통", "mid"), 4: ("어려움", "hard"), 5: ("어려움", "hard")}

# ---------------------------------------------------------------------------
# REAL evidence -- transcribed verbatim from the operator-uploaded saved
# copy of Blue Heron's own official course page
# (https://blueheron.co.kr/swp/course/east/hole06, saved as
# "블루헤런E6번홀.html"). Only Hole 6 is covered because that is the only
# hole the operator provided real evidence for -- no other hole's real
# course facts/video/pro-tip are fabricated here.
# ---------------------------------------------------------------------------
_HOLE6_REAL = {
    "hole": 6,
    "course": "East",
    "par": 4,
    "hdcp": 14,
    "yards": {"Blue": 412, "White": 366, "Gold": 334, "Red": 314},
    "pro_tip": (
        "제일 높은 지역에 위치한 홀로써 블루 티에서는 레귤러 티에 심어진 나무가 "
        "티샷에 부담을 준다. 티샷을 IP지점 좌측 벙커와 우측 경사면의 벙커 사이로 "
        "공략하고 좌, 우측은 OB이므로 주의해야 한다. 그린 앞과 우측에 깊은 벙커로 "
        "둘러싸여 있어 세컨샷의 길이 조정이 중요하다."
    ),
    "youtube_id": "G33Qr32IkNU",
    "source_url": "https://blueheron.co.kr/swp/course/east/hole06",
}


def _stars(n: int) -> str:
    return "★" * n + "☆" * (5 - n)


def _course_summary():
    total_par = sum(h["par"] for h in _MOCK_HOLES)
    total_distance = sum(h["distance"] for h in _MOCK_HOLES)
    avg_rel = sum(h["avg_rel"] for h in _MOCK_HOLES) / len(_MOCK_HOLES)
    avg_birdie = sum(h["birdie"] for h in _MOCK_HOLES) / len(_MOCK_HOLES)
    avg_bogey_plus = sum(h["bogey_plus"] for h in _MOCK_HOLES) / len(_MOCK_HOLES)
    avg_stars = sum(h["stars"] for h in _MOCK_HOLES) / len(_MOCK_HOLES)
    long_iron_holes = [h for h in _MOCK_HOLES if h["par"] == 4 and h["stars"] >= 4]
    rough_impact_pct = sum(h["tee"]["left_rough"] + h["tee"]["right_rough"] for h in _MOCK_HOLES) / len(_MOCK_HOLES)
    putt_impact_pct = sum(h["bogey_plus"] for h in _MOCK_HOLES if h["stars"] >= 4) / max(1, len([h for h in _MOCK_HOLES if h["stars"] >= 4]))
    return {
        "total_par": total_par,
        "total_distance": total_distance,
        "avg_rel": avg_rel,
        "avg_birdie": avg_birdie,
        "avg_bogey_plus": avg_bogey_plus,
        "difficulty_stars": round(avg_stars),
        "rough_impact_pct": rough_impact_pct,
        "long_iron_holes": long_iron_holes,
        "putt_impact_pct": putt_impact_pct,
    }


def _top5(key: str, reverse: bool) -> list[dict]:
    return sorted(_MOCK_HOLES, key=lambda h: h[key], reverse=reverse)[:5]


def _fmt_rel(v: float) -> str:
    return f"{'+' if v >= 0 else ''}{v:.2f}"


def _glance_card(label: str, stars: int, sub: str) -> str:
    return (
        f"<div class='dd-glance-card'><p class='dd-glance-label'>{_esc(label)}</p>"
        f"<p class='dd-stars' aria-label='{stars}/5'>{_stars(stars)}</p>"
        f"<p class='dd-glance-sub'>{_esc(sub)}</p></div>"
    )


def _hole_strip() -> str:
    cells = []
    for h in _MOCK_HOLES:
        _, tier_class = _DIFFICULTY_TIER[h["stars"]]
        rough = h["tee"]["left_rough"] + h["tee"]["right_rough"]
        tip = (
            "<div class='dd-strip-tip'>"
            f"<b>{h['hole']}번홀 PAR {h['par']} · {h['distance']}yd</b>"
            f"<span>평균 {_fmt_rel(h['avg_rel'])}타 · 버디 {h['birdie']}% · 보기+ {h['bogey_plus']}% · 러프 {rough}%</span>"
            "</div>"
        )
        cells.append(
            f"<div class='dd-strip-cell dd-tier--{tier_class}' tabindex='0'>"
            f"<span class='dd-strip-hole'>{h['hole']}</span>"
            f"<span class='dd-strip-stars'>{_stars(h['stars'])}</span>"
            f"{tip}"
            "</div>"
        )
    return "<div class='dd-hole-strip'>" + "".join(cells) + "</div>"


def _bar(label: str, pct: int, css_class: str) -> str:
    return (
        f"<div class='dd-bar-row'><span class='dd-bar-label'>{_esc(label)}</span>"
        f"<div class='dd-bar-track'><div class='dd-bar-fill dd-bar--{css_class}' style='width:{pct}%'></div></div>"
        f"<span class='dd-bar-pct'>{pct}%</span></div>"
    )


def _hole_detail_card(h: dict) -> str:
    tier_label, tier_class = _DIFFICULTY_TIER[h["stars"]]
    tee = h["tee"]
    bars = (
        _bar("Fairway", tee["fairway"], "fw")
        + _bar("좌 Rough", tee["left_rough"], "rough")
        + _bar("우 Rough", tee["right_rough"], "rough")
        + _bar("벙커", tee["bunker"], "bunker")
        + _bar("기타", tee["other"], "other")
    )
    return (
        f"<article class='dd-hole-card' id='hole-{h['hole']}'>"
        f"<header class='dd-hole-card-head'><h3>{h['hole']}번홀 <span class='dd-par-tag'>PAR {h['par']} · {h['distance']}yd</span></h3>"
        f"<span class='dd-tier-badge dd-tier--{tier_class}'>{_stars(h['stars'])} {tier_label}</span></header>"
        f"<p class='dd-hole-avg'>평균 {_fmt_rel(h['avg_rel'])}타</p>"
        f"<div class='dd-hole-stats'>"
        f"<span>버디 <b>{h['birdie']}%</b></span><span>파 <b>{h['par_pct']}%</b></span>"
        f"<span>보기 이상 <b>{h['bogey_plus']}%</b></span></div>"
        f"<div class='dd-tee-dist'>{bars}</div>"
        f"<p class='dd-hole-note'>“{_esc(h['note'])}”</p>"
        f"</article>"
    )


def _tee_shot_card(h: dict) -> str:
    tee = h["tee"]
    bars = (
        _bar("Fairway", tee["fairway"], "fw")
        + _bar("좌 Rough", tee["left_rough"], "rough")
        + _bar("우 Rough", tee["right_rough"], "rough")
        + _bar("벙커", tee["bunker"], "bunker")
        + _bar("기타", tee["other"], "other")
    )
    return (
        f"<article class='dd-tee-card'><p class='dd-tee-card-hole'>{h['hole']}번홀 "
        f"<span class='dd-par-tag'>PAR {h['par']}</span></p>{bars}</article>"
    )


def _hole_matrix() -> str:
    rows = []
    for h in _MOCK_HOLES:
        tier_label, _ = _DIFFICULTY_TIER[h["stars"]]
        rough = h["tee"]["left_rough"] + h["tee"]["right_rough"]
        rows.append(
            "<tr>"
            f"<td data-label='홀'>{h['hole']}</td>"
            f"<td data-label='PAR'>{h['par']}</td>"
            f"<td data-label='난이도'>{_stars(h['stars'])} {tier_label}</td>"
            f"<td data-label='평균'>{_fmt_rel(h['avg_rel'])}</td>"
            f"<td data-label='버디%'>{h['birdie']}</td>"
            f"<td data-label='파%'>{h['par_pct']}</td>"
            f"<td data-label='보기+%'>{h['bogey_plus']}</td>"
            f"<td data-label='Fairway%'>{h['tee']['fairway']}</td>"
            f"<td data-label='Rough%'>{rough}</td>"
            f"<td data-label='벙커%'>{h['tee']['bunker']}</td>"
            f"<td data-label='비거리'>{h['distance']}</td>"
            "</tr>"
        )
    thead = (
        "<tr><th>홀</th><th>PAR</th><th>난이도</th><th>평균</th><th>버디%</th><th>파%</th>"
        "<th>보기+%</th><th>Fairway%</th><th>Rough%</th><th>벙커%</th><th>비거리</th></tr>"
    )
    return (
        "<div class='table-scroll'><table class='data-table dd-matrix-table'>"
        f"<thead>{thead}</thead><tbody>{''.join(rows)}</tbody></table></div>"
    )


def _top5_list(title: str, items: list[dict], value_key: str, value_fmt) -> str:
    rows = []
    for i, h in enumerate(items):
        rough = h["tee"]["left_rough"] + h["tee"]["right_rough"]
        rows.append(
            "<li>"
            f"<div class='dd-top5-row'><span class='dd-top5-rank'>{i + 1}</span>"
            f"<span class='dd-top5-hole'>{h['hole']}번홀</span>"
            f"<span class='dd-top5-value'>{value_fmt(h[value_key])}</span></div>"
            f"<p class='dd-top5-detail'>평균 {_fmt_rel(h['avg_rel'])}타 · 버디 {h['birdie']}% · "
            f"보기+ {h['bogey_plus']}% · 러프 {rough}% · 비거리 {h['distance']}yd</p>"
            "</li>"
        )
    return f"<div class='dd-top5-card'><h3>{_esc(title)}</h3><ol class='dd-top5-list'>{''.join(rows)}</ol></div>"


def _polar(cx: float, cy: float, r: float, angle_deg: float) -> tuple[float, float]:
    rad = math.radians(angle_deg)
    return cx + r * math.sin(rad), cy - r * math.cos(rad)


def _radar_chart(dims: list[tuple[str, int, str]]) -> str:
    cx = cy = 120.0
    radius = 82.0
    n = len(dims)
    step = 360.0 / n
    rings = []
    for ring in range(1, 6):
        r = radius * ring / 5
        pts = " ".join(f"{_polar(cx, cy, r, i * step)[0]:.1f},{_polar(cx, cy, r, i * step)[1]:.1f}" for i in range(n))
        rings.append(f"<polygon points='{pts}' class='dd-radar-ring'/>")
    axis_lines = "".join(
        f"<line x1='{cx}' y1='{cy}' x2='{_polar(cx, cy, radius, i * step)[0]:.1f}' y2='{_polar(cx, cy, radius, i * step)[1]:.1f}' class='dd-radar-axis'/>"
        for i in range(n)
    )
    data_pts = [_polar(cx, cy, radius * val / 5, i * step) for i, (_, val, _) in enumerate(dims)]
    poly = " ".join(f"{x:.1f},{y:.1f}" for x, y in data_pts)
    dots = "".join(f"<circle cx='{x:.1f}' cy='{y:.1f}' r='3.5' class='dd-radar-dot'/>" for x, y in data_pts)
    labels = "".join(
        f"<text x='{_polar(cx, cy, radius + 22, i * step)[0]:.1f}' y='{_polar(cx, cy, radius + 22, i * step)[1]:.1f}' "
        f"class='dd-radar-label' text-anchor='middle' dominant-baseline='middle'>{_esc(label)}</text>"
        for i, (label, _, _) in enumerate(dims)
    )
    return (
        "<svg viewBox='0 0 240 240' class='dd-radar-svg' role='img' aria-label='코스 DNA 레이더 차트'>"
        f"{''.join(rings)}{axis_lines}"
        f"<polygon points='{poly}' class='dd-radar-shape'/>{dots}{labels}"
        "</svg>"
    )


def _radar_legend(dims: list[tuple[str, int, str]]) -> str:
    rows = "".join(
        f"<li><b>{_esc(label)}</b><span>{val}/5 · {_esc(sub)}</span></li>"
        for label, val, sub in dims
    )
    return f"<ul class='dd-radar-legend'>{rows}</ul>"


_STYLE = """
<style>
/* Uses this site's own real theme tokens (neo-site.css :root --ink/
--muted/--surface/--panel/--line/--green/--gold/--red) -- never an
invented dark-theme palette; every text color below is explicit
rather than relying on an inherited default, since several site-wide
defaults (e.g. --ink on no background) silently become invisible once
placed on this module's own card backgrounds otherwise. */
.dd-wrap{display:flex;flex-direction:column;gap:1.75rem}
.dd-preview-badge{display:inline-block;font-size:.72rem;font-weight:700;letter-spacing:.02em;color:#7a5610;background:#f3e6c8;border-radius:.7rem;padding:.15rem .6rem;margin-top:.4rem}
.dd-section-title{font-size:1.15rem;font-weight:800;margin:0 0 .8rem;color:var(--ink)}
.dd-glance-grid{display:grid;grid-template-columns:repeat(2,1fr);gap:.6rem}
@media (min-width:720px){.dd-glance-grid{grid-template-columns:repeat(3,1fr)}}
.dd-glance-card{background:var(--surface);border:1px solid var(--line);border-radius:.5rem;padding:.9rem}
.dd-glance-label{font-size:.8rem;color:var(--muted);margin:0 0 .35rem}
.dd-stars{font-size:1.1rem;letter-spacing:.1em;color:var(--gold);margin:0 0 .35rem}
.dd-glance-sub{font-size:.8rem;color:var(--ink);margin:0}
.dd-oneliner{font-size:1rem;font-weight:650;line-height:1.55;padding:1rem;border-left:3px solid var(--green);background:var(--green-2);border-radius:0 .5rem .5rem 0;color:var(--ink)}
.dd-hole-strip{display:grid;grid-template-columns:repeat(6,1fr);gap:.4rem}
@media (min-width:720px){.dd-hole-strip{grid-template-columns:repeat(9,1fr)}}
.dd-strip-cell{position:relative;display:flex;flex-direction:column;align-items:center;gap:.25rem;padding:.5rem .25rem;border-radius:.4rem;font-size:.68rem}
.dd-strip-hole{font-weight:800;font-size:.8rem;color:var(--ink)}
.dd-strip-stars{color:var(--gold);font-size:.68rem;letter-spacing:.05em}
.dd-strip-tip{position:absolute;left:50%;bottom:calc(100% + 6px);transform:translateX(-50%);min-width:9.5rem;padding:.5rem .6rem;border-radius:.5rem;background:var(--ink);color:var(--paper);font-size:.68rem;line-height:1.45;opacity:0;pointer-events:none;transition:opacity .12s;z-index:5;text-align:left}
.dd-strip-tip b{display:block;margin-bottom:.2rem;font-size:.7rem}
.dd-strip-cell:hover .dd-strip-tip,.dd-strip-cell:focus-within .dd-strip-tip,.dd-strip-cell:focus .dd-strip-tip{opacity:1}
.dd-tier--easy{background:var(--green-2)}
.dd-tier--mid{background:#f3e6c8}
.dd-tier--hard{background:#f3e5e2}
.dd-legend{display:flex;gap:.9rem;font-size:.75rem;color:var(--muted);margin-top:.6rem}
.dd-legend-dot{display:inline-block;width:.55rem;height:.55rem;border-radius:50%;margin-right:.25rem;vertical-align:middle}
.dd-legend-dot--easy{background:var(--green)}.dd-legend-dot--mid{background:var(--gold)}.dd-legend-dot--hard{background:var(--red)}
.dd-hole-grid{display:grid;grid-template-columns:1fr;gap:.75rem}
@media (min-width:720px){.dd-hole-grid{grid-template-columns:repeat(2,1fr)}}
@media (min-width:1100px){.dd-hole-grid{grid-template-columns:repeat(3,1fr)}}
.dd-tee-grid{display:grid;grid-template-columns:1fr;gap:.6rem}
@media (min-width:720px){.dd-tee-grid{grid-template-columns:repeat(2,1fr)}}
@media (min-width:1100px){.dd-tee-grid{grid-template-columns:repeat(3,1fr)}}
.dd-tee-card{background:var(--surface);border:1px solid var(--line);border-radius:.5rem;padding:.75rem}
.dd-tee-card-hole{font-size:.8rem;font-weight:700;margin:0 0 .5rem;color:var(--ink)}
.dd-hole-card{background:var(--surface);border:1px solid var(--line);border-radius:.5rem;padding:.9rem}
.dd-hole-card-head{display:flex;align-items:center;justify-content:space-between;gap:.5rem;margin-bottom:.4rem}
.dd-hole-card-head h3{font-size:.95rem;margin:0;color:var(--ink)}
.dd-par-tag{font-size:.7rem;color:var(--muted);font-weight:600}
.dd-tier-badge{font-size:.7rem;font-weight:700;padding:.1rem .45rem;border-radius:.7rem;white-space:nowrap;color:var(--ink)}
.dd-hole-avg{font-size:.95rem;font-weight:800;margin:.25rem 0;color:var(--ink)}
.dd-hole-stats{display:flex;gap:.75rem;font-size:.78rem;color:var(--ink);margin-bottom:.6rem}
.dd-tee-dist{display:flex;flex-direction:column;gap:.25rem;margin-bottom:.5rem}
.dd-bar-row{display:grid;grid-template-columns:3.2rem 1fr 2.2rem;align-items:center;gap:.4rem;font-size:.68rem;color:var(--muted)}
.dd-bar-track{height:.45rem;background:var(--panel);border-radius:.3rem;overflow:hidden}
.dd-bar-fill{height:100%;border-radius:.3rem}
.dd-bar--fw{background:var(--green)}.dd-bar--rough{background:var(--gold)}.dd-bar--bunker{background:var(--red)}.dd-bar--other{background:#9aa39c}
.dd-hole-note{font-size:.78rem;color:var(--muted);font-style:normal;margin:0}
.dd-matrix-table th:nth-child(2),.dd-matrix-table td:nth-child(2){text-align:right}
.dd-matrix-table th:nth-child(3),.dd-matrix-table td:nth-child(3){text-align:left}
.dd-top5-grid{display:grid;grid-template-columns:1fr;gap:.75rem}
@media (min-width:720px){.dd-top5-grid{grid-template-columns:repeat(2,1fr)}}
.dd-top5-card{background:var(--surface);border:1px solid var(--line);border-radius:.5rem;padding:.9rem}
.dd-top5-card h3{font-size:.88rem;margin:0 0 .6rem;color:var(--ink)}
.dd-top5-list{list-style:none;margin:0;padding:0;display:flex;flex-direction:column;gap:.25rem}
.dd-top5-list li{display:flex;flex-direction:column;gap:.25rem;padding:.4rem 0;border-bottom:1px solid var(--line)}
.dd-top5-list li:last-child{border-bottom:0}
.dd-top5-row{display:grid;grid-template-columns:1.4rem 1fr auto;align-items:center;gap:.5rem;font-size:.82rem;color:var(--ink)}
.dd-top5-rank{font-weight:800;color:var(--green)}
.dd-top5-value{font-weight:700;color:var(--ink)}
.dd-top5-detail{margin:0;font-size:.72rem;color:var(--muted)}
.dd-neo-list{list-style:none;margin:0;padding:0;display:flex;flex-direction:column;gap:.6rem}
.dd-neo-list li{font-size:.9rem;line-height:1.55;padding:.75rem;border-radius:.5rem;background:var(--surface);border:1px solid var(--line);color:var(--ink)}
.dd-neo-tag{display:inline-block;margin-right:.5rem;padding:.1rem .45rem;border-radius:.6rem;background:var(--green-2);color:var(--green);font-size:.68rem;font-weight:800;vertical-align:middle}
.dd-quality-grid{display:grid;grid-template-columns:repeat(2,1fr);gap:.6rem}
@media (min-width:720px){.dd-quality-grid{grid-template-columns:repeat(5,1fr)}}
.dd-quality-card{text-align:center;background:var(--surface);border:1px solid var(--line);border-radius:.5rem;padding:.75rem}
.dd-quality-label{font-size:.75rem;color:var(--muted);margin:0 0 .35rem}
.dd-quality-value{font-size:.85rem;font-weight:800;margin:0;color:var(--ink)}
.dd-quality-value--pass{color:var(--green)}
.dd-dna-grid{display:flex;flex-direction:column;align-items:center;gap:1rem}
@media (min-width:720px){.dd-dna-grid{flex-direction:row;align-items:center}}
.dd-radar-svg{width:100%;max-width:280px;height:auto;flex-shrink:0}
.dd-radar-ring{fill:none;stroke:var(--line);stroke-width:1}
.dd-radar-axis{stroke:var(--line);stroke-width:1}
.dd-radar-shape{fill:var(--green-2);stroke:var(--green);stroke-width:2;fill-opacity:.7}
.dd-radar-dot{fill:var(--green)}
.dd-radar-label{font-size:9px;fill:var(--ink);font-weight:700}
.dd-radar-legend{list-style:none;margin:0;padding:0;display:grid;grid-template-columns:repeat(2,1fr);gap:.5rem .9rem;width:100%}
.dd-radar-legend li{display:flex;flex-direction:column;gap:.1rem}
.dd-radar-legend b{font-size:.8rem;color:var(--ink)}
.dd-radar-legend span{color:var(--muted);font-size:.72rem}
.dd-cine-stage{display:grid;gap:1rem}
@media (min-width:860px){.dd-cine-stage{grid-template-columns:1.1fr 1fr;align-items:start}}
.dd-cine-video-wrap{position:sticky;top:5rem;border-radius:.6rem;overflow:hidden;aspect-ratio:16/9;background:#000}
.dd-cine-video{width:100%;height:100%;border:0;display:block}
.dd-cine-scroll{display:flex;flex-direction:column;gap:1rem}
.dd-cine-card{background:var(--surface);border:1px solid var(--line);border-radius:.6rem;padding:1rem;opacity:0;transform:translateY(28px);transition:opacity .5s ease,transform .5s ease}
.dd-cine-card.is-visible{opacity:1;transform:translateY(0)}
.dd-cine-tag{display:inline-block;margin-bottom:.4rem;padding:.15rem .5rem;border-radius:.6rem;background:var(--green-2);color:var(--green);font-size:.68rem;font-weight:800}
.dd-cine-tag--mock{background:#f3e6c8;color:#7a5610}
.dd-cine-card h3{margin:.2rem 0;font-size:1rem;color:var(--ink)}
.dd-cine-fact{margin:.2rem 0;font-size:.85rem;color:var(--ink)}
.dd-cine-tip{margin:.2rem 0;font-size:.85rem;color:var(--ink);line-height:1.65;font-style:normal}
.dd-cine-source{margin:.4rem 0 0;font-size:.7rem;color:var(--muted)}
.dd-cine-source a{color:var(--green)}
</style>
"""

_CINE_SCRIPT = """
<script>
(function(){
  var cards = document.querySelectorAll('.dd-cine-card');
  if(!cards.length){ return; }
  if(!('IntersectionObserver' in window)){
    cards.forEach(function(c){ c.classList.add('is-visible'); });
    return;
  }
  var io = new IntersectionObserver(function(entries){
    entries.forEach(function(entry){
      if(entry.isIntersecting){
        entry.target.classList.add('is-visible');
        io.unobserve(entry.target);
      }
    });
  }, {threshold: 0.2});
  cards.forEach(function(c){ io.observe(c); });
})();
</script>
"""


def _hole6_cinematic_section() -> str:
    r = _HOLE6_REAL
    mock = next(h for h in _MOCK_HOLES if h["hole"] == 6)
    rough = mock["tee"]["left_rough"] + mock["tee"]["right_rough"]
    yards_line = " · ".join(f"{tee} {yd}yd" for tee, yd in r["yards"].items())
    return (
        "<section class='panel dd-cine' id='hole6-cinematic'>"
        "<h2 class='dd-section-title'>6번홀 코스 영상 · 블루헤런 공식</h2>"
        "<div class='dd-cine-stage'>"
        "<div class='dd-cine-video-wrap'>"
        f"<iframe class='dd-cine-video' src='https://www.youtube.com/embed/{r['youtube_id']}' "
        f"title='블루헤런 {r['course']} {r['hole']}번홀 코스 영상' loading='lazy' "
        "allow='accelerometer; autoplay; encrypted-media; gyroscope; picture-in-picture' allowfullscreen></iframe>"
        "</div>"
        "<div class='dd-cine-scroll'>"
        "<article class='dd-cine-card'>"
        "<span class='dd-cine-tag'>실제 코스 정보 · 블루헤런 공식 홈페이지</span>"
        f"<h3>{r['course']} {r['hole']}번홀</h3>"
        f"<p class='dd-cine-fact'>PAR {r['par']} · Hdcp {r['hdcp']} · {yards_line}</p>"
        f"<p class='dd-cine-source'>출처: <a href='{r['source_url']}' rel='noopener'>{_esc(r['source_url'])}</a></p>"
        "</article>"
        "<article class='dd-cine-card'>"
        "<span class='dd-cine-tag'>Pro Tip · 블루헤런 공식</span>"
        f"<p class='dd-cine-tip'>“{_esc(r['pro_tip'])}”</p>"
        "</article>"
        "<article class='dd-cine-card'>"
        "<span class='dd-cine-tag dd-cine-tag--mock'>더미 성적 데이터 · 레이아웃 미리보기</span>"
        f"<p class='dd-cine-fact'>평균 {_fmt_rel(mock['avg_rel'])}타 · 버디 {mock['birdie']}% · 보기 이상 {mock['bogey_plus']}%</p>"
        f"<p class='dd-cine-fact'>Fairway {mock['tee']['fairway']}% · 좌우 Rough {rough}% · 벙커 {mock['tee']['bunker']}%</p>"
        "</article>"
        "</div>"
        "</div>"
        "</section>"
    )


def render_deep_dive_mock_page(*, tournament_name: str, game_code: str) -> str:
    s = _course_summary()
    hardest5 = _top5("avg_rel", reverse=True)
    easiest5 = _top5("avg_rel", reverse=False)
    birdie5 = _top5("birdie", reverse=True)
    risk5 = _top5("bogey_plus", reverse=True)

    dims = [
        ("코스 난이도", s["difficulty_stars"], f"평균 스코어 {_fmt_rel(s['avg_rel'])}타"),
        ("버디 기회", 2, f"평균 버디율 {s['avg_birdie']:.1f}%"),
        ("실수 위험", 4, f"평균 보기 이상 {s['avg_bogey_plus']:.1f}%"),
        ("러프 영향", 3, f"좌·우 러프 진입 {s['rough_impact_pct']:.1f}%"),
        ("롱아이언 중요도", 4, f"4성 이상 파4 {len(s['long_iron_holes'])}개 홀"),
        ("퍼트 영향", 3, f"4성 이상 홀 보기 이상 {s['putt_impact_pct']:.1f}%"),
    ]
    glance = "".join(_glance_card(label, stars, sub) for label, stars, sub in dims)
    radar_svg = _radar_chart(dims)
    radar_legend = _radar_legend(dims)

    oneliner = (
        f"이번 코스는 보기 이상 비율이 {s['avg_bogey_plus']:.1f}%로 버디 비율 {s['avg_birdie']:.1f}%보다 "
        f"높아, 버디보다 보기를 줄이는 선수가 유리했다."
    )

    hole_grid = "".join(_hole_detail_card(h) for h in _MOCK_HOLES)
    tee_shot_grid = "".join(_tee_shot_card(h) for h in _MOCK_HOLES)
    hole_matrix = _hole_matrix()

    top5_section = (
        "<div class='dd-top5-grid'>"
        + _top5_list("가장 어려운 홀 TOP5", hardest5, "avg_rel", lambda v: f"{_fmt_rel(v)}타")
        + _top5_list("가장 쉬운 홀 TOP5", easiest5, "avg_rel", lambda v: f"{_fmt_rel(v)}타")
        + _top5_list("버디 기회 TOP5", birdie5, "birdie", lambda v: f"{v}%")
        + _top5_list("실수 위험 TOP5", risk5, "bogey_plus", lambda v: f"{v}%")
        + "</div>"
    )

    hardest_avg = sum(h["avg_rel"] for h in hardest5) / 5
    fairway_bottom3 = sorted(_MOCK_HOLES, key=lambda h: h["tee"]["fairway"])[:3]
    fb3_holes = "·".join(str(h["hole"]) for h in fairway_bottom3)
    fb3_avg_bogey = sum(h["bogey_plus"] for h in fairway_bottom3) / 3
    neo_notes = [
        f"18번홀은 버디 {_MOCK_HOLES[17]['birdie']}%, 보기 이상 {_MOCK_HOLES[17]['bogey_plus']}%로, "
        f"보기 이상이 버디보다 약 {_MOCK_HOLES[17]['bogey_plus'] // _MOCK_HOLES[17]['birdie']}배 많이 발생했다.",
        f"가장 어려운 5개 홀(18·2·11·8·16)의 평균 스코어는 {_fmt_rel(hardest_avg)}타로, "
        f"코스 전체 평균 {_fmt_rel(s['avg_rel'])}타보다 {hardest_avg - s['avg_rel']:.2f}타 더 어려웠다.",
        f"쇼트홀(2·7·11·15번) 중 2번·11번홀의 보기 이상 비율이 36%·41%로, "
        f"나머지 쇼트홀(7번 29%, 15번 15%)보다 뚜렷하게 높았다.",
        f"Fairway 적중률이 가장 낮은 3개 홀({fb3_holes}번)의 평균 보기 이상 비율은 {fb3_avg_bogey:.1f}%로, "
        f"코스 전체 평균 {s['avg_bogey_plus']:.1f}%보다 {fb3_avg_bogey - s['avg_bogey_plus']:.1f}%p 높다.",
    ]
    neo_section = "<ul class='dd-neo-list'>" + "".join(
        f"<li><span class='dd-neo-tag'>근거 {i + 1}</span>{_esc(n)}</li>" for i, n in enumerate(neo_notes)
    ) + "</ul>"

    quality = "".join(
        f"<div class='dd-quality-card'><p class='dd-quality-label'>{label}</p>"
        f"<p class='dd-quality-value{' dd-quality-value--pass' if ok else ''}'>{value}</p></div>"
        for label, value, ok in [
            ("출처", "KLPGA", False), ("수집", "PASS", True), ("검증", "PASS", True),
            ("라운드", "PASS", True), ("플레이어", "107/107", True),
        ]
    )

    breadcrumb = breadcrumb_html(tournament_name, f"/tournaments/2026/{game_code}/pre/", "딥 다이브")
    hole6_cinematic = _hole6_cinematic_section()

    body = (
        "<!doctype html><html lang=\"ko\"><head>"
        f"{STAGE_NOT_READY_META}"
        "<meta charset=\"utf-8\">"
        "<meta name=\"viewport\" content=\"width=device-width,initial-scale=1\">"
        f"<title>NEO GOLF DATA · {tournament_name} 딥 다이브</title>"
        "<link rel=\"stylesheet\" href=\"/assets/neo-site.css\">"
        "<link rel=\"stylesheet\" href=\"/assets/neo.css\">"
        f"{_STYLE}"
        "</head><body>"
        "<main>"
        f"{breadcrumb}"
        "<section class=\"page-head\">"
        f"<p class=\"kicker\">{tournament_name} · 블루헤런</p>"
        "<h1>코스 딥 다이브</h1>"
        "<span class='dd-preview-badge'>레이아웃 미리보기 — 더미 데이터 (6번홀 코스 정보/영상은 실제)</span>"
        "</section>"
        "<div class='dd-wrap'>"

        f"{hole6_cinematic}"

        "<section class='panel' id='glance'>"
        "<h2 class='dd-section-title'>코스 한눈에 보기</h2>"
        f"<div class='dd-glance-grid'>{glance}</div>"
        "</section>"

        "<section class='panel' id='course-dna'>"
        "<h2 class='dd-section-title'>Course DNA</h2>"
        f"<div class='dd-dna-grid'>{radar_svg}{radar_legend}</div>"
        "</section>"

        "<section class='panel' id='oneliner'>"
        "<h2 class='dd-section-title'>한 줄 분석</h2>"
        f"<p class='dd-oneliner'>{_esc(oneliner)}</p>"
        "</section>"

        "<section class='panel' id='difficulty-strip'>"
        "<h2 class='dd-section-title'>18홀 난이도</h2>"
        f"{_hole_strip()}"
        "<p class='dd-legend'>"
        "<span><span class='dd-legend-dot dd-legend-dot--easy'></span>쉬움</span>"
        "<span><span class='dd-legend-dot dd-legend-dot--mid'></span>보통</span>"
        "<span><span class='dd-legend-dot dd-legend-dot--hard'></span>어려움</span>"
        "</p>"
        "</section>"

        "<section class='panel' id='hole-detail'>"
        "<h2 class='dd-section-title'>홀별 상세 분석</h2>"
        f"<div class='dd-hole-grid'>{hole_grid}</div>"
        "</section>"

        "<section class='panel' id='tee-shot'>"
        "<h2 class='dd-section-title'>티샷 분포</h2>"
        f"<div class='dd-tee-grid'>{tee_shot_grid}</div>"
        "</section>"

        "<section class='panel' id='hole-matrix'>"
        "<h2 class='dd-section-title'>18홀 Matrix</h2>"
        f"{hole_matrix}"
        "</section>"

        "<section class='panel' id='top5'>"
        "<h2 class='dd-section-title'>TOP5 비교</h2>"
        f"{top5_section}"
        "</section>"

        "<section class='panel' id='neo-analysis'>"
        "<h2 class='dd-section-title'>NEO 코스 분석</h2>"
        f"{neo_section}"
        "</section>"

        "<section class='panel' id='data-quality'>"
        "<h2 class='dd-section-title'>DATA QUALITY</h2>"
        f"<div class='dd-quality-grid'>{quality}</div>"
        "</section>"

        "</div>"
        "</main>"
        "<footer class=\"site-footer\"><div class=\"site-footer__inner\">"
        "<p class=\"site-footer__copyright\">© 2026 NEO GOLF DATA. All Rights Reserved.</p>"
        "</div></footer>"
        f"{_CINE_SCRIPT}"
        "</body></html>"
    )
    return inject_global_navigation(
        body, active_section="tournaments",
        nav_overrides={"tournaments": f"/tournaments/2026/{game_code}/pre/"},
    )


def is_mock_page(html: str) -> bool:
    return 'name="neo-mock-data" content="true"' in html
