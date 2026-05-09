from __future__ import annotations

from dataclasses import asdict

import pandas as pd

from core.models import CardRole


ROLE_PATTERNS = {
    "enemy_management": [
        "fight.",
        "fight:",
        "+1 combat",
        "+2 combat",
        "deal 1 damage",
        "deal 2 damage",
        "takes 1 damage",
    ],
    "clue": [
        "discover 1 clue",
        "discover a clue",
        "investigate.",
        "investigate:",
        "+1 intellect",
        "+2 intellect",
    ],
    "economy": [
        "gain 1 resource",
        "gain 2 resources",
        "gain 3 resources",
    ],
    "healing": [
        "heal 1 damage",
        "heal 1 horror",
        "heal 2 damage",
        "heal 2 horror",
    ],
    "defense": [
        "cancel",
        "ignore",
        "prevent",
        "evade.",
        "evade:",
    ],
    "card_draw": [
        "draw 1 card",
        "draw 2 cards",
        "search your deck",
    ],
    "mobility": [
        "move to",
        "connecting location",
        "moves to",
    ],
}


MECHANIC_PATTERNS = {
    "weapon": [
        "weapon.",
        "firearm.",
        "melee.",
    ],
    "spell": [
        "spell.",
    ],
    "ally": [
        "ally.",
    ],
    "soak": [
        "health",
        "sanity",
    ],
    "action_compression": [
        "fast.",
        "without spending an action",
        "additional action",
    ],
}


def extract_text_blob(card: pd.Series) -> str:
    fields = [
        str(card.get("name", "")),
        str(card.get("traits", "")),
        str(card.get("text", "")),
        str(card.get("real_text", "")),
    ]

    return " ".join(fields).lower()


def detect_roles(text: str) -> list[str]:
    detected = []

    for role, patterns in ROLE_PATTERNS.items():
        if any(pattern in text for pattern in patterns):
            detected.append(role)

    return detected


def detect_mechanics(text: str) -> list[str]:
    detected = []

    for mechanic, patterns in MECHANIC_PATTERNS.items():
        if any(pattern in text for pattern in patterns):
            detected.append(mechanic)

    return detected


def classify_card(card: pd.Series) -> CardRole:
    if str(card.get("type_code", "")) == "investigator":
        return CardRole(
            card_code=str(card["code"]),
            card_name=str(card["name"]),
        )

    text = extract_text_blob(card)

    roles = detect_roles(text)
    mechanics = detect_mechanics(text)

    primary_role = roles[0] if roles else None
    secondary_roles = roles[1:] if len(roles) > 1 else []

    return CardRole(
        card_code=str(card["code"]),
        card_name=str(card["name"]),
        primary_role=primary_role,
        secondary_roles=secondary_roles,
        mechanics=mechanics,
        economy_tags=[],
        tempo_tags=[],
        synergy_tags=[],
    )


def classify_cards(cards: pd.DataFrame) -> pd.DataFrame:
    rows = []

    for _, card in cards.iterrows():
        role = classify_card(card)

        rows.append(asdict(role))

    return pd.DataFrame(rows)