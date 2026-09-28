"""The Question Engine -- MISSION V100 (2026-09-28).

"Every answer in NEO must originate from a Question object. Question
-> Evidence -> Metrics -> Visualization -> Rendering. Player History is
only one renderer. Compare is another renderer. Coach Mode is another
renderer. Tournament Preview is another renderer. The engine must never
know which renderer consumes it. Architecture before features.
Questions before charts. Evidence before conclusions."

This module is the engine. It has NO import of, and no knowledge of,
any renderer (player_history_report.py, player_compare.py, or any
future coach_mode.py / tournament_preview.py). It never draws an SVG,
never writes an HTML tag, never picks a color. It exists to answer one
question: "what real evidence and metrics does this Question need, and
how should something be shown to answer it" -- never "how is it shown."

The pipeline, as real objects:

  Question       one real question a NEO page answers (a Korean
                  question string + an id), carrying...
  Evidence        ...real, unmodified values pulled from a player's doc
                  by dotted path (never fabricated -- a missing path
                  means no Evidence entry, never a placeholder), which
                  are combined into...
  Metric          ...one named, typed, already-computed value (the
                  computation itself lives in the builder scripts --
                  data layer, not here; a Metric is a reference to an
                  already-computed number, never a new calculation),
                  described for display by...
  Visualization   ...a renderer-agnostic spec: `kind` (e.g. "radar",
                  "trend_line", "arrow_grid", "table") + the Metrics it
                  needs + free-form `params`. The engine does not know
                  what "radar" looks like -- only a renderer does.
  Rendering       a renderer's job entirely; see the Renderer protocol
                  below, which this module never imports an
                  implementation of.

A renderer-side adapter module (e.g. player_history_questions.py) is
where a Question gets turned into a real HTML string, by calling a
real, already-existing, frozen renderer function with the Metrics'
values. That adapter imports both this engine and a renderer; this
engine imports neither the adapter nor any renderer, so it can be
reused by a coach-mode or tournament-preview renderer later without
ever being touched.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional, Protocol, runtime_checkable


@dataclass(frozen=True)
class Evidence:
    """One real, unmodified value, straight from a player's doc.
    `source_path` names exactly where in the doc this came from (dotted
    path, e.g. "why_now.lead_component") -- purely for traceability, so
    every Metric built from this Evidence can be audited back to its
    real source field. Never holds a value this engine invented."""
    source_path: str
    value: Any


@dataclass(frozen=True)
class Metric:
    """One named, already-computed real value a Question's answer is
    built from. The computation itself happened in a builder script
    (e.g. scripts/build_10097_player_history.py) or upstream in the
    doc -- this is a reference to that real value, carrying the
    Evidence it was read from, never a new calculation performed by
    this engine."""
    name: str
    value: Any
    evidence: tuple[Evidence, ...] = ()
    unit: Optional[str] = None


@dataclass(frozen=True)
class VisualizationSpec:
    """A renderer-agnostic description of HOW a set of Metrics should
    be shown -- `kind` is a free-form string a renderer maps to its own
    real chart/section function (e.g. "radar", "trend_line",
    "arrow_grid", "table", "skill_chain"). This engine never
    interprets `kind` itself; it only carries it."""
    kind: str
    metrics: tuple[Metric, ...] = ()
    params: dict = field(default_factory=dict)


@dataclass(frozen=True)
class Question:
    """Question -> Evidence -> Metrics -> Visualization. One real
    question a NEO page answers, with everything a renderer needs to
    answer it -- never the rendered HTML itself, which is the
    renderer's job alone."""
    id: str
    text_ko: str
    evidence: tuple[Evidence, ...]
    metrics: tuple[Metric, ...]
    visualization: VisualizationSpec

    def metric(self, name: str) -> Optional[Metric]:
        """Look up one of this Question's own Metrics by name -- the
        normal way a renderer-side adapter pulls a real value back out
        to pass into an existing chart/section function."""
        return next((m for m in self.metrics if m.name == name), None)

    def metric_value(self, name: str, default: Any = None) -> Any:
        m = self.metric(name)
        return m.value if m is not None else default


@runtime_checkable
class Renderer(Protocol):
    """The contract every renderer (player_history_report.py's
    adapter, player_compare.py's adapter, and any future coach_mode /
    tournament_preview renderer) must satisfy: answer(question) -> a
    real HTML string. This engine module never imports a class that
    implements this protocol -- it exists here purely as documentation
    of the boundary, so a new renderer knows what shape to be without
    this engine ever needing to know the new renderer exists."""

    def answer(self, question: Question) -> str: ...


def _dig(doc: Optional[dict], path: str) -> Any:
    """Real dotted-path lookup into a doc -- 'why_now.lead_component'
    walks doc['why_now']['lead_component']. Returns a sentinel-free
    None on any missing key/None-along-the-way, so a caller can tell
    'not present' from a real None value only by checking the returned
    Evidence tuple's length, never by the value itself."""
    node = doc
    for part in path.split("."):
        if not isinstance(node, dict) or part not in node:
            return None
        node = node[part]
    return node


def build_evidence(doc: Optional[dict], *paths: str) -> tuple[Evidence, ...]:
    """Pull real values out of a doc by dotted path, each wrapped as
    Evidence. A path whose value is missing or None is simply left out
    -- never a placeholder Evidence with a fabricated value, matching
    every renderer's own 'never invent, only real data' rule."""
    out = []
    for p in paths:
        v = _dig(doc, p)
        if v is not None:
            out.append(Evidence(source_path=p, value=v))
    return tuple(out)
