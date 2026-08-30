"""BETA #001 candidate migration built from structured, separated records."""
from __future__ import annotations

import hashlib
import json
import shutil
from html import escape
from pathlib import Path

from klpga.evidence import load_and_verify_manifest
from klpga.website_v2.shell import STAGE_LABELS, STAGES, STATIC_DIR, TournamentMetadata, render_page


class CandidateBuildError(RuntimeError):
    """Raised before an invalid or evidence-mutating candidate can be accepted."""


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _write(path: Path, text: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text + "\n", encoding="utf-8", newline="\n")
    return path


def _cta(meta: TournamentMetadata, location: str, stage: str = "overview") -> str:
    return (
        '<a class="deep-dive-cta" href="/deep-dive/" data-deep-dive-interest '
        f'data-tournament-id="{escape(meta.tournament_id)}" data-tournament-slug="{escape(meta.slug)}" '
        f'data-stage="{escape(stage)}" data-cta-location="{escape(location)}" '
        'data-deep-dive-id="beta001-r3-leaders" data-content-type="tournament-analysis">'
        'Explore Deep Dive</a>'
    )


def _result_card(result: dict) -> str:
    rounds = "".join(f'<span><small>R{index}</small><br><strong>{score}</strong></span>'
                     for index, score in enumerate(result["rounds"], 1))
    return (
        '<div class="result-card"><div><span class="status-label">RESULT</span>'
        f'<p class="result-card__winner">{escape(result["winner"])}</p><p>Official winner</p></div>'
        f'<div><div class="result-card__score">{result["total"]} ({result["to_par"]})</div>'
        f'<div class="rounds">{rounds}</div></div></div>'
    )


def _home(data: dict, meta: TournamentMetadata) -> str:
    result = data["final_result"]
    return (
        '<section class="hero-v2"><p class="kicker">NEO GOLF DATA</p>'
        '<h1>Forecasts frozen in time. Results kept separate.</h1>'
        '<p>NEO organizes tournament forecasts by what was knowable at each stage, then evaluates them against validated official results.</p></section>'
        '<section class="section-v2"><div class="section-v2__head"><div><p class="kicker">Latest tournament</p>'
        f'<h2>{escape(meta.display_name)}</h2></div><span class="status-label">COMPLETE</span></div>'
        f'<p>BETA #{escape(meta.beta_number)} · {escape(data["dates"]["display"])}</p>'
        f'<p><a class="text-link" href="{meta.base_url}">Open tournament overview</a></p></section>'
        '<section class="section-v2"><div class="section-v2__head"><div><p class="kicker">Latest result</p><h2>Winner</h2></div></div>'
        f'{_result_card(result)}</section>'
        '<section class="section-v2"><p class="kicker">Prediction archive</p><h2>One tournament, five frozen checkpoints</h2>'
        '<div class="route-list">' + "".join(
            f'<a href="{meta.stage_url(stage)}">{STAGE_LABELS[stage]}</a>' for stage in STAGES
        ) + '</div></section>'
        '<section class="section-v2"><p class="kicker">Deep Dive</p><h2>Why probabilities differ even when scores match</h2>'
        f'<p>Open the analysis destination for the questions behind the leaderboard.</p>{_cta(meta, "home")}</section>'
        '<section class="section-v2" id="methodology"><p class="kicker">About / methodology</p>'
        '<h2>Evidence first</h2><p>Forecasts are probability estimates, not guarantees. Published evidence is frozen; official results are validated and presented separately.</p>'
        '<p><a class="text-link" href="/about/">How NEO works</a></p></section>'
    )


def _tournament_index(data: dict, meta: TournamentMetadata) -> str:
    return (
        '<section class="hero-v2"><p class="kicker">Tournament archive</p><h1>Completed tournaments</h1>'
        '<p>Each entry keeps forecast checkpoints distinct from official results.</p></section>'
        '<section class="section-v2"><article class="data-card"><span class="status-label">COMPLETE</span>'
        f'<h2><a href="{meta.base_url}">{escape(meta.display_name)}</a></h2>'
        f'<p>BETA #{escape(meta.beta_number)} · {escape(data["dates"]["display"])}</p>'
        f'<p>Winner {escape(data["final_result"]["winner"])} · {data["final_result"]["total"]} ({data["final_result"]["to_par"]})</p>'
        '</article></section>'
    )


def _overview(data: dict, meta: TournamentMetadata, manifest: dict) -> str:
    result = data["final_result"]
    timeline = "".join(
        f'<a href="{meta.stage_url(stage)}"><strong>{STAGE_LABELS[stage]}</strong>'
        f'<span>{"RESULT" if stage == "final" else "FROZEN FORECAST"}</span></a>'
        for stage in STAGES if stage != "overview"
    )
    evidence = "".join(
        f'<article class="data-card"><span class="status-label">{escape(record["stage"])}</span>'
        f'<h3>{escape(record["publication_provenance"]["classification"].replace("_", " ").title())}</h3>'
        f'<p>{escape(record["artifact_type"])}</p><p>SHA-256 {escape(record["sha256"][:16])}…</p></article>'
        for record in manifest["stages"]
    )
    return (
        '<section class="section-v2"><div class="section-v2__head"><div><p class="kicker">Tournament overview</p>'
        f'<h2>{escape(data["dates"]["display"])}</h2></div><span class="status-label">COMPLETE</span></div>'
        f'{_result_card(result)}</section>'
        '<section class="section-v2"><p class="kicker">Stage timeline</p><h2>Forecast → result</h2>'
        f'<div class="timeline">{timeline}</div></section>'
        '<section class="section-v2"><p class="kicker">Forecast versus result</p><h2>The winner was in the POST-R3 forecast</h2>'
        '<div class="card-grid"><article class="data-card"><h3>POST-R3 FORECAST</h3>'
        '<p>신다인 entered FINAL tied for the lead at −9 with a frozen 7.40% win probability.</p></article>'
        f'<article class="data-card"><h3>OFFICIAL RESULT</h3><p>{escape(result["winner"])} won at {result["total"]} ({result["to_par"]}).</p></article></div>'
        '<p>These records are compared; the earlier forecast is not rewritten with the later result.</p></section>'
        f'<section class="section-v2"><p class="kicker">Evidence & publication</p><h2>Protected sources</h2><div class="card-grid">{evidence}</div></section>'
        f'<section class="section-v2"><p class="kicker">Deep Dive</p><h2>Explore the forecast logic</h2>{_cta(meta, "tournament_overview")}</section>'
    )


def _pre(data: dict, meta: TournamentMetadata, source: Path, record: dict) -> str:
    archive = json.loads(source.read_text(encoding="utf-8"))
    rows = "".join(
        f'<tr><td>{item["rank"]}</td><td>{escape(item["player_name_display"])}</td>'
        f'<td>{escape(item["player_code"])}</td><td>{item["win_probability"] * 100:.3f}%</td></tr>'
        for item in archive["predictions"]
    )
    return (
        '<section class="section-v2"><div class="provenance"><strong>RECONSTRUCTED ARCHIVE EVIDENCE</strong>'
        '<span>This is not an original publication capture. It is the protected byte-exact archive registered in PHASE 0 and disclosed as a rerun reconstruction.</span></div></section>'
        '<section class="section-v2"><p class="kicker">PRE · FROZEN FORECAST</p><h2>Pre-tournament win probabilities</h2>'
        f'<p>Prediction {escape(record["prediction_id"])} · model {escape(record["model_version"])} · cutoff {escape(record["data_cutoff"])}</p>'
        f'<div class="table-scroll"><table class="evidence-table"><thead><tr><th>Rank</th><th>Player</th><th>Code</th><th>Win probability</th></tr></thead><tbody>{rows}</tbody></table></div></section>'
    )


def _published_stage(stage: str, record: dict, evidence_url: str) -> str:
    provenance = record["publication_provenance"]
    return (
        '<section class="section-v2"><div class="provenance"><strong>ORIGINAL PUBLISHED FORECAST EVIDENCE</strong>'
        f'<span>{escape(record["notes"])}</span></div>'
        f'<p>Published provenance commit {escape(provenance["git_commit"][:8])} · protected SHA-256 {escape(record["sha256"])}</p></section>'
        '<section class="section-v2"><p class="kicker">FROZEN FORECAST</p>'
        f'<h2>{escape(stage)} historical publication</h2><p>The evidence below is a byte-exact protected source rendered in a script-disabled frame.</p>'
        f'<iframe class="evidence-frame" src="{evidence_url}" sandbox title="{escape(stage)} protected historical forecast"></iframe></section>'
    )


def _final(data: dict) -> str:
    result = data["final_result"]
    return (
        '<section class="section-v2"><p class="kicker">FINAL · RESULT</p><h2>Official final result</h2>'
        '<p>FINAL is an official result record, not a forecast checkpoint.</p>'
        f'{_result_card(result)}</section>'
        '<section class="section-v2"><p class="kicker">Evaluation boundary</p><h2>Forecasts remain frozen</h2>'
        '<p>PRE, R1, R2 and R3 remain as their historical forecast evidence. The official result is referenced only for later evaluation and never written back into those records.</p>'
        '<div class="route-list"><a href="../pre/">PRE forecast</a><a href="../r1/">R1 forecast</a>'
        '<a href="../r2/">R2 forecast</a><a href="../r3/">R3 forecast</a></div></section>'
    )


def _deep_dive(meta: TournamentMetadata) -> str:
    return (
        '<section class="hero-v2"><p class="kicker">NEO Deep Dive · Beta</p><h1>Score alone does not explain probability.</h1>'
        '<p>A lightweight analysis destination for the questions behind BETA #001.</p></section>'
        '<section class="section-v2"><p class="kicker">POST-R3 question</p><h2>Four co-leaders, four probabilities</h2>'
        '<div class="card-grid"><article class="data-card"><h3>노승희</h3><p>T1 · −9 · 15.04%</p></article>'
        '<article class="data-card"><h3>박혜준</h3><p>T1 · −9 · 11.56%</p></article>'
        '<article class="data-card"><h3>신다인</h3><p>T1 · −9 · 7.40%</p></article>'
        '<article class="data-card"><h3>유아현</h3><p>T1 · −9 · 0.24%</p></article></div>'
        '<p>These are frozen POST-R3 forecast values, not final-result-adjusted probabilities.</p>'
        f'<p><a class="text-link" href="{meta.stage_url("r3")}">View protected R3 evidence</a></p></section>'
    )


def _about(data: dict) -> str:
    compatibility = data["url_compatibility"]
    legacy = "".join(f'<li><code>{escape(route)}</code> — {escape(decision)}</li>' for route, decision in compatibility.items())
    return (
        '<section class="hero-v2"><p class="kicker">About NEO</p><h1>Independent golf data, with an evidence trail.</h1>'
        '<p>NEO GOLF DATA is an independent project for structured tournament forecasts and post-round evaluation.</p></section>'
        '<section class="section-v2" id="methodology"><p class="kicker">Methodology</p><h2>What the model actually uses</h2>'
        '<p>BETA #001 PRE used verified prior average round score-to-par and prior recent-form features. Round updates used completed-round results and the frozen PRE source to simulate the remaining rounds.</p>'
        '<p>Updates occur after completed rounds; NEO does not claim continuous real-time prediction.</p></section>'
        '<section class="section-v2"><p class="kicker">Evidence policy</p><h2>Forecast and result are different record types</h2>'
        '<p>Forecast evidence is immutable once protected. Reconstructed material is labeled. Official results are validated separately.</p></section>'
        f'<section class="section-v2"><p class="kicker">Legacy route decision</p><h2>Compatibility record</h2><ul>{legacy}</ul></section>'
    )


def build_beta001_candidate(content_path: Path, manifest_path: Path, repo_root: Path, output_root: Path) -> tuple[Path, ...]:
    data = json.loads(Path(content_path).read_text(encoding="utf-8"))
    manifest = json.loads(Path(manifest_path).read_text(encoding="utf-8"))
    verified_before = load_and_verify_manifest(manifest_path, repo_root)
    meta = TournamentMetadata.from_dict(data["tournament"])
    if set(meta.published_stages) != set(STAGES):
        raise CandidateBuildError("BETA #001 candidate requires all six stages")
    forecast_stages = data["forecast_stages"]
    forbidden = {"winner", "rounds", "total", "to_par", "official_result", "final_result"}
    for stage, record in forecast_stages.items():
        if forbidden & set(record):
            raise CandidateBuildError(f"result fields leaked into forecast stage {stage}")
    result = data["final_result"]
    if result != {"record_type": "RESULT", "winner": "신다인", "player_code": "9135", "rounds": [70, 70, 67, 64], "total": 271, "to_par": "-17"}:
        raise CandidateBuildError("official FINAL result does not match the validated record")

    records = {record["stage"].lower(): record for record in manifest["stages"]}
    if records["pre"]["publication_provenance"]["classification"] != "reconstructed":
        raise CandidateBuildError("PRE provenance must remain reconstructed")
    output_root = Path(output_root)
    written: list[Path] = []
    pages = {
        output_root / "index.html": render_page(title="Home", active_section="home", body_html=_home(data, meta), lang="ko"),
        output_root / "tournaments" / "index.html": render_page(title="Tournaments", active_section="tournaments", body_html=_tournament_index(data, meta), lang="ko"),
        output_root / "deep-dive" / "index.html": render_page(title="Deep Dive", active_section="deep-dive", body_html=_deep_dive(meta), lang="ko"),
        output_root / "about" / "index.html": render_page(title="About NEO", active_section="about", body_html=_about(data), lang="ko"),
        output_root / "tournaments" / "2026" / meta.slug / "index.html": render_page(title=meta.display_name, active_section="tournaments", body_html=_overview(data, meta, manifest), tournament=meta, current_stage="overview", lang="ko"),
        output_root / "tournaments" / "2026" / meta.slug / "pre" / "index.html": render_page(title=f"{meta.display_name} PRE", active_section="tournaments", body_html=_pre(data, meta, repo_root / records["pre"]["source_artifact"], records["pre"]), tournament=meta, current_stage="pre", lang="ko"),
        output_root / "tournaments" / "2026" / meta.slug / "r1" / "index.html": render_page(title=f"{meta.display_name} R1", active_section="tournaments", body_html=_published_stage("R1", records["r1"], "/protected/beta001/r1.html"), tournament=meta, current_stage="r1", lang="ko"),
        output_root / "tournaments" / "2026" / meta.slug / "r2" / "index.html": render_page(title=f"{meta.display_name} R2", active_section="tournaments", body_html=_published_stage("R2", records["r2"], "/protected/beta001/r2.html"), tournament=meta, current_stage="r2", lang="ko"),
        output_root / "tournaments" / "2026" / meta.slug / "r3" / "index.html": render_page(title=f"{meta.display_name} R3", active_section="tournaments", body_html=_published_stage("R3", records["r3"], "/protected/beta001/r3.html"), tournament=meta, current_stage="r3", lang="ko"),
        output_root / "tournaments" / "2026" / meta.slug / "final" / "index.html": render_page(title=f"{meta.display_name} FINAL", active_section="tournaments", body_html=_final(data), tournament=meta, current_stage="final", lang="ko"),
    }
    for path, html in pages.items():
        written.append(_write(path, html))
    assets = output_root / "assets"
    assets.mkdir(parents=True, exist_ok=True)
    for name in ("neo-site.css", "neo-site.js"):
        destination = assets / name
        shutil.copyfile(STATIC_DIR / name, destination)
        written.append(destination)
    protected_dir = output_root / "protected" / "beta001"
    protected_dir.mkdir(parents=True, exist_ok=True)
    for stage, filename in (("r1", "r1.html"), ("r2", "r2.html"), ("r3", "r3.html")):
        source = repo_root / records[stage]["source_artifact"]
        destination = protected_dir / filename
        shutil.copyfile(source, destination)
        if _sha256(destination) != records[stage]["sha256"]:
            raise CandidateBuildError(f"{stage.upper()} protected copy changed bytes")
        written.append(destination)
    if load_and_verify_manifest(manifest_path, repo_root) != verified_before:
        raise CandidateBuildError("protected evidence changed during candidate generation")
    return tuple(written)
