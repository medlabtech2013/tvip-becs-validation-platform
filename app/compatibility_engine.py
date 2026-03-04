from dataclasses import dataclass
from typing import Dict, List, Tuple

COMPATIBILITY: Dict[str, List[str]] = {
    "O-": ["O-"],
    "O+": ["O-", "O+"],
    "A-": ["O-", "A-"],
    "A+": ["O-", "O+", "A-", "A+"],
    "B-": ["O-", "B-"],
    "B+": ["O-", "O+", "B-", "B+"],
    "AB-": ["O-", "A-", "B-", "AB-"],
    "AB+": ["O-", "O+", "A-", "A+", "B-", "B+", "AB-", "AB+"],
}

@dataclass
class ValidationOutcome:
    compatible: bool
    rationale: str
    rule_id: str

def check_rbc_compatibility(donor: str, recipient: str) -> ValidationOutcome:
    donor = donor.strip().upper()
    recipient = recipient.strip().upper()

    if donor not in COMPATIBILITY or recipient not in COMPATIBILITY:
        return ValidationOutcome(
            compatible=False,
            rationale="Unknown blood type input (outside supported ABO/Rh set).",
            rule_id="BB-RULE-000"
        )

    allowed_donors = COMPATIBILITY[recipient]
    ok = donor in allowed_donors

    return ValidationOutcome(
        compatible=ok,
        rationale=f"RBC compatibility evaluated using recipient-allowed donor set: {allowed_donors}.",
        rule_id="BB-RULE-ABO-RH-001"
    )

def apply_antibody_gate(antibody_screen_positive: bool, crossmatch_incompatible: bool) -> Tuple[bool, str, str]:
    if crossmatch_incompatible:
        return False, "Crossmatch incompatible: transfusion not permitted without clinical override.", "BB-RULE-XM-CRIT-001"
    if antibody_screen_positive:
        return False, "Antibody screen positive: requires ID workup and antigen-negative units.", "BB-RULE-ABID-REQ-001"
    return True, "No antibody/crossmatch blocks detected.", "BB-RULE-GATE-OK-001"
