"""Phase 1: generates the synthetic informal-settlement parcel fabric,
occupant/household roster, and a matching overhead "imagery" raster that
Phase 2's boundary-extraction model and every later phase build on.

Everything here is procedurally generated -- no real settlement, no real
occupant, no real imagery. See settlement_gen.py for the generation
procedure itself (shared with Phase 2's training-data builder); this
script just runs it for the canonical seed and writes the committed
output files.

The coordinate reference system is an arbitrary local projection centered
on lon=0, lat=0 ("Null Island") -- chosen specifically so the data cannot
be read as any real place, while still being a valid projected CRS in
metres for QGIS tooling (scale bars, area/distance measurement) to work
against normally.

Run: python3 scripts/generate_synthetic_settlement.py [--seed 42]
Output: data/synthetic/settlement.gpkg (layers: boundary, road, canal,
paths, parcels), data/synthetic/occupants.csv, data/synthetic/imagery.tif
"""

import argparse
import os

import geopandas as gpd

from settlement_gen import LOCAL_CRS, build_settlement, render_imagery

OUT_DIR = os.path.join(os.path.dirname(__file__), "..", "data", "synthetic")


def main(seed):
    os.makedirs(OUT_DIR, exist_ok=True)
    s = build_settlement(seed)

    gpkg_path = os.path.join(OUT_DIR, "settlement.gpkg")
    gpd.GeoDataFrame({"name": ["settlement_boundary"]}, geometry=[s["boundary"]], crs=LOCAL_CRS).to_file(gpkg_path, layer="boundary", driver="GPKG")
    gpd.GeoDataFrame({"name": ["access_road"]}, geometry=[s["road"]], crs=LOCAL_CRS).to_file(gpkg_path, layer="road", driver="GPKG")
    gpd.GeoDataFrame({"name": ["canal"]}, geometry=[s["canal"]], crs=LOCAL_CRS).to_file(gpkg_path, layer="canal", driver="GPKG")
    gpd.GeoDataFrame({"name": ["footpaths"]}, geometry=[s["paths"]], crs=LOCAL_CRS).to_file(gpkg_path, layer="paths", driver="GPKG")
    s["parcels_gdf"].to_file(gpkg_path, layer="parcels", driver="GPKG")

    s["occupants"].to_csv(os.path.join(OUT_DIR, "occupants.csv"), index=False)

    render_imagery(
        s["boundary"], s["road"], s["canal"], s["parcels_gdf"], s["paths"], s["rng"],
        out_path=os.path.join(OUT_DIR, "imagery.tif"),
        transform=s["transform"], width=s["width"], height=s["height"],
    )

    print(f"Parcels: {len(s['parcels_gdf'])}, total area {s['parcels_gdf'].area_m2.sum():.0f} m2, "
          f"occupants: {len(s['occupants'])}")
    print(f"Wrote {gpkg_path}, occupants.csv, imagery.tif to {OUT_DIR}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed", type=int, default=42)
    args = ap.parse_args()
    main(args.seed)
