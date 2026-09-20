"""4R FINAL PRE-BUILD Phase 9: single source-of-truth content export.

Every channel below is a pure projection of the SAME
final_report.build_final_report(context) output -- no channel computes
its own number. If the report itself is BLOCKED (no real FINAL truth
yet), every channel export is BLOCKED too, never a partially-fabricated
draft.
"""
from __future__ import annotations

from klpga.neo_win.final_report import STATUS_BLOCKED, build_final_report
from klpga.tournament_context import TournamentContext

CHANNELS = ("homepage_deep_dive", "naver_blog", "threads", "card_news")


def _blocked(report: dict) -> dict:
    return {"status": STATUS_BLOCKED, "blocked_reason": report.get("blocked_reason")}


def _homepage_deep_dive_source(report: dict) -> dict:
    return {"status": report["status"], "report": report}


def _naver_blog_source(report: dict) -> dict:
    perf = report["forecast_performance"]
    native = perf["frozen_forecast_native_metrics"]
    proxy = perf["post_hoc_rank_proxy_diagnostics"]
    return {
        "status": report["status"],
        "event_summary": report["event_summary"],
        "neo_prediction_summary": report["neo_pre_final_forecast"]["top_candidates"],
        "actual_result": report["event_summary"],
        "biggest_surprises": {
            "positive": report["biggest_positive_surprises"],
            "negative": report["biggest_negative_surprises"],
            "rank_basis_note": report["surprises_rank_basis_note"],
        },
        "course_data": report["course_connection"],
        "neo_validation": {
            "winner_hit": native["winner_hit"],
            "top5_hit": native["top5_hit"],
            "top10_hit": native["top10_hit"],
            "rank_mae": proxy["rank_mae"],
            "rank_mae_note": proxy["rank_proxy_note"],
        },
    }


def _threads_source(report: dict) -> dict:
    native = report["forecast_performance"]["frozen_forecast_native_metrics"]
    return {
        "status": report["status"],
        "winner": report["event_summary"]["winner_name"],
        "neo_called_winner": native["winner_hit"],
        "top_surprise_positive": (report["biggest_positive_surprises"] or [None])[0],
        "top_surprise_negative": (report["biggest_negative_surprises"] or [None])[0],
    }


def _card_news_source(report: dict) -> dict:
    native = report["forecast_performance"]["frozen_forecast_native_metrics"]
    return {
        "status": report["status"],
        "cards": [
            {"card": "winner", "value": report["event_summary"]["winner_name"], "message": None},
            {"card": "neo_winner_hit", "value": native["winner_hit"], "message": None},
            {"card": "neo_top5_hit", "value": native["top5_hit"], "message": None},
            {"card": "biggest_positive_surprise", "value": (report["biggest_positive_surprises"] or [None])[0], "message": None},
            {"card": "biggest_negative_surprise", "value": (report["biggest_negative_surprises"] or [None])[0], "message": None},
        ],
    }


_BUILDERS = {
    "homepage_deep_dive": _homepage_deep_dive_source,
    "naver_blog": _naver_blog_source,
    "threads": _threads_source,
    "card_news": _card_news_source,
}


def export_content_sources(context: TournamentContext) -> dict:
    report = build_final_report(context)
    if report["status"] == STATUS_BLOCKED:
        return {channel: _blocked(report) for channel in CHANNELS}
    return {channel: builder(report) for channel, builder in _BUILDERS.items()}
