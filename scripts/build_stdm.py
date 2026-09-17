"""Phase 4: builds the STDM (Social Tenure Domain Model) data structure
from Phase 3's validated parcels and field submissions -- the actual FFP
deliverable is this relational model, not just a parcel map: **person
(party) <-> parcel (spatial unit) <-> social tenure relationship**, where
one spatial unit can carry more than one (possibly conflicting) STR, which
is exactly how a real disputed claim gets represented rather than forced
into a single "owner" field.

The real STDM QGIS plugin normally runs this schema against a PostgreSQL/
PostGIS backend, configured through its GUI Configuration Wizard -- there
is no scriptable, GUI-free way to drive that plugin, and it does not yet
support this QGIS version. So this script implements the same schema
STDM itself uses (party / spatial_unit / tenure_type /
social_tenure_relationship, spec-compliant GeoPackage "attributes" tables
for the non-spatial ones) directly, as a single portable file any GIS or
database tool can open -- the methodology is faithful to STDM even though
the storage engine isn't the live plugin.

Run: python3 scripts/build_stdm.py
Output: data/synthetic/stdm.gpkg (layers: spatial_unit [spatial],
party, tenure_type, social_tenure_relationship [non-spatial])
"""

import os
import sqlite3

import geopandas as gpd
import numpy as np
import pandas as pd

REPO_ROOT = os.path.join(os.path.dirname(__file__), "..")
SYN_DIR = os.path.join(REPO_ROOT, "data", "synthetic")
GPKG_PATH = os.path.join(SYN_DIR, "stdm.gpkg")

TENURE_TYPES = [
    ("owned_documented", "Owned, has documentation"),
    ("owned_undocumented", "Owned, no documentation"),
    ("rented", "Rented"),
    ("informal_occupation", "Informal occupation (no ownership claim)"),
    ("customary", "Customary / community-recognized claim"),
]


def register_attribute_table(conn, table_name, identifier):
    """Marks a plain SQLite table as a GeoPackage non-spatial 'attributes'
    table (GeoPackage spec sec. 6) so QGIS and other GeoPackage-aware
    tools list it as a proper related table, not just leftover SQL."""
    conn.execute(
        "INSERT OR REPLACE INTO gpkg_contents (table_name, data_type, identifier) VALUES (?, 'attributes', ?)",
        (table_name, identifier),
    )


def build_party_table(submissions):
    claimants = submissions[submissions.household_id.notna()].copy()
    parties = claimants.drop_duplicates(subset="household_id")[["household_id", "claimant_name", "household_size"]]
    rng = np.random.default_rng(11)
    parties = parties.rename(columns={"household_id": "party_id", "claimant_name": "full_name"})
    parties["party_type"] = "natural_person"
    parties["national_id"] = [f"SYN-NID-{rng.integers(100000, 999999)}" for _ in range(len(parties))]
    parties["phone"] = [f"01{rng.integers(300000000, 999999999)}" for _ in range(len(parties))]
    return parties[["party_id", "full_name", "party_type", "household_size", "national_id", "phone"]]


def build_str_table(submissions):
    claimed = submissions[submissions.household_id.notna()].copy()
    claimed = claimed.reset_index(drop=True)
    claimed["str_id"] = [f"STR-{i + 1:04d}" for i in range(len(claimed))]
    claimed["str_status"] = np.where(claimed.dispute_flag == "yes", "disputed", "validated")
    claimed["validity_start"] = claimed["today"]
    return claimed[["str_id", "household_id", "parcel_id", "tenure_type", "str_status",
                     "validity_start", "evidence_photo", "notes", "dispute_notes"]].rename(
        columns={"household_id": "party_id", "parcel_id": "spatial_unit_id", "tenure_type": "tenure_type_id",
                 "evidence_photo": "documented_by"})


def main():
    validated = gpd.read_file(os.path.join(SYN_DIR, "validated_parcels.gpkg"), layer="validated_parcels")
    submissions = pd.read_csv(os.path.join(SYN_DIR, "field_submissions.csv"))

    spatial_unit = validated[["parcel_id", "boundary_action", "geometry"]].rename(columns={"parcel_id": "spatial_unit_id"})
    spatial_unit["area_m2"] = spatial_unit.geometry.area.round(2)
    spatial_unit["spatial_unit_type"] = "residential_parcel"

    party = build_party_table(submissions)
    str_table = build_str_table(submissions)
    tenure_type = pd.DataFrame(TENURE_TYPES, columns=["tenure_type_id", "name"])

    if os.path.exists(GPKG_PATH):
        os.remove(GPKG_PATH)
    spatial_unit.to_file(GPKG_PATH, layer="spatial_unit", driver="GPKG")

    conn = sqlite3.connect(GPKG_PATH)
    party.to_sql("party", conn, index=False, if_exists="replace")
    tenure_type.to_sql("tenure_type", conn, index=False, if_exists="replace")
    str_table.to_sql("social_tenure_relationship", conn, index=False, if_exists="replace")
    register_attribute_table(conn, "party", "STDM party (person/household)")
    register_attribute_table(conn, "tenure_type", "STDM tenure type lookup")
    register_attribute_table(conn, "social_tenure_relationship", "STDM social tenure relationship (party <-> spatial unit)")
    conn.commit()
    conn.close()

    n_disputed_str = (str_table.str_status == "disputed").sum()
    n_parcels_with_2_str = str_table.spatial_unit_id.value_counts().gt(1).sum()
    print(f"spatial_unit: {len(spatial_unit)}, party: {len(party)}, "
          f"social_tenure_relationship: {len(str_table)} ({n_disputed_str} disputed, "
          f"{n_parcels_with_2_str} spatial units carrying >1 STR)")
    print(f"Wrote {GPKG_PATH}")


if __name__ == "__main__":
    main()
