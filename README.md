# FFP Urban Tenure Mapping

A Fit-For-Purpose (FAO/GLTN) land administration build for urban/peri-urban
informal settlements: AI-assisted boundary drafting from imagery, participatory
field validation, an STDM person–parcel–tenure data model, adjudication QA,
tenure-security classification, and both an interactive dashboard and a
print-ready atlas as outputs.

**Synthetic data only.** The settlement, parcels, occupants, and imagery in
this repo are all generated, not real — no real place, no real person's
tenure record. See `data/synthetic/README.md` for how each layer is
generated. This is a methodology demonstration, not a deployable cadastre
system.

## Why Fit-For-Purpose

A full cadastral survey is slow and expensive, which is exactly why dense,
largely undocumented informal settlements rarely get one — leaving
occupants without any record of tenure and exposed to eviction with no
paper trail. FFP land administration (FAO/GLTN) trades survey-grade
precision for speed and inclusiveness: general boundaries instead of exact
ones, low-cost tools, participatory adjudication, and a data model built to
be upgraded later rather than perfect from day one.

## What's here

- `model/` — the AI-assisted boundary-extraction step (segmentation model
  applied to synthetic imagery)
- `field_form/` — the ODK XLSForm an enumerator uses to validate the AI
  draft against ground reality
- `qgis/` — the QGIS/STDM project: parcel fabric, tenure attributes,
  topology QA, tenure-security classification, print atlas
- `webapp/` — the interactive dashboard (tenure-security map +
  adjudication queue)
- `scripts/` — the end-to-end scripted pipeline
- `data/synthetic/` — generated settlement, imagery, and attribute data,
  with provenance notes

See `docs/ROADMAP.md` for the phase-by-phase build plan and current status.

## Requirements

Python 3.11+ with `geopandas`, `shapely`, `rasterio`, `numpy`, `pandas`,
`Pillow`, `scipy`, `openpyxl`, `reportlab`, and (for `model/`) `torch`.
No GPU required — training runs fine on CPU or Apple Silicon (MPS);
`model/README.md` has details.

## License

Apache 2.0 — see `LICENSE`.
