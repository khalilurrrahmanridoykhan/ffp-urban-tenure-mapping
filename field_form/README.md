# Field form

`ffp_boundary_validation.xlsx` — a standard ODK XLSForm (survey/choices/
settings sheets) for the enumerator pass that validates Phase 2's AI
draft against ground reality. Built by `scripts/build_xlsform.py`;
compiles cleanly through `pyxform` with no warnings, so it's a genuinely
importable form, not just a mockup — load it as-is into ODK Collect, ODK
Central, KoboToolbox, or QField.

## What it captures

For each AI draft parcel an enumerator visits:

- which action applies — confirms the draft, corrects it, flags a real
  parcel the draft missed entirely, or rejects a draft polygon that
  doesn't correspond to a real parcel (`boundary_action`)
- a re-walked boundary (`boundary_walk`, a `geoshape` question) when
  correcting or adding a parcel
- the claimant's name, household size, and tenure type
  (`owned_documented` / `owned_undocumented` / `rented` /
  `informal_occupation` / `customary`)
- whether the parcel or claim is disputed by another household, and why
- photo evidence and a free-text notes field

`scripts/simulate_field_validation.py` is the stand-in for actually
running this form in the field — it plays the enumerator, using Phase
1's true parcel/occupant data as "what's really on the ground" so every
correction, rejection, and dispute it produces traces back to a genuine
discrepancy, not an arbitrary random label. See
`data/synthetic/README.md` for its outputs.
