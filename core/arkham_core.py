from __future__ import annotations

import ast
import json
import re

import pandas as pd
import requests


TEXT_RULES = [
    ("action", "fight", r"\bFight\.", 1.0),
    ("action", "investigate", r"\bInvestigate\.", 1.0),
    ("action", "evade", r"\bEvade\.", 1.0),
    ("effect", "discover_clue", r"\bdiscover\b.*\bclue\b", 1.0),
    ("effect", "deal_damage", r"\bdeal\b.*\bdamage\b|\+\d+\s+damage", 1.0),
    ("effect", "draw_cards", r"\bdraw\b.*\bcard", 0.8),
    ("effect", "gain_resources", r"\bgain\b.*\bresource", 0.8),
    ("effect", "heal_damage", r"\bheal\b.*\bdamage", 0.8),
    ("effect", "heal_horror", r"\bheal\b.*\bhorror", 0.8),
    ("effect", "cancel", r"\bcancel\b", 0.8),
    ("resource", "uses_charges", r"\bUses \(\d+ charges\)", 1.0),
    ("resource", "uses_ammo", r"\bUses \(\d+ ammo\)", 1.0),
]


def safe_text(value) -> str:
    if value is None or pd.isna(value):
        return ""
    return str(value)


def build_card_identity_key(cards: pd.DataFrame) -> pd.Series:
    return cards["name"].astype("string").str.strip().str.lower()


def extract_decklist_id(decklist_url: str) -> int:
    match = re.search(r"/decklist/view/(\d+)", decklist_url)

    if not match:
        raise ValueError(f"Could not extract decklist id from URL: {decklist_url}")

    return int(match.group(1))


def fetch_public_decklist(decklist_url: str) -> dict:
    decklist_id = extract_decklist_id(decklist_url)
    api_url = f"https://arkhamdb.com/api/public/decklist/{decklist_id}.json"

    response = requests.get(api_url, timeout=30)
    response.raise_for_status()

    return response.json()


def get_investigator_from_decklist(decklist: dict, cards: pd.DataFrame) -> pd.Series:
    investigator_code = str(decklist["investigator_code"])

    investigator = cards[cards["code"] == investigator_code]

    if investigator.empty:
        raise ValueError(f"Investigator not found in card table: {investigator_code}")

    return investigator.iloc[0]


def parse_maybe_json(value):
    if value is None:
        return None

    if isinstance(value, (dict, list)):
        return value

    if pd.isna(value):
        return None

    value = str(value)

    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return ast.literal_eval(value)


def card_matches_deck_option(card: pd.Series, option: dict) -> bool:
    xp_value = pd.to_numeric(card.get("xp"), errors="coerce")
    xp = 0 if pd.isna(xp_value) else int(xp_value)

    if "level" in option:
        level = option["level"]
        min_xp = int(level.get("min", 0))
        max_xp = int(level.get("max", 5))

        if not (min_xp <= xp <= max_xp):
            return False

    if "faction" in option:
        card_factions = {
            safe_text(card.get("faction_code")),
            safe_text(card.get("faction2_code")),
            safe_text(card.get("faction3_code")),
        }

        allowed_factions = set(option["faction"])

        if card_factions.isdisjoint(allowed_factions):
            return False

    if "type" in option:
        if safe_text(card.get("type_code")) not in set(option["type"]):
            return False

    if "trait" in option:
        traits = safe_text(card.get("traits")).lower()
        allowed_traits = [trait.lower() for trait in option["trait"]]

        if not any(trait in traits for trait in allowed_traits):
            return False

    return True


def card_is_legal_for_investigator(card: pd.Series, investigator: pd.Series) -> bool:
    deck_options = parse_maybe_json(investigator.get("deck_options"))

    if not deck_options:
        return False

    return any(card_matches_deck_option(card, option) for option in deck_options)


def add_feature(
    rows: list[dict],
    card: pd.Series,
    feature_type: str,
    feature: str,
    weight: float,
    source: str,
) -> None:
    rows.append(
        {
            "card_code": card["code"],
            "card_name": card["name"],
            "card_identity_key": card["card_identity_key"],
            "feature_type": feature_type,
            "feature": feature,
            "weight": weight,
            "source": source,
        }
    )


def build_card_features(cards: pd.DataFrame) -> pd.DataFrame:
    cards = cards.copy()
    cards["card_identity_key"] = build_card_identity_key(cards)

    rows = []

    for _, card in cards.iterrows():
        for column, feature_type in [
            ("type_name", "type"),
            ("faction_name", "faction"),
            ("slot", "slot"),
        ]:
            value = safe_text(card.get(column)).strip()

            if value:
                add_feature(
                    rows,
                    card,
                    feature_type,
                    value.lower().replace(" ", "_"),
                    1.0,
                    "derived",
                )

        traits = safe_text(card.get("traits"))

        for trait in re.findall(r"([A-Za-z][A-Za-z '\-]+)\.", traits):
            add_feature(
                rows,
                card,
                "trait",
                trait.strip().lower().replace(" ", "_"),
                1.0,
                "derived",
            )

        for column, feature in [
            ("skill_willpower", "willpower_icon"),
            ("skill_intellect", "intellect_icon"),
            ("skill_combat", "combat_icon"),
            ("skill_agility", "agility_icon"),
            ("skill_wild", "wild_icon"),
        ]:
            value = pd.to_numeric(card.get(column), errors="coerce")

            if pd.notna(value) and value > 0:
                add_feature(rows, card, "skill_icon", feature, float(value), "derived")

        for column, feature in [
            ("health", "damage_soak"),
            ("sanity", "horror_soak"),
        ]:
            value = pd.to_numeric(card.get(column), errors="coerce")

            if pd.notna(value) and value > 0:
                add_feature(rows, card, "soak", feature, float(value), "derived")

        text = safe_text(card.get("text"))

        for feature_type, feature, pattern, weight in TEXT_RULES:
            if re.search(pattern, text, flags=re.IGNORECASE):
                add_feature(rows, card, feature_type, feature, weight, "rule")

    return pd.DataFrame(rows)

def build_deck_cards(decklist: dict, cards: pd.DataFrame) -> pd.DataFrame:
    slots = decklist["slots"]

    deck_rows = [
        {
            "code": str(card_code),
            "deck_quantity": quantity,
        }
        for card_code, quantity in slots.items()
    ]

    deck_cards = pd.DataFrame(deck_rows)

    return deck_cards.merge(cards, on="code", how="left")