from dataclasses import dataclass
from typing import List

@dataclass
class RiskResult:
    level: str
    score: int
    drivers: List[str]

def risk_assessment(abo_rh_compatible: bool, antibody_screen_positive: bool, crossmatch_incompatible: bool, emergency_release: bool) -> RiskResult:
    score = 0
    drivers = []

    if not abo_rh_compatible:
        score += 80
        drivers.append("ABO/Rh incompatible")

    if crossmatch_incompatible:
        score += 90
        drivers.append("Crossmatch incompatible")

    if antibody_screen_positive:
        score += 40
        drivers.append("Antibody screen positive")

    if emergency_release:
        score += 15
        drivers.append("Emergency release workflow")

    if score >= 90:
        level = "CRITICAL"
    elif score >= 60:
        level = "HIGH"
    elif score >= 25:
        level = "MODERATE"
    else:
        level = "LOW"

    return RiskResult(level=level, score=score, drivers=drivers)
