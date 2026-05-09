from __future__ import annotations

from pathlib import Path
import sys

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from core.deck_generator import generate_deck_for_class
from core.deck_validator import validate_deck


CARDS_PATH = PROJECT_ROOT / "data" / "arkham_cards.tsv"


def print_card_group(
    title: str,
    card_group: dict[str, int],
    cards_by_code: pd.DataFrame,
) -> None:
    print(f"\n=== {title} ===\n")

    if not card_group:
        print("(none)")
        return

    for card_code, quantity in card_group.items():
        card = cards_by_code.loc[card_code]

        name = card.get("name", "")
        faction = card.get("faction_name", "")
        card_type = card.get("type_name", "")
        subtype = card.get("subtype_name", "")
        cost = card.get("cost", "")

        print(
            f"{quantity}x {name} "
            f"[{card_code}] "
            f"- {faction} / {card_type} / {subtype} / cost {cost}"
        )


def main() -> None:
    cards = pd.read_csv(CARDS_PATH, sep="\t", dtype=str)

    deck = generate_deck_for_class(
        cards=cards,
        investigator_name="Mark Harrigan",
        investigator_code="03001",
        class_name="guardian",
        intended_role="fighter",
    )

    report = validate_deck(deck)

    cards_by_code = cards.set_index("code", drop=False)

    print("\n=== GENERATED DECK ===\n")
    print(f"Investigator: {deck.investigator_name} ({deck.investigator_code})")
    print(f"Intended role: {deck.intended_role}")
    print(f"XP spent: {deck.xp_spent}")
    print(f"Main deck count: {sum(deck.main_deck_cards.values())}")
    print(f"Signature count: {sum(deck.signature_cards.values())}")
    print(f"Weakness count: {sum(deck.weakness_cards.values())}")
    print(f"Permanent count: {sum(deck.permanent_cards.values())}")
    print(f"Set-aside count: {sum(deck.set_aside_cards.values())}")
    print(f"Rationale: {deck.rationale}")

    print_card_group(
        title="MAIN DECK CARDS",
        card_group=deck.main_deck_cards,
        cards_by_code=cards_by_code,
    )

    print_card_group(
        title="SIGNATURE CARDS",
        card_group=deck.signature_cards,
        cards_by_code=cards_by_code,
    )

    print_card_group(
        title="WEAKNESS CARDS",
        card_group=deck.weakness_cards,
        cards_by_code=cards_by_code,
    )

    print_card_group(
        title="PERMANENT CARDS",
        card_group=deck.permanent_cards,
        cards_by_code=cards_by_code,
    )

    print_card_group(
        title="SET-ASIDE CARDS",
        card_group=deck.set_aside_cards,
        cards_by_code=cards_by_code,
    )

    print("\n=== VALIDATION ===\n")
    print(f"Valid: {report.is_valid}")

    for issue in report.issues:
        print(f"[{issue.severity}] {issue.code}: {issue.message}")


if __name__ == "__main__":
    main()