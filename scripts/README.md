# Scripts

- `real_data_source.py` (Phase 1) — fetches the real imagery (OpenAerialMap
  tiles) and real building footprints (OSM/Overpass) that `data/synthetic/`
  is now built from, re-origining coordinates to an arbitrary local grid.
  See `data/synthetic/README.md` for the full attribution and rationale.
- `fetch_real_foundation.py` (Phase 1) — writes the canonical AOI's real
  data into `data/synthetic/settlement.gpkg` + `imagery.tif`, and generates
  the fictional `occupants.csv` roster on top of it.
- `settlement_gen.py` — occupant-roster generation (`build_occupants`,
  reused by `fetch_real_foundation.py`) plus the original fully-procedural
  settlement generator, kept as the alternative fully-synthetic mode this
  project started from (see `generate_synthetic_settlement.py` below).
- `generate_synthetic_settlement.py` — the original **fully-procedural**
  Phase 1 (synthetic imagery *and* synthetic parcels, no real data at
  all). Not what `data/synthetic/` currently holds — kept as a documented
  alternative mode; run it and then rerun Phases 2-7 to switch the whole
  pipeline back to fully-synthetic.
- `build_xlsform.py` (Phase 3) — builds `field_form/ffp_boundary_validation.xlsx`.
- `simulate_field_validation.py` (Phase 3) — simulates the field pass
  against the AI draft, producing `data/synthetic/field_submissions.csv`
  and `data/synthetic/validated_parcels.gpkg`.
- `build_stdm.py` (Phase 4) — builds the STDM party/spatial_unit/tenure_type/
  social_tenure_relationship schema into `data/synthetic/stdm.gpkg`. See
  `qgis/README.md` for the methodology.
- `generate_certificates.py` (Phase 4) — generates sample tenure
  certificates (PDF) from `stdm.gpkg` into `outputs/certificates/`.
- `topology_qa.py` (Phase 5) — runs topology and business-logic QA over
  `stdm.gpkg`, producing `data/synthetic/adjudication_queue.csv` and
  `qa_report.md`. See `qgis/README.md` for what each check does.
- `classify_tenure_security.py` (Phase 6) — classifies every parcel's
  tenure security into `data/synthetic/tenure_security.gpkg`. See
  `qgis/README.md` for the scoring method.
- `generate_previews.py` — regenerates the Phase 3/5/6 preview PNGs in
  `outputs/` (Phase 2's own preview is written directly by
  `model/predict_boundaries.py`).
- `export_webapp_data.py` (Phase 7) — exports static JSON/GeoJSON/JPEG
  snapshots into `webapp/data/` for the dashboard. See `webapp/README.md`.

The full end-to-end pipeline (PyQGIS/`qgis_process`, covering every phase
through the atlas output) is scripted in Phase 9.
