# Data

Folder name kept as `data/synthetic/` for path stability across every
script in this repo, even though as of Phase 2's real-data rework it no
longer holds only synthetic content. Read this file before assuming
anything about a given layer — real and fictional data sit side by side
here, and which is which matters.

**Real**: `settlement.gpkg`'s `parcels` layer and `imagery.tif` — a real
November 2023 drone orthomosaic and real OSM building footprints over
**Korail, Dhaka's largest informal settlement** (see
`scripts/real_data_source.py` for the exact source, license, and
attribution, and `docs/GLOBAL_AND_BANGLADESH_CONTEXT.md` for why this
place). Everything downstream that's
*derived* from real geometry (`ai_draft_parcels.gpkg`,
`validated_parcels.gpkg`'s boundaries, `stdm.gpkg`'s `spatial_unit`,
`tenure_security.gpkg`) is real too, in the sense that the shapes are
real buildings.

**Fictional**: every occupant, household, name, tenure claim, dispute,
and evidence photo caption from Phase 3 onward. No real person's tenure
record appears anywhere in this repo. See the "Why fictional people"
section below for why this line is drawn where it is.

Regenerate everything from scratch:

```
python3 scripts/fetch_real_foundation.py   # Phase 1: real imagery + buildings
python3 model/train.py --epochs 20         # Phase 2: train on 12 other real AOIs
python3 model/predict_boundaries.py        # Phase 2: AI draft + evaluation
python3 scripts/simulate_field_validation.py  # Phase 3
python3 scripts/build_stdm.py              # Phase 4
python3 scripts/generate_certificates.py   # Phase 4
python3 scripts/topology_qa.py             # Phase 5
python3 scripts/classify_tenure_security.py  # Phase 6
python3 scripts/generate_previews.py       # Phase 3/5/6 preview images
python3 scripts/export_webapp_data.py      # Phase 7
```

## Why fictional people, real place

There's no public, consented dataset of real households' tenure claims
and disputes for any informal settlement — that kind of data only exists
through an actual field survey with real consent, usually under an
NGO/government ethical framework. Publishing real people's occupancy
status, dispute history, or informal/undocumented tenure in a public
GitHub repo would be a real privacy and safety risk to them (eviction
risk, exposing a dispute, revealing undocumented status). The imagery
and building footprints, by contrast, are already public open data
(CC-BY 4.0 / ODbL) with no personal information in them, so using them
as the real geometric/visual foundation carries none of that risk.

## Coordinates are stripped

Real Web Mercator coordinates are translated to an arbitrary local
origin (0,0 at each AOI's own bounding-box corner) before anything is
written — `scripts/real_data_source.py`'s `build_real_settlement`. No
file in this repo carries real lon/lat, so nothing here lets you
reverse-locate a specific "disputed" building to a real street address
from the data alone. The residual limit: this is imagery of a real,
visually identifiable place, so someone who recognizes it (or runs
reverse image search) can still identify it from the pixels themselves —
no amount of coordinate-stripping changes that, and it's why the
fictional data is kept to attributes (names, claims, disputes) rather
than being presented as if it described real people.

Every layer still uses the `LOCAL_CRS` tag (from `scripts/settlement_gen.py`,
originally defined for the fully-procedural version of this project) as
a nominal "arbitrary local metres" label — the real data's actual
coordinates aren't a transverse-Mercator-at-null-island reprojection,
just Web Mercator metres re-origined per AOI, but the tag communicates
the same thing to anyone opening the file: don't treat these numbers as
real-world coordinates.

## Layers

- `settlement.gpkg` — `boundary` (each AOI's 150m × 150m extent) and
  `parcels` (real building footprints, **482** in the canonical AOI —
  Korail is one of the densest urban informal settlements anywhere —
  built by `scripts/fetch_real_foundation.py` from real OSM building
  traces, clipped to the AOI and re-origined to local metres).
- `occupants.csv` — one row per fictional household (`household_id`,
  `parcel_id`, `occupant_name`, `household_size`), 1–2 households per
  real building depending on its size. Names are drawn from a small
  fixed pool of common Bengali first/last names purely for readability —
  they do not refer to any real Korail resident; `is_synthetic` is
  `True` on every row. (Built by `scripts/settlement_gen.py`'s
  `build_occupants`, reused unchanged from the original fully-procedural
  version — it only needs a parcel's ID and area, so it works the same
  whether the parcel is real or procedural.)
- `imagery.tif` — the real drone orthomosaic, cropped to the AOI and
  re-origined to local metres (0.149m/px). Source: Korail/Banani drone
  orthomosaic (Nov 2023), Geo-Planning for Advanced Development (GPAD) /
  Rejaur Rahman, via OpenAerialMap, CC-BY 4.0.
- `ai_draft_parcels.gpkg` (layer `ai_draft_parcels`, Phase 2) — the
  model's candidate parcel boundaries, vectorized from its predicted
  mask over the real imagery (`draft_id`, `area_m2`, `confidence`).
  Deliberately not corrected — see `model/README.md` for how it compares
  to the real `parcels` layer above (spoiler: badly — Korail's
  wall-to-wall density makes this a genuinely hard segmentation problem,
  consistent with published remote-sensing literature on very dense
  informal settlements), and Phase 3 for the participatory correction
  pass.
- `field_submissions.csv` (Phase 3) — one row per simulated ODK
  submission (columns match `field_form/ffp_boundary_validation.xlsx`
  exactly, plus `_id`/`_uuid` meta fields as a real ODK/Kobo export would
  have). Two rows per parcel where a second fictional household disputes
  the claim. Built by `scripts/simulate_field_validation.py`, which
  plays the enumerator using the real building layer and fictional
  occupant roster as ground truth — every correction, rejection, and
  dispute in this file traces back to a real geometric discrepancy (the
  AI draft vs. the real building) or a fictional second claimant, not an
  arbitrary random label.
- `validated_parcels.gpkg` (layer `validated_parcels`, Phase 3) — the
  corrected parcel fabric after the field pass: **482** real buildings,
  each with `boundary_action`, `tenure_type` (fictional, or `disputed`
  where fictional claimants disagree), `dispute_flag`, and
  `n_claimants`. This is what Phase 4's STDM model is built from.
- `field_photos/` (Phase 3) — a sample of evidence photos (every
  disputed and rejected case, plus a small random sample of routine
  ones), each a real crop of the real `imagery.tif` at that parcel's
  location — not a full photo per parcel, to keep the repo lean, but a
  genuine demonstration of the capability.
- `stdm.gpkg` (Phase 4) — the Social Tenure Domain Model: `spatial_unit`
  (spatial layer, the 482 real validated buildings), `party` (fictional
  households, keyed by `household_id`, one row per unique claimant),
  `tenure_type` (the 5-code lookup), and `social_tenure_relationship`
  (rows linking party ↔ spatial unit ↔ tenure type — 14 spatial units
  carry two STRs, one per disputing fictional claimant). The non-spatial
  tables are registered as proper GeoPackage `attributes` tables (spec
  section 6), not just SQL leftovers, so they browse correctly in
  QGIS/any GeoPackage-aware tool. See `qgis/README.md` for why this is a
  scripted schema replication of STDM (and its formal alignment to ISO
  19152/LADM) rather than the live STDM QGIS plugin, and how it maps to
  Phase 3's data.
- `adjudication_queue.csv` + `qa_report.md` (Phase 5) — the output of
  `scripts/topology_qa.py` over the real building fabric plus fictional
  tenure data: **22 genuine geometric overlaps and 219 near-miss
  boundaries** (Korail's real buildings are often genuinely wall-to-wall,
  so GPS-walk jitter produces far more real topology findings here than
  in a less dense settlement), plus 14 duplicate (fictional) claims and
  a report showing every check that ran, including the ones that came
  back clean. See `qgis/README.md` for what each check does and why.
- `tenure_security.gpkg` (layer `tenure_security`, Phase 6) — every real
  parcel classified `secure` / `moderate` / `at_risk` / `contested`
  based on its fictional tenure data, the layer both the Phase 7
  dashboard and Phase 8 atlas present. Kept separate from `stdm.gpkg`
  deliberately — this is a derived policy-analysis layer, not part of
  the base STDM registry. See `qgis/README.md` for the scoring method.
