"""Phase 5: runs topology and business-logic QA over the STDM data and
produces an adjudication queue -- the list a land officer has to
manually resolve, not a script that silently rewrites the record. Same
spirit as the PH Repo Quality Auditor: a set of independent rule checks,
each producing a structured finding (category, severity, whether it
blocks anything), not a single pass/fail.

Checks:
- invalid_geometry / overlap -- pure topology on spatial_unit
- boundary_conflict -- two spatial units closer than 0.5m without
  overlapping (inside typical handheld-GPS error margin; may or may not
  be a real conflict, needs a look)
- duplicate_claim -- more than one STR on the same spatial unit (a real
  double claim, not synthetic noise -- inherited from Phase 3)
- data_integrity -- STR referencing a party_id or spatial_unit_id that
  doesn't exist
- low_confidence_confirmation -- a parcel the field pass *confirmed* the
  AI draft on, but the model's own confidence for that draft was below
  0.9 -- not wrong, just worth a risk-based spot-check
missing_evidence coverage is reported as a summary statistic, not
per-parcel findings -- 396 individual rows for "no photo on file" isn't
an actionable queue, it's a coverage metric.

Run: python3 scripts/topology_qa.py
Output: data/synthetic/adjudication_queue.csv, data/synthetic/qa_report.md
"""

import os
import sqlite3

import geopandas as gpd
import pandas as pd

REPO_ROOT = os.path.join(os.path.dirname(__file__), "..")
SYN_DIR = os.path.join(REPO_ROOT, "data", "synthetic")

OVERLAP_MIN_AREA = 0.05          # m2 -- ignore floating-point-noise overlaps
NEAR_MISS_DISTANCE = 0.5         # m -- inside typical handheld GPS accuracy
LOW_CONFIDENCE_THRESHOLD = 0.9


def check_invalid_geometry(spatial_unit):
    findings = []
    for _, row in spatial_unit[~spatial_unit.is_valid].iterrows():
        findings.append(_finding("invalid_geometry", "high", True, [row.spatial_unit_id], [],
                                  f"Spatial unit {row.spatial_unit_id} has an invalid geometry."))
    return findings


def check_overlaps(spatial_unit):
    findings = []
    sindex = spatial_unit.sindex
    for i, geom in spatial_unit.geometry.items():
        candidates = list(sindex.intersection(geom.bounds))
        for j in candidates:
            if j <= i:
                continue
            other = spatial_unit.geometry.iloc[j]
            inter_area = geom.intersection(other).area
            if inter_area > OVERLAP_MIN_AREA:
                a, b = spatial_unit.iloc[i].spatial_unit_id, spatial_unit.iloc[j].spatial_unit_id
                findings.append(_finding("overlap", "high", True, [a, b], [],
                                          f"Spatial units {a} and {b} overlap by {inter_area:.2f} m2."))
    return findings


def check_near_miss_boundaries(spatial_unit):
    findings = []
    sindex = spatial_unit.sindex
    for i, geom in spatial_unit.geometry.items():
        candidates = list(sindex.intersection(geom.buffer(NEAR_MISS_DISTANCE).bounds))
        for j in candidates:
            if j <= i:
                continue
            other = spatial_unit.geometry.iloc[j]
            d = geom.distance(other)
            if 0 < d < NEAR_MISS_DISTANCE:
                a, b = spatial_unit.iloc[i].spatial_unit_id, spatial_unit.iloc[j].spatial_unit_id
                findings.append(_finding("boundary_conflict", "medium", True, [a, b], [],
                                          f"Spatial units {a} and {b} are only {d:.2f} m apart -- "
                                          f"inside typical handheld GPS error, verify they don't actually overlap."))
    return findings


def check_duplicate_claims(str_table):
    findings = []
    for spatial_unit_id, group in str_table.groupby("spatial_unit_id"):
        if len(group) > 1:
            parties = list(group.party_id)
            strs = list(group.str_id)
            findings.append(_finding("duplicate_claim", "high", True, [spatial_unit_id], parties,
                                      f"Spatial unit {spatial_unit_id} has {len(group)} competing claims "
                                      f"({', '.join(strs)}) from different households -- needs adjudication."))
    return findings


def check_referential_integrity(str_table, party, spatial_unit):
    findings = []
    orphan_party = str_table[~str_table.party_id.isin(party.party_id)]
    for _, row in orphan_party.iterrows():
        findings.append(_finding("data_integrity", "high", True, [], [row.party_id],
                                  f"{row.str_id} references party {row.party_id}, which does not exist."))
    orphan_su = str_table[~str_table.spatial_unit_id.isin(spatial_unit.spatial_unit_id)]
    for _, row in orphan_su.iterrows():
        findings.append(_finding("data_integrity", "high", True, [row.spatial_unit_id], [],
                                  f"{row.str_id} references spatial unit {row.spatial_unit_id}, which does not exist."))
    return findings


def check_low_confidence_confirmations(validated, ai_draft):
    findings = []
    confirmed = validated[validated.boundary_action == "confirm_ai_draft"]
    joined = confirmed.merge(ai_draft[["draft_id", "confidence"]], left_on="ai_draft_id", right_on="draft_id", how="left")
    low = joined[joined.confidence < LOW_CONFIDENCE_THRESHOLD]
    for _, row in low.iterrows():
        findings.append(_finding("low_confidence_confirmation", "low", False, [row.parcel_id], [],
                                  f"Parcel {row.parcel_id}'s AI draft boundary was confirmed as-is in the field, "
                                  f"but the model's confidence was only {row.confidence:.3f} -- recommended for "
                                  f"random quality-assurance spot-check, not a known error."))
    return findings


def _finding(category, severity, action_required, spatial_unit_ids, party_ids, description):
    return {
        "category": category, "severity": severity, "action_required": action_required,
        "spatial_unit_ids": ";".join(spatial_unit_ids), "party_ids": ";".join(party_ids),
        "description": description,
    }


def main():
    spatial_unit = gpd.read_file(os.path.join(SYN_DIR, "stdm.gpkg"), layer="spatial_unit")
    conn = sqlite3.connect(os.path.join(SYN_DIR, "stdm.gpkg"))
    party = pd.read_sql("SELECT * FROM party", conn)
    str_table = pd.read_sql("SELECT * FROM social_tenure_relationship", conn)
    conn.close()

    validated = gpd.read_file(os.path.join(SYN_DIR, "validated_parcels.gpkg"), layer="validated_parcels")
    ai_draft = gpd.read_file(os.path.join(SYN_DIR, "ai_draft_parcels.gpkg"), layer="ai_draft_parcels")

    checks = [
        ("invalid_geometry", check_invalid_geometry(spatial_unit)),
        ("overlap", check_overlaps(spatial_unit)),
        ("boundary_conflict", check_near_miss_boundaries(spatial_unit)),
        ("duplicate_claim", check_duplicate_claims(str_table)),
        ("data_integrity", check_referential_integrity(str_table, party, spatial_unit)),
        ("low_confidence_confirmation", check_low_confidence_confirmations(validated, ai_draft)),
    ]
    findings = [f for _, results in checks for f in results]

    queue = pd.DataFrame(findings)
    queue.insert(0, "finding_id", [f"QA-{i + 1:04d}" for i in range(len(queue))])
    queue["status"] = "open"
    queue.to_csv(os.path.join(SYN_DIR, "adjudication_queue.csv"), index=False)

    n_missing_evidence = ((str_table.str_status == "validated") & (str_table.documented_by.isna())).sum()
    n_validated = (str_table.str_status == "validated").sum()

    lines = ["# Phase 5 QA report\n", "## Checks run\n", "| check | findings |", "|---|---|"]
    for name, results in checks:
        lines.append(f"| {name} | {len(results)} |")

    lines.append("\n## Adjudication queue\n")
    if len(queue):
        by_cat = queue.groupby(["category", "severity", "action_required"]).size().reset_index(name="count")
        lines += ["| category | severity | blocking | count |", "|---|---|---|---|"]
        for _, row in by_cat.iterrows():
            lines.append(f"| {row.category} | {row.severity} | {row.action_required} | {row['count']} |")
        lines.append(f"\n**Total findings: {len(queue)}** ({queue.action_required.sum()} blocking, "
                     f"{(~queue.action_required).sum()} informational)\n")
    else:
        lines.append("No findings.\n")
    lines.append("## Coverage (not a finding, a metric)\n")
    lines.append(f"- Evidence photo on file for validated STRs: {n_validated - n_missing_evidence}/{n_validated} "
                 f"({100 * (n_validated - n_missing_evidence) / n_validated:.0f}%)")
    report = "\n".join(lines) + "\n"
    with open(os.path.join(SYN_DIR, "qa_report.md"), "w") as f:
        f.write(report)

    print(report)
    print(f"Wrote {len(queue)} findings to adjudication_queue.csv")


if __name__ == "__main__":
    main()
