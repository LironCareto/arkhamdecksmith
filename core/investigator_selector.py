from __future__ import annotations

from dataclasses import dataclass

from core.models import BuildRequest


@dataclass(frozen=True)
class InvestigatorCandidate:
    investigator_name: str
    class_name: str
    suggested_role: str
    reasoning: str


CLASS_INVESTIGATORS = {
    "guardian": [
        InvestigatorCandidate(
            investigator_name="Mark Harrigan",
            class_name="guardian",
            suggested_role="fighter",
            reasoning="Strong combat specialist for campaigns.",
        ),
        InvestigatorCandidate(
            investigator_name="Zoey Samaras",
            class_name="guardian",
            suggested_role="fighter",
            reasoning="Reliable enemy engagement and combat.",
        ),
    ],
    "seeker": [
        InvestigatorCandidate(
            investigator_name="Daisy Walker",
            class_name="seeker",
            suggested_role="cluever",
            reasoning="Excellent investigation and tome synergy.",
        ),
        InvestigatorCandidate(
            investigator_name="Amanda Sharpe",
            class_name="seeker",
            suggested_role="flex",
            reasoning="Extremely efficient skill-based investigator.",
        ),
    ],
    "rogue": [
        InvestigatorCandidate(
            investigator_name="Jenny Barnes",
            class_name="rogue",
            suggested_role="flex",
            reasoning="Strong economy and adaptable gameplay.",
        ),
        InvestigatorCandidate(
            investigator_name="Finn Edwards",
            class_name="rogue",
            suggested_role="evader",
            reasoning="Excellent mobility and enemy control.",
        ),
    ],
    "mystic": [
        InvestigatorCandidate(
            investigator_name="Gloria Goldberg",
            class_name="mystic",
            suggested_role="flex",
            reasoning="Excellent encounter control and clue support.",
        ),
        InvestigatorCandidate(
            investigator_name="Agnes Baker",
            class_name="mystic",
            suggested_role="fighter",
            reasoning="Reliable damage-oriented mystic.",
        ),
    ],
    "survivor": [
        InvestigatorCandidate(
            investigator_name="Ashcan Pete",
            class_name="survivor",
            suggested_role="flex",
            reasoning="Strong all-round investigator with Duke.",
        ),
        InvestigatorCandidate(
            investigator_name="Silas Marsh",
            class_name="survivor",
            suggested_role="fighter",
            reasoning="Excellent combat and skill recursion.",
        ),
    ],
}


def select_investigators(
    request: BuildRequest,
) -> list[InvestigatorCandidate]:
    selected = []

    required_investigators_lower = {
        name.lower()
        for name in request.required_investigators
    }

    for class_name in request.required_classes:
        candidates = CLASS_INVESTIGATORS.get(class_name, [])

        if not candidates:
            continue

        explicit_match = next(
            (
                candidate
                for candidate in candidates
                if candidate.investigator_name.lower() in required_investigators_lower
            ),
            None,
        )

        if explicit_match is not None:
            selected.append(explicit_match)
            continue

        selected.append(candidates[0])

    return selected