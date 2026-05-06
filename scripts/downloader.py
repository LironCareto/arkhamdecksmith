import argparse
import pandas as pd
import re
import requests
import ast
import json

from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = PROJECT_ROOT / "data"
OUTPUT_DIR = PROJECT_ROOT / "outputs"

DATA_DIR.mkdir(exist_ok=True)
OUTPUT_DIR.mkdir(exist_ok=True)

DEFAULT_DECKLIST_URL = None
DECK_UPGRADES_OUTPUT = "arkham_deck_upgrade_candidates.tsv"

CARDS_URL = "https://arkhamdb.com/api/public/cards/"

CARDS_OUTPUT = "arkham_cards.tsv"
UPGRADE_ROUTES_OUTPUT = "arkham_upgrade_routes.tsv"

CARD_COLUMNS = [
    "code",
    "name",
    "real_name",
    "subname",

    "type_code",
    "type_name",
    "subtype_name",

    "faction_code",
    "faction_name",
    "faction2_code",
    "faction2_name",
    "faction3_code",
    "faction3_name",

    "cost",
    "xp",
    "slot",
    "traits",
    "skill_willpower",
    "skill_intellect",
    "skill_combat",
    "skill_agility",
    "skill_wild",
    "health",
    "sanity",
    "deck_limit",
    "quantity",
    "pack_code",
    "pack_name",
    "position",
    "text",
    "url",
    "deck_options",
    "deck_requirements",
]

def parse_args():
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--deck-url",
        dest="deck_url",
        type=str,
        required=False,
        default=DEFAULT_DECKLIST_URL,
        help="Public ArkhamDB decklist URL",
    )

    return parser.parse_args()

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

    return deck_cards.merge(
        cards,
        on="code",
        how="left",
    )

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
    xp = int(card["xp"])

    if "level" in option:
        level = option["level"]

        if not (int(level.get("min", 0)) <= xp <= int(level.get("max", 5))):
            return False

    if "faction" in option:
        card_factions = {
            str(card.get("faction_code", "")),
            str(card.get("faction2_code", "")),
            str(card.get("faction3_code", "")),
        }

        allowed_factions = set(option["faction"])

        if card_factions.isdisjoint(allowed_factions):
            return False

    if "type" in option:
        if str(card.get("type_code", "")) not in set(option["type"]):
            return False

    return True


def card_is_legal_for_investigator(card: pd.Series, investigator: pd.Series) -> bool:
    deck_options = parse_maybe_json(investigator["deck_options"])

    if not deck_options:
        return False

    for option in deck_options:
        if card_matches_deck_option(card, option):
            return True

    return False

def build_deck_upgrade_candidates(
    deck_cards: pd.DataFrame,
    cards: pd.DataFrame,
    investigator: pd.Series,
) -> pd.DataFrame:
    all_cards = cards.copy()
    deck_cards = deck_cards.copy()

    all_cards["xp"] = (
        pd.to_numeric(all_cards["xp"], errors="coerce")
        .fillna(0)
        .astype(int)
    )

    deck_cards["xp"] = (
        pd.to_numeric(deck_cards["xp"], errors="coerce")
        .fillna(0)
        .astype(int)
    )

    all_cards["card_identity_key"] = build_card_identity_key(all_cards)
    deck_cards["card_identity_key"] = build_card_identity_key(deck_cards)

    upgrade_pool = all_cards[
        all_cards["type_name"].isin(["Asset", "Event", "Skill"])
    ].copy()

    rows = []

    for _, deck_card in deck_cards.iterrows():
        possible_upgrades = upgrade_pool[
            (upgrade_pool["card_identity_key"] == deck_card["card_identity_key"])
            & (upgrade_pool["xp"] > deck_card["xp"])
        ].copy()

        for _, upgrade_card in possible_upgrades.iterrows():
            if not card_is_legal_for_investigator(upgrade_card, investigator):
                continue

            rows.append({
                "deck_card_code": deck_card["code"],
                "deck_card_name": deck_card["name"],
                "deck_quantity": deck_card["deck_quantity"],
                "deck_card_xp": deck_card["xp"],
                "deck_card_pack": deck_card["pack_name"],
                "upgrade_code": upgrade_card["code"],
                "upgrade_name": upgrade_card["name"],
                "upgrade_xp": upgrade_card["xp"],
                "xp_difference": upgrade_card["xp"] - deck_card["xp"],
                "upgrade_faction": upgrade_card["faction_name"],
                "upgrade_pack": upgrade_card["pack_name"],
                "upgrade_url": upgrade_card["url"],
            })

    return pd.DataFrame(rows)

def write_tsv(df: pd.DataFrame, path: str) -> None:
    df.to_csv(
        path,
        sep="\t",
        index=False,
        encoding="utf-8-sig"
    )


def build_card_identity_key(df: pd.DataFrame) -> pd.Series:
    return (
        df["name"]
        .astype("string")
        .str.strip()
        .str.lower()
    )


def build_upgrade_routes(cards: pd.DataFrame) -> pd.DataFrame:
    upgrade_cards = cards.copy()

    upgrade_cards["xp"] = (
        pd.to_numeric(upgrade_cards["xp"], errors="coerce")
        .fillna(0)
        .astype(int)
    )

    upgrade_cards["card_identity_key"] = build_card_identity_key(upgrade_cards)

    upgrade_cards = upgrade_cards[
        upgrade_cards["type_name"].isin(["Asset", "Event", "Skill"])
    ].copy()

    routes = []

    for card_identity_key, group in upgrade_cards.groupby("card_identity_key"):
        xp_levels = sorted(group["xp"].unique())

        if len(xp_levels) < 2:
            continue

        for from_xp in xp_levels:
            for to_xp in xp_levels:
                if to_xp <= from_xp:
                    continue

                from_cards = group[group["xp"] == from_xp]
                to_cards = group[group["xp"] == to_xp]

                routes.append({
                    "card_identity_key": card_identity_key,
                    "card_name": group["name"].iloc[0],
                    "from_xp": from_xp,
                    "to_xp": to_xp,
                    "xp_difference": to_xp - from_xp,
                    "from_codes": "|".join(from_cards["code"].astype(str)),
                    "to_codes": "|".join(to_cards["code"].astype(str)),
                    "from_pack_names": "|".join(sorted(from_cards["pack_name"].dropna().unique())),
                    "to_pack_names": "|".join(sorted(to_cards["pack_name"].dropna().unique())),
                    "from_urls": "|".join(from_cards["url"].astype(str)),
                    "to_urls": "|".join(to_cards["url"].astype(str)),
                })

    return pd.DataFrame(routes)

def main() -> None:
    args = parse_args()

    cards = pd.read_json(CARDS_URL)

    existing_columns = [c for c in CARD_COLUMNS if c in cards.columns]

    cards = cards[existing_columns].copy()
    cards = cards.loc[:, ~cards.columns.duplicated()].copy()

    write_tsv(cards, CARDS_OUTPUT)

    upgrade_routes = build_upgrade_routes(cards)
    write_tsv(upgrade_routes, UPGRADE_ROUTES_OUTPUT)

    print(f"Saved: {CARDS_OUTPUT}")
    print(f"Card rows: {len(cards)}")

    print(f"Saved: {UPGRADE_ROUTES_OUTPUT}")
    print(f"Upgrade rows: {len(upgrade_routes)}")

    if args.deck_url:
        decklist = fetch_public_decklist(args.deck_url)

        deck_cards = build_deck_cards(decklist, cards)

        investigator = get_investigator_from_decklist(decklist, cards)

        deck_upgrade_candidates = build_deck_upgrade_candidates(
            deck_cards,
            cards,
            investigator,
        )

        write_tsv(deck_upgrade_candidates, DECK_UPGRADES_OUTPUT)

        print(f"Saved: {DECK_UPGRADES_OUTPUT}")
        print(f"Deck upgrade candidate rows: {len(deck_upgrade_candidates)}")

if __name__ == "__main__":
    main()