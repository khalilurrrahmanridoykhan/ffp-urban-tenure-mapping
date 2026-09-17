# Scripts

- `generate_synthetic_settlement.py` (Phase 1) — generates the synthetic
  parcel fabric, occupant roster, and overhead imagery in
  `data/synthetic/`. See that folder's README for what each output layer
  is and how it's built.
- `settlement_gen.py` (Phase 1) — the shared settlement-generation
  procedure both the Phase 1 script and Phase 2's training-data builder
  import from.
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
- `export_webapp_data.py` (Phase 7) — exports static JSON/GeoJSON/JPEG
  snapshots into `webapp/data/` for the dashboard. See `webapp/README.md`.

The full end-to-end pipeline (PyQGIS/`qgis_process`, covering every phase
through the atlas output) is scripted in Phase 9.
