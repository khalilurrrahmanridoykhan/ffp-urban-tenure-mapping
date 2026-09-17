# Geo AI model — AI-assisted boundary extraction

A small U-Net (`unet.py`) that segments building/parcel footprints from
**real drone imagery**, giving a rough first-pass boundary draft for
Phase 3's participatory validation to correct — the same "AI drafts, a
human adjudicates" division of labor real FFP AI-assisted-extraction
pilots use.

## Data

`dataset.py` builds 12 training AOIs and 3 validation AOIs from real
imagery + real OSM building footprints (see
`scripts/real_data_source.py` for the full source and attribution),
tiled into 256×256 patches. **The canonical AOI Phase 1 committed is
never used for training or validation** — Phase 2's evaluation below is
on real imagery the model has genuinely never seen.

No synthetic realism pass is needed here (an earlier fully-synthetic
version of this project needed one — flat-colored procedural imagery
made segmentation trivially easy, >99.9% IoU, zero instance errors).
Real imagery already has real blur, shadow, occlusion, and roof-material
ambiguity between adjacent structures, which is exactly what makes this
version's result below meaningfully harder and more representative.

## Model & training

`unet.py` — a 4-level U-Net, 16→256 channels, ~2M parameters. `train.py`
trains it with a BCE + Dice loss on MPS (Apple Silicon GPU) for 20
epochs. Validation IoU plateaus around **0.75–0.77**, not near-perfect —
consistent with published results on real informal-settlement
building-footprint extraction (dense, touching structures with similar
roof materials are genuinely hard to separate from imagery alone). See
`training_log.md` for the full curve.

Reproduce: `python3 train.py --epochs 20`

## Inference & evaluation

`predict_boundaries.py` runs sliding-window inference over Phase 1's
committed `data/synthetic/imagery.tif` (the real canonical AOI),
thresholds and connects the prediction into blobs, vectorizes each into
a polygon (with a per-blob mean-confidence score), and writes the result
to `data/synthetic/ai_draft_parcels.gpkg` (layer `ai_draft_parcels`) —
the draft Phase 3 works from.

It also scores that draft against Phase 1's true (real) building layer
and writes `eval_report.md`. Current result:

| metric | value |
|---|---|
| pixel IoU | 0.826 |
| true parcels (real buildings) | 231 |
| draft blobs | 74 |
| matched / missed true parcels | 216 / 15 |
| draft blobs covering multiple true parcels | 33 |
| true parcels absorbed into a merged blob | 178 |

Reading this honestly: this is a real, substantial merging problem —
most of the settlement's tightly-packed real buildings get folded into
larger draft blobs rather than kept as separate parcels, and 15 real
buildings are missed by the model entirely. That's not a synthetic
stand-in for imperfection, it's the actual, expected failure mode of
building-footprint segmentation in a dense informal settlement: adjacent
structures sharing walls or near-identical corrugated-tin roofs are
genuinely hard to separate from imagery alone. This is exactly the
material Phase 3's participatory validation exists to resolve — a human
walking the block knows where one household's roof ends and the
neighbour's begins even when the model can't.

Reproduce: `python3 predict_boundaries.py`
