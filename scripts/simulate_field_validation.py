"""Phase 3: simulates a field-collection pass against the Phase 2 AI
draft -- an enumerator walking each draft parcel, filling in the
ffp_boundary_validation XLSForm, and either confirming, correcting, or
rejecting it. Ground truth (the true parcels/occupants Phase 1 generated)
stands in for "what the enumerator actually finds," so the simulation is
grounded, not just randomly generated: every correction, rejection, and
dispute traces back to a real discrepancy between the AI draft and the
true parcel fabric, or a real second household sharing a parcel.

Run: python3 scripts/simulate_field_validation.py
Output: data/synthetic/field_submissions.csv (one row per ODK-style
submission), data/synthetic/validated_parcels.gpkg (layer
validated_parcels -- the corrected fabric Phase 4 builds STDM records
from), data/synthetic/field_photos/*.jpg (a sample of evidence photos)
"""

import datetime
import os
import uuid

import geopandas as gpd
import numpy as np
import pandas as pd
import rasterio
from PIL import Image
from shapely.geometry import Polygon

REPO_ROOT = os.path.join(os.path.dirname(__file__), "..")
SYN_DIR = os.path.join(REPO_ROOT, "data", "synthetic")
PHOTOS_DIR = os.path.join(SYN_DIR, "field_photos")

from settlement_gen import LOCAL_CRS  # noqa: E402

MATCH_THRESHOLD = 0.3     # true-parcel overlap fraction to count as "this draft corresponds to this parcel"
CONFIRM_IOU = 0.97        # per-parcel IoU above which the enumerator just confirms the AI draft as-is
WALK_JITTER_M = 0.25      # GPS-walk imprecision -- a human re-walking a boundary isn't survey-perfect either

TENURE_WEIGHTS = {
    "owned_documented": 0.10, "owned_undocumented": 0.25, "rented": 0.30,
    "informal_occupation": 0.30, "customary": 0.05,
}
ENUMERATORS = ["ENUM-01", "ENUM-02", "ENUM-03", "ENUM-04"]
REJECTION_NOTES = [
    "Standing water / drainage channel, no structure here.",
    "Shared courtyard between neighbouring households, not a separate plot.",
    "Debris pile from a demolished structure, not currently occupied.",
]
DISPUTE_NOTES = [
    "Both households state they have lived here since before the other's claim.",
    "Boundary line between the two claims is contested; neither has documentation.",
    "Second household moved in after the first left temporarily; occupancy disputed.",
]


def jitter_walk(true_geom, rng):
    coords = list(true_geom.exterior.coords)[:-1]
    walked = [(x + rng.normal(0, WALK_JITTER_M), y + rng.normal(0, WALK_JITTER_M)) for x, y in coords]
    walked.append(walked[0])
    out = Polygon(walked).buffer(0)
    return out if out.is_valid and not out.is_empty else true_geom


def classify_drafts(draft_gdf, true_gdf):
    """For each AI draft blob, decide what an enumerator would report:
    confirm / correct / reject, and which true parcel (if any) it maps to."""
    sindex = true_gdf.sindex
    results = []
    for d_idx, draft_geom in draft_gdf.geometry.items():
        candidates = list(sindex.intersection(draft_geom.bounds))
        overlaps = {t_idx: draft_geom.intersection(true_gdf.geometry.iloc[t_idx]).area for t_idx in candidates}
        hits = {t_idx: a for t_idx, a in overlaps.items() if a > MATCH_THRESHOLD * true_gdf.geometry.iloc[t_idx].area}

        if not hits:
            results.append({"draft_idx": d_idx, "action": "reject_not_a_parcel", "true_idx": None, "iou": None})
            continue

        best_t_idx = max(hits, key=lambda t: hits[t])
        true_geom = true_gdf.geometry.iloc[best_t_idx]
        iou = draft_geom.intersection(true_geom).area / draft_geom.union(true_geom).area
        action = "confirm_ai_draft" if iou >= CONFIRM_IOU else "correct_boundary"
        results.append({"draft_idx": d_idx, "action": action, "true_idx": best_t_idx, "iou": round(float(iou), 4)})
    return results


def find_missed_parcels(draft_gdf, true_gdf, classified):
    covered_true = {c["true_idx"] for c in classified if c["true_idx"] is not None}
    return [i for i in true_gdf.index if i not in covered_true]


def save_photo(imagery, transform, geom, out_path):
    minx, miny, maxx, maxy = geom.buffer(1.0).bounds
    col0, row0 = ~transform * (minx, maxy)
    col1, row1 = ~transform * (maxx, miny)
    r0, r1 = max(int(row0), 0), min(int(row1), imagery.shape[0])
    c0, c1 = max(int(col0), 0), min(int(col1), imagery.shape[1])
    if r1 <= r0 or c1 <= c0:
        return False
    crop = imagery[r0:r1, c0:c1, :]
    Image.fromarray(crop).save(out_path, quality=85)
    return True


def main(seed=7):
    rng = np.random.default_rng(seed)

    draft_gdf = gpd.read_file(os.path.join(SYN_DIR, "ai_draft_parcels.gpkg"), layer="ai_draft_parcels")
    true_gdf = gpd.read_file(os.path.join(SYN_DIR, "settlement.gpkg"), layer="parcels")
    occupants = pd.read_csv(os.path.join(SYN_DIR, "occupants.csv"))

    with rasterio.open(os.path.join(SYN_DIR, "imagery.tif")) as src:
        imagery = np.moveaxis(src.read(), 0, -1)
        transform = src.transform

    classified = classify_drafts(draft_gdf, true_gdf)
    missed = find_missed_parcels(draft_gdf, true_gdf, classified)
    print(f"Draft blobs: {len(draft_gdf)} -> "
          f"{sum(c['action'] == 'confirm_ai_draft' for c in classified)} confirmed, "
          f"{sum(c['action'] == 'correct_boundary' for c in classified)} corrected, "
          f"{sum(c['action'] == 'reject_not_a_parcel' for c in classified)} rejected. "
          f"True parcels missed entirely by the AI draft: {len(missed)}")

    if os.path.exists(PHOTOS_DIR):
        for fn in os.listdir(PHOTOS_DIR):
            os.remove(os.path.join(PHOTOS_DIR, fn))
    os.makedirs(PHOTOS_DIR, exist_ok=True)
    photo_sample_budget = 20

    submissions = []
    validated_records = []
    campaign_start = datetime.datetime(2026, 8, 3, 8, 0)
    minute_cursor = 0

    def next_timestamp():
        nonlocal minute_cursor
        minute_cursor += int(rng.integers(4, 14))
        return campaign_start + datetime.timedelta(minutes=minute_cursor)

    def draw_tenure():
        names, weights = zip(*TENURE_WEIGHTS.items())
        return rng.choice(names, p=weights)

    for c in classified:
        draft_geom = draft_gdf.geometry.iloc[c["draft_idx"]]
        draft_id = draft_gdf.iloc[c["draft_idx"]]["draft_id"]
        enumerator = rng.choice(ENUMERATORS)
        ts = next_timestamp()

        if c["action"] == "reject_not_a_parcel":
            submissions.append({
                "_id": len(submissions) + 1, "_uuid": str(uuid.uuid4()),
                "start": ts.isoformat(), "end": (ts + datetime.timedelta(minutes=3)).isoformat(), "today": ts.date().isoformat(),
                "enumerator_id": enumerator, "ai_draft_id": draft_id, "parcel_id": None,
                "boundary_action": c["action"], "rejection_reason": rng.choice(REJECTION_NOTES),
                "household_id": None, "claimant_name": None, "household_size": None, "tenure_type": None,
                "dispute_flag": "no", "dispute_notes": None, "evidence_photo": None,
                "gps_accuracy_m": round(float(rng.uniform(2.0, 6.0)), 1), "notes": None,
            })
            if photo_sample_budget > 0:
                fn = f"{draft_id}_reject.jpg"
                if save_photo(imagery, transform, draft_geom, os.path.join(PHOTOS_DIR, fn)):
                    submissions[-1]["evidence_photo"] = fn
                    photo_sample_budget -= 1
            continue

        true_idx = c["true_idx"]
        true_geom = true_gdf.geometry.iloc[true_idx]
        parcel_id = true_gdf.iloc[true_idx]["parcel_id"]
        final_geom = draft_geom if c["action"] == "confirm_ai_draft" else jitter_walk(true_geom, rng)

        claimants = occupants[occupants.parcel_id == parcel_id]
        is_disputed = len(claimants) > 1

        claim_geoms_photo_done = False
        for _, hh in claimants.iterrows():
            ts = next_timestamp()
            tenure = draw_tenure()
            sub = {
                "_id": len(submissions) + 1, "_uuid": str(uuid.uuid4()),
                "start": ts.isoformat(), "end": (ts + datetime.timedelta(minutes=6)).isoformat(), "today": ts.date().isoformat(),
                "enumerator_id": enumerator, "ai_draft_id": draft_id, "parcel_id": parcel_id,
                "boundary_action": c["action"], "rejection_reason": None,
                "household_id": hh.household_id, "claimant_name": hh.occupant_name,
                "household_size": int(hh.household_size), "tenure_type": tenure,
                "dispute_flag": "yes" if is_disputed else "no",
                "dispute_notes": rng.choice(DISPUTE_NOTES) if is_disputed else None,
                "evidence_photo": None,
                "gps_accuracy_m": round(float(rng.uniform(1.5, 5.0)), 1),
                "notes": None if c["action"] == "confirm_ai_draft" else f"Boundary IoU vs AI draft: {c['iou']}",
            }
            if photo_sample_budget > 0 and (is_disputed or rng.random() < 0.05) and not claim_geoms_photo_done:
                fn = f"{parcel_id}.jpg"
                if save_photo(imagery, transform, final_geom, os.path.join(PHOTOS_DIR, fn)):
                    sub["evidence_photo"] = fn
                    photo_sample_budget -= 1
                    claim_geoms_photo_done = True
            submissions.append(sub)

        primary_tenure = submissions[-1]["tenure_type"] if not is_disputed else "disputed"
        validated_records.append({
            "parcel_id": parcel_id, "ai_draft_id": draft_id, "boundary_action": c["action"],
            "boundary_iou_vs_ai_draft": c["iou"], "tenure_type": primary_tenure,
            "dispute_flag": is_disputed, "n_claimants": len(claimants),
            "geometry": final_geom,
        })

    # Any true parcel the AI draft missed entirely still gets walked and submitted fresh.
    for t_idx in missed:
        true_geom = true_gdf.geometry.iloc[t_idx]
        parcel_id = true_gdf.iloc[t_idx]["parcel_id"]
        enumerator = rng.choice(ENUMERATORS)
        claimants = occupants[occupants.parcel_id == parcel_id]
        is_disputed = len(claimants) > 1
        for _, hh in claimants.iterrows():
            ts = next_timestamp()
            submissions.append({
                "_id": len(submissions) + 1, "_uuid": str(uuid.uuid4()),
                "start": ts.isoformat(), "end": (ts + datetime.timedelta(minutes=6)).isoformat(), "today": ts.date().isoformat(),
                "enumerator_id": enumerator, "ai_draft_id": None, "parcel_id": parcel_id,
                "boundary_action": "new_parcel_not_in_ai_draft", "rejection_reason": None,
                "household_id": hh.household_id, "claimant_name": hh.occupant_name,
                "household_size": int(hh.household_size), "tenure_type": draw_tenure(),
                "dispute_flag": "yes" if is_disputed else "no",
                "dispute_notes": rng.choice(DISPUTE_NOTES) if is_disputed else None,
                "evidence_photo": None, "gps_accuracy_m": round(float(rng.uniform(1.5, 5.0)), 1),
                "notes": "Parcel entirely missed by the AI draft.",
            })
        validated_records.append({
            "parcel_id": parcel_id, "ai_draft_id": None, "boundary_action": "new_parcel_not_in_ai_draft",
            "boundary_iou_vs_ai_draft": None, "tenure_type": "disputed" if is_disputed else submissions[-1]["tenure_type"],
            "dispute_flag": is_disputed, "n_claimants": len(claimants),
            "geometry": jitter_walk(true_geom, rng),
        })

    submissions_df = pd.DataFrame(submissions)
    submissions_df.to_csv(os.path.join(SYN_DIR, "field_submissions.csv"), index=False)

    validated_gdf = gpd.GeoDataFrame(validated_records, crs=LOCAL_CRS)
    validated_gdf.to_file(os.path.join(SYN_DIR, "validated_parcels.gpkg"), layer="validated_parcels", driver="GPKG")

    n_disputed = validated_gdf.dispute_flag.sum()
    n_photos = len(os.listdir(PHOTOS_DIR))
    print(f"Wrote {len(submissions_df)} field submissions, {len(validated_gdf)} validated parcels "
          f"({n_disputed} disputed), {n_photos} sample evidence photos.")


if __name__ == "__main__":
    main()
