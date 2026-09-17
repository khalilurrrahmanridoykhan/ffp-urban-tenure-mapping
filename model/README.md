# Geo AI model — AI-assisted boundary extraction

A small U-Net (`unet.py`) that segments building/parcel footprints from
**real drone imagery over Korail, Dhaka's largest informal settlement**,
giving a rough first-pass boundary draft for Phase 3's participatory
validation to correct — the same "AI drafts, a human adjudicates"
division of labor real FFP AI-assisted-extraction pilots use.

## Data

`dataset.py` builds 12 training AOIs and 3 validation AOIs from real
imagery + real OSM building footprints (see
`scripts/real_data_source.py` for the full source and attribution),
tiled into 256×256 patches. **The canonical AOI Phase 1 committed is
never used for training or validation** — Phase 2's evaluation below is
on real imagery the model has genuinely never seen. Any 256×256 tile
with a tile-fetch gap (the imagery tile service occasionally throttles
rapid sequential requests) is excluded from the training/val index
entirely, not zero-filled — a gap paired with real building labels would
teach the model that black patches are buildings.

No synthetic realism pass is needed here (an earlier fully-synthetic
version of this project needed one — flat-colored procedural imagery
made segmentation trivially easy). Real imagery already has real blur,
shadow, occlusion, and roof-material ambiguity between adjacent
structures — and Korail in particular is genuinely one of the hardest
cases this kind of model can face.

## Model & training

`unet.py` — a 4-level U-Net, 16→256 channels, ~2M parameters. `train.py`
trains it with a BCE + Dice loss on MPS (Apple Silicon GPU).

**This was a harder training run than expected, and that's worth being
honest about.** At the default 20 epochs, train loss barely moved
(1.25→1.13) and val IoU stayed noisy around 0.1–0.28 — a genuinely
different pattern from an earlier, less-dense real settlement this
project trained on, where the same setup converged to near-perfect
within 5 epochs. A gradient/data-integrity check (manual per-batch loss
and grad-norm inspection) confirmed the model *was* learning, just very
slowly: Korail's buildings are frequently wall-to-wall, so the
foreground/background boundary signal a CNN needs is far weaker than in
a settlement with visible gaps between structures. Extending to **60
epochs** let the trend continue (loss 1.25→1.13) without fully
converging — the honest finding is that basic semantic segmentation
plateaus well short of "solved" on a settlement this dense, which is
consistent with published remote-sensing literature noting that very
high-density informal settlements are a known hard case for
imagery-only building extraction.

Reproduce: `python3 train.py --epochs 60 --lr 1.5e-3`

## Inference & evaluation

`predict_boundaries.py` runs sliding-window inference over Phase 1's
committed `data/synthetic/imagery.tif` (the real canonical AOI),
thresholds and connects the prediction into blobs, vectorizes each into
a polygon (with a per-blob mean-confidence score), and writes the result
to `data/synthetic/ai_draft_parcels.gpkg` (layer `ai_draft_parcels`) —
the draft Phase 3 works from.

**The binarization threshold is calibrated for instance separation, not
raw pixel accuracy — and that tradeoff is deliberate.** A validation-set
sweep found 0.5 is pixel-IoU-optimal (0.25 IoU) but collapses the whole
AOI into a single connected blob once thresholded and connected (Korail
really is that dense). Raising the threshold to **0.65** costs pixel
IoU (0.19 on val) but breaks the image into 636 separate raw components
— the difference between an unusable "yes, this is all building" output
and something Phase 3 can actually work through parcel by parcel. This
is the real tradeoff behind `BINARIZATION_THRESHOLD = 0.65` in
`predict_boundaries.py`, not an arbitrary constant.

Result on the canonical AOI (482 real buildings):

| metric | value |
|---|---|
| pixel IoU | 0.335 |
| true parcels (real buildings) | 482 |
| draft blobs | 97 |
| matched / missed true parcels | 258 / 224 |
| draft blobs covering multiple true parcels | 25 |
| true parcels absorbed into a merged blob | 238 |
| true parcels split across multiple draft blobs | 31 |

Reading this honestly: fewer than half of Korail's real buildings get a
individually-identifiable draft footprint. This is a substantially
harder result than this project's earlier, less-dense real settlement,
and that's the point of using Korail rather than an easier real place —
it's an honest demonstration of where AI-assisted boundary extraction
actually struggles, not a cherry-picked success case. Phase 3's
participatory validation is doing real, load-bearing work here: most of
Korail's 482 buildings reach a validated boundary only because a
(simulated) enumerator corrected or added them, not because the AI draft
was already close.

Reproduce: `python3 predict_boundaries.py`
