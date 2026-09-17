# Geo AI model — AI-assisted boundary extraction

A small U-Net (`unet.py`) that segments parcel footprints from the
synthetic overhead imagery, giving a rough first-pass boundary draft for
Phase 3's participatory validation to correct — the same "AI drafts, a
human adjudicates" division of labor real FFP AI-assisted-extraction
pilots use.

## Data

`dataset.py` generates 12 training settlements (seeds 1–12) and 3
validation settlements (seeds 101–103) on the fly from
`scripts/settlement_gen.py`, tiled into 256×256 patches. **The canonical
seed-42 settlement Phase 1 committed is never used for training or
validation** — Phase 2's evaluation below is on a settlement the model
has genuinely never seen.

Rendering includes a deliberate realism pass (`degrade_realism` in
`settlement_gen.py`): Gaussian blur + sensor noise applied after the
vector fabric is painted. Without it, the flat-colored, razor-edged
synthetic imagery makes parcel segmentation trivially easy (>99.9% IoU,
zero instance errors) — not a meaningful demonstration of anything. With
it, the model has to contend with the same kind of soft, ambiguous
boundaries real overhead imagery has.

## Model & training

`unet.py` — a 4-level U-Net, 16→256 channels, ~2M parameters. `train.py`
trains it with a BCE + Dice loss on MPS (Apple Silicon GPU). The
checkpoint committed here (`checkpoints/unet_boundary.pt`) was trained
for **5 epochs only** — deliberately brief, representative of a
resource-constrained first pilot rather than a fully converged
production model. See `training_log.md` for the full curve.

Reproduce: `python3 train.py --epochs 5`

## Inference & evaluation

`predict_boundaries.py` runs sliding-window inference over Phase 1's
committed `data/synthetic/imagery.tif`, thresholds and connects the
prediction into blobs, vectorizes each into a polygon (with a per-blob
mean-confidence score), and writes the result to
`data/synthetic/ai_draft_parcels.gpkg` (layer `ai_draft_parcels`) — the
draft Phase 3 works from.

It also scores that draft against Phase 1's true parcel layer and writes
`eval_report.md`. Current result:

| metric | value |
|---|---|
| pixel IoU | 0.981 |
| true parcels | 416 |
| draft blobs | 418 |
| matched / missed true parcels | 416 / 0 |
| true parcels split across multiple draft blobs | 0 |
| mean per-parcel boundary IoU | 0.969 |
| worst per-parcel boundary IoU | 0.917 |

Reading this honestly: the model gets parcel *topology* right (correct
count, no merges, no splits by a 30%-overlap threshold) but not
*precise* boundaries — every matched parcel's drawn outline deviates
visibly from the true survey line (up to ~8% IoU loss on the worst
case), and 2 of the 418 draft blobs don't cleanly correspond to any
single true parcel. That's the actual shape of what Phase 3 has to
check: not "which parcels did the AI miss entirely" but "where exactly
does this boundary really sit, and are these two stray fragments real."

Reproduce: `python3 predict_boundaries.py`
