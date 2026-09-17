"""Phase 1: generates the synthetic informal-settlement parcel fabric,
occupant/household roster, and a matching overhead "imagery" raster that
Phase 2's boundary-extraction model and every later phase build on.

Everything here is procedurally generated -- no real settlement, no real
occupant, no real imagery. The parcel fabric is built by recursively
subdividing a fictional settlement boundary (a road and a canal strip
carved off first, the remainder split into irregular cells, each eroded
inward by a random gap so adjacent parcels never touch -- the gaps become
the informal footpath network). The raster is a synthetic "orthophoto"
painted directly from that vector fabric, not derived from any real
imagery source.

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
import numpy as np
import pandas as pd
import rasterio
from rasterio.features import rasterize
from rasterio.transform import from_origin
from shapely.geometry import LineString, Polygon
from shapely.ops import split, unary_union

LOCAL_CRS = "+proj=tmerc +lat_0=0 +lon_0=0 +k=1 +x_0=500000 +y_0=0 +datum=WGS84 +units=m +no_defs +type=crs"

OUT_DIR = os.path.join(os.path.dirname(__file__), "..", "data", "synthetic")

FIRST_NAMES = ["Rahim", "Karim", "Amina", "Salma", "Jasim", "Fatema", "Hasan", "Nurjahan", "Belal", "Rekha",
               "Shafiq", "Momtaz", "Kamal", "Rina", "Anwar", "Shirin", "Habib", "Parvin", "Sultan", "Ruma"]
LAST_NAMES = ["Mia", "Begum", "Sheikh", "Islam", "Talukder", "Akter", "Molla", "Hossain", "Chowdhury", "Khan"]

ROOF_PALETTE = [
    (150, 150, 155),  # weathered corrugated tin
    (170, 110, 80),   # rusted tin
    (60, 90, 130),    # blue tarp
    (140, 40, 40),    # faded red tin
    (100, 100, 100),  # grey tin
]


def make_boundary(rng):
    """An irregular ~140m x 190m settlement extent -- a perturbed rectangle,
    not a clean geometric shape."""
    w, h = 140.0, 190.0
    base = [(0, 0), (w, 0), (w, h), (0, h)]
    pts = []
    for i in range(len(base)):
        x0, y0 = base[i]
        x1, y1 = base[(i + 1) % len(base)]
        pts.append((x0, y0))
        mx, my = (x0 + x1) / 2, (y0 + y1) / 2
        jitter = rng.uniform(-8, 8)
        if x0 == x1:  # vertical edge, jitter outward/inward in x
            pts.append((mx + jitter, my))
        else:  # horizontal edge, jitter in y
            pts.append((mx, my + jitter))
    return Polygon(pts).buffer(0)


def carve_strip(boundary, edge, width, rng):
    """Cuts a road/canal strip off one edge of the boundary's bounding box
    and returns (strip_polygon, remaining_polygon)."""
    minx, miny, maxx, maxy = boundary.bounds
    if edge == "north":
        strip = Polygon([(minx - 5, maxy - width), (maxx + 5, maxy - width), (maxx + 5, maxy + 5), (minx - 5, maxy + 5)])
    elif edge == "south":
        strip = Polygon([(minx - 5, miny - 5), (maxx + 5, miny - 5), (maxx + 5, miny + width), (minx - 5, miny + width)])
    else:
        raise ValueError(edge)
    strip = strip.intersection(boundary)
    remaining = boundary.difference(strip)
    return strip, remaining


def bsp_subdivide(poly, rng, min_area=22.0, max_area=85.0, depth=0, max_depth=9):
    """Recursively splits a polygon into irregular cells by cutting across
    its longer axis at a randomised fraction, until each cell falls in the
    target parcel-size range or the depth limit is hit."""
    if poly.is_empty or poly.area < min_area * 0.5:
        return []
    if (poly.area <= max_area and depth > 0) or depth >= max_depth:
        return [poly]

    minx, miny, maxx, maxy = poly.bounds
    dx, dy = maxx - minx, maxy - miny
    frac = rng.uniform(0.4, 0.6)
    if dx >= dy:
        cut_x = minx + dx * frac
        divider = LineString([(cut_x, miny - 5), (cut_x, maxy + 5)])
    else:
        cut_y = miny + dy * frac
        divider = LineString([(minx - 5, cut_y), (maxx + 5, cut_y)])

    try:
        pieces = list(split(poly, divider).geoms)
    except Exception:
        return [poly]

    if len(pieces) < 2:
        return [poly]

    out = []
    for piece in pieces:
        if piece.geom_type != "Polygon" or piece.is_empty:
            continue
        out.extend(bsp_subdivide(piece, rng, min_area, max_area, depth + 1, max_depth))
    return out if out else [poly]


def jitter_vertices(poly, rng, magnitude=0.35):
    """Nudges each corner independently so parcels read as hand-adjudicated
    plots rather than clean machine-cut rectangles."""
    coords = list(poly.exterior.coords)[:-1]
    jittered = [(x + rng.uniform(-magnitude, magnitude), y + rng.uniform(-magnitude, magnitude)) for x, y in coords]
    jittered.append(jittered[0])
    out = Polygon(jittered).buffer(0)
    return out if out.is_valid and not out.is_empty else poly


def build_parcels(buildable, rng):
    cells = bsp_subdivide(buildable, rng)
    parcels = []
    for cell in cells:
        gap = rng.uniform(0.5, 1.1)
        eroded = cell.buffer(-gap)
        if eroded.is_empty or eroded.area < 6.0:
            continue
        if eroded.geom_type == "MultiPolygon":
            eroded = max(eroded.geoms, key=lambda g: g.area)
        eroded = jitter_vertices(eroded, rng)
        if eroded.is_empty or eroded.area < 6.0:
            continue
        parcels.append(eroded)
    return parcels


def build_occupants(parcels_gdf, rng):
    rows = []
    hh_counter = 1
    for _, row in parcels_gdf.iterrows():
        n_households = 1 if row.area_m2 < 45 else rng.choice([1, 1, 2])
        for _ in range(n_households):
            name = f"{rng.choice(FIRST_NAMES)} {rng.choice(LAST_NAMES)}"
            rows.append({
                "household_id": f"SYN-HH-{hh_counter:04d}",
                "parcel_id": row.parcel_id,
                "occupant_name": name,
                "household_size": int(rng.integers(1, 8)),
                "is_synthetic": True,
            })
            hh_counter += 1
    return pd.DataFrame(rows)


def render_imagery(boundary, road, canal, parcels_gdf, paths, rng, pixel_size=0.15, out_path=None):
    minx, miny, maxx, maxy = boundary.buffer(3).bounds
    width = int((maxx - minx) / pixel_size)
    height = int((maxy - miny) / pixel_size)
    transform = from_origin(minx, maxy, pixel_size, pixel_size)

    def rasterize_shape(geom):
        return rasterize([(geom, 1)], out_shape=(height, width), transform=transform, fill=0, dtype="uint8")

    img = rng.integers(150, 185, size=(height, width, 3), dtype=np.uint8)
    img[:, :, 1] = (img[:, :, 1].astype(int) - 15).clip(0, 255).astype(np.uint8)
    img[:, :, 2] = (img[:, :, 2].astype(int) - 40).clip(0, 255).astype(np.uint8)

    path_mask = rasterize_shape(paths).astype(bool)
    path_noise = rng.integers(-10, 10, size=(height, width))
    for c, base in zip(range(3), (165, 140, 105)):
        band = img[:, :, c].astype(int)
        band[path_mask] = (base + path_noise[path_mask]).clip(0, 255)
        img[:, :, c] = band.astype(np.uint8)

    road_mask = rasterize_shape(road).astype(bool)
    for c, base in zip(range(3), (120, 118, 112)):
        band = img[:, :, c].astype(int)
        band[road_mask] = (base + rng.integers(-8, 8, size=road_mask.sum())).clip(0, 255)
        img[:, :, c] = band.astype(np.uint8)

    canal_mask = rasterize_shape(canal).astype(bool)
    for c, base in zip(range(3), (50, 80, 110)):
        band = img[:, :, c].astype(int)
        band[canal_mask] = (base + rng.integers(-12, 12, size=canal_mask.sum())).clip(0, 255)
        img[:, :, c] = band.astype(np.uint8)

    for _, row in parcels_gdf.iterrows():
        mask = rasterize_shape(row.geometry).astype(bool)
        if not mask.any():
            continue
        r, g, b = ROOF_PALETTE[rng.integers(0, len(ROOF_PALETTE))]
        n = int(mask.sum())
        streak = (rng.integers(-18, 18, size=n))
        img[:, :, 0][mask] = np.clip(r + streak, 0, 255).astype(np.uint8)
        img[:, :, 1][mask] = np.clip(g + streak, 0, 255).astype(np.uint8)
        img[:, :, 2][mask] = np.clip(b + streak, 0, 255).astype(np.uint8)

    path_polys = [paths] if paths.geom_type == "Polygon" else list(paths.geoms)
    for _ in range(35):
        poly = path_polys[rng.integers(0, len(path_polys))]
        if poly.area < 1:
            continue
        minx2, miny2, maxx2, maxy2 = poly.bounds
        for _try in range(5):
            px, py = rng.uniform(minx2, maxx2), rng.uniform(miny2, maxy2)
            pt = Polygon([(px - 0.4, py - 0.4), (px + 0.4, py - 0.4), (px + 0.4, py + 0.4), (px - 0.4, py + 0.4)])
            if poly.contains(pt.centroid):
                mask = rasterize_shape(pt).astype(bool)
                img[:, :, 0][mask] = np.clip(60 + rng.integers(-10, 10), 0, 255)
                img[:, :, 1][mask] = np.clip(110 + rng.integers(-10, 10), 0, 255)
                img[:, :, 2][mask] = np.clip(50 + rng.integers(-10, 10), 0, 255)
                break

    with rasterio.open(
        out_path, "w", driver="GTiff", height=height, width=width, count=3,
        dtype="uint8", crs=LOCAL_CRS, transform=transform,
    ) as dst:
        for i in range(3):
            dst.write(img[:, :, i], i + 1)


def main(seed):
    rng = np.random.default_rng(seed)
    os.makedirs(OUT_DIR, exist_ok=True)

    boundary = make_boundary(rng)
    road, remaining = carve_strip(boundary, "north", 5.0, rng)
    canal, buildable = carve_strip(remaining, "south", 4.0, rng)

    parcel_geoms = build_parcels(buildable, rng)
    parcels_gdf = gpd.GeoDataFrame(
        {"parcel_id": [f"P{i + 1:04d}" for i in range(len(parcel_geoms))]},
        geometry=parcel_geoms, crs=LOCAL_CRS,
    )
    parcels_gdf["area_m2"] = parcels_gdf.geometry.area.round(2)

    paths = buildable.difference(unary_union(parcels_gdf.geometry.tolist()))

    occupants = build_occupants(parcels_gdf, rng)

    gpkg_path = os.path.join(OUT_DIR, "settlement.gpkg")
    gpd.GeoDataFrame({"name": ["settlement_boundary"]}, geometry=[boundary], crs=LOCAL_CRS).to_file(gpkg_path, layer="boundary", driver="GPKG")
    gpd.GeoDataFrame({"name": ["access_road"]}, geometry=[road], crs=LOCAL_CRS).to_file(gpkg_path, layer="road", driver="GPKG")
    gpd.GeoDataFrame({"name": ["canal"]}, geometry=[canal], crs=LOCAL_CRS).to_file(gpkg_path, layer="canal", driver="GPKG")
    gpd.GeoDataFrame({"name": ["footpaths"]}, geometry=[paths], crs=LOCAL_CRS).to_file(gpkg_path, layer="paths", driver="GPKG")
    parcels_gdf.to_file(gpkg_path, layer="parcels", driver="GPKG")

    occupants.to_csv(os.path.join(OUT_DIR, "occupants.csv"), index=False)

    render_imagery(boundary, road, canal, parcels_gdf, paths, rng, out_path=os.path.join(OUT_DIR, "imagery.tif"))

    print(f"Parcels: {len(parcels_gdf)}, total area {parcels_gdf.area_m2.sum():.0f} m2, "
          f"occupants: {len(occupants)}")
    print(f"Wrote {gpkg_path}, occupants.csv, imagery.tif to {OUT_DIR}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed", type=int, default=42)
    args = ap.parse_args()
    main(args.seed)
