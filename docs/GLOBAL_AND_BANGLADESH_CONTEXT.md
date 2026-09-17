# Global standards and Bangladesh context

This build isn't a generic exercise — it's positioned against real
standards, real precedent, and a real, currently unresolved case. This
document is the evidence for that positioning: what's a verified fact
with a source, versus what's this project's own design choice.

## 1. The global standard this schema implements: ISO 19152 (LADM)

Phase 4's STDM tables aren't a bespoke schema — the Social Tenure Domain
Model is formally a **specialisation of ISO 19152, the Land
Administration Domain Model**, the international standard for land
administration data ([ISO 19152-1:2024](https://www.iso.org/standard/81263.html),
[ISO 19152-2:2025](https://www.iso.org/standard/81264.html)). LADM
defines four core packages; every one of them has a direct counterpart
in `data/synthetic/stdm.gpkg`:

| LADM package | LADM class | This build |
|---|---|---|
| Party | `LA_Party` | `party` table |
| Administrative | `LA_RRR` (Right/Restriction/Responsibility) | `social_tenure_relationship` table — STDM's specialisation of `LA_RRR` for tenure types LADM's formal-registration model doesn't cover on its own (informal occupation, customary claims) |
| Spatial unit | `LA_SpatialUnit` | `spatial_unit` table (real building footprints) |
| Spatial source | `LA_Source` | the real drone orthomosaic + OSM building traces that `spatial_unit` is digitized from |

STDM was built specifically to extend LADM to informal and customary
tenure — exactly the case this repo demonstrates — while keeping
structural compatibility with the ISO standard, which is what makes a
disputed parcel (two competing `LA_RRR`-equivalent records against one
`LA_SpatialUnit`) a first-class, representable case here rather than a
workaround.

## 2. The global precedent this methodology follows: Rwanda's Land Tenure Regularization

The Fit-For-Purpose approach itself — general boundaries, participatory
orthophoto-based demarcation, incremental improvement over survey-grade
precision from day one — was formalized by FIG and the World Bank in
2014 and carried forward by GLTN's *[Fit-For-Purpose Land
Administration: Guiding Principles for Country
Implementation](https://gltn.net/publications/fit-purpose-land-administration-guiding-principles-country-implementation-english-and)*
(2016). Its flagship real-world validation is Rwanda's Land Tenure
Regularization program: a nationwide systematic land registration that
started after a 2009 pilot and was completed in four years, using
exactly this build's core technique — enumerators identifying parcel
boundaries directly on printed orthophotos in a participatory process,
instead of conventional field survey. It registered **10.4 million
parcels** and issued **8.8 million land lease certificates** at an
average unit cost of **about US$6 per parcel**
([GLTN impact assessment](https://landwise-production.s3.amazonaws.com/2022/03/GLTN_Rwanda-assessing-the-impact-of-the-land-tenure-regularization-program_nd-1.pdf);
[World Bank, Land Administration Reforms in
Rwanda](https://thedocs.worldbank.org/en/doc/439051611674305609-0090022021/original/LandAdministrationReformsinRwanda.pdf)).
This build's AI-drafted-then-field-corrected boundary (Phases 2–3) is
the same participatory-orthophoto principle with a machine-learning
first pass added — the boundary each enumerator "corrects" in Phase 3
here is standing in for the orthophoto print Rwanda's land officers
actually walked and marked up.

The scale this addresses is real too: GLTN's own framing is that roughly
70% of the world's population lacks access to formal land administration
services, concentrated among the poor and most vulnerable — informal
settlements like Korail are exactly that population.

## 3. Why Korail, Dhaka — the real, currently unresolved case this demonstrates against

Korail is Bangladesh's largest urban informal settlement — roughly
**80,000 residents** on land whose formal owner is the **Housing and
Building Research Institute (HBRI)**, with **no formal tenure allocation
to the households who actually live there** and a standing risk of
eviction ([ICCCAD community profile](http://website.icccad.net/wp-content/uploads/2024/02/IUI-Community-Profile-Dhaka_compressed.pdf);
[case study, Korail
slum](https://www.researchgate.net/publication/352785100_Analysis_of_Urban_Slum_Case_Study_of_Korail_Slum_Dhaka)).
Prior remote-sensing work on Dhaka's slums (satellite-based mapping from
2006–2010 onward, and more recent ML-based housing-condition prediction
from VHR imagery) has consistently found the same limitation: **slum
maps built from imagery alone show where structures are, not who has
what claim to them** — exactly the gap Phases 3–6 of this build exist to
close (real building footprints from Phase 2's imagery, participatory
tenure attribution from Phase 3 onward).

There is no public record of a Fit-For-Purpose land administration pilot
having been run in a Bangladeshi urban informal settlement — this build
is a demonstration of what that would produce, not a reproduction of an
existing program.

## 4. Bangladesh's own land administration digitization — what this build would plug into

Bangladesh's Ministry of Land is mid-transformation, and this build's
output schema (a georeferenced parcel with linked tenure/party records)
is the same kind of object these programs already manage:

- **e-Mutation** (land ownership transfer digitization) cut mutation
  processing from 60 days and 3–4 in-person visits down to 28 days and
  one visit, and won the **UN Public Service Award in 2020**
  ([UNPSA citation](https://publicadministration.un.org/unpsa/database/Winners/2020-winners/e-mutation)) —
  it has served 1.5 million+ beneficiaries.
- **e-Porcha** (eporcha.gov.bd) has digitized CS, SA, RS, and BS survey
  records — Bangladesh's actual historical cadastral chain — across all
  64 districts, the same "which survey record is authoritative"
  provenance problem this build's `spatial_source`-equivalent tracking
  (Phase 2's AI draft → Phase 3's field-corrected boundary → Phase 4's
  STDM record) is designed around.
- The **National Digital Land Zoning Project** covers 56,348 mouzas
  across all 493 upazilas using satellite imagery plus field
  verification, with a stated target of full national coverage by 2027
  under the Land Use Control and Agricultural Land Protection Ordinance,
  2026.
- A **"Smart Land Management" system** integrating these efforts is
  targeted for 2026.

None of these programs currently reach informal, undocumented urban
settlements the way this build's methodology is built to — that's the
specific gap this project is positioned against, not a claim of
involvement with any of the above.

## What this section is not

This is context and precedent, not an implementation history. Nothing in
this repo has been deployed by, submitted to, or reviewed by the
Bangladesh Ministry of Land, HBRI, GLTN, or any government or NGO named
above. All tenure/occupant/dispute data remains entirely fictional (see
`data/synthetic/README.md`); citing Korail's real, documented tenure
situation as motivation is not the same as claiming to have collected
real data about it.
