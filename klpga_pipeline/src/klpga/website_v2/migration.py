"""Structured production-candidate generator for NEO GOLF DATA."""
from __future__ import annotations

import hashlib
import json
import re
import shutil
from html import escape
from html.parser import HTMLParser
from pathlib import Path

from klpga.evidence import load_and_verify_manifest
from klpga.website_v2.analytics import (accessible_series_table, aggregate_holes, bar_chart_svg,
    checkpoint_series, classify_hole_score, hole_leaders, line_chart_svg, multi_line_chart_svg, parse_rank)
from klpga.website_v2.shell import STAGES, STATIC_DIR, TournamentMetadata, render_page


class CandidateBuildError(RuntimeError):
    pass


class _Tables(HTMLParser):
    def __init__(self) -> None:
        super().__init__(); self.tables=[]; self.in_table=False; self.in_cell=False
        self.headers=[]; self.rows=[]; self.row=[]; self.parts=[]; self.header=False

    def handle_starttag(self, tag, attrs):
        if tag == "table" and not self.in_table:
            self.in_table=True; self.headers=[]; self.rows=[]
        elif self.in_table and tag == "tr": self.row=[]
        elif self.in_table and tag in ("th", "td"):
            self.in_cell=True; self.header=tag == "th"; self.parts=[]

    def handle_data(self, data):
        if self.in_cell: self.parts.append(data)

    def handle_endtag(self, tag):
        if self.in_table and tag in ("th", "td") and self.in_cell:
            value=" ".join("".join(self.parts).split()); (self.headers if self.header else self.row).append(value); self.in_cell=False
        elif self.in_table and tag == "tr" and self.row:
            self.rows.append(self.row); self.row=[]
        elif tag == "table" and self.in_table:
            self.tables.append((self.headers,self.rows)); self.in_table=False


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write(path: Path, text: str) -> Path:
    path.parent.mkdir(parents=True,exist_ok=True); path.write_text(text+"\n",encoding="utf-8",newline="\n"); return path


def _table(source: Path) -> tuple[list[str], list[list[str]]]:
    parser=_Tables(); parser.feed(source.read_text(encoding="utf-8"))
    if not parser.tables: raise CandidateBuildError(f"forecast table missing: {source}")
    return parser.tables[-1]


def _pct(value: str | None) -> float | None:
    if value is None: return None
    match=re.search(r"[-+]?\d+(?:\.\d+)?", value)
    return float(match.group()) if match else None


def _snapshots(repo_root: Path, records: dict, data: dict) -> dict[str,list[dict]]:
    snapshots: dict[str,list[dict]]={}
    pre=json.loads((repo_root/records["pre"]["source_artifact"]).read_text(encoding="utf-8"))
    snapshots["PRE"]=[{"player":x["player_name_display"],"rank":x["rank"],"win":round(x["win_probability"]*100,3)} for x in pre["predictions"]]
    for stage in ("R1","R2","R3"):
        headers, rows=_table(repo_root/records[stage.lower()]["source_artifact"]); normalized=[]
        for row in rows:
            item=dict(zip(headers,row)); player=item.get("선수")
            if not player: continue
            win=item.get("우승확률") or item.get("WIN")
            normalized.append({
                "player":player, "rank":parse_rank(item.get("순위") or item.get("현재 순위")),
                "rank_display":item.get("순위") or item.get("현재 순위"),
                "score_to_par":item.get("스코어") or item.get("합계"), "round_score_to_par":item.get("3R"),
                "total_strokes":item.get("합계") if stage=="R2" else None,
                "win":_pct(win), "top5":_pct(item.get("TOP5")), "top10":_pct(item.get("TOP10")), "top20":_pct(item.get("TOP20")),
                "change":_pct(item.get("R2→R3 WIN 변화")), "cut":_pct(item.get("컷 통과확률")),
            })
        snapshots[stage]=normalized
    override=data["validated_display_records"]["post_r3_shin_dain_win_probability"]
    shin=next((row for row in snapshots["R3"] if row["player"]=="신다인"),None)
    if shin is None: raise CandidateBuildError("Shin Dain missing from POST-R3 snapshot")
    shin["win"]=float(override.rstrip("%"))
    return snapshots


def _player_series(snapshots: dict, player: str, stages: tuple[str,...], field: str) -> list[dict]:
    values={}
    for stage in stages:
        row=next((item for item in snapshots.get(stage,[]) if item["player"]==player),None)
        values[stage]=None if row is None else row.get(field)
    return checkpoint_series(list(stages),values)


def _cta(meta: TournamentMetadata, location: str, stage: str="overview") -> str:
    return ('<a class="primary-action" href="/deep-dive/" data-deep-dive-interest '
            f'data-tournament-id="{escape(meta.tournament_id)}" data-tournament-slug="{escape(meta.slug)}" data-stage="{escape(stage)}" '
            f'data-cta-location="{escape(location)}" data-deep-dive-id="kg-r3-leaders" data-content-type="tournament-analysis">NEO DEEP DIVE</a>')


def _result_card(result: dict) -> str:
    rounds="".join(f'<span><small>R{i}</small><strong>{score}</strong></span>' for i,score in enumerate(result["rounds"],1))
    return ('<article class="result-card"><div><span class="label-chip">결과</span><p class="result-name">'+escape(result["winner"])+"</p><p>우승</p></div>"
            f'<div><p class="result-score">{result["total"]} <small>({result["to_par"]})</small></p><div class="round-grid">{rounds}</div></div></article>')


def _watch(rows: list[dict], count: int=4) -> str:
    leaders=sorted((row for row in rows if row["win"] is not None),key=lambda row:(-row["win"],row["player"]))[:count]
    return '<div class="watch-grid">'+"".join(f'<article><span>{i}</span><h3>{escape(row["player"])}</h3><strong>{row["win"]:.2f}%</strong></article>' for i,row in enumerate(leaders,1))+'</div>'


def _forecast_table(rows: list[dict], stage: str) -> str:
    columns=[("rank_display","순위"),("player","선수"),("score_to_par","스코어"),("win","WIN")]
    if stage in ("R2","R3"): columns += [("top5","TOP 5"),("top10","TOP 10"),("top20","TOP 20")]
    head="".join(f'<th scope="col">{label}</th>' for _,label in columns)
    body=[]
    for row in rows:
        cells=[]
        for key,_ in columns:
            value=row.get(key)
            if key in ("win","top5","top10","top20") and value is not None: value=f"{value:.2f}%"
            cells.append(f'<td>{escape("—" if value is None else str(value))}</td>')
        body.append('<tr>'+''.join(cells)+'</tr>')
    return f'<div class="table-scroll"><table class="data-table" data-forecast-table><thead><tr>{head}</tr></thead><tbody>{"".join(body)}</tbody></table></div>'


def _evidence(record: dict, url: str|None=None) -> str:
    provenance=record["publication_provenance"]; timestamp=provenance.get("publication_timestamp") or provenance.get("commit_timestamp") or "정확한 시각 없음"
    link=f'<a href="{url}">원본 기록 보기</a>' if url else ""
    return ('<details class="evidence-detail"><summary>방법론 / 원본 기록</summary>'
            f'<dl><dt>예측 확정 시점</dt><dd>{escape(timestamp)}</dd><dt>모델</dt><dd>{escape(record["model_version"])}</dd>'
            f'<dt>분류</dt><dd>{escape(provenance["classification"])}</dd><dt>SHA-256</dt><dd><code>{escape(record["sha256"])}</code></dd></dl>{link}</details>')


def _chart_block(title: str, player: str, series: list[dict], unit: str, invert: bool=False) -> str:
    svg=line_chart_svg(title=title,player=player,series=series,unit=unit,invert=invert)
    if not svg: return ""
    return f'<article class="chart-card"><header><p class="section-label">{escape(title)}</p><h3>{escape(player)}</h3></header><div class="chart-scroll">{svg}</div>{accessible_series_table(player,title,series,unit)}</article>'


def _official_final_sections(official: dict) -> str:
    sg=next(row for row in official["sg"]["tournament"] if row["player"]=="신다인")
    sg_values={"SG 티샷":sg["off_the_tee"],"SG 어프로치":sg["approach"],"SG 그린주변":sg["around_green"],"SG 퍼팅":sg["putting"]}
    leaderboard_rows=[]
    for row in official["leaderboard"]:
        rounds="".join(f'<td>{"—" if value is None else value}</td>' for value in row["rounds"])
        leaderboard_rows.append(f'<tr><td>{escape(row["rank"])}</td><td>{escape(row["player"])}</td>{rounds}<td>{"—" if row["total"] is None else row["total"]}</td><td>{escape(row["to_par"] or row["status"])}</td></tr>')
    holes=aggregate_holes(official["holes"]); leaders=hole_leaders(holes)
    hole_points=checkpoint_series([str(x["hole"]) for x in holes],{str(x["hole"]):x["average_vs_par"] for x in holes})
    hole_chart=line_chart_svg(title="홀별 평균 타수",player="전체 선수",series=hole_points,unit="",invert=False)
    shin_holes=[row for row in official["holes"] if row["player"]=="신다인" and row["round"]==4]
    counts={label:sum(classify_hole_score(r["strokes"],r["par"])==label for r in shin_holes) for label in ("Eagle","Birdie","Par","Bogey","Double Bogey","Triple Bogey+")}
    explanations={"SG 티샷":f'티샷으로 필드보다 약 {abs(sg["off_the_tee"]):.1f}타를 {"벌었습니다" if sg["off_the_tee"]>=0 else "잃었습니다"}.',"SG 어프로치":f'아이언 샷으로 필드보다 약 {abs(sg["approach"]):.1f}타를 {"벌었습니다" if sg["approach"]>=0 else "잃었습니다"}.',"SG 그린주변":f'그린 주변에서 약 {abs(sg["around_green"]):.1f}타를 {"벌었습니다" if sg["around_green"]>=0 else "잃었습니다"}.',"SG 퍼팅":f'퍼팅으로 약 {abs(sg["putting"]):.1f}타를 {"벌었습니다" if sg["putting"]>=0 else "잃었습니다"}.'}
    return ('<section class="product-section"><p class="section-label">WHY · 대회 누적 경기력</p><h2>그렇다면 신다인은 어디에서 타수를 벌었을까?</h2><p class="sg-explainer"><b>SG</b>는 다른 선수들과 비교해 어디에서 타수를 벌거나 잃었는지를 보여줍니다. +는 벌고, −는 잃었다는 뜻입니다.</p>'
            f'<div class="sg-summary"><strong>전체 경기력 {sg["total"]:+.2f} <small>SG 전체</small></strong><span>티샷부터 그린까지 {sg["tee_to_green"]:+.2f}</span></div>{bar_chart_svg("신다인 대회 누적 SG",sg_values)}'
            '<div class="sg-meanings">'+''.join(f'<article><b>{escape(label.replace("SG ",""))} {sg_values[label]:+.2f}</b><span>{escape(explanations[label])}</span><small>{escape(label)}</small></article>' for label in sg_values)+'</div><p class="note">KLPGA 공식 대회 누적값입니다. NEO 확률 모델의 입력이 아니라 실제 경기력 분석입니다.</p></section>'
            '<section class="product-section"><p class="section-label">홀 분석</p><h2>18홀은 어떻게 플레이됐나</h2><div class="chart-full">'+hole_chart+'</div>'
            f'<div class="movement-grid"><article><span>가장 어려웠던 홀</span><strong>{leaders["hardest"]}번</strong></article><article><span>가장 쉬웠던 홀</span><strong>{leaders["easiest"]}번</strong></article><article><span>버디가 가장 많았던 홀</span><strong>{leaders["most_birdies"]}번</strong></article></div></section>'
            '<section class="product-section"><p class="section-label">PERFORMANCE · FINAL 라운드 · 신다인 스코어 구성</p><h2>64타는 어떻게 만들어졌을까?</h2><div class="composition-grid">'+''.join(f'<div><span>{escape(k)}</span><strong>{v}</strong></div>' for k,v in counts.items())+'</div><p class="note">신다인의 R4 공식 홀별 스코어 18개를 분류한 실제 횟수입니다.</p></section>'
            '<section class="product-section"><div class="section-heading"><div><p class="section-label">공식 최종 리더보드</p><h2>전체 119명</h2></div></div><div class="table-scroll"><table class="data-table"><thead><tr><th>순위</th><th>선수</th><th>R1</th><th>R2</th><th>R3</th><th>R4</th><th>합계</th><th>파 대비</th></tr></thead><tbody>'+''.join(leaderboard_rows)+'</tbody></table></div></section>')


def _context_and_next(official: dict) -> str:
    contenders=official["leaderboard"][:7]
    cards=''.join(f'<article><span>{escape(row["rank"])}</span><b>{escape(row["player"])}</b><strong>{row["rounds"][3]}</strong><small>{escape(row["to_par"])}</small></article>' for row in contenders)
    return ('<section class="product-section"><p class="section-label">경쟁자 맥락</p><h2>신다인이 줄이는 동안, 필드도 움직였습니다.</h2><p>선수는 자신의 샷을 관리하지만 순위는 경쟁자들의 동시 변화로 만들어집니다. 상위권의 FINAL 라운드와 최종 스코어를 함께 봅니다.</p><div class="competitor-grid">'+cards+'</div></section>'
            '<section class="product-section probability-explainer"><p class="section-label">예측과 결과</p><h2>7.47%였는데 우승했습니다.<br>확률과 실제 결과는 같은 개념이 아닙니다.</h2><p>7.47%는 R3 시점의 정보와 모델 상태에서 우승이라는 결과가 가능한 결과 분포의 일부였다는 뜻입니다. 낮은 확률은 불가능하다는 뜻이 아닙니다. NEO는 FINAL을 본 뒤 R3를 고치지 않습니다.</p></section>'
            '<section class="product-section next-panel"><p class="section-label">NEXT · 앞으로 무엇을 볼까?</p><h2>한 대회로 영구적인 강점이나 약점을 정하지 않습니다.</h2><p>이번 대회에서는 공식 SG와 홀별 기록으로 경기 내용을 설명할 수 있습니다. 반복되는 방향을 판단하려면 동일 범위의 5개 대회, 10개 대회, 시즌 데이터가 필요합니다.</p><div class="monitor-grid"><span>5개 대회<small>최근 변화</small></span><span>10개 대회<small>반복 패턴</small></span><span>시즌<small>지속성</small></span><span>장기<small>기준선</small></span></div><p class="note">검증된 비교 표본이 쌓일 때까지 영구적 약점, 코스 적합도, 향후 성과를 단정하지 않습니다.</p></section>')


def _home(data,meta,snapshots):
    r3=snapshots["R3"]; rises=[x for x in r3 if x["change"] is not None]; rise=max(rises,key=lambda x:x["change"]); fall=min(rises,key=lambda x:x["change"])
    return ('<section class="product-hero completed-hero"><div><p class="section-label">대회 종료 · FINAL 분석</p><h1>신다인은 어떻게<br>우승까지 갔을까?</h1><p>결과부터 우승까지의 변화, 실제 경기력까지 KLPGA 공식 데이터로 이어서 봅니다.</p>'
            f'<div class="actions"><a class="primary-action" href="{meta.stage_url("final")}">FINAL 분석 보기</a><a class="secondary-action" href="{meta.stage_url("r3")}">마지막 예측 보기</a></div></div>'
            '<aside class="hero-data"><span>우승</span><strong>신다인</strong><p>271 (-17) · 70 → 70 → 67 → 64</p></aside></section>'
            '<section class="product-section"><div class="section-heading"><div><p class="section-label">최근 대회</p><h2>'+escape(meta.display_name)+'</h2></div><span class="state-chip">대회 종료</span></div>'
            '<div class="latest-grid"><div><span>우승</span><strong>신다인</strong><small>271 (-17)</small></div><div><span>R3 종료 후 우승 확률</span><strong>7.47%</strong><small>→ 실제 우승</small></div><a href="'+meta.base_url+'">대회 분석 보기</a></div></section>'
            '<section class="product-section"><div class="section-heading"><div><p class="section-label">최근 데이터</p><h2>R3 주요 우승 확률</h2></div><a href="'+meta.stage_url('r3')+'">전체 예측 보기</a></div>'+_watch(r3)+
            f'<div class="movement-grid"><article><span>R2 → R3 가장 큰 상승</span><strong>{escape(rise["player"])}</strong><b>+{rise["change"]:.2f}%p</b></article><article><span>R2 → R3 가장 큰 하락</span><strong>{escape(fall["player"])}</strong><b>{fall["change"]:.2f}%p</b></article><article><span>FINAL 핵심 데이터</span><strong>신다인</strong><b>64타 · 우승</b></article></div></section>'
            '<section class="product-section deep-question"><p class="section-label">DEEP DIVE</p><h2>같은 공동선두인데<br>왜 15.04%와 0.24%였을까?</h2><div class="compare-strip"><span>노승희 <b>15.04%</b></span><span>박혜준 <b>11.56%</b></span><span>신다인 <b>7.47%</b></span><span>유아현 <b>0.24%</b></span></div>'+_cta(meta,'home')+'</section>')


def _tournaments(data,meta):
    return ('<section class="page-head"><p class="section-label">대회</p><h1>KLPGA 대회 분석</h1><p>라운드별 예측 변화와 공식 결과를 함께 봅니다.</p></section><section class="product-section">'
            f'<a class="tournament-row" href="{meta.base_url}"><div><span class="state-chip">대회 종료</span><h2>{escape(meta.display_name)}</h2><p>{escape(data["dates"]["display"])} · {escape(data["course"]["name"])}</p></div><div><span>우승</span><strong>신다인</strong><small>271 (-17)</small></div></a></section>')


def _archive(meta):
    return ('<section class="page-head"><p class="section-label">예측 기록</p><h1>결과가 나오기 전의 기록</h1><p>정해진 시점에 확정된 우승 확률을 대회별로 확인합니다.</p></section><section class="product-section">'
            f'<article class="archive-card"><h2>{escape(meta.display_name)}</h2><div class="stage-links"><a href="{meta.stage_url("pre")}">PRE</a><a href="{meta.stage_url("r1")}">R1</a><a href="{meta.stage_url("r2")}">R2</a><a href="{meta.stage_url("r3")}">R3</a><a href="{meta.stage_url("final")}">FINAL</a></div></article></section>')


def _overview(data,meta):
    course=data["course"]
    return (f'<section class="tournament-summary"><div><p class="section-label">대회 개요</p><h2>예측에서 결과까지</h2></div><dl>'
            f'<div><dt>기간</dt><dd>{escape(data["dates"]["display"])}</dd></div>'
            f'<div><dt>코스</dt><dd>{escape(course["name"])} · {escape(course["routing"])}</dd></div>'
            f'<div><dt>기준파</dt><dd>PAR {course["par"]}</dd></div><div><dt>상태</dt><dd>대회 종료</dd></div></dl></section>'
            '<section class="product-section outcome-story"><p class="section-label">예측 → 실제 결과</p><div class="outcome-grid"><div><span>POST-R3</span><h2>신다인</h2><strong>7.47%</strong><p>최종 라운드 전 우승 확률</p><a href="'+meta.stage_url('r3')+'">R3 예측 보기</a></div><div class="outcome-arrow" aria-hidden="true">→</div><div><span>FINAL</span><h2>우승</h2><strong>271 (-17)</strong><p>70 · 70 · 67 · 64</p><a href="'+meta.stage_url('final')+'">FINAL 분석 보기</a></div></div><p class="note">7.47%는 우승자 지목이 아니라 당시 가능한 결과에 부여된 확률입니다.</p></section>'
            '<section class="product-section"><p class="section-label">대회 흐름</p><h2>예측 확정 시점</h2><div class="timeline"><a href="'+meta.stage_url('pre')+'"><b>PRE</b><span>대회 전</span></a><a href="'+meta.stage_url('r1')+'"><b>R1</b><span>1R 종료</span></a><a href="'+meta.stage_url('r2')+'"><b>R2</b><span>2R 종료</span></a><a href="'+meta.stage_url('r3')+'"><b>R3</b><span>3R 종료</span></a><a href="'+meta.stage_url('final')+'"><b>FINAL</b><span>공식 결과</span></a></div></section>')


def _pre(meta,rows,record):
    table_rows=[{"rank_display":r["rank"],"player":r["player"],"score_to_par":None,"win":r["win"]} for r in rows]
    return ('<section class="stage-head"><p class="section-label">PRE · 예측 확정</p><h2>대회 시작 전 우승 확률</h2><p>이 자료는 당시 실행을 바탕으로 보존된 재구성 아카이브이며 원본 출판 캡처가 아닙니다.</p></section>'
            '<section class="product-section"><p class="section-label">NEO WATCH</p><h2>대회 전 주요 확률</h2>'+_watch(rows)+'</section>'
            '<section class="product-section"><div class="section-heading"><div><p class="section-label">전체 예측</p><h2>PRE 우승 확률</h2></div></div>'+_forecast_table(table_rows,"PRE")+'</section>'
            '<section class="product-section evidence-section">'+_evidence(record)+'</section>')


def _stage(meta,stage,rows,snapshots,record,url):
    titles={"R1":"1라운드 종료 후 예측","R2":"2라운드 종료 후 예측","R3":"3라운드 종료 후 예측"}
    subtitles={"R1":"2라운드 시작 전 확정된 NEO의 우승 확률입니다.","R2":"3라운드 시작 전 확정된 NEO의 우승 확률입니다.","R3":"최종 라운드를 앞둔 NEO의 우승 확률입니다."}
    leader=sorted(rows,key=lambda r:(-(r["win"] or -1),r["player"]))[0]["player"]
    checkpoints=tuple(x for x in ("PRE","R1","R2","R3") if ("PRE","R1","R2","R3").index(x) <= ("PRE","R1","R2","R3").index(stage))
    series=_player_series(snapshots,leader,checkpoints,"win")
    return (f'<section class="stage-head"><p class="section-label">{stage} · 예측 확정</p><h2>{titles[stage]}</h2><p>{subtitles[stage]} 예측은 다음 라운드 시작 전에 확정됐으며 결과가 나온 뒤 수정하지 않았습니다.</p></section>'
            '<section class="product-section"><p class="section-label">NEO WATCH</p><h2>주요 우승 확률</h2>'+_watch(rows)+'</section>'
            '<section class="product-section"><p class="section-label">확률 변화</p><h2>선두 확률의 이동</h2><div class="charts-grid">'+_chart_block("우승 확률 변화",leader,series,"%")+'</div></section>'
            f'<section class="product-section" data-forecast-stage="{stage.lower()}"><div class="section-heading"><div><p class="section-label">전체 예측</p><h2>선수별 확률</h2></div><div class="forecast-tools"><button type="button" data-row-limit="10">TOP 10</button><button type="button" data-row-limit="20">TOP 20</button><button type="button" data-row-limit="all" aria-pressed="true">전체</button></div></div>'+_forecast_table(rows,stage)+'</section>'
            '<section class="product-section deep-link"><h2>같은 스코어, 다른 확률</h2>'+_cta(meta,stage.lower()+"_forecast",stage.lower())+'</section>'
            '<section class="product-section evidence-section">'+_evidence(record,url)+'</section>')


def _final(data,meta,snapshots,availability,official):
    shin="신다인"; win=_player_series(snapshots,shin,("PRE","R1","R2","R3"),"win")
    rank=_player_series(snapshots,shin,("R1","R2","R3"),"rank")+[{"stage":"FINAL","value":1}]
    scores=checkpoint_series(["R1","R2","R3","R4"],dict(zip(("R1","R2","R3","R4"),data["final_result"]["rounds"])))
    r3row=next(row for row in snapshots["R3"] if row["player"]==shin)
    return ('<section class="stage-head result-head"><p class="section-label">FINAL · 결과</p><h2>대회가 끝난 뒤, 예측을 다시 봅니다.</h2><p>공식 결과와 마지막 확정 예측을 분리해 비교합니다.</p></section><section class="product-section">'+_result_card(data["final_result"])+'</section>'
            '<section class="product-section outcome-story"><p class="section-label">예측 → 실제 결과</p><h2>신다인은 어떻게 우승했나</h2><div class="comparison-table"><div><span>R3 순위</span><strong>'+escape(r3row["rank_display"] or "—")+'</strong></div><div><span>R3 우승 확률</span><strong>7.47%</strong></div><div><span>FINAL 순위</span><strong>1</strong></div><div><span>FINAL 스코어</span><strong>271 (-17)</strong></div></div><p class="note">‘예측보다 높은 결과’는 마지막 확정 확률이 100%가 아니었던 선수가 공식 우승을 기록했다는 사실만 설명합니다. 선수 간 임의 순위는 만들지 않습니다.</p></section>'
            '<section class="product-section final-trends"><p class="section-label">JOURNEY</p><h2>신다인의 우승까지,<br>숫자는 어떻게 변했나</h2><p class="trend-summary">PRE 1.90% → R1 0.34% → R2 0.50% → R3 7.47%</p>'+_chart_block("우승 가능성의 변화",shin,win,"%")+'<p class="chart-takeaway">마지막 예측에서도 우승은 여러 가능한 결과 중 하나였습니다.</p><p class="trend-summary">R1 39위 → R2 18위 → R3 T1 → FINAL 1위</p>'+_chart_block("리더보드의 변화",shin,rank,"위",True)+'<p class="chart-takeaway">39위에서 시작해 매 라운드 순위를 끌어올렸습니다.</p><p class="trend-summary">70 → 70 → 67 → 64</p>'+_chart_block("라운드 스코어의 변화",shin,scores,"타")+'<p class="chart-takeaway">마지막 두 라운드에서 스코어를 연속으로 줄였습니다.</p></section>'
            +_official_final_sections(official)+_context_and_next(official)+
            '<section class="product-section deep-link"><h2>예측 차이를 더 깊게 보기</h2>'+_cta(meta,"final_analysis","final")+'</section>')


def _deep(meta,snapshots,official,pre_archive):
    players=("노승희","박혜준","신다인","유아현")
    trends={player:_player_series(snapshots,player,("PRE","R1","R2","R3"),"win") for player in players}
    features={row["player_name_display"]:row for row in pre_archive["predictions"] if row["player_name_display"] in players}
    sg_rows={row["player"]:row for row in official["sg"]["r3"] if row["player"] in players}
    model_rows=''.join(f'<tr><td>{p}</td><td>{features[p]["prior_avg_round_score_to_par"]:+.2f}</td><td>{features[p]["prior_recent_form_10"]:+.1f}</td><td>T1 · -9</td><td>{trends[p][-1]["value"]:.2f}%</td></tr>' for p in players)
    sg_table=''.join(f'<tr><td>{p}</td><td>{sg_rows[p]["total"]:+.2f}</td><td>{sg_rows[p]["tee_to_green"]:+.2f}</td><td>{sg_rows[p]["off_the_tee"]:+.2f}</td><td>{sg_rows[p]["approach"]:+.2f}</td><td>{sg_rows[p]["around_green"]:+.2f}</td><td>{sg_rows[p]["putting"]:+.2f}</td></tr>' for p in players)
    composition=[]
    for player in players:
        rows=[r for r in official["holes"] if r["player"]==player and r["round"]<=3]
        counts={label:sum(classify_hole_score(r["strokes"],r["par"])==label for r in rows) for label in ("Eagle","Birdie","Par","Bogey","Double Bogey","Triple Bogey+")}
        composition.append('<tr><td>'+player+'</td>'+''.join(f'<td>{counts[label]}</td>' for label in counts)+'</tr>')
    return ('<section class="page-head"><p class="section-label">DEEP DIVE</p><h1>같은 스코어인데<br>왜 우승 확률은 다를까?</h1><p>R3 종료 시점 공동 선두 네 명의 실제 확정 확률을 비교합니다.</p></section><section class="product-section">'
            '<div class="comparison-table four"><div><span>노승희 · T1 · -9</span><strong>15.04%</strong></div><div><span>박혜준 · T1 · -9</span><strong>11.56%</strong></div><div><span>신다인 · T1 · -9</span><strong>7.47%</strong></div><div><span>유아현 · T1 · -9</span><strong>0.24%</strong></div></div>'
            '<h2>무엇이 15.04%와 0.24%를 갈라놓았나?</h2></section><section class="product-section"><p class="section-label">LAYER A · NEO MODEL</p><h2>모델이 실제로 사용한 입력</h2><div class="table-scroll"><table class="data-table"><thead><tr><th>선수</th><th>대회 전 평균 라운드 대비 파</th><th>최근 10개 대회 폼</th><th>R3 결과</th><th>우승 확률</th></tr></thead><tbody>'+model_rows+'</tbody></table></div><div class="chart-full">'+multi_line_chart_svg(title="네 선수 우승 확률 변화",series_by_player=trends)+'</div><p class="note">SG는 이 모델 버전의 입력이 아닙니다. 누락된 체크포인트는 연결하거나 재구성하지 않습니다.</p></section>'
            '<section class="product-section"><p class="section-label">LAYER B · PERFORMANCE ANALYSIS</p><h2>같은 -9, 경기 내용도 같았을까?</h2><p class="sg-explainer"><b>SG</b>는 필드와 비교해 어느 영역에서 타수를 벌거나 잃었는지를 보여줍니다. +는 벌고, −는 잃었다는 뜻입니다.</p><div class="table-scroll"><table class="data-table"><thead><tr><th>선수</th><th>SG 전체</th><th>티샷→그린</th><th>티샷</th><th>어프로치</th><th>그린주변</th><th>퍼팅</th></tr></thead><tbody>'+sg_table+'</tbody></table></div><p class="note">KLPGA 공식 R3 단일 라운드 SG입니다. 경기 내용을 설명하지만 NEO 확률의 원인으로 사용하지 않습니다.</p><h3>R3까지 스코어 구성</h3><div class="table-scroll"><table class="data-table"><thead><tr><th>선수</th><th>이글 이하</th><th>버디</th><th>파</th><th>보기</th><th>더블보기</th><th>트리플보기+</th></tr></thead><tbody>'+''.join(composition)+'</tbody></table></div>'
            f'<a class="secondary-action" href="{meta.stage_url("r3")}">R3 전체 예측 보기</a></section>')


def _about():
    return ('<section class="page-head compact"><p class="section-label">NEO 소개</p><h1>맞히는 것보다,<br>설명하는 것.</h1><p>NEO GOLF DATA는 미래를 맞히기 위해 숫자를 만드는 것이 아니라, 불확실한 골프를 조금 더 이해하기 위해 숫자를 사용합니다.</p></section><section class="product-section philosophy"><h2>예측은 가능성을, 결과는 실제로 일어난 하나의 사건을 기록합니다.</h2><p>우리는 결과가 나온 뒤 예측을 고치지 않습니다. 대신 왜 실제 결과가 달라졌는지를 다시 데이터로 분석합니다.</p></section>'
            '<section class="principles"><article><b>01</b><h2>정해진 시점에 확정</h2><p>예측은 다음 라운드가 시작되기 전에 확정합니다.</p></article><article><b>02</b><h2>결과 뒤에 수정하지 않음</h2><p>그래서 그때 무엇을 예상했는지 그대로 남습니다.</p></article><article><b>03</b><h2>공식 결과와 비교</h2><p>예측과 실제 결과의 차이를 데이터로 살펴봅니다.</p></article></section>'
            '<section class="product-section" id="methodology"><details class="evidence-detail" open><summary>방법론 / 원본 기록</summary><p>대회 전 예측은 검증된 과거 평균 라운드 스코어와 최근 경기력 특성을 사용했습니다. 라운드 업데이트는 완료된 공식 결과와 고정된 PRE 소스로 남은 라운드를 시뮬레이션했습니다.</p><p>업데이트는 라운드 종료 후 이뤄지며 실시간 예측을 주장하지 않습니다. 원본 출판 자료, 확정 시점, 모델 버전, 체크섬은 각 예측 페이지에서 확인할 수 있습니다.</p></details></section>')


def build_beta001_candidate(content_path: Path, manifest_path: Path, repo_root: Path, output_root: Path) -> tuple[Path,...]:
    data=json.loads(Path(content_path).read_text(encoding="utf-8")); manifest=json.loads(Path(manifest_path).read_text(encoding="utf-8"))
    availability_path=Path(content_path).with_name("beta001_availability.json"); availability=json.loads(availability_path.read_text(encoding="utf-8"))
    official_path=Path(content_path).with_name("kg_2026080001_official.json"); official=json.loads(official_path.read_text(encoding="utf-8"))
    before=load_and_verify_manifest(manifest_path,repo_root); meta=TournamentMetadata.from_dict(data["tournament"])
    if set(meta.published_stages)!=set(STAGES): raise CandidateBuildError("all tournament stages required")
    forbidden={"winner","rounds","total","to_par","official_result","final_result"}
    if any(forbidden & set(record) for record in data["forecast_stages"].values()): raise CandidateBuildError("FINAL data leaked into forecast record")
    expected={"record_type":"RESULT","winner":"신다인","player_code":"9135","rounds":[70,70,67,64],"total":271,"to_par":"-17"}
    if data["final_result"]!=expected: raise CandidateBuildError("validated FINAL result changed")
    if data["validated_display_records"]["post_r3_shin_dain_win_probability"]!="7.47%": raise CandidateBuildError("validated POST-R3 probability changed")
    records={record["stage"].lower():record for record in manifest["stages"]}; snapshots=_snapshots(repo_root,records,data); output_root=Path(output_root)
    pages={
        output_root/"index.html":render_page(title="홈",active_section="home",body_html=_home(data,meta,snapshots)),
        output_root/"tournaments"/"index.html":render_page(title="대회",active_section="tournaments",body_html=_tournaments(data,meta)),
        output_root/"predictions"/"index.html":render_page(title="예측 기록",active_section="predictions",body_html=_archive(meta)),
        output_root/"deep-dive"/"index.html":render_page(title="DEEP DIVE",active_section="deep-dive",body_html=_deep(meta,snapshots,official,json.loads((repo_root/records["pre"]["source_artifact"]).read_text(encoding="utf-8")))),
        output_root/"about"/"index.html":render_page(title="NEO 소개",active_section="about",body_html=_about()),
        output_root/"tournaments"/str(meta.year)/meta.slug/"index.html":render_page(title=meta.display_name,active_section="tournaments",body_html=_overview(data,meta),tournament=meta,current_stage="overview"),
        output_root/"tournaments"/str(meta.year)/meta.slug/"pre"/"index.html":render_page(title=f"{meta.display_name} PRE",active_section="tournaments",body_html=_pre(meta,snapshots["PRE"],records["pre"]),tournament=meta,current_stage="pre"),
        output_root/"tournaments"/str(meta.year)/meta.slug/"final"/"index.html":render_page(title=f"{meta.display_name} FINAL",active_section="tournaments",body_html=_final(data,meta,snapshots,availability,official),tournament=meta,current_stage="final")}
    for stage in ("r1","r2","r3"):
        pages[output_root/"tournaments"/str(meta.year)/meta.slug/stage/"index.html"]=render_page(title=f"{meta.display_name} {stage.upper()}",active_section="tournaments",body_html=_stage(meta,stage.upper(),snapshots[stage.upper()],snapshots,records[stage],f"/protected/beta001/{stage}.html"),tournament=meta,current_stage=stage)
    written=[_write(path,html) for path,html in pages.items()]
    assets=output_root/"assets"; assets.mkdir(parents=True,exist_ok=True)
    for name in ("neo-site.css","neo-site.js"):
        dest=assets/name; shutil.copyfile(STATIC_DIR/name,dest); written.append(dest)
    data_dir=output_root/"data"; data_dir.mkdir(parents=True,exist_ok=True); dest=data_dir/"availability.json"; shutil.copyfile(availability_path,dest); written.append(dest)
    official_dest=data_dir/"kg_2026080001_official.json"; shutil.copyfile(official_path,official_dest); written.append(official_dest)
    protected=output_root/"protected"/"beta001"; protected.mkdir(parents=True,exist_ok=True)
    for stage in ("r1","r2","r3"):
        source=repo_root/records[stage]["source_artifact"]; destination=protected/f"{stage}.html"; shutil.copyfile(source,destination)
        if _sha(destination)!=records[stage]["sha256"]: raise CandidateBuildError("protected evidence bytes changed")
        written.append(destination)
    if load_and_verify_manifest(manifest_path,repo_root)!=before: raise CandidateBuildError("protected evidence changed")
    return tuple(written)
