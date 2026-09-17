# Outputs

Generated deliverables.

- `phase2_ai_draft_preview.png` (Phase 2) — the AI draft parcel outlines
  (magenta) overlaid on the true parcel outlines (green), for visually
  checking what the model got right/wrong. See `model/README.md` for the
  numeric evaluation.
- `phase3_field_validation_preview.png` (Phase 3) — validated parcels
  colored by what the field pass found: green = AI draft confirmed,
  orange = boundary corrected, thick magenta = disputed claim.
- `certificates/` (Phase 4) — a sample of STDM-style tenure
  certificates, one PDF per validated social tenure relationship (one
  per tenure type, plus a few extras). See `qgis/README.md`.
- `phase5_adjudication_queue_preview.png` (Phase 5) — parcels colored by
  QA finding: magenta = duplicate claim, orange = boundary conflict,
  yellow = low-confidence spot-check recommended, grey = no finding.
- `phase6_tenure_security_map.png` (Phase 6) — the tenure-security
  choropleth: green = secure, yellow = moderate, orange = at_risk,
  magenta = contested.

The settlement-level tenure-security atlas PDF is added from Phase 8
onward.
