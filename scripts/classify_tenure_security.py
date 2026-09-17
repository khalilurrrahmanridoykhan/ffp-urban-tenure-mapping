"""Phase 6: classifies every parcel's tenure security -- the layer both
the Phase 7 dashboard and Phase 8 atlas present. Deliberately kept
separate from the STDM tables themselves (stdm.gpkg stays a clean
implementation of STDM's own schema); this is a derived policy-analysis
layer built from it, not part of the base registry.

Two things feed the classification, on purpose kept apart because
they're different risks:
- **tenure type** -- what kind of right the household claims, from the
  social_tenure_relationship table (owned_documented down to
  informal_occupation), giving a 1-5 base score.
- **spatial fitness** -- whether the parcel's physical extent is itself
  contested (Phase 5's boundary_conflict finding), which undermines
  security regardless of what the tenure_type claim is.

A disputed STR (two households claiming the same parcel) overrides
everything else: "contested" isn't a low tenure-type score, it's a
different kind of insecurity -- the right itself is unresolved, not just
weakly evidenced. low_confidence_confirmation findings from Phase 5 are
deliberately NOT used here -- that's a model/spatial-QA signal about the
AI draft, not a tenure-security signal about the household's claim.

Run: python3 scripts/classify_tenure_security.py
Output: data/synthetic/tenure_security.gpkg (layer tenure_security)
"""

import os
import sqlite3

import geopandas as gpd
import pandas as pd

REPO_ROOT = os.path.join(os.path.dirname(__file__), "..")
SYN_DIR = os.path.join(REPO_ROOT, "data", "synthetic")
OUT_PATH = os.path.join(SYN_DIR, "tenure_security.gpkg")

TENURE_TYPE_SCORE = {
    "owned_documented": 5,
    "owned_undocumented": 4,
    "customary": 3,
    "rented": 2,
    "informal_occupation": 1,
}
BOUNDARY_CONFLICT_PENALTY = 1


def classify(score, disputed):
    if disputed:
        return "contested"
    if score >= 4:
        return "secure"
    if score >= 2:
        return "moderate"
    return "at_risk"


def main():
    spatial_unit = gpd.read_file(os.path.join(SYN_DIR, "stdm.gpkg"), layer="spatial_unit")
    conn = sqlite3.connect(os.path.join(SYN_DIR, "stdm.gpkg"))
    str_table = pd.read_sql("SELECT * FROM social_tenure_relationship", conn)
    conn.close()

    queue = pd.read_csv(os.path.join(SYN_DIR, "adjudication_queue.csv"))
    conflict_ids = set()
    for ids in queue[queue.category == "boundary_conflict"].spatial_unit_ids:
        conflict_ids.update(ids.split(";"))

    records = []
    for spatial_unit_id, group in str_table.groupby("spatial_unit_id"):
        disputed = (group.str_status == "disputed").any()
        has_boundary_conflict = spatial_unit_id in conflict_ids

        if disputed:
            tenure_summary = f"disputed ({len(group)} competing claims: {', '.join(sorted(group.tenure_type_id))})"
            score = 1
        else:
            tenure_type = group.iloc[0].tenure_type_id
            tenure_summary = tenure_type
            score = TENURE_TYPE_SCORE[tenure_type]
            if has_boundary_conflict:
                score = max(1, score - BOUNDARY_CONFLICT_PENALTY)

        records.append({
            "spatial_unit_id": spatial_unit_id,
            "tenure_type_summary": tenure_summary,
            "disputed": bool(disputed),
            "boundary_conflict": has_boundary_conflict,
            "security_score": score,
            "security_class": classify(score, disputed),
        })

    df = pd.DataFrame(records)
    result = spatial_unit[["spatial_unit_id", "geometry"]].merge(df, on="spatial_unit_id", how="left")
    result = gpd.GeoDataFrame(result, geometry="geometry", crs=spatial_unit.crs)

    if os.path.exists(OUT_PATH):
        os.remove(OUT_PATH)
    result.to_file(OUT_PATH, layer="tenure_security", driver="GPKG")

    print(result.security_class.value_counts().to_string())
    print(f"Wrote {len(result)} classified parcels to {OUT_PATH}")


if __name__ == "__main__":
    main()
