"""Phase 2: runs the trained model over the canonical Phase 1 settlement
(seed 42 -- never seen during training) and vectorizes its predictions
into a candidate parcel-boundary layer. This AI draft is deliberately not
corrected here -- merged plots, missed parcels, and jagged edges are left
as-is; Phase 3's participatory validation step is what catches and fixes
them, same as real FFP pilots that use AI-assisted boundary extraction as
a first pass, not a final answer.

Run: python3 model/predict_boundaries.py
Output: data/synthetic/ai_draft_parcels.gpkg (layer ai_draft_parcels),
outputs/phase2_ai_draft_preview.png, model/eval_report.md
"""

import os
import sys

import geopandas as gpd
import numpy as np
import rasterio
import torch
from PIL import Image, ImageDraw
from rasterio.features import shapes
from scipy import ndimage
from shapely.geometry import shape as shapely_shape

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
from settlement_gen import LOCAL_CRS  # noqa: E402

from unet import UNet  # noqa: E402

REPO_ROOT = os.path.join(os.path.dirname(__file__), "..")
IMAGERY_PATH = os.path.join(REPO_ROOT, "data", "synthetic", "imagery.tif")
GPKG_PATH = os.path.join(REPO_ROOT, "data", "synthetic", "settlement.gpkg")
CKPT_PATH = os.path.join(os.path.dirname(__file__), "checkpoints", "unet_boundary.pt")
OUT_GPKG = os.path.join(REPO_ROOT, "data", "synthetic", "ai_draft_parcels.gpkg")
PREVIEW_PATH = os.path.join(REPO_ROOT, "outputs", "phase2_ai_draft_preview.png")
REPORT_PATH = os.path.join(os.path.dirname(__file__), "eval_report.md")

TILE = 256
STRIDE = 192
MIN_BLOB_AREA_M2 = 5.0


def sliding_window_predict(model, img, device):
    h, w, _ = img.shape
    prob_sum = np.zeros((h, w), dtype=np.float32)
    weight = np.zeros((h, w), dtype=np.float32)

    ys = list(range(0, max(h - TILE, 0) + 1, STRIDE))
    if ys[-1] != h - TILE and h > TILE:
        ys.append(h - TILE)
    xs = list(range(0, max(w - TILE, 0) + 1, STRIDE))
    if xs[-1] != w - TILE and w > TILE:
        xs.append(w - TILE)

    model.eval()
    with torch.no_grad():
        for y in ys:
            for x in xs:
                tile = img[y:y + TILE, x:x + TILE, :]
                th, tw, _ = tile.shape
                pad = np.zeros((TILE, TILE, 3), dtype=np.uint8)
                pad[:th, :tw, :] = tile
                t = torch.from_numpy(pad).float().permute(2, 0, 1).unsqueeze(0) / 255.0
                logits = model(t.to(device))
                probs = torch.sigmoid(logits)[0, 0].cpu().numpy()
                prob_sum[y:y + th, x:x + tw] += probs[:th, :tw]
                weight[y:y + th, x:x + tw] += 1

    return prob_sum / np.maximum(weight, 1)


def vectorize_mask(label_arr, transform, pixel_area, prob_map):
    records = []
    for geom, val in shapes(label_arr.astype(np.int32), mask=label_arr > 0, transform=transform):
        val = int(val)
        poly = shapely_shape(geom).buffer(0)
        if poly.is_empty:
            continue
        area_m2 = poly.area
        if area_m2 < MIN_BLOB_AREA_M2:
            continue
        blob_mask = label_arr == val
        confidence = float(prob_map[blob_mask].mean())
        records.append({"geometry": poly.simplify(0.2), "area_m2": round(area_m2, 2), "confidence": round(confidence, 3)})
    return records


def evaluate(true_gdf, draft_gdf, pred_mask, true_mask):
    inter = np.logical_and(pred_mask, true_mask).sum()
    union = np.logical_or(pred_mask, true_mask).sum()
    pixel_iou = inter / union if union else 0.0

    sindex = draft_gdf.sindex
    draft_to_true = {}
    missed = 0
    split_true_parcels = 0
    per_parcel_iou = []
    for i, true_geom in true_gdf.geometry.items():
        candidates = list(sindex.intersection(true_geom.bounds))
        overlaps = {idx: true_geom.intersection(draft_gdf.geometry.iloc[idx]).area for idx in candidates}
        hits = [idx for idx, a in overlaps.items() if a > 0.3 * true_geom.area]
        fragments = [idx for idx, a in overlaps.items() if a > 0.1 * true_geom.area]
        if not hits:
            missed += 1
        else:
            best_idx = max(hits, key=lambda idx: overlaps[idx])
            best_draft = draft_gdf.geometry.iloc[best_idx]
            parcel_iou = true_geom.intersection(best_draft).area / true_geom.union(best_draft).area
            per_parcel_iou.append(parcel_iou)
        if len(fragments) > 1:
            split_true_parcels += 1
        for idx in hits:
            draft_to_true.setdefault(idx, []).append(i)
    matched = len(true_gdf) - missed
    per_parcel_iou = np.array(per_parcel_iou)

    merged = sum(1 for v in draft_to_true.values() if len(v) > 1)
    merged_true_parcels = sum(len(v) for v in draft_to_true.values() if len(v) > 1)

    return {
        "pixel_iou": round(float(pixel_iou), 4),
        "true_parcels": len(true_gdf),
        "draft_blobs": len(draft_gdf),
        "matched_true_parcels": matched,
        "missed_true_parcels": missed,
        "true_parcels_split_across_multiple_draft_blobs": split_true_parcels,
        "mean_per_parcel_boundary_iou": round(float(per_parcel_iou.mean()), 4),
        "worst_per_parcel_boundary_iou": round(float(per_parcel_iou.min()), 4),
        "parcels_below_0.85_boundary_iou": int((per_parcel_iou < 0.85).sum()),
        "draft_blobs_covering_multiple_parcels": merged,
        "true_parcels_absorbed_into_merged_blobs": merged_true_parcels,
    }


def save_preview(img, true_gdf, draft_gdf, transform, out_path):
    im = Image.fromarray(img).convert("RGB")
    draw = ImageDraw.Draw(im)

    def to_px(geom):
        return [(~transform * (x, y)) for x, y in geom.exterior.coords]

    for geom in true_gdf.geometry:
        draw.line(to_px(geom), fill=(0, 255, 0), width=1)
    for geom in draft_gdf.geometry:
        draw.line(to_px(geom), fill=(255, 0, 255), width=2)

    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    im.save(out_path)


def main():
    device = "mps" if torch.backends.mps.is_available() else "cpu"

    with rasterio.open(IMAGERY_PATH) as src:
        img = np.moveaxis(src.read(), 0, -1)
        transform = src.transform
        pixel_area = abs(transform.a * transform.e)

    model = UNet().to(device)
    model.load_state_dict(torch.load(CKPT_PATH, map_location=device))

    prob_map = sliding_window_predict(model, img, device)
    binary = prob_map > 0.5
    binary = ndimage.binary_opening(binary, structure=np.ones((3, 3)))

    labeled, n_labels = ndimage.label(binary, structure=np.ones((3, 3)))
    print(f"Raw connected components: {n_labels}")

    records = vectorize_mask(labeled, transform, pixel_area, prob_map)
    draft_gdf = gpd.GeoDataFrame(
        {"draft_id": [f"AI{i + 1:04d}" for i in range(len(records))],
         "area_m2": [r["area_m2"] for r in records],
         "confidence": [r["confidence"] for r in records]},
        geometry=[r["geometry"] for r in records], crs=LOCAL_CRS,
    )
    draft_gdf.to_file(OUT_GPKG, layer="ai_draft_parcels", driver="GPKG")
    print(f"Wrote {len(draft_gdf)} AI draft parcels to {OUT_GPKG}")

    true_gdf = gpd.read_file(GPKG_PATH, layer="parcels")
    from rasterio.features import rasterize as rio_rasterize
    true_mask = rio_rasterize(
        [(g, 1) for g in true_gdf.geometry], out_shape=binary.shape, transform=transform, fill=0
    ).astype(bool)

    metrics = evaluate(true_gdf, draft_gdf, binary, true_mask)
    lines = ["# Phase 2 evaluation -- AI draft vs true parcels (canonical seed-42 settlement, unseen during training)\n"]
    for k, v in metrics.items():
        lines.append(f"- **{k}**: {v}")
    report = "\n".join(lines) + "\n"
    with open(REPORT_PATH, "w") as f:
        f.write(report)
    print(report)

    save_preview(img, true_gdf, draft_gdf, transform, PREVIEW_PATH)
    print(f"Wrote preview to {PREVIEW_PATH}")


if __name__ == "__main__":
    main()
