from __future__ import annotations

from core.models import (
    DeckCandidate,
    ValidationIssue,
    ValidationReport,
)

MAX_COPIES_PER_CARD = 2
STANDARD_DECK_SIZE = 30


def validate_deck_size(
    deck: DeckCandidate,
) -> list[ValidationIssue]:
    total_cards = sum(deck.cards.values())

    if total_cards != STANDARD_DECK_SIZE:
        return [
            ValidationIssue(
                severity="error",
                code="INVALID_DECK_SIZE",
                message=(
                    f"Deck contains {total_cards} cards "
                    f"instead of {STANDARD_DECK_SIZE}."
                ),
            )
        ]

    return []


def validate_card_copies(
    deck: DeckCandidate,
) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []

    for card_code, quantity in deck.cards.items():
        if quantity > MAX_COPIES_PER_CARD:
            issues.append(
                ValidationIssue(
                    severity="error",
                    code="TOO_MANY_COPIES",
                    message=(
                        f"Card {card_code} has "
                        f"{quantity} copies."
                    ),
                    card_code=card_code,
                )
            )

    return issues


def validate_deck(
    deck: DeckCandidate,
) -> ValidationReport:
    issues: list[ValidationIssue] = []

    issues.extend(validate_deck_size(deck))
    issues.extend(validate_card_copies(deck))

    has_errors = any(
        issue.severity == "error"
        for issue in issues
    )

    return ValidationReport(
        is_valid=not has_errors,
        issues=issues,
    )