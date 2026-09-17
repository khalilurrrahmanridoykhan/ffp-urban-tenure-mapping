"""Generates the Phase 3/5/6 QA-style preview PNGs (Phase 2's own
preview is written directly by model/predict_boundaries.py). Kept as a
standalone script -- previously these were one-off commands, which isn't
reproducible; this fixes that.

Run: python3 scripts/generate_previews.py
Output: outputs/phase3_field_validation_preview.png,
outputs/phase5_adjudication_queue_preview.png,
outputs/phase6_tenure_security_map.png
"""

import os

import geopandas as gpd
import numpy as np
import pandas as pd
import rasterio
from PIL import Image, ImageDraw

REPO_ROOT = os.path.join(os.path.dirname(__file__), "..")
SYN_DIR = os.path.join(REPO_ROOT, "data", "synthetic")
OUT_DIR = os.path.join(REPO_ROOT, "outputs")


def load_imagery():
    with rasterio.open(os.path.join(SYN_DIR, "imagery.tif")) as src:
        return np.moveaxis(src.read(), 0, -1), src.transform


def to_px(geom, transform):
    return [(~transform * (x, y)) for x, y in geom.exterior.coords]


def phase3_preview():
    img, transform = load_imagery()
    v = gpd.read_file(os.path.join(SYN_DIR, "validated_parcels.gpkg"), layer="validated_parcels")
    colors = {"confirm_ai_draft": (0, 255, 0), "correct_boundary": (255, 165, 0), "new_parcel_not_in_ai_draft": (0, 200, 255)}

    im = Image.fromarray(img).convert("RGB")
    draw = ImageDraw.Draw(im)
    for _, row in v.iterrows():
        col = (255, 0, 255) if row.dispute_flag else colors.get(row.boundary_action, (200, 200, 200))
        w = 3 if row.dispute_flag else 1
        draw.line(to_px(row.geometry, transform), fill=col, width=w)
    im.save(os.path.join(OUT_DIR, "phase3_field_validation_preview.png"))


def phase5_preview():
    img, transform = load_imagery()
    sp = gpd.read_file(os.path.join(SYN_DIR, "stdm.gpkg"), layer="spatial_unit")
    q = pd.read_csv(os.path.join(SYN_DIR, "adjudication_queue.csv"))

    dup_ids, conflict_ids, lowconf_ids = set(), set(), set()
    for ids in q[q.category == "duplicate_claim"].spatial_unit_ids:
        dup_ids.update(ids.split(";"))
    for ids in q[q.category.isin(["boundary_conflict", "overlap"])].spatial_unit_ids:
        conflict_ids.update(ids.split(";"))
    for ids in q[q.category == "low_confidence_confirmation"].spatial_unit_ids:
        lowconf_ids.update(ids.split(";"))

    im = Image.fromarray(img).convert("RGB")
    draw = ImageDraw.Draw(im)
    for _, row in sp.iterrows():
        sid = row.spatial_unit_id
        if sid in dup_ids:
            draw.line(to_px(row.geometry, transform), fill=(255, 0, 255), width=3)
        elif sid in conflict_ids:
            draw.line(to_px(row.geometry, transform), fill=(255, 140, 0), width=3)
        elif sid in lowconf_ids:
            draw.line(to_px(row.geometry, transform), fill=(255, 230, 0), width=1)
        else:
            draw.line(to_px(row.geometry, transform), fill=(60, 60, 60), width=1)
    im.save(os.path.join(OUT_DIR, "phase5_adjudication_queue_preview.png"))


def phase6_preview():
    img, transform = load_imagery()
    g = gpd.read_file(os.path.join(SYN_DIR, "tenure_security.gpkg"), layer="tenure_security")
    colors = {"secure": (40, 160, 60), "moderate": (230, 200, 40), "at_risk": (230, 120, 30), "contested": (200, 20, 120)}

    base = Image.fromarray(img).convert("RGB")
    overlay = Image.new("RGBA", base.size, (0, 0, 0, 0))
    odraw = ImageDraw.Draw(overlay)
    for _, row in g.iterrows():
        col = colors[row.security_class]
        odraw.polygon(to_px(row.geometry, transform), fill=col + (140,), outline=col + (255,))
    out = Image.alpha_composite(base.convert("RGBA"), overlay).convert("RGB")
    out.save(os.path.join(OUT_DIR, "phase6_tenure_security_map.png"))


if __name__ == "__main__":
    phase3_preview()
    phase5_preview()
    phase6_preview()
    print(f"Wrote phase3/5/6 previews to {OUT_DIR}")
