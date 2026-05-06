from __future__ import annotations

import argparse

import pandas as pd

from core.arkham_core import (
    build_card_features,
    build_deck_cards,
    fetch_public_decklist,
    get_investigator_from_decklist,
)

from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = PROJECT_ROOT / "data"
OUTPUT_DIR = PROJECT_ROOT / "outputs"

CARDS_INPUT = DATA_DIR / "arkham_cards.tsv"
DECK_PROFILE_OUTPUT = OUTPUT_DIR / "arkham_deck_profile.tsv"

DATA_DIR.mkdir(exist_ok=True)
OUTPUT_DIR.mkdir(exist_ok=True)

def parse_args():
    parser = argparse.ArgumentParser()

    parser.add_argument("--deck-url", type=str, required=True)

    return parser.parse_args()


def build_deck_profile(
    decklist: dict,
    deck_cards: pd.DataFrame,
    card_features: pd.DataFrame,
    investigator: pd.Series,
) -> pd.DataFrame:
    deck_id = str(decklist["id"])
    investigator_name = investigator["name"]

    deck_feature_rows = deck_cards[["code", "deck_quantity"]].merge(
        card_features,
        left_on="code",
        right_on="card_code",
        how="inner",
    )

    deck_feature_rows["deck_quantity"] = pd.to_numeric(
        deck_feature_rows["deck_quantity"],
        errors="coerce",
    ).fillna(0)

    deck_feature_rows["weight"] = pd.to_numeric(
        deck_feature_rows["weight"],
        errors="coerce",
    ).fillna(0)

    deck_feature_rows["weighted_value"] = (
        deck_feature_rows["deck_quantity"] * deck_feature_rows["weight"]
    )

    profile = (
        deck_feature_rows
        .groupby(["feature_type", "feature"], as_index=False)["weighted_value"]
        .sum()
        .rename(columns={"weighted_value": "value"})
    )

    profile.insert(0, "investigator", investigator_name)
    profile.insert(0, "deck_id", deck_id)

    return profile.sort_values(
        by=["feature_type", "value", "feature"],
        ascending=[True, False, True],
    )


def main() -> None:
    args = parse_args()

    cards = pd.read_csv(CARDS_INPUT, sep="\t", dtype=str)

    card_features = build_card_features(cards)

    decklist = fetch_public_decklist(args.deck_url)

    investigator = get_investigator_from_decklist(decklist, cards)

    deck_cards = build_deck_cards(decklist, cards)

    deck_profile = build_deck_profile(
        decklist=decklist,
        deck_cards=deck_cards,
        card_features=card_features,
        investigator=investigator,
    )

    deck_profile.to_csv(
        DECK_PROFILE_OUTPUT,
        sep="\t",
        index=False,
        encoding="utf-8-sig",
    )

    print(f"Saved: {DECK_PROFILE_OUTPUT}")
    print(f"Deck profile rows: {len(deck_profile)}")
    print(deck_profile.head(30))


if __name__ == "__main__":
    main()