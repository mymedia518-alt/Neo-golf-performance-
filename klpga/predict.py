"""python -m klpga.predict

Scaffold for the NEO GOLF DATA TOP20 output. Intentionally refuses to
print WIN/TOP5/TOP10/TOP20 numbers when the historical DB isn't populated
with real, collected data yet: this command never fabricates or estimates
a probability.
"""
from __future__ import annotations

import argparse
import sys

from . import db

MIN_TOURNAMENTS_FOR_MODEL = 20  # arbitrary-but-documented floor; revisit once real data exists


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m klpga.predict",
        description=(
            "Predict WIN/TOP5/TOP10/TOP20 for an upcoming tournament's field "
            "(requires a populated, feature-built historical DB)."
        ),
    )
    parser.add_argument(
        "--field",
        help="path to a CSV of player_id,player_name for the upcoming tournament's confirmed entry list",
        required=False,
    )
    args = parser.parse_args(argv)

    conn = db.get_connection()
    db.init_db(conn)
    try:
        n_tournaments = conn.execute(
            "SELECT COUNT(*) FROM tournaments WHERE in_model_scope = 1"
        ).fetchone()[0]
        n_features = conn.execute("SELECT COUNT(*) FROM player_features").fetchone()[0]
    finally:
        conn.close()

    if n_tournaments < MIN_TOURNAMENTS_FOR_MODEL or n_features == 0:
        print(
            "Historical DB is not yet populated enough to produce a real prediction "
            f"({n_tournaments} in-scope tournaments, {n_features} feature rows; "
            f"need >= {MIN_TOURNAMENTS_FOR_MODEL} tournaments and computed features).\n\n"
            "Run, in order:\n"
            "  python -m klpga.collect --events 100\n"
            "  python -m klpga.validate\n"
            "  python -m klpga.features\n\n"
            "This command intentionally refuses to print WIN/TOP5/TOP10/TOP20 numbers "
            "when the underlying data is missing - no placeholder or estimated "
            "probabilities are ever generated here."
        )
        return 1

    if not args.field:
        print(
            "No --field CSV was provided (the upcoming tournament's confirmed entry "
            "list). A real prediction requires the actual field; provide it with "
            "--field path/to/field.csv (columns: player_id,player_name)."
        )
        return 1

    # NOTE: model training/calibration is intentionally not implemented yet. There is
    # no real historical data available in the environment this scaffold was built in
    # (klpga.co.kr / data.klpga.co.kr were unreachable), so there is nothing to fit or
    # validate a model against. Once klpga.collect has been run against the live site
    # and klpga.validate confirms data quality, implement training/calibration here so
    # WIN probabilities across the field sum to ~100% and TOP5/TOP10/TOP20 are
    # calibrated - not ad hoc weights.
    print(
        "Model scoring is not implemented yet. The historical DB and feature pipeline "
        "are ready (see klpga.features), but no model has been trained/calibrated "
        "against real KLPGA data, so no TOP20 output is produced."
    )
    return 1


if __name__ == "__main__":
    sys.exit(main())
