from __future__ import annotations
from core.arkham_core import (
    build_card_features,
    fetch_public_decklist,
    get_investigator_from_decklist,
    card_is_legal_for_investigator,
)
import pandas as pd
import argparse
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = PROJECT_ROOT / "data"
OUTPUT_DIR = PROJECT_ROOT / "outputs"

DATA_DIR.mkdir(exist_ok=True)
OUTPUT_DIR.mkdir(exist_ok=True)

def parse_args():
    parser = argparse.ArgumentParser()

    parser.add_argument("--deck-url", type=str, required=True)
    parser.add_argument("--card-name", type=str, required=True)
    parser.add_argument("--card-xp", type=int, required=True)

    return parser.parse_args()

def resolve_target_card(cards: pd.DataFrame, name: str, xp: int) -> pd.Series:
    candidates = cards[
        (cards["name"].str.lower() == name.lower())
    ].copy()

    candidates["xp"] = (
        pd.to_numeric(candidates["xp"], errors="coerce")
        .fillna(0)
        .astype(int)
    )

    candidates = candidates[candidates["xp"] == xp]

    if candidates.empty:
        raise ValueError(f"Card not found: {name} (XP {xp})")

    return candidates.iloc[0]

def build_feature_matrix(features: pd.DataFrame) -> pd.DataFrame:
    return (
        features
        .pivot_table(
            index="card_code",
            columns="feature",
            values="weight",
            aggfunc="sum",
            fill_value=0,
        )
    )

def compute_similarity(target_vec, candidate_vec):
    return (target_vec * candidate_vec).sum()

def rank_alternatives(
    target_card: pd.Series,
    cards: pd.DataFrame,
    features: pd.DataFrame,
    investigator: pd.Series,
) -> pd.DataFrame:

    feature_matrix = build_feature_matrix(features)

    target_code = target_card["code"]

    target_vec = feature_matrix.loc[target_code]

    rows = []

    for _, card in cards.iterrows():
        if card["code"] == target_code:
            continue

        if not card_is_legal_for_investigator(card, investigator):
            continue

        if card["type_name"] != target_card["type_name"]:
            continue  # keep v1 simple

        if card["code"] not in feature_matrix.index:
            continue

        candidate_vec = feature_matrix.loc[card["code"]]

        score = compute_similarity(target_vec, candidate_vec)

        if score == 0:
            continue

        rows.append({
            "candidate_code": card["code"],
            "candidate_name": card["name"],
            "candidate_xp": card["xp"],
            "candidate_faction": card["faction_name"],
            "candidate_pack": card["pack_name"],
            "score": score,
            "url": card["url"],
        })

    df = pd.DataFrame(rows)

    return df.sort_values(by="score", ascending=False)


ALTERNATIVES_OUTPUT = "arkham_card_alternatives.tsv"

args = parse_args()

cards = pd.read_csv("arkham_cards.tsv", sep="\t", dtype=str)

features = build_card_features(cards)

decklist = fetch_public_decklist(args.deck_url)

investigator = get_investigator_from_decklist(decklist, cards)

target_card = resolve_target_card(
    cards,
    args.card_name,
    args.card_xp,
)

alternatives = rank_alternatives(
    target_card,
    cards,
    features,
    investigator,
)

alternatives.to_csv(ALTERNATIVES_OUTPUT, sep="\t", index=False, encoding="utf-8-sig")

print(alternatives.head(20))
