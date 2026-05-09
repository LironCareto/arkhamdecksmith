from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

from core.arkham_core import (
    build_card_features,
    build_deck_cards,
    fetch_public_decklist,
    get_investigator_from_decklist,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = PROJECT_ROOT / "data"
OUTPUT_DIR = PROJECT_ROOT / "outputs"

CARDS_INPUT = DATA_DIR / "arkham_cards.tsv"
DECK_PROFILE_OUTPUT = OUTPUT_DIR / "arkham_deck_profile.tsv"
DECK_METRICS_OUTPUT = OUTPUT_DIR / "arkham_deck_metrics.tsv"

DATA_DIR.mkdir(exist_ok=True)
OUTPUT_DIR.mkdir(exist_ok=True)


ROLE_FEATURE_MAPPING = {
    "combat": {
        "fight": 1.0,
        "deal_damage": 1.0,
        "combat_icon": 0.25,
        "wild_icon": 0.25,
    },
    "clue": {
        "investigate": 1.0,
        "discover_clue": 1.0,
        "intellect_icon": 0.25,
        "wild_icon": 0.25,
    },
    "economy": {
        "gain_resources": 1.0,
    },
    "consistency": {
        "draw_cards": 1.0,
        "wild_icon": 0.15,
    },
    "survival": {
        "damage_soak": 1.0,
        "horror_soak": 1.0,
        "heal_damage": 0.75,
        "heal_horror": 0.75,
        "cancel": 0.75,
        "willpower_icon": 0.2,
        "wild_icon": 0.2,
    },
}


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


def get_profile_value(
    deck_profile: pd.DataFrame,
    feature: str,
) -> float:
    rows = deck_profile[deck_profile["feature"] == feature]

    if rows.empty:
        return 0.0

    return float(rows["value"].sum())


def build_deck_metrics(
    decklist: dict,
    deck_cards: pd.DataFrame,
    deck_profile: pd.DataFrame,
    investigator: pd.Series,
) -> pd.DataFrame:
    deck_id = str(decklist["id"])
    investigator_name = investigator["name"]

    rows = []

    def add_metric(metric_group: str, metric: str, value: float) -> None:
        rows.append(
            {
                "deck_id": deck_id,
                "investigator": investigator_name,
                "metric_group": metric_group,
                "metric": metric,
                "value": float(value),
            }
        )

    for role, feature_weights in ROLE_FEATURE_MAPPING.items():
        role_score = 0.0

        for feature, role_weight in feature_weights.items():
            role_score += get_profile_value(deck_profile, feature) * role_weight

        add_metric("role", f"{role}_score", role_score)

    cards = deck_cards.copy()

    cards["deck_quantity"] = pd.to_numeric(
        cards["deck_quantity"],
        errors="coerce",
    ).fillna(0)

    cards["cost_numeric"] = pd.to_numeric(
        cards["cost"],
        errors="coerce",
    )

    playable_cards = cards[
        cards["type_name"].isin(["Asset", "Event"])
        & cards["cost_numeric"].notna()
    ].copy()

    playable_cards["weighted_cost"] = (
        playable_cards["deck_quantity"] * playable_cards["cost_numeric"]
    )

    total_play_cost = playable_cards["weighted_cost"].sum()
    playable_card_copies = playable_cards["deck_quantity"].sum()

    average_play_cost = (
        total_play_cost / playable_card_copies
        if playable_card_copies > 0
        else 0.0
    )

    add_metric("economy", "total_play_cost", total_play_cost)
    add_metric("economy", "playable_card_copies", playable_card_copies)
    add_metric("economy", "average_play_cost", average_play_cost)
    add_metric("economy", "economy_supply", get_profile_value(deck_profile, "gain_resources"))

    for cost_value in [0, 1, 2, 3]:
        count = playable_cards.loc[
            playable_cards["cost_numeric"] == cost_value,
            "deck_quantity",
        ].sum()

        add_metric("cost_curve", f"cost_{cost_value}_count", count)

    cost_4plus_count = playable_cards.loc[
        playable_cards["cost_numeric"] >= 4,
        "deck_quantity",
    ].sum()

    add_metric("cost_curve", "cost_4plus_count", cost_4plus_count)

    for icon_feature in [
        "willpower_icon",
        "intellect_icon",
        "combat_icon",
        "agility_icon",
        "wild_icon",
    ]:
        add_metric("skill_icons", icon_feature, get_profile_value(deck_profile, icon_feature))

    for soak_feature in [
        "damage_soak",
        "horror_soak",
    ]:
        add_metric("survival", soak_feature, get_profile_value(deck_profile, soak_feature))

    for slot_feature in [
        "hand",
        "arcane",
        "ally",
        "body",
        "accessory",
    ]:
        add_metric("slot_pressure", f"{slot_feature}_slots", get_profile_value(deck_profile, slot_feature))

    for card_type in [
        "asset",
        "event",
        "skill",
    ]:
        add_metric("card_type_distribution", f"{card_type}_count", get_profile_value(deck_profile, card_type))

    return pd.DataFrame(rows)


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

    deck_metrics = build_deck_metrics(
        decklist=decklist,
        deck_cards=deck_cards,
        deck_profile=deck_profile,
        investigator=investigator,
    )

    deck_profile.to_csv(
        DECK_PROFILE_OUTPUT,
        sep="\t",
        index=False,
        encoding="utf-8-sig",
    )

    deck_metrics.to_csv(
        DECK_METRICS_OUTPUT,
        sep="\t",
        index=False,
        encoding="utf-8-sig",
    )

    print(f"Saved: {DECK_PROFILE_OUTPUT}")
    print(f"Deck profile rows: {len(deck_profile)}")

    print(f"Saved: {DECK_METRICS_OUTPUT}")
    print(f"Deck metrics rows: {len(deck_metrics)}")

    print(deck_metrics)


if __name__ == "__main__":
    main()