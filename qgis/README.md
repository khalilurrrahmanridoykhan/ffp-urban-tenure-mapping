# QGIS / STDM

The parcel fabric, tenure attributes, topology QA, tenure-security
classification, and print atlas all live in `data/synthetic/` and
`outputs/` (see those folders' READMEs) rather than as files checked in
here — this folder documents the QGIS/STDM methodology and how to open
the data in QGIS directly; a bundled `.qgz` project is added once the
print atlas (Phase 8) needs one.

## STDM (Phase 4)

The core FFP data structure is **party ↔ spatial unit ↔ social tenure
relationship**, not just parcel geometry — one spatial unit can carry
more than one (possibly conflicting) STR, which is how a real disputed
claim gets represented instead of forced into a single "owner" field.

**This isn't a bespoke schema.** STDM is formally a specialisation of
**ISO 19152, the Land Administration Domain Model** — the international
standard for land administration data. Every LADM core package maps
directly onto a table here: `party` → `LA_Party`, `spatial_unit` →
`LA_SpatialUnit`, `social_tenure_relationship` → `LA_RRR`
(Right/Restriction/Responsibility, specialised by STDM to cover informal
and customary tenure types LADM's formal-registration model doesn't
reach on its own), and the real imagery + OSM traces `spatial_unit` is
digitized from → `LA_Source`. See
`docs/GLOBAL_AND_BANGLADESH_CONTEXT.md` for the full mapping and sources
(ISO 19152-1:2024, ISO 19152-2:2025).

The real [STDM QGIS plugin](https://stdm.gltn.net/) implements exactly
this schema against a PostgreSQL/PostGIS backend, configured through its
GUI Configuration Wizard. Two things rule out running the live plugin in
this repo: it doesn't yet support this QGIS version, and its
Configuration Wizard has no scriptable/GUI-free path — which would break
every other phase's "one command reproduces this" pattern. So
`scripts/build_stdm.py` implements STDM's own schema directly against a
single portable GeoPackage (`data/synthetic/stdm.gpkg`):

| STDM concept | Table | Source |
|---|---|---|
| Spatial unit | `spatial_unit` (spatial layer) | Phase 3's `validated_parcels` (real buildings) |
| Party | `party` | Phase 3's field submissions, deduplicated by `household_id` (fictional households) |
| Tenure type | `tenure_type` | the 5-code FFP lookup used since Phase 3 |
| Social tenure relationship | `social_tenure_relationship` | one row per claim: `party_id` × `spatial_unit_id` × `tenure_type_id`, `str_status` = `validated` or `disputed` |

The non-spatial tables are registered as proper GeoPackage `attributes`
tables (spec section 6), not just leftover SQL — they browse correctly
as related tables in QGIS or any other GeoPackage-aware tool. Open
`stdm.gpkg` in QGIS to see the actual party/spatial_unit/STR structure;
join `social_tenure_relationship` to `spatial_unit` on
`spatial_unit_id` to see tenure overlaid on the parcel fabric, or to
`party` on `party_id` to see what any one household claims.

482 real buildings, 496 fictional parties, 496 STRs, 14 spatial units
carrying two STRs each (both `disputed`) — real double claims from Phase
3's fictional-household simulation, not label noise added at this phase.
Reproduce: `python3 scripts/build_stdm.py`.

### Tenure documentation (certificates)

`scripts/generate_certificates.py` generates one PDF per validated STR —
STDM's own Document Generator module produces the same kind of output
from this same schema. Only issued for `validated` STRs (one per tenure
type, plus a few extras — a representative sample, not all 482);
disputed STRs get no certificate, which is deliberate: they're exactly
the material Phase 5's adjudication queue works from. Output:
`outputs/certificates/<str_id>.pdf`.

## Topology QA & adjudication queue (Phase 5)

`scripts/topology_qa.py` runs six independent checks over the STDM data
and produces `data/synthetic/adjudication_queue.csv` — the list a land
officer would need to manually resolve, not something the script
silently fixes:

| check | what it catches | result |
|---|---|---|
| `invalid_geometry` | self-intersecting spatial units | 0 |
| `overlap` | spatial units overlapping by >0.05 m² | 22 |
| `boundary_conflict` | spatial units <0.5m apart without overlapping (inside typical handheld-GPS error) | 219 |
| `duplicate_claim` | more than one STR on the same spatial unit | 14 |
| `data_integrity` | an STR referencing a party or spatial unit that doesn't exist | 0 |
| `low_confidence_confirmation` | a parcel the field pass confirmed as-is, but the AI draft's own confidence was below 0.9 | 0 |

This QA pass looks very different against real building footprints than
it did against the fully-procedural version of this project: Korail's
real buildings are often genuinely wall-to-wall or a hand's width apart,
so 22 real overlaps and a striking 219 real near-misses show up once
GPS-walk jitter is applied — this is honest topology noise from
extremely dense real geometry, not a bug, and a direct, quantified
reflection of just how tightly packed this settlement is.
`low_confidence_confirmation` comes back empty here because none of the
real AI draft blobs were precise enough for the field pass to mark
`confirm_ai_draft` at all (see `model/README.md`) — there's nothing to
spot-check. The 14 duplicate claims are the fictional-household double
claims from Phase 3, not fabricated for this phase. Missing
photo-evidence coverage (2/468 validated STRs) is reported as a metric
in `qa_report.md`, not as hundreds of individual queue rows — that's not
an actionable per-parcel finding.

Reproduce: `python3 scripts/topology_qa.py`.

## Tenure security classification (Phase 6)

`scripts/classify_tenure_security.py` produces
`data/synthetic/tenure_security.gpkg` — the layer both the Phase 7
dashboard and Phase 8 atlas present. It deliberately keeps two risk
dimensions apart rather than folding them into one number silently:

- **tenure type** — a 1-5 base score from the STR's tenure type
  (`owned_documented`=5 down to `informal_occupation`=1)
- **spatial fitness** — whether Phase 5 flagged the parcel's boundary as
  a near-miss conflict; if so, the score drops by 1 (floor 1), because a
  physically ambiguous extent undermines security regardless of the
  tenure claim's strength

A disputed STR (Phase 5's `duplicate_claim`) overrides both and forces
`contested` — a disputed claim isn't "weak tenure," it's a different
kind of insecurity: the right itself is unresolved. Phase 5's
`low_confidence_confirmation` findings are deliberately **not** used
here — that's a model/spatial-QA signal about the AI draft, not a
tenure-security signal about the household's claim.

| class | score | meaning | count |
|---|---|---|---|
| secure | 4-5 | owned, no open boundary conflict | 91 |
| moderate | 2-3 | customary/owned-undocumented, or downgraded by a boundary conflict | 156 |
| at_risk | 1 | informal occupation or rented, uncontested | 221 |
| contested | — | disputed STR, overrides tenure type entirely | 14 |

Reproduce: `python3 scripts/classify_tenure_security.py`.
