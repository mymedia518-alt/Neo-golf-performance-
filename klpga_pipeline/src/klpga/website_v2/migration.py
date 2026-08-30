"""BETA #001 candidate migration from immutable evidence and structured records."""
from __future__ import annotations

import hashlib
import json
import shutil
from html import escape
from html.parser import HTMLParser
from pathlib import Path

from klpga.evidence import load_and_verify_manifest
from klpga.website_v2.shell import STAGE_LABELS, STAGES, STATIC_DIR, TournamentMetadata, render_page


class CandidateBuildError(RuntimeError):
    pass


class _Tables(HTMLParser):
    def __init__(self) -> None:
        super().__init__(); self.tables = []; self.table = False; self.cell = False
        self.headers = []; self.rows = []; self.row = []; self.parts = []; self.header = False

    def handle_starttag(self, tag, attrs):
        if tag == "table" and not self.table:
            self.table = True; self.headers = []; self.rows = []
        elif self.table and tag == "tr": self.row = []
        elif self.table and tag in ("th", "td"):
            self.cell = True; self.header = tag == "th"; self.parts = []

    def handle_data(self, data):
        if self.cell: self.parts.append(data)

    def handle_endtag(self, tag):
        if self.table and tag in ("th", "td") and self.cell:
            value = " ".join("".join(self.parts).split())
            (self.headers if self.header else self.row).append(value); self.cell = False
        elif self.table and tag == "tr" and self.row:
            self.rows.append(self.row); self.row = []
        elif tag == "table" and self.table:
            self.tables.append((self.headers, self.rows)); self.table = False


def _sha(path: Path) -> str:
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    return digest


def _write(path: Path, text: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text + "\n", encoding="utf-8", newline="\n")
    return path


def _cta(meta: TournamentMetadata, location: str, stage: str = "overview") -> str:
    return ('<a class="deep-dive-cta" href="/deep-dive/" data-deep-dive-interest '
            f'data-tournament-id="{escape(meta.tournament_id)}" data-tournament-slug="{escape(meta.slug)}" '
            f'data-stage="{escape(stage)}" data-cta-location="{escape(location)}" '
            'data-deep-dive-id="beta001-r3-leaders" data-content-type="tournament-analysis">Explore Deep Dive</a>')


def _result(result: dict) -> str:
    rounds = "".join(f'<span><small>R{i}</small><br><strong>{score}</strong></span>' for i, score in enumerate(result["rounds"], 1))
    return ('<div class="result-card"><div><span class="status-label">RESULT</span>'
            f'<p class="result-card__winner">{escape(result["winner"])}</p><p>Official winner</p></div>'
            f'<div><div class="result-card__score">{result["total"]} ({result["to_par"]})</div><div class="rounds">{rounds}</div></div></div>')


def _home(data, meta):
    return ('<section class="hero-v2 hero-v2--home"><p class="kicker">NEO GOLF DATA</p>'
            '<h1>골프는 결과로 끝나지만<br>NEO는 결과가 나오기 전을 기록합니다.</h1>'
            '<p>NEO는 KLPGA 대회 데이터를 바탕으로 정해진 라운드 시점마다 우승 확률을 추정하고, 이후 검증된 공식 결과와 함께 비교합니다.</p>'
            f'<div class="hero-actions"><a class="deep-dive-cta" href="{meta.base_url}">최근 대회 보기</a><a class="text-link" href="/about/">NEO 알아보기</a></div></section>'
            '<section class="section-v2"><div class="section-v2__head"><div><p class="kicker">Latest tournament</p>'
            f'<h2>{escape(meta.display_name)}</h2></div><span class="status-label">COMPLETE</span></div><p>BETA #{meta.beta_number} · {escape(data["dates"]["display"])}</p>'
            f'<p><a class="text-link" href="{meta.base_url}">Open tournament overview</a></p></section>'
            '<section class="section-v2"><p class="kicker">What you can see</p><h2>예측이 결과를 만나기까지</h2><p>PRE부터 R3까지 당시 시점의 확률을 보고, FINAL에서 공식 결과와 비교할 수 있습니다.</p>'
            '<div class="route-list">' + "".join(f'<a href="{meta.stage_url(s)}">{STAGE_LABELS[s]}</a>' for s in STAGES) + '</div></section>'
            '<section class="section-v2"><p class="kicker">Latest result</p><h2>Official winner</h2>' + _result(data["final_result"]) + '</section>'
            '<section class="section-v2"><p class="kicker">Deep Dive</p><h2>같은 스코어, 다른 확률</h2><p>리더보드 너머에서 확률이 달라지는 이유를 살펴봅니다.</p>' + _cta(meta, "home") + '</section>'
            '<section class="section-v2 trust-note"><p class="kicker">Methodology / trust</p><h2>예측은 결과가 나온 뒤 바꾸지 않습니다.</h2><p>Forecasts frozen in time. Results kept separate.</p><a class="text-link" href="/about/">How NEO works</a></section>')


def _index(data, meta):
    return ('<section class="hero-v2"><p class="kicker">Tournament archive</p><h1>Completed tournaments</h1><p>라운드별 예측과 공식 결과를 한 흐름 안에서 확인합니다.</p></section>'
            f'<section class="section-v2"><article class="data-card"><span class="status-label">COMPLETE</span><h2><a href="{meta.base_url}">{escape(meta.display_name)}</a></h2>'
            f'<p>BETA #{meta.beta_number} · {escape(data["dates"]["display"])}</p><p>Winner {escape(data["final_result"]["winner"])} · 271 (-17)</p></article></section>')


def _overview(data, meta):
    p = data["validated_display_records"]["post_r3_shin_dain_win_probability"]
    timeline = "".join(f'<a href="{meta.stage_url(s)}"><strong>{STAGE_LABELS[s]}</strong><span>{"RESULT" if s == "final" else "FROZEN FORECAST"}</span></a>' for s in STAGES if s != "overview")
    return ('<section class="section-v2 overview-lead"><p class="kicker">Forecast → Result</p><h2>확률이 결과를 만나는 순간</h2><div class="comparison-card"><div><span class="status-label">POST-R3 FORECAST</span>'
            f'<p>POST-R3에서 신다인의 우승 확률은 <strong>{p}</strong>였다.</p><a class="text-link" href="{meta.stage_url("r3")}">View R3 forecast</a></div>'
            f'<div class="comparison-arrow" aria-hidden="true">→</div><div><span class="status-label">OFFICIAL RESULT</span><p>그리고 최종 결과는 <strong>우승</strong>이었다.<br>271 (-17) · 70 / 70 / 67 / 64</p><a class="text-link" href="{meta.stage_url("final")}">View final result</a></div></div>'
            '<p class="plain-trust">이 확률은 우승자 지목이 아닙니다. 당시의 전망과 이후의 공식 결과를 나란히 봅니다.</p></section>'
            f'<section class="section-v2"><div class="section-v2__head"><div><p class="kicker">Tournament overview</p><h2>{escape(data["dates"]["display"])}</h2></div><span class="status-label">COMPLETE</span></div></section>'
            f'<section class="section-v2"><p class="kicker">Stage timeline</p><h2>Forecast → result</h2><div class="timeline">{timeline}</div></section>'
            '<section class="section-v2 evidence-summary"><p class="kicker">Evidence</p><h2>예측은 결과 뒤에 바꾸지 않습니다.</h2><p>원본 출판 자료와 검증 정보는 각 예측 페이지에서 확인할 수 있습니다.</p></section>'
            '<section class="section-v2"><p class="kicker">Deep Dive</p><h2>확률의 차이를 더 살펴보기</h2>' + _cta(meta, "tournament_overview") + '</section>')


def _pre(source, record):
    archive = json.loads(source.read_text(encoding="utf-8"))
    rows = "".join(f'<tr><td>{x["rank"]}</td><td>{escape(x["player_name_display"])}</td><td>{escape(x["player_code"])}</td><td>{x["win_probability"]*100:.3f}%</td></tr>' for x in archive["predictions"])
    return ('<section class="section-v2"><p class="kicker">PRE FORECAST · FROZEN</p><h2>Pre-tournament win probabilities</h2><p>당시 실행을 바탕으로 보존된 재구성 아카이브이며, 원본 출판 캡처가 아닙니다.</p>'
            f'<div class="table-scroll"><table class="evidence-table"><thead><tr><th>Rank</th><th>Player</th><th>Code</th><th>Win probability</th></tr></thead><tbody>{rows}</tbody></table></div></section>'
            '<section class="section-v2 evidence-reference"><p class="kicker">Archive evidence</p><h2>재구성 자료의 범위</h2><p>RECONSTRUCTED ARCHIVE EVIDENCE · not an original publication capture.</p>'
            f'<details><summary>Technical provenance</summary><p>Prediction {escape(record["prediction_id"])} · cutoff {escape(record["data_cutoff"])}</p></details></section>')


def _table(source):
    parser = _Tables(); parser.feed(source.read_text(encoding="utf-8"))
    if not parser.tables: raise CandidateBuildError(f"no forecast table in {source}")
    return parser.tables[-1]


def _forecast(stage, config, record, source, evidence_url, meta):
    headers, rows = _table(source); override = config.get("validated_display_override")
    if override:
        pi, vi = headers.index(override["player_column"]), headers.index(override["value_column"])
        matches = [r for r in rows if len(r) > max(pi, vi) and r[pi] == override["player"]]
        if len(matches) != 1: raise CandidateBuildError("invalid validated display override")
        matches[0][vi] = override["value"]
    head = "".join(f'<th scope="col">{escape(x)}</th>' for x in headers)
    body = "".join('<tr>' + "".join(f'<td>{escape(x)}</td>' for x in row) + '</tr>' for row in rows)
    return (f'<section class="section-v2 forecast-stage" data-forecast-stage="{stage.lower()}"><p class="kicker">{escape(config["round_label"])} FORECAST · FROZEN</p><h2>{escape(config["title_ko"])}</h2><p>{escape(config["context_ko"])}</p>'
            '<div class="forecast-tools" aria-label="Forecast table display"><button type="button" data-row-limit="10">TOP 10</button><button type="button" data-row-limit="20">TOP 20</button><button type="button" data-row-limit="all" aria-pressed="true">ALL</button></div>'
            f'<div class="table-scroll"><table class="evidence-table forecast-table" data-forecast-table><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table></div>'
            f'<div class="forecast-followup"><p>라운드 종료 시점에 고정된 확률입니다. 이후 결과로 다시 쓰지 않았습니다.</p>{_cta(meta, stage.lower()+"_forecast", stage.lower())}</div></section>'
            f'<section class="section-v2 evidence-reference"><p class="kicker">Original publication evidence</p><h2>Frozen historical source</h2><a class="text-link" href="{evidence_url}">View original evidence</a>'
            f'<details><summary>Technical verification</summary><p>SHA-256 verified · {record["sha256"]}</p></details></section>')


def _final(data, meta):
    p = data["validated_display_records"]["post_r3_shin_dain_win_probability"]
    return ('<section class="section-v2"><p class="kicker">FINAL · RESULT</p><h2>Official final result</h2><p>FINAL은 공식 결과 기록이며 예측 단계가 아닙니다.</p>' + _result(data["final_result"]) + '</section>'
            f'<section class="section-v2 evaluation-block"><p class="kicker">Forecast → Result</p><h2>어제 NEO는 어떻게 봤나</h2><p>POST-R3 신다인 우승 확률 <strong class="probability-callout">{p}</strong></p><p>POST-R3 forecast → Official winner</p><a class="text-link" href="{meta.stage_url("r3")}">View R3 forecast</a></section>'
            '<section class="section-v2"><p class="kicker">Evaluation boundary</p><h2>예측은 그대로 남습니다.</h2><p>공식 결과는 비교에만 사용하며 이전 예측에 다시 쓰지 않습니다.</p>' + _cta(meta, "final_evaluation", "final") + '</section>')


def _deep(meta, p):
    return ('<section class="hero-v2"><p class="kicker">NEO Deep Dive · Beta</p><h1>같은 스코어라도 확률은 다릅니다.</h1><p>리더보드에 보이지 않는 예측의 차이를 살펴보는 분석 공간입니다.</p></section>'
            '<section class="section-v2"><p class="kicker">POST-R3 question</p><h2>공동 선두 네 명, 서로 다른 확률</h2><div class="card-grid">'
            '<article class="data-card"><h3>노승희</h3><p>T1 · −9 · 15.04%</p></article><article class="data-card"><h3>박혜준</h3><p>T1 · −9 · 11.56%</p></article>'
            f'<article class="data-card"><h3>신다인</h3><p>T1 · −9 · {p}</p></article><article class="data-card"><h3>유아현</h3><p>T1 · −9 · 0.24%</p></article></div><p>같은 점수에서도 입력 정보와 남은 라운드 시뮬레이션에 따라 확률은 달라집니다.</p><a class="text-link" href="{meta.stage_url("r3")}">View R3 forecast</a></section>')


def _about(data):
    legacy = "".join(f'<li><code>{escape(k)}</code> — {escape(v)}</li>' for k, v in data["url_compatibility"].items())
    return ('<section class="hero-v2"><p class="kicker">About NEO</p><h1>결과가 나오기 전의 확률을 기록합니다.</h1><p>NEO GOLF DATA는 KLPGA 대회 예측과 라운드별 평가를 만드는 독립 프로젝트입니다.</p></section>'
            '<section class="section-v2" id="methodology"><p class="kicker">Methodology</p><h2>확률은 정해진 시점에 계산됩니다.</h2><p>BETA #001 PRE는 검증된 과거 평균 라운드 스코어와 최근 경기력 특성을 사용했습니다. 라운드 업데이트는 완료된 결과와 고정된 PRE 소스로 남은 라운드를 시뮬레이션했습니다.</p><p>라운드 종료 후 업데이트되며 실시간 예측을 주장하지 않습니다.</p></section>'
            '<section class="section-v2 evidence-reference"><p class="kicker">Evidence policy</p><h2>예측은 결과가 나온 뒤 바꾸지 않습니다.</h2><p>재구성 자료는 별도로 표시하고, 공식 결과는 예측과 분리해 검증합니다.</p></section>'
            f'<section class="section-v2 evidence-reference"><details><summary>Legacy route compatibility record</summary><ul>{legacy}</ul></details></section>')


def build_beta001_candidate(content_path: Path, manifest_path: Path, repo_root: Path, output_root: Path) -> tuple[Path, ...]:
    data = json.loads(Path(content_path).read_text(encoding="utf-8")); manifest = json.loads(Path(manifest_path).read_text(encoding="utf-8"))
    before = load_and_verify_manifest(manifest_path, repo_root); meta = TournamentMetadata.from_dict(data["tournament"])
    if set(meta.published_stages) != set(STAGES): raise CandidateBuildError("all six stages required")
    forbidden = {"winner", "rounds", "total", "to_par", "official_result", "final_result"}
    if any(forbidden & set(x) for x in data["forecast_stages"].values()): raise CandidateBuildError("result leaked into forecast")
    if data["final_result"] != {"record_type":"RESULT","winner":"신다인","player_code":"9135","rounds":[70,70,67,64],"total":271,"to_par":"-17"}: raise CandidateBuildError("invalid final result")
    if data["validated_display_records"]["post_r3_shin_dain_win_probability"] != "7.47%": raise CandidateBuildError("validated probability changed")
    records = {r["stage"].lower(): r for r in manifest["stages"]}; output_root = Path(output_root)
    pages = {
        output_root/"index.html": render_page(title="Home",active_section="home",body_html=_home(data,meta),lang="ko"),
        output_root/"tournaments"/"index.html": render_page(title="Tournaments",active_section="tournaments",body_html=_index(data,meta),lang="ko"),
        output_root/"deep-dive"/"index.html": render_page(title="Deep Dive",active_section="deep-dive",body_html=_deep(meta,"7.47%"),lang="ko"),
        output_root/"about"/"index.html": render_page(title="About NEO",active_section="about",body_html=_about(data),lang="ko"),
        output_root/"tournaments"/"2026"/meta.slug/"index.html": render_page(title=meta.display_name,active_section="tournaments",body_html=_overview(data,meta),tournament=meta,current_stage="overview",lang="ko"),
        output_root/"tournaments"/"2026"/meta.slug/"pre"/"index.html": render_page(title=f"{meta.display_name} PRE",active_section="tournaments",body_html=_pre(repo_root/records["pre"]["source_artifact"],records["pre"]),tournament=meta,current_stage="pre",lang="ko"),
        output_root/"tournaments"/"2026"/meta.slug/"final"/"index.html": render_page(title=f"{meta.display_name} FINAL",active_section="tournaments",body_html=_final(data,meta),tournament=meta,current_stage="final",lang="ko")}
    for stage in ("r1","r2","r3"):
        pages[output_root/"tournaments"/"2026"/meta.slug/stage/"index.html"] = render_page(title=f"{meta.display_name} {stage.upper()}",active_section="tournaments",body_html=_forecast(stage.upper(),data["forecast_stages"][stage],records[stage],repo_root/records[stage]["source_artifact"],f"/protected/beta001/{stage}.html",meta),tournament=meta,current_stage=stage,lang="ko")
    written = [_write(p,h) for p,h in pages.items()]; assets = output_root/"assets"; assets.mkdir(parents=True,exist_ok=True)
    for name in ("neo-site.css","neo-site.js"):
        dest=assets/name; shutil.copyfile(STATIC_DIR/name,dest); written.append(dest)
    protected=output_root/"protected"/"beta001"; protected.mkdir(parents=True,exist_ok=True)
    for stage in ("r1","r2","r3"):
        src=repo_root/records[stage]["source_artifact"]; dest=protected/f"{stage}.html"; shutil.copyfile(src,dest)
        if _sha(dest) != records[stage]["sha256"]: raise CandidateBuildError("protected evidence bytes changed")
        written.append(dest)
    if load_and_verify_manifest(manifest_path,repo_root) != before: raise CandidateBuildError("evidence changed")
    return tuple(written)
