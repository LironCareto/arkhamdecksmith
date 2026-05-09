from __future__ import annotations

import argparse
import ast
import json
from pathlib import Path
from typing import Any

import pandas as pd

from core.arkham_core import (
    build_card_features,
    fetch_public_decklist,
    get_investigator_from_decklist,
    card_is_legal_for_investigator,
)

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = PROJECT_ROOT / "data"
OUTPUT_DIR = PROJECT_ROOT / "outputs"

DATA_DIR.mkdir(exist_ok=True)
OUTPUT_DIR.mkdir(exist_ok=True)

CARDS_INPUT = "arkham_cards.tsv"
ALTERNATIVES_OUTPUT = "arkham_card_alternatives.tsv"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()

    parser.add_argument("--deck-url", type=str, required=True)
    parser.add_argument("--card-name", type=str, required=True)
    parser.add_argument("--card-xp", type=int, required=True)

    parser.add_argument(
        "--max-xp-spend",
        type=int,
        default=0,
        help="Maximum additional XP allowed for the replacement card. Use 0 for beginner decks.",
    )

    return parser.parse_args()


def normalize_cards(cards: pd.DataFrame) -> pd.DataFrame:
    cards = cards.copy()
    cards["xp"] = pd.to_numeric(cards["xp"], errors="coerce").fillna(0).astype(int)
    cards["code"] = cards["code"].astype(str)
    return cards


def parse_jsonish(value: Any) -> Any:
    if value is None or pd.isna(value):
        return None

    if isinstance(value, (dict, list)):
        return value

    text = str(value).strip()

    if not text:
        return None

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    try:
        return ast.literal_eval(text)
    except (ValueError, SyntaxError):
        return None


def resolve_target_card(cards: pd.DataFrame, name: str, xp: int) -> pd.Series:
    candidates = cards[cards["name"].str.lower() == name.lower()].copy()
    candidates = candidates[candidates["xp"] == xp]

    if candidates.empty:
        raise ValueError(f"Card not found: {name} (XP {xp})")

    if len(candidates) > 1:
        print(f"Warning: multiple cards found for {name} XP {xp}; using first match.")

    return candidates.iloc[0]


def build_feature_matrix(features: pd.DataFrame) -> pd.DataFrame:
    return features.pivot_table(
        index="card_code",
        columns="feature",
        values="weight",
        aggfunc="sum",
        fill_value=0,
    )


def compute_similarity(target_vec: pd.Series, candidate_vec: pd.Series) -> float:
    return float((target_vec * candidate_vec).sum())


def get_deck_slots(decklist: dict[str, Any]) -> dict[str, int]:
    slots = decklist.get("slots")

    if not isinstance(slots, dict):
        raise ValueError("Decklist does not contain a valid 'slots' dictionary.")

    return {str(card_code): int(quantity) for card_code, quantity in slots.items()}


def get_deck_options(investigator: pd.Series) -> list[dict[str, Any]]:
    options = parse_jsonish(investigator.get("deck_options"))

    if not isinstance(options, list):
        raise ValueError(
            "Investigator does not contain parseable deck_options. "
            "Cannot validate limited deckbuilding slots safely."
        )

    return [option for option in options if isinstance(option, dict)]


def option_has_limit(option: dict[str, Any]) -> bool:
    return option.get("limit") is not None


def card_matches_option(card: pd.Series, option: dict[str, Any]) -> bool:
    faction = option.get("faction")
    level = option.get("level")

    card_faction = str(card.get("faction_code", "")).lower()
    card_xp = int(card.get("xp", 0))

    if faction is not None:
        allowed_factions = faction if isinstance(faction, list) else [faction]
        allowed_factions = [str(item).lower() for item in allowed_factions]

        if card_faction not in allowed_factions:
            return False

    if isinstance(level, dict):
        min_level = int(level.get("min", 0))
        max_level = int(level.get("max", 99))

        if not min_level <= card_xp <= max_level:
            return False

    return True


def deck_respects_limited_slots(
    deck_slots: dict[str, int],
    cards_by_code: dict[str, pd.Series],
    investigator: pd.Series,
) -> bool:
    deck_options = get_deck_options(investigator)

    unlimited_options = [
        option
        for option in deck_options
        if not option_has_limit(option)
    ]

    limited_options = [
        option
        for option in deck_options
        if option_has_limit(option)
    ]

    limited_usage = [0 for _ in limited_options]

    for card_code, quantity in deck_slots.items():
        card = cards_by_code.get(card_code)

        if card is None:
            continue

        if any(card_matches_option(card, option) for option in unlimited_options):
            continue

        matching_limited_indexes = [
            index
            for index, option in enumerate(limited_options)
            if card_matches_option(card, option)
        ]

        if not matching_limited_indexes:
            return False

        selected_index = matching_limited_indexes[0]
        limited_usage[selected_index] += quantity

    for usage, option in zip(limited_usage, limited_options):
        limit = int(option["limit"])

        if usage > limit:
            return False

    return True


def simulate_swap(
    deck_slots: dict[str, int],
    target_code: str,
    candidate_code: str,
) -> dict[str, int]:
    simulated = dict(deck_slots)

    if simulated.get(target_code, 0) <= 0:
        raise ValueError(f"Target card {target_code} is not present in the decklist.")

    simulated[target_code] -= 1

    if simulated[target_code] == 0:
        del simulated[target_code]

    simulated[candidate_code] = simulated.get(candidate_code, 0) + 1

    return simulated


def card_is_investigator_specific(card: pd.Series) -> bool:
    restrictions = str(card.get("restrictions", "")).lower()
    real_text = str(card.get("real_text", "")).lower()
    text = f"{restrictions} {real_text}"

    return "deck only" in text


def card_is_bonded_child(card: pd.Series) -> bool:
    bonded_to = str(card.get("bonded_to", "")).strip().lower()
    bonded = str(card.get("bonded", "")).strip().lower()

    return (
        bonded_to not in {"", "nan", "none"}
        or bonded in {"1", "true", "yes"}
    )


def candidate_is_allowed_for_recommendation(
    card: pd.Series,
    target_card: pd.Series,
    investigator: pd.Series,
    feature_matrix: pd.DataFrame,
    deck_slots: dict[str, int],
    cards_by_code: dict[str, pd.Series],
    max_xp_spend: int,
) -> tuple[bool, int]:
    candidate_code = str(card["code"])
    target_code = str(target_card["code"])

    if candidate_code == target_code:
        return False, 0

    if card.get("type_name") != target_card.get("type_name"):
        return False, 0

    if card_is_investigator_specific(card):
        return False, 0

    if card_is_bonded_child(card):
        return False, 0

    candidate_xp = int(card["xp"])
    target_xp = int(target_card["xp"])
    additional_xp = max(0, candidate_xp - target_xp)

    if additional_xp > max_xp_spend:
        return False, additional_xp

    if not card_is_legal_for_investigator(card, investigator):
        return False, additional_xp

    if candidate_code not in feature_matrix.index:
        return False, additional_xp

    simulated_deck = simulate_swap(
        deck_slots=deck_slots,
        target_code=target_code,
        candidate_code=candidate_code,
    )

    if not deck_respects_limited_slots(
        deck_slots=simulated_deck,
        cards_by_code=cards_by_code,
        investigator=investigator,
    ):
        return False, additional_xp

    return True, additional_xp


def rank_alternatives(
    target_card: pd.Series,
    cards: pd.DataFrame,
    features: pd.DataFrame,
    investigator: pd.Series,
    deck_slots: dict[str, int],
    max_xp_spend: int,
) -> pd.DataFrame:
    feature_matrix = build_feature_matrix(features)

    target_code = str(target_card["code"])

    if target_code not in feature_matrix.index:
        raise ValueError(f"Target card has no generated features: {target_card['name']}")

    target_vec = feature_matrix.loc[target_code]

    cards_by_code = {
        str(card["code"]): card
        for _, card in cards.iterrows()
    }

    rows = []

    for _, card in cards.iterrows():
        candidate_code = str(card["code"])

        allowed, additional_xp = candidate_is_allowed_for_recommendation(
            card=card,
            target_card=target_card,
            investigator=investigator,
            feature_matrix=feature_matrix,
            deck_slots=deck_slots,
            cards_by_code=cards_by_code,
            max_xp_spend=max_xp_spend,
        )

        if not allowed:
            continue

        candidate_vec = feature_matrix.loc[candidate_code]
        score = compute_similarity(target_vec, candidate_vec)

        if score == 0:
            continue

        rows.append({
            "candidate_code": candidate_code,
            "candidate_name": card["name"],
            "candidate_xp": int(card["xp"]),
            "additional_xp": additional_xp,
            "candidate_faction": card.get("faction_name", ""),
            "candidate_pack": card.get("pack_name", ""),
            "score": score,
            "url": card.get("url", ""),
        })

    alternatives = pd.DataFrame(rows)

    if alternatives.empty:
        return alternatives

    return alternatives.sort_values(
        by=["score", "additional_xp", "candidate_name"],
        ascending=[False, True, True],
    )


def main() -> None:
    args = parse_args()

    cards = pd.read_csv(CARDS_INPUT, sep="\t", dtype=str)
    cards = normalize_cards(cards)

    features = build_card_features(cards)

    decklist = fetch_public_decklist(args.deck_url)
    deck_slots = get_deck_slots(decklist)

    investigator = get_investigator_from_decklist(decklist, cards)

    target_card = resolve_target_card(
        cards=cards,
        name=args.card_name,
        xp=args.card_xp,
    )

    alternatives = rank_alternatives(
        target_card=target_card,
        cards=cards,
        features=features,
        investigator=investigator,
        deck_slots=deck_slots,
        max_xp_spend=args.max_xp_spend,
    )

    alternatives.to_csv(
        ALTERNATIVES_OUTPUT,
        sep="\t",
        index=False,
        encoding="utf-8-sig",
    )

    print(alternatives.head(20))


if __name__ == "__main__":
    main()