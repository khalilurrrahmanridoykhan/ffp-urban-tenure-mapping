"""Replaces the procedurally-generated Phase 1 foundation with a real
one: real drone imagery + real OSM building footprints over Korail,
Dhaka (see real_data_source.py for full attribution and the
coordinate-stripping rationale). Occupants remain entirely synthetic,
generated the same way as before (settlement_gen.build_occupants) --
only now attached to real building footprints instead of procedural
ones.

Overwrites data/synthetic/settlement.gpkg (layers: boundary, parcels),
data/synthetic/occupants.csv, data/synthetic/imagery.tif -- the exact
same file contract Phase 1 originally produced, so every downstream
script (Phase 2 onward) needs no changes.

Run: python3 scripts/fetch_real_foundation.py
"""

import os

import geopandas as gpd
import numpy as np
import rasterio

from real_data_source import AOIS_4326, SOURCE_ATTRIBUTION, build_real_settlement, get_all_buildings
from settlement_gen import LOCAL_CRS, build_occupants

OUT_DIR = os.path.join(os.path.dirname(__file__), "..", "data", "synthetic")
CACHE_DIR = os.path.join(os.path.dirname(__file__), "..", ".oam_cache")


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    all_buildings = get_all_buildings(cache_path=os.path.join(CACHE_DIR, "korail_buildings.geojson"))
    s = build_real_settlement(AOIS_4326["canonical"], all_buildings, cache_dir=CACHE_DIR)

    coverage = s["valid_mask"].mean()
    if coverage < 1.0:
        raise RuntimeError(f"Canonical AOI imagery only {coverage:.1%} covered by successfully-fetched "
                            f"tiles -- rerun (tile service throttling) before using this as the committed foundation.")

    parcels_gdf = gpd.GeoDataFrame(s["parcels_gdf"], geometry="geometry", crs=LOCAL_CRS)
    gpkg_path = os.path.join(OUT_DIR, "settlement.gpkg")
    gpd.GeoDataFrame({"name": ["settlement_boundary"]}, geometry=[s["boundary"]], crs=LOCAL_CRS).to_file(gpkg_path, layer="boundary", driver="GPKG")
    parcels_gdf.to_file(gpkg_path, layer="parcels", driver="GPKG")

    rng = np.random.default_rng(42)
    occupants = build_occupants(parcels_gdf, rng)
    occupants.to_csv(os.path.join(OUT_DIR, "occupants.csv"), index=False)

    with rasterio.open(
        os.path.join(OUT_DIR, "imagery.tif"), "w", driver="GTiff",
        height=s["height"], width=s["width"], count=3, dtype="uint8",
        crs=LOCAL_CRS, transform=s["transform"],
    ) as dst:
        for i in range(3):
            dst.write(s["image"][:, :, i], i + 1)

    print(f"Real foundation: {len(parcels_gdf)} real buildings, {len(occupants)} synthetic occupants, "
          f"image {s['width']}x{s['height']} @ {s['transform'].a:.3f} m/px")
    print(SOURCE_ATTRIBUTION)


if __name__ == "__main__":
    main()
