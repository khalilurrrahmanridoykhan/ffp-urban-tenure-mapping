# FFP Urban Tenure Mapping

A Fit-For-Purpose (FAO/GLTN) land administration build for urban/peri-urban
informal settlements: AI-assisted boundary drafting from imagery, participatory
field validation, an STDM person–parcel–tenure data model, adjudication QA,
tenure-security classification, and both an interactive dashboard and a
print-ready atlas as outputs.

**Real imagery, real buildings, fictional people.** The overhead imagery
and building footprints are real — a 2024 drone orthomosaic and OSM
building traces over Mburahati, a real informal settlement in Dar es
Salaam, Tanzania (properly attributed below and in
`scripts/real_data_source.py`). Every occupant, household, tenure claim,
and dispute from Phase 3 onward is entirely fictional. Real-world
coordinates are stripped from every published file — everything here
uses an arbitrary local coordinate grid, so nothing lets you
reverse-locate a specific "disputed" building to a real street address;
that said, using real imagery of a real, identifiable place means the
place itself remains visually identifiable to anyone who recognizes it,
which no coordinate-stripping can change. See `data/synthetic/README.md`
for exactly what's real vs. fictional in every file. This is a
methodology demonstration, not a deployable cadastre system, and not
affiliated with any real land administration authority.

**Attribution** (CC-BY 4.0 / ODbL, both require it): Imagery — "Mabibo
Mburahati 2024", OMDTZ / Iddy Chazua, via
[OpenAerialMap](https://map.openaerialmap.org). Building footprints —
© [OpenStreetMap](https://www.openstreetmap.org/copyright) contributors.

**Live dashboard:** https://khalilurrrahmanridoykhan.github.io/ffp-urban-tenure-mapping/

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
  applied to real drone imagery)
- `field_form/` — the ODK XLSForm an enumerator uses to validate the AI
  draft against ground reality
- `qgis/` — the QGIS/STDM project: parcel fabric, tenure attributes,
  topology QA, tenure-security classification, print atlas
- `webapp/` — the interactive dashboard (tenure-security map +
  adjudication queue)
- `scripts/` — the end-to-end scripted pipeline, including
  `real_data_source.py` (fetches the real imagery/buildings)
- `data/synthetic/` — real imagery/buildings + fictional occupant and
  tenure data, with provenance notes (folder name kept for path
  stability — see that folder's README for exactly what's real)

See `docs/ROADMAP.md` for the phase-by-phase build plan and current status.

## Requirements

Python 3.11+ with `geopandas`, `shapely`, `rasterio`, `numpy`, `pandas`,
`Pillow`, `scipy`, `openpyxl`, `reportlab`, `requests`, `pyproj`, and
(for `model/`) `torch`. No GPU required — training runs fine on CPU or
Apple Silicon (MPS); `model/README.md` has details. Regenerating the
foundation from scratch (`scripts/fetch_real_foundation.py`,
`model/train.py`) needs network access to OpenAerialMap's tile service
and the Overpass API; everything downstream of that runs offline against
the committed data files.

## License

Apache 2.0 — see `LICENSE`.
