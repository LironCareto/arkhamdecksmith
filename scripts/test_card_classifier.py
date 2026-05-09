from __future__ import annotations

from pathlib import Path
import sys

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from core.card_role_classifier import classify_cards


CARDS_PATH = PROJECT_ROOT / "data" / "arkham_cards.tsv"


def main() -> None:
    cards = pd.read_csv(CARDS_PATH, sep="\t", dtype=str)

    classified = classify_cards(cards)

    interesting = classified[
        classified["primary_role"].notna()
    ]

    print(
        interesting[
            [
                "card_name",
                "primary_role",
                "secondary_roles",
                "mechanics",
            ]
        ]
        .head(50)
        .to_string(index=False)
    )


if __name__ == "__main__":
    main()