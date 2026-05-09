from __future__ import annotations

from core.models import (
    DeckCandidate,
    ValidationIssue,
    ValidationReport,
)

MAX_COPIES_PER_TITLE = 2


def validate_main_deck_size(
    deck: DeckCandidate,
) -> list[ValidationIssue]:
    total_cards = sum(deck.main_deck_cards.values())

    if total_cards != deck.deck_size_requirement:
        return [
            ValidationIssue(
                severity="error",
                code="INVALID_MAIN_DECK_SIZE",
                message=(
                    f"Main deck contains {total_cards} cards "
                    f"instead of {deck.deck_size_requirement}."
                ),
            )
        ]

    return []


def validate_main_deck_copies(
    deck: DeckCandidate,
) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []

    for card_code, quantity in deck.main_deck_cards.items():
        if quantity > MAX_COPIES_PER_TITLE:
            issues.append(
                ValidationIssue(
                    severity="error",
                    code="TOO_MANY_MAIN_DECK_COPIES",
                    message=(
                        f"Main deck card {card_code} has "
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

    issues.extend(validate_main_deck_size(deck))
    issues.extend(validate_main_deck_copies(deck))

    has_errors = any(
        issue.severity == "error"
        for issue in issues
    )

    return ValidationReport(
        is_valid=not has_errors,
        issues=issues,
    )