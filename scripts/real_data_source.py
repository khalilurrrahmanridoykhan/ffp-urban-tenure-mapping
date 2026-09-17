"""Real-imagery foundation: replaces settlement_gen.py's procedural
generation with a real drone orthomosaic and real OSM building footprints
over an actual informal settlement -- Mburahati, Dar es Salaam, Tanzania.

Source data:
- Imagery: "Mabibo Mburahati 2024", a 2024 drone orthomosaic (2.1cm/px,
  DJI Mavic 2 Pro), provider OMDTZ / Iddy Chazua, via OpenAerialMap
  (https://map.openaerialmap.org, hosted by HOTOSM). License: CC-BY 4.0.
- Building footprints: OpenStreetMap, via the Overpass API. License:
  ODbL. (c) OpenStreetMap contributors.

Both are real, both are attributed here and in every README that uses
this data. What's NOT real: every occupant, household, tenure claim, and
dispute layered on top from Phase 3 onward -- entirely synthetic, same as
before.

**Coordinates are deliberately stripped.** Real lon/lat never appears in
any output file. Each AOI's real Web Mercator (EPSG:3857) coordinates
are translated to an arbitrary local origin before anything is written,
so no file in this repo lets you reverse-locate a specific building to
its real street address -- you'd need the real imagery's own visual
content for that, which is an inherent limit of using real imagery at
all, not something any coordinate-stripping can fix.

Run standalone to fetch the full grid: python3 scripts/real_data_source.py
"""

import math
import os
import time

import geopandas as gpd
import numpy as np
import pandas as pd
import rasterio
import requests
from rasterio.transform import from_origin
from shapely.geometry import Polygon, box
from shapely.ops import transform as shp_transform
import pyproj

from settlement_gen import build_occupants

SOURCE_TILE_TEMPLATE = "https://tiles.openaerialmap.org/675568899da8040001df994d/0/675568899da8040001df994e/{z}/{x}/{y}"
SOURCE_ATTRIBUTION = ("Imagery: \"Mabibo Mburahati 2024\", OMDTZ / Iddy Chazua, via OpenAerialMap "
                      "(CC-BY 4.0). Building footprints: (c) OpenStreetMap contributors (ODbL).")
OVERPASS_URL = "https://overpass.kumi.systems/api/interpreter"
ZOOM = 20
TILE_PX = 256

_to_3857 = pyproj.Transformer.from_crs("EPSG:4326", "EPSG:3857", always_xy=True).transform
_to_4326 = pyproj.Transformer.from_crs("EPSG:3857", "EPSG:4326", always_xy=True).transform


def deg2num(lon, lat, zoom):
    lat_rad = math.radians(lat)
    n = 2 ** zoom
    x = (lon + 180.0) / 360.0 * n
    y = (1.0 - math.log(math.tan(lat_rad) + 1 / math.cos(lat_rad)) / math.pi) / 2.0 * n
    return x, y


def num2deg(x, y, zoom):
    n = 2 ** zoom
    lon = x / n * 360.0 - 180.0
    lat_rad = math.atan(math.sinh(math.pi * (1 - 2 * y / n)))
    return lon, math.degrees(lat_rad)


def fetch_tile(z, x, y, session):
    url = SOURCE_TILE_TEMPLATE.format(z=z, x=x, y=y)
    for attempt in range(3):
        try:
            r = session.get(url, timeout=20, allow_redirects=True)
            if r.status_code == 200 and r.content:
                return r.content
        except requests.RequestException:
            pass
        time.sleep(1)
    return None


def fetch_mosaic(lon_min, lat_min, lon_max, lat_max, cache_dir=None):
    """Fetches and mosaics real OAM tiles covering the given lon/lat box.
    Returns (image_array HxWx3 uint8, mercator_transform, merc_bounds)."""
    from PIL import Image
    import io

    xmin_f, ymax_f = deg2num(lon_min, lat_max, ZOOM)
    xmax_f, ymin_f = deg2num(lon_max, lat_min, ZOOM)
    x0, x1 = int(math.floor(xmin_f)), int(math.ceil(xmax_f))
    y0, y1 = int(math.floor(ymax_f)), int(math.ceil(ymin_f))
    n_cols, n_rows = x1 - x0, y1 - y0

    mosaic = np.zeros((n_rows * TILE_PX, n_cols * TILE_PX, 3), dtype=np.uint8)
    session = requests.Session()
    missing = 0
    for row, ty in enumerate(range(y0, y1)):
        for col, tx in enumerate(range(x0, x1)):
            cache_path = os.path.join(cache_dir, f"{ZOOM}_{tx}_{ty}.png") if cache_dir else None
            content = None
            if cache_path and os.path.exists(cache_path):
                content = open(cache_path, "rb").read()
            else:
                content = fetch_tile(ZOOM, tx, ty, session)
                if content and cache_path:
                    os.makedirs(cache_dir, exist_ok=True)
                    open(cache_path, "wb").write(content)
            if content:
                tile_img = np.array(Image.open(io.BytesIO(content)).convert("RGB"))
                mosaic[row * TILE_PX:(row + 1) * TILE_PX, col * TILE_PX:(col + 1) * TILE_PX, :] = tile_img
            else:
                missing += 1

    if missing:
        print(f"  warning: {missing}/{n_cols * n_rows} tiles failed to fetch")

    # Web Mercator (EPSG:3857) bounds of the fetched tile grid
    merc_xmin, merc_ymax = _tile_to_merc(x0, y0)
    merc_xmax, merc_ymin = _tile_to_merc(x1, y1)
    res = (merc_xmax - merc_xmin) / (n_cols * TILE_PX)
    transform = from_origin(merc_xmin, merc_ymax, res, res)
    return mosaic, transform, (merc_xmin, merc_ymin, merc_xmax, merc_ymax)


def _tile_to_merc(x, y, zoom=ZOOM):
    lon, lat = num2deg(x, y, zoom)
    return _to_3857(lon, lat)


def fetch_osm_buildings(lon_min, lat_min, lon_max, lat_max, cache_path=None):
    if cache_path and os.path.exists(cache_path):
        gdf = gpd.read_file(cache_path)
        return gdf.to_crs("EPSG:3857") if gdf.crs and gdf.crs.to_epsg() != 3857 else gdf

    query = f"""
    [out:json][timeout:120];
    (
      way["building"]({lat_min},{lon_min},{lat_max},{lon_max});
    );
    out geom;
    """
    for attempt in range(5):
        try:
            r = requests.post(OVERPASS_URL, data={"data": query}, timeout=150)
        except requests.RequestException:
            time.sleep(15 * (attempt + 1))
            continue
        if r.status_code in (429, 502, 503, 504):
            time.sleep(15 * (attempt + 1))
            continue
        r.raise_for_status()
        break
    else:
        raise RuntimeError("Overpass API unavailable after 5 retries")
    elements = r.json()["elements"]

    polys = []
    for el in elements:
        if el.get("type") != "way" or "geometry" not in el:
            continue
        coords = [(pt["lon"], pt["lat"]) for pt in el["geometry"]]
        if len(coords) < 4:
            continue
        poly = Polygon(coords)
        if poly.is_valid and poly.area > 0:
            polys.append({"osm_id": el["id"], "geometry": poly})

    gdf = gpd.GeoDataFrame(polys, crs="EPSG:4326")
    if cache_path:
        os.makedirs(os.path.dirname(cache_path), exist_ok=True)
        gdf.to_file(cache_path, driver="GeoJSON")
    gdf["geometry"] = gdf.geometry.apply(lambda g: shp_transform(_to_3857, g))
    gdf.set_crs("EPSG:3857", allow_override=True, inplace=True)
    return gdf


def build_real_settlement(bbox_4326, all_buildings_3857, cache_dir=None, min_area_m2=6.0, max_area_m2=400.0):
    """Builds one AOI's settlement from a real image (freshly tiled for
    this bbox) and real buildings (sliced from an already-fetched,
    whole-extent GeoDataFrame -- so Overpass is only queried once total,
    not once per AOI). Re-origins everything to local metres (0,0 at the
    bbox's SW corner) -- real shapes and real relative positions, no
    absolute real-world coordinate retained in the output."""
    lon_min, lat_min, lon_max, lat_max = bbox_4326

    mosaic, merc_transform, merc_bounds = fetch_mosaic(lon_min, lat_min, lon_max, lat_max, cache_dir)

    aoi_merc = box(*_to_3857(lon_min, lat_min), *_to_3857(lon_max, lat_max))
    buildings = all_buildings_3857[all_buildings_3857.intersects(aoi_merc)].copy()
    origin_x, origin_y = aoi_merc.bounds[0], aoi_merc.bounds[1]

    def to_local(x, y):
        return x - origin_x, y - origin_y

    buildings["geometry"] = buildings.geometry.intersection(aoi_merc)
    buildings = buildings[buildings.geometry.geom_type.isin(["Polygon"])]
    buildings["geometry"] = buildings.geometry.apply(lambda g: shp_transform(to_local, g))
    buildings["area_m2"] = buildings.geometry.area.round(2)
    buildings = buildings[(buildings.area_m2 >= min_area_m2) & (buildings.area_m2 <= max_area_m2)]
    buildings = buildings.reset_index(drop=True)
    buildings["parcel_id"] = [f"P{i + 1:04d}" for i in range(len(buildings))]
    buildings = buildings[["parcel_id", "area_m2", "geometry"]]

    # crop the mercator mosaic down to exactly the AOI, re-origin its transform to local metres
    inv = ~merc_transform
    col0, row1 = inv * (aoi_merc.bounds[0], aoi_merc.bounds[1])
    col1, row0 = inv * (aoi_merc.bounds[2], aoi_merc.bounds[3])
    col0, col1 = int(max(col0, 0)), int(min(col1, mosaic.shape[1]))
    row0, row1 = int(max(row0, 0)), int(min(row1, mosaic.shape[0]))
    img = mosaic[row0:row1, col0:col1, :]

    res = merc_transform.a
    local_transform = from_origin(0, img.shape[0] * res, res, res)

    boundary = Polygon([(0, 0), (img.shape[1] * res, 0), (img.shape[1] * res, img.shape[0] * res), (0, img.shape[0] * res)])

    return {"boundary": boundary, "parcels_gdf": gpd.GeoDataFrame(buildings, geometry="geometry"),
            "image": img, "transform": local_transform, "width": img.shape[1], "height": img.shape[0]}


FULL_EXTENT_4326 = (39.229123, -6.813991, 39.241473, -6.804107)

# 16 non-overlapping 150x150m cells (15m gaps) picked from the full drone
# image extent by real OSM building density (top 16 of 48 candidate
# cells) -- hardcoded so every rerun fetches the exact same AOIs
# regardless of later OSM edits. "canonical" is the one every phase from
# 3 onward is built on; the 12 train_* + 3 val_* are Phase 2's model
# training data, spatially disjoint from canonical and from each other.
AOIS_4326 = {
    "canonical": (39.233657, -6.809592, 39.235004, -6.808254),
    "train_01": (39.233657, -6.811063, 39.235004, -6.809725),
    "train_02": (39.235139, -6.812535, 39.236487, -6.811197),
    "train_03": (39.229210, -6.811063, 39.230558, -6.809725),
    "train_04": (39.232175, -6.809592, 39.233522, -6.808254),
    "train_05": (39.233657, -6.812535, 39.235004, -6.811197),
    "train_06": (39.239586, -6.808120, 39.240933, -6.806782),
    "train_07": (39.230693, -6.809592, 39.232040, -6.808254),
    "train_08": (39.236621, -6.814007, 39.237969, -6.812669),
    "train_09": (39.229210, -6.809592, 39.230558, -6.808254),
    "train_10": (39.232175, -6.811063, 39.233522, -6.809725),
    "train_11": (39.230693, -6.808120, 39.232040, -6.806782),
    "train_12": (39.229210, -6.812535, 39.230558, -6.811197),
    "val_01": (39.238104, -6.808120, 39.239451, -6.806782),
    "val_02": (39.235139, -6.814007, 39.236487, -6.812669),
    "val_03": (39.230693, -6.812535, 39.232040, -6.811197),
}


def get_all_buildings(cache_path="/tmp/oam_tile_cache/mburahati_buildings.geojson"):
    return fetch_osm_buildings(*FULL_EXTENT_4326, cache_path=cache_path)


if __name__ == "__main__":
    all_buildings = get_all_buildings()
    print(f"total buildings in full extent: {len(all_buildings)}")
    s = build_real_settlement(AOIS_4326["canonical"], all_buildings, cache_dir="/tmp/oam_tile_cache")
    print(f"canonical buildings: {len(s['parcels_gdf'])}, image: {s['image'].shape}")
