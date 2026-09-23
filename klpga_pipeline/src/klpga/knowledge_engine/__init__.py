"""NEO Knowledge Engine.

Architecture: statistics -> Knowledge Engine -> Player Intelligence.

This package converts verified statistics (the warehouse and normalized
field files already produced by the pipeline) into golfer intelligence:
player type, why-she-wins / why-she-loses reasons, multi-season evolution,
and condition-based ("if today") scenarios.

Hard rules:
- Never invent a statistic. Every number comes from an existing source file.
- Never invent a formula. Thresholds live in knowledge_rules.py.
- Every sentence is traceable back to a Citation(source, field_path, value).

This package is the render-agnostic core. It must never import from, or
be imported for, HTML/CSS/UI rendering concerns.
"""
