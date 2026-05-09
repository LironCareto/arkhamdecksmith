from __future__ import annotations

from collections import defaultdict

import pandas as pd

from core.models import DeckCandidate


TARGET_DECK_SIZE = 30
MAX_COPIES_PER_CARD = 2

DEFAULT_COMPOSITION_TARGETS = {
    "Asset": 14,
    "Event": 8,
    "Skill": 8,
}

CLASS_ROLE_KEYWORDS = {
    "guardian": [
        "weapon",
        "firearm",
        "melee",
        "armor",
        "ally",
        "tactic",
    ],
    "seeker": [
        "tool",
        "tome",
        "science",
        "insight",
        "practiced",
    ],
    "rogue": [
        "item",
        "illicit",
        "trick",
        "favor",
        "service",
    ],
    "mystic": [
        "spell",
        "ritual",
        "charm",
        "arcane",
    ],
    "survivor": [
        "item",
        "weapon",
        "ally",
        "fortune",
        "spirit",
        "innate",
    ],
}


def normalize_cards(cards: pd.DataFrame) -> pd.DataFrame:
    cards = cards.copy()

    cards["xp"] = pd.to_numeric(cards["xp"], errors="coerce").fillna(0).astype(int)
    cards["cost_numeric"] = pd.to_numeric(cards["cost"], errors="coerce")

    required_text_columns = [
        "code",
        "name",
        "faction_code",
        "faction_name",
        "type_code",
        "type_name",
        "subtype_name",
        "traits",
        "text",
        "real_text",
        "restrictions",
        "bonded_to",
        "bonded_cards",
        "deck_requirements",
        "deck_options",
    ]

    for column in required_text_columns:
        if column not in cards.columns:
            cards[column] = ""

        cards[column] = cards[column].fillna("").astype(str)

    return cards


def card_is_player_card(card: pd.Series) -> bool:
    return card["type_code"] not in {
        "investigator",
        "scenario",
        "enemy",
        "treachery",
        "act",
        "agenda",
        "location",
        "story",
    }


def card_is_basic_deck_card(card: pd.Series) -> bool:
    return card["type_name"] in {
        "Asset",
        "Event",
        "Skill",
    }


def card_is_level_zero(card: pd.Series) -> bool:
    return int(card["xp"]) == 0


def card_is_class_card(card: pd.Series, class_name: str) -> bool:
    return card["faction_code"].lower() == class_name.lower()


def card_has_valid_cost(card: pd.Series) -> bool:
    if card["type_name"] == "Skill":
        return True

    cost = card["cost_numeric"]

    if pd.isna(cost):
        return False

    return cost >= 0


def card_is_permanent(card: pd.Series) -> bool:
    subtype = str(card.get("subtype_name", "")).lower()
    text = str(card.get("text", "")).lower()

    return "permanent" in subtype or "permanent." in text


def card_is_signature(card: pd.Series) -> bool:
    restrictions = str(card.get("restrictions", "")).lower()

    return "investigator" in restrictions


def card_is_bonded_child(card: pd.Series) -> bool:
    bonded_to = str(card.get("bonded_to", "")).strip().lower()
    bonded_cards = str(card.get("bonded_cards", "")).strip().lower()

    return (
        bonded_to not in {"", "nan", "none"}
        or bonded_cards not in {"", "nan", "none"}
    )


def card_is_main_deck_candidate(
    card: pd.Series,
    class_name: str,
) -> bool:
    if not card_is_player_card(card):
        return False

    if not card_is_basic_deck_card(card):
        return False

    if not card_is_level_zero(card):
        return False

    if not card_is_class_card(card, class_name):
        return False

    if not card_has_valid_cost(card):
        return False

    if card_is_permanent(card):
        return False

    if card_is_signature(card):
        return False

    if card_is_bonded_child(card):
        return False

    return True


def card_priority_score(
    card: pd.Series,
    class_name: str,
) -> tuple[int, int, float, str]:
    traits = str(card.get("traits", "")).lower()
    text = str(card.get("text", "")).lower()
    combined = f"{traits} {text}"

    keywords = CLASS_ROLE_KEYWORDS.get(class_name.lower(), [])

    keyword_hit = 1

    for keyword in keywords:
        if keyword in combined:
            keyword_hit = 0
            break

    type_name = card["type_name"]

    type_priority = {
        "Asset": 0,
        "Event": 1,
        "Skill": 2,
    }.get(type_name, 9)

    cost = card["cost_numeric"]

    if pd.isna(cost):
        cost = 99

    return (
        type_priority,
        keyword_hit,
        float(cost),
        card["name"],
    )


def build_main_deck_candidate_pool(
    cards: pd.DataFrame,
    class_name: str,
) -> pd.DataFrame:
    cards = normalize_cards(cards)

    mask = cards.apply(
        lambda card: card_is_main_deck_candidate(card, class_name),
        axis=1,
    )

    candidate_cards = cards[mask].copy()

    candidate_cards["_sort_key"] = candidate_cards.apply(
        lambda card: card_priority_score(card, class_name),
        axis=1,
    )

    return candidate_cards.sort_values(
        by="_sort_key",
        ascending=True,
    )


def add_cards_by_type(
    deck_cards: dict[str, int],
    candidate_cards: pd.DataFrame,
    card_type: str,
    target_quantity: int,
) -> int:
    added = 0

    typed_cards = candidate_cards[
        candidate_cards["type_name"] == card_type
    ]

    for _, card in typed_cards.iterrows():
        if added >= target_quantity:
            break

        card_code = str(card["code"])
        current = deck_cards.get(card_code, 0)

        if current >= MAX_COPIES_PER_CARD:
            continue

        copies_to_add = min(
            MAX_COPIES_PER_CARD - current,
            target_quantity - added,
        )

        deck_cards[card_code] = current + copies_to_add
        added += copies_to_add

    return added


def fill_remaining_slots(
    deck_cards: dict[str, int],
    candidate_cards: pd.DataFrame,
) -> None:
    total_cards = sum(deck_cards.values())

    for _, card in candidate_cards.iterrows():
        if total_cards >= TARGET_DECK_SIZE:
            break

        card_code = str(card["code"])
        current = deck_cards.get(card_code, 0)

        if current >= MAX_COPIES_PER_CARD:
            continue

        deck_cards[card_code] = current + 1
        total_cards += 1


def generate_deck_for_class(
    cards: pd.DataFrame,
    investigator_name: str,
    investigator_code: str,
    class_name: str,
    intended_role: str,
) -> DeckCandidate:
    candidate_cards = build_main_deck_candidate_pool(
        cards=cards,
        class_name=class_name,
    )

    main_deck_cards: dict[str, int] = defaultdict(int)

    for card_type, target_quantity in DEFAULT_COMPOSITION_TARGETS.items():
        add_cards_by_type(
            deck_cards=main_deck_cards,
            candidate_cards=candidate_cards,
            card_type=card_type,
            target_quantity=target_quantity,
        )

    fill_remaining_slots(
        deck_cards=main_deck_cards,
        candidate_cards=candidate_cards,
    )

    return DeckCandidate(
        investigator_code=investigator_code,
        investigator_name=investigator_name,
        intended_role=intended_role,
        main_deck_cards=dict(main_deck_cards),
        signature_cards={},
        weakness_cards={},
        permanent_cards={},
        set_aside_cards={},
        xp_spent=0,
        deck_size_requirement=TARGET_DECK_SIZE,
        rationale=(
            f"Deterministic starter main deck for "
            f"{investigator_name} ({class_name}). "
            f"Signature cards and weaknesses are tracked separately."
        ),
    )