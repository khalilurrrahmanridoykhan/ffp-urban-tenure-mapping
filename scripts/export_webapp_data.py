"""Phase 7: exports static snapshots of the synthetic dataset for the
dashboard -- a plain JPEG of the imagery, GeoJSON of the tenure-security
layer (coordinates converted from the local meters CRS into Leaflet
CRS.Simple pixel space, matching the image), and the adjudication queue
as JSON. No server, no live queries -- the dashboard reads these files
directly.

Run: python3 scripts/export_webapp_data.py
Output: webapp/data/imagery.jpg, webapp/data/tenure_security.geojson,
webapp/data/adjudication_queue.json, webapp/data/meta.json
"""

import json
import os
import sqlite3

import geopandas as gpd
import pandas as pd
import rasterio
from PIL import Image

REPO_ROOT = os.path.join(os.path.dirname(__file__), "..")
SYN_DIR = os.path.join(REPO_ROOT, "data", "synthetic")
OUT_DIR = os.path.join(REPO_ROOT, "webapp", "data")


def meters_to_pixel_xy(x, y, transform, height):
    """Converts a local-CRS (metres) coordinate to Leaflet CRS.Simple
    [x, y] pixel space, where y=0 is the image's bottom edge (matching
    an image overlay with bounds [[0,0],[height,width]])."""
    col, row = ~transform * (x, y)
    return [col, height - row]


def convert_geometry(geom, transform, height):
    def convert_ring(coords):
        return [meters_to_pixel_xy(x, y, transform, height) for x, y in coords]

    if geom.geom_type == "Polygon":
        return {"type": "Polygon", "coordinates": [convert_ring(geom.exterior.coords)]}
    raise ValueError(f"Unsupported geometry type: {geom.geom_type}")


def main():
    os.makedirs(OUT_DIR, exist_ok=True)

    with rasterio.open(os.path.join(SYN_DIR, "imagery.tif")) as src:
        import numpy as np
        arr = np.moveaxis(src.read(), 0, -1)
        transform = src.transform
        height, width = src.height, src.width

    Image.fromarray(arr).convert("RGB").save(os.path.join(OUT_DIR, "imagery.jpg"), quality=85, optimize=True)

    with open(os.path.join(OUT_DIR, "meta.json"), "w") as f:
        json.dump({"width": width, "height": height}, f)

    security = gpd.read_file(os.path.join(SYN_DIR, "tenure_security.gpkg"), layer="tenure_security")

    conn = sqlite3.connect(os.path.join(SYN_DIR, "stdm.gpkg"))
    party = pd.read_sql("SELECT * FROM party", conn)
    str_table = pd.read_sql("SELECT * FROM social_tenure_relationship", conn)
    conn.close()

    features = []
    for _, row in security.iterrows():
        claims = str_table[str_table.spatial_unit_id == row.spatial_unit_id]
        claim_list = []
        for _, c in claims.iterrows():
            p = party[party.party_id == c.party_id].iloc[0]
            claim_list.append({
                "party_id": c.party_id, "claimant_name": p.full_name,
                "household_size": int(p.household_size), "tenure_type": c.tenure_type_id,
                "str_status": c.str_status, "str_id": c.str_id,
                "documented_by": c.documented_by if isinstance(c.documented_by, str) else None,
            })
        features.append({
            "type": "Feature",
            "geometry": convert_geometry(row.geometry, transform, height),
            "properties": {
                "spatial_unit_id": row.spatial_unit_id,
                "security_class": row.security_class,
                "security_score": int(row.security_score),
                "tenure_type_summary": row.tenure_type_summary,
                "disputed": bool(row.disputed),
                "boundary_conflict": bool(row.boundary_conflict),
                "claims": claim_list,
            },
        })

    with open(os.path.join(OUT_DIR, "tenure_security.geojson"), "w") as f:
        json.dump({"type": "FeatureCollection", "features": features}, f)

    queue = pd.read_csv(os.path.join(SYN_DIR, "adjudication_queue.csv"))
    # DataFrame.to_json (not json.dump on a manually-built dict) is what
    # correctly emits NaN as JSON null -- .where(notna, None) looks right
    # but pandas silently converts None back to NaN on float columns,
    # which produces bare `NaN` tokens that JSON.parse() rejects in the
    # browser (Python's json.load is permissive about it, which is why
    # this didn't show up until testing the actual page).
    queue.to_json(os.path.join(OUT_DIR, "adjudication_queue.json"), orient="records")

    print(f"Wrote imagery.jpg ({width}x{height}), {len(features)} parcels, {len(queue)} queue items to {OUT_DIR}")


if __name__ == "__main__":
    main()
