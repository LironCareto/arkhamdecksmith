from __future__ import annotations

from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from core.deck_validator import validate_deck
from core.models import DeckCandidate


def main() -> None:
    deck = DeckCandidate(
        investigator_code="01001",
        investigator_name="Roland Banks",
        intended_role="fighter",
        cards={
            "01020": 2,
            "01021": 2,
            "01022": 26,
        },
    )

    report = validate_deck(deck)

    print("\n=== VALIDATION REPORT ===\n")
    print(f"Valid: {report.is_valid}")

    for issue in report.issues:
        print(f"[{issue.severity}] {issue.code}: {issue.message}")


if __name__ == "__main__":
    main()