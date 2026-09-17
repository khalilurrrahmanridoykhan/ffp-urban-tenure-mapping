"""Phase 3: builds the XLSForm an enumerator would actually load into
ODK Collect / QField to validate the Phase 2 AI draft against ground
reality. Standard ODK XLSForm structure (survey/choices/settings sheets)
-- importable into KoboToolbox, ODK Central, or QField as-is.

Run: python3 scripts/build_xlsform.py
Output: field_form/ffp_boundary_validation.xlsx
"""

import os

import pandas as pd

OUT_PATH = os.path.join(os.path.dirname(__file__), "..", "field_form", "ffp_boundary_validation.xlsx")

survey = pd.DataFrame([
    {"type": "start", "name": "start"},
    {"type": "end", "name": "end"},
    {"type": "today", "name": "today"},
    {"type": "select_one enumerators", "name": "enumerator_id", "label": "Enumerator ID", "required": "yes"},
    {"type": "text", "name": "ai_draft_id", "label": "AI draft parcel ID (from the printed/tablet map)", "required": "yes"},
    {"type": "select_one boundary_actions", "name": "boundary_action", "label": "What did you find walking this parcel?", "required": "yes"},
    {"type": "geoshape", "name": "boundary_walk", "label": "Walk the actual parcel boundary",
     "relevant": "${boundary_action}='correct_boundary' or ${boundary_action}='new_parcel_not_in_ai_draft'"},
    {"type": "text", "name": "rejection_reason", "label": "Why is this not a real parcel?",
     "relevant": "${boundary_action}='reject_not_a_parcel'"},
    {"type": "text", "name": "claimant_name", "label": "Claimant / occupant name",
     "relevant": "${boundary_action}!='reject_not_a_parcel'", "required": "yes"},
    {"type": "integer", "name": "household_size", "label": "Household size",
     "relevant": "${boundary_action}!='reject_not_a_parcel'"},
    {"type": "select_one tenure_types", "name": "tenure_type", "label": "Claimed tenure type",
     "relevant": "${boundary_action}!='reject_not_a_parcel'", "required": "yes"},
    {"type": "select_one yes_no", "name": "dispute_flag", "label": "Is this parcel or claim disputed by another household?",
     "relevant": "${boundary_action}!='reject_not_a_parcel'", "required": "yes"},
    {"type": "text", "name": "dispute_notes", "label": "Describe the dispute", "relevant": "${dispute_flag}='yes'"},
    {"type": "photo", "name": "evidence_photo", "label": "Photo evidence",
     "relevant": "${boundary_action}!='reject_not_a_parcel'"},
    {"type": "decimal", "name": "gps_accuracy_m", "label": "Reported GPS accuracy (m)"},
    {"type": "text", "name": "notes", "label": "Additional notes"},
])

choices = pd.DataFrame([
    {"list_name": "enumerators", "name": "ENUM-01", "label": "Enumerator 1"},
    {"list_name": "enumerators", "name": "ENUM-02", "label": "Enumerator 2"},
    {"list_name": "enumerators", "name": "ENUM-03", "label": "Enumerator 3"},
    {"list_name": "enumerators", "name": "ENUM-04", "label": "Enumerator 4"},

    {"list_name": "boundary_actions", "name": "confirm_ai_draft", "label": "AI draft boundary matches the ground"},
    {"list_name": "boundary_actions", "name": "correct_boundary", "label": "AI draft is close but needs correcting"},
    {"list_name": "boundary_actions", "name": "new_parcel_not_in_ai_draft", "label": "Real parcel the AI draft missed entirely"},
    {"list_name": "boundary_actions", "name": "reject_not_a_parcel", "label": "AI draft does not correspond to a real parcel"},

    {"list_name": "tenure_types", "name": "owned_documented", "label": "Owned, has documentation"},
    {"list_name": "tenure_types", "name": "owned_undocumented", "label": "Owned, no documentation"},
    {"list_name": "tenure_types", "name": "rented", "label": "Rented"},
    {"list_name": "tenure_types", "name": "informal_occupation", "label": "Informal occupation (no ownership claim)"},
    {"list_name": "tenure_types", "name": "customary", "label": "Customary / community-recognized claim"},

    {"list_name": "yes_no", "name": "yes", "label": "Yes"},
    {"list_name": "yes_no", "name": "no", "label": "No"},
])

settings = pd.DataFrame([{
    "form_title": "FFP Boundary Validation -- Synthetic Settlement",
    "form_id": "ffp_boundary_validation",
    "version": "1",
    "default_language": "English (en)",
}])


def main():
    os.makedirs(os.path.dirname(OUT_PATH), exist_ok=True)
    with pd.ExcelWriter(OUT_PATH, engine="openpyxl") as writer:
        survey.to_excel(writer, sheet_name="survey", index=False)
        choices.to_excel(writer, sheet_name="choices", index=False)
        settings.to_excel(writer, sheet_name="settings", index=False)
    print(f"Wrote {OUT_PATH}")


if __name__ == "__main__":
    main()
